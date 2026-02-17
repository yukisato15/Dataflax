#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based folder analyzer with multiple folder selection and dry-run support
Enhanced version with Sort/Flatten operations
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pathlib import Path
import sys
import json
import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
import shutil
import time
from threading import Event

from .folder_tools import (
    FolderNameDeleteDialog,
    MATCH_EXACT,
    remove_folders_matching_query,
)

# Import the scanner from core module
sys.path.append(str(Path(__file__).parent.parent))
from core.scanner import FileScanner
from core.processor import FileProcessor

# Safe imports for optional core.processor functions
try:
    from core.processor import perform_sort as _core_perform_sort
    from core.processor import perform_flatten as _core_perform_flatten
except Exception:
    _core_perform_sort = None
    _core_perform_flatten = None


# Internal fallback implementations
def _unique_path(dest_dir: Path, name: str) -> Path:
    """Generate unique file path to avoid overwriting"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(name).stem
    suffix = Path(name).suffix
    candidate = dest_dir / name
    counter = 1
    while candidate.exists():
        candidate = dest_dir / f"{stem}_{counter:02d}{suffix}"
        counter += 1
    return candidate


def _op_copy(src: Path, dst: Path):
    """Copy file operation"""
    shutil.copy2(str(src), str(dst))


def _op_move(src: Path, dst: Path):
    """Move file operation"""
    shutil.move(str(src), str(dst))


def _op_link(src: Path, dst: Path):
    """Create symbolic link operation"""
    dst.symlink_to(src)


class ScannerThread(QThread):
    """複数フォルダ対応の非同期走査スレッド"""
    
    # シグナル定義
    scan_started = Signal(int)               # 総ファイル数
    progress_updated = Signal(int, int, str) # 処理済み, 総数, 現在ファイル
    counting_progress = Signal(int, int, str) # 計測済みフォルダ数, 総フォルダ数, 現在フォルダ
    scan_completed = Signal(dict, float)     # 走査結果, 所要時間
    scan_cancelled = Signal(dict)            # 中止時の部分結果
    error_occurred = Signal(str)             # エラーメッセージ
    log_ready = Signal(str)                  # ログファイルパス
    
    def __init__(self, paths: List[Path]):
        super().__init__()
        self.paths = paths if isinstance(paths, list) else [paths]
        self.scanner = FileScanner()
        self.cancel_event = Event()
        self._log_entries: List[str] = []
        self._processed_files: int = 0
        self._total_files: int = 0

    def _accumulate_single_file(self, stats: Dict[str, Dict[str, Any]], file_path: Path):
        """単一ファイルを集計に追加"""
        if FileScanner.is_hidden(file_path):
            return
        try:
            if not file_path.is_file():
                return
            ext = file_path.suffix.lower()
            media_type = FileScanner.detect_media_type(ext)
            size = file_path.stat().st_size
            stats[media_type]["count"] += 1
            stats[media_type]["size"] += size
            stats[media_type]["extensions"][ext] += 1
            stats[media_type]["files"].append(str(file_path))
        except Exception:
            return

    def request_cancel(self):
        """ユーザーからのキャンセル要求"""
        self.cancel_event.set()

    def _append_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_entries.append(f"[{timestamp}] {message}")

    def _finalize_log(self, status: str, elapsed: float) -> Optional[Path]:
        try:
            project_root = Path(__file__).resolve().parent.parent
            log_dir = project_root / "logs"
            log_dir.mkdir(exist_ok=True)
            summary = (
                f"status={status} total_files={self._total_files} "
                f"processed={self._processed_files} elapsed={elapsed:.2f}s"
            )
            self._log_entries.append(summary)
            log_path = log_dir / f"analyzer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            log_path.write_text("\n".join(self._log_entries), encoding="utf-8")
            return log_path
        except Exception:
            return None

    def run(self):
        """複数フォルダを順次走査してマージ"""
        start_time = time.monotonic()
        self._log_entries = []
        self._append_log(f"scan start (targets={len(self.paths)})")

        try:
            dir_counts = []
            total_files = 0
            total_dirs = max(len(self.paths), 1)
            for index, path in enumerate(self.paths, start=1):
                if self.cancel_event.is_set():
                    break
                self.counting_progress.emit(index - 1, total_dirs, str(path))
                if path.exists() and path.is_file():
                    count = 1 if not FileScanner.is_hidden(path) else 0
                else:
                    count = FileScanner.count_files(path, self.cancel_event)
                dir_counts.append((path, count))
                total_files += count
                self._append_log(f"counted {count} files in {path}")
                self.counting_progress.emit(index, total_dirs, str(path))

            self._total_files = total_files

            if self.cancel_event.is_set():
                elapsed = time.monotonic() - start_time
                log_path = self._finalize_log("cancelled", elapsed)
                if log_path:
                    self.log_ready.emit(str(log_path))
                self.scan_cancelled.emit({})
                return

            self.scan_started.emit(total_files)

            combined_stats = defaultdict(lambda: {
                "count": 0,
                "size": 0,
                "extensions": defaultdict(int),
                "files": [],
                "source_folders": set(),
            })

            processed_offset = 0
            processed_global = 0

            for path, dir_total in dir_counts:
                if self.cancel_event.is_set():
                    break

                if path.exists() and path.is_file():
                    self._accumulate_single_file(combined_stats, path)
                    processed_offset += dir_total
                    self._processed_files = processed_offset
                    self.progress_updated.emit(processed_offset, total_files, str(path))
                    self._append_log(f"processed {processed_offset} / {total_files} files")
                    continue

                def wrapped_callback(processed: int, _total: int, current: str):
                    nonlocal processed_global
                    processed_global = processed_offset + processed
                    self._processed_files = processed_global
                    self.progress_updated.emit(processed_global, total_files, current)

                stats = self.scanner.scan_directory(
                    path,
                    wrapped_callback,
                    self.cancel_event,
                )

                for media_type, data in stats.items():
                    bucket = combined_stats[media_type]
                    bucket["count"] += data["count"]
                    bucket["size"] += data["size"]
                    bucket["files"].extend(data["files"])
                    bucket["source_folders"].add(str(path))

                    for ext, count in data["extensions"].items():
                        bucket["extensions"][ext] += count

                processed_offset += dir_total if dir_total else sum(d["count"] for d in stats.values())
                self._append_log(f"processed {processed_offset} / {total_files} files")

            self._processed_files = processed_offset
            
            elapsed = time.monotonic() - start_time

            if self.cancel_event.is_set():
                final_stats = {}
                for media_type, data in combined_stats.items():
                    final_stats[media_type] = {
                        "count": data["count"],
                        "size": data["size"],
                        "extensions": dict(data["extensions"]),
                        "files": data["files"],
                        "source_folders": list(data["source_folders"]),
                    }
                log_path = self._finalize_log("cancelled", elapsed)
                if log_path:
                    self.log_ready.emit(str(log_path))
                self.scan_cancelled.emit(final_stats)
                return

            final_stats = {}
            for media_type, data in combined_stats.items():
                final_stats[media_type] = {
                    "count": data["count"],
                    "size": data["size"],
                    "extensions": dict(data["extensions"]),
                    "files": data["files"],
                    "source_folders": list(data["source_folders"]),
                }

            log_path = self._finalize_log("completed", elapsed)
            if log_path:
                self.log_ready.emit(str(log_path))

            self.scan_completed.emit(final_stats, elapsed)

        except Exception as e:
            elapsed = time.monotonic() - start_time
            self._append_log(f"error: {e}")
            log_path = self._finalize_log("error", elapsed)
            if log_path:
                self.log_ready.emit(str(log_path))
            self.error_occurred.emit(str(e))


# DropAreaWidgetクラスを削除 - シンプルなQListWidgetで置き換え


class OutputFolderDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("出力フォルダ設定")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)
        self.folder_edits = {}
        media_types = sorted({it["media"] for it in items})
        for media in media_types:
            edit = QLineEdit(media.lower())
            self.folder_edits[media] = edit
            layout.addRow(f"{media}：", edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get_folder_names(self) -> Dict[str, str]:
        return {media: edit.text().strip() for media, edit in self.folder_edits.items()}


class DryRunPreviewDialog(QDialog):
    """Dry-runプレビューダイアログ"""
    
    def __init__(self, operation: str, selected_items: List[Dict], parent=None):
        super().__init__(parent)
        self.operation = operation
        self.selected_items = selected_items
        
        self.setWindowTitle(f"🧪 Dry-run Preview: {operation}")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # ヘッダー
        header_label = QLabel(f"🔍 {self.operation} 操作プレビュー")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(header_label)
        
        # 概要情報
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Box)
        info_layout = QVBoxLayout(info_frame)
        
        info_text = f"""
