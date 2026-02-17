#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Flattener + Sorter (Integrated UI)
- 複数フォルダを入力
- モード切替: Flattener / Sorter
- Flattener: 残すフォーマットを複数選択し、親直下へ集約（重複は連番回避）
- Sorter: 拡張子 / サンプルレート / チャンネル / 長さ帯 / 更新月 で仕分け
- 共通: ZIP削除/保持、空フォルダ削除（隠しメタファイル掃除）、削除(ゴミ箱)/隔離(任意名) オプション、ドライラン

依存: 標準ライブラリのみ（tkinter, wave, aifc, shutil, pathlib など）
注意: macOS のゴミ箱は ~/.Trash を使用（衝突時は連番）
"""
from __future__ import annotations
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import threading
import queue
import contextlib
import wave, aifc
from datetime import datetime

# ========= ユーティリティ =========

def unique_name(dest_dir: Path, filename: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = Path(filename).stem
    ext = Path(filename).suffix
    cand = dest_dir / f"{base}{ext}"
    i = 1
    while cand.exists():
        cand = dest_dir / f"{base}_{i:02d}{ext}"
        i += 1
    return cand


def is_hidden(p: Path) -> bool:
    return p.name.startswith(".")


def safe_unlink(p: Path):
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def send_to_trash(p: Path):
    """macOS のローカルゴミ箱 (~/.Trash) に移動。衝突は連番で回避。"""
    trash = Path.home() / ".Trash"
    target = unique_name(trash, p.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(target))


def delete_junk_files(root: Path, dry_run: bool, log):
    for pat in [".DS_Store", "._*"]:
        for f in root.rglob(pat):
            if dry_run:
                log(f"[DRY] DELETE {f}")
            else:
                safe_unlink(f)


def remove_empty_dirs_deep(root: Path, protect: set[Path], dry_run: bool, log):
    dirs = sorted([d for d in root.rglob("*") if d.is_dir()], key=lambda d: len(d.parts), reverse=True)
    for d in dirs + [root]:
        if any(d.resolve() == pr.resolve() for pr in protect):
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


# ========= 解析（サマリー） =========

def scan_summary(paths: list[Path]) -> dict[str, dict[str, int]]:
    """拡張子ごとの {count, bytes} を返す"""
    out: dict[str, dict[str, int]] = {}
    for root in paths:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                ext = p.suffix.lower() or ""
                d = out.setdefault(ext, {"count": 0, "bytes": 0})
                d["count"] += 1
                try:
                    d["bytes"] += p.stat().st_size
                except Exception:
                    pass
    return out


# ========= Audio メタ情報 =========

def audio_probe(p: Path):
    info = {
        "path": p,
        "ext": p.suffix.lower(),
        "samplerate": None,
        "channels": None,
        "duration": None,
        "mtime": p.stat().st_mtime if p.exists() else None,
    }
    try:
        if p.suffix.lower() == ".wav":
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                info["samplerate"] = w.getframerate()
                info["channels"] = w.getnchannels()
                frames = w.getnframes()
                fr = w.getframerate() or 0
                info["duration"] = (frames / fr) if fr else None
        elif p.suffix.lower() in (".aif", ".aiff"):
            with contextlib.closing(aifc.open(str(p), "rb")) as w:
                info["samplerate"] = w.getframerate()
                info["channels"] = w.getnchannels()
                frames = w.getnframes()
                fr = w.getframerate() or 0
                info["duration"] = (frames / fr) if fr else None
    except Exception:
        pass
    return info


def bucket_duration(sec: float | None) -> str:
    if sec is None:
        return "len_unknown"
    if sec < 5:
        return "len_lt5s"
    if sec < 15:
        return "len_5_15s"
    if sec < 60:
        return "len_15_60s"
    if sec < 300:
        return "len_1_5min"
    return "len_ge5min"


def bucket_sr(sr: int | None) -> str:
    return f"sr_{sr}" if sr else "sr_unknown"


def bucket_ch(ch: int | None) -> str:
    if ch is None:
        return "ch_unknown"
    if ch == 1:
        return "ch_mono"
    if ch == 2:
        return "ch_stereo"
    return f"ch_{ch}"


def bucket_month(ts: float | None) -> str:
    if ts is None:
        return "date_unknown"
    d = datetime.fromtimestamp(ts)
    return f"{d:%Y-%m}"


# ========= Audio Flattener / Sorter ロジック =========

def iter_audio_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for pat in patterns:
        files += list(root.rglob(pat))
    return files


def do_flatten_audio(inputs: list[Path], allowed_exts: set[str], del_zip: bool, rm_empty: bool,
                     dry_run: bool, isolate_dir: Path | None, trash: bool, log) -> dict:
    moved = 0
    isolated = 0
    trashed = 0
    zdeleted = 0
    roots_protect = set()

    for folder in inputs:
        if not folder.is_dir():
            log(f"[SKIP] Not a dir: {folder}")
            continue
        parent = folder
        # 収集する対象
        for p in folder.rglob("*"):
            if p.is_file():
                ext = p.suffix.lower().lstrip(".")
                if ext in allowed_exts:
                    # 集約先 = 親フォルダ直下（要件に合わせて parent をそのまま利用）
                    dest_dir = parent
                    to = unique_name(dest_dir, p.name)
                    if dry_run:
                        log(f"[DRY] MOVE {p} -> {to}")
                    else:
                        shutil.move(str(p), str(to))
                    moved += 1
                else:
                    # 非対象：削除 or 隔離 or スキップ
                    if trash:
                        if dry_run:
                            log(f"[DRY] TRASH {p}")
                        else:
                            send_to_trash(p)
                        trashed += 1
                    elif isolate_dir is not None:
                        to = unique_name(isolate_dir, p.name)
                        if dry_run:
                            log(f"[DRY] ISOLATE {p} -> {to}")
                        else:
                            shutil.move(str(p), str(to))
                        isolated += 1
                    else:
                        # skip
                        pass
        # ZIP処理
        if del_zip:
            for z in folder.rglob("*.zip"):
                if dry_run:
                    log(f"[DRY] DELETE {z}")
                else:
                    safe_unlink(z)
                zdeleted += 1
        # 空フォルダ削除
        if rm_empty:
            delete_junk_files(folder, dry_run, log)
            remove_empty_dirs_deep(folder, protect=roots_protect, dry_run=dry_run, log=log)
    return {
        "moved": moved,
        "isolated": isolated,
        "trashed": trashed,
        "zip_deleted": zdeleted,
    }


def do_sort_audio(inputs: list[Path], criterion: str, del_zip: bool, rm_empty: bool,
                  dry_run: bool, isolate_dir: Path | None, trash: bool, log) -> dict:
    moved = 0
    isolated = 0
    trashed = 0
    zdeleted = 0

    for folder in inputs:
        if not folder.is_dir():
            log(f"[SKIP] Not a dir: {folder}")
            continue
        files = iter_audio_files(folder, ("*.wav", "*.aif", "*.aiff", "*.mp3", "*.flac", "*.m4a"))
        for p in files:
            info = audio_probe(p)
            if criterion == "拡張子":
                bucket = info["ext"].lstrip(".") or "unknown"
            elif criterion == "サンプリングレート":
                bucket = bucket_sr(info["samplerate"])
            elif criterion == "チャンネル数":
                bucket = bucket_ch(info["channels"])
            elif criterion == "長さ(秒)":
                bucket = bucket_duration(info["duration"])
            elif criterion == "更新月(YYYY-MM)":
                bucket = bucket_month(info["mtime"])
            else:
                bucket = "unknown"
            out_dir = folder / bucket
            out_path = unique_name(out_dir, p.name)
            if dry_run:
                log(f"[DRY] MOVE {p} -> {out_path}")
            else:
                shutil.move(str(p), str(out_path))
            moved += 1
        # ZIP処理
        if del_zip:
            for z in folder.rglob("*.zip"):
                if dry_run:
                    log(f"[DRY] DELETE {z}")
                else:
                    safe_unlink(z)
                zdeleted += 1
        # 残りファイルに対する削除/隔離（任意）
        leftovers = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() not in (".zip",)]
        for p in leftovers:
            if trash:
                if dry_run:
                    log(f"[DRY] TRASH {p}")
                else:
                    send_to_trash(p)
                trashed += 1
            elif isolate_dir is not None:
                to = unique_name(isolate_dir, p.name)
                if dry_run:
                    log(f"[DRY] ISOLATE {p} -> {to}")
                else:
                    shutil.move(str(p), str(to))
                isolated += 1
        # 空フォルダ削除
        if rm_empty:
            delete_junk_files(folder, dry_run, log)
            remove_empty_dirs_deep(folder, protect=set(), dry_run=dry_run, log=log)

    return {
        "moved": moved,
        "isolated": isolated,
        "trashed": trashed,
        "zip_deleted": zdeleted,
    }


# ========= GUI =========
class AudioIntegratedUI(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Audio Flattener / Sorter")
        self.geometry("1024x640")
        self._q = queue.Queue()

        # 入力フォルダ管理
        self.inputs: list[Path] = []

        # モード切替
        self.mode = tk.StringVar(value="Flattener")  # Flattener / Sorter

        # Flattener: フォーマット選択
        self.format_vars = {
            "wav": tk.BooleanVar(value=True),
            "mp3": tk.BooleanVar(value=False),
            "flac": tk.BooleanVar(value=False),
            "m4a": tk.BooleanVar(value=False),
            "aiff": tk.BooleanVar(value=False),
        }

        # Sorter: 基準
        self.sort_key = tk.StringVar(value="拡張子")

        # 共通オプション
        self.del_zip = tk.BooleanVar(value=True)
        self.rm_empty = tk.BooleanVar(value=True)
        self.dry_run = tk.BooleanVar(value=True)
        self.use_trash = tk.BooleanVar(value=False)  # 削除をゴミ箱へ
        self.isolate = tk.BooleanVar(value=False)
        self.isolate_name = tk.StringVar(value="隔離フォルダ")

        self._build()
        self._poll_log()

    # ====== UI 構築 ======
    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # 上段: 入力フォルダ
        top = ttk.LabelFrame(root, text="入力フォルダ（複数追加可）")
        top.pack(fill="x")
        row = ttk.Frame(top)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text="フォルダ追加...", command=self.add_folders).pack(side="left")
        ttk.Button(row, text="選択削除", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(row, text="全クリア", command=self.clear_inputs).pack(side="left")
        ttk.Button(row, text="解析（拡張子集計）", command=self.run_analysis).pack(side="right")

        self.lst = tk.Listbox(top, height=5, selectmode="extended")
        self.lst.pack(fill="x", pady=(0,8))

        self.summary = tk.Text(top, height=6)
        self.summary.pack(fill="x")

        # 中段: モード切替
        modef = ttk.LabelFrame(root, text="モード")
        modef.pack(fill="x", pady=8)
        ttk.Radiobutton(modef, text="Flattener", value="Flattener", variable=self.mode, command=self._refresh_mode).pack(side="left")
        ttk.Radiobutton(modef, text="Sorter", value="Sorter", variable=self.mode, command=self._refresh_mode).pack(side="left", padx=12)

        # 下段: オプション + 実行
        self.opt_area = ttk.Frame(root)
        self.opt_area.pack(fill="both", expand=True)
        self._build_flattener_options(self.opt_area)
        self._build_common_options(root)

        run = ttk.Frame(root)
        run.pack(fill="x", pady=8)
        self.pb = ttk.Progressbar(run, mode="determinate")
        self.pb.pack(side="left", fill="x", expand=True)
        ttk.Button(run, text="実行", command=self.execute).pack(side="left", padx=8)

        logf = ttk.LabelFrame(root, text="ログ")
        logf.pack(fill="both", expand=True)
        self.logbox = tk.Text(logf, height=12)
        self.logbox.pack(fill="both", expand=True)

    def _build_flattener_options(self, parent):
        # Flattener 用
        for w in parent.winfo_children():
            w.destroy()
        flf = ttk.LabelFrame(parent, text="Flattener オプション（残すフォーマット）")
        flf.pack(fill="x", pady=6)
        row = ttk.Frame(flf); row.pack(fill="x")
        for i, (ext, var) in enumerate(self.format_vars.items()):
            ttk.Checkbutton(row, text=ext.upper(), variable=var).grid(row=0, column=i, sticky="w", padx=4)
        btns = ttk.Frame(flf); btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="全部選択", command=lambda: self._set_all_formats(True)).pack(side="left")
        ttk.Button(btns, text="全部解除", command=lambda: self._set_all_formats(False)).pack(side="left", padx=6)

    def _build_sorter_options(self, parent):
        # Sorter 用
        for w in parent.winfo_children():
            w.destroy()
        sof = ttk.LabelFrame(parent, text="Sorter オプション（仕分け基準）")
        sof.pack(fill="x", pady=6)
        ttk.Label(sof, text="基準").pack(side="left")
        ttk.Combobox(sof, textvariable=self.sort_key, state="readonly",
                     values=["拡張子", "サンプリングレート", "チャンネル数", "長さ(秒)", "更新月(YYYY-MM)"]
                     ).pack(side="left", padx=8)

    def _build_common_options(self, root):
        cof = ttk.LabelFrame(self, text="共通オプション")
        cof.pack(fill="x", pady=6)
        ttk.Checkbutton(cof, text="ZIPを削除", variable=self.del_zip).pack(side="left")
        ttk.Checkbutton(cof, text="空フォルダを削除（隠しファイル掃除込み）", variable=self.rm_empty).pack(side="left", padx=12)
        ttk.Checkbutton(cof, text="ドライラン（プレビューのみ）", variable=self.dry_run).pack(side="left", padx=12)

        # 削除/隔離
        row = ttk.Frame(cof); row.pack(fill="x", pady=6)
        ttk.Checkbutton(row, text="削除（ゴミ箱へ）", variable=self.use_trash).pack(side="left")
        ttk.Checkbutton(row, text="隔離", variable=self.isolate).pack(side="left", padx=8)
        ttk.Label(row, text="隔離フォルダ名").pack(side="left")
        ttk.Entry(row, textvariable=self.isolate_name, width=20).pack(side="left", padx=6)

    # ====== UI ヘルパ ======
    def _refresh_mode(self):
        self._log("[UI] モード切替: " + self.mode.get())
        if self.mode.get() == "Flattener":
            self._build_flattener_options(self.opt_area)
        else:
            self._build_sorter_options(self.opt_area)

    def _set_all_formats(self, v: bool):
        for var in self.format_vars.values():
            var.set(v)

    def add_folders(self):
        # 複数回追加で複数入力に対応
        p = filedialog.askdirectory(title="入力フォルダを選択")
        if p:
            path = Path(p)
            if path not in self.inputs:
                self.inputs.append(path)
                self.lst.insert(tk.END, str(path))

    def remove_selected(self):
        sel = list(self.lst.curselection())
        sel.reverse()
        for i in sel:
            removed = self.lst.get(i)
            self.lst.delete(i)
            try:
                self.inputs.remove(Path(removed))
            except ValueError:
                pass

    def clear_inputs(self):
        self.inputs.clear()
        self.lst.delete(0, tk.END)
        self.summary.delete("1.0", "end")

    def run_analysis(self):
        if not self.inputs:
            messagebox.showinfo("情報", "入力フォルダを追加してください。")
            return
        s = scan_summary(self.inputs)
        lines = ["拡張子\t件数\t合計サイズ(MB)"]
        for ext, d in sorted(s.items(), key=lambda x: (-x[1]["count"], x[0])):
            mb = d["bytes"] / (1024*1024) if d["bytes"] else 0
            lines.append(f"{ext or '(no ext)'}\t{d['count']}\t{mb:.2f}")
        self.summary.delete("1.0", "end")
        self.summary.insert("end", "\n".join(lines))

    # ====== 実行 ======
    def _poll_log(self):
        try:
            while True:
                s = self._q.get_nowait()
                self.logbox.insert("end", s + "\n")
                self.logbox.see("end")
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    def _log(self, s: str):
        self._q.put(s)

    def execute(self):
        if not self.inputs:
            messagebox.showerror("エラー", "入力フォルダを追加してください。")
            return
        # 隔離フォルダ（任意）
        iso_dir = None
        if self.isolate.get():
            # 1つ目の入力直下に作成（必要に応じて変更可）
            base = self.inputs[0]
            iso_dir = base / self.isolate_name.get()
            if not self.dry_run.get():
                iso_dir.mkdir(parents=True, exist_ok=True)

        self.pb.configure(maximum=len(self.inputs), value=0)
        self.logbox.delete("1.0", "end")
        self._log(f"開始: {len(self.inputs)} フォルダ / モード={self.mode.get()}")

        def worker():
            t0 = time.time()
            if self.mode.get() == "Flattener":
                allowed = {k for k, v in self.format_vars.items() if v.get()}
                if not allowed:
                    self._log("[WARN] 残すフォーマットが未選択です。中止します。")
                    return
                res = do_flatten_audio(
                    inputs=self.inputs,
                    allowed_exts=allowed,
                    del_zip=self.del_zip.get(),
                    rm_empty=self.rm_empty.get(),
                    dry_run=self.dry_run.get(),
                    isolate_dir=iso_dir,
                    trash=self.use_trash.get(),
                    log=self._log,
                )
            else:
                res = do_sort_audio(
                    inputs=self.inputs,
                    criterion=self.sort_key.get(),
                    del_zip=self.del_zip.get(),
                    rm_empty=self.rm_empty.get(),
                    dry_run=self.dry_run.get(),
                    isolate_dir=iso_dir,
                    trash=self.use_trash.get(),
                    log=self._log,
                )
            self._log("--- SUMMARY ---")
            for k, v in res.items():
                self._log(f"{k}: {v}")
            self._log(f"経過: {time.time()-t0:.1f}s")
            self.pb.after(0, lambda: self.pb.configure(value=self.pb["maximum"]))
        threading.Thread(target=worker, daemon=True).start()


# スタンドアロン実行用
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    AudioIntegratedUI(root)
    root.mainloop()
