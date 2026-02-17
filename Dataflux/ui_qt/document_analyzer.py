#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based Document Analysis and Processing Tool
Enhanced document analyzer with detailed metadata analysis including PDF properties and Office document info
Based on the audio/video/image analyzer UI structure
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
import hashlib
import mimetypes
import zipfile
import xml.etree.ElementTree as ET
import re

# Document processing library availability check
LIBRARY_STATUS = {}

# PDF processing
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
    LIBRARY_STATUS['PyPDF2'] = {
        'available': True, 
        'version': getattr(PyPDF2, '__version__', 'unknown'),
        'description': 'PDF文書の詳細解析（ページ数、メタデータ、テキスト抽出）',
        'install_cmd': 'pip install PyPDF2'
    }
except ImportError as e:
    PYPDF2_AVAILABLE = False
    LIBRARY_STATUS['PyPDF2'] = {
        'available': False,
        'error': str(e),
        'description': 'PDF文書の詳細解析（ページ数、メタデータ、テキスト抽出）',
        'install_cmd': 'pip install PyPDF2'
    }

# Word document processing
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
    try:
        import docx
        version = getattr(docx, '__version__', 'unknown')
    except:
        version = 'unknown'
    LIBRARY_STATUS['python-docx'] = {
        'available': True,
        'version': version,
        'description': 'Word文書の詳細解析（メタデータ、段落数、テキスト抽出）',
        'install_cmd': 'pip install python-docx'
    }
except ImportError as e:
    DOCX_AVAILABLE = False
    LIBRARY_STATUS['python-docx'] = {
        'available': False,
        'error': str(e),
        'description': 'Word文書の詳細解析（メタデータ、段落数、テキスト抽出）',
        'install_cmd': 'pip install python-docx'
    }

# Character encoding detection
try:
    import chardet
    CHARDET_AVAILABLE = True
    LIBRARY_STATUS['chardet'] = {
        'available': True,
        'version': getattr(chardet, '__version__', 'unknown'),
        'description': 'テキストファイルの文字エンコーディング自動検出',
        'install_cmd': 'pip install chardet'
    }
except ImportError as e:
    CHARDET_AVAILABLE = False
    LIBRARY_STATUS['chardet'] = {
        'available': False,
        'error': str(e),
        'description': 'テキストファイルの文字エンコーディング自動検出',
        'install_cmd': 'pip install chardet'
    }

# Optional libraries for enhanced functionality
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
    LIBRARY_STATUS['openpyxl'] = {
        'available': True,
        'version': getattr(openpyxl, '__version__', 'unknown'),
        'description': 'Excel文書の高度な解析',
        'install_cmd': 'pip install openpyxl'
    }
except ImportError:
    OPENPYXL_AVAILABLE = False
    LIBRARY_STATUS['openpyxl'] = {
        'available': False,
        'description': 'Excel文書の高度な解析（オプション）',
        'install_cmd': 'pip install openpyxl'
    }

# Import the scanner from core module
sys.path.append(str(Path(__file__).parent.parent))

from .folder_tools import (
    FolderNameDeleteDialog,
    MATCH_EXACT,
    remove_folders_matching_query,
)

# Document processing utilities
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

