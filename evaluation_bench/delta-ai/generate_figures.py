"""Generate SC26 paper-ready figures from Pythia evaluation results.

IEEE two-column format: figures are 3.5in (single col) or 7in (double col).
Clean, readable labels — no overlapping text.

Output: delta-ai/figures/*.pdf
"""

import json
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── IEEE SC26 Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.framealpha": 0.95,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.08,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "grid.linestyle": "--",
})

# Color palette (colorblind-safe)
C_BLUE = "#2166ac"
C_RED = "#b2182b"
C_GREEN = "#4daf4a"
C_ORANGE = "#ff7f00"
C_PURPLE = "#984ea3"
C_BROWN = "#a65628"
C_GRAY = "#636363"

FAMILY_COLORS = {
    "GPT-OSS": C_BLUE,
    "Qwen": C_ORANGE,
    "Llama": C_GREEN,
    "Gemma": C_RED,
    "Phi": C_PURPLE,
    "Claude": C_BROWN,
}

FIGDIR = Path(__file__).parent / "figures"
FIGDIR.mkdir(exist_ok=True)
WORKLOADS_DIR = Path(__file__).parent.parent / "workloads"
RUNS_DIR = WORKLOADS_DIR / "hpc_cg/runs"


def load_all(workload="hpc_cg"):
    runs_dir = WORKLOADS_DIR / workload / "runs"
    runs = []
    for d in sorted(runs_dir.iterdir()):
        cfg_f, sum_f = d / "config.json", d / "summary.json"
        if not cfg_f.exists() or not sum_f.exists():
            continue
        try:
            c = json.loads(cfg_f.read_text())
            s = json.loads(sum_f.read_text())
        except Exception:
            continue
        if s.get("total_interactions", 0) == 0:
            continue
        solver = c.get("solver", {}).get("model", "?")
        draft = c.get("draft", {}).get("model", "none")
        runs.append({
            "workload": workload,
            "baseline": c.get("baseline", "?"),
            "solver": solver, "draft": draft,
            "temp": c.get("agent_temperature", 0.3),
            "n": s["total_interactions"],
            "solver_ms": s["mean_solver_ms"],
            "spec_ms": s["mean_speculator_ms"],
            "pipeline_s": s["mean_pipeline_s"],
            "hit_rate": s["hit_rate"],
            "salvage": s["mean_salvage_ratio"],
            "waste": s["wasted_compute_ratio_W"],
            "benefit": s["net_benefit"],
            "n_conv": s["N_conv"],
            "tokens": s["total_tokens"],
            "cost": s["total_cost"],
            "modes": s.get("mode_distribution", {}),
            "confidence": s.get("confidence_at_end", 0),
        })
    return runs


def load_all_workloads():
    all_runs = []
    for wl in ["hpc_cg", "sdp", "rwa"]:
        all_runs.extend(load_all(wl))
    return all_runs


def model_label(m):
    """Short, clean label for a model name."""
    return {
        "gpt-oss:120b": "GPT-OSS 120B",
        "gpt-oss:20b": "GPT-OSS 20B",
        "qwen3:4b": "Qwen3 4B",
        "qwen3:1.7b": "Qwen3 1.7B",
        "llama3.2:3b": "Llama3.2 3B",
        "gemma2:2b": "Gemma2 2B",
        "phi4-mini:3.8b": "Phi4-mini 3.8B",
        "claude-haiku-4-5-20251001": "Claude Haiku",
        "claude-sonnet-4-6": "Claude Sonnet",
        "claude-opus-4-6": "Claude Opus",
        "rule-based": "Rule-Based",
        "none": "None",
    }.get(m, m)


def model_family(m):
    if "gpt-oss" in m: return "GPT-OSS"
    if "qwen" in m: return "Qwen"
    if "llama" in m: return "Llama"
    if "gemma" in m: return "Gemma"
    if "phi" in m: return "Phi"
    if "claude" in m: return "Claude"
    return "Other"


