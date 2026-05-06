#!/usr/bin/env python3
"""
plot_results.py — Extract, summarize, and plot multi-model benchmark results.

Auto-discovers all result files under results/**/plan_execute.json and
generates cross-model comparison plots.

Generates:
  1. Per-model stacked bar (planning vs execution) grouped by problem type
  2. Cross-model comparison: dispatch fraction (sequential and parallel)
  3. Cross-model comparison: absolute planning time
  4. Summary CSV for further analysis
  5. §2.5 Figure 1: Dispatch latency box plot (plan-only data)
  6. §2.5 Figure 2: Dispatch predictability heatmap

Usage:
    python plot_results.py                                    # all legacy plots
    python plot_results.py --figure 1                         # §2.5 dispatch latency
    python plot_results.py --figure 2                         # §2.5 predictability
    python plot_results.py --figure all                       # both §2.5 figures
    python plot_results.py --results-dir results --figure all
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
import numpy as np
from sklearn.cluster import KMeans


# ── Data loading ──────────────────────────────────────────────────────


# Models to exclude from plots (set to empty to include all)
EXCLUDE_MODELS = {
    "qwen3.5_9b", "qwen3_8b", "qwen3.5_4b", "qwen3_4b",
    "gemini_gemini-2.5-flash", "gemini_gemini-2.5-flash-lite",
}


def discover_results(results_dir: Path) -> dict[str, list[dict]]:
    """Find all plan_execute.json files, keyed by model tag (folder name).

    Filters out excluded models and planner-failed runs.
    """
    models = {}
    for f in sorted(results_dir.glob("**/plan_execute.json")):
        model_tag = f.parent.name
        # Check exclusion against the model name prefix (before _tok)
        model_prefix = model_tag.rsplit("_tok", 1)[0]
        if model_prefix in EXCLUDE_MODELS:
            print(f"  Skipping {model_tag} (excluded)")
            continue

        with open(f) as fh:
            data = json.load(fh)
        if not data:
            continue

        # Separate valid and failed runs
        valid = [r for r in data if not r.get("planner_failed", False)]
        failed = [r for r in data if r.get("planner_failed", False)]
        if failed:
            print(f"  Loaded {model_tag}: {len(valid)} valid, {len(failed)} planner-failed (excluded from plots)")
        else:
            print(f"  Loaded {model_tag}: {len(valid)} records")

        if valid:
            models[model_tag] = valid

    return models


def aggregate_by_query(results: list[dict]) -> dict[str, dict]:
    """Aggregate repetitions per query_id: mean ± std."""
    by_query: dict[str, list[dict]] = {}
    for r in results:
        by_query.setdefault(r["query_id"], []).append(r)

    agg = {}
    for qid, runs in sorted(by_query.items()):
        planning = [r["planning_s"] for r in runs]
        exec_seq = [r["execution_seq_s"] for r in runs]
        exec_par = [r["execution_par_s"] for r in runs]
        total_seq = [r["total_seq_s"] for r in runs]
        total_par = [r["total_par_s"] for r in runs]
        frac_seq = [r["dispatch_fraction_seq"] for r in runs]
        frac_par = [r["dispatch_fraction_par"] for r in runs]
        agg[qid] = {
            "model": runs[0]["model"],
            "domain": runs[0]["domain"],
            "complexity": runs[0]["complexity"],
            "planning_mean": np.mean(planning),
            "planning_std": np.std(planning),
            "exec_seq_mean": np.mean(exec_seq),
            "exec_seq_std": np.std(exec_seq),
            "exec_par_mean": np.mean(exec_par),
            "exec_par_std": np.std(exec_par),
            "total_seq_mean": np.mean(total_seq),
            "total_par_mean": np.mean(total_par),
            "frac_seq_mean": np.mean(frac_seq),
            "frac_seq_std": np.std(frac_seq),
            "frac_par_mean": np.mean(frac_par),
            "frac_par_std": np.std(frac_par),
            "num_agents": np.mean([r["num_agent_calls"] for r in runs]),
            "n_runs": len(runs),
        }
    return agg


def aggregate_by_problem_type(results: list[dict]) -> dict[str, dict]:
    """Aggregate by problem_type (from query metadata)."""
    by_ptype: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        # Extract problem type from query_id: gen_omp_26_reduce_... -> reduce
        parts = r["query_id"].split("_")
        # Find problem type from the known set
        ptype = "unknown"
        for known in ["reduce", "transform", "sort", "search", "histogram",
                       "scan", "graph", "geometry", "dense_la", "sparse_la",
                       "fft", "stencil"]:
            if known in r["query_id"]:
                ptype = known
                break
        by_ptype[ptype].append(r)

    agg = {}
    for ptype, runs in sorted(by_ptype.items()):
        planning = [r["planning_s"] for r in runs]
        exec_seq = [r["execution_seq_s"] for r in runs]
        exec_par = [r["execution_par_s"] for r in runs]
        total_seq = [r["total_seq_s"] for r in runs]
        total_par = [r["total_par_s"] for r in runs]
        frac_seq = [r["dispatch_fraction_seq"] for r in runs]
        frac_par = [r["dispatch_fraction_par"] for r in runs]
        agg[ptype] = {
            "planning_mean": np.mean(planning),
            "planning_std": np.std(planning),
            "exec_seq_mean": np.mean(exec_seq),
            "exec_par_mean": np.mean(exec_par),
            "total_seq_mean": np.mean(total_seq),
            "total_par_mean": np.mean(total_par),
            "frac_seq_mean": np.mean(frac_seq),
            "frac_par_mean": np.mean(frac_par),
            "num_agents": np.mean([r["num_agent_calls"] for r in runs]),
            "n_runs": len(runs),
        }
    return agg


# ── §2.5 Data Loading ────────────────────────────────────────────────


# Display names for model tags (updated as new models are added)
MODEL_DISPLAY: dict[str, str] = {
    "claude_claude-haiku-4-5-20251001_tokunlim": "Haiku\n(4.5)",
    "claude_claude-opus-4-6_tokunlim": "Opus\n(4.6)",
    "claude_claude-sonnet-4-6_tokunlim": "Sonnet\n(4.6)",
    "claude_claude-sonnet-4-20250514_tokunlim": "Sonnet\n(4)",
    "ollama-sdk_gemma4_e2b_tok2048": "Gemma4\n(E2B)",
    "ollama-sdk_gemma4_26b_tok2048": "Gemma4\n(26B)",
    "ollama-sdk_gemma4_26b_tokunlim": "Gemma4\n(26B)",
    "ollama-sdk_gpt-oss_20b_tok2048": "GPT-OSS\n(20B)",
    "ollama-sdk_gpt-oss_20b_tokunlim": "GPT-OSS\n(20B)",
    "ollama-sdk_mistral-small3.2_24b_tok2048": "Mistral\n(24B)",
    "ollama-sdk_nemotron-3-nano_4b_tok2048": "Nemotron\n(4B)",
    "ollama_gemma4_e2b_tok2048": "Gemma4\n(E2B)",
    "ollama_gemma4_26b_tok2048": "Gemma4\n(26B)",
    "ollama_gpt-oss_20b_tok2048": "GPT-OSS\n(20B)",
    "ollama_mistral-small3.2_24b_tok2048": "Mistral\n(24B)",
    "ollama_nemotron-3-nano_4b_tok2048": "Nemotron\n(4B)",
}

# Ordering for consistent x-axis (cloud first, then local by size)
MODEL_ORDER = [
    "Opus\n(4.6)", "Sonnet\n(4.6)", "Sonnet\n(4)", "Haiku\n(4.5)",
    "Gemma4\n(26B)", "Mistral\n(24B)", "GPT-OSS\n(20B)",
    "Gemma4\n(E2B)", "Nemotron\n(4B)",
]

WORKLOAD_DISPLAY: dict[str, str] = {
    "hpc_cg": "HPC Code Gen",
    "sdp": "Data Pipelines",
    "rwa": "Research Workflows",
}


def short_model_name(tag: str) -> str:
    """Convert model directory tag to short display name."""
    if tag in MODEL_DISPLAY:
        return MODEL_DISPLAY[tag]
    # Fallback: strip backend prefix and token suffix
    parts = tag.split("_")
    return "_".join(parts[1:-1]) if len(parts) >= 3 else tag


def discover_results_nested(results_dir: Path) -> dict[str, dict[str, list[dict]]]:
    """Discover results organized as {workload: {model_tag: [records]}}.

    Handles nested structure: results/{workload}/{backend}_{model}_{tokens}/plan_execute.json
    Falls back to flat structure: results/{backend}_{model}_{tokens}/plan_execute.json
    """
    data: dict[str, dict[str, list[dict]]] = {}

    for f in sorted(results_dir.glob("**/plan_execute.json")):
        model_tag = f.parent.name
        # Determine workload: if parent's parent is results_dir, it's flat (no workload)
        if f.parent.parent == results_dir:
            workload = "unknown"
        else:
            workload = f.parent.parent.name

        # Skip workspace dirs and excluded models
        if workload == "workspace" or model_tag == "workspace":
            continue
        model_prefix = model_tag.rsplit("_tok", 1)[0]
        if model_prefix in EXCLUDE_MODELS:
            continue

        with open(f) as fh:
            records = json.load(fh)
        if not records:
            continue

        valid = [r for r in records if not r.get("planner_failed", False)]
        if not valid:
            continue

        data.setdefault(workload, {})[model_tag] = valid

    return data


def load_all_plan_logs(results_dir: Path) -> dict[str, dict[str, dict[str, list[dict]]]]:
    """Load plan logs: {workload: {model_tag: {query_id: plan_steps}}}.

    Each plan_steps is a list of dicts with keys: step, agent, depends_on.
    """
    logs: dict[str, dict[str, dict[str, list[dict]]]] = {}

    for f in sorted(results_dir.glob("**/logs/*_plan.json")):
        # Path: results/{workload}/{model_tag}/logs/{query_id}_rep{N}_plan.json
        log_dir = f.parent        # logs/
        model_dir = log_dir.parent  # {model_tag}/
        model_tag = model_dir.name

        if model_dir.parent == results_dir:
            workload = "unknown"
        else:
            workload = model_dir.parent.name

        if workload == "workspace" or model_tag == "workspace":
            continue
        model_prefix = model_tag.rsplit("_tok", 1)[0]
        if model_prefix in EXCLUDE_MODELS:
            continue

        with open(f) as fh:
            plan_data = json.load(fh)

        if plan_data.get("planner_failed", False):
            continue

        query_id = plan_data.get("query_id", "")
        steps = plan_data.get("plan", [])
        if not query_id or not steps:
            continue

        logs.setdefault(workload, {}).setdefault(model_tag, {})[query_id] = steps

    return logs


# ── §2.5 Similarity Metric ──────────────────────────────────────────


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Longest Common Subsequence length."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _dag_edges_by_role(steps: list[dict]) -> set[tuple[str, str]]:
    """Convert numbered dependency edges to agent-role pair edges."""
    step_to_agent = {s.get("step", i + 1): s.get("agent", "") for i, s in enumerate(steps)}
    edges = set()
    for s in steps:
        step_num = s.get("step", 0)
        agent = s.get("agent", "")
        for dep in s.get("depends_on", []):
            dep_agent = step_to_agent.get(dep, "")
            if dep_agent and agent:
                edges.add((dep_agent, agent))
    return edges


def compute_plan_similarity(plan_a: list[dict], plan_b: list[dict]) -> float:
    """Compute structural similarity between two dispatch plans.

    Combines:
      - Agent sequence similarity (normalized LCS): weight 0.5
      - DAG edge Jaccard similarity: weight 0.5

    Returns value in [0, 1].
    """
    # Agent sequences
    seq_a = [s.get("agent", "") for s in plan_a]
    seq_b = [s.get("agent", "") for s in plan_b]

    if not seq_a and not seq_b:
        return 1.0
    if not seq_a or not seq_b:
        return 0.0

    lcs = _lcs_length(seq_a, seq_b)
    seq_sim = 2.0 * lcs / (len(seq_a) + len(seq_b))

    # DAG edge similarity
    edges_a = _dag_edges_by_role(plan_a)
    edges_b = _dag_edges_by_role(plan_b)

    if not edges_a and not edges_b:
        dag_sim = 1.0  # both have no dependencies (linear chains)
    elif not edges_a or not edges_b:
        dag_sim = 0.0
    else:
        intersection = edges_a & edges_b
        union = edges_a | edges_b
        dag_sim = len(intersection) / len(union)

    return 0.5 * seq_sim + 0.5 * dag_sim


def compute_pairwise_similarity(
    plans_by_model: dict[str, dict[str, list[dict]]],
) -> dict[tuple[str, str], dict]:
    """Compute mean pairwise plan similarity across shared queries.

    Returns {(model_a, model_b): {"mean": float, "std": float, "n": int}}.
    """
    models = sorted(plans_by_model.keys())
    results = {}

    for i, m_a in enumerate(models):
        for j, m_b in enumerate(models):
            if i > j:
                continue
            # Find shared queries
            shared = set(plans_by_model[m_a].keys()) & set(plans_by_model[m_b].keys())
            if not shared:
                results[(m_a, m_b)] = {"mean": float("nan"), "std": 0.0, "n": 0}
                continue

            sims = []
            for qid in shared:
                sim = compute_plan_similarity(
                    plans_by_model[m_a][qid], plans_by_model[m_b][qid]
                )
                sims.append(sim)

            results[(m_a, m_b)] = {
                "mean": float(np.mean(sims)),
                "std": float(np.std(sims)),
                "n": len(sims),
            }
            results[(m_b, m_a)] = results[(m_a, m_b)]

    return results


# ── §2.5 IEEE Style ─────────────────────────────────────────────────


def setup_ieee_style():
    """Configure matplotlib for IEEE two-column format."""
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.linewidth": 0.5,
        "lines.linewidth": 1.0,
        "grid.linewidth": 0.3,
    })


# ── §2.5 Figure 1: Dispatch Latency Box Plot ────────────────────────


# Color palette: cloud API models vs local models
_CLOUD_COLOR = "#2c3e50"
_LOCAL_COLOR = "#e67e22"
_CLOUD_MODELS = {"Opus\n(4.6)", "Sonnet\n(4.6)", "Sonnet\n(4)", "Haiku\n(4.5)"}


def plot_dispatch_latency_boxplot(
    nested_data: dict[str, dict[str, list[dict]]], outdir: Path,
):
    """§2.5 Figure 1: Box plot of planning latency, faceted by workload."""
    setup_ieee_style()

    workloads = [w for w in ["hpc_cg", "sdp", "rwa"] if w in nested_data]
    if not workloads:
        workloads = sorted(nested_data.keys())

    # Collect all models across workloads, sort by MODEL_ORDER
    all_models_set: set[str] = set()
    for wl in workloads:
        for tag in nested_data[wl]:
            all_models_set.add(short_model_name(tag))
    all_models = [m for m in MODEL_ORDER if m in all_models_set]
    # Add any not in MODEL_ORDER
    for m in sorted(all_models_set):
        if m not in all_models:
            all_models.append(m)

    n_workloads = len(workloads)
    n_models = len(all_models)

    fig, axes = plt.subplots(
        1, n_workloads, sharey=True,
        figsize=(5 * n_workloads, 3),
        squeeze=False,
    )
    axes = axes[0]

    for ax_idx, wl in enumerate(workloads):
        ax = axes[ax_idx]
        models_in_wl = nested_data[wl]

        # Build data arrays aligned with all_models
        box_data = []
        box_positions = []
        box_colors = []
        present_labels = []

        for i, model_name in enumerate(all_models):
            # Find the tag for this model name in this workload
            tag = None
            for t in models_in_wl:
                if short_model_name(t) == model_name:
                    tag = t
                    break
            if tag is None:
                continue

            values = [r["planning_s"] for r in models_in_wl[tag]]
            box_data.append(values)
            box_positions.append(len(present_labels))
            color = _CLOUD_COLOR if model_name in _CLOUD_MODELS else _LOCAL_COLOR
            box_colors.append(color)
            present_labels.append(model_name)

        if not box_data:
            continue

        # Bar chart with mean height
        bar_color = "#5b7ea1"
        dot_color = "#e74c3c"
        means = [np.mean(v) for v in box_data]
        x = np.arange(len(box_data))

        ax.bar(x, means, width=0.5, color=bar_color, alpha=0.7, zorder=2)

        # Jittered scatter overlay for individual queries
        rng = np.random.default_rng(42)
        for i, values in enumerate(box_data):
            jitter = rng.uniform(-0.12, 0.12, size=len(values))
            ax.scatter(
                x[i] + jitter, values,
                s=15, alpha=0.7, color=dot_color,
                edgecolors="white", linewidths=0.3, zorder=3,
            )

        ax.set_title(WORKLOAD_DISPLAY.get(wl, wl), fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(present_labels, rotation=0, ha="center")
        ax.grid(axis="y", alpha=0.3)

        if ax_idx == 0:
            ax.set_ylabel("Planning Latency (s)")

    # Legend: bar = mean, dot = individual query
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_handles = [
        Patch(facecolor=bar_color, alpha=0.7, label="Mean latency"),
        Line2D([0], [0], marker="o", color=dot_color, linestyle="None",
               markersize=4, markeredgecolor="white", markeredgewidth=0.3,
               label="Per-query latency"),
    ]
    axes[-1].legend(handles=legend_handles, loc="upper right", framealpha=0.9)

    fig.tight_layout()
    for fmt in ["pdf", "png", "eps"]:
        path = outdir / f"fig1_dispatch_latency.{fmt}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"  Saved: {outdir}/fig1_dispatch_latency.{{pdf,png}}")
    plt.close(fig)


# ── §2.5 Figure 2: Dispatch Predictability Heatmap ──────────────────


def plot_dispatch_predictability_heatmap(
    plan_logs: dict[str, dict[str, dict[str, list[dict]]]],
    outdir: Path,
):
    """§2.5 Figure 2: Pairwise plan similarity heatmap, one panel per workload."""
    setup_ieee_style()

    workloads = [w for w in ["hpc_cg", "sdp", "rwa"] if w in plan_logs]
    if not workloads:
        workloads = sorted(plan_logs.keys())

    # Build global model list for consistent axes across panels
    all_models_set: set[str] = set()
    for wl in workloads:
        for tag in plan_logs[wl]:
            all_models_set.add(short_model_name(tag))

    model_names = [m for m in MODEL_ORDER if m in all_models_set]
    for m in sorted(all_models_set):
        if m not in model_names:
            model_names.append(m)
    n = len(model_names)

    if n < 2:
        print("  Skipping Figure 2: need at least 2 models with plan logs")
        return

    n_workloads = len(workloads)
    # Extra width for colorbar; use constrained_layout to avoid overlap
    fig, axes = plt.subplots(
        1, n_workloads,
        figsize=(4.5 * n_workloads + 0.8, 4),
        squeeze=False,
        gridspec_kw={"wspace": 0.05},
        constrained_layout=True,
    )
    axes = axes[0]

    for ax_idx, wl in enumerate(workloads):
        ax = axes[ax_idx]

        # Build per-model plans for this workload
        plans_by_name: dict[str, dict[str, list[dict]]] = {}
        for tag, queries in plan_logs[wl].items():
            plans_by_name[short_model_name(tag)] = queries

        # Compute pairwise similarity for models present in this workload
        pairwise = compute_pairwise_similarity(
            {m: plans_by_name[m] for m in model_names if m in plans_by_name}
        )

        matrix = np.full((n, n), float("nan"))
        for i, m_a in enumerate(model_names):
            for j, m_b in enumerate(model_names):
                entry = pairwise.get((m_a, m_b))
                if entry is not None:
                    matrix[i, j] = entry["mean"]

        im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="equal")

        # Annotate cells
        for i in range(n):
            for j in range(n):
                val = matrix[i, j]
                if np.isnan(val):
                    text = "—"
                else:
                    text = f"{val:.2f}"
                color = "white" if not np.isnan(val) and val > 0.65 else "black"
                ax.text(j, i, text, ha="center", va="center", fontsize=6, color=color)

        ax.set_title(WORKLOAD_DISPLAY.get(wl, wl), fontweight="bold")
        ax.set_xticks(range(n))
        ax.set_xticklabels(model_names, rotation=0, ha="center", fontsize=6)
        if ax_idx == 0:
            ax.set_yticks(range(n))
            ax.set_yticklabels(model_names, fontsize=6)
        else:
            ax.set_yticks(range(n))
            ax.set_yticklabels([])

    # Single colorbar on the right
    cbar = fig.colorbar(im, ax=axes.tolist(), shrink=0.8, label="Plan Similarity",
                        pad=0.02)
    cbar.ax.tick_params(labelsize=6)
    for fmt in ["pdf", "png", "eps"]:
        path = outdir / f"fig2_dispatch_predictability.{fmt}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"  Saved: {outdir}/fig2_dispatch_predictability.{{pdf,png}}")
    plt.close(fig)


# ── §2.5 Figure 2b: Latency vs Plan Quality Scatter ─────────────────

# Reference model tag substring for matching (Opus 4.6)
_REFERENCE_TAG = "opus-4-6"


def _find_reference_model(plan_logs_merged: dict[str, dict[str, list[dict]]]) -> str | None:
    """Find the reference model (Opus 4.6) in merged plan logs."""
    for name in plan_logs_merged:
        if "opus" in name.lower():
            return name
    return None


def plot_latency_vs_quality_scatter(
    nested_data: dict[str, dict[str, list[dict]]],
    plan_logs: dict[str, dict[str, dict[str, list[dict]]]],
    outdir: Path,
):
    """§2.5 Figure 2b: X=mean planning latency, Y=plan similarity vs reference.

    One panel per workload, sharing the same y-axis.
    """
    setup_ieee_style()

    # Distinct colors/markers per model (consistent across panels)
    _MODEL_COLORS = [
        "#2c3e50", "#e74c3c", "#3498db", "#2ecc71", "#9b59b6",
        "#f39c12", "#1abc9c", "#e67e22", "#34495e", "#16a085",
    ]
    _MODEL_MARKERS = ["*", "s", "D", "^", "o", "v", "p", "h", "X", "P"]

    workloads = [w for w in ["hpc_cg", "sdp", "rwa"] if w in plan_logs]
    if not workloads:
        workloads = sorted(plan_logs.keys())

    # Build global model list for consistent colors across panels
    model_is_cloud: dict[str, bool] = {}
    all_model_names_set: set[str] = set()
    for wl in workloads:
        for tag in plan_logs.get(wl, {}):
            name = short_model_name(tag)
            all_model_names_set.add(name)
            if "claude" in tag:
                model_is_cloud[name] = True
            elif name not in model_is_cloud:
                model_is_cloud[name] = False
        for tag in nested_data.get(wl, {}):
            name = short_model_name(tag)
            if "claude" in tag:
                model_is_cloud[name] = True
            elif name not in model_is_cloud:
                model_is_cloud[name] = False

    all_models = [m for m in MODEL_ORDER if m in all_model_names_set]
    for m in sorted(all_model_names_set):
        if m not in all_models:
            all_models.append(m)

    # Assign color/marker per model globally
    model_style: dict[str, tuple[str, str, str]] = {}
    for idx, name in enumerate(all_models):
        color = _MODEL_COLORS[idx % len(_MODEL_COLORS)]
        marker = _MODEL_MARKERS[idx % len(_MODEL_MARKERS)]
        raw = name.replace("\n", "-").replace(" ", "-").replace("(", "").replace(")", "")
        prefix = "claude" if model_is_cloud.get(name, False) else "local"
        display = f"{prefix}-{raw}".lower()
        model_style[name] = (color, marker, display)

    n_workloads = len(workloads)
    fig, axes = plt.subplots(
        1, n_workloads, sharey=True,
        figsize=(5 * n_workloads, 3.5),
        squeeze=False,
    )
    axes = axes[0]

    # Cluster colors (sorted by centroid latency, low→high)
    _CLUSTER_COLORS = ["#2ecc71", "#3498db", "#e74c3c", "#9b59b6"]

    for ax_idx, wl in enumerate(workloads):
        ax = axes[ax_idx]
        wl_plans = plan_logs.get(wl, {})
        wl_data = nested_data.get(wl, {})

        # Build per-model plans and latencies for this workload
        plans_by_name: dict[str, dict[str, list[dict]]] = {}
        for tag, queries in wl_plans.items():
            plans_by_name[short_model_name(tag)] = queries

        latency_by_name: dict[str, list[float]] = {}
        for tag, records in wl_data.items():
            name = short_model_name(tag)
            latency_by_name[name] = [r["planning_s"] for r in records]

        # Find reference
        ref_name = _find_reference_model(plans_by_name)
        if ref_name is None:
            continue
        ref_plans = plans_by_name.get(ref_name, {})

        # First pass: collect all (latency, similarity) points
        all_points: list[tuple[float, float]] = []
        point_names: list[str] = []

        for name in all_models:
            if name not in plans_by_name or name not in latency_by_name:
                continue

            lats = latency_by_name[name]
            mean_lat = float(np.mean(lats))
            is_ref = (name == ref_name)

            if is_ref:
                mean_sim = 1.0
            else:
                model_plans = plans_by_name[name]
                shared = set(model_plans.keys()) & set(ref_plans.keys())
                if not shared:
                    continue
                sims = [compute_plan_similarity(model_plans[q], ref_plans[q]) for q in shared]
                mean_sim = float(np.mean(sims))

            all_points.append((mean_lat, mean_sim))
            point_names.append(name)

        # KMeans clustering (normalize features before clustering)
        k = min(2, len(all_points))
        if len(all_points) >= 2:
            pts_arr = np.array(all_points)
            # Normalize to [0,1] for balanced clustering
            mins = pts_arr.min(axis=0)
            maxs = pts_arr.max(axis=0)
            ranges = maxs - mins
            ranges[ranges == 0] = 1.0
            pts_norm = (pts_arr - mins) / ranges

            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(pts_norm)

            # Sort clusters by centroid latency (leftmost = cluster 0)
            centroid_lats = [pts_arr[labels == c, 0].mean() for c in range(k)]
            order = np.argsort(centroid_lats)
            label_map = {old: new for new, old in enumerate(order)}
            labels = np.array([label_map[l] for l in labels])
        else:
            labels = np.zeros(len(all_points), dtype=int)

        # Second pass: plot points
        point_labels_map = dict(zip(point_names, labels))
        for name in all_models:
            if name not in plans_by_name or name not in latency_by_name:
                continue
            if name not in point_labels_map:
                continue

            color, marker, display = model_style[name]
            lats = latency_by_name[name]
            mean_lat = float(np.mean(lats))
            is_ref = (name == ref_name)

            if is_ref:
                mean_sim = 1.0
                label = f"{display} (ref.)" if ax_idx == 0 else None
                ax.scatter(mean_lat, mean_sim, s=64, color=color, marker=marker,
                           edgecolors="black", linewidths=0.5, zorder=5, label=label)
            else:
                model_plans = plans_by_name[name]
                shared = set(model_plans.keys()) & set(ref_plans.keys())
                if not shared:
                    continue
                sims = [compute_plan_similarity(model_plans[q], ref_plans[q]) for q in shared]
                mean_sim = float(np.mean(sims))
                label = display if ax_idx == 0 else None
                ax.scatter(mean_lat, mean_sim, s=32, color=color, marker=marker,
                           edgecolors="white", linewidths=0.3, zorder=4, label=label)

        # Draw cluster ellipses from KMeans
        if len(all_points) >= 2:
            pts_arr = np.array(all_points)
            for c in range(k):
                mask = labels == c
                if mask.sum() < 2:
                    continue
                xs = pts_arr[mask, 0]
                ys = pts_arr[mask, 1]
                cx, cy = np.mean(xs), np.mean(ys)

                w = max(np.std(xs) * 3.0, (np.max(xs) - np.min(xs)) + 2.0)
                h = max(np.std(ys) * 3.0, (np.max(ys) - np.min(ys)) + 0.08)

                clr = _CLUSTER_COLORS[c % len(_CLUSTER_COLORS)]
                ellipse = Ellipse(
                    (cx, cy), width=w, height=h,
                    facecolor=clr, alpha=0.08,
                    edgecolor=clr, linewidth=1.0,
                    linestyle="--", zorder=1,
                )
                ax.add_patch(ellipse)

                # Derive label from centroid position
                # Speed: compare to global latency range
                lat_range = pts_arr[:, 0].max() - pts_arr[:, 0].min()
                lat_mid = pts_arr[:, 0].min() + lat_range / 2
                if cx < lat_mid:
                    speed_word = "Fast"
                else:
                    speed_word = "Slow"
                # Fidelity: based on mean similarity
                if cy >= 0.75:
                    quality_word = "high quality"
                elif cy >= 0.55:
                    quality_word = "moderate quality"
                else:
                    quality_word = "lower quality"
                cluster_label = f"{speed_word},\n{quality_word}"

                # Place label above or below ellipse, whichever has more room
                top_y = cy + h / 2 + 0.03
                bot_y = cy - h / 2 - 0.03
                if top_y <= 1.05:
                    label_y = top_y
                    va = "bottom"
                else:
                    label_y = bot_y
                    va = "top"
                ax.text(cx, label_y, cluster_label,
                        ha="center", va=va, fontsize=8, color=clr,
                        fontstyle="italic", fontweight="bold")

        ax.set_title(WORKLOAD_DISPLAY.get(wl, wl), fontweight="bold", fontsize=14)
        ax.set_xlabel("Mean Planning Latency (s)", fontsize=14)
        ax.tick_params(axis="both", labelsize=14)
        ax.set_ylim(-0.05, 1.1)
        ax.set_xlim(left=0)
        ax.grid(alpha=0.3)

        if ax_idx == 0:
            ax.set_ylabel("Plan Similarity", fontsize=14)

    # Legend inside the first subplot (bottom-right, where there's empty space)
    handles, labels = axes[0].get_legend_handles_labels()
    legend = axes[0].legend(handles, labels, loc="lower right", framealpha=0.6,
                   ncol=min(2, len(handles)), fontsize=10, borderpad=0.4, labelspacing=0.3)
    _legend_fontsize = legend.get_texts()[0].get_fontsize() if legend.get_texts() else 10

    fig.tight_layout()
    for fmt in ["pdf", "png", "eps"]:
        path = outdir / f"fig2_latency_vs_quality.{fmt}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"  Saved: {outdir}/fig2_latency_vs_quality.{{pdf,png}}")
    plt.close(fig)


# ── Plotting (legacy) ────────────────────────────────────────────────


COLORS = [
    "#2c3e50", "#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12",
    "#1abc9c", "#e67e22", "#34495e", "#16a085",
]


def plot_per_model_stacked(model_tag: str, agg: dict, outdir: Path):
    """Stacked bar: planning vs execution per query for one model."""
    qids = list(agg.keys())
    planning = [agg[q]["planning_mean"] for q in qids]
    exec_seq = [agg[q]["exec_seq_mean"] for q in qids]
    planning_err = [agg[q]["planning_std"] for q in qids]

    labels = [q.replace("gen_", "").replace("trans_", "T:")[:30] for q in qids]

    fig, ax = plt.subplots(figsize=(max(10, len(qids) * 0.8), 5))
    x = np.arange(len(qids))
    width = 0.6

    ax.bar(x, planning, width, label="Planning (dispatch)",
           color="#2c3e50", yerr=planning_err, capsize=2)
    ax.bar(x, exec_seq, width, bottom=planning, label="Agent execution",
           color="#95a5a6")

    for i, q in enumerate(qids):
        frac = agg[q]["frac_seq_mean"]
        total = agg[q]["total_seq_mean"]
        ax.text(i, total + 0.3, f"{frac:.0%}",
                ha="center", va="bottom", fontsize=7, fontweight="bold")

    ax.set_xlabel("Query")
    ax.set_ylabel("Latency (seconds)")
    ax.set_title(f"Planning vs Execution — {model_tag}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6, rotation=45, ha="right")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = outdir / f"{model_tag}_stacked.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {path}")
    plt.close(fig)


def plot_cross_model_dispatch_fraction(all_agg: dict[str, dict], outdir: Path):
    """Bar chart comparing dispatch fraction across models (seq and par)."""
    models = list(all_agg.keys())
    frac_seq = []
    frac_par = []
    planning_abs = []

    for m in models:
        agg = all_agg[m]
        fracs_s = [v["frac_seq_mean"] for v in agg.values()]
        fracs_p = [v["frac_par_mean"] for v in agg.values()]
        plans = [v["planning_mean"] for v in agg.values()]
        frac_seq.append(np.mean(fracs_s))
        frac_par.append(np.mean(fracs_p))
        planning_abs.append(np.mean(plans))

    x = np.arange(len(models))
    width = 0.35

    # ── Dispatch fraction plot ──
    fig, ax = plt.subplots(figsize=(max(8, len(models) * 1.5), 5))
    # bars1 = ax.bar(x - width/2, [f * 100 for f in frac_seq], width,
    #                label="Sequential", color="#2c3e50")
    bars2 = ax.bar(x + width/2, [f * 100 for f in frac_par], width,
                   label="Parallel (critical path)", color="#3498db")

    for i in range(len(models)):
        # ax.text(i - width/2, frac_seq[i] * 100 + 0.5, f"{frac_seq[i]:.0%}",
        #         ha="center", fontsize=8)
        ax.text(i + width/2, frac_par[i] * 100 + 0.5, f"{frac_par[i]:.0%}",
                ha="center", fontsize=8)

    ax.set_ylabel("Dispatch Overhead (%)")
    ax.set_title("Planning Dispatch Overhead Across Models")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8, rotation=20, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = outdir / "cross_model_dispatch_fraction.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {path}")
    plt.close(fig)

    # ── Absolute planning time plot ──
    fig, ax = plt.subplots(figsize=(max(8, len(models) * 1.5), 5))
    bars = ax.bar(x, planning_abs, 0.5, color=COLORS[:len(models)])

    for i, v in enumerate(planning_abs):
        ax.text(i, v + 0.1, f"{v:.1f}s", ha="center", fontsize=9, fontweight="bold")

    ax.set_ylabel("Mean Planning Time (seconds)")
    ax.set_title("Absolute Planning Latency Across Models")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = outdir / "cross_model_planning_time.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {path}")
    plt.close(fig)


def plot_cross_model_by_problem_type(all_ptype: dict[str, dict], outdir: Path):
    """Grouped bar: planning time per problem type, one group per model."""
    models = list(all_ptype.keys())
    # Collect all problem types across models
    all_ptypes = sorted(set(
        pt for agg in all_ptype.values() for pt in agg.keys()
    ))
    if not all_ptypes:
        return

    x = np.arange(len(all_ptypes))
    width = 0.8 / len(models)

    fig, ax = plt.subplots(figsize=(max(10, len(all_ptypes) * 1.2), 5))

    for i, model in enumerate(models):
        agg = all_ptype[model]
        vals = [agg.get(pt, {}).get("planning_mean", 0) for pt in all_ptypes]
        offset = (i - len(models) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=model, color=COLORS[i % len(COLORS)])

    ax.set_ylabel("Mean Planning Time (seconds)")
    ax.set_title("Planning Latency by Problem Type Across Models")
    ax.set_xticks(x)
    ax.set_xticklabels(all_ptypes, fontsize=8, rotation=30, ha="right")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = outdir / "cross_model_by_problem_type.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {path}")
    plt.close(fig)


# ── Summary table ─────────────────────────────────────────────────────


def print_summary(model_tag: str, agg: dict):
    """Print per-model summary table."""
    print(f"\n{'='*80}")
    print(f"  {model_tag}")
    print(f"{'='*80}")
    print(
        f"  {'Query':<40} {'Plan':>6} {'ExecS':>7} {'ExecP':>7} "
        f"{'TotS':>7} {'TotP':>7} {'F%seq':>6} {'F%par':>6} {'Agts':>5}"
    )
    print(f"  {'-'*76}")
    for qid, s in agg.items():
        label = qid[:38]
        print(
            f"  {label:<40} {s['planning_mean']:>5.1f}s "
            f"{s['exec_seq_mean']:>6.1f}s {s['exec_par_mean']:>6.1f}s "
            f"{s['total_seq_mean']:>6.1f}s {s['total_par_mean']:>6.1f}s "
            f"{s['frac_seq_mean']:>5.0%} {s['frac_par_mean']:>5.0%} "
            f"{s['num_agents']:>4.1f}"
        )
    # Averages
    plans = [s["planning_mean"] for s in agg.values()]
    exec_s = [s["exec_seq_mean"] for s in agg.values()]
    exec_p = [s["exec_par_mean"] for s in agg.values()]
    tot_s = [s["total_seq_mean"] for s in agg.values()]
    tot_p = [s["total_par_mean"] for s in agg.values()]
    fs = [s["frac_seq_mean"] for s in agg.values()]
    fp = [s["frac_par_mean"] for s in agg.values()]
    print(f"  {'-'*76}")
    print(
        f"  {'MEAN':<40} {np.mean(plans):>5.1f}s "
        f"{np.mean(exec_s):>6.1f}s {np.mean(exec_p):>6.1f}s "
        f"{np.mean(tot_s):>6.1f}s {np.mean(tot_p):>6.1f}s "
        f"{np.mean(fs):>5.0%} {np.mean(fp):>5.0%}"
    )


def write_summary_csv(all_agg: dict[str, dict], outdir: Path):
    """Write combined CSV for all models."""
    path = outdir / "summary.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "model", "query_id", "domain", "complexity",
            "planning_s", "exec_seq_s", "exec_par_s",
            "total_seq_s", "total_par_s",
            "dispatch_frac_seq", "dispatch_frac_par",
            "num_agents", "n_runs",
        ])
        for model_tag, agg in all_agg.items():
            for qid, s in agg.items():
                writer.writerow([
                    model_tag, qid, s["domain"], s["complexity"],
                    f"{s['planning_mean']:.4f}",
                    f"{s['exec_seq_mean']:.4f}",
                    f"{s['exec_par_mean']:.4f}",
                    f"{s['total_seq_mean']:.4f}",
                    f"{s['total_par_mean']:.4f}",
                    f"{s['frac_seq_mean']:.4f}",
                    f"{s['frac_par_mean']:.4f}",
                    f"{s['num_agents']:.1f}",
                    s["n_runs"],
                ])
    print(f"\n  Summary CSV: {path}")


# ── Main ──────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract, summarize, and plot multi-model benchmark results"
    )
    parser.add_argument(
        "--results-dir", default="results",
        help="Root directory containing model result folders",
    )
    parser.add_argument(
        "--outdir", default="results/plots",
        help="Output directory for plots and CSV",
    )
    parser.add_argument(
        "--figure", default=None, choices=["1", "2", "all"],
        help="Generate §2.5 figures: 1=dispatch latency, 2=predictability, all=both",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Discovering results...")

    # Also report failure rates from raw data (before filtering)
    print("\nPlanner failure rates:")
    for f in sorted(results_dir.glob("**/plan_execute.json")):
        model_tag = f.parent.name
        with open(f) as fh:
            raw = json.load(fh)
        if not raw:
            continue
        n_fail = sum(1 for r in raw if r.get("planner_failed", False))
        n_total = len(raw)
        if n_fail > 0:
            print(f"  {model_tag}: {n_fail}/{n_total} failed ({n_fail/n_total:.0%})")
        else:
            print(f"  {model_tag}: 0/{n_total} failed")
    print()

    all_data = discover_results(results_dir)

    if not all_data:
        print("No results found (after filtering). Run benchmarks first:")
        print("  ./run_models.sh")
        exit(1)

    # Aggregate per query and per problem type for each model
    all_agg: dict[str, dict] = {}
    all_ptype: dict[str, dict] = {}
    for model_tag, data in all_data.items():
        all_agg[model_tag] = aggregate_by_query(data)
        all_ptype[model_tag] = aggregate_by_problem_type(data)
        print_summary(model_tag, all_agg[model_tag])

    # Per-model stacked bar
    print("\nGenerating per-model plots...")
    for model_tag, agg in all_agg.items():
        plot_per_model_stacked(model_tag, agg, outdir)

    # Cross-model comparisons
    if len(all_agg) > 1:
        print("\nGenerating cross-model plots...")
        plot_cross_model_dispatch_fraction(all_agg, outdir)
        plot_cross_model_by_problem_type(all_ptype, outdir)

    # CSV export
    write_summary_csv(all_agg, outdir)

    # ── §2.5 Figures ─────────────────────────────────────────────
    nested = None
    plan_logs = None

    if args.figure in ("1", "2", "all"):
        nested = discover_results_nested(results_dir)
        plan_logs = load_all_plan_logs(results_dir)

    if args.figure in ("1", "all"):
        print("\nGenerating §2.5 Figure 1: Dispatch Latency...")
        if nested:
            plot_dispatch_latency_boxplot(nested, outdir)
        else:
            print("  No nested results found for Figure 1")

    if args.figure in ("2", "all"):
        print("\nGenerating §2.5 Figure 2: Dispatch Predictability...")
        if plan_logs:
            plot_dispatch_predictability_heatmap(plan_logs, outdir)
            plot_latency_vs_quality_scatter(nested, plan_logs, outdir)
        else:
            print("  No plan logs found for Figure 2")

    print("\nDone.")
