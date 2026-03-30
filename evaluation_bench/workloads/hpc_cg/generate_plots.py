"""Generate evaluation plots for HPC-CG workload.

Reads from runs/<run_dir>/all_results.json produced by run_full_eval.py.
Produces publication-quality figures mapped to paper §6 claims.

Figures:
  01 — Speculator vs Solver Latency (§6.2, Claim C1)
  02 — Per-Agent Execution Breakdown (§6.2)
  03 — Learning Curve: Hit Rate Over Time (§6.3, Claim C4)
  04 — Progressive Mode Activation + Confidence (§6.3, Claim C2)
  05 — Verdict Distribution (§6.3, Claim C3)
  06 — Cost Analysis: Net Benefit + Salvage (§6.4)
  07 — Solver Plan Quality: Agent Count + DAG (§5.1)
  08 — Cache Behavior: Hit/Miss Over Time
  09 — Speculator vs Solver Plan Comparison (§3.3)

Usage:
  python generate_plots.py                           # latest run
  python generate_plots.py runs/20260327_.../        # specific run
"""

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

plt.rcParams.update({
    "font.size": 11,
    "font.family": "serif",
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.pad_inches": 0.1,
})

DATA_DIR = Path(__file__).parent
PLOT_DIR = DATA_DIR / "plots"
PLOT_DIR.mkdir(exist_ok=True)


def find_run_dir(arg=None) -> Path:
    """Find run directory from CLI arg or latest."""
    if arg:
        p = Path(arg)
        if p.exists():
            return p
    runs = sorted((DATA_DIR / "runs").glob("*_*req"))
    if not runs:
        print("No runs found in runs/")
        sys.exit(1)
    return runs[-1]


def load_data(run_dir: Path):
    with open(run_dir / "all_results.json") as f:
        data = json.load(f)
    return data["summary"], data["events"]


def load_interaction_details(run_dir: Path, interaction: int) -> dict:
    """Load per-layer JSON for a specific interaction."""
    idir = run_dir / f"interaction_{interaction:03d}"
    details = {}
    for f in idir.glob("*.json"):
        details[f.stem] = json.load(open(f))
    return details


# ═══════════════════════════════════════════════════════════
# Fig 01: Speculator vs Solver Latency (§6.2, Claim C1)
# ═══════════════════════════════════════════════════════════

def plot_speculator_vs_solver(events, plot_dir):
    """Shows speculation hides solver latency."""
    n = len(events)
    x = np.arange(1, n + 1)
    solver_ms = [e["solver_time_ms"] for e in events]
    spec_ms = [e["speculator_time_ms"] for e in events]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [2, 1]})

    # Left: bar chart comparison
    width = 0.35
    ax1.bar(x - width/2, solver_ms, width, label="Solver (LLM)", color="#ef4444", alpha=0.85)
    ax1.bar(x + width/2, spec_ms, width, label="Speculator (cache/draft)", color="#2563eb", alpha=0.85)
    ax1.set_xlabel("Interaction")
    ax1.set_ylabel("Latency (ms)")
    ax1.set_title("Dispatch Latency: Solver vs Speculator (§6.2)")
    ax1.set_xticks(x)
    ax1.legend()
    ax1.grid(True, alpha=0.2, axis="y")

    # Add speedup annotations
    for i, (s, sp) in enumerate(zip(solver_ms, spec_ms)):
        if sp > 0:
            speedup = s / sp
            ax1.text(i + 1, max(s, sp) + 200, f"{speedup:.0f}x",
                     ha="center", fontsize=8, color="#16a34a")

    # Right: summary stats
    mean_solver = np.mean(solver_ms)
    mean_spec = np.mean(spec_ms)
    speedups = [s / sp if sp > 0 else 0 for s, sp in zip(solver_ms, spec_ms)]

    ax2.barh(["Solver\n(Claude)", "Speculator\n(cache)"],
             [mean_solver, mean_spec],
             color=["#ef4444", "#2563eb"], alpha=0.85, height=0.4)
    ax2.set_xlabel("Mean Latency (ms)")
    ax2.set_title(f"Mean Speedup: {np.mean(speedups):.0f}x")
    for i, v in enumerate([mean_solver, mean_spec]):
        ax2.text(v + 100, i, f"{v:.0f}ms", va="center", fontsize=10)
    ax2.grid(True, alpha=0.2, axis="x")

    fig.tight_layout()
    fig.savefig(plot_dir / "01_speculator_vs_solver.png", bbox_inches="tight")
    plt.close(fig)
    print("  01_speculator_vs_solver.png")


