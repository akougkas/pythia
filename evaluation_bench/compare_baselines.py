"""Cross-baseline comparison for Pythia evaluation.

Reads multiple run summaries, computes deltas, and produces:
1. Comparison table (markdown + terminal)
2. Comparison figures (dispatch latency, hit rate, cost)
3. Detailed report saved to evaluation_bench/comparison_report.md

Usage:
  python evaluation_bench/compare_baselines.py evaluation_bench/workloads/hpc_cg/runs/

  Or specify runs explicitly:
  python evaluation_bench/compare_baselines.py \
    runs/20260329_pythia_5req runs/20260329_ns_5req runs/20260329_sh_5req
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.size": 11, "font.family": "serif",
    "axes.labelsize": 12, "axes.titlesize": 13,
    "legend.fontsize": 10, "figure.dpi": 150, "savefig.dpi": 300,
})

BASELINE_LABELS = {
    "pythia": "Pythia",
    "ns": "No Speculation",
    "sh": "Static Heuristic",
    "swol": "Spec. w/o Learning",
    "oracle": "Oracle",
}

BASELINE_COLORS = {
    "pythia": "#2563eb",
    "ns": "#ef4444",
    "sh": "#f59e0b",
    "swol": "#8b5cf6",
    "oracle": "#22c55e",
}

BASELINE_ORDER = ["ns", "sh", "swol", "pythia", "oracle"]


def find_runs(path: Path) -> dict[str, dict]:
    """Find all baseline runs in a directory."""
    runs = {}
    for d in sorted(path.glob("*_*req")):
        summary_f = d / "summary.json"
        if not summary_f.exists():
            continue
        with open(summary_f) as f:
            summary = json.load(f)
        bl = summary.get("baseline", "pythia")
        # Keep latest run per baseline
        runs[bl] = summary
        runs[bl]["_run_dir"] = str(d)
    return runs


def print_comparison_table(runs: dict[str, dict]):
    """Print comparison table to terminal."""
    ordered = [b for b in BASELINE_ORDER if b in runs]

    print(f"\n{'═'*90}")
    print(f"  CROSS-BASELINE COMPARISON")
    print(f"{'═'*90}")

    # Header
    header = f"{'Metric':<30s}"
    for b in ordered:
        header += f" {BASELINE_LABELS.get(b, b):>14s}"
    print(header)
    print("─" * 90)

    # Rows
    metrics = [
        ("Dispatch Latency (ms)", "mean_dispatch_latency_ms", "{:.0f}"),
        ("Solver Time (ms)", "mean_solver_ms", "{:.0f}"),
        ("Speculator Time (ms)", "mean_speculator_ms", "{:.1f}"),
        ("Pipeline Time (s)", "mean_pipeline_s", "{:.0f}"),
        ("Hit Rate (%)", "hit_rate", "{:.0%}"),
        ("Net Benefit", "net_benefit", "{:.1f}"),
        ("Wasted Compute (W)", "wasted_compute_ratio_W", "{:.3f}"),
        ("Convergence (N_conv)", "N_conv", "{:d}"),
        ("Total Tokens", "total_tokens", "{:,d}"),
        ("Total Cost (E)", "total_cost", "{:.4f}"),
        ("Mean Salvage (σ)", "mean_salvage_ratio", "{:.2f}"),
        ("Confidence (end)", "confidence_at_end", "{:.3f}"),
    ]

    for label, key, fmt in metrics:
        row = f"{label:<30s}"
        for b in ordered:
            val = runs[b].get(key, 0)
            if val is None:
                val = 0
            try:
                row += f" {fmt.format(val):>14s}"
            except (ValueError, TypeError):
                row += f" {str(val):>14s}"
        print(row)

    # Verdict breakdown
    print("─" * 90)
    print(f"{'Verdicts':<30s}")
    for b in ordered:
        v = runs[b].get("verdicts", {})
        vstr = ", ".join(f"{k}:{v}" for k, v in sorted(v.items()))
        print(f"  {BASELINE_LABELS.get(b, b)}: {vstr}")

    # Speedup vs NS
    if "ns" in runs and "pythia" in runs:
        ns_lat = runs["ns"].get("mean_dispatch_latency_ms", 1)
        py_lat = runs["pythia"].get("mean_dispatch_latency_ms", 1)
        print(f"\n  Pythia vs NS speedup: {ns_lat/py_lat:.1f}x dispatch latency")
        print(f"  Pythia vs NS pipeline: {runs['ns']['mean_pipeline_s']:.0f}s vs {runs['pythia']['mean_pipeline_s']:.0f}s")


def generate_comparison_figures(runs: dict[str, dict], output_dir: Path):
    """Generate comparison figures."""
    output_dir.mkdir(exist_ok=True)
    ordered = [b for b in BASELINE_ORDER if b in runs]
    labels = [BASELINE_LABELS.get(b, b) for b in ordered]
    colors = [BASELINE_COLORS.get(b, "#999") for b in ordered]
    x = np.arange(len(ordered))

    # ── Fig 1: Dispatch + Pipeline Latency (grouped bars, all baselines) ──
    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.35
    solver_s = [runs[b].get("mean_solver_ms", 0) / 1000 for b in ordered]
    pipeline_s = [runs[b].get("mean_pipeline_s", 0) for b in ordered]

    bars1 = ax.bar(x - width/2, solver_s, width, label="Dispatch Latency (s)",
                   color=[c for c in colors], alpha=0.85, edgecolor="white")
    bars2 = ax.bar(x + width/2, pipeline_s, width, label="Pipeline Latency (s)",
                   color=[c for c in colors], alpha=0.45, edgecolor="white", hatch="//")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=11)
    ax.set_ylabel("Time (seconds)", fontsize=12)
    ax.set_title("Dispatch vs Pipeline Latency — All Baselines (§6.2)", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.2, axis="y")

    for bar, val in zip(bars1, solver_s):
        ax.text(bar.get_x() + bar.get_width()/2, val + 3,
                f"{val:.0f}s", ha="center", fontsize=8, fontweight="bold")
    for bar, val in zip(bars2, pipeline_s):
        ax.text(bar.get_x() + bar.get_width()/2, val + 3,
                f"{val:.0f}s", ha="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_dir / "comparison_dispatch_vs_pipeline.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  comparison_dispatch_vs_pipeline.png")

    # ── Fig 2: Speculation Accuracy (only baselines that speculate) ──
    spec_baselines = [b for b in ordered if runs[b].get("hit_rate", 0) > 0 or b in ("swol", "pythia", "oracle")]
    spec_baselines = [b for b in spec_baselines if b not in ("ns", "sh")]
    if spec_baselines:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

        sx = np.arange(len(spec_baselines))
        slabels = [BASELINE_LABELS.get(b, b) for b in spec_baselines]
        scolors = [BASELINE_COLORS.get(b, "#999") for b in spec_baselines]

        # Hit rate
        hit_rates = [runs[b].get("hit_rate", 0) * 100 for b in spec_baselines]
        ax1.bar(sx, hit_rates, color=scolors, alpha=0.85, width=0.5)
        ax1.set_xticks(sx)
        ax1.set_xticklabels(slabels, rotation=15, ha="right")
        ax1.set_ylabel("Hit Rate (%)")
        ax1.set_title("Speculation Hit Rate (§6.3)")
        ax1.set_ylim(0, 115)
        ax1.grid(True, alpha=0.2, axis="y")
        for i, v in enumerate(hit_rates):
            ax1.text(i, v + 2, f"{v:.0f}%", ha="center", fontsize=11, fontweight="bold")

        # Salvage ratio
        salvage = [runs[b].get("mean_salvage_ratio", 0) for b in spec_baselines]
        ax2.bar(sx, salvage, color=scolors, alpha=0.85, width=0.5)
        ax2.set_xticks(sx)
        ax2.set_xticklabels(slabels, rotation=15, ha="right")
        ax2.set_ylabel("Mean Salvage Ratio (σ)")
        ax2.set_title("Salvage Ratio — Reusable Work (§3.3)")
        ax2.set_ylim(0, 1.15)
        ax2.grid(True, alpha=0.2, axis="y")
        for i, v in enumerate(salvage):
            ax2.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=11, fontweight="bold")

        fig.tight_layout()
        fig.savefig(output_dir / "comparison_speculation_accuracy.png", bbox_inches="tight")
        plt.close(fig)
        print(f"  comparison_speculation_accuracy.png")

    # ── Fig 3: Cost Analysis — Net Benefit + Wasted Compute ──
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    net_benefit = [runs[b].get("net_benefit", 0) for b in ordered]
    ax1.bar(x, net_benefit, color=colors, alpha=0.85, width=0.5)
    ax1.axhline(y=0, color="black", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=15, ha="right")
    ax1.set_ylabel("Net Benefit")
    ax1.set_title("Net Benefit (§6.4)")
    ax1.grid(True, alpha=0.2, axis="y")
    for i, v in enumerate(net_benefit):
        ax1.text(i, v + 0.1, f"{v:.1f}", ha="center", fontsize=10, fontweight="bold")

    wasted = [runs[b].get("wasted_compute_ratio_W", 0) for b in ordered]
    ax2.bar(x, wasted, color=colors, alpha=0.85, width=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=15, ha="right")
    ax2.set_ylabel("Wasted Compute Ratio (W)")
    ax2.set_title("Wasted Compute (§6.4)")
    ax2.grid(True, alpha=0.2, axis="y")
    for i, v in enumerate(wasted):
        ax2.text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_dir / "comparison_cost.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  comparison_cost.png")

    # Fig 3: Pipeline time (end-to-end including agent execution)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pipeline_s = [runs[b].get("mean_pipeline_s", 0) for b in ordered]
    ax.bar(x, pipeline_s, color=colors, alpha=0.85, width=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Mean Pipeline Time (seconds)")
    ax.set_title("End-to-End Pipeline Latency")
    ax.grid(True, alpha=0.2, axis="y")
    for i, v in enumerate(pipeline_s):
        ax.text(i, v + 5, f"{v:.0f}s", ha="center", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_dir / "comparison_pipeline.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  comparison_pipeline.png")


def generate_report(runs: dict[str, dict], output_path: Path):
    """Generate markdown comparison report."""
    ordered = [b for b in BASELINE_ORDER if b in runs]

    lines = ["# Baseline Comparison Report", ""]
    lines.append(f"**Date**: {__import__('time').strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Baselines**: {', '.join(BASELINE_LABELS.get(b, b) for b in ordered)}")
    lines.append("")

    # Table
    lines.append("## Summary Table")
    lines.append("")
    header = "| Metric |"
    sep = "|--------|"
    for b in ordered:
        header += f" {BASELINE_LABELS.get(b, b)} |"
        sep += "--------|"
    lines.append(header)
    lines.append(sep)

    metrics = [
        ("Solver Latency (ms)", "mean_solver_ms", "{:.0f}"),
        ("Speculator Latency (ms)", "mean_speculator_ms", "{:.1f}"),
        ("Hit Rate", "hit_rate", "{:.0%}"),
        ("Net Benefit", "net_benefit", "{:.1f}"),
        ("Wasted Compute (W)", "wasted_compute_ratio_W", "{:.3f}"),
        ("Convergence (N_conv)", "N_conv", "{}"),
        ("Total Tokens", "total_tokens", "{:,}"),
        ("Total Cost (E)", "total_cost", "{:.4f}"),
        ("Mean Salvage (σ)", "mean_salvage_ratio", "{:.2f}"),
        ("Pipeline Time (s)", "mean_pipeline_s", "{:.0f}"),
    ]

    for label, key, fmt in metrics:
        row = f"| {label} |"
        for b in ordered:
            val = runs[b].get(key, 0) or 0
            try:
                row += f" {fmt.format(val)} |"
            except (ValueError, TypeError):
                row += f" {val} |"
        lines.append(row)

    lines.append("")

    # Verdicts
    lines.append("## Verdict Distribution")
    lines.append("")
    for b in ordered:
        v = runs[b].get("verdicts", {})
        lines.append(f"- **{BASELINE_LABELS.get(b, b)}**: {v}")
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    if "ns" in runs and "pythia" in runs:
        ns = runs["ns"]
        py = runs["pythia"]
        lines.append(f"- Pythia reduces dispatch latency from {ns['mean_solver_ms']:.0f}ms (NS) — "
                     f"speculation hides solver latency")
        lines.append(f"- Hit rate: {py['hit_rate']:.0%} — {py['hit_rate']*100:.0f}% of predictions are usable")
        lines.append(f"- Net benefit: {py['net_benefit']:.1f} (system is {'profitable' if py['net_benefit'] > 0 else 'unprofitable'})")
        lines.append(f"- Wasted compute: {py['wasted_compute_ratio_W']:.1%}")
    if "sh" in runs:
        sh = runs["sh"]
        lines.append(f"- Static Heuristic solver time: {sh['mean_solver_ms']:.0f}ms (fast but no LLM reasoning)")
    if "swol" in runs and "pythia" in runs:
        swol = runs["swol"]
        py = runs["pythia"]
        lines.append(f"- Learning adds {(py['hit_rate'] - swol['hit_rate'])*100:.0f} percentage points to hit rate")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n  Report: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_baselines.py <runs_directory_or_run_dirs...>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if (path / "summary.json").exists():
        # Individual run dirs specified
        runs = {}
        for arg in sys.argv[1:]:
            p = Path(arg)
            if (p / "summary.json").exists():
                with open(p / "summary.json") as f:
                    s = json.load(f)
                bl = s.get("baseline", "pythia")
                runs[bl] = s
                runs[bl]["_run_dir"] = str(p)
    else:
        # Directory containing runs
        runs = find_runs(path)

    if not runs:
        print("No runs found")
        sys.exit(1)

    print(f"Found {len(runs)} baseline runs: {list(runs.keys())}")

    print_comparison_table(runs)

    # Generate figures
    output_dir = path if path.is_dir() and not (path / "summary.json").exists() else path.parent
    plot_dir = output_dir / "comparison_plots"
    print(f"\nGenerating comparison figures → {plot_dir}/")
    generate_comparison_figures(runs, plot_dir)

    # Generate report
    report_path = output_dir / "comparison_report.md"
    generate_report(runs, report_path)


if __name__ == "__main__":
    main()