def detect_encoding(path: Path) -> str:
    """Detect file encoding for text files"""
    if not CHARDET_AVAILABLE:
        return 'utf-8'
    
    try:
        with open(path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def analyze_pdf(path: Path) -> Dict[str, Any]:
    """Analyze PDF document"""
    info = {}
    
    if not PYPDF2_AVAILABLE:
        return info
    
    try:
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            
            # Basic info
            info["page_count"] = len(reader.pages)
            
            # Metadata
            if reader.metadata:
                metadata = reader.metadata
                info["title"] = getattr(metadata, 'title', None)
                info["author"] = getattr(metadata, 'author', None)
                info["subject"] = getattr(metadata, 'subject', None)
                info["creator"] = getattr(metadata, 'creator', None)
                info["producer"] = getattr(metadata, 'producer', None)
                info["creation_date"] = getattr(metadata, 'creation_date', None)
                info["modification_date"] = getattr(metadata, 'modification_date', None)
            
            # Try to extract text from first few pages for analysis
            text_content = ""
            for i, page in enumerate(reader.pages[:3]):  # First 3 pages
                try:
                    text_content += page.extract_text() + "\n"
                except:
                    continue
            
            if text_content.strip():
                info["has_text"] = True
                info["text_length"] = len(text_content)
                info["word_count"] = len(text_content.split())
                info["line_count"] = len(text_content.split('\n'))
            else:
                info["has_text"] = False
                
    except Exception as e:
        pass
    
    return info

def analyze_docx(path: Path) -> Dict[str, Any]:
    """Analyze DOCX document"""
    info = {}
    
    if not DOCX_AVAILABLE:
        return info
    
    try:
        doc = DocxDocument(path)
        
        # Core properties
        core_props = doc.core_properties
        info["title"] = core_props.title
        info["author"] = core_props.author
        info["subject"] = core_props.subject
        info["keywords"] = core_props.keywords
        info["comments"] = core_props.comments
        info["category"] = core_props.category
        info["created"] = core_props.created
        info["modified"] = core_props.modified
        info["last_modified_by"] = core_props.last_modified_by
        info["revision"] = core_props.revision
        
        # Content analysis
        paragraphs = doc.paragraphs
        info["paragraph_count"] = len(paragraphs)
        
        text_content = ""
        for para in paragraphs:
            text_content += para.text + "\n"
        
        if text_content.strip():
            info["has_text"] = True
            info["text_length"] = len(text_content)
            info["word_count"] = len(text_content.split())
            info["line_count"] = len(text_content.split('\n'))
        else:
            info["has_text"] = False
            
    except Exception as e:
        pass
    
    return info

def analyze_text_file(path: Path) -> Dict[str, Any]:
    """Analyze text-based document"""
    info = {}
    
    try:
        encoding = detect_encoding(path)
        info["encoding"] = encoding
        
        with open(path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()
            
        if content:
            info["has_text"] = True
            info["text_length"] = len(content)
            info["char_count"] = len(content)
            info["word_count"] = len(content.split())
            info["line_count"] = len(content.split('\n'))
            
            # Analyze content type
            if path.suffix.lower() in ['.py', '.js', '.java', '.cpp', '.c', '.h', '.css', '.html', '.php']:
                info["content_type"] = "code"
                # Count comments and code lines
                lines = content.split('\n')
                code_lines = 0
                comment_lines = 0
                empty_lines = 0
                
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        empty_lines += 1
                    elif stripped.startswith(('#', '//', '/*', '*', '--', '<!--')):
                        comment_lines += 1
                    else:
                        code_lines += 1
                
                info["code_lines"] = code_lines
                info["comment_lines"] = comment_lines
                info["empty_lines"] = empty_lines
                
            elif path.suffix.lower() in ['.md', '.markdown']:
                info["content_type"] = "markdown"
                # Count markdown elements
                info["header_count"] = len(re.findall(r'^#+\s', content, re.MULTILINE))
                info["link_count"] = len(re.findall(r'\[.*?\]\(.*?\)', content))
                info["image_count"] = len(re.findall(r'!\[.*?\]\(.*?\)', content))
                
            elif path.suffix.lower() in ['.json']:
                info["content_type"] = "json"
                try:
                    json_data = json.loads(content)
                    info["json_valid"] = True
                    if isinstance(json_data, dict):
                        info["json_keys"] = len(json_data.keys())
                    elif isinstance(json_data, list):
                        info["json_items"] = len(json_data)
                except:
                    info["json_valid"] = False
                    
            elif path.suffix.lower() in ['.csv']:
                info["content_type"] = "csv"
                lines = content.split('\n')
                if lines:
                    info["csv_columns"] = len(lines[0].split(','))
                    info["csv_rows"] = len([l for l in lines if l.strip()])
                    
            elif path.suffix.lower() in ['.xml']:
                info["content_type"] = "xml"
                try:
                    root = ET.fromstring(content)
                    info["xml_valid"] = True
                    info["xml_root_tag"] = root.tag
                    info["xml_elements"] = len(list(root.iter()))
                except:
                    info["xml_valid"] = False
                    
            else:
                info["content_type"] = "text"
                
        else:
            info["has_text"] = False
            
    except Exception as e:
        info["has_text"] = False
        info["encoding"] = "unknown"
    
    return info

def document_probe(path: Path) -> Dict[str, Any]:
    """Extract comprehensive document metadata"""
    info = {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size": 0,
        "mtime": None,
        "file_hash": None,
        # Common document properties
        "title": None,
        "author": None,
        "subject": None,
        "keywords": None,
        "creator": None,
        "producer": None,
        "creation_date": None,
        "modification_date": None,
        "page_count": None,
        "word_count": None,
        "text_length": None,
        "line_count": None,
        "has_text": False,
        "content_type": None,
        "encoding": None,
        # Format-specific properties
        "paragraph_count": None,
        "revision": None,
        "last_modified_by": None,
        "category": None,
        "comments": None
    }
    
    try:
        stat = path.stat()
        info["size"] = stat.st_size
        info["mtime"] = stat.st_mtime
    except:
        pass
    
    # Calculate file hash for duplicate detection
    info["file_hash"] = get_file_hash(path)
    
    ext = path.suffix.lower()
    
    try:
        if ext == '.pdf':
            pdf_info = analyze_pdf(path)
            info.update(pdf_info)
            info["doc_type"] = "pdf"
            
        elif ext in ['.docx', '.docm']:
            docx_info = analyze_docx(path)
            info.update(docx_info)
            info["doc_type"] = "word"
            
        elif ext in ['.txt', '.md', '.py', '.js', '.java', '.cpp', '.c', '.h', '.css', '.html', '.php', '.json', '.xml', '.csv', '.log', '.ini', '.cfg', '.conf', '.yml', '.yaml']:
            text_info = analyze_text_file(path)
            info.update(text_info)
            info["doc_type"] = "text"
            
        elif ext in ['.rtf']:
            info["doc_type"] = "rtf"
            # Basic RTF analysis
            try:
                with open(path, 'rb') as f:
                    content = f.read(10000).decode('latin1', errors='ignore')
                    info["has_text"] = True
                    info["text_length"] = len(content)
            except:
                pass
                
        elif ext in ['.pptx', '.pptm']:
            info["doc_type"] = "powerpoint"
            # Basic PPTX analysis using zip
            try:
                with zipfile.ZipFile(path, 'r') as zip_file:
                    slides = [f for f in zip_file.namelist() if f.startswith('ppt/slides/slide')]
                    info["slide_count"] = len(slides)
            except:
                pass
                
        elif ext in ['.xlsx', '.xlsm']:
            info["doc_type"] = "excel"
            # Basic XLSX analysis using zip
            try:
                with zipfile.ZipFile(path, 'r') as zip_file:
                    worksheets = [f for f in zip_file.namelist() if f.startswith('xl/worksheets/')]
                    info["worksheet_count"] = len(worksheets)
            except:
                pass
                
        elif ext in ['.odt', '.ods', '.odp']:
            info["doc_type"] = "openoffice"
            
        elif ext in ['.epub']:
            info["doc_type"] = "epub"
            
        else:
            info["doc_type"] = "unknown"
            
    except Exception as e:
        pass
    
    return info

def categorize_document(info: Dict[str, Any]) -> Dict[str, str]:
    """Categorize document file by various criteria"""
    categories = {}
    
    # Format category
    ext = info.get("ext", "").lower()
    doc_type = info.get("doc_type", "unknown")
    
    if doc_type == "pdf":
        categories["format"] = "fmt_pdf"
    elif doc_type == "word":
        categories["format"] = "fmt_word"
    elif doc_type == "powerpoint":
        categories["format"] = "fmt_powerpoint"
    elif doc_type == "excel":
        categories["format"] = "fmt_excel"
    elif doc_type == "text":
        content_type = info.get("content_type", "text")
        if content_type == "code":
            categories["format"] = "fmt_code"
        elif content_type == "markdown":
            categories["format"] = "fmt_markdown"
        elif content_type == "json":
            categories["format"] = "fmt_json"
        elif content_type == "xml":
            categories["format"] = "fmt_xml"
        elif content_type == "csv":
            categories["format"] = "fmt_csv"
        else:
            categories["format"] = "fmt_text"
    elif doc_type == "rtf":
        categories["format"] = "fmt_rtf"
    elif doc_type == "openoffice":
        categories["format"] = "fmt_openoffice"
    elif doc_type == "epub":
        categories["format"] = "fmt_epub"
    else:
        categories["format"] = "fmt_other"
    
    # Size category (pages/content)
    page_count = info.get("page_count")
    word_count = info.get("word_count")
    
    if page_count:
        if page_count <= 5:
            categories["length"] = "len_short"
        elif page_count <= 20:
            categories["length"] = "len_medium"
        elif page_count <= 100:
            categories["length"] = "len_long"
        else:
            categories["length"] = "len_very_long"
    elif word_count:
        if word_count < 500:
            categories["length"] = "len_short"
        elif word_count < 2000:
            categories["length"] = "len_medium"
        elif word_count < 10000:
            categories["length"] = "len_long"
        else:
            categories["length"] = "len_very_long"
    else:
        categories["length"] = "len_unknown"
    
    # File size category
    size = info.get("size", 0)
    if size:
        size_kb = size / 1024
        if size_kb < 10:
            categories["size"] = "size_tiny"
        elif size_kb < 100:
            categories["size"] = "size_small"
        elif size_kb < 1024:
            categories["size"] = "size_medium"
        elif size_kb < 10240:
            categories["size"] = "size_large"
        else:
            categories["size"] = "size_huge"
    else:
        categories["size"] = "size_unknown"
    
    # Content type category
    content_type = info.get("content_type")
    if content_type == "code":
        categories["content"] = "content_code"
    elif content_type == "markdown":
        categories["content"] = "content_markdown"
    elif content_type == "json":
        categories["content"] = "content_data"
    elif content_type == "xml":
        categories["content"] = "content_data"
    elif content_type == "csv":
        categories["content"] = "content_data"
    elif doc_type in ["word", "pdf", "rtf"]:
        categories["content"] = "content_document"
    elif doc_type == "powerpoint":
        categories["content"] = "content_presentation"
    elif doc_type == "excel":
        categories["content"] = "content_spreadsheet"
    else:
        categories["content"] = "content_other"
    
    # Author category
    author = info.get("author")
    if author and isinstance(author, str):
        # Clean author name
        clean_author = re.sub(r'[^a-zA-Z0-9\s]', '', author).strip()
        if clean_author:
            # Use first part of author name as category
            first_name = clean_author.split()[0] if clean_author.split() else "unknown"
            categories["author"] = f"author_{first_name.lower()}"
        else:
            categories["author"] = "author_unknown"
    else:
        categories["author"] = "author_unknown"
    
    # Language category (simple detection based on content)
    has_text = info.get("has_text", False)
    if has_text and info.get("text_length", 0) > 100:
        # Very basic language detection - this could be enhanced
        categories["language"] = "lang_mixed"  # Placeholder
    else:
        categories["language"] = "lang_unknown"
    
    # Date category
    creation_date = info.get("creation_date") or info.get("created")
    if creation_date:
        try:
            if hasattr(creation_date, 'year'):
                date = creation_date
            else:
                # Try to parse datetime
                if isinstance(creation_date, str):
                    date = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
                else:
                    date = creation_date
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


class DocumentAnalysisThread(QThread):
    """Document analysis thread for detailed document file processing"""
    
    progress_updated = Signal(str, int, int)  # message, current, total
    analysis_completed = Signal(dict)         # analysis results
    error_occurred = Signal(str)              # error message
    
    def __init__(self, paths: List[Path]):
        super().__init__()
        self.paths = paths if isinstance(paths, list) else [paths]
        self.document_extensions = {
            '.pdf', '.doc', '.docx', '.docm', '.xls', '.xlsx', '.xlsm', '.ppt', '.pptx', '.pptm',
            '.odt', '.ods', '.odp', '.rtf', '.txt', '.md', '.markdown', '.csv', '.json', '.xml',
            '.html', '.htm', '.py', '.js', '.java', '.cpp', '.c', '.h', '.css', '.php', '.rb',
            '.go', '.rs', '.swift', '.kt', '.scala', '.pl', '.sh', '.bat', '.ps1', '.yml', '.yaml',
            '.ini', '.cfg', '.conf', '.log', '.tex', '.bib', '.epub', '.mobi'
        }
    
    def run(self):
        """Analyze document files in the given paths"""
        try:
            results = {}
            total_files = 0
            processed = 0
            
            # Count total document files
            document_files = []
            for root_path in self.paths:
                if root_path.is_dir():
                    for file_path in root_path.rglob("*"):
                        if file_path.is_file() and file_path.suffix.lower() in self.document_extensions:
                            document_files.append(file_path)
            
            total_files = len(document_files)
            if total_files == 0:
                self.analysis_completed.emit({})
                return
            
            # Process each document file
            for file_path in document_files:
                self.progress_updated.emit(f"解析中: {file_path.name}", processed + 1, total_files)
                
                try:
                    # Get detailed document info
                    document_info = document_probe(file_path)
                    categories = categorize_document(document_info)
                    
                    # Organize by categories
                    for category_type, category_value in categories.items():
                        if category_type not in results:
                            results[category_type] = {}
                        
                        if category_value not in results[category_type]:
                            results[category_type][category_value] = {
                                "count": 0,
                                "total_size": 0,
                                "total_pages": 0,
                                "total_words": 0,
                                "files": []
                            }
                        
                        category_data = results[category_type][category_value]
                        category_data["count"] += 1
                        category_data["total_size"] += document_info.get("size", 0)
                        
                        page_count = document_info.get("page_count", 0) or document_info.get("slide_count", 0)
                        if page_count:
                            category_data["total_pages"] += page_count
                            
                        word_count = document_info.get("word_count", 0)
                        if word_count:
                            category_data["total_words"] += word_count
                            
                        category_data["files"].append(document_info)
                
                except Exception as e:
                    continue  # Skip files that can't be analyzed
                
                processed += 1
            
            self.analysis_completed.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(str(e))


class DocumentAnalyzerWindow(QMainWindow):
    """Enhanced document analyzer with comprehensive analysis and processing capabilities"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文書解析・整理ツール")
        self.setGeometry(200, 200, 1400, 900)
        self.setMinimumSize(1200, 800)
        
        # Data management
        self.selected_paths: List[Path] = []
        self.analysis_results: Dict[str, Any] = {}
        self.analysis_thread: Optional[DocumentAnalysisThread] = None
        self.folder_placeholder_text = "ここに文書フォルダをドラッグ&ドロップ"

        # Check library availability and show detailed status
        self.check_library_dependencies()
        
        self.init_ui()
        self.apply_pro_theme()
        self.setAcceptDrops(True)
    
    def check_library_dependencies(self):
        """Check library dependencies and show detailed status"""
        missing_libs = [lib for lib, status in LIBRARY_STATUS.items() 
                       if not status['available'] and lib in ['PyPDF2', 'python-docx', 'chardet']]
        
        if missing_libs:
            self.show_dependency_dialog(missing_libs)
    
    def show_dependency_dialog(self, missing_libs: List[str]):
        """Show detailed dependency information dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("文書解析ライブラリの依存関係")
        dialog.setMinimumSize(600, 400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Header
        header = QLabel("🔧 文書解析機能の依存関係")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        info_label = QLabel(
            "以下のライブラリが不足しています。インストールすることで文書解析機能が向上します：")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Scrollable area for library details
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for lib_name in missing_libs:
            if lib_name in LIBRARY_STATUS:
                lib_info = LIBRARY_STATUS[lib_name]
                
                lib_group = QGroupBox(f"📦 {lib_name}")
                lib_layout = QVBoxLayout(lib_group)
                
                # Description
                desc_label = QLabel(f"機能: {lib_info['description']}")
                desc_label.setWordWrap(True)
                lib_layout.addWidget(desc_label)
                
                # Install command
                cmd_layout = QHBoxLayout()
                cmd_label = QLabel("インストールコマンド:")
                cmd_layout.addWidget(cmd_label)
                
                cmd_text = QLineEdit(lib_info['install_cmd'])
                cmd_text.setReadOnly(True)
                cmd_text.setStyleSheet("background-color: #f0f0f0; font-family: monospace;")
                cmd_layout.addWidget(cmd_text)
                
                copy_btn = QPushButton("コピー")
                copy_btn.clicked.connect(lambda checked, cmd=lib_info['install_cmd']: 
                                       QApplication.clipboard().setText(cmd))
                copy_btn.setMaximumWidth(60)
                cmd_layout.addWidget(copy_btn)
                
                lib_layout.addLayout(cmd_layout)
                
                scroll_layout.addWidget(lib_group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Quick install section
        quick_install_group = QGroupBox("🚀 一括インストール")
        quick_install_layout = QVBoxLayout(quick_install_group)
        
        all_cmd = "pip install " + " ".join(lib_info['install_cmd'].split()[-1] 
                                          for lib_info in [LIBRARY_STATUS[lib] for lib in missing_libs])
        
        quick_cmd_layout = QHBoxLayout()
        quick_cmd_layout.addWidget(QLabel("全てインストール:"))
        
        quick_cmd_text = QLineEdit(all_cmd)
        quick_cmd_text.setReadOnly(True)
        quick_cmd_text.setStyleSheet("background-color: #f0f0f0; font-family: monospace;")
        quick_cmd_layout.addWidget(quick_cmd_text)
        
        quick_copy_btn = QPushButton("コピー")
        quick_copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(all_cmd))
        quick_copy_btn.setMaximumWidth(60)
        quick_cmd_layout.addWidget(quick_copy_btn)
        
        quick_install_layout.addLayout(quick_cmd_layout)
        
        # Requirements.txt info
        req_info = QLabel("💡 requirements.txtからインストール: pip install -r requirements.txt")
        req_info.setStyleSheet("color: #666; font-style: italic;")
        quick_install_layout.addWidget(req_info)
        
        layout.addWidget(quick_install_group)
        
        # Current status
        status_group = QGroupBox("📊 現在の状況")
        status_layout = QVBoxLayout(status_group)
        
        for lib_name, lib_info in LIBRARY_STATUS.items():
            if lib_name in ['PyPDF2', 'python-docx', 'chardet', 'openpyxl']:
                status_text = f"• {lib_name}: "
                if lib_info['available']:
                    version = lib_info.get('version', 'unknown')
                    status_text += f"✅ インストール済み (v{version})"
                    status_color = "color: green;"
                else:
                    status_text += "❌ 未インストール"
                    status_color = "color: red;"
                
                status_label = QLabel(status_text)
                status_label.setStyleSheet(status_color)
                status_layout.addWidget(status_label)
        
        layout.addWidget(status_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        continue_btn = QPushButton("継続（基本機能のみ使用）")
        continue_btn.clicked.connect(dialog.accept)
        continue_btn.setStyleSheet("background-color: #6c757d; color: white; padding: 8px 16px;")
        button_layout.addWidget(continue_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
        
    def show_library_status_dialog(self):
        """Show current library status (for menu/toolbar access)"""
        all_libs = list(LIBRARY_STATUS.keys())
        self.show_dependency_dialog(all_libs)
    
    def init_ui(self):
        """Initialize the UI layout similar to other analyzers"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Main splitter (vertical)
        vsplitter = QSplitter(Qt.Vertical)
        
        # Top: Document folder tree
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
        self.status_bar.showMessage("文書ファイルフォルダを追加して解析を開始してください")
    
    def create_folder_tree_widget(self):
        """Create folder tree widget for document folders"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("文書フォルダ"))
        
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
        """Create toolbar with document-specific options"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Folder selection
        add_btn = QPushButton("フォルダ選択")
        add_btn.clicked.connect(self.select_document_folders)
        layout.addWidget(add_btn)
        
        # Remove selected
        remove_btn = QPushButton("選択削除")
        remove_btn.clicked.connect(self.remove_selected_folders)
        layout.addWidget(remove_btn)

        name_remove_btn = QPushButton("名前で削除")
        name_remove_btn.clicked.connect(self.remove_folders_by_name)
        layout.addWidget(name_remove_btn)

        # Analysis
        analyze_btn = QPushButton("文書解析実行")
        analyze_btn.setStyleSheet("background-color: #2d5a2d; color: white; font-weight: bold;")
        analyze_btn.clicked.connect(self.run_document_analysis)
        layout.addWidget(analyze_btn)
        
        layout.addWidget(QLabel("|"))
        
        # Processing mode
        layout.addWidget(QLabel("処理モード:"))
        self.processing_mode = QComboBox()
        self.processing_mode.addItems(["文書整理", "フラット化"])
        layout.addWidget(self.processing_mode)
        
        # Dry run
        self.dry_run_check = QCheckBox("シミュレーション")
        self.dry_run_check.setChecked(True)
        layout.addWidget(self.dry_run_check)
        
        layout.addStretch()
        
        # Library status button
        lib_status_btn = QPushButton("ライブラリ状況")
        lib_status_btn.setStyleSheet("color: #007acc;")
        lib_status_btn.clicked.connect(self.show_library_status_dialog)
        lib_status_btn.setToolTip("文書解析ライブラリの依存関係を確認")
        layout.addWidget(lib_status_btn)
        
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
        header = QLabel("文書解析結果")
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
        """Create tabs for different document analysis categories"""
        categories = [
            ("フォーマット", "format"),
            ("文書長", "length"), 
            ("ファイルサイズ", "size"),
            ("コンテンツ", "content"),
            ("作成者", "author"),
            ("言語", "language"),
            ("日付", "date")
        ]
        
        self.category_trees = {}
        
        for tab_name, category_key in categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            tree = QTreeWidget()
            tree.setHeaderLabels(["カテゴリ", "ファイル数", "合計サイズ", "総ページ/語数"])
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
            ("pdf", "PDF", True),
            ("word", "Word文書", True),
            ("excel", "Excel", False),
            ("powerpoint", "PowerPoint", False),
            ("text", "テキストファイル", True),
            ("code", "コードファイル", False)
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
            "文書長別", 
            "ファイルサイズ別",
            "コンテンツ別",
            "作成者別",
            "言語別",
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
            "文書長別", 
            "ファイルサイズ別",
            "コンテンツ別",
            "作成者別",
            "言語別",
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
        self.filter_type.addItems(["ページ数", "文字数", "サイズ", "作成日"])
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
        
        self.duplicate_check = QCheckBox("重複文書を検出・削除")
        additional_layout.addWidget(self.duplicate_check)
        
        self.extract_text_check = QCheckBox("テキスト内容を抽出・保存")
        additional_layout.addWidget(self.extract_text_check)
        
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
            
        # Document analyzer specific styles
        document_style = """
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
        
        self.setStyleSheet(base_style + document_style)
    
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
    
    def select_document_folders(self):
        """Select document folders for analysis"""
        folder = QFileDialog.getExistingDirectory(
            self, "文書フォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.add_document_folder(Path(folder))
    
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
        """Remove folders whose names match the dialog criteria."""
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

    def run_document_analysis(self):
        """Run detailed document analysis"""
        if not self.selected_paths:
            QMessageBox.warning(self, "警告", "解析する文書フォルダがありません")
            return
        
        # Clear previous results
        for tree in self.category_trees.values():
            tree.clear()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start analysis thread
        self.analysis_thread = DocumentAnalysisThread(self.selected_paths)
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
            QMessageBox.information(self, "結果", "文書ファイルが見つかりませんでした")
            return
        
        # Category display names
        category_names = {
            "format": {"fmt_pdf": "PDF", "fmt_word": "Word文書", "fmt_powerpoint": "PowerPoint", "fmt_excel": "Excel", "fmt_text": "テキスト", "fmt_code": "コード", "fmt_markdown": "Markdown", "fmt_json": "JSON", "fmt_xml": "XML", "fmt_csv": "CSV", "fmt_rtf": "RTF", "fmt_openoffice": "OpenOffice", "fmt_epub": "電子書籍", "fmt_other": "その他"},
            "length": {"len_short": "短い", "len_medium": "中程度", "len_long": "長い", "len_very_long": "とても長い", "len_unknown": "不明"},
            "size": {"size_tiny": "極小 (<10KB)", "size_small": "小 (10-100KB)", "size_medium": "中 (100KB-1MB)", "size_large": "大 (1-10MB)", "size_huge": "巨大 (10MB+)", "size_unknown": "不明"},
            "content": {"content_document": "文書", "content_presentation": "プレゼンテーション", "content_spreadsheet": "スプレッドシート", "content_code": "コード", "content_markdown": "Markdown", "content_data": "データ", "content_other": "その他"},
            "author": {},
            "language": {"lang_mixed": "混在", "lang_unknown": "不明"},
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
                display_name = names.get(subcategory, subcategory.replace('_', ' ').title())
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
                
                # Pages/Words
                total_pages = data.get('total_pages', 0)
                total_words = data.get('total_words', 0)
                
                if total_pages > 0:
                    item.setText(3, f"{total_pages:,} ページ")
                elif total_words > 0:
                    if total_words >= 1000:
                        item.setText(3, f"{total_words/1000:.1f}K 語")
                    else:
                        item.setText(3, f"{total_words:,} 語")
                else:
                    item.setText(3, "不明")
                
                # Store data for processing
                item.setData(0, Qt.UserRole, subcategory)
        
        # Expand all trees
        for tree in self.category_trees.values():
            tree.expandAll()
            tree.resizeColumnToContents(0)
        
        self.status_bar.showMessage(f"文書解析完了: {sum(len(cat_data) for cat_data in results.values())} カテゴリ")
    
    def handle_analysis_error(self, error_message: str):
        """Handle analysis errors"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "解析エラー", f"文書解析中にエラーが発生しました:\n\n{error_message}")
        self.status_bar.showMessage("文書解析エラー")
    
    def execute_processing(self):
        """Execute document processing based on settings"""
        if not self.analysis_results:
            QMessageBox.warning(self, "警告", "先に文書解析を実行してください")
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
        self._execute_document_processing(selected_files, Path(output_dir))
    
    def _execute_document_processing(self, files: List[Dict], output_dir: Path):
        """Execute the actual document processing"""
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
                elif mode == "文書整理":
                    # Sort by current category
                    current_tab = self.result_tabs.currentIndex()
                    category_keys = list(self.category_trees.keys())
                    if current_tab < len(category_keys):
                        category = category_keys[current_tab]
                        # Create subdirectory based on category
                        categories = categorize_document(file_info)
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
                    self.add_document_folder(path)
            event.acceptProposedAction()
    
    def add_document_folder(self, folder_path: Path):
        """Add document folder to the analysis list"""
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
        
        # Add document files as children
        document_extensions = {
            '.pdf', '.doc', '.docx', '.docm', '.xls', '.xlsx', '.xlsm', '.ppt', '.pptx', '.pptm',
            '.odt', '.ods', '.odp', '.rtf', '.txt', '.md', '.markdown', '.csv', '.json', '.xml',
            '.html', '.htm', '.py', '.js', '.java', '.cpp', '.c', '.h', '.css', '.php', '.rb',
            '.go', '.rs', '.swift', '.kt', '.scala', '.pl', '.sh', '.bat', '.ps1', '.yml', '.yaml',
            '.ini', '.cfg', '.conf', '.log', '.tex', '.bib', '.epub', '.mobi'
        }
        document_count = 0
        
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in document_extensions:
                    document_count += 1
                    if document_count <= 100:  # Limit display for performance
                        child_item = QTreeWidgetItem(root_item)
                        child_item.setText(0, f"📄 {file_path.name}")
                        child_item.setData(0, Qt.UserRole, str(file_path))
                        child_item.setToolTip(0, str(file_path))
            
            if document_count > 100:
                more_item = QTreeWidgetItem(root_item)
                more_item.setText(0, f"... 他{document_count - 100}個の文書ファイル")
                more_item.setFlags(Qt.NoItemFlags)
                more_item.setForeground(0, QBrush(QColor("#888888")))
        
        except Exception:
            pass
        
        root_item.setExpanded(True)
        self.status_bar.showMessage(f"文書フォルダを追加しました: {folder_path.name} ({document_count}ファイル)")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = DocumentAnalyzerWindow()
    window.show()
    sys.exit(app.exec())