def family_color(m):
    return FAMILY_COLORS.get(model_family(m), C_GRAY)


def dedup_best(runs, key_fn):
    """Keep the run with highest benefit for each key."""
    best = {}
    for r in runs:
        k = key_fn(r)
        if k not in best or r["benefit"] > best[k]["benefit"]:
            best[k] = r
    return list(best.values())


def save(fig, name):
    fig.savefig(FIGDIR / f"{name}.pdf")
    fig.savefig(FIGDIR / f"{name}.png")
    plt.close(fig)


# ═══════════════════════════════════════════════════
#  FIG 6a: SOLVER vs SPECULATOR LATENCY (horizontal bar)
# ═══════════════════════════════════════════════════
def fig6a(runs):
    pythia = [r for r in runs if r["baseline"] == "pythia" and r["temp"] == 0.3
              and r["draft"] != "none"]
    data = dedup_best(pythia, lambda r: (r["solver"], r["draft"]))
    data = sorted(data, key=lambda x: x["solver_ms"] / max(x["spec_ms"], 0.01))

    fig, ax = plt.subplots(figsize=(7, 3.6))

    labels = [f"{model_label(r['solver'])}  /  {model_label(r['draft'])}" for r in data]
    y = np.arange(len(data))
    h = 0.35

    solver_vals = [r["solver_ms"] / 1000 for r in data]
    spec_vals = [r["spec_ms"] / 1000 for r in data]

    ax.barh(y + h/2, solver_vals, h, label="Solver (target model)",
            color=C_BLUE, edgecolor="white", linewidth=0.5)
    ax.barh(y - h/2, spec_vals, h, label="Speculator (draft model)",
            color=C_RED, edgecolor="white", linewidth=0.5)

    # Add speedup annotations on right side
    for i, r in enumerate(data):
        ratio = r["solver_ms"] / max(r["spec_ms"], 0.01)
        maxval = max(solver_vals[i], spec_vals[i])
        color = C_GREEN if ratio > 2 else C_ORANGE if ratio > 1 else C_RED
        ax.text(maxval + 0.3, y[i], f"{ratio:.1f}x",
                fontsize=8, fontweight="bold", va="center", color=color)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Latency (seconds)")
    ax.set_title("Solver vs. Speculator Dispatch Latency")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0), framealpha=0.95)
    ax.invert_yaxis()
    # Extend x-axis to make room for speedup labels
    ax.set_xlim(0, max(max(solver_vals), max(spec_vals)) * 1.25)

    fig.tight_layout()
    save(fig, "fig6a_latency_gap")
    print(f"  fig6a: {len(data)} model pairs")


# ═══════════════════════════════════════════════════
#  FIG 6b: DRAFT MODEL FAMILY COMPARISON
# ═══════════════════════════════════════════════════
def fig6b(runs):
    data = [r for r in runs if r["baseline"] == "pythia" and r["solver"] == "gpt-oss:20b"
            and r["temp"] == 0.3 and r["draft"] not in ("none", "gpt-oss:20b") and r["benefit"] > 1]
    data = dedup_best(data, lambda r: r["draft"])
    data = sorted(data, key=lambda x: -x["benefit"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 2.8), gridspec_kw={"wspace": 0.35})

    labels = [model_label(r["draft"]) for r in data]
    colors = [family_color(r["draft"]) for r in data]
    x = np.arange(len(data))

    # Left: Net Benefit
    bars = ax1.bar(x, [r["benefit"] for r in data], color=colors,
                   edgecolor="white", linewidth=0.8, width=0.6)
    for i, r in enumerate(data):
        ax1.text(i, r["benefit"] + 0.3, f'{r["benefit"]:.1f}',
                 fontsize=8, ha="center", va="bottom", fontweight="bold")
    ax1.set_ylabel("Net Benefit")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=7.5, rotation=20, ha="right")
    ax1.set_title("(a) Net Benefit by Draft Family")
    ax1.set_ylim(0, max(r["benefit"] for r in data) * 1.15)

    # Right: Salvage vs Waste (grouped bars)
    w = 0.3
    ax2.bar(x - w/2, [r["salvage"] for r in data], w, label="Salvage ($\\sigma$)",
            color=colors, edgecolor="white", linewidth=0.8)
    ax2.bar(x + w/2, [r["waste"] for r in data], w, label="Waste ($W$)",
            color=colors, edgecolor="white", linewidth=0.8, alpha=0.4, hatch="///")
    ax2.set_ylabel("Ratio")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=7.5, rotation=20, ha="right")
    ax2.set_title("(b) Salvage vs. Wasted Compute")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8)
    ax2.set_ylim(0, 1.1)

    fig.tight_layout()
    save(fig, "fig6b_draft_family")
    print(f"  fig6b: {len(data)} draft models")


