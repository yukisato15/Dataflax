# Binary Dependencies

この `bin/` ディレクトリには実行に必要なバイナリファイルを配置します。

## ffprobe

動画ファイル解析に必要な ffprobe バイナリを配置してください：

### macOS/Linux
```bash
# ffprobe バイナリを bin/ にコピー
cp /path/to/ffprobe bin/ffprobe
chmod +x bin/ffprobe
```

### Windows
```cmd
# ffprobe.exe を bin\ にコピー
copy /path/to/ffprobe.exe bin\ffprobe.exe
```

## ライセンス注意

ffprobe は FFmpeg プロジェクトの一部です。配布時は FFmpeg のライセンス（LGPL v2.1+）に従ってください：

- ソースコード開示義務（LGPL）
- ライセンス文書の同梱
- 商用利用時の注意事項

詳細は https://ffmpeg.org/legal.html を参照してください。

## 入手方法

### macOS
```bash
# Homebrew経由
brew install ffmpeg
# バイナリは /opt/homebrew/bin/ffprobe にあります

# 公式サイトから
# https://evermeet.cx/ffmpeg/ からスタティックビルドをダウンロード
```

### Windows  
```cmd
# 公式サイトから
# https://www.gyan.dev/ffmpeg/builds/ からビルドをダウンロード
# bin\ffprobe.exe を抽出
```

### Linux
```bash
# パッケージマネージャー
sudo apt install ffmpeg     # Ubuntu/Debian
sudo yum install ffmpeg     # CentOS/RHEL
# バイナリは /usr/bin/ffprobe にあります
```