# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive desktop multimedia file analysis and processing application built with Python and PySide6 (Qt6). The project consists of specialized analyzers for different media types:

- **ui_qt/multimedia_analyzer.py** - Ultimate file analyzer supporting all media types (Audio/Video/Image/Document/3D)
- **ui_qt/audio_analyzer.py** - Specialized audio file processor with metadata analysis
- **ui_qt/video_analyzer.py** - Video file analyzer with ffprobe integration
- **ui_qt/image_analyzer.py** - Image file analyzer with EXIF data extraction
- **ui_qt/document_analyzer.py** - Document analyzer for PDF/Word/Text files
- **ui_qt/threed_analyzer.py** - 3D model analyzer with mesh analysis

## Development Environment

### Setup Commands
```bash
# Activate virtual environment
source .venv312/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run main application
python main.py
```

### Key Dependencies
- **PySide6** - Qt6-based GUI framework for cross-platform desktop applications
- **mutagen** - Audio metadata processing library for comprehensive audio format support
- **ffprobe/ffmpeg** - Video analysis tool for detailed multimedia metadata extraction
- **Pillow** - Image processing library with EXIF support for image analysis
- **PyPDF2/python-docx** - Document analysis libraries for PDF and Word documents
- **trimesh/numpy** - 3D model analysis and computational geometry
- Built on Python 3.12+ with modern Qt6 framework

## Architecture

### Application Structure
- **Multi-analyzer system**: Specialized analyzers for each media type with unified UI framework
- **Qt-based interface**: Modern PySide6 implementation with dark theme support
- **Signal/slot architecture**: Qt's event-driven system with thread-safe communication
- **Modular design**: Independent analyzer modules with shared UI components

### Core Components
- **Multimedia Analysis Engines**: Comprehensive file analysis supporting 300+ formats across all major categories
- **Independent Analysis Libraries**: Direct integration with mutagen, ffprobe, Pillow, PyPDF2, trimesh for detailed metadata
- **Qt Tree-based Interface**: QTreeWidget with multi-selection, drag-and-drop, and real-time filtering
- **Cross-platform Design**: Qt6 ensures consistent experience across Windows, macOS, and Linux

## Processing Modes

### Flattener Mode
- **Purpose**: Consolidate audio files from subdirectories to parent directory
- **Format Selection**: Dynamic checkboxes generated from analysis results
- **Duplicate Handling**: Automatic numbering with `_01`, `_02` suffixes
- **Non-audio Files**: Option to trash or isolate to separate folder

### Sorter Mode  
- **Criteria Options**: Extension, sample rate, channel count, duration buckets, modification date
- **Duration Buckets**: `<5s`, `5-15s`, `15-60s`, `1-5min`, `≥5min`
- **Sample Rate**: Preserves exact values (e.g., `sr_44100`, `sr_48000`)
- **Channel Mapping**: `mono`, `stereo`, or `ch_N` for multi-channel

## Audio Processing Features

### Metadata Extraction
- **WAV/AIFF**: Direct analysis using wave/aifc standard libraries
- **MP3/FLAC/M4A**: mutagen library for comprehensive metadata
- **Extracted Data**: Sample rate, channel count, duration, file modification time
- **Error Handling**: Graceful fallback for corrupted or unsupported files

### File Operation Safety
- **Dry-run Mode**: Preview all operations without making changes
- **Duplicate Resolution**: Automatic unique naming with numbered suffixes
- **Trash Integration**: macOS Finder integration via AppleScript
- **Empty Directory Cleanup**: Automatic removal with junk file deletion (.DS_Store, ._ files)

## GUI Features

### Tree Interface
- **Display Modes**: 
  - `folders_only`: Show directory structure only
  - `one_above_leaf`: Show directories one level above files
  - `with_files`: Full tree with individual files
- **Multi-selection**: Extended selection for batch processing
- **Drag & Drop**: Direct folder addition to input list
- **Real-time Analysis**: Extension summary and audio metadata distribution

