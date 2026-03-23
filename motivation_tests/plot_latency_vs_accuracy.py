#!/usr/bin/env python3
"""
plot_latency_vs_accuracy.py — Scatter plot of latency vs accuracy per case.

Reads plan metadata JSON (for duration_wall_s) and grade JSON (for overall_score),
then produces one subplot per case with:
  - Log-scale x-axis to spread the low-latency cluster
  - Same hue per framework, lightness gradient per model capability
  - Small number IDs instead of text annotations
  - Pareto frontier line

Usage:
    python plot_latency_vs_accuracy.py
    python plot_latency_vs_accuracy.py --results-dir ./results --output figure.png
"""

import argparse
import colorsys
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import numpy as np


def load_case_data(case_dir: Path) -> list[dict]:
    """Load paired latency + accuracy data for one case."""
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

        framework = grade_data.get("framework_name", "unknown")
        model = grade_data.get("model_name", "unknown")

        records.append({
            "framework": framework,
            "model": model,
            "latency_s": duration,
            "accuracy": score,
        })

    return records


# ── Framework base colors (HSL hue, used to generate lightness variants) ──
# Stored as (H, S, L) in 0-1 range
FRAMEWORK_HSL = {
    "claude_code": (0.0, 0.75, 0.50),     # red
    "agents_sdk":  (0.58, 0.70, 0.42),     # blue
    "langgraph":   (0.73, 0.50, 0.55),     # purple
    "crewai":      (0.33, 0.70, 0.40),     # green
    "aider":       (0.08, 0.95, 0.53),     # orange
    "gemini_adk":  (0.50, 0.75, 0.45),     # cyan/teal
    "direct_api":  (0.0, 0.0, 0.50),       # gray
}

# ── Model capability tier (higher = more capable = darker shade) ──
# Scale 0.0 (weakest) to 1.0 (strongest)
MODEL_CAPABILITY = {
    # Anthropic
    "anthropic__claude-opus-4-6":            1.0,
    "anthropic__claude-sonnet-4-6":          0.75,
    "anthropic__claude-haiku-4-5-20251001":  0.5,
    # GitHub Models
    "github_models__gpt-5":                  1.0,
    "github_models__gpt-4o":                 0.7,
    "github_models__gpt-4o-mini":            0.4,
    # Gemini
    "gemini__gemini-2.5-flash":              1.0,
    "gemini__gemini-3-flash-preview":        0.6,
    "gemini__gemini-3.1-flash-lite-preview": 0.3,
    # Local Ollama
    "ollama__gpt-oss_20b":                   0.8,
    "ollama__qwen3.5_9b":                    0.6,
    "ollama__qwen3.5_4b":                    0.35,
    "ollama__granite4_3b":                   0.15,
}


def capability_to_color(framework: str, model: str) -> str:
    """
    Generate a color for a framework+model combo.
    Same hue per framework; darker = more capable model.
    """
    h, s, base_l = FRAMEWORK_HSL.get(framework, (0.0, 0.0, 0.50))
    cap = MODEL_CAPABILITY.get(model, 0.5)

    # Map capability to lightness: 0.0 (weak) -> light, 1.0 (strong) -> dark
    # Range: L from 0.82 (very light) down to 0.28 (dark)
    l = 0.82 - cap * 0.54

    # Convert HLS to RGB
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def model_short_name(model: str) -> str:
    """Shorten model name for legend."""
    return (model
            .replace("anthropic__", "")
            .replace("ollama__", "")
            .replace("github_models__", "")
            .replace("gemini__", "")
            .replace("-20251001", "")
            .replace("-preview", ""))


def compute_pareto_frontier(records: list[dict]) -> list[tuple[float, float]]:
    """Points where no other has both lower latency AND higher accuracy."""
    if not records:
        return []
    pts = sorted([(r["latency_s"], r["accuracy"]) for r in records])
    frontier = []
    best_acc = -1.0
    for lat, acc in pts:
        if acc > best_acc:
            frontier.append((lat, acc))
            best_acc = acc
    return frontier


