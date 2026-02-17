# Dataflux ビルド手順書

ffprobe同梱版の作成と配布用ZIPパッケージ生成手順

## 前提条件

### 必要なソフトウェア
- Python 3.12+ 
- PySide6
- PyInstaller
- ffprobe バイナリ

### 依存関係インストール
```bash
# 仮想環境がアクティブな状態で
pip install pyinstaller
```

## 1. ffprobe バイナリの配置

### macOS
```bash
# Homebrewからffprobeを取得
brew install ffmpeg

# バイナリをプロジェクトにコピー  
cp /opt/homebrew/bin/ffprobe bin/ffprobe
chmod +x bin/ffprobe
```

### Windows
```cmd
# 公式サイトからFFmpegをダウンロード
# https://www.gyan.dev/ffmpeg/builds/

# ffprobe.exe を bin\ にコピー
copy "C:\path\to\ffmpeg\bin\ffprobe.exe" bin\ffprobe.exe
```

### Linux
```bash
# パッケージマネージャーからインストール
sudo apt install ffmpeg  # Ubuntu/Debian
# または
sudo yum install ffmpeg  # CentOS/RHEL

# バイナリをコピー
cp /usr/bin/ffprobe bin/ffprobe
chmod +x bin/ffprobe
```

## 2. アイコンファイルの準備

```bash
# プラットフォーム用アイコンを生成
python scripts/create_icons.py
```

これにより以下が生成されます：
- `assets/icons/dataflux.ico` (Windows用)
- `assets/icons/dataflux.icns` (macOS用) 
- `assets/icons/dataflux.png` (Linux用)

## 3. ビルド実行

### 自動ビルドスクリプト使用（推奨）
```bash
python build_dataflux.py
```

### 手動ビルド

#### macOS
```bash
pyinstaller --noconfirm --windowed --name "Dataflux" \
  --icon assets/icons/dataflux.icns \
  --add-data "themes:themes" \
  --add-data "ui_qt:ui_qt" \
  --add-data "core:core" \
  --add-data "utils:utils" \
  --add-binary "bin/ffprobe:bin" \
  main.py
```

#### Windows
```cmd
pyinstaller --noconfirm --windowed --name "Dataflux" ^
  --icon assets/icons/dataflux.ico ^
  --add-data "themes;themes" ^
  --add-data "ui_qt;ui_qt" ^
  --add-data "core;core" ^  
  --add-data "utils;utils" ^
  --add-binary "bin\ffprobe.exe;bin" ^
  main.py
```

#### Linux
```bash
pyinstaller --noconfirm --windowed --name "Dataflux" \
  --icon assets/icons/dataflux.png \
  --add-data "themes:themes" \
  --add-data "ui_qt:ui_qt" \
  --add-data "core:core" \
  --add-data "utils:utils" \
  --add-binary "bin/ffprobe:bin" \
  main.py
```

## 4. 配布パッケージ作成

### macOS
```bash
cd dist
zip -r Dataflux-macOS.zip Dataflux.app README.md FFMPEG_LICENSE.txt
```

### Windows
```powershell
cd dist
Compress-Archive -Path "Dataflux", "README.md", "FFMPEG_LICENSE.txt" -DestinationPath "Dataflux-Windows.zip"
```

### Linux
```bash
cd dist  
zip -r Dataflux-Linux.zip Dataflux README.md FFMPEG_LICENSE.txt
```

## 5. テスト手順

### 基本動作確認
1. 生成されたアプリケーションを起動
2. 各アナライザー（Audio, Video, Image等）が起動することを確認
3. UIが正しく表示されることを確認

### ffprobe統合確認
1. Video Analyzerを起動  
2. 動画ファイルを解析
3. ffprobeエラーが発生しないことを確認
4. 詳細なメタデータが取得できることを確認

### 配布テスト
1. ZIPファイルを別の環境に展開
2. ffprobeが正しく同梱されていることを確認
3. クリーンな環境での動作確認

## トラブルシューティング

### ffprobe not found エラー
- `bin/ffprobe` の存在を確認
- 実行権限を確認（Unix系：`chmod +x bin/ffprobe`）
- PyInstallerの `--add-binary` オプションを確認

### アイコンが表示されない
- アイコンファイルの存在を確認
- ファイル形式が正しいことを確認（.ico/.icns/.png）
- PyInstallerの `--icon` オプションを確認

### 起動時エラー
- 依存関係が正しく同梱されているか確認
- `--add-data` オプションでui_qt, core, utilsが含まれているか確認
- コンソールからの起動でエラー詳細を確認

## ライセンス注意事項

FFmpeg (ffprobe) は LGPL v2.1+ ライセンスです：
- ソースコード開示義務
- ライセンス文書の同梱必須
- 配布時はFFMPEG_LICENSE.txtを含める

詳細は [FFmpeg Legal](https://ffmpeg.org/legal.html) を参照してください。
