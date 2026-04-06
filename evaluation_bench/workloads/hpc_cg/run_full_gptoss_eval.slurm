#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --job-name=pythia-full-gptoss
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/full_gptoss_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/full_gptoss_%j.err

# ═══════════════════════════════════════════════════════════════════
#  FULL EVALUATION PLAN — gpt-oss:20b on GH200
# ═══════════════════════════════════════════════════════════════════
#  Phase 1: All 5 baselines × 20 requests × fleet=2 (local only)
#  Phase 2: Fleet size sweep {2} × Pythia baseline × 20 requests
#  Phase 3: Comparison report generation
#
#  Total: 5 baselines × 20 req = ~100 interactions
#  Estimated time: ~2-3 hours
# ═══════════════════════════════════════════════════════════════════

set -e

# ── Environment ──
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

echo "═══════════════════════════════════════════════════════════════════"
echo "  PYTHIA FULL EVALUATION — gpt-oss:20b"
echo "  Node: $(hostname) | GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "  Started: $(date)"
echo "  Job ID: $SLURM_JOB_ID"
echo "═══════════════════════════════════════════════════════════════════"

# ── Start Ollama ──
echo ""
echo "Starting Ollama server..."
ollama serve > /tmp/ollama_${SLURM_JOB_ID}.log 2>&1 &
OLLAMA_PID=$!
sleep 8
ollama list
echo ""

cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg

N_REQ=20
COMMON="--solver-provider ollama --solver-model gpt-oss:20b --primary-local gpt-oss:20b --secondary-local gpt-oss:20b --prompt-mode original"

# ═══════════════════════════════════════════════════════════════════
#  PHASE 1: All 5 baselines × 20 requests × fleet=2
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  PHASE 1: 5 BASELINES × $N_REQ REQUESTS × FLEET=2"
echo "═══════════════════════════════════════════════════════════════════"

for BASELINE in pythia ns sh swol oracle; do
    echo ""
    echo "┌─────────────────────────────────────────────────────┐"
    echo "│  BASELINE: $BASELINE | n=$N_REQ | fleet=2            "
    echo "│  Time: $(date '+%H:%M:%S')                           "
    echo "└─────────────────────────────────────────────────────┘"

    python3 run_full_eval.py \
        --baseline $BASELINE \
        --n-requests $N_REQ \
        --fleet-size 2 \
        $COMMON

    echo ""
    echo "  ✓ $BASELINE complete at $(date '+%H:%M:%S')"
    echo ""
done

# ═══════════════════════════════════════════════════════════════════
#  PHASE 2: Comparison report
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  PHASE 2: GENERATING COMPARISON REPORT"
echo "═══════════════════════════════════════════════════════════════════"