def plot_cases(results_dir: Path, output: Path | None = None):
    case_dirs = sorted(
        d for d in results_dir.iterdir()
        if d.is_dir() and (d / "grades").exists()
    )
    if not case_dirs:
        print("No cases with grades found.")
        return

    # ── Collect all unique models across all cases, assign stable IDs ──
    all_models = set()
    for case_dir in case_dirs:
        for r in load_case_data(case_dir):
            all_models.add(r["model"])

    # Sort models by capability (strongest first) for a logical numbering
    model_list = sorted(
        all_models,
        key=lambda m: MODEL_CAPABILITY.get(m, 0.5),
        reverse=True,
    )
    model_id = {m: i + 1 for i, m in enumerate(model_list)}

    n_cases = len(case_dirs)
    fig, axes = plt.subplots(1, n_cases, figsize=(7 * n_cases, 6.5), squeeze=False)

    all_seen_fw = set()

    for idx, case_dir in enumerate(case_dirs):
        ax = axes[0, idx]
        records = load_case_data(case_dir)
        if not records:
            ax.set_title(case_dir.name)
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes)
            continue

        for r in records:
            all_seen_fw.add(r["framework"])

        # Plot each point
        for r in records:
            color = capability_to_color(r["framework"], r["model"])
            ax.scatter(
                r["latency_s"], r["accuracy"],
                c=color, marker="o", s=100, alpha=0.92,
                edgecolors="black", linewidths=0.6,
                zorder=3,
            )

            # Small number ID next to each dot
            mid = model_id[r["model"]]
            ax.annotate(
                str(mid), (r["latency_s"], r["accuracy"]),
                fontsize=6, fontweight="bold", color="#333333",
                xytext=(5, -3), textcoords="offset points",
                zorder=4,
            )

        # Pareto frontier
        frontier = compute_pareto_frontier(records)
        if len(frontier) >= 2:
            f_lat = [p[0] for p in frontier]
            f_acc = [p[1] for p in frontier]

            step_lat, step_acc = [], []
            for j in range(len(frontier)):
                step_lat.append(f_lat[j])
                step_acc.append(f_acc[j])
                if j < len(frontier) - 1:
                    step_lat.append(f_lat[j + 1])
                    step_acc.append(f_acc[j])

            ax.plot(step_lat, step_acc, color="#333333", linewidth=1.5,
                    linestyle="--", alpha=0.45, zorder=2)

            max_lat = max(r["latency_s"] for r in records) * 1.3
            ext_lat = step_lat + [max_lat, max_lat, step_lat[0]]
            ext_acc = step_acc + [step_acc[-1], 5.5, 5.5]
            ax.fill(ext_lat, ext_acc, color="#2ECC71", alpha=0.05, zorder=1)

        # Formatting
        ax.set_xscale("log")
        case_title = (case_dir.name
                      .replace("case_001_", "Case 1: ")
                      .replace("case_002_", "Case 2: ")
                      .replace("case_003_", "Case 3: ")
                      .replace("_", " ")
                      .title())
        ax.set_title(case_title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Latency (seconds, log scale)", fontsize=10)
        if idx == 0:
            ax.set_ylabel("Plan Quality Score (1\u20135)", fontsize=10)
        ax.set_ylim(0.5, 5.7)
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.grid(True, alpha=0.2, linestyle="--", which="both")
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.xaxis.get_major_formatter().set_scientific(False)

    # ═══════════════════════════════════════════════════════════════
    # Legend: two parts
    # Left:  Framework color swatches (darkest shade)
    # Right: Model ID lookup table
    # ═══════════════════════════════════════════════════════════════

    # Framework legend — show dark shade as representative color
    fw_handles = []
    for fw in sorted(all_seen_fw):
        dark_color = capability_to_color(fw, "")  # fallback cap=0.5
        # Use a strong shade for the legend swatch
        h, s, _ = FRAMEWORK_HSL.get(fw, (0.0, 0.0, 0.5))
        r, g, b = colorsys.hls_to_rgb(h, 0.45, s)
        swatch = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        fw_handles.append(
            Line2D([0], [0], marker="o", color="w", markerfacecolor=swatch,
                   markeredgecolor="black", markeredgewidth=0.5,
                   markersize=10, label=fw)
        )
    # Pareto handle
    fw_handles.append(
        Line2D([0], [0], color="#333333", linewidth=1.5, linestyle="--",
               alpha=0.45, label="Pareto frontier")
    )

    fw_legend = fig.legend(
        handles=fw_handles,
        title="Framework (darker = stronger model)",
        title_fontproperties={"weight": "bold", "size": 9},
        loc="lower left",
        bbox_to_anchor=(0.01, -0.02),
        ncol=len(fw_handles),
        fontsize=8, frameon=True, fancybox=True,
    )
    fig.add_artist(fw_legend)

    # Model ID legend — numbered list
    model_handles = []
    for m in model_list:
        mid = model_id[m]
        cap = MODEL_CAPABILITY.get(m, 0.5)
        # Use a neutral gray shade scaled by capability
        gl = 0.82 - cap * 0.54
        r, g, b = gl, gl, gl
        gray_hex = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        model_handles.append(
            Line2D([0], [0], marker="o", color="w", markerfacecolor=gray_hex,
                   markeredgecolor="black", markeredgewidth=0.5,
                   markersize=9, label=f"{mid}  {model_short_name(m)}")
        )

    fig.legend(
        handles=model_handles,
        title="Model ID",
        title_fontproperties={"weight": "bold", "size": 9},
        loc="lower right",
        bbox_to_anchor=(0.99, -0.02),
        ncol=min(len(model_handles), 5),
        fontsize=7.5, frameon=True, fancybox=True,
        columnspacing=1.0,
    )

    fig.suptitle("Plan Quality vs Generation Latency",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0.12, 1, 0.95])

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Saved to {output}")
    else:
        plt.show()


def main():
    p = argparse.ArgumentParser(description="Plot latency vs accuracy per case")
    p.add_argument("--results-dir", type=Path, default=Path(__file__).parent / "results")
    p.add_argument("--output", type=Path, default=None,
                   help="Save figure to file (e.g., figure.png)")
    args = p.parse_args()
    plot_cases(args.results_dir, args.output)


if __name__ == "__main__":
    main()
