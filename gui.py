"""
gui.py — Tkinter GUI for benchmark_graph.py

Run with:
    python gui.py
"""
from __future__ import annotations

import os
import platform
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

import numpy as np
import pandas as pd

import benchmark_graph as bg


# ---------------------------------------------------------------------------
# Colour constants (match the dark chart theme)
# ---------------------------------------------------------------------------
BG_DARK    = "#1a1a2e"
BG_PANEL   = "#16213e"
BG_WIDGET  = "#0f3460"
FG_TEXT    = "#ccccdd"
FG_ACCENT  = "#e43f64"
FG_DIM     = "#666688"
FONT_MAIN  = ("Segoe UI", 10)
FONT_MONO  = ("Consolas", 9)
FONT_TITLE = ("Segoe UI", 11, "bold")


# ---------------------------------------------------------------------------
# Color palette presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, list[str]] = {
    "Neon Dark":     ["#e43f64", "#2daae9", "#c680cf"],
    "Arctic Blue":   ["#00b4d8", "#48cae4", "#ade8f4"],
    "Warm Sunset":   ["#f77f00", "#fcbf49", "#eae2b7"],
    "Forest":        ["#52b788", "#2d6a4f", "#95d5b2"],
    "Monochrome":    ["#e0e0e0", "#a0a0a0", "#606060"],
}


# ---------------------------------------------------------------------------
# Color editor dialog
# ---------------------------------------------------------------------------