# Find the latest run dirs for each baseline
LATEST_PYTHIA=$(ls -dt runs/*pythia_fleet2_${N_REQ}req 2>/dev/null | head -1)
LATEST_NS=$(ls -dt runs/*ns_fleet2_${N_REQ}req 2>/dev/null | head -1)
LATEST_SH=$(ls -dt runs/*sh_fleet2_${N_REQ}req 2>/dev/null | head -1)
LATEST_SWOL=$(ls -dt runs/*swol_fleet2_${N_REQ}req 2>/dev/null | head -1)
LATEST_ORACLE=$(ls -dt runs/*oracle_fleet2_${N_REQ}req 2>/dev/null | head -1)

echo "Latest runs:"
echo "  pythia: $LATEST_PYTHIA"
echo "  ns:     $LATEST_NS"
echo "  sh:     $LATEST_SH"
echo "  swol:   $LATEST_SWOL"
echo "  oracle: $LATEST_ORACLE"

# Generate inline comparison
python3 -c "
import json, sys
from pathlib import Path

runs = {
    'pythia': '$LATEST_PYTHIA',
    'ns': '$LATEST_NS',
    'sh': '$LATEST_SH',
    'swol': '$LATEST_SWOL',
    'oracle': '$LATEST_ORACLE',
}

labels = {
    'pythia': 'Pythia (full)',
    'ns': 'No Speculation',
    'sh': 'Static Heuristic',
    'swol': 'Spec w/o Learning',
    'oracle': 'Oracle',
}

data = {}
for k, path in runs.items():
    try:
        with open(Path(path) / 'summary.json') as f:
            data[k] = json.load(f)
    except Exception as e:
        print(f'  WARNING: Could not load {k}: {e}')
        data[k] = None

print()
print('=' * 110)
print('  FULL EVALUATION RESULTS — gpt-oss:20b on GH200 (n=$N_REQ)')
print('=' * 110)

# ── Setup table ──
print()
print('  LLM CONFIGURATION')
print('  ─────────────────')
print('  Provider:        Ollama only (local)')
print('  All Agents:      gpt-oss:20b (20B params, MXFP4 quantized)')
print('  Solver:          gpt-oss:20b via Ollama')
print('  Hardware:        NVIDIA GH200 120GB')
print('  Temperature:     0.3')
print('  Max Tokens:      2048 (code_gen), 1024 (planner), 512 (reviewer)')
print('  Fleet Size:      2 (all local)')
print('  Quantization:    MXFP4 (4.25 bpw)')
print('  Context Window:  128K')
print()

# ── Summary table ──
hdr = f\"  {'Baseline':<20} {'Solver(ms)':<12} {'Pipe(s)':<10} {'Hit%':<8} {'Verdicts':<30} {'Tokens':<10} {'Cost':<10} {'W':<8} {'σ':<8} {'Benefit':<10} {'N_conv':<8}\"
print(hdr)
print('  ' + '─' * 128)

for k in ['pythia', 'ns', 'sh', 'swol', 'oracle']:
    d = data.get(k)
    if d is None:
        print(f'  {labels[k]:<20} --- (no data)')
        continue
    v_str = ', '.join(f'{k2}:{v2}' for k2, v2 in d['verdicts'].items())
    print(f\"  {labels[k]:<20} {d['mean_solver_ms']:<12.0f} {d['mean_pipeline_s']:<10.1f} {d['hit_rate']*100:<8.0f} {v_str:<30} {d['total_tokens']:<10} {d['total_cost']:<10.1f} {d['wasted_compute_ratio_W']:<8.3f} {d['mean_salvage_ratio']:<8.2f} {d['net_benefit']:<10.1f} {d['N_conv']:<8}\")

# ── Claim verification ──
p = data.get('pythia')
ns = data.get('ns')
sh = data.get('sh')
swol = data.get('swol')
oracle = data.get('oracle')

if all([p, ns, sh, swol, oracle]):
    print()
    print('=' * 110)
    print('  PAPER CLAIM VERIFICATION')
    print('=' * 110)

    # 1. L_spec << L_s
    spec_ms = p['mean_speculator_ms']
    solv_ms = p['mean_solver_ms']
    ratio = solv_ms / spec_ms if spec_ms > 0 else float('inf')
    status = 'VERIFIED' if ratio > 10 else 'MARGINAL' if ratio > 2 else 'FAILED'
    print(f'  1. L_spec << L_s: Speculator {spec_ms:.1f}ms vs Solver {solv_ms:.0f}ms ({ratio:.0f}x faster) [{status}]')

    # 2. Hit rate
    print(f'  2. Hit rate H: {p[\"hit_rate\"]*100:.0f}% [{\"VERIFIED\" if p[\"hit_rate\"] >= 0.8 else \"CHECK\"}]')

    # 3. Wasted compute bounded
    print(f'  3. Wasted compute W: {p[\"wasted_compute_ratio_W\"]:.3f} [{\"VERIFIED\" if p[\"wasted_compute_ratio_W\"] < 0.3 else \"HIGH\"}]')

    # 4. Pythia > NS (net benefit)
    delta_ns = p['net_benefit'] - ns['net_benefit']
    print(f'  4. Pythia > NS benefit: {p[\"net_benefit\"]:.1f} vs {ns[\"net_benefit\"]:.1f} (Δ={delta_ns:+.1f}) [{\"VERIFIED\" if delta_ns > 0 else \"FAILED\"}]')

    # 5. Pythia > SH
    delta_sh = p['mean_pipeline_s'] - sh['mean_pipeline_s']
    p_faster = sh['mean_pipeline_s'] / p['mean_pipeline_s'] if p['mean_pipeline_s'] > 0 else 0
    print(f'  5. Pythia vs SH pipeline: Pythia {p[\"mean_pipeline_s\"]:.1f}s vs SH {sh[\"mean_pipeline_s\"]:.1f}s ({p_faster:.1f}x) [{\"VERIFIED\" if p[\"mean_pipeline_s\"] < sh[\"mean_pipeline_s\"] else \"CHECK\"}]')

    # 6. Learner improves over SwoL
    delta_swol = p['net_benefit'] - swol['net_benefit']
    print(f'  6. Pythia > SwoL: benefit {p[\"net_benefit\"]:.1f} vs {swol[\"net_benefit\"]:.1f} (Δ={delta_swol:+.1f}) [{\"VERIFIED\" if delta_swol > 0 else \"CHECK\"}]')

    # 7. Oracle is upper bound
    delta_oracle = oracle['net_benefit'] - p['net_benefit']
    print(f'  7. Oracle ≥ Pythia: {oracle[\"net_benefit\"]:.1f} vs {p[\"net_benefit\"]:.1f} (gap={delta_oracle:+.1f}) [{\"VERIFIED\" if delta_oracle >= 0 else \"ANOMALY\"}]')

    # 8. Convergence
    print(f'  8. N_conv: Pythia={p[\"N_conv\"]}, SwoL={swol[\"N_conv\"]}, NS={ns[\"N_conv\"]}')

    # 9. Mode distribution
    print(f'  9. Mode distribution: {p[\"mode_distribution\"]}')
    modes = p['mode_distribution']
    has_m2 = any(int(k) >= 2 for k in modes.keys())
    has_m3 = any(int(k) >= 3 for k in modes.keys())
    print(f'     Mode 2 activated: {\"YES\" if has_m2 else \"NO\"} | Mode 3 activated: {\"YES\" if has_m3 else \"NO\"}')

    # 10. Cost efficiency
    cost_reduction = (ns['total_cost'] - p['total_cost']) / ns['total_cost'] * 100 if ns['total_cost'] > 0 else 0
    token_reduction = (ns['total_tokens'] - p['total_tokens']) / ns['total_tokens'] * 100 if ns['total_tokens'] > 0 else 0
    print(f'  10. Cost vs NS: {cost_reduction:+.0f}% cost, {token_reduction:+.0f}% tokens')

    # Save consolidated comparison JSON
    consolidated = {
        'setup': {
            'model': 'gpt-oss:20b', 'provider': 'ollama', 'hardware': 'NVIDIA GH200 120GB',
            'fleet_size': 2, 'temperature': 0.3, 'quantization': 'MXFP4', 'n_requests': $N_REQ,
        },
        'baselines': {k: {
            'solver_ms': data[k]['mean_solver_ms'], 'pipeline_s': data[k]['mean_pipeline_s'],
            'hit_rate': data[k]['hit_rate'], 'verdicts': data[k]['verdicts'],
            'tokens': data[k]['total_tokens'], 'cost': data[k]['total_cost'],
            'wasted_W': data[k]['wasted_compute_ratio_W'], 'salvage': data[k]['mean_salvage_ratio'],
            'net_benefit': data[k]['net_benefit'], 'N_conv': data[k]['N_conv'],
            'mode_dist': data[k]['mode_distribution'],
            'confidence_end': data[k]['confidence_at_end'], 'phase_end': data[k]['phase_at_end'],
        } for k in ['pythia','ns','sh','swol','oracle'] if data.get(k)},
        'claims': {
            'L_spec_ratio': ratio, 'hit_rate': p['hit_rate'],
            'wasted_W': p['wasted_compute_ratio_W'], 'benefit_vs_ns': delta_ns,
            'benefit_vs_swol': delta_swol, 'oracle_gap': delta_oracle,
            'N_conv': p['N_conv'], 'mode2_activated': has_m2, 'mode3_activated': has_m3,
        },
    }
    out = Path('runs/full_eval_gptoss_20b_summary.json')
    with open(out, 'w') as f:
        json.dump(consolidated, f, indent=2)
    print(f'')
    print(f'  Summary saved to: {out}')
"

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ALL PHASES COMPLETE"
echo "  Finished: $(date)"
echo "═══════════════════════════════════════════════════════════════════"

# Cleanup
kill $OLLAMA_PID 2>/dev/null || true
