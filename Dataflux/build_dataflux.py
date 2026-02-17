#!/usr/bin/env python3
"""
Dataflux 配布用ビルドスクリプト
ffprobe同梱版の作成とZIP配布パッケージ生成
"""

import os
import sys
import shutil
import subprocess
import platform
import zipfile
from pathlib import Path

def get_platform_info():
    """プラットフォーム情報を取得"""
    system = platform.system().lower()
    if system == "darwin":
        return "macOS", "Dataflux.app", "icns"
    elif system == "windows":
        return "Windows", "Dataflux.exe", "ico"
    else:
        return "Linux", "Dataflux", "png"

def check_ffprobe():
    """ffprobe バイナリの存在確認"""
    system = platform.system().lower()
    if system == "windows":
        ffprobe_path = Path("bin/ffprobe.exe")
    else:
        ffprobe_path = Path("bin/ffprobe")
    
    if not ffprobe_path.exists():
        print(f"⚠️  {ffprobe_path} not found!")
        print("Please place ffprobe binary in bin/ directory.")
        print("See bin/README.md for instructions.")
        return False
    
    # 実行権限チェック（Unix系）
    if system != "windows" and not os.access(ffprobe_path, os.X_OK):
        print(f"Setting execute permission for {ffprobe_path}")
        ffprobe_path.chmod(0o755)
    
    print(f"✅ ffprobe found: {ffprobe_path}")
    return True

def prepare_assets():
    """アセット準備"""
    assets_dir = Path("assets/icons")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    platform_name, _, icon_ext = get_platform_info()
    
    # アイコンファイル準備
    main_icon = Path("icon_dataflux.png")
    target_icon = assets_dir / f"dataflux.{icon_ext}"
    
    if main_icon.exists():
        shutil.copy2(main_icon, target_icon)
        print(f"✅ Icon prepared: {target_icon}")
    else:
        print("⚠️  Main icon not found, using fallback")
    
    return target_icon.exists()

def build_with_pyinstaller():
    """PyInstaller でビルド実行"""
    platform_name, app_name, icon_ext = get_platform_info()
    
    # 基本コマンド
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        "--name", "Dataflux"
    ]
    
    # アイコン追加
    icon_path = Path(f"assets/icons/dataflux.{icon_ext}")
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
    
    # データファイル追加
    if platform.system().lower() == "windows":
        # Windows用パス区切り
        cmd.extend([
            "--add-data", "themes;themes",
            "--add-data", "ui_qt;ui_qt", 
            "--add-data", "core;core",
            "--add-data", "utils;utils",
            "--add-binary", "bin\\ffprobe.exe;bin"
        ])
    else:
        # Unix系用パス区切り
        cmd.extend([
            "--add-data", "themes:themes",
            "--add-data", "ui_qt:ui_qt",
            "--add-data", "core:core", 
            "--add-data", "utils:utils",
            "--add-binary", "bin/ffprobe:bin"
        ])
    
    # PySide6 を明示的に収集（PyInstaller 6.x / Python 3.12 での漏れ対策）
    cmd.extend([
        "--hidden-import", "PySide6",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
    ])

    # メインスクリプト
    cmd.append("main.py")
    
    print("🔨 Building Dataflux with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Build completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def create_distribution_files():
    """配布用ファイル作成"""
    
    # README.md
    readme_content = """# Dataflux v2.0

完全抽象・流線型デザインのデータフロー解析スイート

## 特徴

- 🌊 **流線型UI**: 勝色・千草色を基調とした和風デザイン
- 📊 **マルチメディア解析**: Audio・Video・Image・Document・3D対応
- 🎯 **専門特化ツール**: 各形式に最適化された解析機能
- 🎨 **抽象アートロゴ**: データの流れを表現したブランドデザイン
- ⚡ **ffprobe同梱**: 動画解析に必要なツールを内蔵

## システム要件

- **macOS**: 10.14 以上
- **Windows**: Windows 10 以上  
- **メモリ**: 4GB以上推奨
- **ストレージ**: 500MB以上の空き容量

## 使用方法

1. アプリケーションを起動
2. 目的に応じたツールを選択
3. ファイルまたはフォルダを指定して解析実行

## 同梱ソフトウェア

- **FFmpeg ffprobe**: LGPL v2.1+ ライセンス
  - 動画ファイルのメタデータ解析に使用
  - https://ffmpeg.org/

## ライセンス

本アプリケーションは独自ライセンスです。
同梱のFFmpegコンポーネントはLGPL v2.1+に従います。

## サポート

技術的な問題やご質問は開発者までお問い合わせください。
"""
    
    Path("README.md").write_text(readme_content, encoding="utf-8")
    
    # FFmpeg LICENSE
    ffmpeg_license = """FFmpeg License Notice

This application includes FFmpeg components (ffprobe) which are licensed under 
the GNU Lesser General Public License (LGPL) version 2.1 or later.

FFmpeg source code is available at: https://ffmpeg.org/download.html

For complete license terms, see: https://www.gnu.org/licenses/lgpl-2.1.html

Key LGPL requirements:
- Source code availability for LGPL components
- Permission to link with proprietary software
- Distribution of license notices

The LGPL does not affect the licensing of the main application,
but applies specifically to the included FFmpeg components.
"""
    
    Path("FFMPEG_LICENSE.txt").write_text(ffmpeg_license)
    print("✅ Distribution files created")

def create_distribution_zip():
    """配布用ZIP作成"""
    platform_name, app_name, _ = get_platform_info()
    
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ dist/ directory not found. Build first.")
        return False
    
    # 出力ファイル名
    zip_name = f"Dataflux-{platform_name}.zip"
    zip_path = dist_dir / zip_name
    
    # 既存ZIPを削除
    if zip_path.exists():
        zip_path.unlink()
    
    print(f"📦 Creating distribution ZIP: {zip_name}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # アプリケーション追加
        if platform_name == "macOS":
            app_path = dist_dir / "Dataflux.app"
            if app_path.exists():
                # .app バンドル全体を追加
                for root, dirs, files in os.walk(app_path):
                    for file in files:
                        file_path = Path(root) / file
                        arc_path = file_path.relative_to(dist_dir)
                        zf.write(file_path, arc_path)
        else:
            # Windows/Linux
            app_dir = dist_dir / "Dataflux"  # フォルダ版
            if app_dir.exists():
                for root, dirs, files in os.walk(app_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arc_path = file_path.relative_to(dist_dir)
                        zf.write(file_path, arc_path)
        
        # 配布文書追加
        zf.write("README.md")
        zf.write("FFMPEG_LICENSE.txt")
    
    print(f"✅ Distribution ZIP created: {zip_path}")
    print(f"   Size: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    return True

def main():
    """メイン処理"""
    print("🚀 Dataflux Distribution Build Script")
    print("=" * 50)
    
    # 1. ffprobe チェック
    if not check_ffprobe():
        sys.exit(1)
    
    # 2. アセット準備  
    prepare_assets()
    
    # 3. 配布文書作成
    create_distribution_files()
    
    # 4. PyInstaller ビルド
    if not build_with_pyinstaller():
        sys.exit(1)
    
    # 5. 配布ZIP作成
    if not create_distribution_zip():
        sys.exit(1)
    
    print("\n🎉 Build completed successfully!")
    print("\n📋 Next steps:")
    print("1. Test the built application")
    print("2. Verify ffprobe integration works")
    print("3. Check video analysis functionality")
    print("4. Distribute the ZIP file")

if __name__ == "__main__":
    main()
