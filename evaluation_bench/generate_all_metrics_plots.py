"""Generate comprehensive metrics plots across all workloads.

Produces publication-quality figures covering all 7 paper metrics
across HPC-CG, RWA, and SDP workloads with all 5 baselines.

Output: evaluation_bench/all_metrics_plots/

Figures:
  01 — Cross-workload pipeline latency comparison
  02 — Cross-workload dispatch latency breakdown
  03 — Speculation accuracy across workloads (hit rate + salvage)
  04 — Cost analysis across workloads (net benefit + wasted compute)
  05 — Learner confidence progression per workload
  06 — Verdict distribution heatmap
  07 — Q metric: dispatch quality comparison
  08 — Tokens and cost efficiency
  09 — Mode distribution across workloads
  10 — Summary dashboard (all key metrics in one figure)
"""

import json
import sys
from pathlib import Path
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

plt.rcParams.update({
    "font.size": 11, "font.family": "serif",
    "axes.labelsize": 12, "axes.titlesize": 13,
    "legend.fontsize": 10, "xtick.labelsize": 10, "ytick.labelsize": 10,
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.pad_inches": 0.15,
})

BASE = Path(__file__).parent
PLOT_DIR = BASE / "all_metrics_plots"
PLOT_DIR.mkdir(exist_ok=True)

WORKLOADS = ["hpc_cg", "rwa", "sdp"]
WORKLOAD_LABELS = {"hpc_cg": "HPC-CG", "rwa": "RWA", "sdp": "SDP"}
BASELINE_ORDER = ["ns", "sh", "swol", "pythia", "oracle"]
BASELINE_LABELS = {
    "ns": "No Spec.", "sh": "Static Heur.", "swol": "Spec. w/o Learn.",
    "pythia": "Pythia", "oracle": "Oracle",
}
BASELINE_COLORS = {
    "ns": "#ef4444", "sh": "#f59e0b", "swol": "#8b5cf6",
    "pythia": "#2563eb", "oracle": "#22c55e",
}
WORKLOAD_COLORS = {"hpc_cg": "#2563eb", "rwa": "#f59e0b", "sdp": "#22c55e"}


def load_all_runs() -> dict:
    """Load summaries for all workloads × baselines."""
    data = {}
    for w in WORKLOADS:
        data[w] = {}
        runs_dir = BASE / f"workloads/{w}/runs"
        for d in sorted(runs_dir.glob("*_*req")):
            sf = d / "summary.json"
            if not sf.exists():
                continue
            with open(sf) as f:
                s = json.load(f)
            bl = s.get("baseline", "pythia")
            data[w][bl] = s
            # Also load events
            af = d / "all_results.json"
            if af.exists():
                with open(af) as f:
                    data[w][bl]["_events"] = json.load(f).get("events", [])
            data[w][bl]["_dir"] = str(d)
    return data


def get_val(data, workload, baseline, key, default=0):
    return data.get(workload, {}).get(baseline, {}).get(key, default) or default


# ═══════════════════════════════════════════════════
# Fig 01: Cross-workload Pipeline Latency
# ═══════════════════════════════════════════════════

