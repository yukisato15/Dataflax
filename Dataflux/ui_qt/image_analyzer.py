#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based Image Analysis and Processing Tool
Enhanced image analyzer with detailed metadata analysis including EXIF data
Based on the audio/video analyzer UI structure
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
from collections import defaultdict
import shutil
import subprocess
import hashlib
import mimetypes
import threading
import concurrent.futures
import time

# Try to import PIL for advanced image processing
try:
    from PIL import Image, ExifTags
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Import the scanner from core module
sys.path.append(str(Path(__file__).parent.parent))

from .folder_tools import (
    FolderNameDeleteDialog,
    MATCH_EXACT,
    remove_folders_matching_query,
)

# Dot-file handling
def is_dot_file(path: Path) -> bool:
    """Return True when the file should be treated as dot/metadata file."""
    name = path.name
    return name.startswith(".") or name.startswith("._")

# Image processing utilities
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

def get_file_hash(path: Path) -> str:
    """Calculate MD5 hash of file for duplicate detection"""
    try:
        hash_md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return ""

def image_probe(path: Path, *, compute_hash: bool = False) -> Dict[str, Any]:
    """画像メタデータの抽出。
    compute_hash=True のときのみMD5ハッシュを計算（既定はオフで高速化）。
    """
    info = {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size": 0,
        "mtime": None,
        "width": None,
        "height": None,
        "megapixels": None,
        "aspect_ratio": None,
        "color_mode": None,
        "bit_depth": None,
        "compression": None,
        "dpi": None,
        "file_hash": None,
        # EXIF data
        "camera_make": None,
        "camera_model": None,
        "lens_model": None,
        "focal_length": None,
        "f_number": None,
        "exposure_time": None,
        "iso_speed": None,
        "flash": None,
        "date_taken": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "orientation": None,
        "white_balance": None,
        "exposure_mode": None,
        "scene_capture_type": None
        ,
        "analysis_error": None
    }
    
    try:
        stat = path.stat()
        info["size"] = stat.st_size
        info["mtime"] = stat.st_mtime
    except:
        pass
    
    # ハッシュ計算は重いので既定で無効（重複検出時のみ有効化）
    info["file_hash"] = get_file_hash(path) if compute_hash else ""
    
    if not PIL_AVAILABLE:
        return info
    
    try:
        with Image.open(path) as img:
            # Basic image info
            info["width"] = img.width
            info["height"] = img.height
            info["megapixels"] = round((img.width * img.height) / 1_000_000, 2)
            
            if img.height > 0:
                info["aspect_ratio"] = round(img.width / img.height, 3)
            
            info["color_mode"] = img.mode
            
            # Get format-specific info
            if hasattr(img, 'bits'):
                info["bit_depth"] = img.bits
            elif img.mode in ['1', 'L']:
                info["bit_depth"] = 8 if img.mode == 'L' else 1
            elif img.mode in ['RGB', 'YCbCr']:
                info["bit_depth"] = 24
            elif img.mode == 'RGBA':
                info["bit_depth"] = 32
                
            # DPI information
            if hasattr(img, 'info') and 'dpi' in img.info:
                info["dpi"] = img.info['dpi'][0] if isinstance(img.info['dpi'], tuple) else img.info['dpi']
            
            # Compression info for JPEG
            if img.format == 'JPEG' and hasattr(img, 'info'):
                info["compression"] = "JPEG"
                if 'quality' in img.info:
                    info["jpeg_quality"] = img.info['quality']
            elif img.format == 'PNG':
                info["compression"] = "PNG"
            elif img.format in ['TIFF', 'TIF']:
                info["compression"] = "TIFF"
                
            # EXIFはJPEG/TIFF系のみ対象にして高速化
            ext_lower = path.suffix.lower()
            if ext_lower in {'.jpg', '.jpeg', '.tif', '.tiff'} and hasattr(img, '_getexif') and img._getexif() is not None:
                exif = img._getexif()
                
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    try:
                        if tag == "Make":
                            info["camera_make"] = str(value).strip()
                        elif tag == "Model":
                            info["camera_model"] = str(value).strip()
                        elif tag == "LensModel":
                            info["lens_model"] = str(value).strip()
                        elif tag == "FocalLength":
                            if isinstance(value, tuple) and len(value) == 2:
                                info["focal_length"] = round(value[0] / value[1], 1)
                            else:
                                info["focal_length"] = float(value)
                        elif tag == "FNumber":
                            if isinstance(value, tuple) and len(value) == 2:
                                info["f_number"] = round(value[0] / value[1], 1)
                            else:
                                info["f_number"] = float(value)
                        elif tag == "ExposureTime":
                            if isinstance(value, tuple) and len(value) == 2:
                                exposure = value[0] / value[1]
                                if exposure >= 1:
                                    info["exposure_time"] = f"{exposure:.1f}s"
                                else:
                                    info["exposure_time"] = f"1/{int(1/exposure)}"
                            else:
                                info["exposure_time"] = str(value)
                        elif tag == "ISOSpeedRatings" or tag == "PhotographicSensitivity":
                            info["iso_speed"] = int(value) if isinstance(value, (int, float)) else value
                        elif tag == "Flash":
                            info["flash"] = int(value) if isinstance(value, (int, float)) else value
                        elif tag == "DateTime" or tag == "DateTimeOriginal":
                            if isinstance(value, str):
                                try:
                                    info["date_taken"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S").isoformat()
                                except:
                                    info["date_taken"] = value
                        elif tag == "Orientation":
                            info["orientation"] = int(value)
                        elif tag == "WhiteBalance":
                            info["white_balance"] = int(value)
                        elif tag == "ExposureMode":
                            info["exposure_mode"] = int(value)
                        elif tag == "SceneCaptureType":
                            info["scene_capture_type"] = int(value)
                        elif tag == "GPSInfo" and isinstance(value, dict):
                            # Extract GPS coordinates
                            if 2 in value and 4 in value:  # Latitude and Longitude
                                try:
                                    lat = value[2]
                                    lon = value[4]
                                    if isinstance(lat, tuple) and len(lat) == 3:
                                        lat_deg = lat[0][0] / lat[0][1] if lat[0][1] != 0 else 0
                                        lat_min = lat[1][0] / lat[1][1] if lat[1][1] != 0 else 0
                                        lat_sec = lat[2][0] / lat[2][1] if lat[2][1] != 0 else 0
                                        info["gps_latitude"] = lat_deg + lat_min/60 + lat_sec/3600
                                        
                                    if isinstance(lon, tuple) and len(lon) == 3:
                                        lon_deg = lon[0][0] / lon[0][1] if lon[0][1] != 0 else 0
                                        lon_min = lon[1][0] / lon[1][1] if lon[1][1] != 0 else 0
                                        lon_sec = lon[2][0] / lon[2][1] if lon[2][1] != 0 else 0
                                        info["gps_longitude"] = lon_deg + lon_min/60 + lon_sec/3600
                                        
                                    # Apply hemisphere
                                    if 1 in value and value[1] == 'S':
                                        info["gps_latitude"] = -info["gps_latitude"]
                                    if 3 in value and value[3] == 'W':
                                        info["gps_longitude"] = -info["gps_longitude"]
                                except:
                                    pass
                    except:
                        continue
                        
    except Exception as e:
        info["analysis_error"] = str(e)
    
    return info

def categorize_image(info: Dict[str, Any]) -> Dict[str, str]:
    """Categorize image file by various criteria"""
    categories = {}
    
    # Format category
    ext = info.get("ext", "").lower()
    if ext in [".jpg", ".jpeg"]:
        categories["format"] = "fmt_jpeg"
    elif ext == ".png":
        categories["format"] = "fmt_png"
    elif ext in [".tif", ".tiff"]:
        categories["format"] = "fmt_tiff"
    elif ext == ".gif":
        categories["format"] = "fmt_gif"
    elif ext == ".bmp":
        categories["format"] = "fmt_bmp"
    elif ext == ".webp":
        categories["format"] = "fmt_webp"
    elif ext in [".raw", ".cr2", ".nef", ".arw", ".dng"]:
        categories["format"] = "fmt_raw"
    elif ext == ".svg":
        categories["format"] = "fmt_svg"
    elif ext in [".heic", ".heif"]:
        categories["format"] = "fmt_heic"
    else:
        categories["format"] = "fmt_other"
    
    # Resolution category
    width = info.get("width")
    height = info.get("height")
    if width and height:
        megapixels = (width * height) / 1_000_000
        
        if megapixels < 1:
            categories["resolution"] = "res_low"
        elif megapixels < 5:
            categories["resolution"] = "res_medium"
        elif megapixels < 12:
            categories["resolution"] = "res_high"
        elif megapixels < 24:
            categories["resolution"] = "res_very_high"
        elif megapixels < 50:
            categories["resolution"] = "res_ultra_high"
        else:
            categories["resolution"] = "res_extreme"
    else:
        categories["resolution"] = "res_unknown"
    
    # Aspect ratio category
    aspect_ratio = info.get("aspect_ratio")
    if aspect_ratio:
        if 0.9 <= aspect_ratio <= 1.1:
            categories["aspect"] = "aspect_square"
        elif 1.2 <= aspect_ratio <= 1.4:
            categories["aspect"] = "aspect_4_3"
        elif 1.7 <= aspect_ratio <= 1.8:
            categories["aspect"] = "aspect_16_9"
        elif 2.1 <= aspect_ratio <= 2.5:
            categories["aspect"] = "aspect_panoramic"
        elif aspect_ratio < 0.9:
            categories["aspect"] = "aspect_portrait"
        elif aspect_ratio > 2.5:
            categories["aspect"] = "aspect_wide"
        else:
            categories["aspect"] = "aspect_other"
    else:
        categories["aspect"] = "aspect_unknown"
    
    # Color mode category
    color_mode = info.get("color_mode")
    if color_mode == "RGB":
        categories["color"] = "color_rgb"
    elif color_mode == "RGBA":
        categories["color"] = "color_rgba"
    elif color_mode in ["L", "P"]:
        categories["color"] = "color_grayscale"
    elif color_mode == "CMYK":
        categories["color"] = "color_cmyk"
    elif color_mode == "1":
        categories["color"] = "color_bw"
    else:
        categories["color"] = "color_other"
    
    # Camera category (if EXIF available)
    camera_make = info.get("camera_make")
    if camera_make:
        make_lower = camera_make.lower()
        if "canon" in make_lower:
            categories["camera"] = "camera_canon"
        elif "nikon" in make_lower:
            categories["camera"] = "camera_nikon"
        elif "sony" in make_lower:
            categories["camera"] = "camera_sony"
        elif "apple" in make_lower or "iphone" in make_lower:
            categories["camera"] = "camera_apple"
        elif "samsung" in make_lower:
            categories["camera"] = "camera_samsung"
        elif "fuji" in make_lower:
            categories["camera"] = "camera_fuji"
        elif "olympus" in make_lower:
            categories["camera"] = "camera_olympus"
        elif "panasonic" in make_lower:
            categories["camera"] = "camera_panasonic"
        else:
            categories["camera"] = "camera_other"
    else:
        categories["camera"] = "camera_unknown"
    
    # File size category
    size = info.get("size", 0)
    if size:
        size_mb = size / (1024 * 1024)
        if size_mb < 1:
            categories["size"] = "size_small"
        elif size_mb < 5:
            categories["size"] = "size_medium"
        elif size_mb < 20:
            categories["size"] = "size_large"
        elif size_mb < 100:
            categories["size"] = "size_very_large"
        else:
            categories["size"] = "size_huge"
    else:
        categories["size"] = "size_unknown"
    
    # Date category
    date_taken = info.get("date_taken")
    if date_taken:
        try:
            if isinstance(date_taken, str):
                if 'T' in date_taken:
                    date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
                else:
                    date = datetime.fromisoformat(date_taken)
            else:
                date = date_taken
            categories["date"] = f"{date.year}-{date.month:02d}"
        except:
            # Fallback to file modification time
            mtime = info.get("mtime")
            if mtime:
                date = datetime.fromtimestamp(mtime)
                categories["date"] = f"{date.year}-{date.month:02d}"
            else:
                categories["date"] = "date_unknown"
    else:
        # Use file modification time
        mtime = info.get("mtime")
        if mtime:
            date = datetime.fromtimestamp(mtime)
            categories["date"] = f"{date.year}-{date.month:02d}"
        else:
            categories["date"] = "date_unknown"
    
    return categories


class ImageAnalysisThread(QThread):
    """Image analysis thread for detailed image file processing"""
    
    progress_updated = Signal(str, int, int)  # message, current, total
    analysis_completed = Signal(dict)         # analysis results
    error_occurred = Signal(str)              # error message
    
    canceled = Signal()

    def __init__(self, paths: List[Path], *, compute_hash: bool = False, ignore_dot_files: bool = True):
        super().__init__()
        self.paths = paths if isinstance(paths, list) else [paths]
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.raw', '.cr2', '.nef', '.arw', '.dng', '.heic', '.heif', '.ico'}
        # 制御用フラグ
        self._cancel = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # 通常は進行
        self.compute_hash = compute_hash
        self.ignore_dot_files = ignore_dot_files

    def pause(self):
        """一時停止"""
        self._pause_event.clear()

    def resume(self):
        """再開"""
        self._pause_event.set()

    def cancel(self):
        """中止"""
        self._cancel = True
        # 停止状態でも即座に抜けられるように解除
        self._pause_event.set()
    
    def run(self):
        """Analyze image files in the given paths"""
        try:
            results = {}
            total_files = 0
            processed = 0
            
            # Count total image files
            image_files = []
            for root_path in self.paths:
                if root_path.is_dir():
                    for file_path in root_path.rglob("*"):
                        if (
                            file_path.is_file()
                            and file_path.suffix.lower() in self.image_extensions
                            and not (self.ignore_dot_files and is_dot_file(file_path))
                        ):
                            image_files.append(file_path)
            
            total_files = len(image_files)
            # 初期進捗通知
            self.progress_updated.emit("準備中", 0, total_files)
            if total_files == 0:
                self.analysis_completed.emit({})
                return
            
            # 並列解析: ThreadPoolExecutor を使用
            def _analyze_one(p: Path):
                info = image_probe(p, compute_hash=self.compute_hash)
                cats = categorize_image(info)
                return info, cats, p.name

            # ワーカー数（I/O バウンド寄りなので CPU の数×4 を上限32まで）
            try:
                import os as _os
                max_workers = min(32, max(4, (_os.cpu_count() or 4) * 4))
            except Exception:
                max_workers = 8

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_analyze_one, fp) for fp in image_files]

                last_emit = 0.0
                for future in concurrent.futures.as_completed(futures):
                    # 中止要求
                    if self._cancel:
                        self.canceled.emit()
                        self.analysis_completed.emit(results)
                        return
                    # 一時停止
                    self._pause_event.wait()

                    try:
                        image_info, categories, fname = future.result()
                    except Exception:
                        processed += 1
                        # 進捗更新のみ
                        now = time.time()
                        if now - last_emit > 0.05 or processed == total_files:
                            self.progress_updated.emit(f"解析中: (エラー)", processed, total_files)
                            last_emit = now
                        continue

                    # 集計（スレッド外で安全に実行）
                    for category_type, category_value in categories.items():
                        if category_type not in results:
                            results[category_type] = {}

                        if category_value not in results[category_type]:
                            results[category_type][category_value] = {
                                "count": 0,
                                "total_size": 0,
                                "total_megapixels": 0,
                                "files": []
                            }

                        category_data = results[category_type][category_value]
                        category_data["count"] += 1
                        category_data["total_size"] += image_info.get("size", 0)
                        megapixels = image_info.get("megapixels", 0)
                        if megapixels:
                            category_data["total_megapixels"] += megapixels
                        category_data["files"].append(image_info)

                    processed += 1
                    now = time.time()
                    if now - last_emit > 0.05 or processed == total_files:
                        self.progress_updated.emit(f"解析中: {fname}", processed, total_files)
                        last_emit = now

            self.analysis_completed.emit(results)
        except Exception as e:
            # 解析全体の例外はシグナルで通知
            self.error_occurred.emit(str(e))