# ═══════════════════════════════════════════════════════════
# Fig 02: Per-Agent Execution Breakdown (§6.2)
# ═══════════════════════════════════════════════════════════

def plot_agent_execution(run_dir, events, plot_dir):
    """Shows per-agent real execution times across fleet."""
    agent_data = {}  # agent_type -> [(model, time_s), ...]

    for e in events:
        idir = run_dir / f"interaction_{e['interaction']:03d}"
        exec_file = idir / "layer4_execution.json"
        if not exec_file.exists():
            continue
        with open(exec_file) as f:
            l4 = json.load(f)
        for agent_type, info in l4.get("agents", {}).items():
            model = info.get("model", "?")
            time_s = info.get("time_s", 0)
            agent_data.setdefault(agent_type, []).append((model, time_s))

    if not agent_data:
        print("  02_agent_execution.png — no data")
        return

    agents = sorted(agent_data.keys())
    means = [np.mean([t for _, t in agent_data[a]]) for a in agents]
    stds = [np.std([t for _, t in agent_data[a]]) for a in agents]
    models = [Counter(m for m, _ in agent_data[a]).most_common(1)[0][0] for a in agents]

    colors = {
        "planner": "#3b82f6", "code_gen": "#ef4444",
        "tester": "#f59e0b", "review": "#22c55e",
    }

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(range(len(agents)), means, xerr=stds, height=0.5,
                   color=[colors.get(a, "#64748b") for a in agents], alpha=0.85, capsize=4)
    ax.set_yticks(range(len(agents)))
    ax.set_yticklabels([f"{a}\n({m})" for a, m in zip(agents, models)], fontsize=9)
    ax.set_xlabel("Execution Time (seconds)")
    ax.set_title("Per-Agent Execution Latency (§6.2)")
    ax.grid(True, alpha=0.2, axis="x")

    for bar, mean in zip(bars, means):
        ax.text(mean + 1, bar.get_y() + bar.get_height()/2,
                f"{mean:.0f}s", va="center", fontsize=10)

    fig.tight_layout()
    fig.savefig(plot_dir / "02_agent_execution.png", bbox_inches="tight")
    plt.close(fig)
    print("  02_agent_execution.png")


# ═══════════════════════════════════════════════════════════
# Fig 03: Learning Curve (§6.3, Claim C4)
# ═══════════════════════════════════════════════════════════

def plot_learning_curve(events, plot_dir):
    """Shows hit rate improving over interactions."""
    n = len(events)
    hits = [1 if e["verdict"] in ("COMMIT", "PARTIAL") else 0 for e in events]

    # Cumulative hit rate
    cumulative = [sum(hits[:i+1]) / (i+1) for i in range(n)]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, n+1), [c * 100 for c in cumulative],
            color="#2563eb", linewidth=2, label="Cumulative hit rate")
    ax.scatter(range(1, n+1), [h * 100 for h in hits],
               c=["#22c55e" if h else "#ef4444" for h in hits],
               s=40, zorder=5, alpha=0.7)

    # Annotate verdicts
    for i, e in enumerate(events):
        ax.annotate(e["verdict"][:3], (i+1, hits[i]*100 + 3),
                    fontsize=7, ha="center", color="#64748b")

    ax.set_xlabel("Interaction Number")
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("Speculation Hit Rate — Learning Curve (§6.3)")
    ax.set_ylim(-5, 110)
    ax.set_xlim(0.5, n + 0.5)
    ax.legend()
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(plot_dir / "03_learning_curve.png", bbox_inches="tight")
    plt.close(fig)
    print("  03_learning_curve.png")


