#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based 3D Model Analysis and Processing Tool
Enhanced 3D analyzer with detailed mesh analysis including vertex count, material info, and geometry properties
Based on the audio/video/image/document analyzer UI structure
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
import struct
import re

# 3D processing library availability check
LIBRARY_STATUS = {}

# Basic mesh processing (built-in Python)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
    LIBRARY_STATUS['numpy'] = {
        'available': True,
        'version': np.__version__,
        'description': '数値計算・メッシュ解析の高速化',
        'install_cmd': 'pip install numpy'
    }
except ImportError as e:
    NUMPY_AVAILABLE = False
    LIBRARY_STATUS['numpy'] = {
        'available': False,
        'error': str(e),
        'description': '数値計算・メッシュ解析の高速化',
        'install_cmd': 'pip install numpy'
    }

# Advanced 3D processing
try:
    import trimesh
    TRIMESH_AVAILABLE = True
    LIBRARY_STATUS['trimesh'] = {
        'available': True,
        'version': trimesh.__version__,
        'description': '高度な3Dメッシュ解析・処理・修復機能',
        'install_cmd': 'pip install trimesh'
    }
except ImportError as e:
    TRIMESH_AVAILABLE = False
    LIBRARY_STATUS['trimesh'] = {
        'available': False,
        'error': str(e),
        'description': '高度な3Dメッシュ解析・処理・修復機能',
        'install_cmd': 'pip install trimesh'
    }

# Open3D for advanced point cloud and mesh operations
try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
    LIBRARY_STATUS['open3d'] = {
        'available': True,
        'version': o3d.__version__,
        'description': '点群・メッシュの高度な解析・可視化',
        'install_cmd': 'pip install open3d'
    }
except ImportError as e:
    OPEN3D_AVAILABLE = False
    LIBRARY_STATUS['open3d'] = {
        'available': False,
        'error': str(e),
        'description': '点群・メッシュの高度な解析・可視化',
        'install_cmd': 'pip install open3d'
    }

# PLY file processing
try:
    from plyfile import PlyData, PlyElement
    PLYFILE_AVAILABLE = True
    LIBRARY_STATUS['plyfile'] = {
        'available': True,
        'version': 'available',
        'description': 'PLYファイル（点群・メッシュ）の詳細解析',
        'install_cmd': 'pip install plyfile'
    }
except ImportError as e:
    PLYFILE_AVAILABLE = False
    LIBRARY_STATUS['plyfile'] = {
        'available': False,
        'error': str(e),
        'description': 'PLYファイル（点群・メッシュ）の詳細解析',
        'install_cmd': 'pip install plyfile'
    }

# Import the scanner from core module
sys.path.append(str(Path(__file__).parent.parent))

from .folder_tools import (
    FolderNameDeleteDialog,
    MATCH_EXACT,
    remove_folders_matching_query,
)

# 3D processing utilities
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

def analyze_obj_file(path: Path) -> Dict[str, Any]:
    """Analyze OBJ file format"""
    info = {}
    
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        vertices = 0
        faces = 0
        normals = 0
        textures = 0
        materials = set()
        groups = set()
        
        for line in lines:
            line = line.strip()
            if line.startswith('v '):
                vertices += 1
            elif line.startswith('f '):
                faces += 1
            elif line.startswith('vn '):
                normals += 1
            elif line.startswith('vt '):
                textures += 1
            elif line.startswith('usemtl '):
                materials.add(line.split()[1] if len(line.split()) > 1 else 'default')
            elif line.startswith('g '):
                groups.add(line.split()[1] if len(line.split()) > 1 else 'default')
            elif line.startswith('mtllib '):
                info["material_lib"] = line.split()[1] if len(line.split()) > 1 else None
        
        info.update({
            "vertex_count": vertices,
            "face_count": faces,
            "normal_count": normals,
            "texture_coord_count": textures,
            "material_count": len(materials),
            "group_count": len(groups),
            "has_materials": len(materials) > 0,
            "has_normals": normals > 0,
            "has_textures": textures > 0,
            "materials": list(materials) if materials else [],
            "groups": list(groups) if groups else []
        })
        
    except Exception as e:
        info["error"] = str(e)
    
    return info

