#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based Video Analysis and Processing Tool
Enhanced video analyzer with detailed metadata analysis using ffprobe
Based on the audio analyzer UI structure
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pathlib import Path
import sys
import json
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
import shutil
import subprocess
import re

# Import the scanner from core module
sys.path.append(str(Path(__file__).parent.parent))
from utils.ffprobe_finder import find_ffprobe

from .folder_tools import (
    FolderNameDeleteDialog,
    MATCH_EXACT,
    remove_folders_matching_query,
)

# Video processing utilities
def unique_name(dest_dir: Path, filename: str) -> Path:
    """Generate unique filename to avoid overwriting"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = Path(filename).stem
    ext = Path(filename).suffix
    candidate = dest_dir / f"{base}{ext}"
    counter = 1
    while candidate.exists():
        candidate = dest_dir / f"{base}_{counter:02d}{ext}"
        counter += 1
    return candidate

def send_to_trash(path: Path):
    """Move file to macOS trash"""
    trash = Path.home() / ".Trash"
    target = unique_name(trash, path.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

def check_ffprobe():
    """Check if ffprobe is available using utils finder"""
    ffprobe_path = find_ffprobe()
    if ffprobe_path:
        try:
            subprocess.run([ffprobe_path, '-version'], capture_output=True, check=True)
            return True, ffprobe_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False, None
    return False, None

def video_probe(path: Path) -> Dict[str, Any]:
    """Extract comprehensive video metadata using ffprobe"""
    info = {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size": 0,
        "mtime": None,
        "duration": None,
        "width": None,
        "height": None,
        "fps": None,
        "bitrate": None,
        "codec": None,
        "audio_codec": None,
        "audio_channels": None,
        "audio_sample_rate": None,
        "container": None,
        "title": None,
        "creation_time": None,
        "comment": None
    }
    
    try:
        stat = path.stat()
        info["size"] = stat.st_size
        info["mtime"] = stat.st_mtime
    except:
        pass
    
    if not check_ffprobe():
        return info
    
    try:
        # Run ffprobe to get detailed video information
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return info
        
        data = json.loads(result.stdout)
        
        # Extract format information
        format_info = data.get('format', {})
        info["duration"] = float(format_info.get('duration', 0))
        info["bitrate"] = int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
        info["container"] = format_info.get('format_name', '').upper()
        
        # Extract metadata
        tags = format_info.get('tags', {})
        info["title"] = tags.get('title') or tags.get('Title')
        info["creation_time"] = tags.get('creation_time') or tags.get('Creation Time')
        info["comment"] = tags.get('comment') or tags.get('Comment')
        
        # Extract stream information
        streams = data.get('streams', [])
        for stream in streams:
            codec_type = stream.get('codec_type')
            
            if codec_type == 'video':
                info["width"] = stream.get('width')
                info["height"] = stream.get('height')
                info["codec"] = stream.get('codec_name', '').upper()
                
                # Parse FPS
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    try:
                        num, den = fps_str.split('/')
                        if float(den) != 0:
                            info["fps"] = round(float(num) / float(den), 2)
                    except:
                        pass
            
            elif codec_type == 'audio':
                info["audio_codec"] = stream.get('codec_name', '').upper()
                info["audio_channels"] = stream.get('channels')
                info["audio_sample_rate"] = stream.get('sample_rate')
                if info["audio_sample_rate"]:
                    info["audio_sample_rate"] = int(info["audio_sample_rate"])
                
    except Exception as e:
        pass
    
    return info

def categorize_video(info: Dict[str, Any]) -> Dict[str, str]:
    """Categorize video file by various criteria"""
    categories = {}
    
    # Resolution category
    width = info.get("width")
    height = info.get("height")
    if width and height:
        if height <= 480:
            categories["resolution"] = "res_sd"
        elif height <= 720:
            categories["resolution"] = "res_hd"
        elif height <= 1080:
            categories["resolution"] = "res_full_hd"
        elif height <= 1440:
            categories["resolution"] = "res_2k"
        elif height <= 2160:
            categories["resolution"] = "res_4k"
        else:
            categories["resolution"] = "res_8k_plus"
    else:
        categories["resolution"] = "res_unknown"
    
    # Aspect ratio category
    if width and height:
        ratio = width / height
        if 1.2 <= ratio <= 1.4:
            categories["aspect"] = "aspect_4_3"
        elif 1.7 <= ratio <= 1.8:
            categories["aspect"] = "aspect_16_9"
        elif 2.3 <= ratio <= 2.5:
            categories["aspect"] = "aspect_21_9"
        elif ratio < 1.2:
            categories["aspect"] = "aspect_portrait"
        else:
            categories["aspect"] = "aspect_other"
    else:
        categories["aspect"] = "aspect_unknown"
    
    # FPS category
    fps = info.get("fps")
    if fps:
        if fps <= 25:
            categories["fps"] = "fps_cinematic"
        elif fps <= 30:
            categories["fps"] = "fps_standard"
        elif fps <= 60:
            categories["fps"] = "fps_smooth"
        elif fps <= 120:
            categories["fps"] = "fps_high"
        else:
            categories["fps"] = "fps_ultra"
    else:
        categories["fps"] = "fps_unknown"
    
    # Duration category
    duration = info.get("duration")
    if duration:
        if duration < 60:
            categories["duration"] = "dur_short"
        elif duration < 600:
            categories["duration"] = "dur_medium"
        elif duration < 3600:
            categories["duration"] = "dur_long"
        else:
            categories["duration"] = "dur_very_long"
    else:
        categories["duration"] = "dur_unknown"
    
    # Bitrate category
    bitrate = info.get("bitrate")
    if bitrate:
        bitrate_mbps = bitrate / 1_000_000
        if bitrate_mbps < 1:
            categories["bitrate"] = "br_very_low"
        elif bitrate_mbps < 5:
            categories["bitrate"] = "br_low"
        elif bitrate_mbps < 15:
            categories["bitrate"] = "br_medium"
        elif bitrate_mbps < 50:
            categories["bitrate"] = "br_high"
        else:
            categories["bitrate"] = "br_very_high"
    else:
        categories["bitrate"] = "br_unknown"
    
    # Codec category
    codec = info.get("codec")
    if codec:
        if codec in ["H264", "AVC"]:
            categories["codec"] = "codec_h264"
        elif codec in ["H265", "HEVC"]:
            categories["codec"] = "codec_h265"
        elif codec == "VP9":
            categories["codec"] = "codec_vp9"
        elif codec == "AV1":
            categories["codec"] = "codec_av1"
        elif codec in ["MPEG4", "XVID"]:
            categories["codec"] = "codec_mpeg4"
        else:
            categories["codec"] = "codec_other"
    else:
        categories["codec"] = "codec_unknown"
    
    # Container format
    ext = info.get("ext", "").lower()
    if ext == ".mp4":
        categories["format"] = "fmt_mp4"
    elif ext == ".mkv":
        categories["format"] = "fmt_mkv"
    elif ext == ".avi":
        categories["format"] = "fmt_avi"
    elif ext == ".mov":
        categories["format"] = "fmt_mov"
    elif ext == ".webm":
        categories["format"] = "fmt_webm"
    elif ext in [".m4v", ".3gp"]:
        categories["format"] = "fmt_mobile"
    else:
        categories["format"] = "fmt_other"
    
    # Date category
    mtime = info.get("mtime")
    if mtime:
        date = datetime.fromtimestamp(mtime)
        categories["date"] = f"{date.year}-{date.month:02d}"
    else:
        categories["date"] = "date_unknown"
    
    return categories


class VideoAnalysisThread(QThread):
    """Video analysis thread for detailed video file processing"""
    
    progress_updated = Signal(str, int, int)  # message, current, total
    analysis_completed = Signal(dict)         # analysis results
    error_occurred = Signal(str)              # error message
    
    def __init__(self, paths: List[Path]):
        super().__init__()
        self.paths = paths if isinstance(paths, list) else [paths]
        self.video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.3gp', '.flv', '.wmv', '.mpg', '.mpeg'}
    
    def run(self):
        """Analyze video files in the given paths"""
        try:
            results = {}
            total_files = 0
            processed = 0
            
            # Count total video files
            video_files = []
            for root_path in self.paths:
                if root_path.is_dir():
                    for file_path in root_path.rglob("*"):
                        if file_path.is_file() and file_path.suffix.lower() in self.video_extensions:
                            video_files.append(file_path)
            
            total_files = len(video_files)
            if total_files == 0:
                self.analysis_completed.emit({})
                return
            
            # Process each video file
            for file_path in video_files:
                self.progress_updated.emit(f"解析中: {file_path.name}", processed + 1, total_files)
                
                try:
                    # Get detailed video info
                    video_info = video_probe(file_path)
                    categories = categorize_video(video_info)
                    
                    # Organize by categories
                    for category_type, category_value in categories.items():
                        if category_type not in results:
                            results[category_type] = {}
                        
                        if category_value not in results[category_type]:
                            results[category_type][category_value] = {
                                "count": 0,
                                "total_size": 0,
                                "total_duration": 0,
                                "files": []
                            }
                        
                        category_data = results[category_type][category_value]
                        category_data["count"] += 1
                        category_data["total_size"] += video_info.get("size", 0)
                        duration = video_info.get("duration", 0)
                        if duration:
                            category_data["total_duration"] += duration
                        category_data["files"].append(video_info)
                
                except Exception as e:
                    continue  # Skip files that can't be analyzed
                
                processed += 1
            
            self.analysis_completed.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(str(e))


class VideoAnalyzerWindow(QMainWindow):
    """Enhanced video analyzer with comprehensive analysis and processing capabilities"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("動画解析・整理ツール")
        self.setGeometry(200, 200, 1400, 900)
        self.setMinimumSize(1200, 800)
        
        # Data management
        self.selected_paths: List[Path] = []
        self.analysis_results: Dict[str, Any] = {}
        self.analysis_thread: Optional[VideoAnalysisThread] = None
        self.folder_placeholder_text = "ここに動画フォルダをドラッグ&ドロップ"

        # Check ffprobe availability
        if not check_ffprobe():
            QMessageBox.warning(None, "ffprobe未検出", 
                "ffprobeが見つかりません。動画の詳細解析機能が制限されます。\n"
                "ffmpegをインストールしてffprobeを利用可能にしてください。")
        
        self.init_ui()
        self.apply_pro_theme()
        self.setAcceptDrops(True)
    
    def init_ui(self):
        """Initialize the UI layout similar to audio analyzer"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Main splitter (vertical)
        vsplitter = QSplitter(Qt.Vertical)
        
        # Top: Video folder tree
        folder_widget = self.create_folder_tree_widget()
        vsplitter.addWidget(folder_widget)
        
        # Middle: Toolbar and analysis results
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)
        
        # Toolbar
        toolbar = self.create_toolbar()
        bottom_layout.addWidget(toolbar)
        
        # Analysis results and processing options in horizontal splitter
        hsplitter = QSplitter(Qt.Horizontal)
        
        # Left: Analysis results
        result_widget = self.create_result_widget()
        hsplitter.addWidget(result_widget)
        
        # Right: Processing options
        options_widget = self.create_options_widget()
        hsplitter.addWidget(options_widget)
        
        hsplitter.setSizes([700, 400])
        bottom_layout.addWidget(hsplitter)
        
        vsplitter.addWidget(bottom_widget)
        vsplitter.setSizes([300, 600])
        
        main_layout.addWidget(vsplitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("動画ファイルフォルダを追加して解析を開始してください")
    
    def create_folder_tree_widget(self):
        """Create folder tree widget for video folders"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("動画フォルダ"))
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Tree view
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_tree.setAcceptDrops(True)
        self.folder_tree.setMinimumHeight(200)
        
        # Placeholder
        self._add_placeholder_if_empty()

        layout.addWidget(self.folder_tree)

        return widget

    def _add_placeholder_if_empty(self):
        """Ensure placeholder guidance item is present when tree is empty."""
        if self.folder_tree.topLevelItemCount() == 0:
            placeholder = QTreeWidgetItem(self.folder_tree)
            placeholder.setText(0, self.folder_placeholder_text)
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setForeground(0, QBrush(QColor("#666666")))
    
    def create_toolbar(self):
        """Create toolbar with video-specific options"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Folder selection
        add_btn = QPushButton("フォルダ選択")
        add_btn.clicked.connect(self.select_video_folders)
        layout.addWidget(add_btn)
        
        # Remove selected
        remove_btn = QPushButton("選択削除")
        remove_btn.clicked.connect(self.remove_selected_folders)
        layout.addWidget(remove_btn)

        name_remove_btn = QPushButton("名前で削除")
        name_remove_btn.clicked.connect(self.remove_folders_by_name)
        layout.addWidget(name_remove_btn)

        # Analysis
        analyze_btn = QPushButton("動画解析実行")
        analyze_btn.setStyleSheet("background-color: #2d5a2d; color: white; font-weight: bold;")
        analyze_btn.clicked.connect(self.run_video_analysis)
        layout.addWidget(analyze_btn)
        
        layout.addWidget(QLabel("|"))
        
        # Processing mode
        layout.addWidget(QLabel("処理モード:"))
        self.processing_mode = QComboBox()
        self.processing_mode.addItems(["動画整理", "フラット化"])
        layout.addWidget(self.processing_mode)
        
        # Dry run
        self.dry_run_check = QCheckBox("シミュレーション")
        self.dry_run_check.setChecked(True)
        layout.addWidget(self.dry_run_check)
        
        layout.addStretch()
        
        # Clear all
        clear_btn = QPushButton("全クリア")
        clear_btn.setStyleSheet("color: #a94442;")
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)
        
        return toolbar
    
    def create_result_widget(self):
        """Create analysis results widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QLabel("動画解析結果")
        layout.addWidget(header)
        
        # Category tabs
        self.result_tabs = QTabWidget()
        
        # Create tabs for different analysis categories
        self.create_analysis_tabs()
        
        layout.addWidget(self.result_tabs)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return widget
    
    def create_analysis_tabs(self):
        """Create tabs for different video analysis categories"""
        categories = [
            ("フォーマット", "format"),
            ("解像度", "resolution"), 
            ("アスペクト比", "aspect"),
            ("FPS", "fps"),
            ("時間", "duration"),
            ("ビットレート", "bitrate"),
            ("コーデック", "codec"),
            ("日付", "date")
        ]
        
        self.category_trees = {}
        
        for tab_name, category_key in categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            tree = QTreeWidget()
            tree.setHeaderLabels(["カテゴリ", "ファイル数", "合計サイズ", "合計時間"])
            tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
            tree.setAlternatingRowColors(True)
            
            tab_layout.addWidget(tree)
            self.result_tabs.addTab(tab_widget, tab_name)
            self.category_trees[category_key] = tree
    
    def create_options_widget(self):
        """Create processing options widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Processing options
        options_group = QGroupBox("処理オプション")
        options_layout = QVBoxLayout(options_group)
        
        # Format selection for flattening
        format_group = QGroupBox("保持フォーマット (フラット化時)")
        format_layout = QVBoxLayout(format_group)
        
        self.format_checks = {}
        formats = [
            ("mp4", "MP4", True),
            ("mkv", "MKV", False),
            ("avi", "AVI", False),
            ("mov", "MOV", False),
            ("webm", "WebM", False)
        ]
        
        for fmt_key, fmt_label, default in formats:
            check = QCheckBox(fmt_label)
            check.setChecked(default)
            self.format_checks[fmt_key] = check
            format_layout.addWidget(check)
        
        options_layout.addWidget(format_group)
        
        # Sorting criteria with advanced options
        sort_group = QGroupBox("整理基準")
        sort_layout = QVBoxLayout(sort_group)
        
        self.sort_criterion = QComboBox()
        self.sort_criterion.addItems([
            "フォーマット別",
            "解像度別", 
            "アスペクト比別",
            "FPS別",
            "時間別",
            "ビットレート別",
            "コーデック別",
            "日付別"
        ])
        sort_layout.addWidget(self.sort_criterion)
        
        # Advanced sorting options
        advanced_sort_group = QGroupBox("条件整理オプション")
        advanced_sort_layout = QVBoxLayout(advanced_sort_group)
        
        # Multi-criteria sorting
        multi_sort_layout = QHBoxLayout()
        multi_sort_layout.addWidget(QLabel("複数条件:"))
        
        self.multi_sort_check = QCheckBox("有効")
        multi_sort_layout.addWidget(self.multi_sort_check)
        
        self.secondary_criterion = QComboBox()
        self.secondary_criterion.addItems([
            "なし",
            "フォーマット別",
            "解像度別", 
            "アスペクト比別",
            "FPS別",
            "時間別",
            "ビットレート別",
            "コーデック別",
            "日付別"
        ])
        self.secondary_criterion.setEnabled(False)
        multi_sort_layout.addWidget(self.secondary_criterion)
        
        self.multi_sort_check.toggled.connect(self.secondary_criterion.setEnabled)
        advanced_sort_layout.addLayout(multi_sort_layout)
        
        # Conditional filtering
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("フィルター:"))
        
        self.filter_enabled = QCheckBox("有効")
        filter_layout.addWidget(self.filter_enabled)
        
        self.filter_type = QComboBox()
        self.filter_type.addItems(["解像度", "時間", "サイズ", "ビットレート"])
        self.filter_type.setEnabled(False)
        filter_layout.addWidget(self.filter_type)
        
        self.filter_condition = QComboBox()
        self.filter_condition.addItems(["以上", "以下", "範囲"])
        self.filter_condition.setEnabled(False)
        filter_layout.addWidget(self.filter_condition)
        
        self.filter_value = QLineEdit()
        self.filter_value.setPlaceholderText("値を入力")
        self.filter_value.setEnabled(False)
        filter_layout.addWidget(self.filter_value)
        
        def toggle_filter_controls(enabled):
            self.filter_type.setEnabled(enabled)
            self.filter_condition.setEnabled(enabled)
            self.filter_value.setEnabled(enabled)
        
        self.filter_enabled.toggled.connect(toggle_filter_controls)
        advanced_sort_layout.addLayout(filter_layout)
        
        sort_layout.addWidget(advanced_sort_group)
        options_layout.addWidget(sort_group)
        
        # Additional options
        additional_group = QGroupBox("追加オプション")
        additional_layout = QVBoxLayout(additional_group)
        
        self.delete_zip_check = QCheckBox("ZIP/圧縮ファイルを削除")
        self.delete_zip_check.setChecked(True)
        additional_layout.addWidget(self.delete_zip_check)
        
        self.remove_empty_check = QCheckBox("空フォルダを削除")
        self.remove_empty_check.setChecked(True)
        additional_layout.addWidget(self.remove_empty_check)
        
        self.use_trash_check = QCheckBox("不要ファイルをゴミ箱へ")
        additional_layout.addWidget(self.use_trash_check)
        
        options_layout.addWidget(additional_group)
        
        layout.addWidget(options_group)
        
        # Execute buttons
        button_layout = QHBoxLayout()
        
        execute_btn = QPushButton("実行")
        execute_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px;")
        execute_btn.clicked.connect(self.execute_processing)
        button_layout.addWidget(execute_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return widget
    
    def apply_pro_theme(self):
        """Apply Pro (dark) theme"""
        pro_theme_file = Path("themes/pro.qss")
        if pro_theme_file.exists():
            with open(pro_theme_file, "r", encoding="utf-8") as f:
                base_style = f.read()
        else:
            base_style = self.get_fallback_theme()
            
        # Video analyzer specific styles
        video_style = """
            QTabWidget::pane {
                border: 1px solid #5c5c5c;
                background-color: #2b2b2b;
            }
            
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #cccccc;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #007acc;
                color: #ffffff;
                font-weight: bold;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #4c4c4c;
            }
        """
        
        self.setStyleSheet(base_style + video_style)
    
    def get_fallback_theme(self) -> str:
        """Fallback theme for Pro style"""
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
            QGroupBox { 
                color: #ffffff; border: 1px solid #5c5c5c; 
                border-radius: 5px; margin-top: 15px; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #4ec9b0;
            }
        """
    
    def select_video_folders(self):
        """Select video folders for analysis"""
        folder = QFileDialog.getExistingDirectory(
            self, "動画フォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.add_video_folder(Path(folder))
    
    def remove_selected_folders(self):
        """Remove selected folders from the list"""
        selected_items = self.folder_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "情報", "削除するフォルダを選択してください")
            return
            
        for item in selected_items:
            if item.parent() is None:  # Top level only
                path_str = item.data(0, Qt.UserRole)
                if path_str:
                    path_to_remove = Path(path_str)
                    if path_to_remove in self.selected_paths:
                        self.selected_paths.remove(path_to_remove)
                
                index = self.folder_tree.indexOfTopLevelItem(item)
                if index >= 0:
                    self.folder_tree.takeTopLevelItem(index)
        
        # Add placeholder if empty
        self._add_placeholder_if_empty()

        self.status_bar.showMessage("選択したフォルダを削除しました")

    def remove_folders_by_name(self):
        """Remove folders whose names match user-specified criteria."""
        dialog = FolderNameDeleteDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        query = dialog.get_query()
        match_mode = dialog.get_match_mode()

        removed_paths = remove_folders_matching_query(
            self.folder_tree,
            self.selected_paths,
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

        message = (
            f"{len(removed_paths)}件のフォルダを削除 ({match_label}): {preview_names}"
            if preview_names else
            f"{len(removed_paths)}件のフォルダを削除 ({match_label})"
        )
        self.status_bar.showMessage(message)

    def run_video_analysis(self):
        """Run detailed video analysis"""
        if not self.selected_paths:
            QMessageBox.warning(self, "警告", "解析する動画フォルダがありません")
            return
        
        # Clear previous results
        for tree in self.category_trees.values():
            tree.clear()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start analysis thread
        self.analysis_thread = VideoAnalysisThread(self.selected_paths)
        self.analysis_thread.progress_updated.connect(self.update_analysis_progress)
        self.analysis_thread.analysis_completed.connect(self.display_analysis_results)
        self.analysis_thread.error_occurred.connect(self.handle_analysis_error)
        self.analysis_thread.finished.connect(lambda: self.progress_bar.setVisible(False))
        self.analysis_thread.start()
    
    def update_analysis_progress(self, message: str, current: int, total: int):
        """Update analysis progress"""
        self.status_bar.showMessage(f"{message} ({current}/{total})")
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
    
    def display_analysis_results(self, results: Dict[str, Any]):
        """Display detailed analysis results in category tabs"""
        self.analysis_results = results
        
        if not results:
            QMessageBox.information(self, "結果", "動画ファイルが見つかりませんでした")
            return
        
        # Category display names
        category_names = {
            "format": {"fmt_mp4": "MP4", "fmt_mkv": "MKV", "fmt_avi": "AVI", "fmt_mov": "MOV", "fmt_webm": "WebM", "fmt_mobile": "モバイル", "fmt_other": "その他"},
            "resolution": {"res_sd": "SD (480p以下)", "res_hd": "HD (720p)", "res_full_hd": "Full HD (1080p)", "res_2k": "2K (1440p)", "res_4k": "4K (2160p)", "res_8k_plus": "8K+", "res_unknown": "不明"},
            "aspect": {"aspect_4_3": "4:3", "aspect_16_9": "16:9", "aspect_21_9": "21:9", "aspect_portrait": "縦型", "aspect_other": "その他", "aspect_unknown": "不明"},
            "fps": {"fps_cinematic": "シネマ (24-25fps)", "fps_standard": "標準 (30fps)", "fps_smooth": "スムーズ (60fps)", "fps_high": "高フレーム (120fps)", "fps_ultra": "超高フレーム (120fps+)", "fps_unknown": "不明"},
            "duration": {"dur_short": "短い (1分未満)", "dur_medium": "中程度 (1-10分)", "dur_long": "長い (10分-1時間)", "dur_very_long": "とても長い (1時間+)", "dur_unknown": "不明"},
            "bitrate": {"br_very_low": "極低ビットレート (<1Mbps)", "br_low": "低ビットレート (1-5Mbps)", "br_medium": "中ビットレート (5-15Mbps)", "br_high": "高ビットレート (15-50Mbps)", "br_very_high": "超高ビットレート (50Mbps+)", "br_unknown": "不明"},
            "codec": {"codec_h264": "H.264/AVC", "codec_h265": "H.265/HEVC", "codec_vp9": "VP9", "codec_av1": "AV1", "codec_mpeg4": "MPEG-4", "codec_other": "その他", "codec_unknown": "不明"},
            "date": {}
        }
        
        # Populate category trees
        for category, tree in self.category_trees.items():
            tree.clear()
            if category not in results:
                continue
                
            category_data = results[category]
            names = category_names.get(category, {})
            
            for subcategory, data in category_data.items():
                # Create main item
                display_name = names.get(subcategory, subcategory)
                item = QTreeWidgetItem(tree)
                item.setText(0, display_name)
                item.setText(1, f"{data['count']:,}")
                
                # Size
                size_mb = data['total_size'] / (1024 * 1024)
                if size_mb >= 1024:
                    size_gb = size_mb / 1024
                    item.setText(2, f"{size_gb:.1f} GB")
                else:
                    item.setText(2, f"{size_mb:.1f} MB" if size_mb >= 0.1 else "< 0.1 MB")
                
                # Duration
                total_duration = data.get('total_duration', 0)
                if total_duration > 0:
                    hours = int(total_duration // 3600)
                    minutes = int((total_duration % 3600) // 60)
                    seconds = int(total_duration % 60)
                    if hours > 0:
                        duration_str = f"{hours}h {minutes}m {seconds}s"
                    else:
                        duration_str = f"{minutes}m {seconds}s"
                    item.setText(3, duration_str)
                else:
                    item.setText(3, "不明")
                
                # Store data for processing
                item.setData(0, Qt.UserRole, subcategory)
        
        # Expand all trees
        for tree in self.category_trees.values():
            tree.expandAll()
            tree.resizeColumnToContents(0)
        
        self.status_bar.showMessage(f"動画解析完了: {sum(len(cat_data) for cat_data in results.values())} カテゴリ")
    
    def handle_analysis_error(self, error_message: str):
        """Handle analysis errors"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "解析エラー", f"動画解析中にエラーが発生しました:\n\n{error_message}")
        self.status_bar.showMessage("動画解析エラー")
    
    def execute_processing(self):
        """Execute video processing based on settings"""
        if not self.analysis_results:
            QMessageBox.warning(self, "警告", "先に動画解析を実行してください")
            return
        
        # Get current tab (category) and selected items
        current_tab = self.result_tabs.currentIndex()
        if current_tab < 0:
            return
        
        category_keys = list(self.category_trees.keys())
        if current_tab >= len(category_keys):
            return
        
        current_category = category_keys[current_tab]
        current_tree = self.category_trees[current_category]
        selected_items = current_tree.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "警告", "処理対象を選択してください")
            return
        
        # Get selected files
        selected_files = []
        for item in selected_items:
            subcategory = item.data(0, Qt.UserRole)
            if subcategory and current_category in self.analysis_results:
                category_data = self.analysis_results[current_category].get(subcategory, {})
                files = category_data.get('files', [])
                selected_files.extend(files)
        
        if not selected_files:
            QMessageBox.warning(self, "警告", "処理対象ファイルがありません")
            return
        
        # Get output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "出力先フォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not output_dir:
            return
        
        # Execute processing
        self._execute_video_processing(selected_files, Path(output_dir))
    
    def _execute_video_processing(self, files: List[Dict], output_dir: Path):
        """Execute the actual video processing"""
        mode = self.processing_mode.currentText()
        is_dry_run = self.dry_run_check.isChecked()
        
        success_count = 0
        error_count = 0
        
        for file_info in files:
            try:
                source_path = Path(file_info['path'])
                if not source_path.exists():
                    error_count += 1
                    continue
                
                if mode == "フラット化":
                    # Flatten: move to output directory root
                    target_path = unique_name(output_dir, source_path.name)
                elif mode == "動画整理":
                    # Sort by current category
                    current_tab = self.result_tabs.currentIndex()
                    category_keys = list(self.category_trees.keys())
                    if current_tab < len(category_keys):
                        category = category_keys[current_tab]
                        # Create subdirectory based on category
                        categories = categorize_video(file_info)
                        subdir_name = categories.get(category, "unknown")
                        subdir = output_dir / subdir_name
                        target_path = unique_name(subdir, source_path.name)
                    else:
                        target_path = unique_name(output_dir, source_path.name)
                else:
                    target_path = unique_name(output_dir, source_path.name)
                
                if not is_dry_run:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        # Show results
        mode_text = "シミュレーション" if is_dry_run else "実行"
        result_text = f"{mode} {mode_text}が完了しました\n\n成功: {success_count}ファイル\nエラー: {error_count}ファイル"
        QMessageBox.information(self, "処理完了", result_text)
        
        self.status_bar.showMessage(f"処理完了: 成功{success_count}、エラー{error_count}")
    
    def clear_all(self):
        """Clear all data"""
        reply = QMessageBox.question(self, "確認", "すべてをクリアしますか？")
        if reply == QMessageBox.Yes:
            self.selected_paths.clear()
            self.analysis_results.clear()
            self.folder_tree.clear()
            for tree in self.category_trees.values():
                tree.clear()
            
            # Add placeholder
            self._add_placeholder_if_empty()
            
            self.status_bar.showMessage("すべてクリアしました")
    
    # Drag and drop support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = Path(url.toLocalFile())
                if path.is_dir():
                    self.add_video_folder(path)
            event.acceptProposedAction()
    
    def add_video_folder(self, folder_path: Path):
        """Add video folder to the analysis list"""
        # Remove placeholder if present
        if self.folder_tree.topLevelItemCount() == 1:
            item = self.folder_tree.topLevelItem(0)
            if item.text(0) == self.folder_placeholder_text:
                self.folder_tree.clear()
        
        # Check if already exists
        if folder_path in self.selected_paths:
            return
        
        # Add to paths list
        self.selected_paths.append(folder_path)
        
        # Add to tree
        root_item = QTreeWidgetItem(self.folder_tree, [folder_path.name])
        root_item.setData(0, Qt.UserRole, str(folder_path))
        root_item.setToolTip(0, str(folder_path))
        
        # Add video files as children
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.3gp', '.flv', '.wmv', '.mpg', '.mpeg'}
        video_count = 0
        
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    video_count += 1
                    if video_count <= 100:  # Limit display for performance
                        child_item = QTreeWidgetItem(root_item)
                        child_item.setText(0, f"🎥 {file_path.name}")
                        child_item.setData(0, Qt.UserRole, str(file_path))
                        child_item.setToolTip(0, str(file_path))
            
            if video_count > 100:
                more_item = QTreeWidgetItem(root_item)
                more_item.setText(0, f"... 他{video_count - 100}個の動画ファイル")
                more_item.setFlags(Qt.NoItemFlags)
                more_item.setForeground(0, QBrush(QColor("#888888")))
        
        except Exception:
            pass
        
        root_item.setExpanded(True)
        self.status_bar.showMessage(f"動画フォルダを追加しました: {folder_path.name} ({video_count}ファイル)")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = VideoAnalyzerWindow()
    window.show()
    sys.exit(app.exec())