def plot_01_pipeline_latency(data):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    for idx, w in enumerate(WORKLOADS):
        ax = axes[idx]
        baselines = [b for b in BASELINE_ORDER if b in data[w]]
        vals = [get_val(data, w, b, "mean_pipeline_s") for b in baselines]
        colors = [BASELINE_COLORS[b] for b in baselines]
        labels = [BASELINE_LABELS[b] for b in baselines]

        bars = ax.bar(range(len(baselines)), vals, color=colors, alpha=0.85, width=0.6)
        ax.set_xticks(range(len(baselines)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
        ax.set_title(WORKLOAD_LABELS[w], fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.2, axis="y")

        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, val + 5,
                    f"{val:.0f}s", ha="center", fontsize=9, fontweight="bold")

    axes[0].set_ylabel("Mean Pipeline Time (seconds)")
    fig.suptitle("End-to-End Pipeline Latency Across Workloads (§6.2)", fontsize=15, y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "01_pipeline_latency.png", bbox_inches="tight")
    plt.close(fig)
    print("  01_pipeline_latency.png")


# ═══════════════════════════════════════════════════
# Fig 02: Dispatch vs Pipeline (grouped, all workloads)
# ═══════════════════════════════════════════════════

def plot_02_dispatch_breakdown(data):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    for idx, w in enumerate(WORKLOADS):
        ax = axes[idx]
        baselines = [b for b in BASELINE_ORDER if b in data[w]]
        dispatch_s = [get_val(data, w, b, "mean_solver_ms") / 1000 for b in baselines]
        pipeline_s = [get_val(data, w, b, "mean_pipeline_s") for b in baselines]
        colors = [BASELINE_COLORS[b] for b in baselines]
        labels = [BASELINE_LABELS[b] for b in baselines]

        x = np.arange(len(baselines))
        width = 0.35
        ax.bar(x - width/2, dispatch_s, width, color=colors, alpha=0.9,
               label="Dispatch" if idx == 0 else "")
        ax.bar(x + width/2, pipeline_s, width, color=colors, alpha=0.35,
               hatch="//", label="Pipeline" if idx == 0 else "")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
        ax.set_title(WORKLOAD_LABELS[w], fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.2, axis="y")

    axes[0].set_ylabel("Time (seconds)")
    axes[0].legend(fontsize=11, loc="upper left")
    fig.suptitle("Dispatch vs Pipeline Latency (§6.2)", fontsize=15, y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "02_dispatch_breakdown.png", bbox_inches="tight")
    plt.close(fig)
    print("  02_dispatch_breakdown.png")


# ═══════════════════════════════════════════════════
# Fig 03: Speculation Accuracy (only speculating baselines)
# ═══════════════════════════════════════════════════

def plot_03_speculation_accuracy(data):
    spec_baselines = ["swol", "pythia", "oracle"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Hit rate grouped by workload
    ax = axes[0]
    x = np.arange(len(WORKLOADS))
    width = 0.25
    for i, bl in enumerate(spec_baselines):
        vals = [get_val(data, w, bl, "hit_rate") * 100 for w in WORKLOADS]
        bars = ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
                      color=BASELINE_COLORS[bl], alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                    f"{val:.0f}%", ha="center", fontsize=9)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Speculation Hit Rate (§6.3)")
    ax.set_ylim(0, 115)
    ax.legend()
    ax.grid(True, alpha=0.2, axis="y")

    # Salvage ratio grouped by workload
    ax = axes[1]
    for i, bl in enumerate(spec_baselines):
        vals = [get_val(data, w, bl, "mean_salvage_ratio") for w in WORKLOADS]
        bars = ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
                      color=BASELINE_COLORS[bl], alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, val + 0.02,
                    f"{val:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Salvage Ratio (σ)")
    ax.set_title("Reusable Work After Reconciliation (§3.3)")
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(PLOT_DIR / "03_speculation_accuracy.png", bbox_inches="tight")
    plt.close(fig)
    print("  03_speculation_accuracy.png")


# ═══════════════════════════════════════════════════
# Fig 04: Cost Analysis (net benefit + wasted compute)
# ═══════════════════════════════════════════════════

def plot_04_cost_analysis(data):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Net benefit grouped by workload
    ax = axes[0]
    x = np.arange(len(WORKLOADS))
    width = 0.15
    for i, bl in enumerate(BASELINE_ORDER):
        vals = [get_val(data, w, bl, "net_benefit") for w in WORKLOADS]
        ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Net Benefit")
    ax.set_title("Net Benefit (§6.4)")
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.legend(fontsize=8, ncol=3, loc="upper left")
    ax.grid(True, alpha=0.2, axis="y")

    # Wasted compute — only speculating baselines
    ax = axes[1]
    spec_baselines = ["swol", "pythia", "oracle"]
    width = 0.25
    for i, bl in enumerate(spec_baselines):
        vals = [get_val(data, w, bl, "wasted_compute_ratio_W") for w in WORKLOADS]
        bars = ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
                      color=BASELINE_COLORS[bl], alpha=0.85)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, val + 0.005,
                        f"{val:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Wasted Compute Ratio (W)")
    ax.set_title("Wasted Compute (§6.4)")
    ax.legend()
    ax.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(PLOT_DIR / "04_cost_analysis.png", bbox_inches="tight")
    plt.close(fig)
    print("  04_cost_analysis.png")


# ═══════════════════════════════════════════════════
# Fig 05: Learner Confidence Progression
# ═══════════════════════════════════════════════════