# ═══════════════════════════════════════════════════
#  FIG 6c: TEMPERATURE SENSITIVITY
# ═══════════════════════════════════════════════════
def fig6c(runs):
    temp_runs = [r for r in runs if r["solver"] == "gpt-oss:120b" and r["draft"] == "qwen3:4b"
                 and r["baseline"] in ("pythia", "swol")]

    pythia_t, swol_t = {}, {}
    for r in temp_runs:
        bucket = pythia_t if r["baseline"] == "pythia" else swol_t
        if r["temp"] not in bucket or r["benefit"] > bucket[r["temp"]]["benefit"]:
            bucket[r["temp"]] = r

    temps = sorted(pythia_t.keys())
    if len(temps) < 2:
        print("  fig6c: skipped (not enough data)")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.2), gridspec_kw={"wspace": 0.35})

    # Left: Salvage & Waste vs Temp
    ax1.plot(temps, [pythia_t[t]["salvage"] for t in temps], "o-", color=C_BLUE,
             label="Pythia $\\sigma$", markersize=6, linewidth=2)
    ax1.plot(temps, [swol_t.get(t, {"salvage": 0})["salvage"] for t in temps], "s--",
             color=C_RED, label="SwoL $\\sigma$", markersize=6, linewidth=2)
    ax1.plot(temps, [pythia_t[t]["waste"] for t in temps], "^-", color=C_BLUE,
             label="Pythia $W$", markersize=5, linewidth=1.2, alpha=0.5)
    ax1.plot(temps, [swol_t.get(t, {"waste": 0})["waste"] for t in temps], "v--",
             color=C_RED, label="SwoL $W$", markersize=5, linewidth=1.2, alpha=0.5)
    ax1.set_xlabel("Temperature")
    ax1.set_ylabel("Ratio")
    ax1.set_title("(a) Salvage & Waste vs. Temperature")
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4, fontsize=7)
    ax1.set_ylim(0, 1.0)
    ax1.set_xticks(temps)

    # Right: Net Benefit vs Temp
    ax2.plot(temps, [pythia_t[t]["benefit"] for t in temps], "o-", color=C_BLUE,
             label="Pythia (learner)", markersize=7, linewidth=2.5)
    ax2.plot(temps, [swol_t.get(t, {"benefit": 0})["benefit"] for t in temps], "s--",
             color=C_RED, label="SwoL (frozen)", markersize=7, linewidth=2.5)

    # Highlight peak
    peak_t = max(temps, key=lambda t: pythia_t[t]["benefit"])
    peak_v = pythia_t[peak_t]["benefit"]
    ax2.annotate(f"Peak: T={peak_t}", xy=(peak_t, peak_v),
                 xytext=(peak_t + 0.12, peak_v - 0.5),
                 fontsize=7, fontweight="bold", color=C_BLUE,
                 arrowprops=dict(arrowstyle="->", color=C_BLUE, lw=1))

    ax2.set_xlabel("Temperature")
    ax2.set_ylabel("Net Benefit")
    ax2.set_title("(b) Net Benefit vs. Temperature")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=8)
    ax2.set_xticks(temps)

    fig.tight_layout()
    save(fig, "fig6c_temperature")
    print(f"  fig6c: {len(temps)} temperatures")


