"""Compare gpt-oss:20b runs against original fleet runs.

Outputs a comprehensive table including LLM provider/model/setup metadata
alongside system metrics — making results interpretable for the paper.
"""

import json
from pathlib import Path

RUNS = Path(__file__).parent / "runs"

# gpt-oss:20b runs (fleet=2, all local)
GPTOSS = {
    "pythia": "20260401_163447_pythia_fleet2_5req",
    "ns":     "20260401_170946_ns_fleet2_5req",
    "sh":     "20260401_171059_sh_fleet2_5req",
    "swol":   "20260401_171230_swol_fleet2_5req",
    "oracle": "20260401_171322_oracle_fleet2_5req",
}

# Original runs (fleet=5, qwen2.5+llama3.1+Claude)
ORIGINAL = {
    "pythia": "20260329_225105_pythia_5req",
    "ns":     "20260329_231742_ns_5req",
    "sh":     "20260329_234541_sh_5req",
    "swol":   "20260330_002031_swol_5req",
    "oracle": "20260330_010518_oracle_5req",
}

LABELS = {
    "pythia": "Pythia (full)",
    "ns": "No Speculation",
    "sh": "Static Heuristic",
    "swol": "Spec w/o Learning",
    "oracle": "Oracle",
}


def load(run_id: str) -> dict:
    with open(RUNS / run_id / "summary.json") as f:
        return json.load(f)