def plot_05_learner_confidence(data):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

    for idx, w in enumerate(WORKLOADS):
        ax = axes[idx]
        pythia = data[w].get("pythia", {})
        events = pythia.get("_events", [])
        if not events:
            ax.set_title(WORKLOAD_LABELS[w])
            continue

        n = len(events)
        x = range(1, n + 1)
        conf = [e.get("learner_confidence", 0) for e in events]
        modes = [e.get("speculator_mode", 1) for e in events]

        # Mode background
        mode_colors = {1: "#fee2e2", 2: "#fef3c7", 3: "#dcfce7"}
        for i, m in enumerate(modes):
            ax.axvspan(i + 0.5, i + 1.5, color=mode_colors.get(m, "#f0f0f0"), alpha=0.5)

        ax.plot(x, conf, color="#8b5cf6", linewidth=2.5, marker="o", markersize=6,
                zorder=5, label="Confidence")
        ax.axhline(y=0.5, color="#f59e0b", linestyle="--", linewidth=1.5, alpha=0.7, label="τ₂ = 0.5")
        ax.axhline(y=0.8, color="#22c55e", linestyle="--", linewidth=1.5, alpha=0.7, label="τ₃ = 0.8")

        ax.set_title(WORKLOAD_LABELS[w], fontsize=14, fontweight="bold")
        ax.set_xlabel("Interaction")
        ax.set_xlim(0.5, n + 0.5)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.2)
        if idx == 0:
            ax.legend(fontsize=9, loc="lower right")

    axes[0].set_ylabel("Learner Confidence")
    fig.suptitle("Learner Confidence Progression — Pythia (§4.2, §6.3)", fontsize=15, y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "05_learner_confidence.png", bbox_inches="tight")
    plt.close(fig)
    print("  05_learner_confidence.png")


# ═══════════════════════════════════════════════════
# Fig 06: Verdict Distribution Heatmap
# ═══════════════════════════════════════════════════

def plot_06_verdict_heatmap(data):
    spec_baselines = ["swol", "pythia", "oracle"]
    verdicts_list = ["COMMIT", "PARTIAL", "FLUSH"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    for idx, w in enumerate(WORKLOADS):
        ax = axes[idx]
        matrix = []
        for bl in spec_baselines:
            v = data[w].get(bl, {}).get("verdicts", {})
            row = [v.get(vd, 0) for vd in verdicts_list]
            matrix.append(row)

        matrix = np.array(matrix)
        im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=5)

        ax.set_xticks(range(len(verdicts_list)))
        ax.set_xticklabels(verdicts_list, fontsize=11)
        ax.set_yticks(range(len(spec_baselines)))
        ax.set_yticklabels([BASELINE_LABELS[b] for b in spec_baselines], fontsize=10)
        ax.set_title(WORKLOAD_LABELS[w], fontsize=14, fontweight="bold")

        for i in range(len(spec_baselines)):
            for j in range(len(verdicts_list)):
                val = matrix[i, j]
                color = "white" if val > 2.5 else "black"
                ax.text(j, i, f"{int(val)}", ha="center", va="center",
                        fontsize=14, fontweight="bold", color=color)

    fig.suptitle("Reconciliation Verdict Distribution (§3.3)", fontsize=15, y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "06_verdict_heatmap.png", bbox_inches="tight")
    plt.close(fig)
    print("  06_verdict_heatmap.png")


# ═══════════════════════════════════════════════════
# Fig 07: Q Metric — Dispatch Quality
# ═══════════════════════════════════════════════════

