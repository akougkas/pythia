#!/bin/bash
# Master runner for all Pythia evaluations
#
# Runs all baselines × all workloads, then generates comparisons.
# Each run uses 5 requests. Runs sequentially to avoid GPU contention.
#
# Usage:
#   bash evaluation_bench/run_all.sh           # full run (all baselines × all workloads)
#   bash evaluation_bench/run_all.sh --quick   # quick run (pythia + ns only, hpc-cg only)
#
# Output:
#   evaluation_bench/workloads/{hpc_cg,rwa,sdp}/runs/
#   evaluation_bench/workloads/{hpc_cg,rwa,sdp}/runs/comparison_plots/
#   evaluation_bench/workloads/{hpc_cg,rwa,sdp}/runs/comparison_report.md
#   evaluation_bench/workloads/{hpc_cg,rwa,sdp}/plots/

set -e
cd "$(dirname "$0")/.."

N_REQUESTS=${N_REQUESTS:-5}
SOLVER_PROVIDER=${SOLVER_PROVIDER:-claude}
QUICK=${1:-""}

echo "════════════════════════════════════════════════════════════════"
echo "  PYTHIA EVALUATION — MASTER RUNNER"
echo "════════════════════════════════════════════════════════════════"
echo "  Requests per run: $N_REQUESTS"
echo "  Solver: $SOLVER_PROVIDER"
echo ""

if [ "$QUICK" = "--quick" ]; then
    BASELINES="pythia ns sh"
    WORKLOADS="hpc_cg"
    echo "  Mode: QUICK (pythia+ns+sh, hpc_cg only)"
else
    BASELINES="pythia ns sh swol oracle"
    WORKLOADS="hpc_cg rwa sdp"
    echo "  Mode: FULL (all baselines × all workloads)"
fi
echo ""

# ─────────────────────────────────────────
# Phase 1: Run all baselines × workloads
# ─────────────────────────────────────────

for workload in $WORKLOADS; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  WORKLOAD: $workload"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for baseline in $BASELINES; do
        echo ""
        echo "  ── $workload / $baseline ──"
        python3 evaluation_bench/workloads/$workload/run_full_eval.py \
            --n-requests $N_REQUESTS \
            --baseline $baseline \
            --solver-provider $SOLVER_PROVIDER \
            2>&1 | tail -20
        echo "  ✓ $workload / $baseline done"
    done

    # Generate per-workload plots (from latest pythia run)
    echo ""
    echo "  Generating plots for $workload..."
    python3 evaluation_bench/workloads/$workload/generate_plots.py 2>&1 | tail -15

    # Generate cross-baseline comparison
    echo ""
    echo "  Generating baseline comparison for $workload..."
    python3 evaluation_bench/compare_baselines.py \
        evaluation_bench/workloads/$workload/runs/ 2>&1 | tail -20
done

# ─────────────────────────────────────────
# Phase 2: Compute Q metric (quality)
# ─────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  COMPUTING Q METRIC (dispatch quality)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for workload in $WORKLOADS; do
    RUNS_DIR="evaluation_bench/workloads/$workload/runs"
    PYTHIA_RUN=$(ls -td $RUNS_DIR/*_pythia_* 2>/dev/null | head -1)
    NS_RUN=$(ls -td $RUNS_DIR/*_ns_* 2>/dev/null | head -1)

    if [ -n "$PYTHIA_RUN" ] && [ -n "$NS_RUN" ]; then
        echo "  Q: $workload (Pythia vs NS)"
        python3 evaluation_bench/metrics.py quality "$PYTHIA_RUN" "$NS_RUN" 2>&1 | tail -10
    fi
done

# ─────────────────────────────────────────
# Phase 3: Scalability sweep (hpc-cg only)
# ─────────────────────────────────────────

if [ "$QUICK" != "--quick" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  SCALABILITY SWEEP (§6.6)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for fleet_size in 2 3 5; do
        echo "  Fleet size: $fleet_size"
        python3 evaluation_bench/workloads/hpc_cg/run_full_eval.py \
            --n-requests $N_REQUESTS \
            --baseline pythia \
            --fleet-size $fleet_size \
            --solver-provider $SOLVER_PROVIDER \
            2>&1 | tail -10
    done

    python3 evaluation_bench/metrics.py scalability \
        evaluation_bench/workloads/hpc_cg/runs/ 2>&1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ALL DONE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Results:"
for workload in $WORKLOADS; do
    echo "  $workload:"
    echo "    Runs:       evaluation_bench/workloads/$workload/runs/"
    echo "    Plots:      evaluation_bench/workloads/$workload/plots/"
    echo "    Comparison: evaluation_bench/workloads/$workload/runs/comparison_report.md"
done
echo ""
echo "  Metrics:    evaluation_bench/metrics.py summary <run_dir>"
echo "  Quality:    evaluation_bench/metrics.py quality <run_a> <run_b>"
