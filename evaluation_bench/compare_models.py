"""Cross-model comparison for Pythia evaluation campaign.

Scans all runs, extracts model/provider/temperature metadata from config.json,
and generates comparison tables across dimensions:
  - Solver model × Draft model (latency gap analysis)
  - Temperature sensitivity
  - Cloud solver scaling
  - Baseline comparison per config

Usage:
  python3 compare_models.py [--runs-dir PATH]
"""

import json
from collections import defaultdict
from pathlib import Path


def load_run(run_dir: Path) -> dict | None:
    try:
        config = json.loads((run_dir / "config.json").read_text())
        summary = json.loads((run_dir / "summary.json").read_text())
        return {"config": config, "summary": summary, "dir": str(run_dir)}
    except Exception:
        return None


def extract_key(run: dict) -> dict:
    """Extract comparison keys from a run."""
    c = run["config"]
    solver = c.get("solver", {})
    draft = c.get("draft", {})
    return {
        "baseline": c.get("baseline", "?"),
        "solver_model": solver.get("model", "?"),
        "solver_provider": solver.get("provider", "?"),
        "solver_temp": solver.get("temperature", 0.1),
        "draft_model": draft.get("model", c.get("draft", {}).get("model", "none")),
        "draft_provider": draft.get("provider", "ollama"),
        "agent_temp": c.get("agent_temperature", 0.3),
        "fleet_size": len(c.get("fleet", [])),
        "n_requests": c.get("n_requests", 0),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=str,
                        default=str(Path(__file__).parent / "workloads/hpc_cg/runs"))
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    all_runs = []

    for d in sorted(runs_dir.iterdir()):
        if d.is_dir() and (d / "config.json").exists():
            run = load_run(d)
            if run:
                all_runs.append(run)

    if not all_runs:
        print("No runs found.")
        return

    print(f"Found {len(all_runs)} runs in {runs_dir}\n")

    # ═══════════════════════════════════════════
    #  TABLE 1: LATENCY GAP ANALYSIS
    # ═══════════════════════════════════════════
    print("=" * 110)
    print("  TABLE 1: LATENCY GAP ANALYSIS (Pythia baseline only)")
    print("  Key claim: L_spec << L_s requires heterogeneous model pairs")
    print("=" * 110)

    pythia_runs = [r for r in all_runs if r["config"].get("baseline") == "pythia"]

    print(f"\n  {'Solver Model':<28} {'Draft Model':<20} {'L_solver(ms)':<14} {'L_spec(ms)':<14} {'Ratio':<10} {'Benefit?':<10}")
    print("  " + "─" * 100)

    for r in sorted(pythia_runs, key=lambda x: extract_key(x)["solver_model"]):
        k = extract_key(r)
        s = r["summary"]
        solver_ms = s.get("mean_solver_ms", 0)
        spec_ms = s.get("mean_speculator_ms", 0)
        ratio = solver_ms / spec_ms if spec_ms > 0.01 else float("inf")
        benefit = "YES" if ratio > 2 else "MARGINAL" if ratio > 1 else "NO"
        temp_note = f" t={k['agent_temp']}" if k["agent_temp"] != 0.3 else ""
        print(f"  {k['solver_model']:<28} {k['draft_model']:<20} {solver_ms:<14.0f} {spec_ms:<14.1f} {ratio:<10.1f} {benefit}{temp_note}")

    # ═══════════════════════════════════════════
    #  TABLE 2: SPECULATION ACCURACY BY MODEL PAIR
    # ═══════════════════════════════════════════
    print(f"\n{'=' * 110}")
    print("  TABLE 2: SPECULATION ACCURACY BY MODEL PAIR (Pythia baseline)")
    print("=" * 110)

    print(f"\n  {'Solver/Draft':<40} {'Hit%':<8} {'Salvage':<10} {'N_conv':<8} {'W':<8} {'Benefit':<10} {'Modes':<25}")
    print("  " + "─" * 105)

    for r in sorted(pythia_runs, key=lambda x: extract_key(x)["solver_model"]):
        k = extract_key(r)
        s = r["summary"]
        pair = f"{k['solver_model']} / {k['draft_model']}"
        modes = str(s.get("mode_distribution", {}))
        temp_note = f" t={k['agent_temp']}" if k["agent_temp"] != 0.3 else ""
        print(f"  {pair:<40} {s['hit_rate']*100:<8.0f} {s['mean_salvage_ratio']:<10.2f} "
              f"{s['N_conv']:<8} {s['wasted_compute_ratio_W']:<8.3f} {s['net_benefit']:<10.1f} {modes}{temp_note}")

    # ═══════════════════════════════════════════
    #  TABLE 3: CROSS-BASELINE PER CONFIG
    # ═══════════════════════════════════════════
    print(f"\n{'=' * 110}")
    print("  TABLE 3: CROSS-BASELINE COMPARISON (grouped by solver/draft config)")
    print("=" * 110)

    # Group by (solver_model, draft_model, agent_temp)
    groups = defaultdict(list)
    for r in all_runs:
        k = extract_key(r)
        key = (k["solver_model"], k["draft_model"], k["agent_temp"])
        groups[key].append(r)

    for (solver, draft, temp), runs in sorted(groups.items()):
        temp_note = f" temp={temp}" if temp != 0.3 else ""
        print(f"\n  ── {solver} / {draft}{temp_note} ──")
        print(f"  {'Baseline':<20} {'Solver(ms)':<12} {'Pipe(s)':<10} {'Hit%':<8} {'Tokens':<10} {'Cost':<10} {'W':<8} {'σ':<8} {'Benefit':<10}")
        print("  " + "─" * 95)

        for r in sorted(runs, key=lambda x: x["config"]["baseline"]):
            s = r["summary"]
            bl = r["config"]["baseline"]
            label = {"pythia": "Pythia", "ns": "NoSpec", "sh": "StaticH",
                     "swol": "SwoL", "oracle": "Oracle"}.get(bl, bl)
            print(f"  {label:<20} {s['mean_solver_ms']:<12.0f} {s['mean_pipeline_s']:<10.1f} "
                  f"{s['hit_rate']*100:<8.0f} {s['total_tokens']:<10} {s['total_cost']:<10.1f} "
                  f"{s['wasted_compute_ratio_W']:<8.3f} {s['mean_salvage_ratio']:<8.2f} {s['net_benefit']:<10.1f}")

    # ═══════════════════════════════════════════
    #  TABLE 4: TEMPERATURE SENSITIVITY
    # ═══════════════════════════════════════════
    temp_runs = [r for r in pythia_runs if extract_key(r)["agent_temp"] != 0.3
                 or extract_key(r)["solver_model"] == "gpt-oss:120b"]

    if len(set(extract_key(r)["agent_temp"] for r in temp_runs)) > 1:
        print(f"\n{'=' * 110}")
        print("  TABLE 4: TEMPERATURE SENSITIVITY (Pythia, same solver/draft)")
        print("=" * 110)

        print(f"\n  {'Temp':<8} {'Solver':<25} {'Draft':<18} {'Hit%':<8} {'Salvage':<10} {'N_conv':<8} {'W':<8} {'Benefit':<10}")
        print("  " + "─" * 95)

        for r in sorted(temp_runs, key=lambda x: (extract_key(x)["solver_model"], extract_key(x)["agent_temp"])):
            k = extract_key(r)
            s = r["summary"]
            print(f"  {k['agent_temp']:<8} {k['solver_model']:<25} {k['draft_model']:<18} "
                  f"{s['hit_rate']*100:<8.0f} {s['mean_salvage_ratio']:<10.2f} {s['N_conv']:<8} "
                  f"{s['wasted_compute_ratio_W']:<8.3f} {s['net_benefit']:<10.1f}")

    # ═══════════════════════════════════════════
    #  SAVE CONSOLIDATED JSON
    # ═══════════════════════════════════════════
    consolidated = []
    for r in all_runs:
        k = extract_key(r)
        s = r["summary"]
        consolidated.append({**k, **{
            "solver_ms": s["mean_solver_ms"],
            "speculator_ms": s["mean_speculator_ms"],
            "pipeline_s": s["mean_pipeline_s"],
            "hit_rate": s["hit_rate"],
            "verdicts": s["verdicts"],
            "tokens": s["total_tokens"],
            "cost": s["total_cost"],
            "wasted_W": s["wasted_compute_ratio_W"],
            "salvage": s["mean_salvage_ratio"],
            "net_benefit": s["net_benefit"],
            "N_conv": s["N_conv"],
            "mode_dist": s["mode_distribution"],
            "confidence_end": s["confidence_at_end"],
            "phase_end": s["phase_at_end"],
            "run_dir": r["dir"],
        }})

    out = runs_dir / "all_model_comparison.json"
    with open(out, "w") as f:
        json.dump(consolidated, f, indent=2)
    print(f"\n\nConsolidated data saved to: {out}")
    print(f"Total runs analyzed: {len(all_runs)}")


if __name__ == "__main__":
    main()