def plot_07_quality(data):
    # Load Q metric results
    q_results = {}
    for w in WORKLOADS:
        runs_dir = BASE / f"workloads/{w}/runs"
        for qf in runs_dir.glob("quality_*.json"):
            with open(qf) as f:
                q = json.load(f)
            q_results[w] = q

    if not q_results:
        print("  07_quality.png — no Q metric data")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    workloads_with_q = [w for w in WORKLOADS if w in q_results]
    x = np.arange(len(workloads_with_q))
    width = 0.35

    # Scores
    pythia_q = [q_results[w].get("Q_run_a", 0) for w in workloads_with_q]
    ns_q = [q_results[w].get("Q_run_b", 0) for w in workloads_with_q]

    ax1.bar(x - width/2, pythia_q, width, label="Pythia", color="#2563eb", alpha=0.85)
    ax1.bar(x + width/2, ns_q, width, label="No Speculation", color="#ef4444", alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels([WORKLOAD_LABELS[w] for w in workloads_with_q], fontsize=12)
    ax1.set_ylabel("Quality Score (1-5)")
    ax1.set_title("Dispatch Quality: Pythia vs NS (§6.1)")
    ax1.set_ylim(0, 5.5)
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.2, axis="y")
    for i, (pv, nv) in enumerate(zip(pythia_q, ns_q)):
        ax1.text(i - width/2, pv + 0.1, f"{pv:.1f}", ha="center", fontsize=10, fontweight="bold")
        ax1.text(i + width/2, nv + 0.1, f"{nv:.1f}", ha="center", fontsize=10)

    # Win/loss
    wins = [q_results[w].get("run_a_wins", 0) for w in workloads_with_q]
    losses = [q_results[w].get("run_b_wins", 0) for w in workloads_with_q]
    ties = [q_results[w].get("ties", 0) for w in workloads_with_q]

    ax2.bar(x, wins, 0.6, label="Pythia wins", color="#2563eb", alpha=0.85)
    ax2.bar(x, ties, 0.6, bottom=wins, label="Ties", color="#94a3b8", alpha=0.85)
    ax2.bar(x, losses, 0.6, bottom=[w+t for w, t in zip(wins, ties)],
            label="NS wins", color="#ef4444", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([WORKLOAD_LABELS[w] for w in workloads_with_q], fontsize=12)
    ax2.set_ylabel("Count (out of 5)")
    ax2.set_title("Pairwise Win/Loss (LLM Judge)")
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(PLOT_DIR / "07_quality.png", bbox_inches="tight")
    plt.close(fig)
    print("  07_quality.png")


# ═══════════════════════════════════════════════════
# Fig 08: Tokens and Cost Efficiency
# ═══════════════════════════════════════════════════

def plot_08_cost_efficiency(data):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Total tokens
    ax = axes[0]
    x = np.arange(len(WORKLOADS))
    width = 0.15
    for i, bl in enumerate(BASELINE_ORDER):
        vals = [get_val(data, w, bl, "total_tokens") for w in WORKLOADS]
        ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Total Tokens")
    ax.set_title("Token Consumption (E)")
    ax.legend(fontsize=8, ncol=3)
    ax.grid(True, alpha=0.2, axis="y")

    # Convergence N_conv
    ax = axes[1]
    spec_baselines = ["swol", "pythia", "oracle"]
    width = 0.25
    for i, bl in enumerate(spec_baselines):
        vals = [get_val(data, w, bl, "N_conv") for w in WORKLOADS]
        bars = ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
                      color=BASELINE_COLORS[bl], alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, val + 0.1,
                    f"{val}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS], fontsize=12)
    ax.set_ylabel("Interactions to Converge")
    ax.set_title("Convergence Speed N_conv (§6.3)")
    ax.legend()
    ax.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(PLOT_DIR / "08_cost_efficiency.png", bbox_inches="tight")
    plt.close(fig)
    print("  08_cost_efficiency.png")


# ═══════════════════════════════════════════════════
# Fig 09: Mode Distribution
# ═══════════════════════════════════════════════════

def plot_09_mode_distribution(data):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    for idx, w in enumerate(WORKLOADS):
        ax = axes[idx]
        pythia = data[w].get("pythia", {})
        modes = pythia.get("mode_distribution", {})

        mode_vals = [modes.get(str(m), modes.get(m, 0)) for m in [1, 2, 3]]
        mode_colors_list = ["#ef4444", "#f59e0b", "#22c55e"]
        mode_labels = ["Mode 1\n(Context)", "Mode 2\n(Pre-dispatch)", "Mode 3\n(Draft Exec)"]

        bars = ax.bar(range(3), mode_vals, color=mode_colors_list, alpha=0.85, width=0.6)
        ax.set_xticks(range(3))
        ax.set_xticklabels(mode_labels, fontsize=9)
        ax.set_title(WORKLOAD_LABELS[w], fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.2, axis="y")

        for bar, val in zip(bars, mode_vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, val + 0.1,
                        str(val), ha="center", fontsize=12, fontweight="bold")

    axes[0].set_ylabel("Number of Interactions")
    fig.suptitle("Speculation Mode Distribution — Pythia (§3.2)", fontsize=15, y=1.02)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "09_mode_distribution.png", bbox_inches="tight")
    plt.close(fig)
    print("  09_mode_distribution.png")


# ═══════════════════════════════════════════════════
# Fig 10: Summary Dashboard
# ═══════════════════════════════════════════════════