# ═══════════════════════════════════════════════════
#  FIG 6d: BASELINE COMPARISON (best config)
# ═══════════════════════════════════════════════════
def fig6d(runs):
    # Collect best run per baseline from 120b/20b or 120b/4b configs
    baselines_data = {}
    for r in runs:
        if r["solver"] == "gpt-oss:120b" and r["draft"] in ("gpt-oss:20b", "qwen3:4b") and r["temp"] == 0.3:
            bl = r["baseline"]
            if bl not in baselines_data or r["benefit"] > baselines_data[bl]["benefit"]:
                baselines_data[bl] = r

    order = ["oracle", "pythia", "swol", "ns"]
    labels_map = {"oracle": "Oracle", "pythia": "Pythia",
                  "swol": "SwoL", "ns": "No Spec"}
    subtitle_map = {"oracle": "(upper bound)", "pythia": "(full system)",
                    "swol": "(no learner)", "ns": "(solver only)"}
    colors_map = {"oracle": C_GRAY, "pythia": C_BLUE, "swol": C_RED,
                  "ns": C_ORANGE, "sh": C_GREEN}

    present = [b for b in order if b in baselines_data]
    data = [baselines_data[b] for b in present]
    labels = [labels_map[b] for b in present]
    colors = [colors_map[b] for b in present]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.5), gridspec_kw={"wspace": 0.35})
    x = np.arange(len(data))

    # Left: Net Benefit (horizontal bars for clean labels)
    ax1.barh(x, [r["benefit"] for r in data], color=colors,
             edgecolor="white", linewidth=0.8, height=0.55)
    for i, r in enumerate(data):
        ax1.text(r["benefit"] + 0.3, x[i], f'{r["benefit"]:.1f}',
                 fontsize=9, ha="left", va="center", fontweight="bold")
    ax1.set_xlabel("Net Benefit")
    ax1.set_yticks(x)
    ax1.set_yticklabels([f"{l}\n{subtitle_map[b]}" for l, b in zip(labels, present)], fontsize=8)
    ax1.set_title("(a) Net Benefit by Baseline")
    ax1.set_xlim(0, max(r["benefit"] for r in data) * 1.25)
    ax1.invert_yaxis()

    # Right: Salvage ratio (horizontal bars)
    ax2.barh(x, [r["salvage"] for r in data], color=colors,
             edgecolor="white", linewidth=0.8, height=0.55, label="Salvage ($\\sigma$)")
    ax2.barh(x, [r["waste"] for r in data], left=[r["salvage"] for r in data],
             color=colors, edgecolor="white", linewidth=0.8, height=0.55,
             alpha=0.3, hatch="///", label="Waste ($W$)")
    for i, r in enumerate(data):
        if r["salvage"] > 0:
            ax2.text(r["salvage"] / 2, x[i], f'{r["salvage"]:.2f}',
                     fontsize=8, ha="center", va="center", color="white", fontweight="bold")
    ax2.set_xlabel("Ratio")
    ax2.set_yticks(x)
    ax2.set_yticklabels([f"{l}\n{subtitle_map[b]}" for l, b in zip(labels, present)], fontsize=8)
    ax2.set_title("(b) Salvage & Waste")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8)
    ax2.set_xlim(0, 1.3)
    ax2.invert_yaxis()

    fig.tight_layout()
    save(fig, "fig6d_baseline_comparison")
    print(f"  fig6d: {len(data)} baselines")


