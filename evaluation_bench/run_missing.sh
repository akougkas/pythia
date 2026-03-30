#!/bin/bash
# Run only missing baselines, then generate all comparisons.
set -e
cd "$(dirname "$0")/.."

N=5
SOLVER="claude"

echo "════════════════════════════════════════════════"
echo "  Running missing baselines (sequential)"
echo "════════════════════════════════════════════════"

# HPC-CG: only oracle missing
echo ""
echo "── hpc_cg / oracle ──"
python3 evaluation_bench/workloads/hpc_cg/run_full_eval.py \
    --n-requests $N --baseline oracle --solver-provider $SOLVER

# RWA: ns, sh, swol, oracle missing (pythia patched from old run)
for bl in ns sh swol oracle; do
    echo ""
    echo "── rwa / $bl ──"
    python3 evaluation_bench/workloads/rwa/run_full_eval.py \
        --n-requests $N --baseline $bl --solver-provider $SOLVER
done

# SDP: ns, sh, swol, oracle missing (pythia patched from old run)
for bl in ns sh swol oracle; do
    echo ""
    echo "── sdp / $bl ──"
    python3 evaluation_bench/workloads/sdp/run_full_eval.py \
        --n-requests $N --baseline $bl --solver-provider $SOLVER
done

# ── Generate plots and comparisons ──
echo ""
echo "════════════════════════════════════════════════"
echo "  Generating plots and comparisons"
echo "════════════════════════════════════════════════"

for w in hpc_cg rwa sdp; do
    echo ""
    echo "── $w plots ──"
    # Find latest pythia run for per-workload plots
    latest=$(ls -td evaluation_bench/workloads/$w/runs/*_pythia_* evaluation_bench/workloads/$w/runs/*_rwa_* evaluation_bench/workloads/$w/runs/*_sdp_* 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        python3 evaluation_bench/workloads/$w/generate_plots.py "$latest" 2>&1 | tail -15
    fi
    echo ""
    echo "── $w comparison ──"
    python3 evaluation_bench/compare_baselines.py evaluation_bench/workloads/$w/runs/ 2>&1 | tail -25
done

# ── Q metric ──
echo ""
echo "════════════════════════════════════════════════"
echo "  Computing Q metric (Pythia vs NS)"
echo "════════════════════════════════════════════════"
for w in hpc_cg rwa sdp; do
    P=$(ls -td evaluation_bench/workloads/$w/runs/*_pythia_* evaluation_bench/workloads/$w/runs/*_rwa_* evaluation_bench/workloads/$w/runs/*_sdp_* 2>/dev/null | head -1)
    NS=$(ls -td evaluation_bench/workloads/$w/runs/*_ns_* 2>/dev/null | head -1)
    if [ -n "$P" ] && [ -n "$NS" ]; then
        echo "  Q: $w"
        python3 evaluation_bench/metrics.py quality "$P" "$NS" 2>&1 | tail -8
    fi
done

echo ""
echo "════════════════════════════════════════════════"
echo "  ALL DONE"
echo "════════════════════════════════════════════════"
echo "Results at:"
for w in hpc_cg rwa sdp; do
    echo "  evaluation_bench/workloads/$w/runs/"
    echo "  evaluation_bench/workloads/$w/plots/"
done
