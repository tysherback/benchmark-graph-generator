"""
benchmark_graph.py — Core logic for PresentMon / CapFrameX CSV analysis.

Can be used as a CLI:
    python benchmark_graph.py run1.csv run2.csv --labels 16GB 32GB --title "BF6 RAM"

Or imported by gui.py for embedded chart rendering.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


# ----------------------------
# Helpers
# ----------------------------

def find_frametime_column(df: pd.DataFrame) -> str:
    """Try common PresentMon / CapFrameX frametime column names."""
    candidates = [
        "MsBetweenPresents",
        "MsBetweenDisplayChange",
        "MsBetweenSimulationStart",
        "MsInPresentAPI",
        "FrametimeMS",
        "FrameTimeMs",
        "frametime_ms",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(
        "Couldn't find a frametime column.\n"
        f"Columns found (first 30): {list(df.columns)[:30]}\n"
        "Use the 'Frametime column' field to specify the correct column name."
    )


def load_frametimes(
    csv_path: Path, frametime_col: str | None = None
) -> tuple[np.ndarray, str, np.ndarray | None]:
    """
    Load a PresentMon/CapFrameX CSV and return
    (frametime_ms_array, used_column_name, gpu_busy_array_or_None).

    CapFrameX files start with a comment line (//Ignore=true), so we skip row 0.
    """
    df = pd.read_csv(csv_path, skiprows=1)
    col = frametime_col or find_frametime_column(df)

    ft = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy()
    ft = ft[(ft > 0) & (ft < 1000)]  # discard obviously bad samples

    if len(ft) < 100:
        raise ValueError(f"{csv_path.name}: not enough valid samples after cleanup ({len(ft)}).")

    gpu_busy: np.ndarray | None = None
    if "MsGPUBusy" in df.columns:
        vals = pd.to_numeric(df["MsGPUBusy"], errors="coerce").dropna().to_numpy()
        if len(vals) > 0:
            gpu_busy = vals

    return ft, col, gpu_busy


def compute_metrics(frametime_ms: np.ndarray) -> dict[str, float]:
    """
    Compute review-friendly metrics from per-frame frametime samples.

    1%/0.1% lows = mean of the slowest 1% (0.1%) of FPS samples.
    """
    fps = 1000.0 / frametime_ms
    avg_fps = float(np.mean(fps))

    fps_sorted = np.sort(fps)          # ascending: worst FPS first
    n = len(fps_sorted)
    n_1pct  = max(1, int(np.floor(n * 0.01)))
    n_01pct = max(1, int(np.floor(n * 0.001)))

    one_pct_low    = float(np.mean(fps_sorted[:n_1pct]))
    point1_pct_low = float(np.mean(fps_sorted[:n_01pct]))

    p95_ft = float(np.percentile(frametime_ms, 95))
    p99_ft = float(np.percentile(frametime_ms, 99))

    over_16_7 = float(np.mean(frametime_ms > 16.67) * 100.0)
    over_33_3 = float(np.mean(frametime_ms > 33.33) * 100.0)
    over_50_0 = float(np.mean(frametime_ms > 50.0)  * 100.0)

    return {
        "avg_fps":                 avg_fps,
        "one_pct_low":             one_pct_low,
        "point1_pct_low":          point1_pct_low,
        "p95_frametime_ms":        p95_ft,
        "p99_frametime_ms":        p99_ft,
        "pct_frames_over_16_7ms":  over_16_7,
        "pct_frames_over_33_3ms":  over_33_3,
        "pct_frames_over_50ms":    over_50_0,
    }


# ----------------------------
# Style
# ----------------------------

PALETTE = ["#e43f64", "#2daae9", "#c680cf"]

DARK_STYLE: dict = {
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Inter", "Segoe UI", "Arial", "DejaVu Sans"],
    "font.weight":       "light",
    "figure.facecolor":  "#1a1a2e",
    "axes.facecolor":    "#16213e",
    "axes.edgecolor":    "#444466",
    "axes.labelcolor":   "#ccccdd",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.color":       "#ccccdd",
    "ytick.color":       "#ccccdd",
    "text.color":        "#ccccdd",
    "grid.color":        "#2a2a4a",
    "grid.linestyle":    "--",
    "grid.linewidth":    0.5,
    "legend.facecolor":  "#1a1a2e",
    "legend.edgecolor":  "#444466",
}


# ----------------------------
# Save helper
# ----------------------------

def _save_figure(fig: Figure, save_path: Path) -> None:
    """Save fig as PNG (always) and SVG (best-effort — backend may not be bundled)."""
    fig.savefig(save_path.with_suffix(".png"), dpi=200)
    try:
        fig.savefig(save_path.with_suffix(".svg"))
    except Exception:
        pass  # SVG backend not available (e.g. in PyInstaller bundle without it)


# ----------------------------
# Chart functions
# Each returns the Figure so callers can embed or display it.
# Pass save_path to also write PNG + SVG to disk.
# ----------------------------

def make_frametime_plot(
    frametime_ms: np.ndarray,
    title: str,
    save_path: Path | None = None,
) -> Figure:
    """Single-run frametime line chart (used by the CLI)."""
    return make_frametime_combined(
        {"": frametime_ms}, title, save_path, _single=True
    )


def make_frametime_combined(
    frametimes_by_label: dict[str, np.ndarray],
    title: str,
    save_path: Path | None = None,
    _single: bool = False,
) -> Figure:
    """Overlaid frametime line chart — all runs on one graph, y-axis 0–60 ms."""
    all_ft = np.concatenate(list(frametimes_by_label.values()))
    y_max = 60.0
    total_clipped = int(np.sum(all_ft > y_max))

    with plt.rc_context(DARK_STYLE):
        fig, ax = plt.subplots(figsize=(12, 5))

        for (label, ft), color in zip(frametimes_by_label.items(), PALETTE * 10):
            x = np.arange(len(ft))
            mean_ft = float(np.mean(ft))
            lbl = "" if _single else label
            ax.plot(x, ft, color=color, linewidth=0.8, alpha=0.5, label=lbl or None)
            ax.axhline(mean_ft, color=color, linestyle="-", linewidth=1.2, alpha=0.55,
                       label=f"{lbl+' ' if lbl else ''}avg {mean_ft:.2f} ms  ({1000/mean_ft:.1f} FPS)")

        ax.axhline(16.67, color="#888899", linestyle="--", linewidth=0.9, label="16.7 ms (60 FPS)")
        ax.axhline(33.33, color="#666677", linestyle="--", linewidth=0.9, label="33.3 ms (30 FPS)")

        ax.set_ylim(bottom=0, top=y_max)
        ax.set_title(title)
        ax.set_xlabel("Frame")
        ax.set_ylabel("Frametime (ms) — lower is better, consistent is best")
        ax.yaxis.grid(True)

        clip_note = (
            f"{total_clipped} spike{'s' if total_clipped != 1 else ''} above 60 ms hidden"
            if total_clipped else "y-axis: 0 – 60 ms"
        )
        ax.legend(fontsize=8, title=clip_note, title_fontsize=7)
        fig.tight_layout()

        if save_path is not None:
            _save_figure(fig, save_path)

    return fig


def make_comparison_bar(
    all_metrics: list[dict],
    labels: list[str],
    title: str,
    save_path: Path | None = None,
) -> Figure:
    """Horizontal grouped bar chart: Average FPS, 1% Low, 0.1% Low per run."""
    height  = 0.09   # bar thickness
    spacing = 0.42   # centre-to-centre distance between run groups
    y = np.arange(len(labels)) * spacing

    avg   = [m["avg_fps"]        for m in all_metrics]
    low1  = [m["one_pct_low"]    for m in all_metrics]
    low01 = [m["point1_pct_low"] for m in all_metrics]

    fig_h = max(4.5, len(labels) * 1.2 + 2.0)

    with plt.rc_context(DARK_STYLE):
        fig, ax = plt.subplots(figsize=(10, fig_h))
        b1 = ax.barh(y - height, avg,   height, label="Average FPS", color=PALETTE[0])
        b2 = ax.barh(y,          low1,  height, label="1% Low",      color=PALETTE[1])
        b3 = ax.barh(y + height, low01, height, label="0.1% Low",    color=PALETTE[2])

        for bars in (b1, b2, b3):
            ax.bar_label(bars, fmt="%.0f", padding=4, fontsize=7, color="#ccccdd")

        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_ylim(y[0] - spacing * 0.6, y[-1] + spacing * 0.6)
        ax.set_title(title)
        ax.set_xlabel("FPS — higher is better")
        ax.xaxis.grid(True)
        ax.yaxis.grid(False)
        ax.legend()
        fig.tight_layout()

        if save_path is not None:
            _save_figure(fig, save_path)

    return fig


def make_gpu_busy_line(
    gpu_busy_by_label: dict[str, np.ndarray],
    title: str,
    save_path: Path | None = None,
) -> Figure:
    """Overlaid MsGPUBusy line chart — all runs on one graph, y-axis 0–60 ms."""
    y_max = 60.0

    with plt.rc_context(DARK_STYLE):
        fig, ax = plt.subplots(figsize=(12, 5))

        for (label, vals), color in zip(gpu_busy_by_label.items(), PALETTE * 10):
            x    = np.arange(len(vals))
            mean = float(vals.mean())
            ax.plot(x, vals, color=color, linewidth=0.8, alpha=0.5,
                    label=f"{label}  (mean {mean:.1f} ms)")
            ax.axhline(mean, color=color, linestyle="-", linewidth=1.2, alpha=0.5)

        ax.set_ylim(bottom=0, top=y_max)
        ax.set_title(title)
        ax.set_xlabel("Frame")
        ax.set_ylabel("GPU Busy (ms) — lower is better, consistent is best")
        ax.yaxis.grid(True)
        ax.legend(fontsize=8)
        fig.tight_layout()

        if save_path is not None:
            _save_figure(fig, save_path)

    return fig


def make_distribution_plot(
    frametime_ms_by_label: dict[str, np.ndarray],
    title: str,
    save_path: Path | None = None,
    bins: int = 120,
) -> Figure:
    """Overlaid frametime distribution histogram (useful for stutter/tails)."""
    all_ft = np.concatenate(list(frametime_ms_by_label.values()))
    lo = max(0.0, float(np.percentile(all_ft, 0.5)))
    hi = max(float(np.percentile(all_ft, 99.5)), 40.0)

    with plt.rc_context(DARK_STYLE):
        fig, ax = plt.subplots(figsize=(10, 5))

        for (label, ft), color in zip(frametime_ms_by_label.items(), PALETTE):
            ax.hist(ft, bins=bins, range=(lo, hi), alpha=0.45, label=label, color=color)

        ax.set_title(title)
        ax.set_xlabel("Frametime (ms) — lower is better, consistent is best")
        ax.set_ylabel("Frames (count)")
        ax.yaxis.grid(True)
        ax.legend()
        fig.tight_layout()

        if save_path is not None:
            _save_figure(fig, save_path)

    return fig


# ----------------------------
# CLI entry point (unchanged behaviour)
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate publication-ready charts from PresentMon/CapFrameX CSVs."
    )
    ap.add_argument("csv", nargs="+",
                    help="One or more CSV files (e.g., run1.csv run2.csv run3.csv)")
    ap.add_argument("--labels", nargs="+", default=None,
                    help="Labels for each CSV. Defaults to filenames if omitted or count mismatches.")
    ap.add_argument("--title", default="Benchmark Comparison", help="Chart title")
    ap.add_argument("--outdir", default="charts_out",
                    help="Parent output directory (a timestamped subfolder is created each run)")
    ap.add_argument("--frametime-col", default=None,
                    help="Override frametime column name (e.g., MsBetweenPresents)")
    args = ap.parse_args()

    csv_paths = [Path(p) for p in args.csv]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    outdir    = Path(args.outdir) / timestamp
    outdir.mkdir(parents=True, exist_ok=True)

    labels = args.labels
    if not labels or len(labels) != len(csv_paths):
        labels = [p.stem for p in csv_paths]

    all_metrics:           list[dict]               = []
    frametimes_by_label:   dict[str, np.ndarray]    = {}
    gpu_busy_by_label:     dict[str, np.ndarray]    = {}
    used_col: str | None = None

    for label, path in zip(labels, csv_paths):
        ft, col, gpu_busy = load_frametimes(path, args.frametime_col)
        used_col = used_col or col
        if gpu_busy is not None:
            gpu_busy_by_label[label] = gpu_busy

        metrics = compute_metrics(ft)
        metrics["label"]   = label
        metrics["file"]    = path.name
        metrics["samples"] = len(ft)
        all_metrics.append(metrics)
        frametimes_by_label[label] = ft

        fig = make_frametime_plot(ft, f"{args.title} — {label} (Frametime)",
                                  save_path=outdir / f"{label}_frametime")
        plt.close(fig)

    print(f"Frametime column: {used_col}")
    print("-" * 90)
    for m in all_metrics:
        print(
            f"{m['label']:>12} | "
            f"Avg {m['avg_fps']:.1f} | 1% {m['one_pct_low']:.1f} | "
            f"0.1% {m['point1_pct_low']:.1f} | "
            f"P99ms {m['p99_frametime_ms']:.2f} | "
            f">%16.7ms {m['pct_frames_over_16_7ms']:.2f}% | "
            f">%33.3ms {m['pct_frames_over_33_3ms']:.2f}%"
        )
    print("-" * 90)

    pd.DataFrame(all_metrics).to_csv(outdir / "summary.csv", index=False)

    fig = make_comparison_bar(all_metrics, labels, args.title,
                              save_path=outdir / "comparison_fps")
    plt.close(fig)

    if gpu_busy_by_label:
        fig = make_gpu_busy_line(gpu_busy_by_label, f"{args.title} — GPU Busy",
                                 save_path=outdir / "comparison_gpu_busy")
        plt.close(fig)
    else:
        print("Note: no MsGPUBusy column found in any CSV — skipping GPU chart.")

    fig = make_distribution_plot(frametimes_by_label, f"{args.title} — Frametime Distribution",
                                 save_path=outdir / "frametime_distribution")
    plt.close(fig)

    print(f"Wrote charts to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