# ═══════════════════════════════════════════════════
#  FIG 6e: CLOUD vs EDGE SOLVER (horizontal bar)
# ═══════════════════════════════════════════════════
def fig6e(runs):
    data = [r for r in runs if r["baseline"] == "pythia" and r["temp"] == 0.3
            and r["draft"] == "qwen3:4b" and r["benefit"] > 1]
    data = dedup_best(data, lambda r: r["solver"])
    data = sorted(data, key=lambda x: -x["benefit"])

    if not data:
        print("  fig6e: skipped (no data)")
        return

    fig, ax = plt.subplots(figsize=(3.5, 3.0))

    labels = [model_label(r["solver"]) for r in data]
    y = np.arange(len(data))
    colors = [family_color(r["solver"]) for r in data]

    bars = ax.barh(y, [r["benefit"] for r in data], color=colors,
                   edgecolor="white", linewidth=0.8, height=0.55)

    for i, r in enumerate(data):
        provider = "Cloud" if "claude" in r["solver"] else "Edge"
        ax.text(r["benefit"] + 0.3, y[i],
                f'$\\sigma$={r["salvage"]:.2f}  [{provider}]',
                fontsize=7, va="center")

    ax.set_xlabel("Net Benefit")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title("Solver Comparison\n(draft = Qwen3 4B)")
    ax.invert_yaxis()
    ax.set_xlim(0, max(r["benefit"] for r in data) * 1.35)

    fig.tight_layout()
    save(fig, "fig6e_cloud_vs_edge")
    print(f"  fig6e: {len(data)} solvers")


# ═══════════════════════════════════════════════════
#  FIG 6f: LEARNER vs SwoL (horizontal grouped)
# ═══════════════════════════════════════════════════
def fig6f(runs):
    configs = defaultdict(dict)
    for r in runs:
        if r["baseline"] in ("pythia", "swol") and r["temp"] == 0.3 and r["draft"] != "none":
            key = (r["solver"], r["draft"])
            bl = r["baseline"]
            if bl not in configs[key] or r["benefit"] > configs[key][bl]["benefit"]:
                configs[key][bl] = r

    pairs = [(k, v) for k, v in configs.items() if "pythia" in v and "swol" in v]
    if not pairs:
        print("  fig6f: skipped (no data)")
        return

    pairs.sort(key=lambda x: -(x[1]["pythia"]["benefit"] - x[1]["swol"]["benefit"]))

    # Only show top configs where delta is meaningful (skip near-zero deltas for clarity)
    fig, ax = plt.subplots(figsize=(7, 4.0))

    labels = [f"{model_label(k[0])} / {model_label(k[1])}" for k, _ in pairs]
    y = np.arange(len(pairs))
    h = 0.3

    pythia_vals = [v["pythia"]["benefit"] for _, v in pairs]
    swol_vals = [v["swol"]["benefit"] for _, v in pairs]

    ax.barh(y + h/2, pythia_vals, h, label="Pythia (adaptive learner)",
            color=C_BLUE, edgecolor="white", linewidth=0.5)
    ax.barh(y - h/2, swol_vals, h, label="SwoL (frozen confidence)",
            color=C_RED, edgecolor="white", linewidth=0.5)

    # Delta annotations
    for i, (k, v) in enumerate(pairs):
        delta = v["pythia"]["benefit"] - v["swol"]["benefit"]
        color = C_BLUE if delta > 0 else C_RED
        symbol = "+" if delta > 0 else ""
        maxval = max(pythia_vals[i], swol_vals[i])
        ax.text(maxval + 0.3, y[i], f"$\\Delta$={symbol}{delta:.1f}",
                fontsize=7, fontweight="bold", va="center", color=color)

    ax.set_xlabel("Net Benefit")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_title("Adaptive Learner vs. Static Speculation")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
    ax.invert_yaxis()
    ax.set_xlim(0, max(max(pythia_vals), max(swol_vals)) * 1.2)

    fig.tight_layout()
    save(fig, "fig6f_learner_vs_swol")
    print(f"  fig6f: {len(pairs)} config pairs")


