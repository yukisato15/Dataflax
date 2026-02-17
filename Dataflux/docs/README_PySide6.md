# Dataflux v2.0 - PySide6版

## 🎉 PySide6 MVP実装完了！

新しいPySide6ベースのData Sorting Boxが完成しました。モダンなGUIフレームワークでより高速で美しいインターフェースを提供します。

## 📁 プロジェクト構造

```
Dataflux/
├── core/                    # コアロジック（UI非依存）
│   ├── __init__.py
│   ├── scanner.py          # ファイル走査エンジン
│   ├── processor.py        # Sort/Flatten処理
│   └── rules.py           # ルールエンジン
├── ui_qt/                  # PySide6 GUI
│   ├── __init__.py
│   ├── launcher.py         # メインランチャー
│   └── analyzer.py         # フォルダ解析ツール
├── themes/
│   └── pro.qss            # プロ（ダーク）テーマ
└── main.py                # エントリーポイント
```

## 🚀 セットアップと実行

### 1. 依存関係のインストール

```bash
# 仮想環境をアクティベート
source .venv312/bin/activate

# PySide6をインストール
pip install PySide6
```

### 2. アプリケーションの起動

```bash
# メインランチャーを起動
python main.py

# コアモジュールのテスト
python main.py --test

# バージョン確認
python main.py --version

# ヘルプ表示
python main.py --help
```

## ✨ 実装済み機能

### 🔍 フォルダ解析ツール（新機能・PySide6版）

- **ドラッグ&ドロップ対応**: フォルダを直接UIにドラッグして解析開始
- **複数フォルダ対応**: 複数のフォルダを同時に解析可能
- **非同期処理**: UIをブロックしない高速解析
- **詳細統計表示**: 媒体別・拡張子別の詳細情報をツリー表示
- **CSV出力**: 解析結果をCSVファイルに出力
- **リアルタイムプログレス**: 処理状況をリアルタイム表示

### 📦 メインランチャー（PySide6版）

- **統合UI**: 全ツールを一箇所から起動
- **テーマ切替**: Pro（ダーク）テーマ対応
- **既存ツール連携**: Tkinter版ツールも起動可能
- **美しいカードUI**: モダンなカードベースのレイアウト

### 🎨 テーマシステム

- **プロテーマ**: Visual Studio Code風のダークテーマ
- **QSSスタイリング**: 細かい部分まで統一されたデザイン
- **高DPI対応**: 高解像度ディスプレイに対応

## 🧪 機能テスト確認済み

- ✅ コアスキャナー機能: 6704ファイル, 1.2GB の解析完了
- ✅ PySide6ランチャー起動
- ✅ Analyzerウィンドウ作成
- ✅ ドロップエリア初期化
- ✅ 結果ツリー初期化  
- ✅ テーマ適用成功
- ✅ 非同期スレッド処理

## 📊 対応媒体タイプ

- **video**: .mp4, .mov, .m4v, .avi, .mkv, .webm, .mts, .flv, .wmv, .mxf
- **audio**: .wav, .aiff, .aif, .mp3, .flac, .m4a, .aac, .ogg, .wma, .opus  
- **image**: .jpg, .jpeg, .png, .gif, .tif, .tiff, .bmp, .heic, .webp, .svg, .raw, .dng, .cr2, .nef
- **document**: .pdf, .doc, .docx, .ppt, .pptx, .xls, .xlsx, .txt, .md, .rtf, .csv, .odt
- **3d**: .glb, .gltf, .fbx, .obj, .stl, .ply, .usdz, .dae, .3ds, .blend
- **other**: その他すべてのファイル

## 🔧 使用方法

### フォルダ解析の手順

1. `python main.py` でランチャーを起動
2. "🔍 フォルダ解析・統計 (PySide6)" をクリック
3. 解析したいフォルダをドラッグ&ドロップ
4. "🔍 解析実行" ボタンをクリック
5. 結果をツリーで確認
6. 必要に応じて "💾 CSV出力" で結果保存

### 既存ツール連携

- 🎵 Audio UI (Tkinter版) 起動
- 📊 解析ツール (Tkinter版) 起動  
- 🚀 従来ランチャー (Tkinter版) 起動

## 🏗️ 今後の拡張予定

- **Dreampop テーマ**: カラフルなテーマの追加
- **Sort/Flatten機能**: Qt版での実装
- **ルールエンジン**: 高度なファイル処理ルール
- **設定画面**: より詳細な設定UI
- **バッチ処理**: 複数の処理を組み合わせた自動処理

## 🐛 既知の制限

- 現在はPro（ダーク）テーマのみ実装
- Sort/Flatten機能はコアモジュールのみ（UI未実装）
- CSV出力で大量ファイル時のメモリ使用量

## 💡 開発者向け

### アーキテクチャ

- **UI非依存設計**: `core/` モジュールは完全にUI非依存
- **非同期処理**: QThreadを使用したバックグラウンド処理
- **シグナル/スロット**: Qt標準のイベント機能を活用
- **テーマ分離**: QSSファイルでのスタイル管理

### カスタマイズポイント

- `themes/pro.qss`: テーマのカスタマイズ
- `core/scanner.py`: ファイル走査ロジック
- `ui_qt/analyzer.py`: Analyzer UIの機能拡張

---

🎉 **PySide6版 Dataflux MVP完成！**
用途に応じて統合解析と専門解析を選択できます。
