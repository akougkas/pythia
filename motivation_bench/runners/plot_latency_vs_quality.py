#!/usr/bin/env python3
"""
plot_latency_vs_quality.py — Latency vs. quality plots for motivation_outputs

Joins:
  - <run-dir>/grades/summary.csv      — produced by eval_motivation_plans.py
  - <run-dir>/runs.jsonl              — produced by dispatch_runner.py

Produces two figures under <run-dir>/grades/:
  - latency_vs_quality_mean.png       headline: one point per model, mean
                                      across tasks, error bars = ±1 std,
                                      log-x latency, Pareto frontier
  - latency_vs_quality_per_task.png   small multiples: one panel per task,
                                      one dot per model

Usage:
    python plot_latency_vs_quality.py \\
        --run-dir /home/jye/publications/motivation_outputs/run_20260505T170532

Caveats:
  - The reference model (default claude-opus-4-7) is NOT in summary.csv (it's
    the gold). It is plotted as a vertical "reference latency" line on the
    mean figure for context.
  - Rows in summary.csv with a non-empty `error` column are dropped from the
    quality side; their latency is still shown but with an open marker.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

log = logging.getLogger("plot_latency_vs_quality")


# ─── Visual style ───────────────────────────────────────────────────────────

# Per-model colors. Anthropic family in blue; open-source in warm tones.
MODEL_STYLE: dict[str, dict] = {
    "claude-haiku-4-5":      dict(color="#9ecae1", marker="o", label="Claude Haiku 4.5"),
    "claude-sonnet-4-6":     dict(color="#4292c6", marker="o", label="Claude Sonnet 4.6"),
    "claude-opus-4-6":       dict(color="#08519c", marker="o", label="Claude Opus 4.6"),
    "claude-opus-4-7":       dict(color="#08306b", marker="*", label="Claude Opus 4.7 (ref)"),
    "gemma4_26b":            dict(color="#fdae6b", marker="s", label="Gemma 4 26B"),
    "gpt-oss_20b":           dict(color="#e6550d", marker="s", label="GPT-OSS 20B"),
    "mistral-small3.2_24b":  dict(color="#9e9ac8", marker="s", label="Mistral Small 3.2 24B"),
    "qwen3.5_9b":            dict(color="#74c476", marker="s", label="Qwen 3.5 9B"),
}

PROVIDER_OF: dict[str, str] = {
    "claude-haiku-4-5":      "anthropic",
    "claude-sonnet-4-6":     "anthropic",
    "claude-opus-4-6":       "anthropic",
    "claude-opus-4-7":       "anthropic",
    "gemma4_26b":            "ollama",
    "gpt-oss_20b":           "ollama",
    "mistral-small3.2_24b":  "ollama",
    "qwen3.5_9b":            "ollama",
}


# ─── Data loading ───────────────────────────────────────────────────────────

@dataclass
class Row:
    case: str
    model: str
    provider: str
    quality: float | None     # overall_score from summary.csv (1-5)
    latency_s: float | None   # mean wall time across repeats from runs.jsonl
    grading_error: bool       # True if grade row had non-empty `error`


def _norm_model(name: str) -> str:
    """`gemma4:26b` (jsonl) → `gemma4_26b` (csv)."""
    return name.replace(":", "_")


def load_grades(csv_path: Path) -> dict[tuple[str, str], tuple[float | None, bool]]:
    """Returns (case, model) -> (overall_score_or_None, grading_error_flag)."""
    out: dict[tuple[str, str], tuple[float | None, bool]] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            key = (row["case_name"], row["model_name"])
            err = bool((row.get("error") or "").strip())
            score_s = (row.get("overall_score") or "").strip()
            try:
                score = float(score_s) if score_s else None
            except ValueError:
                score = None
            out[key] = (score, err)
    return out


def load_latencies(jsonl_path: Path) -> dict[tuple[str, str], tuple[float, str]]:
    """Returns (case, normalized_model) -> (mean_wall_s, provider).

    Aggregates over repeats with the mean.
    """
    bucket: dict[tuple[str, str], list[float]] = defaultdict(list)
    provider: dict[tuple[str, str], str] = {}
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            wall = d.get("duration_wall_s")
            if wall is None:
                continue
            case = d["case_id"]
            model = _norm_model(d["model_name"])
            key = (case, model)
            bucket[key].append(float(wall))
            provider[key] = d.get("provider", "")
    return {k: (float(np.mean(v)), provider[k]) for k, v in bucket.items()}


def join(grades, latencies, reference_model: str) -> list[Row]:
    rows: list[Row] = []
    seen_keys = set(grades) | set(latencies)
    for key in sorted(seen_keys):
        case, model = key
        score, gerr = grades.get(key, (None, False))
        lat_pair = latencies.get(key)
        if lat_pair is None:
            log.warning("No latency for %s / %s — skipping", case, model)
            continue
        lat, prov = lat_pair
        if not prov:
            prov = PROVIDER_OF.get(model, "")
        rows.append(Row(case=case, model=model, provider=prov,
                        quality=score, latency_s=lat,
                        grading_error=gerr))
    return rows


# ─── Pareto frontier ────────────────────────────────────────────────────────

def pareto_frontier(points: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Minimize latency, maximize quality. Returns non-dominated points
    sorted by latency ascending."""
    pts = [p for p in points if p[0] is not None and p[1] is not None]
    pts.sort(key=lambda p: (p[0], -p[1]))
    front: list[tuple[float, float, str]] = []
    best_q = -np.inf
    for x, y, lbl in pts:
        if y > best_q:
            front.append((x, y, lbl))
            best_q = y
    return front


