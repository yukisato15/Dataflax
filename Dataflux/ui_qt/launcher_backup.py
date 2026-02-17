#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6-based main launcher for Dataflux - Modern card-based design
"""

import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pathlib import Path


class DataSortingBoxLauncher(QMainWindow):
    """メインランチャーウィンドウ - モダンカードベースデザイン"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dataflux v2.0 - マルチメディア解析スイート")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 700)
        
        # Apply modern window styling
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        
        # Center the window
        self.center_window()
        
        self.tools = {
            "multimedia": {
                "name": "Multimedia", 
                "icon": "", 
                "implemented": True, 
                "description": "全メディア統合解析ツール\nAudio・Video・Image・Document・3D・Archive等300+形式対応",
                "category": "ultimate",
                "priority": 1
            },
            
            "audio": {
                "name": "Audio", 
                "icon": "", 
                "implemented": True, 
                "description": "音声ファイル専門解析\nメタデータ・サンプルレート・ビットレート・時間別整理",
                "category": "specialist",
                "priority": 2
            },
            "video": {
                "name": "Video", 
                "icon": "", 
                "implemented": True, 
                "description": "動画ファイル専門解析\n解像度・FPS・コーデック・コンテナ別分析",
                "category": "specialist",
                "priority": 2
            },
            "image": {
                "name": "Image", 
                "icon": "", 
                "implemented": True, 
                "description": "画像ファイル専門解析\nEXIF・解像度・色空間・カメラ情報分析",
                "category": "specialist",
                "priority": 2
            },
            "document": {
                "name": "Document", 
                "icon": "", 
                "implemented": True, 
                "description": "文書ファイル専門解析\nPDF・Word・テキスト・メタデータ抽出",
                "category": "specialist",
                "priority": 2
            },
            "3d": {
                "name": "3D Model", 
                "icon": "", 
                "implemented": True, 
                "description": "3Dモデルファイル専門解析\nメッシュ・頂点・材質・品質評価",
                "category": "specialist",
                "priority": 2
            },
            
            "analyzer": {
                "name": "Folder Analysis", 
                "icon": "", 
                "implemented": True, 
                "description": "フォルダ構造統計解析\nファイル数・容量・形式別集計表示",
                "category": "basic",
                "priority": 3
            }
        }
        
        # PRO theme fixed (no theme switching)
        self.current_theme = "pro"
        
        self.init_ui()
        self.apply_modern_theme()
    
    def center_window(self):
        """ウィンドウを画面中央に配置"""
        screen = QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        window_rect = self.geometry()
        
        x = (screen_rect.width() - window_rect.width()) // 2
        y = (screen_rect.height() - window_rect.height()) // 2
        self.move(x, y)
    
    def init_ui(self):
        """モダンなUI要素を初期化"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ヘッダーバー
        header_bar = self.create_header_bar()
        main_layout.addWidget(header_bar)
        
        # メインコンテンツエリア
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(25)
        
        # ウェルカムセクション
        welcome = self.create_welcome_section()
        content_layout.addWidget(welcome)
        
        # ツールカード群
        tools_section = self.create_tools_section()
        content_layout.addWidget(tools_section)
        
        # フッター情報
        footer = self.create_footer()
        content_layout.addWidget(footer)
        
        content_layout.addStretch()
        
        # スクロールエリア
        scroll = QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        
        main_layout.addWidget(scroll)
    
    def create_header_bar(self):
        """モダンなヘッダーバーを作成"""
        header_widget = QWidget()
        header_widget.setFixedHeight(80)
        header_widget.setObjectName("headerBar")
        
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(30, 0, 30, 0)
        
        # タイトルセクション
        title_layout = QVBoxLayout()
        title = QLabel("Dataflux")
        title.setObjectName("titleLarge")
        subtitle = QLabel("マルチメディア解析スイート v2.0")
        subtitle.setObjectName("subtitle")
        
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # ステータス表示
        status_layout = QVBoxLayout()
        status_label = QLabel("● 準備完了")
        status_label.setObjectName("statusIndicator")
        version_label = QLabel("PySide6 | Qt6")
        version_label.setObjectName("versionInfo")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(version_label)
        layout.addLayout(status_layout)
        
        return header_widget
    
    def create_welcome_section(self):
        """ウェルカムセクションを作成"""
        section = QWidget()
        section.setObjectName("welcomeSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 20)
        
        welcome_text = QLabel("プロ用ファイル解析ツール")
        welcome_text.setObjectName("welcomeText")
        layout.addWidget(welcome_text)
        
        description = QLabel("高度な解析エンジンでファイル構造を完全把握\nマルチメディア統合解析から専門特化ツールまで、あらゆるニーズに対応")
        description.setObjectName("descriptionText")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        return section
    
    def create_tools_section(self):
        """ツールカードセクションを作成"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(20)
        
        # Ultimate Tool (Featured)
        ultimate_card = self.create_featured_tool_card("multimedia")
        layout.addWidget(ultimate_card)
        
        # Pro Tools セクション - 大きな枠で囲む
        pro_section = QFrame()
        pro_section.setObjectName("proSection")
        pro_section.setFrameStyle(QFrame.Box)
        pro_section_layout = QVBoxLayout(pro_section)
        pro_section_layout.setContentsMargins(20, 15, 20, 20)
        pro_section_layout.setSpacing(10)
        
        specialists_label = QLabel("Pro Tools")
        specialists_label.setObjectName("sectionHeader")
        pro_section_layout.addWidget(specialists_label)
        
        specialists_grid = QGridLayout()
        specialists_grid.setSpacing(15)
        specialist_tools = [tool_id for tool_id, tool in self.tools.items() if tool["category"] == "specialist"]
        
        for i, tool_id in enumerate(specialist_tools):
            card = self.create_tool_card(tool_id)
            row, col = i // 2, i % 2
            specialists_grid.addWidget(card, row, col)
        
        pro_section_layout.addLayout(specialists_grid)
        layout.addWidget(pro_section)
        
        # Basic Tools セクション - Folder Analysisを枠で囲む
        basic_section = QFrame()
        basic_section.setObjectName("basicSection")
        basic_section.setFrameStyle(QFrame.Box)
        basic_section_layout = QVBoxLayout(basic_section)
        basic_section_layout.setContentsMargins(20, 15, 20, 20)
        basic_section_layout.setSpacing(10)
        
        basic_label = QLabel("Basic Tools")
        basic_label.setObjectName("sectionHeader")  
        basic_section_layout.addWidget(basic_label)
        
        basic_tools_layout = QHBoxLayout()
        basic_tools = [tool_id for tool_id, tool in self.tools.items() if tool["category"] == "basic"]
        
        for tool_id in basic_tools:
            card = self.create_tool_card(tool_id)
            basic_tools_layout.addWidget(card)
        
        basic_tools_layout.addStretch()
        basic_section_layout.addLayout(basic_tools_layout)
        layout.addWidget(basic_section)
        
        return section
    
    def create_featured_tool_card(self, tool_id):
        """フィーチャードツールカードを作成"""
        tool = self.tools[tool_id]
        
        card = QFrame()
        card.setObjectName("featuredCard")
        card.setFrameStyle(QFrame.NoFrame)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)
        
        # アイコン削除 - タイトルのみにフォーカス
        
        # メインコンテンツ
        content_layout = QVBoxLayout()
        
        # タイトルとバッジ
        title_row = QHBoxLayout()
        title = QLabel(tool["name"])
        title.setObjectName("featuredTitle")
        title_row.addWidget(title)
        
        ultimate_badge = QLabel("PREMIUM")
        ultimate_badge.setObjectName("ultimateBadge")
        title_row.addWidget(ultimate_badge)
        title_row.addStretch()
        
        content_layout.addLayout(title_row)
        
        # 説明
        description = QLabel(tool["description"])
        description.setObjectName("featuredDescription")
        description.setWordWrap(True)
        content_layout.addWidget(description)
        
        layout.addLayout(content_layout)
        
        button_layout = QVBoxLayout()
        launch_button = QPushButton("Start")
        launch_button.setObjectName("featuredLaunchButton")
        launch_button.clicked.connect(lambda: self.launch_tool(tool_id))
        button_layout.addWidget(launch_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return card
    
    def create_tool_card(self, tool_id):
        """ツールカードを作成"""
        tool = self.tools[tool_id]
        
        card = QFrame()
        card.setObjectName("toolCard")
        card.setFrameStyle(QFrame.NoFrame)
        card.setFixedSize(280, 160)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(8)
        
        # ヘッダー（タイトルのみ）
        header_layout = QHBoxLayout()
        title = QLabel(tool["name"])
        title.setObjectName("cardTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 説明
        description = QLabel(tool["description"].split('\n')[0])  # First line only
        description.setObjectName("cardDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addStretch()
        
        # スタートボタン - シンプルで確実
        launch_button = QPushButton("Start")
        launch_button.setObjectName("cardLaunchButton")
        launch_button.clicked.connect(lambda: self.launch_tool(tool_id))
        layout.addWidget(launch_button)
        
        return card
    
    def create_footer(self):
        """フッター情報を作成"""
        footer = QWidget()
        footer.setObjectName("footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 15, 20, 15)
        
        info_text = QLabel("PySide6 (Qt6) で構築 • 300種類以上のファイル形式対応 • クロスプラットフォーム対応")
        info_text.setObjectName("footerText")
        layout.addWidget(info_text)
        
        layout.addStretch()
        
        github_label = QLabel("オープンソースプロジェクト")
        github_label.setObjectName("footerLink")
        layout.addWidget(github_label)
        
        return footer
    
    def apply_modern_theme(self):
        """日本の伝統色を使ったシックなテーマを適用"""
        stylesheet = """
        /* Japanese Traditional Color Variables */
        /* 
        --bg: #455765 (鉄御納戸 - 画面背景)
        --panel: #181B39 (勝色 - セクション／カードベース) 
        --primary: #003A47 (藍鉄色 - 強調テキスト、主要ボタン)
        --primary-hover: #002834 (濃藍 - 主要ボタン hover)
        --primary-press: #22313A (藍墨茶 - 主要ボタン press)
        --accent: #3A8FB7 (千草色 - 見出しアクセント)
        --accent-weak: #6FAFC6 (退色千草 - アクセント薄版)
        --surface: #4C6473 (御召御納戸 - サブカード)
        --divider: #9AA5AE (銀鼠 - 罫線)
        --text-strong: #F2F3F5 (白鼠 - タイトル)
        --text: #D5DADE (薄墨 - 標準本文)
        --text-mute: #A9B5BC (青鈍 - 補助テキスト)
        --success: #007B5C (常磐色 - ステータス)
        */
        
        /* Main Window */
        QMainWindow {
            background: #455765;
            color: #D5DADE;
        }
        
        /* Header Bar */
        #headerBar {
            background: #181B39;
            border-bottom: 1px solid rgba(154, 165, 174, 0.3);
        }
        
        #titleLarge {
            font-size: 24px;
            font-weight: bold;
            color: #F2F3F5;
        }
        
        #subtitle {
            font-size: 12px;
            color: #A9B5BC;
        }
        
        #statusIndicator {
            font-size: 14px;
            color: #007B5C;
            font-weight: bold;
        }
        
        #versionInfo {
            font-size: 11px;
            color: #A9B5BC;
        }
        
        /* Welcome Section */
        #welcomeSection {
            background: rgba(24, 27, 57, 0.8);
            border: 1px solid rgba(154, 165, 174, 0.2);
            border-radius: 12px;
        }
        
        #welcomeText {
            font-size: 20px;
            font-weight: bold;
            color: #F2F3F5;
        }
        
        #descriptionText {
            font-size: 12px;
            color: #A9B5BC;
            line-height: 1.4;
        }
        
        /* Section Headers - 茶アクセント */
        #sectionHeader {
            font-size: 18px;
            font-weight: bold;
            color: #8C6E54;
            margin: 5px 0;
        }
        
        /* Pro Section - 大きな枠 */
        QFrame#proSection {
            background: rgba(140, 110, 84, 0.08);
            border: 2px solid rgba(140, 110, 84, 0.3);
            border-radius: 16px;
        }
        
        /* Basic Section - シンプルな枠 */
        QFrame#basicSection {
            background: rgba(140, 110, 84, 0.05);
            border: 1px solid rgba(140, 110, 84, 0.2);
            border-radius: 12px;
        }
        
        /* Featured Card - 藍鉄→千草グラデーション */
        #featuredCard {
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 rgba(0, 58, 71, 0.92), stop: 1 rgba(58, 143, 183, 0.92));
            border: 1px solid #003A47;
            border-radius: 16px;
            min-height: 120px;
        }
        
        #featuredTitle {
            font-size: 24px;
            font-weight: bold;
            color: #F2F3F5;
        }
        
        #ultimateBadge {
            background: #ffffff;
            color: #3A8FB7;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }
        
        #featuredDescription {
            font-size: 14px;
            color: #F2F3F5;
            line-height: 1.4;
        }
        
        #featuredLaunchButton {
            background: #ffffff;
            color: #003A47;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: bold;
            min-width: 120px;
        }
        
        #featuredLaunchButton:hover {
            background: #F2F3F5;
        }
        
        #featuredLaunchButton:pressed {
            background: #D5DADE;
        }
        
        /* Tool Cards - グラデーションカード */
        QFrame#toolCard {
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 rgba(24, 27, 57, 0.95), stop: 1 rgba(76, 100, 115, 0.85));
            border: 0.5px solid rgba(140, 110, 84, 0.4);
            border-radius: 12px;
        }
        
        QFrame#toolCard:hover {
            border: 1px solid #8C6E54;
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 rgba(24, 27, 57, 1.0), stop: 1 rgba(76, 100, 115, 0.9));
        }
        
        #cardTitle {
            font-size: 16px;
            font-weight: bold;
            color: #F2F3F5;
        }
        
        #cardDescription {
            font-size: 12px;
            color: #D5DADE;
            line-height: 1.3;
        }
        
        #cardLaunchButton {
            background: #8C6E54;
            color: #F2F3F5;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: bold;
        }
        
        #cardLaunchButton:disabled {
            background: rgba(140, 110, 84, 0.6);
            color: rgba(242, 243, 245, 0.7);
        }
        
        /* Footer */
        #footer {
            background: rgba(24, 27, 57, 0.8);
            border-top: 1px solid rgba(154, 165, 174, 0.2);
        }
        
        #footerText {
            font-size: 11px;
            color: #A9B5BC;
        }
        
        #footerLink {
            font-size: 11px;
            color: #3A8FB7;
        }
        
        /* Scroll Area */
        QScrollArea {
            background: transparent;
            border: none;
        }
        
        QScrollBar:vertical {
            background: rgba(24, 27, 57, 0.3);
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background: #3A8FB7;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background: #6FAFC6;
        }
        """
        
        self.setStyleSheet(stylesheet)
    
    def launch_tool(self, tool_id: str):
        """指定されたツールを起動"""
        tool = self.tools.get(tool_id)
        if not tool or not tool["implemented"]:
            QMessageBox.warning(self, "未実装", f"{tool_id} はまだ実装されていません")
            return
        
        try:
            # Store reference to keep window alive
            if not hasattr(self, '_launched_windows'):
                self._launched_windows = []
            
            # 動的インポートで確実に動作させる
            if tool_id == "analyzer":
                import ui_qt.analyzer
                window = ui_qt.analyzer.AnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "audio":
                import ui_qt.audio_analyzer
                window = ui_qt.audio_analyzer.AudioAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "video":
                import ui_qt.video_analyzer
                window = ui_qt.video_analyzer.VideoAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "image":
                import ui_qt.image_analyzer
                window = ui_qt.image_analyzer.ImageAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "document":
                import ui_qt.document_analyzer
                window = ui_qt.document_analyzer.DocumentAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "3d":
                import ui_qt.threed_analyzer
                window = ui_qt.threed_analyzer.ThreeDAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
            elif tool_id == "multimedia":
                import ui_qt.multimedia_analyzer
                window = ui_qt.multimedia_analyzer.MultimediaAnalyzerWindow()
                self._launched_windows.append(window)
                window.show()
                
        except ImportError as e:
            QMessageBox.critical(self, "インポートエラー", f"モジュールの読み込みに失敗しました:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "起動エラー", f"ツールの起動に失敗しました:\n{e}\n\nデバッグ情報: {type(e).__name__}")


def main():
    """Main entry point"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Qt6 has automatic high DPI support
    
    launcher = DataSortingBoxLauncher()
    launcher.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