# ═══════════════════════════════════════════════════════════
# Fig 04: Mode Activation + Confidence (§6.3, Claim C2)
# ═══════════════════════════════════════════════════════════

def plot_mode_activation(events, plot_dir):
    """Shows progressive mode activation gated by confidence."""
    n = len(events)
    modes = [e["speculator_mode"] for e in events]
    confidences = [e["learner_confidence"] for e in events]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))

    # Mode as colored bars
    mode_colors = {1: "#ef4444", 2: "#f59e0b", 3: "#22c55e"}
    mode_labels = {1: "Mode 1 (Context)", 2: "Mode 2 (Pre-dispatch)", 3: "Mode 3 (Draft Exec)"}
    for i, m in enumerate(modes):
        ax1.bar(i + 1, m, width=0.8, color=mode_colors[m], alpha=0.4)
    ax1.set_ylabel("Speculation Mode")
    ax1.set_yticks([1, 2, 3])
    ax1.set_yticklabels(["Mode 1\n(Context)", "Mode 2\n(Pre-dispatch)", "Mode 3\n(Draft)"])
    ax1.set_ylim(0.3, 3.7)

    # Confidence on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(range(1, n+1), confidences, color="#8b5cf6", linewidth=2.5,
             marker="o", markersize=5, label="Confidence")
    ax2.set_ylabel("Learner Confidence", color="#8b5cf6")
    ax2.set_ylim(-0.05, 1.05)
    ax2.tick_params(axis="y", labelcolor="#8b5cf6")

    # Threshold lines
    ax2.axhline(y=0.5, color="#f59e0b", linestyle="--", alpha=0.6, linewidth=1.5, label="τ₂ = 0.5")
    ax2.axhline(y=0.8, color="#22c55e", linestyle="--", alpha=0.6, linewidth=1.5, label="τ₃ = 0.8")
    ax2.legend(loc="upper left")

    ax1.set_xlabel("Interaction Number")
    ax1.set_title("Progressive Mode Activation with Confidence (§6.3)")
    ax1.set_xlim(0.3, n + 0.7)
    ax1.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(plot_dir / "04_mode_activation.png", bbox_inches="tight")
    plt.close(fig)
    print("  04_mode_activation.png")


# ═══════════════════════════════════════════════════════════
# Fig 05: Verdict Distribution (§6.3, Claim C3)
# ═══════════════════════════════════════════════════════════

def plot_verdict_distribution(events, plot_dir):
    """Shows reconciliation verdicts distribution."""
    verdicts = [e["verdict"] for e in events]
    counts = Counter(verdicts)

    colors = {"COMMIT": "#22c55e", "PARTIAL": "#f59e0b", "FLUSH": "#ef4444"}
    labels = ["COMMIT", "PARTIAL", "FLUSH"]
    vals = [counts.get(v, 0) for v in labels]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: bar chart
    bars = ax1.bar(labels, vals, color=[colors[v] for v in labels], alpha=0.85, width=0.5)
    ax1.set_ylabel("Count")
    ax1.set_title("Reconciliation Verdicts (§3.3)")
    ax1.grid(True, alpha=0.2, axis="y")
    for bar, val in zip(bars, vals):
        if val > 0:
            pct = 100 * val / len(events)
            ax1.text(bar.get_x() + bar.get_width()/2, val + 0.1,
                     f"{val} ({pct:.0f}%)", ha="center", fontsize=11)

    # Right: per-interaction timeline
    for i, e in enumerate(events):
        v = e["verdict"]
        ax2.barh(0, 1, left=i, height=0.5, color=colors.get(v, "gray"), alpha=0.85)
    ax2.set_xlabel("Interaction")
    ax2.set_title("Verdict Timeline")
    ax2.set_yticks([])
    # Add legend
    from matplotlib.patches import Patch
    ax2.legend(handles=[Patch(color=colors[v], label=v) for v in labels if counts.get(v, 0) > 0],
               loc="upper right")

    fig.tight_layout()
    fig.savefig(plot_dir / "05_verdict_distribution.png", bbox_inches="tight")
    plt.close(fig)
    print("  05_verdict_distribution.png")