def plot_10_dashboard(data):
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(2, 3, hspace=0.35, wspace=0.3)

    # Panel 1: Pipeline latency (Pythia vs NS vs Oracle)
    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(WORKLOADS))
    width = 0.25
    for i, bl in enumerate(["ns", "pythia", "oracle"]):
        vals = [get_val(data, w, bl, "mean_pipeline_s") for w in WORKLOADS]
        ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS])
    ax.set_ylabel("Pipeline (s)")
    ax.set_title("Pipeline Latency")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis="y")

    # Panel 2: Hit rate
    ax = fig.add_subplot(gs[0, 1])
    for i, bl in enumerate(["swol", "pythia", "oracle"]):
        vals = [get_val(data, w, bl, "hit_rate") * 100 for w in WORKLOADS]
        ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS])
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Speculation Hit Rate")
    ax.set_ylim(0, 115)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis="y")

    # Panel 3: Net benefit
    ax = fig.add_subplot(gs[0, 2])
    for i, bl in enumerate(["ns", "swol", "pythia", "oracle"]):
        vals = [get_val(data, w, bl, "net_benefit") for w in WORKLOADS]
        ax.bar(x + i * 0.2, vals, 0.2, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + 0.3)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS])
    ax.set_ylabel("Net Benefit")
    ax.set_title("Cost Model Benefit")
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.2, axis="y")

    # Panel 4: Confidence progression
    ax = fig.add_subplot(gs[1, 0])
    for w in WORKLOADS:
        events = data[w].get("pythia", {}).get("_events", [])
        if events:
            conf = [e.get("learner_confidence", 0) for e in events]
            ax.plot(range(1, len(conf) + 1), conf, marker="o", linewidth=2,
                    label=WORKLOAD_LABELS[w], color=WORKLOAD_COLORS[w])
    ax.axhline(y=0.5, color="#f59e0b", linestyle="--", alpha=0.5, label="τ₂")
    ax.axhline(y=0.8, color="#22c55e", linestyle="--", alpha=0.5, label="τ₃")
    ax.set_xlabel("Interaction")
    ax.set_ylabel("Confidence")
    ax.set_title("Learner Convergence")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=7, ncol=3)
    ax.grid(True, alpha=0.2)

    # Panel 5: Salvage ratio
    ax = fig.add_subplot(gs[1, 1])
    for i, bl in enumerate(["swol", "pythia", "oracle"]):
        vals = [get_val(data, w, bl, "mean_salvage_ratio") for w in WORKLOADS]
        ax.bar(x + i * width, vals, width, label=BASELINE_LABELS[bl],
               color=BASELINE_COLORS[bl], alpha=0.85)
    ax.set_xticks(x + width)
    ax.set_xticklabels([WORKLOAD_LABELS[w] for w in WORKLOADS])
    ax.set_ylabel("Salvage Ratio (σ)")
    ax.set_title("Reusable Speculative Work")
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis="y")

    # Panel 6: Q metric
    ax = fig.add_subplot(gs[1, 2])
    q_data = {}
    for w in WORKLOADS:
        for qf in (BASE / f"workloads/{w}/runs").glob("quality_*.json"):
            with open(qf) as f:
                q_data[w] = json.load(f)
    if q_data:
        ww = [w for w in WORKLOADS if w in q_data]
        pythia_q = [q_data[w].get("Q_run_a", 0) for w in ww]
        ns_q = [q_data[w].get("Q_run_b", 0) for w in ww]
        xx = np.arange(len(ww))
        ax.bar(xx - 0.15, pythia_q, 0.3, label="Pythia", color="#2563eb", alpha=0.85)
        ax.bar(xx + 0.15, ns_q, 0.3, label="NS", color="#ef4444", alpha=0.85)
        ax.set_xticks(xx)
        ax.set_xticklabels([WORKLOAD_LABELS[w] for w in ww])
        ax.set_ylabel("Quality (1-5)")
        ax.set_title("Output Quality Q")
        ax.set_ylim(0, 5.5)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.2, axis="y")

    fig.suptitle("Pythia Evaluation Dashboard — All Metrics (§6)", fontsize=16, y=1.01)
    fig.savefig(PLOT_DIR / "10_dashboard.png", bbox_inches="tight")
    plt.close(fig)
    print("  10_dashboard.png")


def main():
    print("Loading all runs...")
    data = load_all_runs()
    for w in WORKLOADS:
        print(f"  {w}: {list(data[w].keys())}")

    print(f"\nGenerating plots → {PLOT_DIR}/\n")

    plot_01_pipeline_latency(data)
    plot_02_dispatch_breakdown(data)
    plot_03_speculation_accuracy(data)
    plot_04_cost_analysis(data)
    plot_05_learner_confidence(data)
    plot_06_verdict_heatmap(data)
    plot_07_quality(data)
    plot_08_cost_efficiency(data)
    plot_09_mode_distribution(data)
    plot_10_dashboard(data)

    print(f"\nAll 10 figures saved to {PLOT_DIR}/")


if __name__ == "__main__":
    main()
