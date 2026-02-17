# インストール手順

## 必要な依存関係

### 基本依存関係
```bash
pip install PySide6 mutagen tkinterdnd2
```

### 文書解析機能の依存関係
```bash
pip install PyPDF2 python-docx chardet
```

### オプションの拡張機能
```bash
pip install openpyxl lxml
```

## 一括インストール

### requirements.txtを使用
```bash
pip install -r requirements.txt
```

### 手動一括インストール
```bash
pip install PySide6 mutagen tkinterdnd2 PyPDF2 python-docx chardet
```

## 仮想環境での設定

### 仮想環境を作成・有効化
```bash
python -m venv .venv312
source .venv312/bin/activate  # macOS/Linux
# または
.venv312\Scripts\activate     # Windows
```

### 依存関係をインストール
```bash
pip install -r requirements.txt
```

## 各ライブラリの役割

| ライブラリ | 用途 | 必須/オプション |
|-----------|------|---------------|
| PySide6 | GUI フレームワーク | 必須 |
| mutagen | 音声ファイルメタデータ解析 | 必須 |
| tkinterdnd2 | ドラッグ&ドロップ機能 | 必須 |
| PyPDF2 | PDF文書の詳細解析 | 推奨 |
| python-docx | Word文書の詳細解析 | 推奨 |
| chardet | 文字エンコーディング検出 | 推奨 |
| openpyxl | Excel文書の高度な解析 | オプション |
| lxml | XML処理の高速化 | オプション |

## トラブルシューティング

### よくあるエラー

#### "No module named 'PyPDF2'"
```bash
pip install PyPDF2
```

#### "No module named 'docx'"
```bash
pip install python-docx
```

#### GUI が起動しない
PySide6が正しくインストールされているか確認：
```bash
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

### ライブラリの確認
アプリケーション内で「ライブラリ状況」ボタンをクリックすると、現在の依存関係の状況を確認できます。

## 起動方法

### ランチャーから起動
```bash
python ui_qt/launcher.py
```

### 個別ツール起動
```bash
# 文書解析ツール
python ui_qt/document_analyzer.py

# 音声解析ツール
python ui_qt/audio_analyzer.py

# 動画解析ツール  
python ui_qt/video_analyzer.py

# 画像解析ツール
python ui_qt/image_analyzer.py
```