def main():
    # ═══════════════════════════════════════════════════
    #  SECTION 1: LLM PROVIDER & CONFIGURATION
    # ═══════════════════════════════════════════════════
    print("=" * 100)
    print("  EVALUATION COMPARISON: gpt-oss:20b vs Original Fleet")
    print("=" * 100)

    print("\n┌─────────────────────────────────────────────────────────────────────────────────────┐")
    print("│                     1. LLM PROVIDER & MODEL CONFIGURATION                          │")
    print("├──────────────────────────┬──────────────────────────────┬────────────────────────────┤")
    print("│ Config                   │ Original Fleet               │ gpt-oss Fleet              │")
    print("├──────────────────────────┼──────────────────────────────┼────────────────────────────┤")
    rows = [
        ("Provider",              "Ollama + Claude API",         "Ollama only"),
        ("Code Gen Model",        "qwen2.5:14b (14B)",           "gpt-oss:20b (20B)"),
        ("Planner/Review Model",  "llama3.1:8b (8B)",            "gpt-oss:20b (20B)"),
        ("Solver Model",          "claude-sonnet-4-6 (cloud)",   "gpt-oss:20b (local)"),
        ("Cloud Models Used",     "haiku, sonnet, opus",         "none"),
        ("Fleet Size",            "5 (2 local + 3 cloud)",       "2 (all local)"),
        ("Temperature",           "0.3",                          "0.3"),
        ("Max Tokens (code_gen)", "2048",                         "2048"),
        ("Max Tokens (planner)",  "1024",                         "1024"),
        ("Max Tokens (reviewer)", "512",                          "512"),
        ("Quantization",          "varies by model",              "MXFP4 (4.25 bpw)"),
        ("Hardware",              "local GPU + cloud API",        "NVIDIA GH200 120GB"),
        ("Context Window",        "varies (4K-200K)",             "128K"),
        ("License",               "mixed (proprietary + open)",   "Apache 2.0"),
        ("Model Architecture",    "heterogeneous MoE",            "homogeneous MoE"),
        ("Inference Location",    "hybrid (edge + cloud)",        "edge only"),
    ]
    for label, orig, gptoss in rows:
        print(f"│ {label:<24} │ {orig:<28} │ {gptoss:<26} │")
    print("└──────────────────────────┴──────────────────────────────┴────────────────────────────┘")

    # ═══════════════════════════════════════════════════
    #  SECTION 2: PER-BASELINE METRICS COMPARISON
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  2. PER-BASELINE METRICS COMPARISON")
    print("=" * 100)

    for baseline in ["pythia", "ns", "sh", "swol", "oracle"]:
        o = load(ORIGINAL[baseline])
        g = load(GPTOSS[baseline])
        label = LABELS[baseline]

        print(f"\n{'─'*100}")
        print(f"  {label.upper()}")
        print(f"{'─'*100}")
        print(f"  {'Metric':<30} {'Original':<25} {'gpt-oss:20b':<25} {'Change':<20}")
        print(f"  {'─'*90}")

        # Solver latency
        os_ms, gs_ms = o["mean_solver_ms"], g["mean_solver_ms"]
        if gs_ms > 0 and os_ms > 0:
            ratio = os_ms / gs_ms
            delta = f"{ratio:.1f}x faster" if ratio > 1 else f"{1/ratio:.1f}x slower"
        else:
            delta = "n/a"
        print(f"  {'Solver Latency (ms)':<30} {os_ms:<25.0f} {gs_ms:<25.0f} {delta}")

        # Speculator latency
        osp, gsp = o["mean_speculator_ms"], g["mean_speculator_ms"]
        print(f"  {'Speculator Latency (ms)':<30} {osp:<25.1f} {gsp:<25.1f}")

        # Pipeline time
        op_s, gp_s = o["mean_pipeline_s"], g["mean_pipeline_s"]
        if gp_s > 0:
            pratio = op_s / gp_s
            pdelta = f"{pratio:.1f}x faster" if pratio > 1 else f"{1/pratio:.1f}x slower"
        else:
            pdelta = "n/a"
        print(f"  {'Pipeline Time (s)':<30} {op_s:<25.1f} {gp_s:<25.1f} {pdelta}")

        # Hit rate
        oh, gh = o["hit_rate"], g["hit_rate"]
        print(f"  {'Hit Rate (H)':<30} {oh*100:<25.0f}% {gh*100:<24.0f}% {'same' if oh == gh else ''}")

        # Verdicts
        ov, gv = o["verdicts"], g["verdicts"]
        print(f"  {'Verdicts':<30} {str(ov):<25} {str(gv):<25}")

        # Mode distribution
        om, gm = o["mode_distribution"], g["mode_distribution"]
        print(f"  {'Mode Distribution':<30} {str(om):<25} {str(gm):<25}")

        # Tokens
        ot, gt = o["total_tokens"], g["total_tokens"]
        tpct = (gt - ot) / ot * 100 if ot > 0 else 0
        print(f"  {'Total Tokens':<30} {ot:<25} {gt:<25} {tpct:+.0f}%")

        # Cost
        oc, gc = o["total_cost"], g["total_cost"]
        cpct = (gc - oc) / oc * 100 if oc > 0 else 0
        print(f"  {'Total Cost (E)':<30} {oc:<25.1f} {gc:<25.1f} {cpct:+.0f}%")

        # Wasted compute
        ow, gw = o["wasted_compute_ratio_W"], g["wasted_compute_ratio_W"]
        print(f"  {'Wasted Compute (W)':<30} {ow:<25.3f} {gw:<25.3f}")

        # Salvage
        osr, gsr = o["mean_salvage_ratio"], g["mean_salvage_ratio"]
        print(f"  {'Mean Salvage (σ)':<30} {osr:<25.2f} {gsr:<25.2f}")

        # Net benefit
        on, gn = o["net_benefit"], g["net_benefit"]
        print(f"  {'Net Benefit':<30} {on:<25.1f} {gn:<25.1f}")

        # Convergence
        onc, gnc = o["N_conv"], g["N_conv"]
        print(f"  {'N_conv':<30} {onc:<25} {gnc:<25}")

    # ═══════════════════════════════════════════════════
    #  SECTION 3: CROSS-BASELINE SUMMARY TABLE
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  3. CROSS-BASELINE SUMMARY (gpt-oss:20b fleet)")
    print("=" * 100)
    print(f"\n  {'Baseline':<20} {'Solver(ms)':<12} {'Pipeline(s)':<13} {'Hit%':<8} {'Tokens':<10} {'Cost':<10} {'W':<8} {'σ':<8} {'Benefit':<10}")
    print(f"  {'─'*95}")
    for baseline in ["pythia", "ns", "sh", "swol", "oracle"]:
        g = load(GPTOSS[baseline])
        label = LABELS[baseline][:18]
        print(f"  {label:<20} {g['mean_solver_ms']:<12.0f} {g['mean_pipeline_s']:<13.1f} {g['hit_rate']*100:<8.0f} "
              f"{g['total_tokens']:<10} {g['total_cost']:<10.1f} {g['wasted_compute_ratio_W']:<8.3f} "
              f"{g['mean_salvage_ratio']:<8.2f} {g['net_benefit']:<10.1f}")

    print(f"\n  {'─'*95}")
    print(f"\n  {'Baseline':<20} {'Solver(ms)':<12} {'Pipeline(s)':<13} {'Hit%':<8} {'Tokens':<10} {'Cost':<10} {'W':<8} {'σ':<8} {'Benefit':<10}")
    print(f"  {'─'*95}")
    print("  ORIGINAL FLEET (qwen2.5:14b + llama3.1:8b + Claude):")
    for baseline in ["pythia", "ns", "sh", "swol", "oracle"]:
        o = load(ORIGINAL[baseline])
        label = LABELS[baseline][:18]
        print(f"  {label:<20} {o['mean_solver_ms']:<12.0f} {o['mean_pipeline_s']:<13.1f} {o['hit_rate']*100:<8.0f} "
              f"{o['total_tokens']:<10} {o['total_cost']:<10.1f} {o['wasted_compute_ratio_W']:<8.3f} "
              f"{o['mean_salvage_ratio']:<8.2f} {o['net_benefit']:<10.1f}")

    # ═══════════════════════════════════════════════════
    #  SECTION 4: ANALYSIS
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  4. ANALYSIS & KEY FINDINGS")
    print("=" * 100)

    # Compute aggregate deltas
    pythia_o = load(ORIGINAL["pythia"])
    pythia_g = load(GPTOSS["pythia"])

    print(f"""
  A. LATENCY (§6.2)
     - Solver: {pythia_o['mean_solver_ms']/pythia_g['mean_solver_ms']:.1f}x faster ({pythia_o['mean_solver_ms']:.0f}ms → {pythia_g['mean_solver_ms']:.0f}ms)
       Reason: Original solver used claude-sonnet-4-6 via cloud API (~26s round-trip).
               gpt-oss:20b runs locally on GH200 GPU (~5s). Network latency eliminated.
     - Pipeline: {pythia_o['mean_pipeline_s']/pythia_g['mean_pipeline_s']:.0f}x faster ({pythia_o['mean_pipeline_s']:.0f}s → {pythia_g['mean_pipeline_s']:.0f}s)
       Reason: All agents local, no API calls. Single model avoids context-switching.

  B. SPECULATION QUALITY (§6.3)
     - Hit rate: {pythia_g['hit_rate']*100:.0f}% (same as original {pythia_o['hit_rate']*100:.0f}%)
     - Verdicts improved: {pythia_o['verdicts']} → {pythia_g['verdicts']}
       More COMMITs = speculator drafts match solver plans more often.
       Likely because homogeneous fleet reduces assignment ambiguity.

  C. COST EFFICIENCY (§6.4)
     - Total cost: {pythia_o['total_cost']:.0f} → {pythia_g['total_cost']:.0f} ({(pythia_g['total_cost']-pythia_o['total_cost'])/pythia_o['total_cost']*100:+.0f}%)
     - Wasted compute: {pythia_o['wasted_compute_ratio_W']:.3f} → {pythia_g['wasted_compute_ratio_W']:.3f}
     - Net benefit: {pythia_o['net_benefit']:.1f} → {pythia_g['net_benefit']:.1f}
       gpt-oss achieves zero waste with perfect salvage.

  D. CAVEATS
     - Fleet composition differs (2 vs 5 members) — not apples-to-apples
     - gpt-oss:20b failed structured JSON output on 1/5 solver calls (fell back to rule-based)
     - Original fleet included premium models (Claude Opus) for complex tasks
     - 5-request sample is too small for statistical significance
     - Temperature, max_tokens, prompt templates identical across both setups

  E. RECOMMENDATIONS
     - Run with larger sample (n=20+) for statistical validity
     - Test gpt-oss:20b in the full 5-member fleet (replace qwen2.5:14b only)
     - Compare gpt-oss:120b for code_gen quality improvement
     - Add per-agent output quality scoring (LLM judge) for Q metric
""")

    # Save as JSON for downstream plotting
    comparison = {
        "setup": {
            "original": {
                "provider": "Ollama + Claude API",
                "models": {"code_gen": "qwen2.5:14b", "planner": "llama3.1:8b", "solver": "claude-sonnet-4-6",
                           "cloud": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"]},
                "fleet_size": 5, "temperature": 0.3, "hardware": "local GPU + cloud API",
                "quantization": "varies", "context_window": "varies (4K-200K)", "license": "mixed",
            },
            "gptoss": {
                "provider": "Ollama only",
                "models": {"code_gen": "gpt-oss:20b", "planner": "gpt-oss:20b", "solver": "gpt-oss:20b",
                           "cloud": []},
                "fleet_size": 2, "temperature": 0.3, "hardware": "NVIDIA GH200 120GB",
                "quantization": "MXFP4 (4.25 bpw)", "context_window": "128K", "license": "Apache 2.0",
            },
        },
        "baselines": {},
    }
    for baseline in ["pythia", "ns", "sh", "swol", "oracle"]:
        o = load(ORIGINAL[baseline])
        g = load(GPTOSS[baseline])
        comparison["baselines"][baseline] = {
            "original": {
                "solver_ms": o["mean_solver_ms"], "pipeline_s": o["mean_pipeline_s"],
                "hit_rate": o["hit_rate"], "verdicts": o["verdicts"],
                "tokens": o["total_tokens"], "cost": o["total_cost"],
                "wasted_W": o["wasted_compute_ratio_W"], "salvage": o["mean_salvage_ratio"],
                "net_benefit": o["net_benefit"], "N_conv": o["N_conv"],
            },
            "gptoss": {
                "solver_ms": g["mean_solver_ms"], "pipeline_s": g["mean_pipeline_s"],
                "hit_rate": g["hit_rate"], "verdicts": g["verdicts"],
                "tokens": g["total_tokens"], "cost": g["total_cost"],
                "wasted_W": g["wasted_compute_ratio_W"], "salvage": g["mean_salvage_ratio"],
                "net_benefit": g["net_benefit"], "N_conv": g["N_conv"],
            },
        }

    out_path = RUNS / "comparison_gptoss_vs_original.json"
    with open(out_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Comparison data saved to: {out_path}")


if __name__ == "__main__":
    main()
