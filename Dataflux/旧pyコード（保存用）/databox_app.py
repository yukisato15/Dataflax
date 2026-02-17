#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import shutil, subprocess, sys, time, threading, queue, contextlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, stat, wave, aifc

APP_TITLE = "データ整理ボックス"

# ---------- フォーマット定義（必要に応じて増やせます） ----------
CATEGORIES = {
    "Audio": ["wav","mp3","flac","m4a","aif","aiff","ogg"],
    "Video": ["mp4","mov","m4v","avi","mkv","webm","wmv"],
    "Image": ["jpg","jpeg","png","tif","tiff","gif","bmp","webp","heic"],
    "Document": ["pdf","doc","docx","xls","xlsx","ppt","pptx","txt","md","csv"],
    "3D": ["fbx","obj","glb","gltf","usd","ply","stl"],
    "Other": ["zip","rar","7z","tar","gz"]
}

# ---------- 共通ユーティリティ ----------
def is_hidden(p: Path) -> bool:
    return p.name.startswith(".")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def unique_name(dest_dir: Path, filename: str) -> Path:
    base, ext = Path(filename).stem, Path(filename).suffix
    cand = dest_dir / f"{base}{ext}"
    i = 1
    while cand.exists():
        cand = dest_dir / f"{base}_{i:02d}{ext}"
        i += 1
    return cand

def move_to_trash(p: Path) -> bool:
    """macOS のゴミ箱へ。失敗時はユーザーTrashへ移動でフォールバック"""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'tell application "Finder" to delete POSIX file "{str(p)}"'],
            check=True, capture_output=True, text=True
        )
        return True
    except Exception:
        try:
            trash = Path.home()/".Trash"
            ensure_dir(trash)
            shutil.move(str(p), str(unique_name(trash, p.name)))
            return True
        except Exception:
            return False

def delete_junk_files(root: Path, dry_run: bool, log):
    for pat in [".DS_Store", "._*"]:
        for f in root.rglob(pat):
            if dry_run: log(f"[DRY] DELETE {f}")
            else:
                try: f.unlink()
                except FileNotFoundError: pass

def remove_empty_dirs_deep(root: Path, protect: Path|None, dry_run: bool, log):
    dirs = sorted([d for d in root.rglob("*") if d.is_dir()],
                  key=lambda d: len(d.parts), reverse=True)
    for d in dirs + [root]:
        if protect and d.resolve() == protect.resolve():  # 移動先は保護
            continue
        try:
            entries = [x for x in d.iterdir() if not is_hidden(x)]
            if not entries:
                if dry_run: log(f"[DRY] RMDIR {d}")
                else: d.rmdir()
        except Exception:
            pass

# ---------- メタ情報（Sorter 用、依存ナシで取れる範囲） ----------
def audio_probe(p: Path):
    info = {"path": p, "ext": p.suffix.lower(), "samplerate": None, "channels": None,
            "duration": None, "mtime": p.stat().st_mtime, "size": p.stat().st_size}
    try:
        if p.suffix.lower() == ".wav":
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                info["samplerate"] = w.getframerate()
                info["channels"]   = w.getnchannels()
                frames = w.getnframes()
                info["duration"]   = frames / float(w.getframerate()) if w.getframerate() else None
        elif p.suffix.lower() in (".aif", ".aiff"):
            with contextlib.closing(aifc.open(str(p), "rb")) as w:
                info["samplerate"] = w.getframerate()
                info["channels"]   = w.getnchannels()
                frames = w.getnframes()
                info["duration"]   = frames / float(w.getframerate()) if w.getframerate() else None
    except Exception:
        pass
    return info

def bucket_duration(sec):
    if sec is None: return "len_unknown"
    if sec < 5: return "len_lt5s"
    if sec < 15: return "len_5_15s"
    if sec < 60: return "len_15_60s"
    if sec < 300: return "len_1_5min"
    return "len_ge5min"

def bucket_sr(sr): return f"sr_{sr}" if sr else "sr_unknown"
def bucket_ch(ch):
    if ch is None: return "ch_unknown"
    if ch == 1: return "ch_mono"
    if ch == 2: return "ch_stereo"
    return f"ch_{ch}"