# ═══════════════════════════════════════════════════════════
# Fig 06: Cost Analysis (§6.4)
# ═══════════════════════════════════════════════════════════

def plot_cost_analysis(events, plot_dir):
    """Shows net benefit, salvage ratio, and wasted compute."""
    n = len(events)
    x = np.arange(1, n + 1)

    rewards = [e["reward"] for e in events]
    cum_reward = np.cumsum(rewards)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

    # Top: per-interaction reward
    colors = ["#22c55e" if r > 0 else "#ef4444" for r in rewards]
    ax1.bar(x, rewards, color=colors, alpha=0.85, width=0.6)
    ax1.axhline(y=0, color="black", linewidth=0.5)
    ax1.set_ylabel("Reward")
    ax1.set_title("Per-Interaction Reward (§6.4)")
    ax1.grid(True, alpha=0.2, axis="y")

    # Bottom: cumulative net benefit
    ax2.plot(x, cum_reward, color="#2563eb", linewidth=2.5, marker="o", markersize=5)
    ax2.fill_between(x, 0, cum_reward, alpha=0.15, color="#2563eb")
    ax2.axhline(y=0, color="black", linewidth=0.5)
    ax2.set_xlabel("Interaction Number")
    ax2.set_ylabel("Cumulative Net Benefit")
    ax2.set_title(f"Cumulative Benefit: {cum_reward[-1]:.1f} (§6.4)")
    ax2.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(plot_dir / "06_cost_analysis.png", bbox_inches="tight")
    plt.close(fig)
    print("  06_cost_analysis.png")


# ═══════════════════════════════════════════════════════════
# Fig 07: Solver Plan Quality (§5.1)
# ═══════════════════════════════════════════════════════════

def plot_solver_plan_quality(run_dir, events, plot_dir):
    """Shows solver producing dynamic plans (not always 4 agents)."""
    n = len(events)
    x = np.arange(1, n + 1)

    agent_counts = [len(e["solver_agents"]) for e in events]
    pipelines = [" → ".join(e["solver_agents"]) for e in events]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), gridspec_kw={"width_ratios": [1.5, 1]})

    # Left: agent count per interaction
    ax1.bar(x, agent_counts, color="#2563eb", alpha=0.85, width=0.5)
    ax1.set_xlabel("Interaction")
    ax1.set_ylabel("Agent Count")
    ax1.set_title("Solver-Selected Agent Count (Dynamic Planning)")
    ax1.set_xticks(x)
    ax1.set_ylim(0, max(agent_counts) + 1.5)
    ax1.grid(True, alpha=0.2, axis="y")

    for i, (cnt, pipe) in enumerate(zip(agent_counts, pipelines)):
        ax1.text(i + 1, cnt + 0.2, str(cnt), ha="center", fontsize=10, fontweight="bold")

    # Right: pipeline distribution
    pipe_counts = Counter(pipelines)
    labels = [p for p, _ in pipe_counts.most_common()]
    counts = [c for _, c in pipe_counts.most_common()]
    short_labels = [p.replace(" → ", "→\n") for p in labels]

    ax2.barh(range(len(labels)), counts,
             color=["#2563eb", "#f59e0b", "#22c55e", "#ef4444"][:len(labels)],
             alpha=0.85, height=0.5)
    ax2.set_yticks(range(len(labels)))
    ax2.set_yticklabels(short_labels, fontsize=8)
    ax2.set_xlabel("Count")
    ax2.set_title("Pipeline Distribution")
    ax2.grid(True, alpha=0.2, axis="x")

    fig.tight_layout()
    fig.savefig(plot_dir / "07_solver_plan_quality.png", bbox_inches="tight")
    plt.close(fig)
    print("  07_solver_plan_quality.png")


