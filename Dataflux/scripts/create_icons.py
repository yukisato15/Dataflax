#!/usr/bin/env python3
"""
Dataflux アイコン形式変換スクリプト
PNG → ICO (Windows) / ICNS (macOS) 変換
"""

from PIL import Image
import os
import subprocess
from pathlib import Path

def create_ico_from_png(png_path, ico_path, sizes=[16, 32, 48, 64, 128, 256]):
    """PNG から ICO ファイルを作成"""
    try:
        original = Image.open(png_path)
        
        # 各サイズのアイコン画像を作成
        icon_sizes = []
        for size in sizes:
            resized = original.resize((size, size), Image.Resampling.LANCZOS)
            icon_sizes.append(resized)
        
        # ICOファイルとして保存
        icon_sizes[0].save(
            ico_path,
            format='ICO',
            sizes=[(img.width, img.height) for img in icon_sizes],
            append_images=icon_sizes[1:]
        )
        print(f"✅ ICO created: {ico_path}")
        return True
    except Exception as e:
        print(f"❌ ICO creation failed: {e}")
        return False

def create_icns_from_png(png_path, icns_path):
    """PNG から ICNS ファイルを作成 (macOS用)"""
    try:
        # macOSのiconutil使用 (macOS専用)
        if os.system("which iconutil > /dev/null") == 0:
            # iconset ディレクトリ作成
            iconset_dir = Path("temp.iconset")
            iconset_dir.mkdir(exist_ok=True)
            
            original = Image.open(png_path)
            
            # 各サイズ作成
            sizes = {
                16: "icon_16x16.png",
                32: "icon_16x16@2x.png", 
                32: "icon_32x32.png",
                64: "icon_32x32@2x.png",
                128: "icon_128x128.png",
                256: "icon_128x128@2x.png",
                256: "icon_256x256.png", 
                512: "icon_256x256@2x.png",
                512: "icon_512x512.png",
                1024: "icon_512x512@2x.png"
            }
            
            for size, filename in sizes.items():
                resized = original.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(iconset_dir / filename)
            
            # iconutil で変換
            result = subprocess.run([
                "iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)
            ], capture_output=True)
            
            # クリーンアップ
            import shutil
            shutil.rmtree(iconset_dir)
            
            if result.returncode == 0:
                print(f"✅ ICNS created: {icns_path}")
                return True
            else:
                print(f"❌ iconutil failed: {result.stderr}")
                return False
        else:
            print("⚠️  iconutil not available (macOS required for ICNS)")
            return False
            
    except Exception as e:
        print(f"❌ ICNS creation failed: {e}")
        return False

def main():
    """メイン処理"""
    print("🎨 Dataflux Icon Conversion")
    print("=" * 30)
    
    # ソースPNG
    source_png = Path("icon_dataflux.png")
    if not source_png.exists():
        print(f"❌ Source PNG not found: {source_png}")
        return
    
    # 出力ディレクトリ
    assets_dir = Path("assets/icons")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Windows ICO
    ico_path = assets_dir / "dataflux.ico"
    create_ico_from_png(source_png, ico_path)
    
    # macOS ICNS
    icns_path = assets_dir / "dataflux.icns"
    create_icns_from_png(source_png, icns_path)
    
    # PNG コピー (Linux用)
    png_path = assets_dir / "dataflux.png"
    import shutil
    shutil.copy2(source_png, png_path)
    print(f"✅ PNG copied: {png_path}")
    
    print("\n🎉 Icon conversion completed!")
    print("\nGenerated files:")
    for icon_file in assets_dir.glob("dataflux.*"):
        size_mb = icon_file.stat().st_size / 1024
        print(f"  - {icon_file.name}: {size_mb:.1f} KB")

if __name__ == "__main__":
    main()
