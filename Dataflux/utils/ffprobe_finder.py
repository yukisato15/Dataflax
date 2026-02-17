import os, sys, shutil
from pathlib import Path

def find_ffprobe() -> str | None:
    exe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"

    # 1) PyInstaller 同梱先
    base = getattr(sys, "_MEIPASS", None)
    if base:
        cand = Path(base) / "bin" / exe_name
        if cand.exists():
            return str(cand)

    # 2) アプリ直下
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    cand = exe_dir / "bin" / exe_name
    if cand.exists():
        return str(cand)

    # 3) PATH
    return shutil.which("ffprobe")