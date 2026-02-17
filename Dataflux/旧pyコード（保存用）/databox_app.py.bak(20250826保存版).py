#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
import threading, queue, time, sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

# ========= 共通ユーティリティ =========
def unique_name(dest_dir: Path, filename: str) -> Path:
    base, ext = Path(filename).stem, Path(filename).suffix
    cand = dest_dir / f"{base}{ext}"
    i = 1
    while cand.exists():
        cand = dest_dir / f"{base}_{i:02d}{ext}"
        i += 1
    return cand

def is_hidden(p: Path) -> bool:
    return p.name.startswith(".")

def safe_unlink(p: Path):
    try: p.unlink()
    except FileNotFoundError: pass

def delete_junk_files(root: Path, dry_run: bool, log):
    for pat in [".DS_Store", "._*"]:
        for f in root.rglob(pat):
            if dry_run:
                log(f"[DRY] DELETE {f}")
            else:
                safe_unlink(f)

def remove_empty_dirs_deep(root: Path, protect: Path|None, dry_run: bool, log):
    dirs = sorted([d for d in root.rglob("*") if d.is_dir()],
                  key=lambda d: len(d.parts), reverse=True)
    for d in dirs + [root]:
        if protect and d.resolve() == protect.resolve():
            continue
        try:
            entries = [x for x in d.iterdir() if not is_hidden(x)]
            if not entries:
                if dry_run:
                    log(f"[DRY] RMDIR {d}")
                else:
                    d.rmdir()
        except Exception:
            pass

# ========= WAVフラットナー =========
def collect_wav_zip(root: Path):
    wavs, zips = [], []
    for p in root.rglob("*"):
        if p.is_file():
            sfx = p.suffix.lower()
            if sfx == ".wav":
                wavs.append(p)
            elif sfx == ".zip":
                zips.append(p)
    return wavs, zips

def flatten_wav_folder(folder: Path, dest_dir: Path, dry_run: bool, del_zip: bool, rm_empty: bool, log):
    moved = 0; deleted_zip = 0; removed_root = False
    if not folder.is_dir():
        log(f"[SKIP] Not a dir: {folder}")
        return (moved, deleted_zip, removed_root)
    wavs, zips = collect_wav_zip(folder)

    # 1) move wav
    for wav in wavs:
        to = unique_name(dest_dir, wav.name)
        if dry_run: log(f"[DRY] MOVE  {wav} -> {to}")
        else:
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(wav), str(to))
        moved += 1

    # 2) delete zip
    if del_zip:
        for z in zips:
            if dry_run: log(f"[DRY] DELETE {z}")
            else: safe_unlink(z)
            deleted_zip += 1

    # 3) cleanup
    if rm_empty:
        delete_junk_files(folder, dry_run, log)
        remove_empty_dirs_deep(folder, protect=dest_dir, dry_run=dry_run, log=log)
        if not dry_run:
            removed_root = not folder.exists()

    return (moved, deleted_zip, removed_root)