class FileProcessingThread(QThread):
    """ファイルのコピー/整理を行うスレッド（UIブロック回避）"""
    progress_updated = Signal(str, int, int)
    completed = Signal(int, int)
    error_occurred = Signal(str)
    canceled = Signal()

    def __init__(self, files: List[Dict], *, mode: str, output_dir: Path, allowed_exts: Optional[set] = None,
                 current_category: Optional[str] = None, dry_run: bool = True):
        super().__init__()
        self.files = files
        self.mode = mode
        self.output_dir = output_dir
        self.allowed_exts = allowed_exts or set()
        self.current_category = current_category
        self.dry_run = dry_run
        self._cancel = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def cancel(self):
        self._cancel = True
        self._pause_event.set()

    def run(self):
        try:
            total = len(self.files)
            success = 0
            errors = 0
            processed = 0
            last_emit = 0.0

            for fi in self.files:
                if self._cancel:
                    self.canceled.emit()
                    self.completed.emit(success, errors)
                    return
                self._pause_event.wait()

                try:
                    src = Path(fi['path'])
                    if not src.exists():
                        errors += 1
                    else:
                        # フラット化
                        if self.mode == "フラット化":
                            if self.allowed_exts and src.suffix.lower() not in self.allowed_exts:
                                # スキップ
                                pass
                            else:
                                dst = unique_name(self.output_dir, src.name)
                                if not self.dry_run:
                                    dst.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(src, dst)
                                success += 1
                        # 画像整理
                        else:
                            subdir_name = "unknown"
                            try:
                                cats = categorize_image(fi)
                                if self.current_category:
                                    subdir_name = cats.get(self.current_category, "unknown")
                            except Exception:
                                pass
                            dst = unique_name(self.output_dir / subdir_name, src.name)
                            if not self.dry_run:
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src, dst)
                            success += 1
                except Exception:
                    errors += 1

                processed += 1
                now = time.time()
                if now - last_emit > 0.05 or processed == total:
                    verb = "コピー" if self.mode == "フラット化" else "整理"
                    name = src.name if 'src' in locals() else "(不明)"
                    self.progress_updated.emit(f"{verb}: {name}", processed, total)
                    last_emit = now

            self.completed.emit(success, errors)
        except Exception as e:
            self.error_occurred.emit(str(e))
            
        except Exception as e:
            self.error_occurred.emit(str(e))


