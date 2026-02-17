#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File processing logic - Sort/Flatten operations
"""

from pathlib import Path
from typing import List, Dict, Optional, Callable
import shutil
from datetime import datetime


class FileProcessor:
    """ファイル処理エンジン（Sort/Flatten操作）"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.operations_log = []
    
    def flatten_directory(
        self, 
        source_dir: Path, 
        target_dir: Path, 
        file_types: List[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        フォルダをフラット化
        
        Args:
            source_dir: ソースディレクトリ
            target_dir: ターゲットディレクトリ
            file_types: 処理対象の拡張子リスト（None=全て）
            progress_callback: プログレスコールバック
        
        Returns:
            処理結果の統計
        """
        stats = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "operations": []
        }
        
        if not source_dir.exists():
            return stats
        
        # ファイル収集
        files_to_process = []
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                if file_types is None or file_path.suffix.lower() in file_types:
                    files_to_process.append(file_path)
        
        total_files = len(files_to_process)
        
        for i, file_path in enumerate(files_to_process):
            try:
                # 重複回避のファイル名生成
                target_path = self._get_unique_target_path(target_dir, file_path.name)
                
                operation = {
                    "source": str(file_path),
                    "target": str(target_path),
                    "operation": "flatten",
                    "timestamp": datetime.now().isoformat()
                }
                
                if not self.dry_run:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file_path), str(target_path))
                
                stats["processed"] += 1
                stats["operations"].append(operation)
                self.operations_log.append(operation)
                
                if progress_callback:
                    progress = int((i + 1) / total_files * 100)
                    progress_callback(progress, f"処理中: {file_path.name}")
                    
            except Exception as e:
                stats["errors"] += 1
                error_op = {
                    "source": str(file_path),
                    "error": str(e),
                    "operation": "flatten_error"
                }
                stats["operations"].append(error_op)
        
        return stats
    
    def sort_by_type(
        self,
        source_dir: Path,
        target_base_dir: Path,
        media_mapping: Dict[str, List[str]],
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        媒体タイプ別にファイルを仕分け
        
        Args:
            source_dir: ソースディレクトリ
            target_base_dir: ベースターゲットディレクトリ
            media_mapping: 媒体マッピング
            progress_callback: プログレスコールバック
        
        Returns:
            処理結果の統計
        """
        stats = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "operations": [],
            "by_type": {}
        }
        
        if not source_dir.exists():
            return stats
        
        # ファイル収集
        files_to_process = []
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                files_to_process.append(file_path)
        
        total_files = len(files_to_process)
        
        for i, file_path in enumerate(files_to_process):
            try:
                # 媒体タイプ判定
                ext = file_path.suffix.lower()
                media_type = self._detect_media_type(ext, media_mapping)
                
                # ターゲットディレクトリ作成
                type_dir = target_base_dir / media_type
                target_path = self._get_unique_target_path(type_dir, file_path.name)
                
                operation = {
                    "source": str(file_path),
                    "target": str(target_path),
                    "media_type": media_type,
                    "operation": "sort_by_type",
                    "timestamp": datetime.now().isoformat()
                }
                
                if not self.dry_run:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file_path), str(target_path))
                
                stats["processed"] += 1
                stats["operations"].append(operation)
                stats["by_type"].setdefault(media_type, 0)
                stats["by_type"][media_type] += 1
                
                if progress_callback:
                    progress = int((i + 1) / total_files * 100)
                    progress_callback(progress, f"処理中: {file_path.name} -> {media_type}")
                    
            except Exception as e:
                stats["errors"] += 1
                error_op = {
                    "source": str(file_path),
                    "error": str(e),
                    "operation": "sort_error"
                }
                stats["operations"].append(error_op)
        
        return stats
    
    def _get_unique_target_path(self, target_dir: Path, filename: str) -> Path:
        """重複しないファイルパスを生成"""
        target_dir.mkdir(parents=True, exist_ok=True)
        
        base_path = target_dir / filename
        if not base_path.exists():
            return base_path
        
        # 重複する場合は連番を付与
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        
        while True:
            new_filename = f"{stem}_{counter:02d}{suffix}"
            new_path = target_dir / new_filename
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _detect_media_type(self, ext: str, media_mapping: Dict[str, List[str]]) -> str:
        """拡張子から媒体タイプを判定"""
        for media_type, extensions in media_mapping.items():
            if ext in extensions:
                return media_type
        return "other"
    
    def get_operations_log(self) -> List[Dict]:
        """操作ログを取得"""
        return self.operations_log.copy()
    
    def clear_log(self):
        """ログをクリア"""
        self.operations_log.clear()