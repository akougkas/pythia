#!/usr/bin/env python3
"""Plot latency breakdown for Test 3: Speculative Dispatch + Merge.

Reads timing/cost data from the JSON artifacts produced by eval_execution.py
and renders a Gantt-style timeline showing overlapping phases.

Usage:
    python plot_test3_latency.py [--case CASE_NAME] [--run-dir DIR]
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime

import matplotlib.pyplot as plt


# ── Data loading ──────────────────────────────────────────────────────────

def load_json(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_timeline(run_dir: pathlib.Path) -> dict:
    """Parse the four JSON artifacts into a unified timeline dict."""
    spec_dsp = run_dir / "test3_spec_dsp"
    solver   = run_dir / "test3_solver"

    # 1. Plan-generation JSONs
    spec_plan = load_json(spec_dsp / "_plan_gen.json")
    opus_plan = load_json(solver  / "_plan_gen.json")

    # 2. Speculative execution result
    spec_exec = load_json(spec_dsp / "_result.json")

    # 3. Merge result
    merge     = load_json(spec_dsp / "_merge_result.json")

    # Parse start timestamps (ISO 8601) to compute absolute offsets
    t0_spec = datetime.fromisoformat(spec_plan["timestamp"])
    t0_opus = datetime.fromisoformat(opus_plan["timestamp"])
    t0 = min(t0_spec, t0_opus)  # global origin

    spec_plan_start = (t0_spec - t0).total_seconds()
    opus_plan_start = (t0_opus - t0).total_seconds()

    spec_plan_dur = spec_plan["duration_wall_s"]
    opus_plan_dur = opus_plan["duration_wall_s"]
    spec_exec_dur = spec_exec["duration_wall_s"]
    merge_dur     = merge["duration_wall_s"]

    # Speculative execution starts when spec plan finishes
    spec_exec_start = spec_plan_start + spec_plan_dur
    # Merge starts when opus plan finishes (and spec exec is stopped)
    merge_start = opus_plan_start + opus_plan_dur

    return {
        "phases": {
            "Dispatcher planning": {
                "start": spec_plan_start,
                "end":   spec_plan_start + spec_plan_dur,
                "row":   0,
                "cost":  spec_plan["total_cost_usd"],
                "model": spec_plan["model_name"],
            },
            "Solver planning": {
                "start": opus_plan_start,
                "end":   opus_plan_start + opus_plan_dur,
                "row":   1,
                "cost":  opus_plan["total_cost_usd"],
                "model": opus_plan["model_name"],
            },
            "Speculative execution": {
                "start": spec_exec_start,
                "end":   spec_exec_start + spec_exec_dur,
                "row":   0,
                "cost":  spec_exec["total_cost_usd"],
                "model": spec_exec["model_name"],
            },
            "Merge": {
                "start": merge_start,
                "end":   merge_start + merge_dur,
                "row":   1,
                "cost":  merge["total_cost_usd"],
                "model": merge["model_name"],
            },
        },
        "models": {
            "dispatcher": spec_plan["model_name"],
            "solver":     opus_plan["model_name"],
        },
        # Extra metadata for annotations
        "spec_exec_meta": {
            "turns":      spec_exec["num_turns"],
            "tokens":     spec_exec["total_tokens"],
            "tool_uses":  spec_exec["timeline_summary"]["total_tool_uses"],
            "cancelled":  spec_exec.get("cancelled", False),
        },
        "merge_meta": {
            "turns":      merge["num_turns"],
            "tokens":     merge["total_tokens"],
            "tool_uses":  merge["timeline_summary"]["total_tool_uses"],
        },
    }


# ── Plotting ──────────────────────────────────────────────────────────────

COLORS = {
    "Dispatcher planning":  "#4C72B0",
    "Solver planning":      "#DD8452",
    "Speculative execution": "#55A868",
    "Merge":                "#C44E52",
}


def plot_timeline(tl: dict, out_dir: pathlib.Path, case_name: str):
    phases = tl["phases"]
    disp_model  = tl["models"]["dispatcher"]
    solver_model = tl["models"]["solver"]

    total_end = max(p["end"] for p in phases.values())
    total_cost = sum(p["cost"] for p in phases.values())

    fig, ax = plt.subplots(figsize=(12, 3.5))
    bar_height = 0.5

    for name, p in phases.items():
        dur = p["end"] - p["start"]
        ax.barh(
            p["row"], dur, left=p["start"], height=bar_height,
            color=COLORS[name], edgecolor="white", linewidth=1.5, zorder=3,
        )
        # Label inside bar
        cx = p["start"] + dur / 2
        cy = p["row"]
        label = f"{name}\n{dur:.1f}s"
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=8, fontweight="bold", color="white", zorder=4)

    # Overlap shading: spec execution overlaps with solver planning
    spec_exec = phases["Speculative execution"]
    solver_plan = phases["Solver planning"]
    overlap_start = max(spec_exec["start"], solver_plan["start"])
    overlap_end   = min(spec_exec["end"],   solver_plan["end"])
    if overlap_end > overlap_start:
        ax.axvspan(overlap_start, overlap_end, alpha=0.08, color="gray", zorder=1)
        ax.annotate(
            "concurrent\n(spec. execution\n+ solver planning)",
            xy=((overlap_start + overlap_end) / 2, 0.55),
            xytext=((overlap_start + overlap_end) / 2, 1.45),
            ha="center", va="bottom", fontsize=7.5, fontstyle="italic", color="gray",
            arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
        )

    # Milestone markers
    milestones = [
        (0, "start"),
        (phases["Dispatcher planning"]["end"], f"{disp_model}\nplan ready"),
        (phases["Solver planning"]["end"], f"{solver_model}\nplan ready"),
        (total_end, "done"),
    ]
    for t, label in milestones:
        ax.axvline(t, color="gray", linestyle="--", linewidth=0.7, zorder=2)
        ax.text(t, -0.48, f"{t:.0f}s", ha="center", va="bottom",
                fontsize=7, color="gray")

    # Axes
    row_labels = [
        f"{disp_model}\n(dispatcher)",
        f"{solver_model}\n(solver)",
    ]
    ax.set_yticks([0, 1])
    ax.set_yticklabels(row_labels, fontsize=10)
    ax.set_xlabel("Wall-clock time (s)", fontsize=11)
    ax.set_title(
        f"Test 3 Latency Breakdown — Speculative Dispatch + Merge  ({case_name})\n"
        f"Total wall time: {total_end:.1f}s",
        fontsize=12, fontweight="bold",
    )
    ax.set_xlim(-5, total_end * 1.08)
    ax.set_ylim(-0.5, 2.0)
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()

    stem = f"test3_latency_breakdown_{case_name}"
    for ext in ("png", "pdf"):
        path = out_dir / f"{stem}.{ext}"
        fig.savefig(path, dpi=200)
        print(f"Saved: {path}")
    plt.show()


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", default="case_002_file_watcher",
        help="Case folder name under run-dir (default: case_002_file_watcher)",
    )
    parser.add_argument(
        "--run-dir",
        default="/home/jye/publications/pythia_eval_runs",
        help="Root directory of eval runs",
    )
    args = parser.parse_args()

    run_dir = pathlib.Path(args.run_dir) / args.case
    if not run_dir.exists():
        print(f"ERROR: run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = pathlib.Path(__file__).resolve().parent

    tl = extract_timeline(run_dir)
    plot_timeline(tl, out_dir, args.case)


if __name__ == "__main__":
    main()
