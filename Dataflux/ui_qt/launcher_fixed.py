#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
確実に動作するランチャー
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SimpleToolCard(QPushButton):
    """シンプルで確実なツールカード"""
    
    def __init__(self, name, description, launch_func):
        super().__init__()
        self.name = name
        self.description = description
        self.launch_func = launch_func
        
        self.setFixedSize(300, 120)
        self.setText(f"{name}\n{description}\n\n[Click to Launch]")
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(24, 27, 57, 0.95), stop: 1 rgba(76, 100, 115, 0.85));
                border: 2px solid #8C6E54;
                border-radius: 12px;
                color: white;
                font-size: 12px;
                text-align: left;
                padding: 15px;
            }
            QPushButton:hover {
                border: 3px solid #8C6E54;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(24, 27, 57, 1.0), stop: 1 rgba(76, 100, 115, 0.9));
            }
            QPushButton:pressed {
                background: rgba(140, 110, 84, 0.3);
            }
        """)
        
        self.clicked.connect(self.launch_tool)
    
    def launch_tool(self):
        """ツール起動"""
        try:
            self.launch_func()
            print(f"✅ {self.name} 起動成功")
        except Exception as e:
            print(f"❌ {self.name} 起動エラー: {e}")
            QMessageBox.critical(None, "起動エラー", f"{self.name} の起動に失敗しました:\n{e}")

class DataSortingBoxLauncher(QMainWindow):
    """メインランチャー"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dataflux v2.0 - マルチメディア解析スイート")
        self.setFixedSize(1000, 800)
        self.center_window()
        
        # ウィンドウ参照を保持
        self.launched_windows = []
        
        self.init_ui()
        self.apply_theme()
    
    def center_window(self):
        """ウィンドウを画面中央に配置"""
        screen = QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        window_rect = self.frameGeometry()
        center_point = screen_rect.center()
        window_rect.moveCenter(center_point)
        self.move(window_rect.topLeft())
    
    def init_ui(self):
        """UI初期化"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # タイトル
        title = QLabel("Dataflux")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #F2F3F5; margin: 20px;")
        layout.addWidget(title)
        
        # 説明
        desc = QLabel("高度な解析エンジンでファイル構造を完全把握\nマルチメディア統合解析から専門特化ツールまで、あらゆるニーズに対応")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 14px; color: #A9B5BC; margin-bottom: 20px;")
        layout.addWidget(desc)
        
        # Pro Tools
        pro_label = QLabel("Pro Tools")
        pro_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #8C6E54; margin: 15px 5px;")
        layout.addWidget(pro_label)
        
        pro_frame = QFrame()
        pro_frame.setStyleSheet("""
            QFrame {
                background: rgba(140, 110, 84, 0.08);
                border: 2px solid rgba(140, 110, 84, 0.3);
                border-radius: 16px;
                padding: 15px;
            }
        """)
        pro_layout = QVBoxLayout(pro_frame)
        pro_layout.setSpacing(15)
        
        # Multimedia（特別扱い）
        multimedia_card = SimpleToolCard("Multimedia", "全メディア統合解析ツール", self.launch_multimedia)
        pro_layout.addWidget(multimedia_card)
        
        # 他のPro Tools
        pro_grid = QGridLayout()
        pro_grid.setSpacing(15)
        
        pro_tools = [
            ("Audio", "音声ファイル専門解析", self.launch_audio),
            ("Video", "動画ファイル専門解析", self.launch_video),
            ("Image", "画像ファイル専門解析", self.launch_image),
            ("Document", "文書ファイル専門解析", self.launch_document),
            ("3D Model", "3Dモデル専門解析", self.launch_3d)
        ]
        
        for i, (name, desc, func) in enumerate(pro_tools):
            card = SimpleToolCard(name, desc, func)
            card.setFixedSize(280, 100)
            row, col = i // 3, i % 3
            pro_grid.addWidget(card, row, col)
        
        pro_layout.addLayout(pro_grid)
        layout.addWidget(pro_frame)
        
        # Basic Tools
        basic_label = QLabel("Basic Tools")
        basic_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #8C6E54; margin: 15px 5px;")
        layout.addWidget(basic_label)
        
        basic_frame = QFrame()
        basic_frame.setStyleSheet("""
            QFrame {
                background: rgba(140, 110, 84, 0.05);
                border: 1px solid rgba(140, 110, 84, 0.2);
                border-radius: 12px;
                padding: 15px;
            }
        """)
        basic_layout = QVBoxLayout(basic_frame)
        
        analyzer_card = SimpleToolCard("Folder Analysis", "フォルダ構造統計解析", self.launch_analyzer)
        basic_layout.addWidget(analyzer_card)
        
        layout.addWidget(basic_frame)
        layout.addStretch()
    
    def apply_theme(self):
        """テーマ適用"""
        self.setStyleSheet("""
            QMainWindow {
                background: #455765;
                color: #D5DADE;
            }
        """)
    
    # 各ツール起動メソッド - 確実に動作
    def launch_multimedia(self):
        try:
            import ui_qt.multimedia_analyzer
            window = ui_qt.multimedia_analyzer.MultimediaAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Multimedia起動失敗: {e}")
    
    def launch_audio(self):
        try:
            import ui_qt.audio_analyzer
            window = ui_qt.audio_analyzer.AudioAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Audio起動失敗: {e}")
    
    def launch_video(self):
        try:
            import ui_qt.video_analyzer
            window = ui_qt.video_analyzer.VideoAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Video起動失敗: {e}")
    
    def launch_image(self):
        try:
            import ui_qt.image_analyzer
            window = ui_qt.image_analyzer.ImageAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Image起動失敗: {e}")
    
    def launch_document(self):
        try:
            import ui_qt.document_analyzer
            window = ui_qt.document_analyzer.DocumentAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Document起動失敗: {e}")
    
    def launch_3d(self):
        try:
            import ui_qt.threed_analyzer
            window = ui_qt.threed_analyzer.ThreeDAnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"3D起動失敗: {e}")
    
    def launch_analyzer(self):
        try:
            import ui_qt.analyzer
            window = ui_qt.analyzer.AnalyzerWindow()
            self.launched_windows.append(window)
            window.show()
        except Exception as e:
            raise Exception(f"Analyzer起動失敗: {e}")

def main():
    """メイン関数"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    app.setApplicationName("Dataflux")
    app.setApplicationVersion("2.0")
    
    launcher = DataSortingBoxLauncher()
    launcher.show()
    
    return app.exec() if not QApplication.instance().property('running') else None

if __name__ == "__main__":
    main()