### Analysis Tools
- **Extension Summary**: File count and size breakdown by format
- **Audio Analysis**: Distribution charts for sample rates, channels, duration, dates
- **Dynamic UI**: Format checkboxes update based on discovered file types
- **Progress Tracking**: Real-time progress bars and detailed logging

## Code Architecture Patterns

### Thread Safety
- **Background Processing**: Non-blocking file operations in separate threads
- **Queue Communication**: Thread-safe logging via queue.Queue
- **GUI Updates**: Main thread updates using tkinter.after() scheduling

### Error Handling
- **Graceful Degradation**: Continue processing on individual file errors
- **Comprehensive Logging**: Detailed operation logs with dry-run preview
- **User Feedback**: Clear error messages and operation summaries

### Platform Integration
- **macOS Optimized**: AppleScript trash integration for proper Finder behavior
- **Path Handling**: Robust pathlib usage for cross-platform compatibility
- **Hidden File Filtering**: Automatic .DS_Store and system file management

## Important Implementation Notes

### File Processing Logic
- All file operations support atomic moves with rollback capability
- ZIP deletion can be disabled automatically if ZIP format is selected for preservation
- Empty directory removal respects input folder protection
- Metadata extraction failures don't halt batch operations

### GUI Responsiveness
- Long operations run in background threads to prevent UI freezing
- Progress updates synchronized via main thread scheduling
- Log output streams in real-time during processing
- Tree view updates efficiently handle large directory structures

### Audio Format Support
- **Primary**: WAV (standard wave module)
- **Secondary**: AIFF (aifc module, deprecated in Python 3.13+)
- **Extended**: MP3, FLAC, M4A via mutagen library
- **Metadata**: Sample rate, channels, duration, modification time
- **Future-proof**: Easy to extend with additional format handlers

## AnalyzerUI（フォルダ解析）

### 概要
analyzer_ui.py は複数フォルダの内容を詳細解析し、媒体別×拡張子別で統計情報を表示するツールです。audio_ui.py から「📊 詳細解析」ボタンで起動できます。

### 主要機能

#### 解析機能
- **媒体分類**: Audio/Video/Image/Document/3D/Other の6カテゴリで自動分類
- **統計集計**: ファイル数、合計サイズ、平均サイズの算出
- **階層表示**: 媒体→拡張子の2階層ツリー表示（🎵🎬🖼️📄🗿📦アイコン付き）
- **スレッド処理**: 大容量フォルダでもUIが固まらない非同期解析

#### 表示・操作機能
- **Treeview**: 詳細な統計情報を階層表示
- **プログレスバー**: 解析進捗をリアルタイム表示
- **ファイルプレビュー**: 選択項目の最初5ファイルを詳細表示
- **エラーハンドリング**: アクセス権限エラーや大容量ファイル（1GB+）の警告

#### 出力・連携機能
- **CSV出力**: タイムスタンプ付きファイル名で統計データをエクスポート
- **ツール連携**: 選択した媒体に応じた推奨ツールの提案
- **直接起動**: audio_ui.py からワンクリックで解析開始

### 対応媒体・拡張子

#### 媒体マッピング
```python
MEDIA_MAP = {
    "video": [".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mts", ".flv", ".wmv", ".mxf"],
    "audio": [".wav", ".aiff", ".aif", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"], 
    "image": [".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".heic", ".webp", ".svg", ".raw", ".dng", ".cr2", ".nef"],
    "document": [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".md", ".rtf", ".csv", ".odt"],
    "3d": [".glb", ".gltf", ".fbx", ".obj", ".stl", ".ply", ".usdz", ".dae", ".3ds", ".blend"]
}
```

### 使用方法

#### audio_ui.pyからの起動
1. audio_ui.py でフォルダを追加
2. 「📊 詳細解析」ボタンをクリック
3. AnalyzerUI ウィンドウが開き、自動的に解析開始

#### スタンドアロン実行
```bash
python analyzer_ui.py
```