def analyze_stl_file(path: Path) -> Dict[str, Any]:
    """Analyze STL file format"""
    info = {}
    
    try:
        with open(path, 'rb') as f:
            # Check if binary or ASCII
            header = f.read(80)
            f.seek(80)
            triangle_count_bytes = f.read(4)
            
            if len(triangle_count_bytes) == 4:
                triangle_count = struct.unpack('<I', triangle_count_bytes)[0]
                expected_size = 80 + 4 + triangle_count * 50
                actual_size = path.stat().st_size
                
                if abs(expected_size - actual_size) < 100:  # Binary STL
                    info.update({
                        "format_type": "binary",
                        "triangle_count": triangle_count,
                        "vertex_count": triangle_count * 3,  # Approximate
                        "face_count": triangle_count
                    })
                else:  # ASCII STL
                    f.seek(0)
                    content = f.read().decode('utf-8', errors='ignore')
                    triangles = content.count('facet normal')
                    vertices = content.count('vertex')
                    
                    info.update({
                        "format_type": "ascii",
                        "triangle_count": triangles,
                        "vertex_count": vertices,
                        "face_count": triangles
                    })
            else:
                # Fallback to ASCII parsing
                f.seek(0)
                content = f.read().decode('utf-8', errors='ignore')
                triangles = content.count('facet normal')
                vertices = content.count('vertex')
                
                info.update({
                    "format_type": "ascii",
                    "triangle_count": triangles,
                    "vertex_count": vertices,
                    "face_count": triangles
                })
                
    except Exception as e:
        info["error"] = str(e)
    
    return info

def analyze_ply_file(path: Path) -> Dict[str, Any]:
    """Analyze PLY file format"""
    info = {}
    
    try:
        if PLYFILE_AVAILABLE:
            # Use plyfile library if available
            plydata = PlyData.read(path)
            
            info.update({
                "format_type": "ply",
                "element_count": len(plydata.elements)
            })
            
            for element in plydata.elements:
                element_name = element.name
                element_count = element.count
                
                if element_name == 'vertex':
                    info["vertex_count"] = element_count
                    info["has_colors"] = any(prop.name in ['red', 'green', 'blue'] for prop in element.properties)
                    info["has_normals"] = any(prop.name in ['nx', 'ny', 'nz'] for prop in element.properties)
                elif element_name == 'face':
                    info["face_count"] = element_count
                
                info[f"{element_name}_count"] = element_count
        else:
            # Manual parsing fallback
            with open(path, 'rb') as f:
                header = f.read(100).decode('ascii', errors='ignore')
                
                if 'ply' in header.lower():
                    info["format_type"] = "ply"
                    
                    # Try to extract basic info from header
                    lines = header.split('\n')
                    for line in lines:
                        if 'element vertex' in line:
                            parts = line.split()
                            if len(parts) >= 3:
                                info["vertex_count"] = int(parts[2])
                        elif 'element face' in line:
                            parts = line.split()
                            if len(parts) >= 3:
                                info["face_count"] = int(parts[2])
                                
    except Exception as e:
        info["error"] = str(e)
    
    return info