# ═══════════════════════════════════════════════════
#  FIG 6g: CROSS-WORKLOAD COMPARISON
# ═══════════════════════════════════════════════════
def fig6g(all_wl_runs):
    # Group by (solver, draft) and find configs present in 2+ workloads
    configs = defaultdict(lambda: defaultdict(list))
    for r in all_wl_runs:
        if r["baseline"] == "pythia" and r["temp"] == 0.3 and r["n"] == 20:
            key = (r["solver"], r["draft"])
            configs[key][r["workload"]].append(r)

    # Keep configs with 2+ workloads, pick best per workload
    plot_data = []
    for (solver, draft), wl_dict in configs.items():
        if len(wl_dict) < 2:
            continue
        entry = {"solver": solver, "draft": draft}
        for wl in ["hpc_cg", "sdp", "rwa"]:
            if wl in wl_dict:
                best = max(wl_dict[wl], key=lambda x: x["benefit"])
                entry[wl] = best
        plot_data.append(entry)

    if not plot_data:
        print("  fig6g: skipped (no cross-workload data)")
        return

    plot_data.sort(key=lambda x: -x.get("hpc_cg", {}).get("benefit", 0))
    plot_data = plot_data[:8]  # top 8

    fig, ax = plt.subplots(figsize=(7, 3.5))
    labels = [f"{model_label(e['solver'])} / {model_label(e['draft'])}" for e in plot_data]
    y = np.arange(len(plot_data))
    h = 0.25

    wl_colors = {"hpc_cg": C_BLUE, "sdp": C_ORANGE, "rwa": C_GREEN}
    wl_labels = {"hpc_cg": "HPC-CG", "sdp": "SDP", "rwa": "RWA"}

    for i, wl in enumerate(["hpc_cg", "sdp", "rwa"]):
        vals = [e.get(wl, {}).get("benefit", 0) for e in plot_data]
        offset = (i - 1) * h
        ax.barh(y + offset, vals, h, label=wl_labels[wl],
                color=wl_colors[wl], edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Net Benefit")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_title("Cross-Workload Comparison (Pythia)")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
    ax.invert_yaxis()

    fig.tight_layout()
    save(fig, "fig6g_cross_workload")
    print(f"  fig6g: {len(plot_data)} configs × 3 workloads")


# ═══════════════════════════════════════════════════
#  FIG 6h: LEARNER CONVERGENCE (n=50 vs n=20)
# ═══════════════════════════════════════════════════
def fig6h(runs):
    # Find n=50 Pythia and SwoL runs
    long_pythia = [r for r in runs if r["baseline"] == "pythia" and r["n"] >= 50 and r["temp"] == 0.3]
    long_swol = [r for r in runs if r["baseline"] == "swol" and r["n"] >= 50 and r["temp"] == 0.3]
    short_pythia = [r for r in runs if r["baseline"] == "pythia" and r["n"] == 20 and r["temp"] == 0.3
                    and r["draft"] != "none"]
    short_swol = [r for r in runs if r["baseline"] == "swol" and r["n"] == 20 and r["temp"] == 0.3
                  and r["draft"] != "none"]

    if not long_pythia:
        print("  fig6h: skipped (no n=50 runs)")
        return

    # Combine for comparison
    all_configs = defaultdict(dict)
    for r in long_pythia:
        all_configs[(r["solver"], r["draft"])]["pythia_50"] = r
    for r in long_swol:
        all_configs[(r["solver"], r["draft"])]["swol_50"] = r
    for r in short_pythia:
        key = (r["solver"], r["draft"])
        if key in all_configs:
            if "pythia_20" not in all_configs[key] or r["benefit"] > all_configs[key]["pythia_20"]["benefit"]:
                all_configs[key]["pythia_20"] = r
    for r in short_swol:
        key = (r["solver"], r["draft"])
        if key in all_configs:
            if "swol_20" not in all_configs[key] or r["benefit"] > all_configs[key]["swol_20"]["benefit"]:
                all_configs[key]["swol_20"] = r

    configs_with_both = [(k, v) for k, v in all_configs.items()
                         if "pythia_50" in v and "swol_50" in v]

    if not configs_with_both:
        # Just show n=50 runs
        fig, ax = plt.subplots(figsize=(3.5, 2.8))
        labels = [f"{model_label(r['solver'])} /\n{model_label(r['draft'])}" for r in long_pythia]
        y = np.arange(len(long_pythia))
        h = 0.3
        ax.barh(y + h/2, [r["benefit"] for r in long_pythia], h, label="Pythia (n=50)",
                color=C_BLUE, edgecolor="white")
        ax.barh(y - h/2, [r["benefit"] for r in long_swol[:len(long_pythia)]], h, label="SwoL (n=50)",
                color=C_RED, edgecolor="white")
        for i, r in enumerate(long_pythia):
            delta = r["benefit"] - (long_swol[i]["benefit"] if i < len(long_swol) else 0)
            ax.text(max(r["benefit"], long_swol[i]["benefit"] if i < len(long_swol) else 0) + 0.5,
                    y[i], f"$\\Delta$={delta:+.1f}", fontsize=7, fontweight="bold", va="center",
                    color=C_BLUE if delta > 0 else C_RED)
        ax.set_xlabel("Net Benefit")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_title("Learner Convergence (n=50)")
        ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
        ax.invert_yaxis()
        fig.tight_layout()
        save(fig, "fig6h_convergence")
        print(f"  fig6h: {len(long_pythia)} configs at n=50")
        return

    fig, ax = plt.subplots(figsize=(7, 3.0))
    labels = [f"{model_label(k[0])} / {model_label(k[1])}" for k, _ in configs_with_both]
    y = np.arange(len(configs_with_both))
    h = 0.18

    for i, (key, vals) in enumerate(configs_with_both):
        p50 = vals["pythia_50"]["benefit"]
        s50 = vals["swol_50"]["benefit"]
        p20 = vals.get("pythia_20", {}).get("benefit", 0)
        s20 = vals.get("swol_20", {}).get("benefit", 0)

        ax.barh(y[i] + 1.5*h, p50, h, color=C_BLUE, edgecolor="white",
                label="Pythia n=50" if i == 0 else "")
        ax.barh(y[i] + 0.5*h, s50, h, color=C_RED, edgecolor="white",
                label="SwoL n=50" if i == 0 else "")
        ax.barh(y[i] - 0.5*h, p20, h, color=C_BLUE, edgecolor="white", alpha=0.4, hatch="...",
                label="Pythia n=20" if i == 0 else "")
        ax.barh(y[i] - 1.5*h, s20, h, color=C_RED, edgecolor="white", alpha=0.4, hatch="...",
                label="SwoL n=20" if i == 0 else "")

        delta_50 = p50 - s50
        ax.text(max(p50, s50) + 0.5, y[i], f"$\\Delta$@50={delta_50:+.1f}",
                fontsize=7, fontweight="bold", va="center",
                color=C_BLUE if delta_50 > 0 else C_RED)

    ax.set_xlabel("Net Benefit")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title("Learner Convergence: n=20 vs n=50")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, fontsize=7)
    ax.invert_yaxis()

    fig.tight_layout()
    save(fig, "fig6h_convergence")
    print(f"  fig6h: {len(configs_with_both)} configs, n=20 vs n=50")


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    print("Loading HPC-CG runs...")
    runs = load_all("hpc_cg")
    print(f"  HPC-CG: {len(runs)} runs")

    print("Loading all workloads...")
    all_wl_runs = load_all_workloads()
    print(f"  Total: {len(all_wl_runs)} runs across all workloads\n")

    print("Generating figures...")
    fig6a(runs)
    fig6b(runs)
    fig6c(runs)
    fig6d(runs)
    fig6e(runs)
    fig6f(runs)
    fig6g(all_wl_runs)
    fig6h(runs)

    print(f"\nAll figures saved to: {FIGDIR}/")
    for f in sorted(FIGDIR.iterdir()):
        print(f"  {f.name} ({f.stat().st_size / 1024:.0f} KB)")
