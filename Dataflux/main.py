#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Sorting Box v2.0 - PySide6版
メインエントリーポイント
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_dependencies():
    """必要なライブラリの確認"""
    missing_deps = []
    
    try:
        import PySide6
    except ImportError:
        missing_deps.append("PySide6")
    
    if missing_deps:
        error_msg = f"以下のライブラリが見つかりません:\n{', '.join(missing_deps)}\n\n"
        error_msg += "インストール方法:\n"
        for dep in missing_deps:
            error_msg += f"pip install {dep}\n"
        
        print(error_msg)
        return False
    
    return True


def setup_application():
    """アプリケーションの初期設定"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    
    # Qt6では高DPI対応が自動的に有効
    
    # アプリケーション作成
    app = QApplication(sys.argv)
    
    # アプリケーション情報設定
    app.setApplicationName("Dataflux")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Dataflux")
    app.setApplicationDisplayName("🌊 Dataflux v2.0")
    
    # アイコン設定
    icon_path = project_root / "icon_dataflux.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        # フォールバックアイコン
        fallback_icon = project_root / "assets" / "icon.png"
        if fallback_icon.exists():
            app.setWindowIcon(QIcon(str(fallback_icon)))
    
    return app


def create_directories():
    """必要なディレクトリの作成"""
    directories = [
        project_root / "logs",
        project_root / "exports",
        project_root / "temp",
        project_root / "assets"
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True)


def main():
    """メイン関数"""
    print("🚀 Dataflux v2.0 - PySide6版")
    print("=" * 50)
    
    # 依存関係チェック
    if not check_dependencies():
        input("Enterキーで終了...")
        sys.exit(1)
    
    try:
        # ディレクトリ作成
        create_directories()
        
        # アプリケーション設定
        app = setup_application()

        from ui_qt.launcher import DataSortingBoxLauncher
        
        # メインランチャー起動
        print("📦 ランチャーを起動中...")
        launcher = DataSortingBoxLauncher()
        launcher.show()
        
        print("✅ ランチャーが正常に起動しました")
        print("テーマ切替、フォルダ解析機能をお試しください")
        print()
        print("利用可能な機能:")
        print("• 📊 マルチメディアファイル解析 (Audio/Video/Image/Document/3D)")
        print("• 🎵 音声ファイル専用解析")
        print("• 🎬 動画ファイル専用解析")
        print("• 🖼️ 画像ファイル専用解析")
        print("• 📄 文書ファイル専用解析")
        print("• 🎮 3Dモデル専用解析")
        print()
        
        # アプリケーション実行
        exit_code = app.exec()
        
        print("👋 アプリケーションが終了しました")
        return exit_code
        
    except Exception as e:
        error_msg = f"アプリケーション起動エラー:\n{str(e)}"
        print(f"❌ {error_msg}")
        
        # GUI環境が利用可能な場合はダイアログを表示
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("起動エラー")
            msg_box.setText("アプリケーションの起動に失敗しました")
            msg_box.setDetailedText(str(e))
            msg_box.exec()
        except:
            pass
        
        return 1


def test_core_scanner():
    """コアスキャナー機能のテスト"""
    print("\n🧪 コアスキャナー機能テスト")
    print("-" * 30)
    
    try:
        from core.scanner import FileScanner
        
        # カレントディレクトリをテスト
        test_path = Path(".")
        print(f"テスト対象: {test_path.absolute()}")
        
        results = FileScanner.scan_directory(test_path)
        
        print("結果:")
        for media_type, data in results.items():
            print(f"  {media_type}: {data['count']}ファイル, {FileScanner.get_human_size(data['size'])}")
        
        print("✅ スキャナーテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ スキャナーテストエラー: {e}")
        return False


if __name__ == "__main__":
    # コマンドライン引数の処理
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # テストモード
            if test_core_scanner():
                print("\n✅ 全テスト完了")
                sys.exit(0)
            else:
                print("\n❌ テスト失敗")
                sys.exit(1)
        
        elif sys.argv[1] == "--version":
            print("Dataflux v2.0 (PySide6版)")
            sys.exit(0)
        
        elif sys.argv[1] == "--help":
            print("Dataflux v2.0 - 使用方法:")
            print("  python main.py        : ランチャーを起動")
            print("  python main.py --test : コアモジュールのテスト")
            print("  python main.py --version : バージョン表示")
            print("  python main.py --help : このヘルプを表示")
            sys.exit(0)
    
    # 通常起動
    sys.exit(main())