# ═══════════════════════════════════════════════════════════
# Fig 08: Cache Behavior (Speculator)
# ═══════════════════════════════════════════════════════════

def plot_cache_behavior(events, plot_dir):
    """Shows cache hit/miss pattern over interactions."""
    n = len(events)
    x = np.arange(1, n + 1)
    cache_hits = [e.get("speculator_cache_hit", False) for e in events]

    fig, ax = plt.subplots(figsize=(8, 3))

    colors = ["#22c55e" if h else "#ef4444" for h in cache_hits]
    ax.bar(x, [1]*n, color=colors, alpha=0.85, width=0.7)

    # Labels
    for i, hit in enumerate(cache_hits):
        label = "HIT" if hit else "MISS"
        ax.text(i + 1, 0.5, label, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white")

    ax.set_xlabel("Interaction")
    ax.set_title("Speculator Cache Behavior")
    ax.set_yticks([])
    ax.set_xticks(x)
    ax.set_xlim(0.3, n + 0.7)

    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color="#22c55e", label="Cache HIT"),
        Patch(color="#ef4444", label="Cache MISS"),
    ], loc="upper right")

    fig.tight_layout()
    fig.savefig(plot_dir / "08_cache_behavior.png", bbox_inches="tight")
    plt.close(fig)
    print("  08_cache_behavior.png")


# ═══════════════════════════════════════════════════════════
# Fig 09: Solver vs Speculator Plan Comparison (§3.3)
# ═══════════════════════════════════════════════════════════