def analyze_3d_with_trimesh(path: Path) -> Dict[str, Any]:
    """Advanced 3D analysis using trimesh library"""
    info = {}
    
    if not TRIMESH_AVAILABLE:
        return info
    
    try:
        # Load mesh with trimesh
        mesh = trimesh.load(str(path))
        
        if hasattr(mesh, 'vertices') and hasattr(mesh, 'faces'):
            info.update({
                "vertex_count": len(mesh.vertices),
                "face_count": len(mesh.faces),
                "is_watertight": mesh.is_watertight,
                "is_winding_consistent": mesh.is_winding_consistent,
                "bounds": mesh.bounds.tolist() if hasattr(mesh.bounds, 'tolist') else str(mesh.bounds),
                "volume": float(mesh.volume) if mesh.is_watertight else None,
                "area": float(mesh.area),
                "center_mass": mesh.center_mass.tolist() if hasattr(mesh.center_mass, 'tolist') else str(mesh.center_mass),
            })
            
            # Material information
            if hasattr(mesh.visual, 'material'):
                material = mesh.visual.material
                if hasattr(material, 'name'):
                    info["material_name"] = material.name
                if hasattr(material, 'baseColorFactor'):
                    info["base_color"] = material.baseColorFactor.tolist()
                    
            # Texture information
            if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
                info["has_uv_mapping"] = True
                info["uv_coords_count"] = len(mesh.visual.uv)
            else:
                info["has_uv_mapping"] = False
                
        elif hasattr(mesh, 'geometry'):
            # Scene with multiple geometries
            info["scene_type"] = "multi_geometry"
            info["geometry_count"] = len(list(mesh.geometry.keys()))
            
            total_vertices = 0
            total_faces = 0
            
            for geom_name, geometry in mesh.geometry.items():
                if hasattr(geometry, 'vertices'):
                    total_vertices += len(geometry.vertices)
                if hasattr(geometry, 'faces'):
                    total_faces += len(geometry.faces)
            
            info["total_vertex_count"] = total_vertices
            info["total_face_count"] = total_faces
            
    except Exception as e:
        info["trimesh_error"] = str(e)
    
    return info

def analyze_gltf_file(path: Path) -> Dict[str, Any]:
    """Analyze GLTF/GLB file format"""
    info = {}
    
    try:
        if path.suffix.lower() == '.gltf':
            # JSON GLTF format
            with open(path, 'r', encoding='utf-8') as f:
                gltf_data = json.load(f)
            
            info.update({
                "format_type": "gltf_json",
                "gltf_version": gltf_data.get("asset", {}).get("version", "unknown"),
                "generator": gltf_data.get("asset", {}).get("generator", "unknown")
            })
            
            # Count various elements
            info["mesh_count"] = len(gltf_data.get("meshes", []))
            info["material_count"] = len(gltf_data.get("materials", []))
            info["texture_count"] = len(gltf_data.get("textures", []))
            info["animation_count"] = len(gltf_data.get("animations", []))
            info["node_count"] = len(gltf_data.get("nodes", []))
            info["scene_count"] = len(gltf_data.get("scenes", []))
            
            # Analyze meshes for vertex/face counts
            total_vertices = 0
            total_faces = 0
            
            for mesh in gltf_data.get("meshes", []):
                for primitive in mesh.get("primitives", []):
                    # This is a simplified analysis - actual vertex counting would require buffer analysis
                    if "POSITION" in primitive.get("attributes", {}):
                        total_vertices += 1000  # Placeholder - would need buffer analysis
                    if "indices" in primitive:
                        total_faces += 500  # Placeholder
            
            info["estimated_vertex_count"] = total_vertices
            info["estimated_face_count"] = total_faces
            
        elif path.suffix.lower() == '.glb':
            # Binary GLTF format
            info["format_type"] = "gltf_binary"
            
            with open(path, 'rb') as f:
                # Read GLB header
                magic = f.read(4)
                if magic == b'glTF':
                    version = struct.unpack('<I', f.read(4))[0]
                    length = struct.unpack('<I', f.read(4))[0]
                    
                    info.update({
                        "gltf_version": f"2.{version}" if version == 2 else str(version),
                        "file_length": length
                    })
                    
                    # JSON chunk header
                    json_length = struct.unpack('<I', f.read(4))[0]
                    json_type = f.read(4)
                    
                    if json_type == b'JSON':
                        json_data = json.loads(f.read(json_length).decode('utf-8'))
                        
                        info["mesh_count"] = len(json_data.get("meshes", []))
                        info["material_count"] = len(json_data.get("materials", []))
                        info["texture_count"] = len(json_data.get("textures", []))
                        info["animation_count"] = len(json_data.get("animations", []))
                        
    except Exception as e:
        info["error"] = str(e)
    
    return info