class ColorEditorDialog(tk.Toplevel):
    """Modal dialog for picking custom series colors."""

    def __init__(self, parent: tk.Tk, current_palette: list[str]) -> None:
        super().__init__(parent)
        self.title("Edit Chart Colors")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)
        self.transient(parent)
        self.grab_set()

        self.result: list[str] | None = None
        self._colors = list(current_palette)
        self._swatches: list[tk.Button] = []

        ttk.Label(self, text="Click a swatch to pick a color",
                  foreground=FG_DIM, font=("Segoe UI", 9)).pack(pady=(12, 6), padx=20)

        for i, label in enumerate(("Series 1", "Series 2", "Series 3")):
            row = ttk.Frame(self)
            row.pack(fill="x", padx=20, pady=4)

            ttk.Label(row, text=label, width=10, anchor="w").pack(side="left")

            swatch = tk.Button(
                row, bg=self._colors[i], width=4, relief="flat",
                activebackground=self._colors[i], cursor="hand2",
                command=lambda idx=i: self._pick(idx),
            )
            swatch.pack(side="left", padx=(0, 8))
            self._swatches.append(swatch)

            hex_var = tk.StringVar(value=self._colors[i])
            hex_entry = ttk.Entry(row, textvariable=hex_var, width=10)
            hex_entry.pack(side="left")
            hex_entry.bind("<FocusOut>", lambda e, idx=i, v=hex_var: self._apply_hex(idx, v))
            hex_entry.bind("<Return>",   lambda e, idx=i, v=hex_var: self._apply_hex(idx, v))
            # stash for later updates
            swatch._hex_var = hex_var  # type: ignore[attr-defined]

        btn_row = ttk.Frame(self)
        btn_row.pack(pady=(14, 14))
        ttk.Button(btn_row, text="Apply",  command=self._confirm).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self.wait_window()

    def _pick(self, idx: int) -> None:
        result = colorchooser.askcolor(
            color=self._colors[idx], parent=self,
            title=f"Pick color for Series {idx + 1}",
        )
        if result[1]:
            self._set_color(idx, result[1])

    def _apply_hex(self, idx: int, var: tk.StringVar) -> None:
        val = var.get().strip()
        if not val.startswith("#"):
            val = "#" + val
        try:
            self.winfo_rgb(val)   # raises TclError if invalid
            self._set_color(idx, val)
        except tk.TclError:
            var.set(self._colors[idx])   # revert bad input

    def _set_color(self, idx: int, hex_color: str) -> None:
        self._colors[idx] = hex_color
        self._swatches[idx].configure(bg=hex_color, activebackground=hex_color)
        self._swatches[idx]._hex_var.set(hex_color)  # type: ignore[attr-defined]

    def _confirm(self) -> None:
        self.result = list(self._colors)
        self.destroy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def open_folder(path: Path) -> None:
    """Open a directory in the system file explorer."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def configure_ttk_style() -> ttk.Style:
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".",
        background=BG_DARK, foreground=FG_TEXT,
        fieldbackground=BG_WIDGET, bordercolor=FG_DIM,
        troughcolor=BG_PANEL, selectbackground=BG_WIDGET,
        selectforeground=FG_TEXT, font=FONT_MAIN,
    )
    style.configure("TFrame",  background=BG_DARK)
    style.configure("TLabel",  background=BG_DARK,  foreground=FG_TEXT, font=FONT_MAIN)
    style.configure("TButton", background=BG_WIDGET, foreground=FG_TEXT, font=FONT_MAIN,
                    borderwidth=1, relief="flat", padding=(8, 4))
    style.map("TButton",
        background=[("active", FG_ACCENT), ("pressed", FG_ACCENT)],
        foreground=[("active", "#ffffff"),  ("pressed", "#ffffff")],
    )
    style.configure("Accent.TButton", background=FG_ACCENT, foreground="#ffffff",
                    font=("Segoe UI", 10, "bold"), padding=(12, 6))
    style.map("Accent.TButton",
        background=[("active", "#c0304e"), ("pressed", "#a0263e")],
    )
    style.configure("TEntry",  fieldbackground=BG_WIDGET, foreground=FG_TEXT,
                    insertcolor=FG_TEXT, bordercolor=FG_DIM)
    style.configure("Treeview",
        background=BG_PANEL, foreground=FG_TEXT,
        fieldbackground=BG_PANEL, rowheight=26,
    )
    style.configure("Treeview.Heading",
        background=BG_WIDGET, foreground=FG_TEXT, font=("Segoe UI", 9, "bold"),
    )
    style.map("Treeview", background=[("selected", BG_WIDGET)])
    style.configure("TNotebook",      background=BG_DARK,  borderwidth=0)
    style.configure("TNotebook.Tab",  background=BG_PANEL, foreground=FG_DIM,
                    padding=(10, 5), font=FONT_MAIN)
    style.map("TNotebook.Tab",
        background=[("selected", BG_WIDGET)],
        foreground=[("selected", FG_TEXT)],
    )
    style.configure("TScrollbar", background=BG_PANEL, troughcolor=BG_DARK,
                    arrowcolor=FG_DIM)
    style.configure("TProgressbar", troughcolor=BG_PANEL, background=FG_ACCENT)
    return style


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Benchmark Graph Generator")
        self.configure(bg=BG_DARK)
        self.minsize(900, 680)
        self.geometry("1200x820")

        configure_ttk_style()

        # State
        self._files: list[dict] = []   # [{"path": Path, "label": str}]
        self._log_queue: queue.Queue[str | None] = queue.Queue()
        self._last_outdir: Path | None = None
        self._generating = False
        self._palette_name = tk.StringVar(value="Neon Dark")

        self._build_menubar()
        self._build_ui()
        self._poll_log()

    # -----------------------------------------------------------------------
    # Menu bar
    # -----------------------------------------------------------------------

    def _build_menubar(self) -> None:
        menubar = tk.Menu(self, bg=BG_PANEL, fg=FG_TEXT, activebackground=BG_WIDGET,
                          activeforeground=FG_TEXT, borderwidth=0, relief="flat")

        colors_menu = tk.Menu(menubar, tearoff=False, bg=BG_PANEL, fg=FG_TEXT,
                              activebackground=BG_WIDGET, activeforeground=FG_TEXT)

        for name in PRESETS:
            colors_menu.add_radiobutton(
                label=name,
                variable=self._palette_name,
                value=name,
                command=lambda n=name: self._apply_preset(n),
            )

        colors_menu.add_separator()
        colors_menu.add_command(label="Edit Colors…", command=self._open_color_editor)

        menubar.add_cascade(label="Colors", menu=colors_menu)
        self.configure(menu=menubar)

    def _apply_preset(self, name: str) -> None:
        bg.PALETTE[:] = PRESETS[name]
        self._palette_name.set(name)
        self._log_widget_write(f"Palette changed to  {name}  — regenerate to apply.\n", tag="dim")

    def _open_color_editor(self) -> None:
        dlg = ColorEditorDialog(self, bg.PALETTE)
        if dlg.result is not None:
            bg.PALETTE[:] = dlg.result
            self._palette_name.set("Custom")
            self._log_widget_write(
                f"Custom palette applied: {', '.join(dlg.result)}"
                "  — regenerate to apply.\n", tag="dim"
            )

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ── Top: file list + controls ──────────────────────────────────────
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(10, 0))

        ttk.Label(top, text="Benchmark Graph Generator", font=FONT_TITLE,
                  foreground=FG_ACCENT).pack(side="left")

        # ── File list section ──────────────────────────────────────────────
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="x", padx=12, pady=(8, 0))

        # Toolbar above the list
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="+ Add CSVs",  command=self._add_files).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="Remove",      command=self._remove_selected).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="↑ Up",        command=self._move_up).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="↓ Down",      command=self._move_down).pack(side="left", padx=(0, 4))
        ttk.Label(toolbar, text="Double-click a Label cell to rename it",
                  foreground=FG_DIM, font=("Segoe UI", 9)).pack(side="left", padx=12)

        # Treeview + scrollbar
        tree_wrap = ttk.Frame(list_frame)
        tree_wrap.pack(fill="x")

        cols = ("num", "file", "label")
        self._tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=6,
                                   selectmode="browse")
        self._tree.heading("num",   text="#")
        self._tree.heading("file",  text="File")
        self._tree.heading("label", text="Label  (double-click to edit)")
        self._tree.column("num",   width=36,  stretch=False, anchor="center")
        self._tree.column("file",  width=340, stretch=True)
        self._tree.column("label", width=220, stretch=True)

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="left", fill="y")

        self._tree.bind("<Double-1>", self._on_tree_double_click)

        # ── Settings row ───────────────────────────────────────────────────
        settings = ttk.Frame(self)
        settings.pack(fill="x", padx=12, pady=(10, 0))

        # Title
        ttk.Label(settings, text="Title:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._title_var = tk.StringVar(value="Benchmark Comparison")
        ttk.Entry(settings, textvariable=self._title_var, width=38).grid(
            row=0, column=1, sticky="ew", padx=(0, 20))

        # Frametime column override
        ttk.Label(settings, text="Frametime col:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self._ft_col_var = tk.StringVar()
        ft_entry = ttk.Entry(settings, textvariable=self._ft_col_var, width=24)
        ft_entry.grid(row=0, column=3, sticky="ew", padx=(0, 4))
        ttk.Label(settings, text="(blank = auto-detect)", foreground=FG_DIM,
                  font=("Segoe UI", 9)).grid(row=0, column=4, sticky="w")

        # Output directory
        ttk.Label(settings, text="Output dir:").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
        self._outdir_var = tk.StringVar(value="charts_out")
        ttk.Entry(settings, textvariable=self._outdir_var, width=38).grid(
            row=1, column=1, sticky="ew", padx=(0, 4), pady=(6, 0))
        ttk.Button(settings, text="Browse…", command=self._browse_outdir).grid(
            row=1, column=2, sticky="w", pady=(6, 0))

        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        # ── Action buttons ─────────────────────────────────────────────────
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=12, pady=(10, 0))

        self._gen_btn = ttk.Button(actions, text="Generate Charts  ▶",
                                    style="Accent.TButton", command=self._generate)
        self._gen_btn.pack(side="left")

        self._open_btn = ttk.Button(actions, text="Open Output Folder",
                                     command=self._open_output, state="disabled")
        self._open_btn.pack(side="left", padx=(10, 0))

        self._progress = ttk.Progressbar(actions, mode="indeterminate", length=160)
        self._progress.pack(side="right", padx=(0, 0))

        # ── Chart preview ──────────────────────────────────────────────────
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", padx=12, pady=(10, 0))

        ttk.Label(self, text="Chart Preview", font=FONT_TITLE).pack(
            anchor="w", padx=12, pady=(6, 0))

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        # Placeholder tab shown before first generation
        placeholder = ttk.Frame(self._notebook)
        placeholder.configure(style="TFrame")
        self._notebook.add(placeholder, text="(no charts yet)")
        lbl = ttk.Label(placeholder,
                        text="Add CSV files and click  Generate Charts  to see results here.",
                        foreground=FG_DIM)
        lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Log output ─────────────────────────────────────────────────────
        sep2 = ttk.Separator(self, orient="horizontal")
        sep2.pack(fill="x", padx=12, pady=(6, 0))

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="x", padx=12, pady=(4, 8))

        self._log = ScrolledText(log_frame, height=6, state="disabled",
                                  bg=BG_PANEL, fg=FG_TEXT, font=FONT_MONO,
                                  insertbackground=FG_TEXT, relief="flat",
                                  borderwidth=0, wrap="word")
        self._log.pack(fill="x")
        self._log.tag_config("error", foreground="#ff6688")
        self._log.tag_config("ok",    foreground="#44dd99")
        self._log.tag_config("dim",   foreground=FG_DIM)

    # -----------------------------------------------------------------------
    # File list management
    # -----------------------------------------------------------------------

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select CapFrameX / PresentMon CSV files",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        for p in paths:
            path = Path(p)
            if any(f["path"] == path for f in self._files):
                continue
            self._files.append({"path": path, "label": path.stem})
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, f in enumerate(self._files, start=1):
            self._tree.insert("", "end", iid=str(i - 1),
                               values=(i, f["path"].name, f["label"]))

    def _selected_index(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _remove_selected(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        self._files.pop(idx)
        self._refresh_tree()

    def _move_up(self) -> None:
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        self._files[idx - 1], self._files[idx] = self._files[idx], self._files[idx - 1]
        self._refresh_tree()
        self._tree.selection_set(str(idx - 1))

    def _move_down(self) -> None:
        idx = self._selected_index()
        if idx is None or idx >= len(self._files) - 1:
            return
        self._files[idx], self._files[idx + 1] = self._files[idx + 1], self._files[idx]
        self._refresh_tree()
        self._tree.selection_set(str(idx + 1))

    def _on_tree_double_click(self, event: tk.Event) -> None:
        """Edit a label on double-click."""
        region = self._tree.identify_region(event.x, event.y)
        col    = self._tree.identify_column(event.x)
        if region != "cell" or col != "#3":   # column 3 = "label"
            return
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        idx   = int(iid)
        old   = self._files[idx]["label"]
        new   = simpledialog.askstring("Edit Label", f"Label for  {self._files[idx]['path'].name}:",
                                        initialvalue=old, parent=self)
        if new is not None and new.strip():
            self._files[idx]["label"] = new.strip()
            self._refresh_tree()

    # -----------------------------------------------------------------------
    # Settings helpers
    # -----------------------------------------------------------------------

    def _browse_outdir(self) -> None:
        d = filedialog.askdirectory(title="Select output parent directory")
        if d:
            self._outdir_var.set(d)

    # -----------------------------------------------------------------------
    # Chart generation
    # -----------------------------------------------------------------------

    def _generate(self) -> None:
        if self._generating:
            return
        if not self._files:
            messagebox.showwarning("No files", "Please add at least one CSV file.")
            return

        self._generating = True
        self._gen_btn.configure(state="disabled")
        self._open_btn.configure(state="disabled")
        self._progress.start(12)
        self._log_clear()

        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()

    def _run_generation(self) -> None:
        """Runs in a background thread. Posts results back via queue."""
        try:
            title     = self._title_var.get().strip() or "Benchmark Comparison"
            ft_col    = self._ft_col_var.get().strip() or None
            outdir    = Path(self._outdir_var.get().strip() or "charts_out")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            run_dir   = outdir / timestamp
            run_dir.mkdir(parents=True, exist_ok=True)

            labels  = [f["label"] for f in self._files]
            paths   = [f["path"]  for f in self._files]

            all_metrics:         list[dict]            = []
            frametimes_by_label: dict[str, np.ndarray] = {}
            gpu_busy_by_label:   dict[str, np.ndarray] = {}
            figs:                list[tuple[str, object]] = []  # (tab_title, Figure)
            used_col: str | None = None

            for label, path in zip(labels, paths):
                self._log(f"Loading  {path.name} …")
                ft, col, gpu_busy = bg.load_frametimes(path, ft_col)
                used_col = used_col or col
                if gpu_busy is not None:
                    gpu_busy_by_label[label] = gpu_busy

                metrics = bg.compute_metrics(ft)
                metrics["label"]   = label
                metrics["file"]    = path.name
                metrics["samples"] = len(ft)
                all_metrics.append(metrics)
                frametimes_by_label[label] = ft

                self._log(f"  {len(ft):,} samples | avg {metrics['avg_fps']:.1f} FPS | "
                          f"1% {metrics['one_pct_low']:.1f} | 0.1% {metrics['point1_pct_low']:.1f}")

                fig = bg.make_frametime_plot(
                    ft, f"{title} — {label} (Frametime)",
                    save_path=run_dir / f"{label}_frametime",
                )
                figs.append((f"Frametime: {label}", fig))

            # Comparison bar
            self._log("Generating comparison bar chart …")
            fig = bg.make_comparison_bar(all_metrics, labels, title,
                                          save_path=run_dir / "comparison_fps")
            figs.append(("Comparison", fig))

            # Frametime distribution
            self._log("Generating distribution histogram …")
            fig = bg.make_distribution_plot(frametimes_by_label,
                                             f"{title} — Frametime Distribution",
                                             save_path=run_dir / "frametime_distribution")
            figs.append(("Distribution", fig))

            # GPU Busy (optional)
            if gpu_busy_by_label:
                self._log("Generating GPU Busy chart …")
                fig = bg.make_gpu_busy_line(gpu_busy_by_label, f"{title} — GPU Busy",
                                             save_path=run_dir / "comparison_gpu_busy")
                figs.append(("GPU Busy", fig))
            else:
                self._log("  (no MsGPUBusy column found — skipping GPU chart)", tag="dim")

            # Summary CSV
            pd.DataFrame(all_metrics).to_csv(run_dir / "summary.csv", index=False)
            self._log(f"Wrote summary.csv + charts to:  {run_dir.resolve()}", tag="ok")

            # Send results to main thread
            self._log_queue.put(("__done__", figs, run_dir))

        except Exception as exc:
            self._log(f"Error: {exc}", tag="error")
            self._log_queue.put(("__error__",))

    # -----------------------------------------------------------------------
    # Log helpers (thread-safe: write to queue, read in main thread)
    # -----------------------------------------------------------------------

    def _log(self, msg: str, tag: str = "") -> None:
        self._log_queue.put(("__msg__", msg, tag))

    def _log_clear(self) -> None:
        self._log_queue.put(("__clear__",))

    def _poll_log(self) -> None:
        """Called repeatedly in the main thread to flush the log queue."""
        try:
            while True:
                item = self._log_queue.get_nowait()
                kind = item[0]

                if kind == "__clear__":
                    self._log_widget_write("", clear=True)

                elif kind == "__msg__":
                    _, msg, tag = item
                    self._log_widget_write(msg + "\n", tag=tag)

                elif kind == "__done__":
                    _, figs, run_dir = item
                    self._on_generation_done(figs, run_dir)

                elif kind == "__error__":
                    self._on_generation_error()

        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_log)

    def _log_widget_write(self, text: str, tag: str = "", clear: bool = False) -> None:
        self._log.configure(state="normal")
        if clear:
            self._log.delete("1.0", "end")
        if text:
            if tag:
                self._log.insert("end", text, tag)
            else:
                self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    # -----------------------------------------------------------------------
    # Post-generation UI update (always on main thread via queue)
    # -----------------------------------------------------------------------

    def _on_generation_done(self, figs: list[tuple[str, object]], run_dir: Path) -> None:
        self._progress.stop()
        self._gen_btn.configure(state="normal")
        self._last_outdir = run_dir
        self._open_btn.configure(state="normal")
        self._generating = False

        # Rebuild notebook tabs with the new figures
        for tab in self._notebook.tabs():
            self._notebook.forget(tab)

        for tab_title, fig in figs:
            frame = ttk.Frame(self._notebook)
            self._notebook.add(frame, text=tab_title)

            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()

            toolbar = NavigationToolbar2Tk(canvas, frame, pack_toolbar=False)
            toolbar.configure(bg=BG_PANEL)
            toolbar.update()

            toolbar.pack(side="bottom", fill="x")
            canvas.get_tk_widget().pack(fill="both", expand=True)

        self._notebook.select(0)

    def _on_generation_error(self) -> None:
        self._progress.stop()
        self._gen_btn.configure(state="normal")
        self._generating = False

    def _open_output(self) -> None:
        if self._last_outdir and self._last_outdir.exists():
            open_folder(self._last_outdir)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
