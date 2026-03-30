"""Evaluation metrics for Pythia — §6 paper metrics.

Computes all 7 metrics defined in the paper:
  L  — Dispatch latency (already in summary)
  H  — Hit rate (already in summary)
  W  — Wasted compute ratio (added to summary)
  Q  — Dispatch quality via LLM judge
  N_conv — Learner convergence point (added to summary)
  E  — Cost efficiency (added to summary)
  S  — Scalability metrics (fleet size sweep)

Usage:
  # Compute Q between two runs
  python evaluation_bench/metrics.py quality \
    evaluation_bench/workloads/hpc_cg/runs/pythia_run \
    evaluation_bench/workloads/hpc_cg/runs/ns_run

  # Compute all metrics for a single run
  python evaluation_bench/metrics.py summary \
    evaluation_bench/workloads/hpc_cg/runs/pythia_run
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "../src"))
sys.path.insert(0, str(Path(__file__).parent / "workloads/hpc_cg"))


# ═══════════════════════════════════════════════════════════
# Q: Dispatch Quality (§6.1)
# ═══════════════════════════════════════════════════════════

def compute_quality_q(
    run_a: Path,
    run_b: Path,
    judge_model: str = "qwen2.5:14b",
) -> dict:
    """Compare agent outputs between two runs using LLM-as-judge.

    For each interaction present in both runs, compare the final outputs
    (code_gen or equivalent) and score quality on a 1-5 scale.

    Args:
        run_a: Pythia (or experimental) run directory
        run_b: Baseline run directory
        judge_model: Ollama model for judging

    Returns:
        dict with per-interaction scores and aggregate Q
    """
    from agent_runner import OllamaClient

    client = OllamaClient(model=judge_model)

    # Load events from both runs
    with open(run_a / "all_results.json") as f:
        events_a = json.load(f)["events"]
    with open(run_b / "all_results.json") as f:
        events_b = json.load(f)["events"]

    # Match by request_id
    b_by_id = {e["request_id"]: e for e in events_b}

    results = []
    for ea in events_a:
        rid = ea["request_id"]
        eb = b_by_id.get(rid)
        if eb is None:
            continue

        # Load agent outputs
        idir_a = run_a / f"interaction_{ea['interaction']:03d}"
        idir_b = run_b / f"interaction_{eb['interaction']:03d}"

        exec_a = idir_a / "layer4_execution.json"
        exec_b = idir_b / "layer4_execution.json"
        if not exec_a.exists() or not exec_b.exists():
            continue

        with open(exec_a) as f:
            l4_a = json.load(f)
        with open(exec_b) as f:
            l4_b = json.load(f)

        # Get the primary output (code_gen or first agent)
        output_a = _get_primary_output(l4_a)
        output_b = _get_primary_output(l4_b)

        if not output_a or not output_b:
            continue

        # Judge quality
        score_a, score_b, reasoning = _judge_pairwise(
            output_a, output_b, client, rid
        )

        results.append({
            "request_id": rid,
            "run_a_score": score_a,
            "run_b_score": score_b,
            "delta": score_a - score_b,
            "reasoning": reasoning,
        })

    if not results:
        return {"Q": 0.0, "comparisons": 0, "details": []}

    mean_a = sum(r["run_a_score"] for r in results) / len(results)
    mean_b = sum(r["run_b_score"] for r in results) / len(results)
    mean_delta = sum(r["delta"] for r in results) / len(results)

    return {
        "Q_run_a": mean_a,
        "Q_run_b": mean_b,
        "Q_delta": mean_delta,
        "comparisons": len(results),
        "run_a_wins": sum(1 for r in results if r["delta"] > 0),
        "run_b_wins": sum(1 for r in results if r["delta"] < 0),
        "ties": sum(1 for r in results if r["delta"] == 0),
        "details": results,
    }


def _get_primary_output(l4: dict) -> str:
    """Extract the primary agent output from layer4_execution.json."""
    agents = l4.get("agents", {})
    # Prefer code_gen > code_generator > analyst > first available
    for key in ["code_gen", "code_generator", "analyst", "data_wrangler"]:
        if key in agents:
            return agents[key].get("output", "")[:2000]
    # Fallback: first agent
    if agents:
        first = next(iter(agents.values()))
        return first.get("output", "")[:2000]
    return ""


def _judge_pairwise(
    output_a: str, output_b: str, client, request_id: str
) -> tuple[int, int, str]:
    """Use LLM judge to score both outputs on a 1-5 scale."""
    import re

    prompt = (
        f"You are evaluating two agent outputs for the same task: {request_id}\n\n"
        f"OUTPUT A:\n{output_a[:1500]}\n\n"
        f"OUTPUT B:\n{output_b[:1500]}\n\n"
        "Score each output independently on a 1-5 scale:\n"
        "1=broken/empty, 2=major issues, 3=partially correct, 4=good, 5=excellent\n\n"
        "Respond in EXACTLY this format:\n"
        "SCORE_A: <number>\n"
        "SCORE_B: <number>\n"
        "REASON: <one sentence>"
    )

    try:
        text, _, _ = client.generate(
            prompt=prompt,
            system="You are a code quality judge. Be concise and precise.",
            max_tokens=100,
            temperature=0.1,
        )

        match_a = re.search(r"SCORE_A:\s*(\d)", text)
        match_b = re.search(r"SCORE_B:\s*(\d)", text)
        reason_match = re.search(r"REASON:\s*(.+)", text)

        score_a = int(match_a.group(1)) if match_a else 3
        score_b = int(match_b.group(1)) if match_b else 3
        reason = reason_match.group(1).strip() if reason_match else text.strip()[:100]

        return min(5, max(1, score_a)), min(5, max(1, score_b)), reason
    except Exception as e:
        return 3, 3, f"Judge error: {e}"


# ═══════════════════════════════════════════════════════════
# S: Scalability (§6.6)
# ═══════════════════════════════════════════════════════════

def generate_fleet_configs() -> dict[str, list[dict]]:
    """Generate fleet configurations for scalability sweep.

    Returns fleet configs for sizes 2, 3, 5 (our current fleet sizes
    are constrained by available models).
    """
    configs = {}

    # Fleet size 2: local only
    configs["fleet_2"] = [
        {"member_id": "qwen2.5-14b-gpu", "model": "qwen2.5:14b",
         "compute": 100, "memory": 64, "rate_limit": 10, "token_budget": 100000,
         "cost_rate": 0.01, "latency": 2.0,
         "capabilities": ["code_gen", "tester", "analyst", "data_wrangler",
                          "code_generator", "planner", "review"],
         "affinity_tags": ["gpu", "local"]},
        {"member_id": "llama3.1-8b-gpu", "model": "llama3.1:8b",
         "compute": 80, "memory": 32, "rate_limit": 20, "token_budget": 200000,
         "cost_rate": 0.005, "latency": 0.5,
         "capabilities": ["planner", "review", "data_discovery", "reporter",
                          "literature_reviewer", "experiment_designer",
                          "experiment_runner", "result_analyzer",
                          "code_gen", "tester"],
         "affinity_tags": ["gpu", "local", "fast"]},
    ]

    # Fleet size 3: local + haiku
    configs["fleet_3"] = configs["fleet_2"] + [
        {"member_id": "claude-haiku-cloud", "model": "claude-haiku-4-5-20251001",
         "compute": 150, "memory": 64, "rate_limit": 10, "token_budget": 200000,
         "cost_rate": 0.02, "latency": 3.0,
         "capabilities": ["planner", "review", "tester", "reporter",
                          "data_discovery", "result_analyzer",
                          "experiment_runner", "experiment_designer"],
         "affinity_tags": ["cloud", "api", "fast"]},
    ]

    # Fleet size 5: full heterogeneous (current default)
    configs["fleet_5"] = configs["fleet_3"] + [
        {"member_id": "claude-sonnet-cloud", "model": "claude-sonnet-4-6",
         "compute": 200, "memory": 128, "rate_limit": 5, "token_budget": 200000,
         "cost_rate": 0.08, "latency": 4.0,
         "capabilities": ["code_gen", "tester", "analyst", "data_wrangler",
                          "code_generator", "planner", "review",
                          "literature_reviewer", "experiment_designer"],
         "affinity_tags": ["cloud", "api", "balanced"]},
        {"member_id": "claude-opus-cloud", "model": "claude-opus-4-6",
         "compute": 300, "memory": 256, "rate_limit": 3, "token_budget": 100000,
         "cost_rate": 0.15, "latency": 5.0,
         "capabilities": ["code_gen", "analyst", "code_generator",
                          "literature_reviewer"],
         "affinity_tags": ["cloud", "api", "premium"]},
    ]

    return configs


def compute_scalability_metrics(runs_dir: Path) -> dict:
    """Compute S metrics from runs with different fleet sizes.

    Expects runs named like: *_fleet2_*, *_fleet3_*, *_fleet5_*
    """
    results = {}
    for run_dir in sorted(runs_dir.glob("*_fleet*_*req")):
        summary_f = run_dir / "summary.json"
        if not summary_f.exists():
            continue
        with open(summary_f) as f:
            s = json.load(f)

        # Extract fleet size from dir name
        name = run_dir.name
        for part in name.split("_"):
            if part.startswith("fleet"):
                fleet_key = part
                break
        else:
            continue

        results[fleet_key] = {
            "fleet_size": len(s["config"]["fleet"]),
            "mean_solver_ms": s.get("mean_solver_ms", 0),
            "mean_speculator_ms": s.get("mean_speculator_ms", 0),
            "hit_rate": s.get("hit_rate", 0),
            "mean_pipeline_s": s.get("mean_pipeline_s", 0),
            "N_conv": s.get("N_conv", 0),
            "wasted_compute_ratio_W": s.get("wasted_compute_ratio_W", 0),
        }

    return results


# ═══════════════════════════════════════════════════════════
# Full Metrics Report
# ═══════════════════════════════════════════════════════════

def compute_full_metrics(run_dir: Path) -> dict:
    """Compute all 7 paper metrics for a single run.

    L, H, W, N_conv, E are from summary.json.
    Q requires a baseline run for comparison.
    S requires multiple fleet-size runs.
    """
    with open(run_dir / "summary.json") as f:
        summary = json.load(f)

    metrics = {
        "L_dispatch_latency_ms": summary.get("mean_dispatch_latency_ms",
                                              summary.get("mean_solver_ms", 0)),
        "H_hit_rate": summary.get("hit_rate", 0),
        "W_wasted_compute": summary.get("wasted_compute_ratio_W", 0),
        "N_conv": summary.get("N_conv", summary.get("total_interactions", 0)),
        "E_total_cost": summary.get("total_cost", 0),
        "E_total_tokens": summary.get("total_tokens", 0),
        "Q_dispatch_quality": "requires baseline comparison (use 'quality' command)",
        "S_scalability": "requires fleet sweep (use 'scalability' command)",
    }

    return metrics


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python metrics.py summary <run_dir>")
        print("  python metrics.py quality <run_a> <run_b> [--judge-model qwen2.5:14b]")
        print("  python metrics.py scalability <runs_dir>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "summary":
        run_dir = Path(sys.argv[2])
        metrics = compute_full_metrics(run_dir)
        print(f"\n§6 Metrics for {run_dir.name}:")
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")

    elif cmd == "quality":
        run_a = Path(sys.argv[2])
        run_b = Path(sys.argv[3])
        judge_model = "qwen2.5:14b"
        if "--judge-model" in sys.argv:
            idx = sys.argv.index("--judge-model")
            judge_model = sys.argv[idx + 1]

        print(f"Computing Q: {run_a.name} vs {run_b.name}")
        print(f"Judge model: {judge_model}")
        result = compute_quality_q(run_a, run_b, judge_model)

        print(f"\n  Q (run A): {result['Q_run_a']:.2f}/5")
        print(f"  Q (run B): {result['Q_run_b']:.2f}/5")
        print(f"  Delta: {result['Q_delta']:+.2f}")
        print(f"  Comparisons: {result['comparisons']}")
        print(f"  A wins: {result['run_a_wins']}, B wins: {result['run_b_wins']}, ties: {result['ties']}")

        # Save results
        output = run_a.parent / f"quality_{run_a.name}_vs_{run_b.name}.json"
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n  Saved: {output}")

    elif cmd == "scalability":
        runs_dir = Path(sys.argv[2])
        result = compute_scalability_metrics(runs_dir)
        if not result:
            print("No scalability runs found (expected *_fleet*_* directories)")
            sys.exit(1)

        print(f"\nScalability metrics ({len(result)} fleet configs):")
        print(f"{'Fleet':<10} {'Size':>5} {'Solver(ms)':>12} {'Spec(ms)':>10} {'Hit%':>6} {'Pipeline(s)':>12}")
        for k in sorted(result.keys()):
            r = result[k]
            print(f"{k:<10} {r['fleet_size']:>5} {r['mean_solver_ms']:>12.0f} "
                  f"{r['mean_speculator_ms']:>10.1f} {r['hit_rate']*100:>5.0f}% "
                  f"{r['mean_pipeline_s']:>12.0f}")

        output = runs_dir / "scalability_metrics.json"
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n  Saved: {output}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
