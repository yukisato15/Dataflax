#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File scanning logic - UI independent
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
from collections import defaultdict
from threading import Event
import os


class FileScanner:
    """UIに依存しないファイル走査ロジック"""
    
    # 媒体マッピング
    MEDIA_MAPPING = {
        "video": [".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mts", ".flv", ".wmv", ".mxf"],
        "audio": [".wav", ".aiff", ".aif", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"],
        "image": [".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".heic", ".webp", ".svg", ".raw", ".dng", ".cr2", ".nef"],
        "document": [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".md", ".rtf", ".csv", ".odt"],
        "3d": [".glb", ".gltf", ".fbx", ".obj", ".stl", ".ply", ".usdz", ".dae", ".3ds", ".blend"],
    }
    
    @staticmethod
    def is_hidden(path: Union[Path, str]) -> bool:
        """隠しファイル判定（.で始まる、._で始まる等）"""
        name = path if isinstance(path, str) else path.name
        return name.startswith(".") or name.startswith("._")

    @staticmethod
    def count_files(path: Path, cancel_event: Optional[Event] = None) -> int:
        """ディレクトリ内のファイル数を再帰的にカウント"""
        if not path.exists() or not path.is_dir():
            return 0

        total = 0
        stack = [path]

        while stack:
            if cancel_event and cancel_event.is_set():
                break

            current_dir = stack.pop()
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if cancel_event and cancel_event.is_set():
                            break

                        if FileScanner.is_hidden(entry.name):
                            continue

                        entry_path = Path(entry.path)

                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry_path)
                            elif entry.is_file(follow_symlinks=False):
                                total += 1
                        except (OSError, PermissionError):
                            continue

            except (OSError, PermissionError):
                continue

        return total
    
    @staticmethod
    def scan_directory(
        path: Path,
        progress_callback=None,
        cancel_event: Optional[Event] = None,
    ) -> Dict[str, Dict]:
        """
        ディレクトリを走査して媒体別統計を返す
        
        Args:
            path: 走査対象ディレクトリ
            progress_callback: プログレス通知用コールバック（オプション）
        
        Returns:
            Dict[str, Dict]: 媒体別統計情報
        """
        stats = defaultdict(lambda: {
            "count": 0, 
            "size": 0, 
            "extensions": defaultdict(int),
            "files": []
        })
        
        if not path.exists() or not path.is_dir():
            return dict(stats)
        
        processed = 0
        total_files = 0

        try:
            if progress_callback:
                total_files = FileScanner.count_files(path, cancel_event)
                progress_callback(processed, total_files, str(path))
                if cancel_event and cancel_event.is_set():
                    return dict(stats)

            stack = [path]

            while stack:
                if cancel_event and cancel_event.is_set():
                    break

                current_dir = stack.pop()
                try:
                    with os.scandir(current_dir) as entries:
                        for entry in entries:
                            if cancel_event and cancel_event.is_set():
                                break

                            if FileScanner.is_hidden(entry.name):
                                continue

                            entry_path = Path(entry.path)

                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    stack.append(entry_path)
                                    continue

                                if not entry.is_file(follow_symlinks=False):
                                    continue

                                ext = entry_path.suffix.lower()
                                media_type = FileScanner.detect_media_type(ext)
                                size = entry.stat(follow_symlinks=False).st_size

                                stats[media_type]["count"] += 1
                                stats[media_type]["size"] += size
                                stats[media_type]["extensions"][ext] += 1
                                stats[media_type]["files"].append(str(entry_path))

                                processed += 1

                                if progress_callback:
                                    progress_callback(processed, total_files, str(entry_path))

                            except (OSError, PermissionError):
                                # ファイルアクセスエラーはスキップ
                                continue

                except (OSError, PermissionError):
                    # ディレクトリアクセスエラーはスキップ
                    continue

        except (OSError, PermissionError):
            pass

        return dict(stats)

    @staticmethod
    def detect_media_type(ext: str) -> str:
        """拡張子から媒体タイプを判定"""
        ext_lower = ext.lower()
        
        for media, extensions in FileScanner.MEDIA_MAPPING.items():
            if ext_lower in extensions:
                return media
        
        return "other"
    
    @staticmethod
    def get_human_size(bytes_size: int) -> str:
        """バイト数を人間が読みやすい形式に変換"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    
    @staticmethod
    def scan_multiple_directories(
        paths: List[Path],
        progress_callback=None,
        cancel_event: Optional[Event] = None,
    ) -> Dict[str, Dict]:
        """
        複数ディレクトリを走査して統合結果を返す
        
        Args:
            paths: 走査対象ディレクトリリスト
            progress_callback: プログレス通知用コールバック
            
        Returns:
            Dict[str, Dict]: 統合された媒体別統計情報
        """
        combined_stats = defaultdict(lambda: {
            "count": 0, 
            "size": 0, 
            "extensions": defaultdict(int),
            "files": []
        })
        
        if progress_callback:
            dir_counts = []
            total_files = 0
            for path in paths:
                count = FileScanner.count_files(path, cancel_event)
                dir_counts.append((path, count))
                total_files += count

                if cancel_event and cancel_event.is_set():
                    return dict(combined_stats)
        else:
            dir_counts = [(path, 0) for path in paths]
            total_files = 0

        processed_offset = 0

        for path, dir_total in dir_counts:
            if cancel_event and cancel_event.is_set():
                break

            def wrapped_callback(processed: int, _total: int, current: str):
                if progress_callback:
                    progress_callback(processed_offset + processed, total_files, current)

            dir_stats = FileScanner.scan_directory(
                path,
                wrapped_callback if progress_callback else None,
                cancel_event,
            )
            
            # 統合
            for media_type, data in dir_stats.items():
                combined_stats[media_type]["count"] += data["count"]
                combined_stats[media_type]["size"] += data["size"]
                combined_stats[media_type]["files"].extend(data["files"])
                
                for ext, count in data["extensions"].items():
                    combined_stats[media_type]["extensions"][ext] += count
            processed_offset += dir_total if dir_total else sum(data["count"] for data in dir_stats.values())

        return dict(combined_stats)
