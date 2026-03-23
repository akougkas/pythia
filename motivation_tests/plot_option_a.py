#!/usr/bin/env python3
"""
Option A: Heatmap-style — framework/model as rows, latency as x-axis,
cell color = accuracy score. One subplot per case.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


def load_case_data(case_dir: Path) -> list[dict]:
    grade_dir = case_dir / "grades"
    plan_dir = case_dir / "plans"
    if not grade_dir.exists() or not plan_dir.exists():
        return []
    records = []
    for grade_file in sorted(grade_dir.glob("*__graded.json")):
        grade_data = json.loads(grade_file.read_text())
        stem = grade_file.stem.replace("__graded", "")
        meta_file = plan_dir / f"{stem}.json"
        if not meta_file.exists():
            continue
        meta_data = json.loads(meta_file.read_text())
        duration = meta_data.get("duration_wall_s")
        score = grade_data.get("overall_score")
        if duration is None or score is None:
            continue
        if score <= 1.0 and duration < 5.0:
            continue
        fw = grade_data.get("framework_name", "?")
        model = grade_data.get("model_name", "?")
        # Exclude gpt-5 from all cases
        if "gpt-5" in model:
            continue
        short_model = (model
                       .replace("anthropic__", "")
                       .replace("ollama__", "")
                       .replace("github_models__", "")
                       .replace("gemini__", "")
                       .replace("-20251001", "")
                       .replace("-preview", ""))
        records.append({
            "framework": fw,
            "model": model,
            "short_model": short_model,
            "label": f"{fw} / {short_model}",
            "latency_s": duration,
            "accuracy": score,
        })
    return records


def main():
    results_dir = Path(__file__).parent / "results"
    case_dirs = sorted(
        d for d in results_dir.iterdir()
        if d.is_dir() and (d / "grades").exists()
    )
    if not case_dirs:
        print("No data.")
        return

    n = len(case_dirs)
    fig, axes = plt.subplots(1, n, figsize=(8 * n, 8), squeeze=False)

    cmap = plt.cm.RdYlGn  # red (bad) -> yellow -> green (good)
    norm = mcolors.Normalize(vmin=1, vmax=5)

    for idx, case_dir in enumerate(case_dirs):
        ax = axes[0, idx]
        records = load_case_data(case_dir)
        if not records:
            continue

        # Sort: group by framework, then by accuracy (best first) within group
        # Framework order: sort frameworks by their best score (descending)
        from collections import defaultdict
        fw_groups = defaultdict(list)
        for r in records:
            fw_groups[r["framework"]].append(r)

        # Order frameworks by best accuracy in group (descending)
        fw_order = sorted(fw_groups.keys(),
                          key=lambda fw: max(r["accuracy"] for r in fw_groups[fw]),
                          reverse=True)

        # Build sorted records: grouped by framework, sorted within each group
        sorted_records = []
        group_boundaries = []  # y positions where groups end
        for fw in fw_order:
            group = sorted(fw_groups[fw], key=lambda r: r["accuracy"], reverse=True)
            sorted_records.extend(group)
            group_boundaries.append(len(sorted_records))

        records = sorted_records

        # Build y-tick labels: "Framework / model" with framework name
        # only on the first entry of each group
        FW_PRETTY = {
            "claude_code": "Claude Code",
            "agents_sdk": "Agents SDK",
            "gemini_adk": "Gemini ADK",
            "langgraph": "LangGraph",
            "crewai": "CrewAI",
            "aider": "Aider",
            "direct_api": "Direct API",
        }
        labels = []
        for r in records:
            fw = r["framework"]
            fw_name = FW_PRETTY.get(fw, fw.replace("_", " ").title())
            labels.append(f"{fw_name} / {r['short_model']}")

        latencies = [r["latency_s"] for r in records]
        scores = [r["accuracy"] for r in records]

        y_pos = np.arange(len(records))

        # Horizontal bar: length = latency, color = accuracy
        colors = [cmap(norm(s)) for s in scores]
        ax.barh(y_pos, latencies, color=colors, edgecolor="black",
                linewidth=0.4, height=0.7, zorder=2)

        # Add score text at end of each bar
        max_lat = max(latencies)
        for j, (lat, score) in enumerate(zip(latencies, scores)):
            ax.text(lat + max_lat * 0.02, j, f"{score:.1f}",
                    va="center", ha="left", fontsize=8, fontweight="bold")

        # Draw horizontal separators between framework groups
        for boundary in group_boundaries[:-1]:
            ax.axhline(y=boundary - 0.5, color="#444444", linewidth=1.2,
                       linestyle="-", alpha=0.8, zorder=4)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=7.5, family="monospace")
        ax.set_xlabel("Latency (seconds)", fontsize=10)
        ax.set_xscale("log")
        ax.invert_yaxis()
        ax.grid(True, axis="x", alpha=0.2, linestyle="--", which="both")
        ax.set_axisbelow(True)

        case_title = (case_dir.name
                      .replace("case_001_", "Case 1: ")
                      .replace("case_002_", "Case 2: ")
                      .replace("case_003_", "Case 3: ")
                      .replace("_", " ").title())
        ax.set_title(case_title, fontsize=12, fontweight="bold")

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes[0, :], orientation="vertical",
                        fraction=0.02, pad=0.15, aspect=40)
    cbar.set_label("Plan Quality Score (1-5)", fontsize=10)

    fig.suptitle("Option A: Framework/Model vs Latency (color = quality)",
                 fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.02, 0.88, 0.95])

    out = Path(__file__).parent / "option_a.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