📊 操作概要:
• 対象項目: {len(self.selected_items)}個
• モード: Dry-run (実際の操作は行いません)
• 操作タイプ: {self.operation}
• 実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        info_label = QLabel(info_text.strip())
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_frame)
        
        # 詳細リスト
        detail_label = QLabel("🗂️ 処理対象詳細:")
        detail_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(detail_label)
        
        # テーブルビュー
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(4)
        self.detail_table.setHorizontalHeaderLabels(["媒体タイプ", "拡張子", "ファイル数", "推定処理"])
        
        self.populate_detail_table()
        
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.resizeColumnsToContents()
        layout.addWidget(self.detail_table)
        
        # ボタン
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 CSV保存")
        save_btn.clicked.connect(self.save_to_csv)
        button_layout.addWidget(save_btn)
        
        json_btn = QPushButton("📄 JSON保存")
        json_btn.clicked.connect(self.save_to_json)
        button_layout.addWidget(json_btn)
        
        button_layout.addStretch()
        
        execute_btn = QPushButton("⚡ 実行する")
        execute_btn.clicked.connect(self.execute_operation)
        execute_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px;")
        button_layout.addWidget(execute_btn)
        
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def populate_detail_table(self):
        """詳細テーブルにデータを設定"""
        self.detail_table.setRowCount(len(self.selected_items))
        
        for i, item in enumerate(self.selected_items):
            media_type = item.get('parent', item.get('type', 'unknown'))
            extension = item.get('type') if item.get('parent') else 'すべて'
            count = item.get('count', '0')
            
            # 推定処理内容
            if self.operation == "Sort":
                estimated_action = f"{media_type}フォルダに移動"
            elif self.operation == "Flatten":
                estimated_action = "親ディレクトリに展開"
            else:
                estimated_action = "カスタム処理"
            
            self.detail_table.setItem(i, 0, QTableWidgetItem(media_type))
            self.detail_table.setItem(i, 1, QTableWidgetItem(extension))
            self.detail_table.setItem(i, 2, QTableWidgetItem(str(count)))
            self.detail_table.setItem(i, 3, QTableWidgetItem(estimated_action))
            
    def save_to_csv(self):
        """CSV形式で保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dryrun_{self.operation.lower()}_{timestamp}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Dry-run結果をCSV保存", filename, "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # ヘッダー
                    writer.writerow(['操作タイプ', '媒体タイプ', '拡張子', 'ファイル数', '推定処理', 'タイムスタンプ'])
                    
                    # データ
                    for item in self.selected_items:
                        media_type = item.get('parent', item.get('type', 'unknown'))
                        extension = item.get('type') if item.get('parent') else 'すべて'
                        count = item.get('count', '0')
                        estimated_action = f"{media_type}フォルダに移動" if self.operation == "Sort" else "親ディレクトリに展開"
                        
                        writer.writerow([
                            self.operation, media_type, extension, count, 
                            estimated_action, datetime.now().isoformat()
                        ])
                
                QMessageBox.information(self, "保存完了", f"Dry-run結果をCSVファイルに保存しました:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "保存エラー", f"CSV保存エラー: {e}")
                
    def save_to_json(self):
        """JSON形式で保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dryrun_{self.operation.lower()}_{timestamp}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Dry-run結果をJSON保存", filename, "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                data = {
                    "operation": self.operation,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "dry_run",
                    "selected_items": self.selected_items,
                    "summary": {
                        "total_items": len(self.selected_items),
                        "total_files": sum(int(item.get('count', 0)) for item in self.selected_items)
                    }
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "保存完了", f"Dry-run結果をJSONファイルに保存しました:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "保存エラー", f"JSON保存エラー: {e}")
                
    def execute_operation(self):
        """実際の操作を実行（ダイアログを閉じて親に通知）"""
        reply = QMessageBox.question(
            self, "実行確認", 
            f"Dry-runを終了して実際の{self.operation}操作を実行しますか?\n\n"
            f"対象: {len(self.selected_items)}項目\n"
            f"この操作は元に戻せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.accept()  # ダイアログを閉じて、親ウィンドウで実際の処理を実行


class TemplateBuildDialog(QDialog):
    """Template-driven folder build settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("テンプレート構築設定（整理ルール）")
        self.setMinimumWidth(760)
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("出力フォルダの構築ルール（テンプレート構築）")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        desc = QLabel("ファイルをテンプレートに沿ってコピー/移動し、フォルダ構造を自動生成します。まずは「かんたん設定」から始め、必要時のみ詳細設定を使ってください。")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        quick_group = QGroupBox("かんたん設定（最初はここだけでOK）")
        quick_layout = QFormLayout(quick_group)
        self.easy_pattern_combo = QComboBox()
        self.easy_pattern_combo.addItems(
            [
                "種類 → 年月で整理（おすすめ）",
                "年月で整理",
                "種類で整理",
                "拡張子で整理",
                "元フォルダ名を活かす",
                "カスタム（下のテンプレートを直接入力）",
            ]
        )
        quick_layout.addRow("整理パターン:", self.easy_pattern_combo)

        self.easy_preview_label = QLabel("")
        self.easy_preview_label.setStyleSheet("color: #9fb3c8;")
        self.easy_preview_label.setWordWrap(True)
        quick_layout.addRow("プレビュー:", self.easy_preview_label)
        layout.addWidget(quick_group)

        form = QFormLayout()
        self.template_edit = QLineEdit("{media_type}/{year}/{month}/{ext}")
        self.template_edit.setPlaceholderText("{media_type}/{year}/{month}/{ext}")
        form.addRow("カスタムテンプレート（出力パス）:", self.template_edit)

        self.unknown_edit = QLineEdit("unknown")
        self.unknown_edit.setPlaceholderText("unknown")
        form.addRow("値がない時の文字:", self.unknown_edit)
        layout.addLayout(form)

        tokens = QLabel(
            "テンプレートで使える項目: "
            "{media_type} {ext} {ext_dot} {year} {month} {day} {hour} "
            "{name} {stem} {size_band} {top_folder} {parent} {parent_1} {parent_2} {parent_3} {rel_dir}"
        )
        tokens.setWordWrap(True)
        tokens.setStyleSheet("color: #aab0b6; font-size: 11px;")
        layout.addWidget(tokens)

        self.preview_check = QCheckBox("シミュレーション時に結果CSV（source/target）も保存する")
        self.preview_check.setChecked(True)
        layout.addWidget(self.preview_check)

        self.conditional_check = QCheckBox("詳細設定を使う（条件分岐でテンプレートを切替）")
        self.conditional_check.setChecked(False)
        layout.addWidget(self.conditional_check)

        self.advanced_container = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(6)

        rules_header = QLabel("上級者向け: 条件分岐ルール(JSON)")
        rules_header.setStyleSheet("font-weight: bold;")
        advanced_layout.addWidget(rules_header)

        self.rules_edit = QPlainTextEdit()
        self.rules_edit.setPlaceholderText(
            '[\n'
            '  {"name": "large", "when": {"min_size_mb": 500}, "template": "large/{media_type}/{year}"},\n'
            '  {"name": "images", "when": {"media_type": "image"}, "template": "images/{ext}/{year}/{month}"}\n'
            ']'
        )
        self.rules_edit.setFixedHeight(180)
        advanced_layout.addWidget(self.rules_edit)

        rule_note = QLabel(
            "条件キー: media_type, ext, min_size_mb, max_size_mb, size_band, year, month, day, "
            "path_contains, name_contains"
        )
        rule_note.setWordWrap(True)
        rule_note.setStyleSheet("color: #aab0b6; font-size: 11px;")
        advanced_layout.addWidget(rule_note)

        preset_row = QHBoxLayout()
        self.load_preset_btn = QPushButton("プリセット読込")
        self.save_preset_btn = QPushButton("プリセット保存")
        self.sample_rules_btn = QPushButton("サンプル挿入")
        preset_row.addWidget(self.load_preset_btn)
        preset_row.addWidget(self.save_preset_btn)
        preset_row.addWidget(self.sample_rules_btn)
        preset_row.addStretch()
        advanced_layout.addLayout(preset_row)
        layout.addWidget(self.advanced_container)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.conditional_check.toggled.connect(self._toggle_advanced_sections)
        self.easy_pattern_combo.currentIndexChanged.connect(self._on_easy_pattern_changed)
        self.load_preset_btn.clicked.connect(self.load_preset)
        self.save_preset_btn.clicked.connect(self.save_preset)
        self.sample_rules_btn.clicked.connect(self.insert_sample_rules)
        self._on_easy_pattern_changed()
        self._toggle_advanced_sections(False)

    def _toggle_advanced_sections(self, enabled: bool):
        self.advanced_container.setVisible(enabled)
        self.rules_edit.setEnabled(enabled)

    def _on_easy_pattern_changed(self):
        mode = self.easy_pattern_combo.currentText()
        mapping = {
            "種類 → 年月で整理（おすすめ）": "{media_type}/{year}/{month}/{ext}",
            "年月で整理": "{year}/{month}/{ext}",
            "種類で整理": "{media_type}/{ext}",
            "拡張子で整理": "{ext}/{year}/{month}",
            "元フォルダ名を活かす": "{top_folder}/{parent}/{ext}",
        }

        if mode in mapping:
            template = mapping[mode]
            self.template_edit.setText(template)
            self.easy_preview_label.setText(f"この設定で作られる構造: {template}")
            self.template_edit.setEnabled(False)
        else:
            self.easy_preview_label.setText("カスタムを選択中: 下のテンプレート欄を自由に編集してください。")
            self.template_edit.setEnabled(True)

    def _set_easy_pattern_from_template(self, template: str):
        mapping = {
            "{media_type}/{year}/{month}/{ext}": "種類 → 年月で整理（おすすめ）",
            "{year}/{month}/{ext}": "年月で整理",
            "{media_type}/{ext}": "種類で整理",
            "{ext}/{year}/{month}": "拡張子で整理",
            "{top_folder}/{parent}/{ext}": "元フォルダ名を活かす",
        }
        target = mapping.get(template.strip(), "カスタム（下のテンプレートを直接入力）")
        idx = self.easy_pattern_combo.findText(target)
        if idx >= 0:
            self.easy_pattern_combo.setCurrentIndex(idx)

    def values(self) -> Dict[str, Any]:
        rules = []
        if self.conditional_check.isChecked():
            text = self.rules_edit.toPlainText().strip()
            if text:
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("条件分岐ルールはJSON配列で指定してください")
                rules = parsed
        return {
            "template": self.template_edit.text().strip(),
            "unknown": self.unknown_edit.text().strip() or "unknown",
            "export_preview": self.preview_check.isChecked(),
            "use_conditions": self.conditional_check.isChecked(),
            "rules": rules,
        }

    def _preset_dir(self) -> Path:
        base = Path(__file__).resolve().parent.parent / "presets" / "template_build"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def insert_sample_rules(self):
        sample = [
            {
                "name": "huge_media",
                "when": {"min_size_mb": 1024, "media_type": ["video", "audio"]},
                "template": "huge/{media_type}/{year}/{month}",
            },
            {
                "name": "images_small",
                "when": {"media_type": "image", "max_size_mb": 20},
                "template": "images/small/{year}/{month}/{ext}",
            },
            {
                "name": "documents",
                "when": {"media_type": "document"},
                "template": "docs/{year}/{month}/{ext}",
            },
        ]
        self.conditional_check.setChecked(True)
        self.rules_edit.setPlainText(json.dumps(sample, ensure_ascii=False, indent=2))

    def save_preset(self):
        try:
            data = self.values()
        except Exception as exc:
            QMessageBox.warning(self, "入力エラー", str(exc))
            return

        default_name = self._preset_dir() / f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "プリセット保存",
            str(default_name),
            "JSON files (*.json)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存完了", f"プリセットを保存しました:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "保存エラー", f"プリセット保存に失敗しました:\n{exc}")

    def load_preset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "プリセット読込",
            str(self._preset_dir()),
            "JSON files (*.json)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            template = str(data.get("template", self.template_edit.text()))
            self._set_easy_pattern_from_template(template)
            self.template_edit.setText(template)
            self.unknown_edit.setText(str(data.get("unknown", self.unknown_edit.text())))
            self.preview_check.setChecked(bool(data.get("export_preview", True)))
            use_conditions = bool(data.get("use_conditions", False))
            self.conditional_check.setChecked(use_conditions)
            rules = data.get("rules", [])
            if isinstance(rules, list):
                self.rules_edit.setPlainText(json.dumps(rules, ensure_ascii=False, indent=2))
            QMessageBox.information(self, "読込完了", f"プリセットを読み込みました:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "読込エラー", f"プリセット読込に失敗しました:\n{exc}")


class AnalyzerWindow(QMainWindow):
    """Enhanced PySide6版フォルダ解析ウィンドウ - 複数フォルダ対応・Dry-run機能付き"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("フォルダ解析ツール")
        self.setGeometry(200, 200, 1200, 800)
        self.setMinimumSize(1000, 700)
        
        # データ管理
        self.selected_paths: List[Path] = []  # 複数パス管理
        self.scan_results: Dict[str, Any] = {}  # 走査結果保存
        self.dry_run_mode: bool = True  # デフォルトシミュレーション ON
        self.scanner_thread: Optional[ScannerThread] = None
        self.analysis_buttons: List[QPushButton] = []
        self.is_scanning: bool = False
        self.latest_log_path: Optional[str] = None
        self.folder_placeholder_text = "ここにフォルダをドラッグ&ドロップ"

        self.init_ui()
        self.setup_shortcuts()
        
        # ドラッグ&ドロップを有効化
        self.setAcceptDrops(True)
        
        # ツールバーの接続漏れを明示的に修正
        self._fix_toolbar_connections()
        self._ensure_button_connections()
        
        self.apply_theme()
    
    def _fix_toolbar_connections(self):
        """ツールバーボタンの接続を確実に行う"""
        # 接続の確認と修正
        if hasattr(self, 'folder_tree') and hasattr(self, 'result_tree'):
            # 基本的な接続が正しく設定されていることを確認
            pass  # create_compact_toolbar()で既に接続済み
    
    def _ensure_button_connections(self):
        """整理・階層削除ボタンの接続を確実にする"""
        # ボタンを探して確実に新しいハンドラーに接続
        for widget in self.findChildren(QPushButton):
            if widget.text() == "整理実行":
                try:
                    widget.clicked.disconnect()
                except:
                    pass
                widget.clicked.connect(self._on_sort_clicked)
            elif widget.text() == "階層削除":
                try:
                    widget.clicked.disconnect()
                except:
                    pass
                widget.clicked.connect(self._on_flatten_clicked)
            elif widget.text() == "テンプレート構築":
                try:
                    widget.clicked.disconnect()
                except:
                    pass
                widget.clicked.connect(self._on_template_build_clicked)
        
    def _register_analysis_button(self, button: QPushButton):
        if button not in self.analysis_buttons:
            self.analysis_buttons.append(button)

    def _set_analysis_controls_enabled(self, enabled: bool):
        for button in self.analysis_buttons:
            button.setEnabled(enabled)

        if hasattr(self, "cancel_button") and self.cancel_button:
            self.cancel_button.setEnabled(not enabled and self.is_scanning)

    def _reset_progress_ui(self, message: str = "準備完了", hide_bar: bool = True):
        if hasattr(self, "progress_bar") and self.progress_bar:
            if hide_bar:
                self.progress_bar.setVisible(False)
            else:
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0)

        if hasattr(self, "progress_label") and self.progress_label:
            self.progress_label.setText(message)
            self.progress_label.setVisible(True)

        if hasattr(self, "cancel_button") and self.cancel_button:
            self.cancel_button.setEnabled(False)
            self.cancel_button.setVisible(False)

        self.is_scanning = False
        self._set_analysis_controls_enabled(True)

    def setup_shortcuts(self):
        """キーボードショートカットを設定"""
        from PySide6.QtGui import QShortcut, QKeySequence
        
        # Ctrl+O: フォルダ選択
        QShortcut(QKeySequence("Ctrl+O"), self, self.select_folders_dialog)
        
        # Ctrl+R: 解析実行
        QShortcut(QKeySequence("Ctrl+R"), self, self.run_analysis)
        
        # Ctrl+S: CSV保存
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_results_to_csv)
        
        # F5: フォルダツリー更新
        QShortcut(QKeySequence("F5"), self, self.refresh_folder_tree)
        
        # Delete: 選択フォルダ削除
        QShortcut(QKeySequence("Delete"), self, self.remove_selected_folders)
        
        # Ctrl+A: 全選択（結果ツリー）
        QShortcut(QKeySequence("Ctrl+A"), self.result_tree, self.result_tree.selectAll)
    
    def _selected_files_from_result(self):
        """
        QTreeWidget(解析結果)の選択から、拡張子行だけを拾って
        実ファイルパスのリストを返す。
        """
        items = self.result_tree.selectedItems() if hasattr(self, "result_tree") else []
        if not items:
            return []

        files = []
        for item in items:
            parent = item.parent()
            # 親がある＝拡張子行（媒体行は親がない）
            if parent is None:
                continue
            
            media = parent.text(0).replace("🎵 ", "").replace("🎥 ", "").replace("🖼️ ", "").replace("📄 ", "").replace("📦 ", "").replace("📁 ", "").strip().lower()
            ext_text = item.text(0).replace("📄 ", "").strip()
            ext = ext_text if ext_text != "(拡張子なし)" else ""
            
            # scan_resultsから該当する実ファイルを取得
            try:
                if hasattr(self, 'scan_results') and self.scan_results:
                    media_data = self.scan_results.get(media, {})
                    if 'files' in media_data:
                        # ファイルリストから拡張子でフィルタ
                        for file_path in media_data['files']:
                            file_ext = Path(file_path).suffix.lower()
                            if file_ext == ext or (not ext and not file_ext):
                                files.append(str(file_path))
            except Exception:
                pass
        
        # 重複排除
        return list(dict.fromkeys(files))
    
    def _on_sort_clicked(self):
        """整理実行ボタンクリック時の処理"""
        selected = self._selected_files_from_result()
        if not selected:
            QMessageBox.warning(self, "警告", "処理対象を選択してください（拡張子行を選択）")
            return
        
        # Dry-run チェックボックスを尊重
        dry_run = getattr(self, "simulation_check", None)
        is_dry_run = dry_run.isChecked() if dry_run else True
        self._start_sort(selected, is_dry_run)
    
    def _on_flatten_clicked(self):
        """階層削除ボタンクリック時の処理"""
        selected = self._selected_files_from_result()
        if not selected:
            QMessageBox.warning(self, "警告", "処理対象を選択してください（拡張子行を選択）")
            return
        
        # Dry-run チェックボックスを尊重
        dry_run = getattr(self, "simulation_check", None)
        is_dry_run = dry_run.isChecked() if dry_run else True
        self._start_flatten(selected, is_dry_run)

    def _on_template_build_clicked(self):
        """テンプレート構築ボタンクリック時の処理"""
        selected = self._selected_files_from_result()
        if not selected:
            QMessageBox.warning(self, "警告", "処理対象を選択してください（拡張子行を選択）")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "テンプレート構築の出力先を選択")
        if not output_dir:
            return

        settings = TemplateBuildDialog(self)
        if settings.exec() != QDialog.Accepted:
            return

        try:
            values = settings.values()
        except Exception as exc:
            QMessageBox.warning(self, "入力エラー", f"テンプレート設定の解釈に失敗しました:\n{exc}")
            return

        template = values.get("template", "").strip()
        if not template:
            QMessageBox.warning(self, "警告", "テンプレートを入力してください（例: {media_type}/{year}/{month}/{ext}）")
            return

        dry_run = getattr(self, "simulation_check", None)
        is_dry_run = dry_run.isChecked() if dry_run else True
        self._start_template_build(
            selected,
            Path(output_dir),
            template,
            unknown_value=values.get("unknown", "unknown"),
            export_preview=bool(values.get("export_preview", False)),
            conditional_rules=values.get("rules", []) if values.get("use_conditions") else [],
            dry_run=is_dry_run,
        )

    def _selected_root_for_file(self, file_path: Path) -> Optional[Path]:
        """選択済みルートから最も深く一致する親フォルダを返す。"""
        candidates: List[Path] = []
        roots: List[Path] = []

        if self.selected_paths:
            roots.extend(self.selected_paths)

        if hasattr(self, "folder_tree"):
            for i in range(self.folder_tree.topLevelItemCount()):
                item = self.folder_tree.topLevelItem(i)
                if not item:
                    continue
                raw = item.data(0, Qt.UserRole)
                if raw:
                    try:
                        p = Path(raw)
                        if p.exists() and p.is_dir():
                            roots.append(p)
                    except Exception:
                        continue

        unique_roots = []
        seen = set()
        for root in roots:
            key = str(root)
            if key in seen:
                continue
            seen.add(key)
            unique_roots.append(root)

        for root in unique_roots:
            try:
                file_path.relative_to(root)
                candidates.append(root)
            except Exception:
                continue

        if not candidates:
            return None

        candidates.sort(key=lambda p: len(str(p)), reverse=True)
        return candidates[0]

    def _sanitize_segment(self, text: str, unknown_value: str) -> str:
        """フォルダ名セグメントを安全化。"""
        value = (text or "").strip()
        if not value:
            return unknown_value

        value = value.replace("\\", "_").replace("/", "_")
        value = re.sub(r'[<>:"|?*\x00-\x1f]', "_", value)
        value = value.strip(" .")
        return value or unknown_value

    def _build_template_context(self, file_path: Path, unknown_value: str) -> Dict[str, Any]:
        """テンプレート置換用のコンテキストを構築。"""
        ext_dot = file_path.suffix.lower()
        ext = ext_dot.lstrip(".")
        media_type = FileScanner.detect_media_type(ext_dot)

        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        except Exception:
            mtime = datetime.now()

        size_bytes = 0
        try:
            size_bytes = file_path.stat().st_size
        except Exception:
            pass

        size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
        if size_mb < 1:
            size_band = "tiny"
        elif size_mb < 10:
            size_band = "small"
        elif size_mb < 100:
            size_band = "medium"
        elif size_mb < 1024:
            size_band = "large"
        else:
            size_band = "huge"

        root = self._selected_root_for_file(file_path)
        rel_dir = ""
        top_folder = unknown_value
        parent_1 = parent_2 = parent_3 = unknown_value
        parent = file_path.parent.name or unknown_value
        if root:
            try:
                rel_parent = file_path.parent.relative_to(root)
                rel_parts = [p for p in rel_parent.parts if p not in (".", "")]
                rel_dir = "/".join(rel_parts)
                if rel_parts:
                    top_folder = rel_parts[0]
                    parent_1 = rel_parts[-1]
                    if len(rel_parts) >= 2:
                        parent_2 = rel_parts[-2]
                    if len(rel_parts) >= 3:
                        parent_3 = rel_parts[-3]
            except Exception:
                pass

        return {
            "media_type": media_type,
            "ext": ext or unknown_value,
            "ext_dot": ext_dot or unknown_value,
            "year": f"{mtime.year:04d}",
            "month": f"{mtime.month:02d}",
            "day": f"{mtime.day:02d}",
            "hour": f"{mtime.hour:02d}",
            "name": file_path.name,
            "stem": file_path.stem,
            "size_band": size_band,
            "top_folder": top_folder,
            "parent": parent,
            "parent_1": parent_1,
            "parent_2": parent_2,
            "parent_3": parent_3,
            "rel_dir": rel_dir or unknown_value,
            "size_mb": round(size_mb, 4),
            "size_bytes": size_bytes,
            "path": str(file_path),
        }

    def _normalize_ext_value(self, value: str) -> str:
        raw = (value or "").strip().lower()
        if not raw:
            return ""
        return raw if raw.startswith(".") else f".{raw}"

    def _rule_matches(self, when: Dict[str, Any], context: Dict[str, Any], file_path: Path) -> bool:
        """Evaluate one conditional rule."""
        if not when:
            return True

        media_type = str(context.get("media_type", "")).lower()
        ext_dot = self._normalize_ext_value(str(context.get("ext_dot", "")))
        size_mb = float(context.get("size_mb", 0) or 0)
        size_band = str(context.get("size_band", "")).lower()
        year = str(context.get("year", ""))
        month = str(context.get("month", ""))
        day = str(context.get("day", ""))
        path_str = str(file_path)
        name_str = file_path.name

        if "media_type" in when:
            expected = when.get("media_type")
            if isinstance(expected, list):
                if media_type not in [str(x).lower() for x in expected]:
                    return False
            elif media_type != str(expected).lower():
                return False

        if "ext" in when:
            expected_ext = when.get("ext")
            if isinstance(expected_ext, list):
                normalized = [self._normalize_ext_value(str(x)) for x in expected_ext]
                if ext_dot not in normalized:
                    return False
            else:
                if ext_dot != self._normalize_ext_value(str(expected_ext)):
                    return False

        if "min_size_mb" in when:
            try:
                if size_mb < float(when.get("min_size_mb")):
                    return False
            except Exception:
                return False

        if "max_size_mb" in when:
            try:
                if size_mb > float(when.get("max_size_mb")):
                    return False
            except Exception:
                return False

        if "size_band" in when:
            expected_band = when.get("size_band")
            if isinstance(expected_band, list):
                if size_band not in [str(x).lower() for x in expected_band]:
                    return False
            elif size_band != str(expected_band).lower():
                return False

        if "year" in when and year != str(when.get("year")):
            return False
        if "month" in when and month != str(when.get("month")).zfill(2):
            return False
        if "day" in when and day != str(when.get("day")).zfill(2):
            return False

        if "path_contains" in when and str(when.get("path_contains")) not in path_str:
            return False
        if "name_contains" in when and str(when.get("name_contains")) not in name_str:
            return False

        return True

    def _select_template_by_rules(
        self,
        default_template: str,
        rules: List[Dict[str, Any]],
        context: Dict[str, Any],
        file_path: Path,
    ) -> Dict[str, str]:
        """Select template using first matching rule."""
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            when = rule.get("when", {})
            template = str(rule.get("template", "")).strip()
            if not template:
                continue
            if self._rule_matches(when if isinstance(when, dict) else {}, context, file_path):
                rule_name = str(rule.get("name", f"rule_{idx+1}")).strip() or f"rule_{idx+1}"
                return {"template": template, "rule": rule_name}
        return {"template": default_template, "rule": "default"}

    def _render_template_folder(self, template: str, context: Dict[str, str], unknown_value: str) -> Path:
        """テンプレートを展開して相対フォルダパスを返す。"""
        rendered = template

        for token in re.findall(r"\{([a-zA-Z0-9_]+)\}", template):
            value = context.get(token, unknown_value)
            rendered = rendered.replace("{" + token + "}", self._sanitize_segment(str(value), unknown_value))

        raw_parts = [p for p in rendered.replace("\\", "/").split("/") if p]
        safe_parts = [self._sanitize_segment(p, unknown_value) for p in raw_parts if p not in (".", "..")]
        if not safe_parts:
            safe_parts = [unknown_value]
        return Path(*safe_parts)

    def _export_template_preview_csv(self, preview_rows: List[Dict[str, str]]) -> Optional[Path]:
        """テンプレート構築のプレビューCSVを出力。"""
        if not preview_rows:
            return None
        try:
            log_dir = Path(__file__).resolve().parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            path = log_dir / f"template_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["source", "target", "folder", "rule", "template"])
                for row in preview_rows:
                    writer.writerow([
                        row.get("source", ""),
                        row.get("target", ""),
                        row.get("folder", ""),
                        row.get("rule", "default"),
                        row.get("template", ""),
                    ])
            return path
        except Exception:
            return None

    def _start_template_build(
        self,
        files: List[str],
        output_root: Path,
        template: str,
        *,
        unknown_value: str,
        export_preview: bool,
        conditional_rules: List[Dict[str, Any]],
        dry_run: bool,
    ):
        """テンプレートに従ってフォルダ構造を構築しながら処理。"""
        mode = "copy"
        if hasattr(self, "operation_group"):
            idx = self.operation_group.checkedId()
            mode = {0: "copy", 1: "move", 2: "link"}.get(idx, "copy")

        operations = {"copy": _op_copy, "move": _op_move, "link": _op_link}
        operation_func = operations[mode]

        success_count = 0
        error_count = 0
        folder_stats: Dict[str, int] = defaultdict(int)
        rule_hits: Dict[str, int] = defaultdict(int)
        preview_rows: List[Dict[str, str]] = []
        total_files = len(files)

        for i, file_path_str in enumerate(files, 1):
            if hasattr(self, "status_bar"):
                self.status_bar.showMessage(f"テンプレート構築中... {i}/{total_files}")
            QApplication.processEvents()

            source_path = Path(file_path_str)
            if not source_path.exists() or not source_path.is_file():
                error_count += 1
                continue

            try:
                context = self._build_template_context(source_path, unknown_value)
                selected = self._select_template_by_rules(template, conditional_rules, context, source_path)
                selected_template = selected["template"]
                selected_rule = selected["rule"]
                rel_folder = self._render_template_folder(selected_template, context, unknown_value)
                target_dir = output_root / rel_folder
                final_path = _unique_path(target_dir, source_path.name)
                folder_stats[str(rel_folder)] += 1
                rule_hits[selected_rule] += 1

                if export_preview or dry_run:
                    preview_rows.append(
                        {
                            "source": str(source_path),
                            "target": str(final_path),
                            "folder": str(rel_folder),
                            "rule": selected_rule,
                            "template": selected_template,
                        }
                    )

                if not dry_run:
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    operation_func(source_path, final_path)

                success_count += 1
            except Exception:
                error_count += 1

        preview_path = self._export_template_preview_csv(preview_rows) if export_preview and preview_rows else None
        top_folders = sorted(folder_stats.items(), key=lambda x: x[1], reverse=True)[:8]
        top_rules = sorted(rule_hits.items(), key=lambda x: x[1], reverse=True)[:8]
        folder_preview = "\n".join([f"  - {name}: {count}" for name, count in top_folders]) if top_folders else "  - なし"
        rule_preview = "\n".join([f"  - {name}: {count}" for name, count in top_rules]) if top_rules else "  - default: 0"

        result_msg = (
            f"テンプレート構築 完了\n\n"
            f"テンプレート: {template}\n"
            f"操作: {mode}\n"
            f"条件ルール数: {len(conditional_rules)}\n"
            f"成功: {success_count}\n"
            f"エラー: {error_count}\n"
            f"生成フォルダ数: {len(folder_stats)}\n"
            f"上位フォルダ:\n{folder_preview}\n"
            f"ルール適用件数:\n{rule_preview}"
        )
        if dry_run:
            result_msg = "[Dry-run] " + result_msg
        if preview_path:
            result_msg += f"\n\nプレビューCSV: {preview_path}"

        QMessageBox.information(self, "結果", result_msg)
    
    def _start_sort(self, files: List[str], dry_run: bool):
        """整理（Sort）の実行"""
        # 可能なら既存 core を優先、なければ内製
        if _core_perform_sort and not dry_run:
            try:
                _core_perform_sort(files)
                QMessageBox.information(self, "完了", "整理を実行しました。")
                return
            except Exception as e:
                QMessageBox.warning(self, "注意", f"core.processor 経由の整理でエラー: {e}\n内蔵実装で再試行します。")

        # 内蔵実装
        output_dir = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択")
        if not output_dir:
            return
        dest_root = Path(output_dir)

        # ラジオの操作モード（コピー/移動/リンク）
        mode = "copy"
        if hasattr(self, "operation_group"):
            idx = self.operation_group.checkedId()
            mode = {0: "copy", 1: "move", 2: "link"}.get(idx, "copy")

        operations = {"copy": _op_copy, "move": _op_move, "link": _op_link}
        operation_func = operations[mode]

        # 進捗
        success_count = error_count = 0
        total_files = len(files)
        
        for i, file_path_str in enumerate(files, 1):
            if hasattr(self, 'status_bar'):
                self.status_bar.showMessage(f"整理中... {i}/{total_files}")
            QApplication.processEvents()

            source_path = Path(file_path_str)
            if not source_path.exists():
                error_count += 1
                continue
                
            # 媒体タイプ別フォルダ作成（簡易版）
            dest_dir = dest_root
            final_path = _unique_path(dest_dir, source_path.name)
            
            if dry_run:
                continue
                
            try:
                operation_func(source_path, final_path)
                success_count += 1
            except Exception:
                error_count += 1

        result_msg = f"整理完了: 成功 {success_count}, エラー {error_count}"
        if dry_run:
            result_msg = f"[Dry-run] " + result_msg
        QMessageBox.information(self, "結果", result_msg)
    
    def _start_flatten(self, files: List[str], dry_run: bool):
        """階層削除（Flatten）の実行"""
        if _core_perform_flatten and not dry_run:
            try:
                _core_perform_flatten(files)
                QMessageBox.information(self, "完了", "階層削除(Flatten)を実行しました。")
                return
            except Exception as e:
                QMessageBox.warning(self, "注意", f"core.processor 経由のFlattenでエラー: {e}\n内蔵実装で再試行します。")

        output_dir = QFileDialog.getExistingDirectory(self, "Flatten先フォルダを選択")
        if not output_dir:
            return
        dest_root = Path(output_dir)

        mode = "copy"
        if hasattr(self, "operation_group"):
            idx = self.operation_group.checkedId()
            mode = {0: "copy", 1: "move", 2: "link"}.get(idx, "copy")
        
        operations = {"copy": _op_copy, "move": _op_move, "link": _op_link}
        operation_func = operations[mode]

        success_count = error_count = 0
        total_files = len(files)
        
        for i, file_path_str in enumerate(files, 1):
            if hasattr(self, 'status_bar'):
                self.status_bar.showMessage(f"Flatten中... {i}/{total_files}")
            QApplication.processEvents()

            source_path = Path(file_path_str)
            if not source_path.exists():
                error_count += 1
                continue
                
            final_path = _unique_path(dest_root, source_path.name)
            
            if dry_run:
                continue
                
            try:
                operation_func(source_path, final_path)   # 階層は無視し1つのフォルダに集約
                success_count += 1
            except Exception:
                error_count += 1

        result_msg = f"Flatten完了: 成功 {success_count}, エラー {error_count}"
        if dry_run:
            result_msg = f"[Dry-run] " + result_msg
        QMessageBox.information(self, "結果", result_msg)
        
    def init_ui(self):
        """レイアウト修正（ツールバーを解析結果の上に）"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # メインスプリッター（縦分割）
        vsplitter = QSplitter(Qt.Vertical)
        
        # 上部：解析対象フォルダツリー
        folder_widget = self.create_folder_tree_widget()
        vsplitter.addWidget(folder_widget)
        
        # 中部：ツールバーと解析結果を含むウィジェット
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)
        
        # ツールバー（解析結果の直上）
        toolbar = self.create_compact_toolbar()
        bottom_layout.addWidget(toolbar)
        
        # 解析結果
        result_widget = self.create_result_widget()
        bottom_layout.addWidget(result_widget)
        
        vsplitter.addWidget(bottom_widget)
        vsplitter.setSizes([400, 300])
        
        main_layout.addWidget(vsplitter)
        
        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了 - フォルダを追加して解析を開始してください")
        
    def create_compact_toolbar(self):
        """ツールバーのボタン配置修正"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(35)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # フォルダ選択
        add_btn = QPushButton("フォルダ選択")
        add_btn.clicked.connect(self.select_folders_dialog)
        layout.addWidget(add_btn)

        file_btn = QPushButton("ファイル選択")
        file_btn.clicked.connect(self.select_files_dialog)
        layout.addWidget(file_btn)
        
        # 更新
        refresh_btn = QPushButton("更新")
        refresh_btn.clicked.connect(self.refresh_analysis)
        layout.addWidget(refresh_btn)
        
        # 選択削除
        remove_btn = QPushButton("選択削除")
        remove_btn.clicked.connect(self.remove_selected_folders)
        layout.addWidget(remove_btn)

        name_remove_btn = QPushButton("名前で削除")
        name_remove_btn.clicked.connect(self.remove_folders_by_name)
        layout.addWidget(name_remove_btn)

        # 解析実行
        analyze_btn = QPushButton("解析実行")
        analyze_btn.setStyleSheet("background-color: #2d5a2d; color: white;")
        analyze_btn.clicked.connect(self.run_analysis)
        self._register_analysis_button(analyze_btn)
        layout.addWidget(analyze_btn)
        
        layout.addWidget(QLabel("|"))
        
        # シミュレーション
        self.simulation_check = QCheckBox("シミュレーション")
        self.simulation_check.setChecked(True)
        layout.addWidget(self.simulation_check)
        
        # 操作モード
        layout.addWidget(QLabel("操作:"))
        self.operation_group = QButtonGroup()
        self.copy_radio = QRadioButton("コピー")
        self.move_radio = QRadioButton("移動")
        self.link_radio = QRadioButton("リンク")
        self.copy_radio.setChecked(True)
        
        self.operation_group.addButton(self.copy_radio, 0)
        self.operation_group.addButton(self.move_radio, 1)
        self.operation_group.addButton(self.link_radio, 2)
        
        layout.addWidget(self.copy_radio)
        layout.addWidget(self.move_radio)
        layout.addWidget(self.link_radio)
        
        layout.addWidget(QLabel("|"))
        
        # 整理実行
        sort_btn = QPushButton("整理実行")
        sort_btn.clicked.connect(self._on_sort_clicked)
        layout.addWidget(sort_btn)
        
        # 階層削除
        flatten_btn = QPushButton("階層削除")
        flatten_btn.clicked.connect(self._on_flatten_clicked)
        layout.addWidget(flatten_btn)

        # テンプレート構築
        template_btn = QPushButton("テンプレート構築")
        template_btn.clicked.connect(self._on_template_build_clicked)
        layout.addWidget(template_btn)
        
        layout.addWidget(QLabel("|"))
        
        # CSV保存
        csv_btn = QPushButton("CSV保存")
        csv_btn.clicked.connect(self.save_csv)
        layout.addWidget(csv_btn)
        
        layout.addStretch()
        
        # 全クリア（右端）
        clear_btn = QPushButton("全クリア")
        clear_btn.setStyleSheet("color: #a94442;")
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)
        
        return toolbar
        
    def create_folder_tree_widget(self):
        """ドロップエリアに説明文追加"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # ヘッダー
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("解析対象フォルダ"))
        
        self.show_files_check = QCheckBox("ファイル表示")
        self.show_files_check.toggled.connect(self.refresh_folder_tree)
        header_layout.addWidget(self.show_files_check)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # ツリービュー（ドロップ可能）
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_tree.setAcceptDrops(True)
        self.folder_tree.setDragDropMode(QAbstractItemView.DropOnly)
        self.folder_tree.setDefaultDropAction(Qt.CopyAction)
        self.folder_tree.viewport().setAcceptDrops(True)
        self.folder_tree.setMinimumHeight(200)
        # ツリー上へのドロップを確実に受け取る
        self.folder_tree.dragEnterEvent = self.folder_tree_drag_enter_event
        self.folder_tree.dragMoveEvent = self.folder_tree_drag_move_event
        self.folder_tree.dropEvent = self.folder_tree_drop_event
        
        # ドロップエリアの説明（ツリーが空の時に表示）
        self.folder_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                border: 2px dashed #3c3c3c;
            }
            QTreeWidget::item {
                padding: 2px;
            }
        """)
        
        # プレースホルダーアイテム
        self._add_placeholder_if_empty()

        layout.addWidget(self.folder_tree)

        return widget

    def folder_tree_drag_enter_event(self, event):
        """フォルダツリーへのドラッグエンター"""
        if event.mimeData().hasUrls():
            has_paths = any(Path(url.toLocalFile()).exists() for url in event.mimeData().urls())
            if has_paths:
                event.acceptProposedAction()
                return
        event.ignore()

    def folder_tree_drag_move_event(self, event):
        """フォルダツリーへのドラッグムーブ"""
        if event.mimeData().hasUrls():
            has_paths = any(Path(url.toLocalFile()).exists() for url in event.mimeData().urls())
            if has_paths:
                event.acceptProposedAction()
                return
        event.ignore()

    def folder_tree_drop_event(self, event):
        """フォルダツリーへのドロップ（ファイル/フォルダ両対応）"""
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        added_count = 0
        for url in event.mimeData().urls():
            try:
                p = Path(url.toLocalFile())
                if self.add_path_item(p):
                    added_count += 1
            except Exception:
                continue

        if added_count > 0:
            self.status_bar.showMessage(f"{added_count}件の対象（フォルダ/ファイル）を追加しました")
            event.acceptProposedAction()
        else:
            self.status_bar.showMessage("有効なフォルダ/ファイルがドロップされませんでした")
            event.ignore()
        
    def create_result_widget(self):
        """解析結果表示ウィジェット作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # ヘッダー
        header = QLabel("解析結果")
        layout.addWidget(header)
        
        # 結果ツリー
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["項目", "ファイル数", "サイズ(MB)", "平均(MB)"])
        self.result_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.result_tree.setAlternatingRowColors(True)
        layout.addWidget(self.result_tree)
        
        # プログレスバー（最初は非表示）
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        progress_row = QHBoxLayout()
        self.progress_label = QLabel("準備完了")
        self.progress_label.setVisible(False)
        progress_row.addWidget(self.progress_label, 1)

        self.cancel_button = QPushButton("中止")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_scan)
        progress_row.addWidget(self.cancel_button, 0)

        layout.addLayout(progress_row)
        
        # 統計表示
        self.stats_label = QLabel("統計: 未解析")
        self.stats_label.setObjectName("stats_text")
        layout.addWidget(self.stats_label)
        
        return widget
        
    def select_folders_dialog(self):
        from PySide6.QtWidgets import QFileDialog, QListView, QTreeView, QAbstractItemView
        from PySide6.QtCore import Qt
        from pathlib import Path

        try:
            dlg = QFileDialog(self, "フォルダを選択")
            dlg.setFileMode(QFileDialog.Directory)
            dlg.setOption(QFileDialog.ShowDirsOnly, True)
            dlg.setOption(QFileDialog.DontUseNativeDialog, True)  # 複数選択のため必須
            dlg.setDirectory(str(Path.home()))

            # ★ PySide6 の findChildren は tuple を直接渡せない。
            #    クラスごとに 2 回呼び出して selectionMode を拡張する。
            for cls in (QListView, QTreeView):
                for view in dlg.findChildren(cls, options=Qt.FindChildrenRecursively):
                    view.setSelectionMode(QAbstractItemView.ExtendedSelection)

            if dlg.exec():
                urls = dlg.selectedUrls()
                added = 0
                for u in urls:
                    p = Path(u.toLocalFile())
                    if self.add_path_item(p):
                        added += 1
                if added == 0:
                    QMessageBox.information(self, "情報", "追加できるフォルダがありませんでした。")
            else:
                # キャンセルは無視
                pass

        except Exception as e:
            QMessageBox.critical(self, "フォルダ選択エラー", str(e))

    def select_files_dialog(self):
        """ファイルを複数選択して解析対象に追加"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "ファイルを選択",
            str(Path.home()),
            "すべてのファイル (*)",
        )
        if not files:
            return

        added = 0
        for file_path in files:
            if self.add_path_item(Path(file_path)):
                added += 1
        if added == 0:
            QMessageBox.information(self, "情報", "追加できるファイルがありませんでした。")

    def add_path_item(self, path: Path) -> bool:
        """フォルダまたはファイルを解析対象に追加"""
        if not path.exists():
            return False
        if path.is_dir():
            self.add_folder_with_structure(path)
            return True
        if path.is_file():
            return self.add_file_item(path)
        return False

    def add_file_item(self, file_path: Path) -> bool:
        """単一ファイルをトップレベル項目として追加"""
        if self.folder_tree.topLevelItemCount() == 1:
            item = self.folder_tree.topLevelItem(0)
            if item.text(0) == self.folder_placeholder_text:
                self.folder_tree.clear()

        path_str = str(file_path)
        for i in range(self.folder_tree.topLevelItemCount()):
            existing_item = self.folder_tree.topLevelItem(i)
            if existing_item.data(0, Qt.UserRole) == path_str:
                return False

        file_item = QTreeWidgetItem(self.folder_tree, [f"📄 {file_path.name}"])
        file_item.setData(0, Qt.UserRole, path_str)
        file_item.setToolTip(0, path_str)
        self.update_statistics()
        return True
    
    def add_folder_with_structure(self, folder_path: Path):
        """ツリー追加時にフルパスを必ず保持（UserRole）"""
        # プレースホルダーを削除
        if self.folder_tree.topLevelItemCount() == 1:
            item = self.folder_tree.topLevelItem(0)
            if item.text(0) == self.folder_placeholder_text:
                self.folder_tree.clear()
        
        # 既存チェック
        for i in range(self.folder_tree.topLevelItemCount()):
            existing_item = self.folder_tree.topLevelItem(i)
            if existing_item.data(0, Qt.UserRole) == str(folder_path):
                return  # 既に存在する
        
        root_item = QTreeWidgetItem(self.folder_tree, [folder_path.name])
        root_item.setData(0, Qt.UserRole, str(folder_path))
        root_item.setToolTip(0, str(folder_path))
        
        # サブフォルダを追加
        self.add_subfolders(root_item, folder_path)
        root_item.setExpanded(True)
        
        # 統計更新
        self.update_statistics()

    def add_subfolders(self, parent_item, folder_path: Path, depth=0, max_depth=3):
        """サブフォルダ追加でUserRole必須設定"""
        if depth >= max_depth:
            return
        try:
            for child in sorted(folder_path.iterdir()):
                if child.name.startswith('.'):
                    continue
                if child.is_dir():
                    it = QTreeWidgetItem(parent_item, [child.name])
                    it.setData(0, Qt.UserRole, str(child))  # ★必須
                    it.setToolTip(0, str(child))
                    self.add_subfolders(it, child, depth+1, max_depth)
                elif hasattr(self, 'show_files_check') and self.show_files_check.isChecked():
                    # ファイル表示がオンの場合
                    file_it = QTreeWidgetItem(parent_item, [f"📄 {child.name}"])
                    file_it.setData(0, Qt.UserRole, str(child))  # ★ファイルもUserRole設定
                    file_it.setToolTip(0, str(child))
        except PermissionError:
            pass

    def add_all_items(self, parent_item, folder_path: Path, include_files: bool, max_depth: int, current_depth: int = 0):
        """フォルダとファイルを再帰的に追加（深さ制限付き）"""
        if current_depth >= max_depth:
            return
        
        try:
            items = list(folder_path.iterdir())
            items.sort(key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items[:1000]:  # 大量ファイル対策
                if item.name.startswith('.'):  # 隠しファイルスキップ
                    continue
                    
                child_item = QTreeWidgetItem(parent_item)
                
                if item.is_dir():
                    child_item.setText(0, f"📁 {item.name}")
                    child_item.setData(0, Qt.UserRole, str(item))
                    # 再帰的にサブフォルダを追加
                    self.add_all_items(child_item, item, include_files, max_depth, current_depth + 1)
                    
                elif include_files:
                    # ファイルを表示
                    child_item.setText(0, f"📄 {item.name}")
                    child_item.setData(0, Qt.UserRole, str(item))
                    # ファイルサイズを追加情報として表示
                    try:
                        size_mb = item.stat().st_size / 1024 / 1024
                        child_item.setToolTip(0, f"{item.name} ({size_mb:.2f} MB)")
                    except:
                        pass
                        
        except (PermissionError, OSError) as e:
            # アクセスできないフォルダの場合
            error_item = QTreeWidgetItem(parent_item)
            error_item.setText(0, f"⚠️ アクセス不可")
            error_item.setForeground(0, QBrush(QColor("#ff6666")))
    
    def refresh_folder_tree(self):
        """ファイル表示切り替え時にツリーを再構築"""
        # 現在の対象（フォルダ/ファイル）を保存
        paths = []
        for i in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(i)
            path_str = item.data(0, Qt.UserRole)
            if path_str:
                p = Path(path_str)
                if p.exists():
                    paths.append(p)
        
        # ツリーをクリアして再構築
        self.folder_tree.clear()
        for p in paths:
            self.add_path_item(p)
        self._add_placeholder_if_empty()

    def _add_placeholder_if_empty(self):
        """Ensure placeholder guidance item is present when tree is empty."""
        if self.folder_tree.topLevelItemCount() == 0:
            placeholder = QTreeWidgetItem(self.folder_tree)
            placeholder.setText(0, self.folder_placeholder_text)
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setForeground(0, QBrush(QColor("#666666")))
    
    def remove_selected_folders(self):
        """選択したフォルダを削除"""
        selected_items = self.folder_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "情報", "削除するフォルダを選択してください")
            return
            
        for item in selected_items:
            if item.parent() is None:  # トップレベルのみ削除
                index = self.folder_tree.indexOfTopLevelItem(item)
                if index >= 0:
                    self.folder_tree.takeTopLevelItem(index)
        
        # ツリーが空になったらプレースホルダーを追加
        self._add_placeholder_if_empty()

        self.status_bar.showMessage("選択したフォルダを削除しました")

    def remove_folders_by_name(self):
        """名前一致でフォルダを削除するダイアログを表示"""
        dialog = FolderNameDeleteDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        query = dialog.get_query()
        match_mode = dialog.get_match_mode()

        removed_paths = remove_folders_matching_query(
            self.folder_tree,
            getattr(self, "selected_paths", None),
            query,
            match_mode=match_mode,
        )

        if not removed_paths:
            QMessageBox.information(self, "情報", f"『{query}』に該当するフォルダは見つかりませんでした。")
            return

        self._add_placeholder_if_empty()

        match_label = "完全一致" if match_mode == MATCH_EXACT else "部分一致"
        preview_names = ", ".join(path.name for path in removed_paths[:3])
        if len(removed_paths) > 3:
            preview_names += " ..."

        if preview_names:
            message = f"{len(removed_paths)}件のフォルダを削除 ({match_label}): {preview_names}"
        else:
            message = f"{len(removed_paths)}件のフォルダを削除 ({match_label})"

        self.status_bar.showMessage(message)

    def clear_all_folders(self):
        """すべてのフォルダをクリア"""
        reply = QMessageBox.question(self, "確認", "すべてのフォルダをクリアしますか？")
        if reply == QMessageBox.Yes:
            self.folder_tree.clear()
            self.result_tree.clear()
            # プレースホルダーを追加
            self._add_placeholder_if_empty()
            self.status_bar.showMessage("フォルダリストをクリアしました")
    
    def dragEnterEvent(self, event):
        """ドラッグエンター時の処理"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            has_paths = any(Path(url.toLocalFile()).exists() for url in urls)
            if has_paths:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """ドラッグ移動時の処理（必須）"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            has_paths = any(Path(url.toLocalFile()).exists() for url in urls)
            if has_paths:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """複数フォルダ/ファイルのドロップ対応"""
        if not event.mimeData().hasUrls():
            event.ignore()
            return
            
        urls = event.mimeData().urls()
        added_count = 0
        
        for url in urls:
            try:
                path = Path(url.toLocalFile())
                if self.add_path_item(path):
                    added_count += 1
            except Exception as e:
                pass
                continue
                
        if added_count > 0:
            self.status_bar.showMessage(f"{added_count}件の対象（フォルダ/ファイル）を追加しました")
        else:
            self.status_bar.showMessage("有効なフォルダ/ファイルがドロップされませんでした")
            
        event.acceptProposedAction()
    
    def refresh_analysis(self):
        """解析を再実行"""
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            return
        self.run_analysis()

    def clear_all(self):
        """すべてクリア"""
        reply = QMessageBox.question(self, "確認", "すべてクリアしますか？")
        if reply == QMessageBox.Yes:
            self.folder_tree.clear()
            self.result_tree.clear()
            self.status_bar.showMessage("すべてクリアしました")
    
    def save_csv(self):
        """CSV保存"""
        if hasattr(self, 'save_results_to_csv'):
            self.save_results_to_csv()
        else:
            QMessageBox.information(self, "情報", "CSV保存機能を実装中です")
        
    def create_toolbar(self) -> QWidget:
        """シンプルな3段構成ツールバーを作成"""
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        main_layout = QVBoxLayout(toolbar)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(3)
        
        # 1段目: 入力系
        row1 = QHBoxLayout()
        
        add_btn = QPushButton("フォルダ追加")
        add_btn.setToolTip("Ctrl+O")
        add_btn.clicked.connect(self.add_folder_dialog)
        row1.addWidget(add_btn)
        
        refresh_btn = QPushButton("更新")
        refresh_btn.setToolTip("F5")
        refresh_btn.clicked.connect(self.refresh_folder_list)
        row1.addWidget(refresh_btn)
        
        row1.addStretch()
        
        analyze_btn = QPushButton("解析実行")
        analyze_btn.setObjectName("execute")
        analyze_btn.setToolTip("Ctrl+R")
        analyze_btn.clicked.connect(self.run_analysis)
        self._register_analysis_button(analyze_btn)
        row1.addWidget(analyze_btn)
        
        main_layout.addLayout(row1)
        
        # 2段目: 処理系（操作モード選択）
        row2 = QHBoxLayout()
        
        # シミュレーションチェック
        self.simulation_check = QCheckBox("シミュレーション")
        self.simulation_check.setChecked(True)
        self.simulation_check.toggled.connect(self.toggle_simulation_mode)
        row2.addWidget(self.simulation_check)
        
        row2.addWidget(QLabel("操作:"))
        
        # 操作モード選択（ラジオボタン）
        self.operation_group = QButtonGroup()
        self.copy_radio = QRadioButton("コピー")
        self.move_radio = QRadioButton("移動")
        self.link_radio = QRadioButton("リンク")
        self.copy_radio.setChecked(True)  # デフォルトはコピー
        
        self.operation_group.addButton(self.copy_radio, 0)
        self.operation_group.addButton(self.move_radio, 1)
        self.operation_group.addButton(self.link_radio, 2)
        
        row2.addWidget(self.copy_radio)
        row2.addWidget(self.move_radio)
        row2.addWidget(self.link_radio)
        row2.addStretch()
        
        sort_btn = QPushButton("整理実行")
        sort_btn.setObjectName("execute")
        sort_btn.clicked.connect(self._on_sort_clicked)
        row2.addWidget(sort_btn)
        
        flatten_btn = QPushButton("階層削除")
        flatten_btn.setObjectName("execute")
        flatten_btn.clicked.connect(self._on_flatten_clicked)
        row2.addWidget(flatten_btn)
        
        main_layout.addLayout(row2)
        
        # 3段目: 管理系
        row3 = QHBoxLayout()
        
        csv_btn = QPushButton("CSV保存")
        csv_btn.setToolTip("Ctrl+S")
        csv_btn.clicked.connect(self.save_results_to_csv)
        row3.addWidget(csv_btn)
        
        row3.addStretch()
        
        clear_btn = QPushButton("全クリア")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self.clear_all_folders)
        row3.addWidget(clear_btn)
        
        main_layout.addLayout(row3)
        
        return toolbar
        
    def create_folder_list(self) -> QWidget:
        """フォルダツリー構造表示"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # タイトル
        label = QLabel("解析対象フォルダ")
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(label)
        
        # QTreeWidgetに変更してフォルダ構造を表示
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabel("フォルダ構造")
        self.folder_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_tree.setAcceptDrops(True)
        self.folder_tree.setAlternatingRowColors(True)
        
        # ドラッグ&ドロップイベント
        self.folder_tree.dragEnterEvent = self.folder_tree_drag_enter
        self.folder_tree.dragMoveEvent = self.folder_tree_drag_move
        self.folder_tree.dropEvent = self.folder_tree_drop
        
        layout.addWidget(self.folder_tree)
        
        # ボタン
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("追加")
        add_btn.clicked.connect(self.add_folder_dialog)
        remove_btn = QPushButton("削除")
        remove_btn.setObjectName("danger")
        remove_btn.clicked.connect(self.remove_selected_folders)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        layout.addLayout(btn_layout)
        
        # 統計情報
        stats_group = QGroupBox("統計情報")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("フォルダ: 0個\n総ファイル: 未解析\n総サイズ: 未解析")
        self.stats_label.setObjectName("stats_text")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        return widget
        
    def folder_tree_drag_enter(self, event):
        """フォルダツリーのドラッグエンターイベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def folder_tree_drag_move(self, event):
        """フォルダツリーのドラッグムーブイベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def folder_tree_drop(self, event):
        """フォルダツリーのドロップイベント"""
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                paths.append(path)
        
        if paths:
            self.add_dropped_folders(paths)
            
        
    def create_result_panel(self) -> QWidget:
        """右パネル: シンプルな結果表示"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        
        # パネルタイトル
        title_label = QLabel("解析結果")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(title_label)
        
        # 結果ツリービュー
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["種類/拡張子", "件数", "サイズ(MB)", "平均サイズ"])
        self.result_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setRootIsDecorated(True)
        
        # カラム幅設定
        self.result_tree.setColumnWidth(0, 200)
        self.result_tree.setColumnWidth(1, 80)
        self.result_tree.setColumnWidth(2, 100)
        self.result_tree.setColumnWidth(3, 100)
        
        layout.addWidget(self.result_tree)
        
        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        progress_row = QHBoxLayout()
        self.progress_label = QLabel("準備完了")
        self.progress_label.setVisible(False)
        progress_row.addWidget(self.progress_label, 1)

        self.cancel_button = QPushButton("中止")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_scan)
        progress_row.addWidget(self.cancel_button, 0)

        layout.addLayout(progress_row)
        
        return panel
        
    def add_folder_dialog(self):
        """フォルダ選択ダイアログを表示"""
        folder = QFileDialog.getExistingDirectory(
            self, "解析対象フォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.add_folder_with_structure(Path(folder))
            
        
    def update_statistics(self):
        """統計情報を更新"""
        folder_count = 0
        file_count_input = 0
        if hasattr(self, "folder_tree"):
            for i in range(self.folder_tree.topLevelItemCount()):
                item = self.folder_tree.topLevelItem(i)
                raw = item.data(0, Qt.UserRole)
                if not raw:
                    continue
                p = Path(raw)
                if p.is_dir():
                    folder_count += 1
                elif p.is_file():
                    file_count_input += 1
        
        if self.scan_results:
            total_files = sum(data["count"] for data in self.scan_results.values())
            total_size = sum(data["size"] for data in self.scan_results.values())
            size_text = FileScanner.get_human_size(total_size)
            
            stats_text = (
                f"フォルダ: {folder_count}個 / ファイル: {file_count_input}個\n"
                f"総ファイル: {total_files:,}個\n総サイズ: {size_text}"
            )
        else:
            stats_text = (
                f"フォルダ: {folder_count}個 / ファイル: {file_count_input}個\n"
                "総ファイル: 未解析\n総サイズ: 未解析"
            )
            
        self.stats_label.setText(stats_text)
        
    def run_analysis(self):
        from pathlib import Path
        items = self.folder_tree.selectedItems()
        targets: List[Path] = []

        def top_root(item):
            while item.parent():
                item = item.parent()
            return item

        if items:
            for it in items:
                raw = it.data(0, Qt.UserRole)
                if not raw:
                    continue
                p = Path(raw)
                if p.exists():
                    targets.append(p)
        else:
            for i in range(self.folder_tree.topLevelItemCount()):
                it = self.folder_tree.topLevelItem(i)
                raw = it.data(0, Qt.UserRole)
                if not raw:
                    continue
                p = Path(raw)
                if p.exists():
                    targets.append(p)

        # 重複除去
        deduped = []
        seen = set()
        for p in targets:
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        targets = deduped

        # ディレクトリが選択されている場合、その配下の個別ファイルは除外して二重集計を防ぐ
        dir_targets = [p for p in targets if p.is_dir()]
        file_targets = [p for p in targets if p.is_file()]
        filtered_files = []
        for f in file_targets:
            covered = False
            for d in dir_targets:
                try:
                    f.relative_to(d)
                    covered = True
                    break
                except Exception:
                    continue
            if not covered:
                filtered_files.append(f)
        targets = dir_targets + filtered_files

        if not targets:
            QMessageBox.warning(self, "警告", "解析対象（フォルダ/ファイル）がありません。")
            return

        self.is_scanning = True
        self._set_analysis_controls_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, max(len(targets), 1))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_label.setText(f"[1/2] ファイル数を計測中… (0/{len(targets)})")
        self.progress_label.setVisible(True)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.status_bar.showMessage(f"[1/2] ファイル数を計測中… (0/{len(targets)})")
        self.result_tree.clear()

        self.thread = ScannerThread(targets)
        self.scanner_thread = self.thread
        self.latest_log_path = None

        self.thread.scan_started.connect(self.on_scan_started)
        self.thread.counting_progress.connect(self.update_counting_progress)
        self.thread.progress_updated.connect(self.update_scan_progress)
        self.thread.scan_completed.connect(self.display_scan_results)
        self.thread.scan_cancelled.connect(self.on_scan_cancelled)
        self.thread.error_occurred.connect(self.handle_scan_error)
        self.thread.log_ready.connect(self.on_scan_log_ready)
        self.thread.finished.connect(self.on_scan_thread_finished)
        self.thread.start()
        
    def cancel_scan(self):
        """現在の解析を中止"""
        if getattr(self, "thread", None) and self.thread.isRunning():
            self.cancel_button.setEnabled(False)
            self.progress_label.setText("中止をリクエストしています…")
            self.status_bar.showMessage("解析を中止しています…", 3000)
            self.thread.request_cancel()

    def on_scan_started(self, total_files: int):
        """走査開始時に総件数を設定"""
        if total_files > 0:
            self.progress_bar.setRange(0, total_files)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")
            self.progress_label.setText(f"[2/2] 解析中 0.0% (0/{total_files})")
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
            self.progress_bar.setFormat("100%")
            self.progress_label.setText("[2/2] 解析対象のファイルが見つかりませんでした")
        self.progress_label.setVisible(True)

    def update_counting_progress(self, processed_dirs: int, total_dirs: int, current_path: str):
        """ファイル数計測フェーズの進捗表示"""
        safe_total = max(total_dirs, 1)
        safe_processed = max(0, min(processed_dirs, safe_total))
        percent = (safe_processed / safe_total) * 100.0
        current_name = Path(current_path).name if current_path else "(計測中)"

        self.progress_bar.setRange(0, safe_total)
        self.progress_bar.setValue(safe_processed)
        self.progress_bar.setFormat("%p%")
        self.progress_label.setText(
            f"[1/2] ファイル数を計測中 {percent:5.1f}% ({safe_processed}/{safe_total}) - {current_name}"
        )
        self.status_bar.showMessage(
            f"[1/2] 計測中: {current_name} ({safe_processed}/{safe_total})"
        )

    def update_scan_progress(self, processed: int, total: int, current_path: str):
        """スキャンプログレスを更新"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(processed, total))
            percent = min(100.0, (processed / total) * 100) if total else 0.0
            self.progress_bar.setFormat("%p%")
            label_text = f"[2/2] 解析中 {percent:5.1f}% ({processed}/{total})"
        else:
            self.progress_bar.setRange(0, 0)
            label_text = f"[2/2] 解析中 {processed} 件処理済み"

        current_name = Path(current_path).name if current_path else "(解析中)"
        self.progress_label.setText(f"{label_text} - {current_name}")
        total_display = total if total > 0 else "?"
        self.status_bar.showMessage(f"[2/2] 解析中: {current_name} ({processed}/{total_display})")

    def display_scan_results(self, stats: Dict[str, Any], elapsed: float):
        """解析完了時の処理"""
        self._render_scan_results(stats)
        total_files = sum(data["count"] for data in stats.values())
        total_size = sum(data["size"] for data in stats.values())
        size_mb = total_size / (1024 * 1024) if total_size else 0

        summary = f"解析完了: {total_files:,}ファイル, {size_mb:.1f}MB"
        if elapsed is not None:
            summary += f" ({elapsed:.1f}秒)"
        if self.latest_log_path:
            summary += f" | ログ: {Path(self.latest_log_path).name}"

        self._reset_progress_ui(summary)
        self.status_bar.showMessage(summary, 7000)
        self.update_statistics()

    def on_scan_cancelled(self, stats: Dict[str, Any]):
        """ユーザーによる中止時の処理"""
        self.scan_results = stats
        if stats:
            self._render_scan_results(stats, show_empty_message=False)

        message = "解析を中止しました"
        if stats:
            message += "（途中結果を表示）"
        if self.latest_log_path:
            message += f" | ログ: {Path(self.latest_log_path).name}"

        self._reset_progress_ui(message)
        self.status_bar.showMessage(message, 7000)
        self.update_statistics()

    def on_scan_log_ready(self, log_path: str):
        """ログファイルの保存を通知"""
        self.latest_log_path = log_path
        if not self.is_scanning:
            self.status_bar.showMessage(f"ログを保存しました: {Path(log_path).name}", 5000)

    def on_scan_thread_finished(self):
        """スレッド完了時に参照をクリア"""
        self.thread = None
        self.scanner_thread = None

    def _render_scan_results(self, stats: Dict[str, Any], show_empty_message: bool = True):
        """結果ツリーを描画"""
        self.scan_results = stats
        self.result_tree.clear()

        if not stats:
            if show_empty_message:
                QMessageBox.information(self, "結果", "対象ファイルが見つかりませんでした。フォルダ内の拡張子やフィルタを確認してください。")
            return

        show_details = self.detail_check.isChecked() if hasattr(self, 'detail_check') else True
        icon_map = {
            "audio": "🎵", "video": "🎥", "image": "🖼️",
            "document": "📄", "archive": "📦", "other": "📁"
        }

        for media_type, data in stats.items():
            media_item = QTreeWidgetItem()
            icon = icon_map.get(media_type, "📁")
            media_item.setText(0, f"{icon} {media_type.capitalize()}")
            media_item.setText(1, f"{data['count']:,}")

            size_mb = data['size'] / (1024 * 1024) if data['size'] else 0
            media_item.setText(2, f"{size_mb:.1f}" if size_mb >= 0.1 else "< 0.1")

            if data['count'] > 0:
                avg_size = data['size'] // data['count']
                avg_mb = avg_size / (1024 * 1024)
                media_item.setText(3, f"{avg_mb:.2f}" if avg_mb >= 0.01 else "< 0.01")
            else:
                media_item.setText(3, "0")

            source_folders = data.get('source_folders', [])
            if source_folders:
                unique_sources = list(dict.fromkeys(source_folders))
                tooltip_text = f"ソースフォルダ ({len(unique_sources)}個):\n" + "\n".join(unique_sources[:5])
                if len(unique_sources) > 5:
                    tooltip_text += f"\n... 他{len(unique_sources) - 5}個"
                media_item.setToolTip(0, tooltip_text)

            self.result_tree.addTopLevelItem(media_item)

            if show_details and data.get('extensions'):
                for ext, count in sorted(data['extensions'].items(), key=lambda x: x[1], reverse=True):
                    ext_item = QTreeWidgetItem(media_item)
                    ext_name = ext if ext else "(拡張子なし)"
                    ext_item.setText(0, f"  📄 {ext_name}")
                    ext_item.setText(1, f"{count:,}")

                    if data['count'] > 0:
                        size_ratio = count / data['count']
                        estimated_total_size = data['size'] * size_ratio
                        est_mb = estimated_total_size / (1024 * 1024)
                        ext_item.setText(2, f"{est_mb:.1f}" if est_mb >= 0.1 else "< 0.1")

                        if count > 0:
                            avg_ext_size = estimated_total_size / count
                            avg_ext_mb = avg_ext_size / (1024 * 1024)
                            ext_item.setText(3, f"{avg_ext_mb:.2f}" if avg_ext_mb >= 0.01 else "< 0.01")

        if show_details:
            self.result_tree.expandAll()

    def handle_scan_error(self, error_message: str):
        """スキャンエラーを処理"""
        self._reset_progress_ui("解析エラー")
        QMessageBox.critical(self, "解析エラー", f"解析中にエラーが発生しました:\n\n{error_message}")
        message = "解析エラーが発生しました"
        if self.latest_log_path:
            message += f" | ログ: {Path(self.latest_log_path).name}"
        self.status_bar.showMessage(message, 7000)
        
    def toggle_simulation_mode(self, checked: bool):
        """シミュレーションモードを切り替え"""
        self.dry_run_mode = checked
        mode_text = "ON" if checked else "OFF"
        self.status_bar.showMessage(f"🧪 シミュレーションモード: {mode_text}", 3000)
        
    # フィルタ機能や詳細表示切替機能は削除してシンプルに
        
    def get_selected_tree_items(self) -> List[Dict[str, Any]]:
        """選択されたツリー項目を取得"""
        selected_items = []
        
        for item in self.result_tree.selectedItems():
            item_data = {
                "type": item.text(0).replace("📁 ", "").replace("📄 ", "").strip(),
                "count": item.text(1).replace(",", ""),
                "size": item.text(2),
                "parent": None
            }
            
            # 親項目がある場合（拡張子アイテム）
            if item.parent():
                item_data["parent"] = item.parent().text(0).replace("📁 ", "").strip()
                
            selected_items.append(item_data)
            
        return selected_items
        
    def get_selected_extensions(self) -> List[Dict[str, Any]]:
        """選択された拡張子のみを取得（フォルダは除外）"""
        selected_items = []
        
        for item in self.result_tree.selectedItems():
            # 拡張子項目のみを処理（子項目かどうかで判定）
            if item.parent() is not None:
                parent_text = item.parent().text(0).replace("📁 ", "").strip()
                ext_text = item.text(0).replace("📄 ", "").strip()
                
                item_data = {
                    "media_type": parent_text,
                    "extension": ext_text,
                    "count": int(item.text(1).replace(",", "")),
                    "size_mb": float(item.text(2)) if item.text(2) != "< 0.1" else 0.1
                }
                selected_items.append(item_data)
                
        return selected_items
        
                
        
    def save_results_to_csv(self):
        """解析結果をCSVに保存"""
        if not self.scan_results:
            QMessageBox.warning(self, "警告", "保存する解析結果がありません")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_results_{timestamp}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "解析結果をCSV保存", filename, "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # ヘッダー
                    writer.writerow([
                        '媒体タイプ', '拡張子', 'ファイル数', '合計サイズ(bytes)', 
                        '合計サイズ(読みやすい)', '平均サイズ(bytes)', 'ソースフォルダ数', 'タイムスタンプ'
                    ])
                    
                    # データ
                    for media_type, data in self.scan_results.items():
                        source_count = len(set(data.get('source_folders', [])))
                        
                        # メディアタイプサマリー行
                        writer.writerow([
                            media_type, 'すべて', data['count'], data['size'],
                            FileScanner.get_human_size(data['size']),
                            data['size'] // data['count'] if data['count'] > 0 else 0,
                            source_count, datetime.now().isoformat()
                        ])
                        
                        # 拡張子別行
                        for ext, count in data['extensions'].items():
                            ext_name = ext if ext else "(拡張子なし)"
                            estimated_size = (data['size'] * count) // data['count'] if data['count'] > 0 else 0
                            avg_size = estimated_size // count if count > 0 else 0
                            
                            writer.writerow([
                                media_type, ext_name, count, estimated_size,
                                FileScanner.get_human_size(estimated_size),
                                avg_size, source_count, datetime.now().isoformat()
                            ])
                
                QMessageBox.information(self, "保存完了", f"解析結果をCSVファイルに保存しました:\n{file_path}")
                self.status_bar.showMessage(f"CSV保存完了: {Path(file_path).name}", 5000)
                
            except Exception as e:
                QMessageBox.critical(self, "保存エラー", f"CSV保存エラー: {e}")
                
    def apply_theme(self):
        """テーマを適用"""
        # 親ウィンドウから継承するか、独自テーマを適用
        theme_file = Path("themes/pro.qss")
        if theme_file.exists():
            with open(theme_file, "r", encoding="utf-8") as f:
                base_style = f.read()
        else:
            base_style = self.get_fallback_theme()
            
        # Analyzer固有のスタイルを追加
        analyzer_style = """
            QWidget#toolbar {
                background-color: inherit;
                border-bottom: 1px solid #5c5c5c;
                padding: 5px;
            }
            
            QLabel#panel_title {
                font-size: 14px;
                font-weight: bold;
                color: #4ec9b0;
                padding: 5px 0;
                border-bottom: 1px solid #5c5c5c;
                margin-bottom: 10px;
            }
            
            QPushButton#analyze_button {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            
            QPushButton#analyze_button:hover {
                background-color: #218838;
            }
            
            QPushButton#operation_button {
                background-color: #17a2b8;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            
            QPushButton#operation_button:hover {
                background-color: #138496;
            }
            
            QLabel#stats_text {
                font-family: monospace;
                color: #cccccc;
                background-color: #2d2d30;
                padding: 10px;
                border-radius: 4px;
            }
        """
        
        self.setStyleSheet(base_style + analyzer_style)
        
    def get_fallback_theme(self) -> str:
        """フォールバック用テーマ"""
        return """
            QMainWindow { background-color: #2b2b2b; color: #ffffff; }
            QPushButton { 
                background-color: #3c3c3c; color: white; border: none; 
                padding: 8px 16px; border-radius: 4px; 
            }
            QPushButton:hover { background-color: #4c4c4c; }
            QTreeWidget { 
                background-color: #1e1e1e; color: #cccccc; 
                border: 1px solid #3c3c3c; 
            }
            QListWidget { 
                background-color: #1e1e1e; color: #cccccc; 
                border: 1px solid #3c3c3c; 
            }
        """
        
    def closeEvent(self, event):
        """ウィンドウクローズ時の処理"""
        # 実行中のスレッドを停止
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.terminate()
            self.scanner_thread.wait()
            
        event.accept()