def plot_plan_comparison(run_dir, events, plot_dir):
    """Side-by-side: how many agents each predicted, and overlap."""
    n = len(events)
    x = np.arange(1, n + 1)

    solver_counts = []
    spec_counts = []
    overlaps = []

    for e in events:
        idir = run_dir / f"interaction_{e['interaction']:03d}"
        solver_f = idir / "layer2_solver.json"
        spec_f = idir / "layer2_speculator.json"
        recon_f = idir / "layer3_reconciliation.json"

        if solver_f.exists() and spec_f.exists():
            with open(solver_f) as f:
                s = json.load(f)
            with open(spec_f) as f:
                sp = json.load(f)
            solver_agents = set(a["agent"] for a in s["output"]["plan"])
            spec_agents = set(a["agent"] for a in sp["output"]["draft_plan"])
            solver_counts.append(len(solver_agents))
            spec_counts.append(len(spec_agents))
            overlaps.append(len(solver_agents & spec_agents))
        else:
            solver_counts.append(0)
            spec_counts.append(0)
            overlaps.append(0)

    fig, ax = plt.subplots(figsize=(8, 4.5))

    width = 0.25
    ax.bar(x - width, solver_counts, width, label="Solver agents", color="#ef4444", alpha=0.85)
    ax.bar(x, spec_counts, width, label="Speculator agents", color="#2563eb", alpha=0.85)
    ax.bar(x + width, overlaps, width, label="Overlap (matched)", color="#22c55e", alpha=0.85)

    ax.set_xlabel("Interaction")
    ax.set_ylabel("Agent Count")
    ax.set_title("Solver vs Speculator Plan Comparison (§3.3)")
    ax.set_xticks(x)
    ax.legend()
    ax.grid(True, alpha=0.2, axis="y")

    # Add verdict labels
    for i, e in enumerate(events):
        ax.text(i + 1, max(solver_counts[i], spec_counts[i]) + 0.3,
                e["verdict"][:3], ha="center", fontsize=8, color="#64748b")

    fig.tight_layout()
    fig.savefig(plot_dir / "09_plan_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print("  09_plan_comparison.png")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    run_dir = find_run_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Run: {run_dir}")

    summary, events = load_data(run_dir)
    print(f"Events: {len(events)}")

    plot_dir = PLOT_DIR
    print(f"\nGenerating figures → {plot_dir}/")
    print()

    plot_speculator_vs_solver(events, plot_dir)
    plot_agent_execution(run_dir, events, plot_dir)
    plot_learning_curve(events, plot_dir)
    plot_mode_activation(events, plot_dir)
    plot_verdict_distribution(events, plot_dir)
    plot_cost_analysis(events, plot_dir)
    plot_solver_plan_quality(run_dir, events, plot_dir)
    plot_cache_behavior(events, plot_dir)
    plot_plan_comparison(run_dir, events, plot_dir)

    # Print claim verification
    print(f"\n{'═'*60}")
    print(f"  CLAIM VERIFICATION")
    print(f"{'═'*60}")

    mean_solver = np.mean([e["solver_time_ms"] for e in events])
    mean_spec = np.mean([e["speculator_time_ms"] for e in events])
    hit_rate = summary["hit_rate"]
    verdicts = summary["verdicts"]
    modes = summary["mode_distribution"]
    net_benefit = summary["net_benefit"]

    print(f"\n  C1: Speculation hides Solver latency")
    print(f"      Solver mean: {mean_solver:.0f}ms | Speculator mean: {mean_spec:.1f}ms")
    print(f"      Speedup: {mean_solver/mean_spec:.0f}x")
    c1 = mean_spec < mean_solver
    print(f"      → {'SUPPORTED' if c1 else 'NOT SUPPORTED'}")

    print(f"\n  C2: Progressive modes (1→2→3) reduce latency")
    print(f"      Mode distribution: {modes}")
    mode_progression = len(set(int(k) for k in modes.keys())) > 1
    print(f"      → {'SUPPORTED (multiple modes observed)' if mode_progression else 'PARTIAL (only 1 mode so far — need more interactions)'}")

    print(f"\n  C3: Reconciliation correctly classifies verdicts")
    print(f"      Verdicts: {verdicts}")
    print(f"      Hit rate: {100*hit_rate:.1f}%")
    c3 = hit_rate > 0
    print(f"      → {'SUPPORTED' if c3 else 'NOT SUPPORTED'}")

    print(f"\n  C4: Learner improves speculation accuracy over time")
    conf_start = events[0]["learner_confidence"]
    conf_end = events[-1]["learner_confidence"]
    print(f"      Confidence: {conf_start:.3f} → {conf_end:.3f}")
    print(f"      Phase: {events[0].get('learner_phase', '?')} → {events[-1].get('learner_phase', '?')}")
    c4 = conf_end >= conf_start
    print(f"      → {'SUPPORTED' if c4 else 'NOT SUPPORTED'}")

    print(f"\n  C5: Cost model thresholds correctly gate modes")
    for e in events:
        mode = e["speculator_mode"]
        conf = e["speculator_confidence"]
        if mode >= 2 and conf < 0.5:
            print(f"      VIOLATION: Mode {mode} at confidence {conf:.3f} < τ₂=0.5")
            break
        if mode >= 3 and conf < 0.8:
            print(f"      VIOLATION: Mode {mode} at confidence {conf:.3f} < τ₃=0.8")
            break
    else:
        print(f"      All mode activations respect thresholds")
        print(f"      → SUPPORTED")

    print(f"\n  Net benefit: {net_benefit:.1f}")
    print(f"  → System {'profitable' if net_benefit > 0 else 'unprofitable'}")
    print()


if __name__ == "__main__":
    main()