class WavFlattener(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("WAVフラットナー")
        self.geometry("980x560")
        self.parent_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        self.dry_run = tk.BooleanVar(value=True)
        self.del_zip = tk.BooleanVar(value=True)
        self.rm_empty = tk.BooleanVar(value=True)
        self._q = queue.Queue()
        self._build()
        self._poll_log()

    def _build(self):
        frm = ttk.Frame(self, padding=12); frm.pack(fill="both", expand=True)

        row1 = ttk.Frame(frm); row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="親フォルダ（サブフォルダ一覧を表示）").pack(side="left")
        ttk.Entry(row1, textvariable=self.parent_dir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row1, text="選択...", command=self.choose_parent).pack(side="left")

        row2 = ttk.Frame(frm); row2.pack(fill="both", expand=True, pady=4)
        left = ttk.Frame(row2); left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="処理対象のサブフォルダ（複数選択可）").pack(anchor="w")
        self.lst = tk.Listbox(left, selectmode="extended"); self.lst.pack(fill="both", expand=True)
        btns = ttk.Frame(left); btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="再スキャン", command=self.scan).pack(side="left")
        ttk.Button(btns, text="全選択", command=lambda:self.lst.select_set(0, tk.END)).pack(side="left", padx=6)
        ttk.Button(btns, text="全解除", command=lambda:self.lst.select_clear(0, tk.END)).pack(side="left")

        right = ttk.Frame(row2, width=420); right.pack(side="left", fill="both")
        opt = ttk.LabelFrame(right, text="オプション"); opt.pack(fill="x", pady=4)
        ttk.Checkbutton(opt, text="ドライラン（変更せずプレビュー）", variable=self.dry_run).pack(anchor="w")
        ttk.Checkbutton(opt, text="ZIPを削除する", variable=self.del_zip).pack(anchor="w")
        ttk.Checkbutton(opt, text="空フォルダを削除する", variable=self.rm_empty).pack(anchor="w")

        drow = ttk.Frame(opt); drow.pack(fill="x", pady=(6,0))
        ttk.Label(drow, text="移動先（既定＝親フォルダ直下）").pack(anchor="w")
        ttk.Entry(drow, textvariable=self.dest_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(drow, text="参照...", command=self.choose_dest).pack(side="left", padx=6)

        runbar = ttk.Frame(right); runbar.pack(fill="x", pady=6)
        self.pb = ttk.Progressbar(runbar, mode="determinate"); self.pb.pack(fill="x", expand=True, side="left")
        ttk.Button(runbar, text="実行", command=self.run).pack(side="left", padx=8)

        logf = ttk.LabelFrame(right, text="ログ"); logf.pack(fill="both", expand=True)
        self.txt = tk.Text(logf, height=18); self.txt.pack(fill="both", expand=True)

    def choose_parent(self):
        p = filedialog.askdirectory(title="親フォルダを選択")
        if not p: return
        self.parent_dir.set(p)
        if not self.dest_dir.get(): self.dest_dir.set(p)
        self.scan()

    def choose_dest(self):
        p = filedialog.askdirectory(title="移動先フォルダ")
        if p: self.dest_dir.set(p)

    def scan(self):
        self.lst.delete(0, tk.END)
        p = Path(self.parent_dir.get())
        if not p.is_dir(): return
        for d in sorted([x for x in p.iterdir() if x.is_dir()]):
            self.lst.insert(tk.END, d.name)

    def log(self, s): self._q.put(s)
    def _poll_log(self):
        try:
            while True:
                s = self._q.get_nowait()
                self.txt.insert("end", s + "\n"); self.txt.see("end")
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    def run(self):
        parent = Path(self.parent_dir.get())
        dest   = Path(self.dest_dir.get() or self.parent_dir.get())
        if not parent.is_dir(): messagebox.showerror("エラー","親フォルダを選択してください。"); return
        if not dest.exists(): messagebox.showerror("エラー","移動先が存在しません。"); return
        sel = [self.lst.get(i) for i in self.lst.curselection()]
        if not sel: messagebox.showerror("エラー","サブフォルダを選択してください。"); return
        targets = [parent / n for n in sel]
        self.pb.configure(maximum=len(targets), value=0)
        self.txt.delete("1.0","end")
        self.log(f"開始: {len(targets)} 個のフォルダ")
        def worker():
            mv=dz=rm=0; t0=time.time()
            for i, f in enumerate(targets,1):
                self.log(f"=== {f} ===")
                a,b,c = flatten_wav_folder(
                    f, dest, self.dry_run.get(), self.del_zip.get(), self.rm_empty.get(), self.log
                )
                mv+=a; dz+=b; rm += 1 if c else 0
                self.pb.after(0, lambda v=i: self.pb.configure(value=v))
            self.log("--- SUMMARY ---")
            self.log(f"WAV moved: {mv}, ZIP deleted: {dz}, Folders removed: {rm}")
            self.log(f"処理時間: {time.time()-t0:.1f}s")
        threading.Thread(target=worker, daemon=True).start()

# ========= AudioSorter（新機能） =========
# 目的: WAV等をメタ情報で仕分け
# ルール: ソート基準（拡張子 / サンプリングレート / チャンネル数 / 長さ / 更新月）
# 備考: WAV の基本情報は標準ライブラリで取得。それ以外は拡張子ベース。
import contextlib, wave, aifc

def audio_probe(p: Path):
    """
    基本メタ情報を返す dict。WAV/AIFF は詳細、それ以外は最小限。
    """
    info = {"path": p, "ext": p.suffix.lower(), "samplerate": None, "channels": None, "duration": None, "mtime": p.stat().st_mtime}
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
        # 他形式は拡張可（mutagen 等）
    except Exception:
        pass
    return info

def bucket_duration(sec: float|None):
    if sec is None: return "len_unknown"
    if sec < 5: return "len_lt5s"
    if sec < 15: return "len_5_15s"
    if sec < 60: return "len_15_60s"
    if sec < 300: return "len_1_5min"
    return "len_ge5min"

def bucket_sr(sr: int|None):
    return f"sr_{sr}" if sr else "sr_unknown"

def bucket_ch(ch: int|None):
    if ch is None: return "ch_unknown"
    if ch == 1: return "ch_mono"
    if ch == 2: return "ch_stereo"
    return f"ch_{ch}"

def bucket_month(ts: float):
    from datetime import datetime
    d = datetime.fromtimestamp(ts)
    return f"{d:%Y-%m}"

class AudioSorter(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("AudioSorter")
        self.geometry("980x600")
        self.src = tk.StringVar()
        self.dest = tk.StringVar()
        self.mode = tk.StringVar(value="拡張子")
        self.recursive = tk.BooleanVar(value=True)
        self.dry_run = tk.BooleanVar(value=True)
        self.move_not_copy = tk.BooleanVar(value=True)
        self.rm_empty = tk.BooleanVar(value=True)
        self._q = queue.Queue()
        self._build()
        self._poll()

    def _build(self):
        frm = ttk.Frame(self, padding=12); frm.pack(fill="both", expand=True)

        r1 = ttk.Frame(frm); r1.pack(fill="x", pady=4)
        ttk.Label(r1, text="入力フォルダ").pack(side="left")
        ttk.Entry(r1, textvariable=self.src).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(r1, text="選択...", command=self.choose_src).pack(side="left")

        r2 = ttk.Frame(frm); r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="出力フォルダ（仕分け先のルート）").pack(side="left")
        ttk.Entry(r2, textvariable=self.dest).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(r2, text="選択...", command=self.choose_dest).pack(side="left")

        opt = ttk.LabelFrame(frm, text="オプション"); opt.pack(fill="x", pady=8)
        ttk.Label(opt, text="ソート基準").grid(row=0, column=0, sticky="w")
        ttk.Combobox(opt, textvariable=self.mode, values=["拡張子","サンプリングレート","チャンネル数","長さ(秒)","更新月(YYYY-MM)"], state="readonly", width=18)\
            .grid(row=0, column=1, sticky="w", padx=8)

        ttk.Checkbutton(opt, text="サブフォルダも対象", variable=self.recursive).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(opt, text="ドライラン（移動/コピーせずログのみ）", variable=self.dry_run).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(opt, text="移動する（オフならコピー）", variable=self.move_not_copy).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(opt, text="空フォルダを削除", variable=self.rm_empty).grid(row=2, column=1, sticky="w")

        runbar = ttk.Frame(frm); runbar.pack(fill="x", pady=6)
        self.pb = ttk.Progressbar(runbar, mode="determinate"); self.pb.pack(fill="x", expand=True, side="left")
        ttk.Button(runbar, text="実行", command=self.run).pack(side="left", padx=8)

        logf = ttk.LabelFrame(frm, text="ログ"); logf.pack(fill="both", expand=True)
        self.txt = tk.Text(logf, height=18); self.txt.pack(fill="both", expand=True)

    def choose_src(self):
        p = filedialog.askdirectory(title="入力フォルダを選択")
        if p: self.src.set(p)

    def choose_dest(self):
        p = filedialog.askdirectory(title="出力フォルダを選択")
        if p: self.dest.set(p)

    def log(self, s): self._q.put(s)
    def _poll(self):
        try:
            while True:
                s = self._q.get_nowait()
                self.txt.insert("end", s + "\n"); self.txt.see("end")
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def run(self):
        src = Path(self.src.get()); dst = Path(self.dest.get())
        if not src.is_dir(): messagebox.showerror("エラー","入力フォルダが不正です。"); return
        if not dst.exists(): messagebox.showerror("エラー","出力フォルダが存在しません。"); return
        pats = ("*.wav","*.aif","*.aiff","*.mp3","*.flac","*.m4a")
        files = []
        if self.recursive.get():
            for pat in pats: files += list(src.rglob(pat))
        else:
            for pat in pats: files += list(src.glob(pat))
        if not files: messagebox.showinfo("情報","対象ファイルが見つかりません。"); return

        self.pb.configure(maximum=len(files), value=0)
        self.txt.delete("1.0","end")
        self.log(f"開始: {len(files)} ファイル / 基準={self.mode.get()}")

        def key_for(info):
            m = self.mode.get()
            if m == "拡張子": return info["ext"].lstrip(".") or "unknown"
            if m == "サンプリングレート": return bucket_sr(info["samplerate"])
            if m == "チャンネル数": return bucket_ch(info["channels"])
            if m == "長さ(秒)": return bucket_duration(info["duration"])
            if m == "更新月(YYYY-MM)": return bucket_month(info["mtime"])
            return "unknown"

        def worker():
            start=time.time(); moved=0; copied=0
            for i, p in enumerate(files, 1):
                info = audio_probe(p)
                bucket = key_for(info)
                out_dir = dst / str(bucket)
                out_path = unique_name(out_dir, p.name)
                if self.dry_run.get():
                    op = "MOVE" if self.move_not_copy.get() else "COPY"
                    self.log(f"[DRY] {op} {p} -> {out_path}")
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    if self.move_not_copy.get(): shutil.move(str(p), str(out_path)); moved += 1
                    else: shutil.copy2(str(p), str(out_path)); copied += 1
                self.pb.after(0, lambda v=i: self.pb.configure(value=v))
            if self.rm_empty.get():
                delete_junk_files(src, self.dry_run.get(), self.log)
                remove_empty_dirs_deep(src, protect=None, dry_run=self.dry_run.get(), log=self.log)
            self.log("--- SUMMARY ---")
            self.log(f"Moved: {moved}, Copied: {copied}, Time: {time.time()-start:.1f}s")
        threading.Thread(target=worker, daemon=True).start()

# ========= ランチャー（トップ画面） =========
class DataBoxApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("データ整理ボックス")
        self.geometry("720x420")
        root = ttk.Frame(self, padding=20); root.pack(fill="both", expand=True)
        head = ttk.Label(root, text="データ整理ボックス", font=("Helvetica", 20, "bold"))
        head.pack(pady=(0,10))
        sub  = ttk.Label(root, text="使いたいツールを選んでください。")
        sub.pack(pady=(0,20))

        grid = ttk.Frame(root); grid.pack(expand=True)
        b1 = ttk.Button(grid, text="WAVフラットナー\n(フォルダを潰してWAVだけ集約)", width=32, command=lambda: WavFlattener(self))
        b2 = ttk.Button(grid, text="AudioSorter\n(メタ情報で自動仕分け)", width=32, command=lambda: AudioSorter(self))
        b1.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        b2.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        # 余白
        ttk.Label(root, text="").pack(pady=6)
        # フッタ
        ttk.Label(root, text="© 2025 Data Organizer", foreground="#666").pack()

if __name__ == "__main__":
    DataBoxApp().mainloop()