class ImageAnalyzerWindow(QMainWindow):
    """Enhanced image analyzer with comprehensive analysis and processing capabilities"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像解析・整理ツール")
        self.setGeometry(200, 200, 1400, 900)
        self.setMinimumSize(1200, 800)
        
        # Data management
        self.selected_paths: List[Path] = []
        self.analysis_results: Dict[str, Any] = {}
        self.analysis_thread: Optional[ImageAnalysisThread] = None
        self.folder_placeholder_text = "ここに画像フォルダをドラッグ&ドロップ"

        # Check PIL availability
        if not PIL_AVAILABLE:
            QMessageBox.warning(None, "PIL未検出", 
                "Pillow (PIL)ライブラリが見つかりません。画像の詳細解析機能が制限されます。\n"
                "pip install Pillowでインストールしてください。")
        
        self.init_ui()
        self.apply_pro_theme()
        self.setAcceptDrops(True)
    
    def init_ui(self):
        """Initialize the UI layout similar to audio/video analyzer"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Main splitter (vertical)
        vsplitter = QSplitter(Qt.Vertical)
        
        # Top: Image folder tree
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
        self.status_bar.showMessage("画像ファイルフォルダを追加して解析を開始してください")
    
    def create_folder_tree_widget(self):
        """Create folder tree widget for image folders"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("画像フォルダ"))
        
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
        """Create toolbar with image-specific options"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Folder selection
        add_btn = QPushButton("フォルダ選択")
        add_btn.clicked.connect(self.select_image_folders)
        layout.addWidget(add_btn)
        
        # Remove selected
        remove_btn = QPushButton("選択削除")
        remove_btn.clicked.connect(self.remove_selected_folders)
        layout.addWidget(remove_btn)

        name_remove_btn = QPushButton("名前で削除")
        name_remove_btn.clicked.connect(self.remove_folders_by_name)
        layout.addWidget(name_remove_btn)

        # Analysis
        self.analyze_btn = QPushButton("画像解析実行")
        self.analyze_btn.setStyleSheet("background-color: #2d5a2d; color: white; font-weight: bold;")
        self.analyze_btn.clicked.connect(self.run_image_analysis)
        layout.addWidget(self.analyze_btn)

        # Pickups
        duplicate_pick_btn = QPushButton("重複候補抽出")
        duplicate_pick_btn.clicked.connect(self.pickup_duplicates)
        layout.addWidget(duplicate_pick_btn)

        corruption_pick_btn = QPushButton("破損候補抽出")
        corruption_pick_btn.clicked.connect(self.pickup_corruption_candidates)
        layout.addWidget(corruption_pick_btn)

        corruption_quarantine_btn = QPushButton("破損候補退避")
        corruption_quarantine_btn.clicked.connect(self.quarantine_corruption_candidates)
        layout.addWidget(corruption_quarantine_btn)

        duplicate_cleanup_btn = QPushButton("重複整理(1件残す)")
        duplicate_cleanup_btn.clicked.connect(self.cleanup_duplicates_keep_one)
        layout.addWidget(duplicate_cleanup_btn)

        # Export analysis CSV
        export_csv_btn = QPushButton("解析CSV出力")
        export_csv_btn.clicked.connect(self.export_analysis_csv)
        layout.addWidget(export_csv_btn)

        # dot_clean
        self.dot_clean_btn = QPushButton("dot_clean実行")
        self.dot_clean_btn.clicked.connect(self.run_dot_clean)
        layout.addWidget(self.dot_clean_btn)

        # Ignore dot files in counting/analysis
        self.ignore_dot_check = QCheckBox("dotをカウントしない")
        self.ignore_dot_check.setChecked(True)
        layout.addWidget(self.ignore_dot_check)

        # Pause/Resume
        self.pause_btn = QPushButton("一時停止")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause_resume)
        layout.addWidget(self.pause_btn)

        # Cancel/Stop
        self.stop_btn = QPushButton("中止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("color: #a94442;")
        self.stop_btn.clicked.connect(self.cancel_analysis)
        layout.addWidget(self.stop_btn)
        
        layout.addWidget(QLabel("|"))
        
        # Processing mode
        layout.addWidget(QLabel("処理モード:"))
        self.processing_mode = QComboBox()
        self.processing_mode.addItems(["画像整理", "フラット化"])
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
        header = QLabel("画像解析結果")
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
        """Create tabs for different image analysis categories"""
        categories = [
            ("フォーマット", "format"),
            ("解像度", "resolution"), 
            ("アスペクト比", "aspect"),
            ("カラーモード", "color"),
            ("カメラ", "camera"),
            ("ファイルサイズ", "size"),
            ("日付", "date")
        ]
        
        self.category_trees = {}
        
        for tab_name, category_key in categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            tree = QTreeWidget()
            tree.setHeaderLabels(["カテゴリ", "ファイル数", "合計サイズ", "総メガピクセル"])
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
            ("jpg", "JPEG", True),
            ("png", "PNG", True),
            ("tiff", "TIFF", False),
            ("gif", "GIF", False),
            ("webp", "WebP", False),
            ("raw", "RAW形式", False)
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
            "カラーモード別",
            "カメラ別",
            "ファイルサイズ別",
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
            "カラーモード別",
            "カメラ別",
            "ファイルサイズ別",
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
        self.filter_type.addItems(["解像度", "メガピクセル", "サイズ", "アスペクト比"])
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
        
        self.duplicate_check = QCheckBox("重複画像を検出・削除")
        additional_layout.addWidget(self.duplicate_check)
        
        self.remove_empty_check = QCheckBox("空フォルダを削除")
        self.remove_empty_check.setChecked(True)
        additional_layout.addWidget(self.remove_empty_check)
        
        self.use_trash_check = QCheckBox("不要ファイルをゴミ箱へ")
        additional_layout.addWidget(self.use_trash_check)
        
        self.preserve_exif_check = QCheckBox("EXIF情報を保持")
        self.preserve_exif_check.setChecked(True)
        additional_layout.addWidget(self.preserve_exif_check)
        
        options_layout.addWidget(additional_group)
        
        layout.addWidget(options_group)

        # 出力先設定
        output_group = QGroupBox("出力先設定")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("ベースフォルダ:"), 0, 0)
        self.output_dir_edit = QLineEdit()
        # 直接入力も許可（/Volumes/A012 などを手入力可）
        self.output_dir_edit.setReadOnly(False)
        self.output_dir_edit.setPlaceholderText("未設定（実行時に選択／手入力可）")
        output_layout.addWidget(self.output_dir_edit, 0, 1)

        self.output_dir_btn = QPushButton("選択…")
        self.output_dir_btn.clicked.connect(self.select_output_directory)
        output_layout.addWidget(self.output_dir_btn, 0, 2)

        self.create_subdir_check = QCheckBox("サブフォルダを作成")
        self.create_subdir_check.setChecked(True)
        output_layout.addWidget(self.create_subdir_check, 1, 0)

        self.subdir_name_edit = QLineEdit()
        self.subdir_name_edit.setPlaceholderText("例: export_{date}")
        self.subdir_name_edit.setText("export_{date}")
        output_layout.addWidget(self.subdir_name_edit, 1, 1, 1, 2)

        layout.addWidget(output_group)
        
        # Execute buttons
        button_layout = QHBoxLayout()
        
        execute_btn = QPushButton("実行")
        execute_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px;")
        execute_btn.clicked.connect(self.execute_processing)
        button_layout.addWidget(execute_btn)
        
        layout.addLayout(button_layout)
        # ビルドスタンプ表示（簡易デバッグ用）
        stamp = QLabel("ビルド: dev-" + datetime.now().strftime("%Y%m%d"))
        stamp.setStyleSheet("color:#A9B5BC; font-size:11px;")
        layout.addWidget(stamp)
        layout.addStretch()
        
        return widget

    def select_output_directory(self):
        default_dir = str(Path('/Volumes')) if sys.platform == 'darwin' and Path('/Volumes').exists() else str(Path.home())
        base = QFileDialog.getExistingDirectory(
            self, "出力先フォルダを選択",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if base:
            self.output_dir_edit.setText(base)

    def _resolve_output_dir(self) -> Optional[Path]:
        """UI設定から最終出力先を決定。未設定なら選択ダイアログを出す。"""
        base_text = self.output_dir_edit.text().strip()
        if not base_text:
            default_dir = str(Path('/Volumes')) if sys.platform == 'darwin' and Path('/Volumes').exists() else str(Path.home())
            base = QFileDialog.getExistingDirectory(
                self, "出力先フォルダを選択",
                default_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if not base:
                return None
            self.output_dir_edit.setText(base)
            base_path = Path(base)
        else:
            base_path = Path(base_text)

        target = base_path
        if self.create_subdir_check.isChecked():
            name = (self.subdir_name_edit.text() or "").strip()
            if name:
                name = name.replace("{date}", datetime.now().strftime("%Y%m%d_%H%M%S"))
                target = base_path / name
        return target
    
    def apply_pro_theme(self):
        """Apply Pro (dark) theme"""
        pro_theme_file = Path("themes/pro.qss")
        if pro_theme_file.exists():
            with open(pro_theme_file, "r", encoding="utf-8") as f:
                base_style = f.read()
        else:
            base_style = self.get_fallback_theme()
            
        # Image analyzer specific styles
        image_style = """
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
        
        self.setStyleSheet(base_style + image_style)
    
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
    
    def select_image_folders(self):
        """Select image folders for analysis"""
        folder = QFileDialog.getExistingDirectory(
            self, "画像フォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.add_image_folder(Path(folder))
    
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
        """Remove folders whose names match criteria provided by the user."""
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

    def run_image_analysis(self):
        """Run detailed image analysis"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "警告", "解析はすでに実行中です")
            return
        if not self.selected_paths:
            QMessageBox.warning(self, "警告", "解析する画像フォルダがありません")
            return
        
        # Clear previous results
        for tree in self.category_trees.values():
            tree.clear()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start analysis thread
        self.analysis_thread = ImageAnalysisThread(
            self.selected_paths,
            compute_hash=getattr(self, 'duplicate_check', None).isChecked() if hasattr(self, 'duplicate_check') else False,
            ignore_dot_files=self.ignore_dot_check.isChecked() if hasattr(self, 'ignore_dot_check') else True,
        )
        self.analysis_thread.progress_updated.connect(self.update_analysis_progress)
        self.analysis_thread.analysis_completed.connect(self.display_analysis_results)
        self.analysis_thread.error_occurred.connect(self.handle_analysis_error)
        self.analysis_thread.canceled.connect(self.handle_analysis_canceled)
        self.analysis_thread.finished.connect(self.handle_analysis_finished)
        self.analysis_thread.start()

        # UI 状態
        self.analyze_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("一時停止")
        self.stop_btn.setEnabled(True)

        # Busy表示（開始時は総数不明なので不確定）
        self._analysis_start = time.time()
        self._analysis_total = 0
        self._start_busy(title="画像解析中", label="ファイルを解析しています…", total=0)
    
    def update_analysis_progress(self, message: str, current: int, total: int):
        """Update analysis progress"""
        if total and getattr(self, '_analysis_total', 0) == 0:
            self._analysis_total = total
        label = self._compose_progress_label(prefix="解析", message=message, start_attr='_analysis_start', current=current, total=total)
        self.status_bar.showMessage(label)
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        # Busyダイアログも更新
        self._update_busy(label, current, total)

    def display_analysis_results(self, results: Dict[str, Any]):
        """Display detailed analysis results in category tabs"""
        self.analysis_results = results
        
        if not results:
            QMessageBox.information(self, "結果", "画像ファイルが見つかりませんでした")
            return
        
        # Category display names
        category_names = {
            "format": {"fmt_jpeg": "JPEG", "fmt_png": "PNG", "fmt_tiff": "TIFF", "fmt_gif": "GIF", "fmt_bmp": "BMP", "fmt_webp": "WebP", "fmt_raw": "RAW形式", "fmt_svg": "SVG", "fmt_heic": "HEIC", "fmt_other": "その他"},
            "resolution": {"res_low": "低解像度 (<1MP)", "res_medium": "中解像度 (1-5MP)", "res_high": "高解像度 (5-12MP)", "res_very_high": "超高解像度 (12-24MP)", "res_ultra_high": "極高解像度 (24-50MP)", "res_extreme": "極限解像度 (50MP+)", "res_unknown": "不明"},
            "aspect": {"aspect_square": "正方形", "aspect_4_3": "4:3", "aspect_16_9": "16:9", "aspect_panoramic": "パノラマ", "aspect_portrait": "縦型", "aspect_wide": "ワイド", "aspect_other": "その他", "aspect_unknown": "不明"},
            "color": {"color_rgb": "RGB", "color_rgba": "RGBA", "color_grayscale": "グレースケール", "color_cmyk": "CMYK", "color_bw": "白黒", "color_other": "その他"},
            "camera": {"camera_canon": "Canon", "camera_nikon": "Nikon", "camera_sony": "Sony", "camera_apple": "Apple", "camera_samsung": "Samsung", "camera_fuji": "Fujifilm", "camera_olympus": "Olympus", "camera_panasonic": "Panasonic", "camera_other": "その他", "camera_unknown": "不明"},
            "size": {"size_small": "小さい (<1MB)", "size_medium": "中程度 (1-5MB)", "size_large": "大きい (5-20MB)", "size_very_large": "とても大きい (20-100MB)", "size_huge": "巨大 (100MB+)", "size_unknown": "不明"},
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
                
                # Total megapixels
                total_megapixels = data.get('total_megapixels', 0)
                if total_megapixels > 0:
                    if total_megapixels >= 1000:
                        item.setText(3, f"{total_megapixels/1000:.1f}K MP")
                    else:
                        item.setText(3, f"{total_megapixels:.1f} MP")
                else:
                    item.setText(3, "不明")
                
                # Store data for processing
                item.setData(0, Qt.UserRole, subcategory)
        
        # Expand all trees
        for tree in self.category_trees.values():
            tree.expandAll()
            tree.resizeColumnToContents(0)
        
        self.status_bar.showMessage(f"画像解析完了: {sum(len(cat_data) for cat_data in results.values())} カテゴリ")

    def handle_analysis_canceled(self):
        """解析中止時のハンドラ"""
        self.status_bar.showMessage("画像解析を中止しました")
        self._stop_busy()

    def handle_analysis_finished(self):
        """解析スレッド終了時の後片付け"""
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("一時停止")
        self.stop_btn.setEnabled(False)
        self._stop_busy()
    
    def handle_analysis_error(self, error_message: str):
        """Handle analysis errors"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "解析エラー", f"画像解析中にエラーが発生しました:\n\n{error_message}")
        self.status_bar.showMessage("画像解析エラー")
    
    def execute_processing(self):
        """Execute image processing based on settings"""
        mode = self.processing_mode.currentText()

        # フラット化は解析なしで実行可能にする
        if mode == "フラット化" and not self.analysis_results:
            if not self.selected_paths:
                QMessageBox.warning(self, "警告", "処理する画像フォルダを追加してください")
                return
            # 出力先
            output_dir = self._resolve_output_dir()
            if not output_dir:
                return

            # 選択フォーマットで対象ファイルを収集
            selected_files = self._collect_files_for_flatten(self.selected_paths)
            if not selected_files:
                QMessageBox.information(self, "情報", "対象となる画像ファイルが見つかりませんでした")
                return

            self._start_processing_thread(selected_files, Path(output_dir), mode)
            return

        # それ以外のモードは従来通り：解析結果に基づいて選択
        if not self.analysis_results:
            QMessageBox.warning(self, "警告", "先に画像解析を実行してください")
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
        output_dir = self._resolve_output_dir()
        if not output_dir:
            return

        # Execute processing
        self._start_processing_thread(selected_files, Path(output_dir), mode)

    def _start_processing_thread(self, files: List[Dict], output_dir: Path, mode: str):
        """ファイル処理をバックグラウンドで実行"""
        # 許可拡張子セット
        allowed = set()
        if mode == "フラット化":
            if self.format_checks.get('jpg') and self.format_checks['jpg'].isChecked():
                allowed.update({'.jpg', '.jpeg'})
            if self.format_checks.get('png') and self.format_checks['png'].isChecked():
                allowed.update({'.png'})
            if self.format_checks.get('tiff') and self.format_checks['tiff'].isChecked():
                allowed.update({'.tif', '.tiff'})
            if self.format_checks.get('gif') and self.format_checks['gif'].isChecked():
                allowed.update({'.gif'})
            if self.format_checks.get('webp') and self.format_checks['webp'].isChecked():
                allowed.update({'.webp'})
            if self.format_checks.get('raw') and self.format_checks['raw'].isChecked():
                allowed.update({'.raw', '.cr2', '.nef', '.arw', '.dng'})

        current_tab = self.result_tabs.currentIndex()
        category_keys = list(self.category_trees.keys())
        current_category = category_keys[current_tab] if 0 <= current_tab < len(category_keys) else None

        self.processing_thread = FileProcessingThread(
            files,
            mode=mode,
            output_dir=output_dir,
            allowed_exts=allowed if allowed else None,
            current_category=current_category,
            dry_run=self.dry_run_check.isChecked(),
        )
        self.processing_thread.progress_updated.connect(self.update_processing_progress)
        self.processing_thread.completed.connect(self.handle_processing_completed)
        self.processing_thread.error_occurred.connect(self.handle_processing_error)
        self.processing_thread.canceled.connect(self.handle_processing_canceled)
        self.processing_thread.finished.connect(self.handle_processing_finished)

        # UI 状態
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)
        self.analyze_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("一時停止")
        self.stop_btn.setEnabled(True)

        self.processing_thread.start()
        # Busy表示（総数既知）
        self._processing_start = time.time()
        self._processing_total = len(files)
        self._start_busy(title="画像処理中", label=f"処理中: 0/{len(files)} (0.0%)", total=len(files))

    def update_processing_progress(self, message: str, current: int, total: int):
        label = self._compose_progress_label(prefix="処理", message=message, start_attr='_processing_start', current=current, total=total)
        self.status_bar.showMessage(label)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self._update_busy(label, current, total)

    def handle_processing_completed(self, success: int, errors: int):
        mode = self.processing_mode.currentText()
        mode_text = "シミュレーション" if self.dry_run_check.isChecked() else "実行"
        result_text = f"{mode} {mode_text}が完了しました\n\n成功: {success}ファイル\nエラー: {errors}ファイル"
        QMessageBox.information(self, "処理完了", result_text)
        self.status_bar.showMessage(f"処理完了: 成功{success}、エラー{errors}")
        self._stop_busy()

    def handle_processing_error(self, error_message: str):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "処理エラー", f"画像処理中にエラーが発生しました:\n\n{error_message}")
        self.status_bar.showMessage("画像処理エラー")
        self._stop_busy()

    def handle_processing_canceled(self):
        self.status_bar.showMessage("画像処理を中止しました")
        self._stop_busy()

    def handle_processing_finished(self):
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("一時停止")
        self.stop_btn.setEnabled(False)
        self._stop_busy()

    # Busyインジケーター（macの砂時計に相当：待機カーソル＋進行ダイアログ）
    def _start_busy(self, *, title: str, label: str, total: int = 0):
        try:
            self._busy_active = True
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if getattr(self, 'busy_dialog', None) is not None:
                self.busy_dialog.close()
                self.busy_dialog = None
            dlg = QProgressDialog(label, "中止", 0, max(0, total), self)
            dlg.setWindowTitle(title)
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumDuration(0)
            dlg.canceled.connect(self.cancel_analysis)
            if total == 0:
                # 不確定進捗
                dlg.setRange(0, 0)
            else:
                dlg.setValue(0)
            dlg.show()
            self.busy_dialog = dlg
        except Exception:
            pass

    def _update_busy(self, message: str, current: int, total: int):
        try:
            if getattr(self, 'busy_dialog', None) is None:
                return
            if total <= 0:
                # 不確定 → 確定に切替
                self.busy_dialog.setRange(0, 0)
            else:
                if self.busy_dialog.maximum() != total:
                    self.busy_dialog.setRange(0, total)
                self.busy_dialog.setValue(max(0, min(current, total)))
            self.busy_dialog.setLabelText(message)
        except Exception:
            pass

    def _stop_busy(self):
        try:
            if getattr(self, '_busy_active', False):
                QApplication.restoreOverrideCursor()
                self._busy_active = False
            if getattr(self, 'busy_dialog', None) is not None:
                self.busy_dialog.hide()
                self.busy_dialog.close()
                self.busy_dialog = None
        except Exception:
            pass

    def _compose_progress_label(self, *, prefix: str, message: str, start_attr: str, current: int, total: int) -> str:
        """パーセンテージとETA付きの進捗ラベルを作成"""
        parts = []
        if message:
            parts.append(f"{prefix}: {message}")
        else:
            parts.append(f"{prefix}実行中")
        if total > 0:
            pct = (current / total) * 100 if total else 0.0
            parts.append(f"— {current}/{total} ({pct:.1f}%)")
            try:
                start_time = getattr(self, start_attr, None)
                if start_time and current > 0:
                    elapsed = max(0.0001, time.time() - start_time)
                    rate = elapsed / current
                    remain = max(0.0, (total - current) * rate)
                    eta = self._format_duration(remain)
                    parts.append(f"残り約 {eta}")
            except Exception:
                pass
        return " ".join(parts)

    def _format_duration(self, seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}秒"
        minutes, sec = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}分{sec:02d}秒"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}時間{minutes:02d}分"

    def _collect_files_for_flatten(self, paths: List[Path]) -> List[Dict]:
        """解析なしでフラット化対象のファイルを収集"""
        image_exts = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp',
            '.raw', '.cr2', '.nef', '.arw', '.dng', '.heic', '.heif', '.ico', '.svg'
        }
        results: List[Dict] = []
        for root in paths:
            try:
                for p in root.rglob('*'):
                    if p.is_file():
                        if self.ignore_dot_check.isChecked() and is_dot_file(p):
                            continue
                        ext = p.suffix.lower()
                        if ext in image_exts and self._is_allowed_format(ext):
                            results.append({'path': str(p)})
            except Exception:
                continue
        return results

    def run_dot_clean(self):
        """Run dot_clean for selected folders (macOS only)."""
        if not self.selected_paths:
            QMessageBox.information(self, "情報", "dot_clean を実行するフォルダがありません")
            return

        if sys.platform != "darwin":
            QMessageBox.warning(self, "未対応", "dot_clean は macOS でのみ実行できます")
            return

        failures = []
        for folder in self.selected_paths:
            try:
                # -m: 可能な限りメタデータを保持しつつ ._ ファイルを整理
                result = subprocess.run(
                    ["dot_clean", "-m", str(folder)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    failures.append((folder, result.stderr.strip() or "unknown error"))
            except Exception as exc:
                failures.append((folder, str(exc)))

        if failures:
            msg = "\n".join([f"{p}: {e}" for p, e in failures[:5]])
            if len(failures) > 5:
                msg += f"\n... 他 {len(failures) - 5} 件"
            QMessageBox.warning(self, "dot_clean 一部失敗", msg)
            self.status_bar.showMessage(f"dot_clean 完了（一部失敗: {len(failures)}件）")
        else:
            QMessageBox.information(self, "完了", "dot_clean が完了しました")
            self.status_bar.showMessage("dot_clean 完了")

    def export_analysis_csv(self):
        """Export current analysis summary to CSV."""
        if not self.analysis_results:
            QMessageBox.information(self, "情報", "先に画像解析を実行してください")
            return

        default_name = f"image_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "解析結果をCSV出力",
            default_name,
            "CSV files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.writer(fp)
                writer.writerow([
                    "カテゴリ種別",
                    "カテゴリキー",
                    "カテゴリ名",
                    "ファイル数",
                    "合計サイズ(バイト)",
                    "合計サイズ(MB)",
                    "総メガピクセル",
                ])

                for category_type, subcategories in self.analysis_results.items():
                    for category_key, data in subcategories.items():
                        total_size = int(data.get("total_size", 0) or 0)
                        total_megapixels = float(data.get("total_megapixels", 0) or 0)
                        count = int(data.get("count", 0) or 0)
                        writer.writerow([
                            category_type,
                            category_key,
                            category_key,
                            count,
                            total_size,
                            round(total_size / (1024 * 1024), 3),
                            round(total_megapixels, 3),
                        ])
            QMessageBox.information(self, "出力完了", f"CSVを保存しました:\n{file_path}")
            self.status_bar.showMessage("解析結果CSVを出力しました")
        except Exception as exc:
            QMessageBox.critical(self, "出力エラー", f"CSV出力に失敗しました:\n{exc}")

    def _get_all_analyzed_files(self) -> List[Dict[str, Any]]:
        """Return de-duplicated analyzed files by path."""
        if not self.analysis_results:
            return []

        master: List[Dict[str, Any]] = []
        seen = set()

        # formatカテゴリは常に全件を含む想定
        format_data = self.analysis_results.get("format", {})
        if format_data:
            for cat in format_data.values():
                for info in cat.get("files", []):
                    p = info.get("path")
                    if p and p not in seen:
                        seen.add(p)
                        master.append(info)
            return master

        for categories in self.analysis_results.values():
            for cat in categories.values():
                for info in cat.get("files", []):
                    p = info.get("path")
                    if p and p not in seen:
                        seen.add(p)
                        master.append(info)
        return master

    def _show_pickup_dialog(self, *, title: str, headers: List[str], rows: List[List[Any]], default_filename: str):
        """Show pickup result in table with CSV export."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(980, 620)
        layout = QVBoxLayout(dialog)

        summary = QLabel(f"{len(rows):,} 件")
        summary.setStyleSheet("font-weight: bold;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)

        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QHBoxLayout()
        export_btn = QPushButton("CSV出力")
        close_btn = QPushButton("閉じる")
        buttons.addWidget(export_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        def _export_csv():
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "CSVとして保存",
                default_filename,
                "CSV files (*.csv)"
            )
            if not file_path:
                return
            try:
                with open(file_path, "w", newline="", encoding="utf-8-sig") as fp:
                    writer = csv.writer(fp)
                    writer.writerow(headers)
                    writer.writerows(rows)
                QMessageBox.information(self, "出力完了", f"CSVを保存しました:\n{file_path}")
            except Exception as exc:
                QMessageBox.critical(self, "出力エラー", f"CSV出力に失敗しました:\n{exc}")

        export_btn.clicked.connect(_export_csv)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def pickup_duplicates(self):
        """Pick up duplicate-name and duplicate-content image candidates."""
        files = self._get_all_analyzed_files()
        if not files:
            QMessageBox.information(self, "情報", "先に画像解析を実行してください")
            return

        by_name = defaultdict(list)
        by_hash = defaultdict(list)

        for info in files:
            path = info.get("path")
            name = info.get("name") or (Path(path).name if path else "")
            by_name[name].append(info)

            file_hash = info.get("file_hash") or ""
            # 解析時にハッシュ未取得の場合はここで補完
            if not file_hash and path:
                file_hash = get_file_hash(Path(path))
            if file_hash:
                by_hash[file_hash].append(info)

        rows: List[List[Any]] = []

        for name, group in by_name.items():
            if len(group) < 2:
                continue
            for info in group:
                rows.append([
                    "名前重複",
                    name,
                    len(group),
                    info.get("path", ""),
                    int(info.get("size", 0) or 0),
                ])

        for file_hash, group in by_hash.items():
            if len(group) < 2:
                continue
            for info in group:
                rows.append([
                    "内容重複",
                    file_hash,
                    len(group),
                    info.get("path", ""),
                    int(info.get("size", 0) or 0),
                ])

        if not rows:
            QMessageBox.information(self, "結果", "重複候補は見つかりませんでした")
            return

        self._show_pickup_dialog(
            title="重複候補一覧",
            headers=["種別", "重複キー", "同一件数", "ファイルパス", "サイズ(バイト)"],
            rows=rows,
            default_filename=f"image_duplicates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        self.status_bar.showMessage(f"重複候補を抽出: {len(rows):,}件")

    def pickup_corruption_candidates(self):
        """Pick up likely corrupted image candidates."""
        files = self._get_all_analyzed_files()
        if not files:
            QMessageBox.information(self, "情報", "先に画像解析を実行してください")
            return

        raster_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".tif", ".tiff", ".webp", ".heic", ".heif", ".ico"
        }

        rows: List[List[Any]] = []
        for info in files:
            reasons: List[str] = []
            path = info.get("path", "")
            ext = (info.get("ext") or "").lower()
            size = int(info.get("size", 0) or 0)

            if size == 0:
                reasons.append("0バイト")

            if info.get("analysis_error"):
                reasons.append(f"解析エラー: {info.get('analysis_error')}")

            if ext in raster_exts and size > 0:
                if not info.get("width") or not info.get("height"):
                    reasons.append("解像度取得不可")

            if not info.get("file_hash"):
                # ハッシュ失敗は読み取り不可の可能性があるので補足チェック
                h = get_file_hash(Path(path)) if path else ""
                if not h:
                    reasons.append("ハッシュ計算不可")

            if reasons:
                rows.append([
                    path,
                    ext,
                    size,
                    " / ".join(dict.fromkeys(reasons)),
                ])

        if not rows:
            QMessageBox.information(self, "結果", "破損候補は見つかりませんでした")
            return

        self._show_pickup_dialog(
            title="破損候補一覧",
            headers=["ファイルパス", "拡張子", "サイズ(バイト)", "判定理由"],
            rows=rows,
            default_filename=f"image_corruption_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        self.status_bar.showMessage(f"破損候補を抽出: {len(rows):,}件")

    def _collect_corruption_actions(self) -> List[Dict[str, Any]]:
        files = self._get_all_analyzed_files()
        if not files:
            return []

        raster_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".tif", ".tiff", ".webp", ".heic", ".heif", ".ico"
        }

        actions: List[Dict[str, Any]] = []
        for info in files:
            reasons: List[str] = []
            path = info.get("path", "")
            if not path:
                continue
            ext = (info.get("ext") or "").lower()
            size = int(info.get("size", 0) or 0)

            if size == 0:
                reasons.append("0バイト")
            if info.get("analysis_error"):
                reasons.append(f"解析エラー: {info.get('analysis_error')}")
            if ext in raster_exts and size > 0:
                if not info.get("width") or not info.get("height"):
                    reasons.append("解像度取得不可")
            if not info.get("file_hash"):
                h = get_file_hash(Path(path)) if path else ""
                if not h:
                    reasons.append("ハッシュ計算不可")

            if reasons:
                actions.append({
                    "path": path,
                    "ext": ext,
                    "size": size,
                    "reason": " / ".join(dict.fromkeys(reasons)),
                })
        return actions

    def quarantine_corruption_candidates(self):
        """Move corruption candidates to quarantine folder with dry-run support."""
        actions = self._collect_corruption_actions()
        if not actions:
            QMessageBox.information(self, "結果", "退避対象の破損候補は見つかりませんでした")
            return

        rows = [[a["path"], a["ext"], a["size"], a["reason"]] for a in actions]

        if self.dry_run_check.isChecked():
            self._show_pickup_dialog(
                title="破損候補退避プレビュー",
                headers=["ファイルパス", "拡張子", "サイズ(バイト)", "判定理由"],
                rows=rows,
                default_filename=f"image_corruption_quarantine_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            self.status_bar.showMessage(f"破損候補退避プレビュー: {len(actions):,}件")
            return

        base_dir = QFileDialog.getExistingDirectory(
            self,
            "破損候補の退避先フォルダを選択",
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not base_dir:
            return

        quarantine = Path(base_dir) / f"corruption_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        quarantine.mkdir(parents=True, exist_ok=True)

        success = 0
        errors = 0
        for idx, a in enumerate(actions, start=1):
            src = Path(a["path"])
            if not src.exists():
                errors += 1
                continue
            try:
                dst = unique_name(quarantine, src.name)
                shutil.move(str(src), str(dst))
                success += 1
            except Exception:
                errors += 1

            if idx % 20 == 0 or idx == len(actions):
                self.status_bar.showMessage(f"破損候補退避中... {idx}/{len(actions)}")
                QApplication.processEvents()

        QMessageBox.information(
            self,
            "破損候補退避完了",
            f"完了しました。\n\n移動成功: {success}\nエラー: {errors}\n退避先: {quarantine}"
        )
        self.status_bar.showMessage(f"破損候補退避完了: 成功{success} / エラー{errors}")

    def _score_keep_candidate(self, info: Dict[str, Any]) -> tuple:
        """Score file priority for 'keep one' selection in duplicate groups."""
        path = (info.get("path") or "").lower()
        preferred_keywords = ("納品", "deliver", "delivery", "master", "final")
        preferred = any(k in path for k in preferred_keywords)
        mtime = float(info.get("mtime", 0) or 0)
        size = int(info.get("size", 0) or 0)
        name = info.get("name") or Path(info.get("path", "")).name
        return (1 if preferred else 0, mtime, size, name)

    def _build_duplicate_groups(self, mode: str, files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Build duplicate groups by content hash or file name."""
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for info in files:
            path = info.get("path")
            if not path:
                continue

            if mode == "内容重複":
                key = info.get("file_hash") or ""
                if not key:
                    key = get_file_hash(Path(path))
            else:
                key = info.get("name") or Path(path).name

            if key:
                groups[key].append(info)

        return {k: v for k, v in groups.items() if len(v) >= 2}

    def cleanup_duplicates_keep_one(self):
        """Keep one file per duplicate group and move others to quarantine folder."""
        files = self._get_all_analyzed_files()
        if not files:
            QMessageBox.information(self, "情報", "先に画像解析を実行してください")
            return

        mode, ok = QInputDialog.getItem(
            self,
            "重複整理モード",
            "整理対象:",
            ["内容重複", "名前重複"],
            0,
            False,
        )
        if not ok:
            return

        groups = self._build_duplicate_groups(mode, files)
        if not groups:
            QMessageBox.information(self, "結果", f"{mode} の重複グループは見つかりませんでした")
            return

        actions: List[Dict[str, Any]] = []
        for dup_key, group in groups.items():
            sorted_group = sorted(group, key=self._score_keep_candidate, reverse=True)
            keep = sorted_group[0]
            for info in sorted_group[1:]:
                actions.append({
                    "mode": mode,
                    "dup_key": dup_key,
                    "keep_path": keep.get("path", ""),
                    "remove_path": info.get("path", ""),
                    "size": int(info.get("size", 0) or 0),
                })

        if not actions:
            QMessageBox.information(self, "結果", "整理対象はありませんでした")
            return

        preview_rows = [
            [a["mode"], a["dup_key"], a["keep_path"], a["remove_path"], a["size"]]
            for a in actions
        ]

        # Dry-run mode: preview only
        if self.dry_run_check.isChecked():
            self._show_pickup_dialog(
                title=f"重複整理プレビュー ({mode})",
                headers=["種別", "重複キー", "残すファイル", "移動対象", "サイズ(バイト)"],
                rows=preview_rows,
                default_filename=f"duplicate_cleanup_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            self.status_bar.showMessage(f"重複整理プレビュー: {len(actions):,}件")
            return

        reply = QMessageBox.question(
            self,
            "実行確認",
            f"{mode} の重複を整理します。\n"
            f"重複グループ: {len(groups):,}\n"
            f"移動対象: {len(actions):,}\n\n"
            "各グループで1件だけ残し、残りを退避フォルダへ移動します。実行しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        base_dir = QFileDialog.getExistingDirectory(
            self,
            "重複ファイル退避先フォルダを選択",
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not base_dir:
            return

        quarantine = Path(base_dir) / f"duplicates_removed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        quarantine.mkdir(parents=True, exist_ok=True)

        success = 0
        errors = 0
        for idx, a in enumerate(actions, start=1):
            src = Path(a["remove_path"])
            if not src.exists():
                errors += 1
                continue
            try:
                dst = unique_name(quarantine, src.name)
                shutil.move(str(src), str(dst))
                success += 1
            except Exception:
                errors += 1

            if idx % 20 == 0 or idx == len(actions):
                self.status_bar.showMessage(f"重複整理中... {idx}/{len(actions)}")
                QApplication.processEvents()

        QMessageBox.information(
            self,
            "重複整理完了",
            f"完了しました。\n\n移動成功: {success}\nエラー: {errors}\n退避先: {quarantine}"
        )
        self.status_bar.showMessage(f"重複整理完了: 成功{success} / エラー{errors}")

    def _is_allowed_format(self, ext: str) -> bool:
        """保持フォーマットチェックの状態に基づいて拡張子を許可するか判定"""
        allowed_sets = set()
        # UIのチェック状態を読む
        if self.format_checks.get('jpg') and self.format_checks['jpg'].isChecked():
            allowed_sets.update({'.jpg', '.jpeg'})
        if self.format_checks.get('png') and self.format_checks['png'].isChecked():
            allowed_sets.update({'.png'})
        if self.format_checks.get('tiff') and self.format_checks['tiff'].isChecked():
            allowed_sets.update({'.tif', '.tiff'})
        if self.format_checks.get('gif') and self.format_checks['gif'].isChecked():
            allowed_sets.update({'.gif'})
        if self.format_checks.get('webp') and self.format_checks['webp'].isChecked():
            allowed_sets.update({'.webp'})
        if self.format_checks.get('raw') and self.format_checks['raw'].isChecked():
            # 一般的なRAW拡張子
            allowed_sets.update({'.raw', '.cr2', '.nef', '.arw', '.dng'})

        # 何もチェックされていない場合は全許可（ユーザーの意図を阻害しない）
        if not allowed_sets:
            return True
        return ext in allowed_sets
    
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

    def toggle_pause_resume(self):
        """解析処理の一時停止/再開"""
        # 解析中 or 処理中のどちらかを制御
        target = None
        if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.isRunning():
            target = self.processing_thread
        elif self.analysis_thread and self.analysis_thread.isRunning():
            target = self.analysis_thread
        if not target:
            return
        if self.pause_btn.text() == "一時停止":
            target.pause()
            self.pause_btn.setText("再開")
            self.status_bar.showMessage("処理を一時停止しました")
        else:
            target.resume()
            self.pause_btn.setText("一時停止")
            self.status_bar.showMessage("処理を再開しました")

    def cancel_analysis(self):
        """解析/処理の中止"""
        canceled = False
        if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel()
            canceled = True
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.cancel()
            canceled = True
        if canceled:
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
    
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
                    self.add_image_folder(path)
            event.acceptProposedAction()
    
    def add_image_folder(self, folder_path: Path):
        """Add image folder to the analysis list"""
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
        
        # Add image files as children
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.raw', '.cr2', '.nef', '.arw', '.dng', '.heic', '.heif', '.ico'}
        image_count = 0
        
        try:
            for file_path in folder_path.rglob("*"):
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in image_extensions
                    and not (self.ignore_dot_check.isChecked() and is_dot_file(file_path))
                ):
                    image_count += 1
                    if image_count <= 100:  # Limit display for performance
                        child_item = QTreeWidgetItem(root_item)
                        child_item.setText(0, f"🖼️ {file_path.name}")
                        child_item.setData(0, Qt.UserRole, str(file_path))
                        child_item.setToolTip(0, str(file_path))
            
            if image_count > 100:
                more_item = QTreeWidgetItem(root_item)
                more_item.setText(0, f"... 他{image_count - 100}個の画像ファイル")
                more_item.setFlags(Qt.NoItemFlags)
                more_item.setForeground(0, QBrush(QColor("#888888")))
        
        except Exception:
            pass
        
        root_item.setExpanded(True)
        self.status_bar.showMessage(f"画像フォルダを追加しました: {folder_path.name} ({image_count}ファイル)")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = ImageAnalyzerWindow()
    window.show()
    sys.exit(app.exec())