def threed_probe(path: Path) -> Dict[str, Any]:
    """Extract comprehensive 3D model metadata"""
    info = {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lower(),
        "size": 0,
        "mtime": None,
        "file_hash": None,
        # Common 3D properties
        "vertex_count": None,
        "face_count": None,
        "triangle_count": None,
        "normal_count": None,
        "texture_coord_count": None,
        "material_count": None,
        "animation_count": None,
        "has_materials": False,
        "has_textures": False,
        "has_normals": False,
        "has_colors": False,
        "has_animations": False,
        "is_watertight": None,
        "volume": None,
        "area": None,
        "bounds": None,
        "format_type": None,
        "model_complexity": None
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
        if ext == '.obj':
            obj_info = analyze_obj_file(path)
            info.update(obj_info)
            info["model_type"] = "mesh"
            
        elif ext == '.stl':
            stl_info = analyze_stl_file(path)
            info.update(stl_info)
            info["model_type"] = "mesh"
            
        elif ext == '.ply':
            ply_info = analyze_ply_file(path)
            info.update(ply_info)
            info["model_type"] = "pointcloud_or_mesh"
            
        elif ext in ['.gltf', '.glb']:
            gltf_info = analyze_gltf_file(path)
            info.update(gltf_info)
            info["model_type"] = "scene"
            
        elif ext in ['.fbx', '.dae', '.x3d', '.3ds']:
            info["model_type"] = "complex_scene"
            # These would need specialized libraries for detailed analysis
            
        # Advanced analysis with trimesh if available
        if TRIMESH_AVAILABLE and ext in ['.obj', '.stl', '.ply', '.off']:
            trimesh_info = analyze_3d_with_trimesh(path)
            info.update(trimesh_info)
            
        # Determine model complexity
        vertex_count = info.get("vertex_count", 0) or 0
        face_count = info.get("face_count", 0) or 0
        
        total_elements = vertex_count + face_count
        
        if total_elements < 1000:
            info["model_complexity"] = "simple"
        elif total_elements < 10000:
            info["model_complexity"] = "moderate"
        elif total_elements < 100000:
            info["model_complexity"] = "complex"
        else:
            info["model_complexity"] = "very_complex"
            
    except Exception as e:
        info["analysis_error"] = str(e)
    
    return info

def categorize_3d_model(info: Dict[str, Any]) -> Dict[str, str]:
    """Categorize 3D model file by various criteria"""
    categories = {}
    
    # Format category
    ext = info.get("ext", "").lower()
    if ext == '.obj':
        categories["format"] = "fmt_obj"
    elif ext == '.stl':
        categories["format"] = "fmt_stl"
    elif ext == '.ply':
        categories["format"] = "fmt_ply"
    elif ext in ['.gltf', '.glb']:
        categories["format"] = "fmt_gltf"
    elif ext == '.fbx':
        categories["format"] = "fmt_fbx"
    elif ext == '.dae':
        categories["format"] = "fmt_collada"
    elif ext == '.x3d':
        categories["format"] = "fmt_x3d"
    elif ext == '.3ds':
        categories["format"] = "fmt_3ds"
    elif ext == '.off':
        categories["format"] = "fmt_off"
    elif ext in ['.blend', '.ma', '.mb', '.c4d', '.max']:
        categories["format"] = "fmt_native"
    else:
        categories["format"] = "fmt_other"
    
    # Complexity category
    complexity = info.get("model_complexity", "unknown")
    categories["complexity"] = f"complex_{complexity}"
    
    # Vertex count category
    vertex_count = info.get("vertex_count", 0) or 0
    if vertex_count == 0:
        categories["vertices"] = "vert_unknown"
    elif vertex_count < 100:
        categories["vertices"] = "vert_very_low"
    elif vertex_count < 1000:
        categories["vertices"] = "vert_low"
    elif vertex_count < 10000:
        categories["vertices"] = "vert_medium"
    elif vertex_count < 100000:
        categories["vertices"] = "vert_high"
    else:
        categories["vertices"] = "vert_very_high"
    
    # Features category
    has_materials = info.get("has_materials", False)
    has_textures = info.get("has_textures", False)
    has_normals = info.get("has_normals", False)
    has_colors = info.get("has_colors", False)
    has_animations = info.get("has_animations", False)
    
    feature_score = sum([has_materials, has_textures, has_normals, has_colors, has_animations])
    
    if feature_score == 0:
        categories["features"] = "feat_basic"
    elif feature_score == 1:
        categories["features"] = "feat_simple"
    elif feature_score <= 2:
        categories["features"] = "feat_moderate"
    elif feature_score <= 3:
        categories["features"] = "feat_rich"
    else:
        categories["features"] = "feat_advanced"
    
    # Model type category
    model_type = info.get("model_type", "unknown")
    if model_type == "mesh":
        categories["type"] = "type_mesh"
    elif model_type == "pointcloud_or_mesh":
        categories["type"] = "type_pointcloud"
    elif model_type == "scene":
        categories["type"] = "type_scene"
    elif model_type == "complex_scene":
        categories["type"] = "type_complex"
    else:
        categories["type"] = "type_unknown"
    
    # File size category
    size = info.get("size", 0)
    if size:
        size_mb = size / (1024 * 1024)
        if size_mb < 1:
            categories["size"] = "size_small"
        elif size_mb < 10:
            categories["size"] = "size_medium"
        elif size_mb < 100:
            categories["size"] = "size_large"
        elif size_mb < 500:
            categories["size"] = "size_very_large"
        else:
            categories["size"] = "size_huge"
    else:
        categories["size"] = "size_unknown"
    
    # Quality/Watertight category
    is_watertight = info.get("is_watertight")
    if is_watertight is True:
        categories["quality"] = "qual_watertight"
    elif is_watertight is False:
        categories["quality"] = "qual_open_mesh"
    else:
        categories["quality"] = "qual_unknown"
    
    # Date category
    mtime = info.get("mtime")
    if mtime:
        date = datetime.fromtimestamp(mtime)
        categories["date"] = f"{date.year}-{date.month:02d}"
    else:
        categories["date"] = "date_unknown"
    
    return categories


class ThreeDAnalysisThread(QThread):
    """3D model analysis thread for detailed 3D file processing"""
    
    progress_updated = Signal(str, int, int)  # message, current, total
    analysis_completed = Signal(dict)         # analysis results
    error_occurred = Signal(str)              # error message
    
    def __init__(self, paths: List[Path]):
        super().__init__()
        self.paths = paths if isinstance(paths, list) else [paths]
        self.threed_extensions = {
            '.obj', '.stl', '.ply', '.off', '.gltf', '.glb', '.fbx', '.dae', '.x3d', '.3ds',
            '.blend', '.ma', '.mb', '.c4d', '.max', '.lwo', '.3mf', '.amf', '.wrl', '.vrml'
        }
    
    def run(self):
        """Analyze 3D model files in the given paths"""
        try:
            results = {}
            total_files = 0
            processed = 0
            
            # Count total 3D model files
            threed_files = []
            for root_path in self.paths:
                if root_path.is_dir():
                    for file_path in root_path.rglob("*"):
                        if file_path.is_file() and file_path.suffix.lower() in self.threed_extensions:
                            threed_files.append(file_path)
            
            total_files = len(threed_files)
            if total_files == 0:
                self.analysis_completed.emit({})
                return
            
            # Process each 3D model file
            for file_path in threed_files:
                self.progress_updated.emit(f"解析中: {file_path.name}", processed + 1, total_files)
                
                try:
                    # Get detailed 3D model info
                    threed_info = threed_probe(file_path)
                    categories = categorize_3d_model(threed_info)
                    
                    # Organize by categories
                    for category_type, category_value in categories.items():
                        if category_type not in results:
                            results[category_type] = {}
                        
                        if category_value not in results[category_type]:
                            results[category_type][category_value] = {
                                "count": 0,
                                "total_size": 0,
                                "total_vertices": 0,
                                "total_faces": 0,
                                "files": []
                            }
                        
                        category_data = results[category_type][category_value]
                        category_data["count"] += 1
                        category_data["total_size"] += threed_info.get("size", 0)
                        
                        vertex_count = threed_info.get("vertex_count", 0) or 0
                        face_count = threed_info.get("face_count", 0) or 0
                        
                        category_data["total_vertices"] += vertex_count
                        category_data["total_faces"] += face_count
                        category_data["files"].append(threed_info)
                
                except Exception as e:
                    continue  # Skip files that can't be analyzed
                
                processed += 1
            
            self.analysis_completed.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(str(e))


class ThreeDAnalyzerWindow(QMainWindow):
    """Enhanced 3D model analyzer with comprehensive analysis and processing capabilities"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3Dモデル解析・整理ツール")
        self.setGeometry(200, 200, 1400, 900)
        self.setMinimumSize(1200, 800)
        
        # Data management
        self.selected_paths: List[Path] = []
        self.analysis_results: Dict[str, Any] = {}
        self.analysis_thread: Optional[ThreeDAnalysisThread] = None
        self.folder_placeholder_text = "ここに3Dモデルフォルダをドラッグ&ドロップ"
        
        # Check library availability and show detailed status
        self.check_library_dependencies()
        
        self.init_ui()
        self.apply_pro_theme()
        self.setAcceptDrops(True)
    
    def check_library_dependencies(self):
        """Check library dependencies and show detailed status"""
        missing_libs = [lib for lib, status in LIBRARY_STATUS.items() 
                       if not status['available'] and lib in ['numpy', 'trimesh']]
        
        if missing_libs:
            self.show_dependency_dialog(missing_libs)
    
    def show_dependency_dialog(self, missing_libs: List[str]):
        """Show detailed dependency information dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("3D解析ライブラリの依存関係")
        dialog.setMinimumSize(600, 400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Header
        header = QLabel("🎮 3D解析機能の依存関係")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        info_label = QLabel(
            "以下のライブラリが不足しています。インストールすることで3D解析機能が向上します：")
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
        
        # Current status
        status_group = QGroupBox("📊 現在の状況")
        status_layout = QVBoxLayout(status_group)
        
        for lib_name, lib_info in LIBRARY_STATUS.items():
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
        
        # Top: 3D model folder tree
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
        self.status_bar.showMessage("3Dモデルファイルフォルダを追加して解析を開始してください")
    
    def create_folder_tree_widget(self):
        """Create folder tree widget for 3D model folders"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("3Dモデルフォルダ"))
        
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
        """Create toolbar with 3D-specific options"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Folder selection
        add_btn = QPushButton("フォルダ選択")
        add_btn.clicked.connect(self.select_threed_folders)
        layout.addWidget(add_btn)
        
        # Remove selected
        remove_btn = QPushButton("選択削除")
        remove_btn.clicked.connect(self.remove_selected_folders)
        layout.addWidget(remove_btn)

        name_remove_btn = QPushButton("名前で削除")
        name_remove_btn.clicked.connect(self.remove_folders_by_name)
        layout.addWidget(name_remove_btn)

        # Analysis
        analyze_btn = QPushButton("3Dモデル解析実行")
        analyze_btn.setStyleSheet("background-color: #2d5a2d; color: white; font-weight: bold;")
        analyze_btn.clicked.connect(self.run_threed_analysis)
        layout.addWidget(analyze_btn)
        
        layout.addWidget(QLabel("|"))
        
        # Processing mode
        layout.addWidget(QLabel("処理モード:"))
        self.processing_mode = QComboBox()
        self.processing_mode.addItems(["3Dモデル整理", "フラット化"])
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
        lib_status_btn.setToolTip("3D解析ライブラリの依存関係を確認")
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
        header = QLabel("3Dモデル解析結果")
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
        """Create tabs for different 3D model analysis categories"""
        categories = [
            ("フォーマット", "format"),
            ("複雑度", "complexity"), 
            ("頂点数", "vertices"),
            ("機能", "features"),
            ("モデル種別", "type"),
            ("ファイルサイズ", "size"),
            ("品質", "quality"),
            ("日付", "date")
        ]
        
        self.category_trees = {}
        
        for tab_name, category_key in categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            tree = QTreeWidget()
            tree.setHeaderLabels(["カテゴリ", "ファイル数", "合計サイズ", "総頂点数"])
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
            ("obj", "OBJ", True),
            ("stl", "STL", True),
            ("ply", "PLY", False),
            ("gltf", "GLTF/GLB", False),
            ("fbx", "FBX", False)
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
            "複雑度別", 
            "頂点数別",
            "機能別",
            "モデル種別",
            "ファイルサイズ別",
            "品質別",
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
            "複雑度別", 
            "頂点数別",
            "機能別",
            "モデル種別",
            "ファイルサイズ別",
            "品質別",
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
        self.filter_type.addItems(["頂点数", "面数", "サイズ", "複雑度"])
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
        
        self.duplicate_check = QCheckBox("重複モデルを検出・削除")
        additional_layout.addWidget(self.duplicate_check)
        
        self.mesh_repair_check = QCheckBox("メッシュ修復を実行")
        self.mesh_repair_check.setEnabled(TRIMESH_AVAILABLE)
        additional_layout.addWidget(self.mesh_repair_check)
        
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
            
        # 3D analyzer specific styles
        threed_style = """
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
        
        self.setStyleSheet(base_style + threed_style)
    
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
    
    def select_threed_folders(self):
        """Select 3D model folders for analysis"""
        folder = QFileDialog.getExistingDirectory(
            self, "3Dモデルフォルダを選択", 
            str(Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.add_threed_folder(Path(folder))
    
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
        """Remove folders whose names match user-provided criteria."""
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

    def run_threed_analysis(self):
        """Run detailed 3D model analysis"""
        if not self.selected_paths:
            QMessageBox.warning(self, "警告", "解析する3Dモデルフォルダがありません")
            return
        
        # Clear previous results
        for tree in self.category_trees.values():
            tree.clear()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start analysis thread
        self.analysis_thread = ThreeDAnalysisThread(self.selected_paths)
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
            QMessageBox.information(self, "結果", "3Dモデルファイルが見つかりませんでした")
            return
        
        # Category display names
        category_names = {
            "format": {"fmt_obj": "OBJ", "fmt_stl": "STL", "fmt_ply": "PLY", "fmt_gltf": "GLTF/GLB", "fmt_fbx": "FBX", "fmt_collada": "Collada", "fmt_x3d": "X3D", "fmt_3ds": "3DS", "fmt_off": "OFF", "fmt_native": "ネイティブ形式", "fmt_other": "その他"},
            "complexity": {"complex_simple": "シンプル", "complex_moderate": "中程度", "complex_complex": "複雑", "complex_very_complex": "非常に複雑", "complex_unknown": "不明"},
            "vertices": {"vert_very_low": "極少 (<100)", "vert_low": "少 (100-1K)", "vert_medium": "中 (1K-10K)", "vert_high": "多 (10K-100K)", "vert_very_high": "極多 (100K+)", "vert_unknown": "不明"},
            "features": {"feat_basic": "基本", "feat_simple": "シンプル", "feat_moderate": "中程度", "feat_rich": "リッチ", "feat_advanced": "高度"},
            "type": {"type_mesh": "メッシュ", "type_pointcloud": "点群", "type_scene": "シーン", "type_complex": "複合シーン", "type_unknown": "不明"},
            "size": {"size_small": "小 (<1MB)", "size_medium": "中 (1-10MB)", "size_large": "大 (10-100MB)", "size_very_large": "特大 (100-500MB)", "size_huge": "巨大 (500MB+)", "size_unknown": "不明"},
            "quality": {"qual_watertight": "水密", "qual_open_mesh": "開放メッシュ", "qual_unknown": "不明"},
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
                
                # Total vertices
                total_vertices = data.get('total_vertices', 0)
                if total_vertices > 0:
                    if total_vertices >= 1_000_000:
                        item.setText(3, f"{total_vertices/1_000_000:.1f}M 頂点")
                    elif total_vertices >= 1_000:
                        item.setText(3, f"{total_vertices/1_000:.1f}K 頂点")
                    else:
                        item.setText(3, f"{total_vertices:,} 頂点")
                else:
                    item.setText(3, "不明")
                
                # Store data for processing
                item.setData(0, Qt.UserRole, subcategory)
        
        # Expand all trees
        for tree in self.category_trees.values():
            tree.expandAll()
            tree.resizeColumnToContents(0)
        
        self.status_bar.showMessage(f"3Dモデル解析完了: {sum(len(cat_data) for cat_data in results.values())} カテゴリ")
    
    def handle_analysis_error(self, error_message: str):
        """Handle analysis errors"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "解析エラー", f"3Dモデル解析中にエラーが発生しました:\n\n{error_message}")
        self.status_bar.showMessage("3Dモデル解析エラー")
    
    def execute_processing(self):
        """Execute 3D model processing based on settings"""
        if not self.analysis_results:
            QMessageBox.warning(self, "警告", "先に3Dモデル解析を実行してください")
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
        self._execute_threed_processing(selected_files, Path(output_dir))
    
    def _execute_threed_processing(self, files: List[Dict], output_dir: Path):
        """Execute the actual 3D model processing"""
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
                elif mode == "3Dモデル整理":
                    # Sort by current category
                    current_tab = self.result_tabs.currentIndex()
                    category_keys = list(self.category_trees.keys())
                    if current_tab < len(category_keys):
                        category = category_keys[current_tab]
                        # Create subdirectory based on category
                        categories = categorize_3d_model(file_info)
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
                    self.add_threed_folder(path)
            event.acceptProposedAction()
    
    def add_threed_folder(self, folder_path: Path):
        """Add 3D model folder to the analysis list"""
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
        
        # Add 3D model files as children
        threed_extensions = {
            '.obj', '.stl', '.ply', '.off', '.gltf', '.glb', '.fbx', '.dae', '.x3d', '.3ds',
            '.blend', '.ma', '.mb', '.c4d', '.max', '.lwo', '.3mf', '.amf', '.wrl', '.vrml'
        }
        threed_count = 0
        
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in threed_extensions:
                    threed_count += 1
                    if threed_count <= 100:  # Limit display for performance
                        child_item = QTreeWidgetItem(root_item)
                        child_item.setText(0, f"🎮 {file_path.name}")
                        child_item.setData(0, Qt.UserRole, str(file_path))
                        child_item.setToolTip(0, str(file_path))
            
            if threed_count > 100:
                more_item = QTreeWidgetItem(root_item)
                more_item.setText(0, f"... 他{threed_count - 100}個の3Dモデルファイル")
                more_item.setFlags(Qt.NoItemFlags)
                more_item.setForeground(0, QBrush(QColor("#888888")))
        
        except Exception:
            pass
        
        root_item.setExpanded(True)
        self.status_bar.showMessage(f"3Dモデルフォルダを追加しました: {folder_path.name} ({threed_count}ファイル)")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = ThreeDAnalyzerWindow()
    window.show()
    sys.exit(app.exec())
