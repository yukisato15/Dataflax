#!/usr/bin/env python3
"""
Dataflux ロゴ・アイコン作成スクリプト
完全抽象・流線型のフリーフォームデザイン
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import math

def create_gradient_circle(draw, center, radius, start_color, end_color, alpha=255):
    """グラデーション円を作成"""
    for r in range(int(radius)):
        # グラデーション計算
        t = r / radius
        color = tuple(int(start_color[i] * (1-t) + end_color[i] * t) for i in range(3))
        color = color + (int(alpha * (1-t*0.3)),)
        
        # 円を描画
        x, y = center
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color)

def create_flowing_line(draw, points, color, width, alpha_gradient=True):
    """流線を描画"""
    for i in range(len(points)-1):
        start = points[i]
        end = points[i+1]
        
        # アルファグラデーション
        if alpha_gradient:
            alpha = int(255 * (1 - i / len(points)))
            line_color = color[:3] + (alpha,)
        else:
            line_color = color
            
        # 線の太さをグラデーション
        current_width = int(width * (1 - i / len(points) * 0.7))
        draw.line([start, end], fill=line_color, width=current_width)

def create_dataflux_logo(size=512):
    """Dataflux ロゴを作成"""
    # RGBA画像作成
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = (size//2, size//2)
    
    # 配色定義
    kachi_color = (24, 27, 57)      # 勝色
    chigusa_color = (58, 143, 183)  # 千草色
    brown_color = (120, 80, 60)     # 焦茶
    light_blue = (111, 175, 198)    # 薄い千草色
    
    # 背景の微細なグラデーション
    for y in range(size):
        alpha = int(20 * (1 - abs(y - size//2) / (size//2)))
        color = kachi_color + (alpha,)
        draw.line([(0, y), (size, y)], fill=color, width=1)
    
    # メインの流線群を作成
    for i in range(8):
        angle_offset = i * math.pi / 4
        
        # 流線の基点
        start_radius = size * 0.15
        end_radius = size * 0.4
        
        start_x = center[0] + start_radius * math.cos(angle_offset)
        start_y = center[1] + start_radius * math.sin(angle_offset)
        
        # 複数の制御点で滑らかな曲線を作成
        points = []
        for t in np.linspace(0, 1, 20):
            # スパイラル + 波の組み合わせ
            angle = angle_offset + t * math.pi * 2 + math.sin(t * math.pi * 3) * 0.3
            radius = start_radius + t * (end_radius - start_radius)
            
            # ノイズを追加して自然な流線に
            noise_x = math.sin(t * math.pi * 6) * size * 0.02
            noise_y = math.cos(t * math.pi * 4) * size * 0.02
            
            x = center[0] + radius * math.cos(angle) + noise_x
            y = center[1] + radius * math.sin(angle) + noise_y
            
            points.append((int(x), int(y)))
        
        # 色を選択（交互に異なる色）
        if i % 3 == 0:
            line_color = chigusa_color + (200,)
            width = 8
        elif i % 3 == 1:
            line_color = light_blue + (180,)
            width = 6
        else:
            line_color = brown_color + (160,)
            width = 4
            
        create_flowing_line(draw, points, line_color, width)
    
    # 中央の光点群
    for i in range(12):
        angle = i * math.pi / 6
        distance = size * 0.08 + (i % 3) * size * 0.02
        
        x = center[0] + distance * math.cos(angle)
        y = center[1] + distance * math.sin(angle)
        
        # グラデーション円
        if i % 4 == 0:
            create_gradient_circle(draw, (int(x), int(y)), 8, 
                                 chigusa_color, light_blue, 200)
        else:
            create_gradient_circle(draw, (int(x), int(y)), 5, 
                                 light_blue, chigusa_color, 150)
    
    # 外周の微細な光効果
    for i in range(24):
        angle = i * math.pi / 12
        distance = size * 0.42
        
        x = center[0] + distance * math.cos(angle)
        y = center[1] + distance * math.sin(angle)
        
        # 小さな光点
        color = chigusa_color + (100,)
        draw.ellipse([x-2, y-2, x+2, y+2], fill=color)
    
    # 虹色のアクセント線（データの多様性を表現）
    rainbow_colors = [
        (255, 100, 100, 120), (255, 165, 100, 120), (255, 255, 100, 120),
        (100, 255, 100, 120), (100, 255, 255, 120), (100, 100, 255, 120),
        (255, 100, 255, 120)
    ]
    
    for i, color in enumerate(rainbow_colors):
        angle = i * math.pi * 2 / len(rainbow_colors)
        start_r = size * 0.2
        end_r = size * 0.35
        
        start_x = center[0] + start_r * math.cos(angle)
        start_y = center[1] + start_r * math.sin(angle)
        end_x = center[0] + end_r * math.cos(angle)
        end_y = center[1] + end_r * math.sin(angle)
        
        draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=3)
    
    return img

def add_text_logo(img, text="Dataflux"):
    """ロゴにテキストを追加"""
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # フォントサイズを動的に調整
    font_size = width // 12
    
    try:
        # システムフォントを使用
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        font = ImageFont.load_default()
    
    # テキストサイズを取得
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # テキスト位置（下部中央）
    text_x = (width - text_width) // 2
    text_y = height - text_height - height // 8
    
    # 影効果
    shadow_color = (24, 27, 57, 200)  # 勝色
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            if dx != 0 or dy != 0:
                draw.text((text_x + dx, text_y + dy), text, font=font, fill=shadow_color)
    
    # メインテキスト
    text_color = (255, 255, 255, 255)  # 白
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    
    return img

def create_icon_version(logo_img, icon_size=256):
    """アイコン用に最適化"""
    # アイコンサイズにリサイズ
    icon = logo_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    
    # アイコン用に少し単純化
    draw = ImageDraw.Draw(icon)
    center = (icon_size//2, icon_size//2)
    
    # 中央に強調点を追加
    chigusa_color = (58, 143, 183, 255)
    create_gradient_circle(draw, center, icon_size//6, 
                         (58, 143, 183), (111, 175, 198), 255)
    
    return icon

if __name__ == "__main__":
    print("Dataflux ロゴ・アイコンを作成中...")
    
    # 高解像度ロゴ作成
    logo = create_dataflux_logo(512)
    logo_with_text = add_text_logo(logo, "Dataflux")
    
    # ロゴ保存
    logo_with_text.save("dataflux_logo.png")
    print("✅ ロゴ保存: dataflux_logo.png")
    
    # アイコン作成（複数サイズ）
    for size in [256, 128, 64, 32]:
        icon = create_icon_version(logo, size)
        icon.save(f"icon_dataflux_{size}.png")
        print(f"✅ アイコン保存: icon_dataflux_{size}.png")
    
    # メインアイコン（256px）をコピー
    main_icon = create_icon_version(logo, 256)
    main_icon.save("icon_dataflux.png")
    print("✅ メインアイコン保存: icon_dataflux.png")
    
    print("\n🎨 Dataflux ロゴ・アイコン作成完了!")
    print("   - 完全抽象・流線型デザイン")
    print("   - 勝色・千草色・茶色の和風配色")
    print("   - データフローを表現する光の束")
    print("   - 虹色アクセントで多様性を表現")