# ─── Plot 1: model means ────────────────────────────────────────────────────

def plot_mean(rows: list[Row], reference_model: str,
              out_path: Path, show_pareto: bool = True) -> None:
    # Group by model
    by_model: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_model[r.model].append(r)

    fig, ax = plt.subplots(figsize=(8.5, 5.6))

    points_for_pareto: list[tuple[float, float, str]] = []
    for model, rs in sorted(by_model.items()):
        qs = [r.quality for r in rs if r.quality is not None]
        ls = [r.latency_s for r in rs if r.latency_s is not None]
        if not qs or not ls:
            continue
        q_mean, q_std = float(np.mean(qs)), float(np.std(qs, ddof=0))
        l_mean, l_std = float(np.mean(ls)), float(np.std(ls, ddof=0))

        style = MODEL_STYLE.get(model, dict(color="gray", marker="o", label=model))
        ax.errorbar(
            l_mean, q_mean,
            xerr=l_std, yerr=q_std,
            fmt=style["marker"],
            color=style["color"],
            markersize=10,
            markeredgecolor="black",
            markeredgewidth=0.8,
            ecolor=style["color"],
            elinewidth=1.0,
            capsize=3,
            label=style["label"],
            zorder=3,
        )
        points_for_pareto.append((l_mean, q_mean, style["label"]))

    if show_pareto and len(points_for_pareto) >= 2:
        front = pareto_frontier(points_for_pareto)
        if len(front) >= 2:
            xs = [p[0] for p in front]
            ys = [p[1] for p in front]
            ax.plot(xs, ys, "--", color="black", alpha=0.45,
                    linewidth=1.2, label="Pareto frontier", zorder=2)

    ax.set_xlabel("Plan-generation latency (s, mean across tasks)")
    ax.set_ylabel("Plan quality (overall score, 1–5; mean across tasks)")
    ax.set_ylim(0.8, 5.2)
    ax.set_xlim(left=0)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.set_title(
        f"Plan latency vs. quality — mean over {len({r.case for r in rows})} tasks (HPC-CG workload)\n"
        f"(reference: {reference_model})",
        fontsize=11,
    )
    ax.legend(loc="lower right", fontsize=8, ncol=1, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    log.info("wrote %s", out_path)


# ─── Plot 2: per-task small multiples ───────────────────────────────────────

def _short_case(c: str) -> str:
    """Trim `multi_gen_omp_26_reduce_product_of_inverses` → `omp_26 reduce/inv`."""
    s = c.removeprefix("multi_gen_")
    return s.replace("_", " ")


def plot_per_task(rows: list[Row], reference_model: str,
                  out_path: Path, show_pareto: bool = True) -> None:
    cases = sorted({r.case for r in rows})
    n = len(cases)
    ncols = 3 if n > 2 else n
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(5.0 * ncols, 4.0 * nrows),
                             squeeze=False)

    by_case: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_case[r.case].append(r)

    handles_for_legend: dict[str, plt.Line2D] = {}

    for idx, case in enumerate(cases):
        ax = axes[idx // ncols][idx % ncols]
        case_rows = by_case[case]

        points_for_pareto: list[tuple[float, float, str]] = []
        for r in case_rows:
            if r.quality is None or r.latency_s is None:
                continue
            style = MODEL_STYLE.get(
                r.model, dict(color="gray", marker="o", label=r.model)
            )
            face = "white" if r.grading_error else style["color"]
            h = ax.scatter(
                r.latency_s, r.quality,
                marker=style["marker"],
                c=face,
                edgecolors=style["color"],
                linewidths=1.2,
                s=70,
                label=style["label"],
                zorder=3,
            )
            handles_for_legend.setdefault(style["label"], h)
            points_for_pareto.append((r.latency_s, r.quality, style["label"]))

        if show_pareto and len(points_for_pareto) >= 2:
            front = pareto_frontier(points_for_pareto)
            if len(front) >= 2:
                xs = [p[0] for p in front]
                ys = [p[1] for p in front]
                ax.plot(xs, ys, "--", color="black",
                        alpha=0.4, linewidth=1.0, zorder=2)

        ax.set_ylim(0.8, 5.2)
        ax.set_xlim(left=0)
        ax.grid(True, alpha=0.25)
        ax.set_title(_short_case(case), fontsize=10)
        if idx % ncols == 0:
            ax.set_ylabel("Quality (1–5)")
        if idx // ncols == nrows - 1:
            ax.set_xlabel("Latency (s)")
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    # Hide unused panels
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    # Shared legend in the last empty cell, or below the figure
    legend_handles = list(handles_for_legend.values())
    legend_labels = list(handles_for_legend.keys())
    if n < nrows * ncols:
        leg_ax = axes[(nrows - 1)][ncols - 1]
        leg_ax.axis("off")
        leg_ax.legend(legend_handles, legend_labels,
                      loc="center", fontsize=9, framealpha=0.95,
                      title="Model")
    else:
        fig.legend(legend_handles, legend_labels,
                   loc="lower center", ncol=min(4, len(legend_labels)),
                   bbox_to_anchor=(0.5, -0.02), fontsize=9)

    fig.suptitle(
        f"Plan latency vs. quality, per task (reference: {reference_model}) - (HPC-CG workload)",
        fontsize=12, y=1.0,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    log.info("wrote %s", out_path)


# ─── Driver ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", type=Path, required=True,
                   help="motivation_outputs/run_<TS> dir with runs.jsonl + grades/summary.csv")
    p.add_argument("--reference-model", type=str, default="claude-opus-4-7")
    p.add_argument("--no-pareto", action="store_true",
                   help="Disable Pareto frontier overlay")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Where to write PNGs (default: <run-dir>/grades/)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    run_dir: Path = args.run_dir.resolve()
    csv_path = run_dir / "grades" / "summary.csv"
    jsonl_path = run_dir / "runs.jsonl"
    if not csv_path.exists():
        log.error("missing %s", csv_path); return 2
    if not jsonl_path.exists():
        log.error("missing %s", jsonl_path); return 2

    out_dir = (args.output_dir or run_dir / "grades").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    grades = load_grades(csv_path)
    latencies = load_latencies(jsonl_path)
    rows = join(grades, latencies, args.reference_model)
    log.info("Joined %d (case, model) rows across %d cases / %d models",
             len(rows),
             len({r.case for r in rows}),
             len({r.model for r in rows}))

    plot_mean(rows, args.reference_model,
              out_dir / "latency_vs_quality_mean.png",
              show_pareto=not args.no_pareto)
    plot_per_task(rows, args.reference_model,
                  out_dir / "latency_vs_quality_per_task.png",
                  show_pareto=not args.no_pareto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