#### 基本操作
- **🔄 再解析**: パスが設定済みの場合、解析を再実行
- **🚀 ツール起動**: 選択した媒体の詳細情報と推奨ツールを表示
- **👁️ プレビュー**: 選択項目のファイル詳細を別ウィンドウで表示
- **💾 CSV保存**: 解析結果を `analysis_YYYYMMDD_HHMMSS.csv` 形式で保存
- **📂 Flatten / 🗃️ Sort**: 将来実装予定の振り分け機能

### CSV出力形式
- **ヘッダー**: 媒体, 拡張子, 件数, 合計サイズ(bytes), 合計サイズ(MB), 平均サイズ(MB), ファイルパス例
- **データ行**: 媒体→拡張子別の詳細統計
- **合計行**: 全体の統計サマリー

### フォルダ操作機能

#### Sort（振り分け）機能
- **目的**: 選択した媒体/拡張子のファイルを指定先フォルダに振り分け
- **構造**: `出力先/媒体名/拡張子名/ファイル` の階層で整理
- **操作モード**: コピー📄 / 移動📤 / シンボリックリンク🔗 から選択
- **重複処理**: `filename_01.ext`、`filename_02.ext` 形式で自動回避

#### Flatten（平坦化）機能  
- **目的**: 複雑なフォルダ構造を1階層に平坦化
- **処理**: サブフォルダ構造を無視して選択フォルダに全ファイル集約
- **重複処理**: 同名ファイルは連番で自動リネーム

#### Dry-run（テスト実行）機能
- **プレビュー**: 実際のファイル操作前に処理内容を詳細表示
- **安全性**: デフォルトでDry-runモード有効、破壊的操作を防止
- **確認**: 処理対象ファイル（最大20件）、操作モード、出力先を事前確認

### 操作制御機能

#### 実行中の制御
- **⏸️一時停止**: 長時間処理の途中で一時停止・再開可能
- **❌キャンセル**: 処理の中断と安全な終了
- **プログレス表示**: リアルタイムの処理進捗と成功/エラー件数

#### フィルタ機能
- **媒体フィルタ**: 特定媒体タイプのみ表示（Audio/Video/Image等）
- **サイズフィルタ**: MB単位での最小・最大サイズ指定
- **適用・リセット**: フィルタ条件の動的変更とTreeview更新

### 設定管理機能

#### 永続化設定
- **自動保存**: ウィンドウ終了時に `analyzer_settings.json` へ設定保存
- **復元機能**: 起動時に前回の解析パス・操作モード・フィルタ設定を復元
- **軽量モード**: 🚀大規模フォルダ用にファイルリスト保持を最小化

#### 外部アプリ連携
- **Finder連携**: macOS Finder で選択ファイルを表示（`open -R`）
- **TODO**: Adobe Audition, 他の専用アプリとの連携予定

### 実行手順例

#### 基本的な振り分け処理
1. audio_ui.py で解析対象フォルダを追加
2. 「📊 詳細解析」ボタンで AnalyzerUI を起動
3. TreeView で振り分けたい媒体/拡張子を選択
4. 操作モード（コピー/移動/リンク）を選択
5. Dry-runでプレビュー確認後、本実行

#### フィルタを使った効率的な作業
1. 🔍フィルタで「audio + 100MB以上」等の条件設定
2. 条件に合致するファイルのみTreeviewに表示
3. 一括で Flatten または Sort 実行
4. 処理完了後にフィルタリセットで全体確認

### エラーハンドリング
- **ファイル操作エラー**: 個別ファイルの失敗は処理を継続
- **権限エラー**: アクセス権限不足時の詳細エラー表示
- **ディスク容量**: 容量不足時の事前警告（TODO）
- **シンボリックリンク**: リンク作成失敗時の適切なエラー処理

### 将来の拡張予定
- **ルール設定エディタ**: サイズ・拡張子条件での自動振り分けルール
- **バッチ処理キュー**: 複数操作の順次実行とキャンセル機能  
- **キャッシュ機能**: 解析結果の保存・再利用
- **サムネイル表示**: 画像・動画のプレビュー表示
- **メタデータ解析**: 解像度、コーデック、音声品質の詳細情報
- **専用ツール連携**: video_ui.py, image_ui.py 等との統合