def bucket_month(ts):
    from datetime import datetime
    d = datetime.fromtimestamp(ts)
    return f"{d:%Y-%m}"
def bucket_size(sz):
    if sz < 1_000_000: return "size_lt1MB"
    if sz < 10_000_000: return "size_1_10MB"
    if sz < 100_000_000: return "size_10_100MB"
    return "size_ge100MB"

# ---------- コア処理 ----------
def iter_targets(src: Path, patterns, recursive: bool):
    if recursive:
        for pat in patterns:
            for f in src.rglob(pat):
                if f.is_file():
                    yield f
    else:
        for pat in patterns:
            for f in src.glob(pat):
                if f.is_file():
                    yield f

def build_patterns(extensions, include_zip=False):
    pats = [f"*.{ext}" for ext in extensions]
    if include_zip and "zip" not in extensions:
        pats.append("*.zip")
    return pats

# ---------- GUI ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1040x640")

        self.src = tk.StringVar()
        self.dest = tk.StringVar()
        self.category = tk.StringVar(value="Audio")
        self.action = tk.StringVar(value="フラット")
        self.sort_key = tk.StringVar(value="拡張子")

        self.recursive = tk.BooleanVar(value=True)
        self.dry_run = tk.BooleanVar(value=True)
        self.zip_as_target = tk.BooleanVar(value=True)  # ZIPも対象に含める
        self.delete_zip = tk.BooleanVar(value=True)     # フラット時：ZIP削除
        self.delete_empty = tk.BooleanVar(value=True)   # フラット時：空フォルダ削除

        self.quarantine_custom = tk.BooleanVar(value=False)
        self.quarantine_name = tk.StringVar(value="隔離フォルダ")

        self.formats_vars = {}  # ext -> BooleanVar
        self._q = queue.Queue()

        self._build_ui()
        self._refresh_formats()
        self._poll_log()

    # --- UI構築 ---
    def _build_ui(self):
        root = ttk.Frame(self, padding=12); root.pack(fill="both", expand=True)

        # 入出力
        r1 = ttk.Frame(root); r1.pack(fill="x", pady=4)
        ttk.Label(r1, text="入力フォルダ").pack(side="left")
        ttk.Entry(r1, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(r1, text="選択…", command=self._choose_src).pack(side="left")

        r2 = ttk.Frame(root); r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="出力フォルダ（フラット先/ソート先のルート）").pack(side="left")
        ttk.Entry(r2, textvariable=self.dest).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(r2, text="選択…", command=self._choose_dest).pack(side="left")

        # カテゴリ & アクション
        r3 = ttk.Frame(root); r3.pack(fill="x", pady=6)
        ttk.Label(r3, text="カテゴリ").pack(side="left")
        ttk.Combobox(r3, textvariable=self.category, values=list(CATEGORIES.keys()),
                     width=16, state="readonly").pack(side="left", padx=8)
        ttk.Button(r3, text="カテゴリ変更を反映", command=self._refresh_formats).pack(side="left", padx=8)

        ttk.Label(r3, text="アクション").pack(side="left", padx=(24,0))
        ttk.Combobox(r3, textvariable=self.action,
                     values=["フラット","削除（ゴミ箱へ）","新規フォルダへ移動","ソート"], width=18, state="readonly")\
            .pack(side="left", padx=8)

        # ソートキー
        r4 = ttk.Frame(root); r4.pack(fill="x", pady=4)
        ttk.Label(r4, text="ソート基準（ソート選択時）").pack(side="left")
        ttk.Combobox(r4, textvariable=self.sort_key,
                     values=["拡張子","更新月","サイズ","(Audio) 長さ","(Audio) サンプリングレート","(Audio) チャンネル数"],
                     width=24, state="readonly").pack(side="left", padx=8)

        # 隔離フォルダオプション
        qf = ttk.Frame(root); qf.pack(fill="x", pady=4)
        ttk.Checkbutton(qf, text="新規フォルダ名を指定する", variable=self.quarantine_custom).pack(side="left")
        ttk.Entry(qf, textvariable=self.quarantine_name, width=24).pack(side="left", padx=8)
        ttk.Label(qf, text="（未指定時は「隔離フォルダ」）").pack(side="left")

        # フォーマット群 + 全選択/全解除
        formats_frame = ttk.LabelFrame(root, text="対象フォーマット"); formats_frame.pack(fill="x", pady=8)
        self.formats_holder = ttk.Frame(formats_frame); self.formats_holder.pack(fill="x")

        selbar = ttk.Frame(formats_frame); selbar.pack(fill="x", pady=4)
        ttk.Button(selbar, text="全部選択", command=self._select_all_formats).pack(side="left")
        ttk.Button(selbar, text="全部解除", command=self._clear_all_formats).pack(side="left", padx=8)
        ttk.Checkbutton(selbar, text="ZIP も対象に含める", variable=self.zip_as_target).pack(side="left", padx=(24,0))

        # オプション
        opt = ttk.LabelFrame(root, text="オプション"); opt.pack(fill="x", pady=8)
        ttk.Checkbutton(opt, text="サブフォルダも対象", variable=self.recursive).pack(side="left")
        ttk.Checkbutton(opt, text="ドライラン（変更せずログのみ）", variable=self.dry_run).pack(side="left", padx=12)
        ttk.Checkbutton(opt, text="（フラット時）ZIPを削除", variable=self.delete_zip).pack(side="left", padx=12)
        ttk.Checkbutton(opt, text="（フラット時）空フォルダを削除", variable=self.delete_empty).pack(side="left", padx=12)

        # 実行バー
        runbar = ttk.Frame(root); runbar.pack(fill="x", pady=6)
        self.pb = ttk.Progressbar(runbar, mode="determinate"); self.pb.pack(fill="x", expand=True, side="left")
        ttk.Button(runbar, text="実行", command=self._run).pack(side="left", padx=8)

        # ログ
        logf = ttk.LabelFrame(root, text="ログ"); logf.pack(fill="both", expand=True)
        self.txt = tk.Text(logf, height=16); self.txt.pack(fill="both", expand=True)

    # --- UIハンドラ ---
    def _choose_src(self):
        p = filedialog.askdirectory(title="入力フォルダを選択")
        if p: self.src.set(p)

    def _choose_dest(self):
        p = filedialog.askdirectory(title="出力フォルダ（ルート）を選択")
        if p: self.dest.set(p)

    def _refresh_formats(self):
        for w in self.formats_holder.winfo_children(): w.destroy()
        exts = CATEGORIES.get(self.category.get(), [])
        self.formats_vars = {ext: tk.BooleanVar(value=(self.category.get()=="Audio" and ext=="wav"))
                             for ext in exts}
        # 並べて表示
        row = ttk.Frame(self.formats_holder); row.pack(fill="x")
        n=0
        for ext, var in self.formats_vars.items():
            ttk.Checkbutton(row, text=ext.upper(), variable=var).pack(side="left", padx=4, pady=2)
            n+=1
            if n%8==0:
                row = ttk.Frame(self.formats_holder); row.pack(fill="x")

    def _select_all_formats(self):
        for v in self.formats_vars.values(): v.set(True)
    def _clear_all_formats(self):
        for v in self.formats_vars.values(): v.set(False)

    def log(self, s): self._q.put(s)
    def _poll_log(self):
        try:
            while True:
                s = self._q.get_nowait()
                self.txt.insert("end", s + "\n"); self.txt.see("end")
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    # --- 実行 ---
    def _run(self):
        src = Path(self.src.get()); dst = Path(self.dest.get() or self.src.get())
        if not src.is_dir(): messagebox.showerror("エラー","入力フォルダが不正です。"); return
        if not dst.exists(): messagebox.showerror("エラー","出力フォルダが存在しません。"); return

        exts = [e for e,v in self.formats_vars.items() if v.get()]
        if not exts and not self.zip_as_target.get():
            messagebox.showerror("エラー","対象フォーマットを1つ以上選択してください。"); return

        pats = build_patterns(exts, include_zip=self.zip_as_target.get())
        files = list(iter_targets(src, pats, self.recursive.get()))
        if not files:
            messagebox.showinfo("情報","対象ファイルが見つかりません。"); return

        self.pb.configure(maximum=len(files), value=0)
        self.txt.delete("1.0","end")
        self.log(f"開始: {len(files)}件 / カテゴリ={self.category.get()} / アクション={self.action.get()}")

        def worker():
            moved=copied=deleted=0
            t0=time.time()
            action = self.action.get()
            dry = self.dry_run.get()

            # 新規フォルダ名
            qname = (self.quarantine_name.get().strip() if self.quarantine_custom.get()
                     and self.quarantine_name.get().strip() else "隔離フォルダ")

            # ソート基準
            def key_for(p: Path):
                key = self.sort_key.get()
                if key == "拡張子":
                    return p.suffix.lower().lstrip(".") or "unknown"
                if key == "更新月":
                    return bucket_month(p.stat().st_mtime)
                if key == "サイズ":
                    return bucket_size(p.stat().st_size)
                if key == "(Audio) 長さ":
                    return bucket_duration(audio_probe(p).get("duration"))
                if key == "(Audio) サンプリングレート":
                    return bucket_sr(audio_probe(p).get("samplerate"))
                if key == "(Audio) チャンネル数":
                    return bucket_ch(audio_probe(p).get("channels"))
                return "unknown"

            # フラット時の移動先
            flat_dest = dst

            for i, f in enumerate(files, 1):
                try:
                    if action == "フラット":
                        # 対象拡張子のみ移動（ZIPは「ZIPを削除」オプション優先）
                        if f.suffix.lower().lstrip(".") in exts:
                            to = unique_name(flat_dest, f.name)
                            if dry: self.log(f"[DRY] MOVE {f} -> {to}")
                            else:
                                ensure_dir(to.parent); shutil.move(str(f), str(to)); moved += 1
                        elif f.suffix.lower() == ".zip" and self.delete_zip.get():
                            if dry: self.log(f"[DRY] DELETE ZIP {f}")
                            else:
                                move_to_trash(f); deleted += 1
                        else:
                            pass  # スキップ
                    elif action == "削除（ゴミ箱へ）":
                        if dry: self.log(f"[DRY] TRASH {f}")
                        else:
                            if move_to_trash(f): deleted += 1
                            else: self.log(f"[WARN] ゴミ箱へ移動できません: {f}")
                    elif action == "新規フォルダへ移動":
                        qdir = dst / qname
                        to = unique_name(qdir, f.name)
                        if dry: self.log(f"[DRY] MOVE {f} -> {to}")
                        else:
                            ensure_dir(to.parent); shutil.move(str(f), str(to)); moved += 1
                    elif action == "ソート":
                        bucket = key_for(f)
                        to = unique_name(dst/str(bucket), f.name)
                        if dry: self.log(f"[DRY] MOVE {f} -> {to}")
                        else:
                            ensure_dir(to.parent); shutil.move(str(f), str(to)); moved += 1
                except Exception as e:
                    self.log(f"[ERROR] {f}: {e}")
                finally:
                    self.pb.after(0, lambda v=i: self.pb.configure(value=v))

            # 後処理（フラット時の空フォルダ・隠しファイル掃除）
            if action == "フラット":
                if self.delete_zip.get():
                    # 念のためZIPパターンで残りを掃除（dry-run表示のみ）
                    for z in iter_targets(src, ["*.zip"], self.recursive.get()):
                        if dry: self.log(f"[DRY] DELETE ZIP {z}")
                        else:
                            if move_to_trash(z): deleted += 1
                if self.delete_empty.get():
                    delete_junk_files(src, dry, self.log)
                    remove_empty_dirs_deep(src, protect=flat_dest, dry_run=dry, log=self.log)

            self.log("--- SUMMARY ---")
            self.log(f"moved={moved} copied={copied} deleted={deleted} time={time.time()-t0:.1f}s")
            if dry:
                self.log("※ ドライランのためファイルは変更していません。")
        threading.Thread(target=worker, daemon=True).start()

# ---- main ----
if __name__ == "__main__":
    App().mainloop()
