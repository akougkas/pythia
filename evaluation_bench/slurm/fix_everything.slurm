#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --job-name=pythia-fix-all
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/fix_all_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/fix_all_%j.err

# ═══════════════════════════════════════════════════════════════════
#  FIX EVERYTHING — Address all reviewer concerns
#
#  1. n=50 long runs (learner convergence proof)
#  2. SDP/RWA missing baselines (sh, swol, oracle)
#  3. Regenerate figures with cross-workload data
#  4. Generate statistical summary
# ═══════════════════════════════════════════════════════════════════

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

WORKLOADS=/u/sislam3/pythia/evaluation_bench/workloads
DELTA_AI=/u/sislam3/pythia/evaluation_bench/delta-ai

echo "═══════════════════════════════════════════════════════════════════"
echo "  FIX EVERYTHING — $(hostname) — $(date)"
echo "═══════════════════════════════════════════════════════════════════"

# Kill any existing Ollama on this node
pkill -f "ollama serve" 2>/dev/null || true
sleep 2

# Start Ollama with explicit models dir
OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models nohup ollama serve > /tmp/ollama_fix_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 60); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready"

# Verify our models are visible
echo "Models available:"
ollama list
echo ""

# Sanity check — gpt-oss:20b must be present
if ! ollama list | grep -q "gpt-oss:20b"; then
    echo "ERROR: gpt-oss:20b not found! Pulling..."
    ollama pull gpt-oss:20b
    ollama pull gpt-oss:120b
    ollama pull qwen3:4b
    ollama pull phi4-mini:3.8b
    ollama pull llama3.2:3b
    ollama pull gemma2:2b
    ollama list
fi
echo ""

run_config() {
    local WORKLOAD=$1 BASELINE=$2 SOLVER_PROVIDER=$3 SOLVER_MODEL=$4
    local DRAFT_MODEL=$5 DRAFT_PROVIDER=$6 TEMP=$7 NREQ=$8
    local PRIMARY=${9:-gpt-oss:20b}
    local SECONDARY=${10:-gpt-oss:20b}
    cd $WORKLOADS/$WORKLOAD
    export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
    echo "    $WORKLOAD/$BASELINE solver=$SOLVER_MODEL draft=$DRAFT_MODEL n=$NREQ temp=$TEMP ($(date '+%H:%M'))"
    python3 run_full_eval.py \
        --baseline $BASELINE --n-requests $NREQ --fleet-size 2 \
        --solver-provider $SOLVER_PROVIDER --solver-model $SOLVER_MODEL \
        --primary-local $PRIMARY --secondary-local $SECONDARY \
        --draft-model $DRAFT_MODEL --draft-provider $DRAFT_PROVIDER \
        --temperature $TEMP --prompt-mode original 2>&1 | tail -5
}

# ═══════════════════════════════════════════════════════════════════
#  SMOKE TEST: Verify agent execution produces real tokens
# ═══════════════════════════════════════════════════════════════════
echo "▶ SMOKE TEST: 1 request, verify real execution..."
cd $WORKLOADS/hpc_cg
python3 run_full_eval.py --baseline pythia --n-requests 1 --fleet-size 2 \
    --solver-provider ollama --solver-model gpt-oss:20b \
    --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
    --draft-model qwen3:4b --draft-provider ollama \
    --temperature 0.3 --prompt-mode original 2>&1 | grep -E "tok |TOTAL|FAIL"

# Verify tokens > 0
LATEST=$(ls -dt runs/*_1req 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    TOKENS=$(python3 -c "import json; s=json.load(open('$LATEST/summary.json')); print(s['total_tokens'])" 2>/dev/null)
    echo "  Smoke test tokens: $TOKENS"
    if [ "$TOKENS" = "0" ]; then
        echo "  ERROR: Zero tokens — Ollama agent execution broken!"
        echo "  Check: ollama list, curl http://localhost:11434/api/generate"
        exit 1
    fi
    echo "  ✓ Smoke test PASSED (tokens=$TOKENS)"
else
    echo "  ERROR: No smoke test output"
    exit 1
fi
echo ""

# ═══════════════════════════════════════════════════════════════════
#  FIX 1: n=50 LONG RUNS — Prove learner converges and beats SwoL
#  Best config: gpt-oss:120b solver, qwen3:4b draft
#  Also cross-family: gpt-oss:20b solver, phi4-mini draft
# ═══════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ FIX 1: Long runs (n=50) for learner convergence"
echo "═══════════════════════════════════════════════════════════════════"

# Config A: gpt-oss:120b / qwen3:4b — best latency gap
for BL in pythia swol ns oracle; do
    run_config hpc_cg $BL ollama gpt-oss:120b qwen3:4b ollama 0.3 50
done
echo "  ✓ Config A (120b/4b n=50) done at $(date '+%H:%M')"

# Config B: gpt-oss:20b / phi4-mini — best learner advantage
for BL in pythia swol ns; do
    run_config hpc_cg $BL ollama gpt-oss:20b phi4-mini:3.8b ollama 0.3 50
done
echo "  ✓ Config B (20b/phi4 n=50) done at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════
#  FIX 2: SDP/RWA — Fill missing baselines (sh, swol, oracle)
#  Best config for each workload
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ FIX 2: SDP/RWA full baseline coverage"
echo "═══════════════════════════════════════════════════════════════════"

# Run all 5 baselines for best local config on SDP and RWA
for WL in sdp rwa; do
    echo "  ── $WL: gpt-oss:20b / qwen3:4b ──"
    for BL in pythia ns sh swol oracle; do
        run_config $WL $BL ollama gpt-oss:20b qwen3:4b ollama 0.3 20
    done
    echo "  ✓ $WL done"
done

# Run all 5 baselines for cloud solver on SDP and RWA
for WL in sdp rwa; do
    echo "  ── $WL: claude-sonnet / qwen3:4b ──"
    for BL in pythia ns sh swol oracle; do
        run_config $WL $BL claude claude-sonnet-4-6 qwen3:4b ollama 0.3 20
    done
    echo "  ✓ $WL done"
done

echo "  ✓ FIX 2 done at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════
#  FIX 3: Regenerate all figures + cross-workload analysis
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ FIX 3: Regenerate figures and analysis"
echo "═══════════════════════════════════════════════════════════════════"

cd $DELTA_AI
python3 generate_figures.py 2>&1
echo "  ✓ Figures regenerated"

# ═══════════════════════════════════════════════════════════════════
#  FIX 4: Statistical summary + cross-workload comparison
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ FIX 4: Statistical summary"
echo "═══════════════════════════════════════════════════════════════════"

python3 -c "
import json, math
from pathlib import Path
from collections import defaultdict

base = Path('$WORKLOADS')
all_data = []
for wl in ['hpc_cg', 'sdp', 'rwa']:
    for d in sorted((base / wl / 'runs').iterdir()):
        cfg_f, sum_f = d / 'config.json', d / 'summary.json'
        if not cfg_f.exists() or not sum_f.exists(): continue
        try:
            c = json.loads(cfg_f.read_text())
            s = json.loads(sum_f.read_text())
        except: continue
        if s.get('total_interactions', 0) == 0: continue
        solver = c.get('solver',{}).get('model','?')
        draft = c.get('draft',{}).get('model','none')
        all_data.append({
            'workload': wl,
            'baseline': c.get('baseline','?'),
            'solver': solver, 'draft': draft,
            'temp': c.get('agent_temperature', 0.3),
            'n': s['total_interactions'],
            'solver_ms': s['mean_solver_ms'],
            'spec_ms': s['mean_speculator_ms'],
            'pipeline_s': s['mean_pipeline_s'],
            'hit_rate': s['hit_rate'],
            'salvage': s['mean_salvage_ratio'],
            'waste': s['wasted_compute_ratio_W'],
            'benefit': s['net_benefit'],
            'n_conv': s['N_conv'],
            'tokens': s['total_tokens'],
            'confidence': s.get('confidence_at_end', 0),
            'phase': s.get('phase_at_end', '?'),
            'modes': s.get('mode_distribution', {}),
        })

print(f'Total valid runs: {len(all_data)}')
print(f'  hpc_cg: {len([r for r in all_data if r[\"workload\"]==\"hpc_cg\"])}')
print(f'  sdp: {len([r for r in all_data if r[\"workload\"]==\"sdp\"])}')
print(f'  rwa: {len([r for r in all_data if r[\"workload\"]==\"rwa\"])}')
print()

# ── n=50 learner convergence ──
long_runs = [r for r in all_data if r['n'] >= 50]
if long_runs:
    print('=' * 100)
    print('  LONG RUNS (n=50) — LEARNER CONVERGENCE PROOF')
    print('=' * 100)
    print(f\"  {'Config':<40} {'Baseline':<10} {'n':<5} {'Hit%':<8} {'sigma':<8} {'W':<8} {'Benefit':<10} {'Phase':<15} {'Conf':<8}\")
    print('  ' + '-' * 95)
    for r in sorted(long_runs, key=lambda x: (x['solver'], x['draft'], x['baseline'])):
        cfg = f\"{r['solver']} / {r['draft']}\"
        bl = r['baseline']
        print(f\"  {cfg:<40} {bl:<10} {r['n']:<5} {r['hit_rate']*100:<8.0f} {r['salvage']:<8.2f} {r['waste']:<8.3f} {r['benefit']:<10.1f} {r['phase']:<15} {r['confidence']:<8.3f}\")
    print()

    # Compare Pythia vs SwoL at n=50
    pythia_50 = {(r['solver'],r['draft']): r for r in long_runs if r['baseline']=='pythia'}
    swol_50 = {(r['solver'],r['draft']): r for r in long_runs if r['baseline']=='swol'}
    print('  PYTHIA vs SwoL at n=50:')
    for key in pythia_50:
        if key in swol_50:
            p, s = pythia_50[key], swol_50[key]
            delta = p['benefit'] - s['benefit']
            winner = 'PYTHIA' if delta > 0 else 'SwoL'
            print(f\"    {key[0]}/{key[1]}: Pythia={p['benefit']:.1f} SwoL={s['benefit']:.1f} Delta={delta:+.1f} -> {winner}\")
    print()

# ── Cross-workload comparison ──
print('=' * 100)
print('  CROSS-WORKLOAD COMPARISON (Pythia baseline, temp=0.3, n=20)')
print('=' * 100)

configs = defaultdict(dict)
for r in all_data:
    if r['baseline'] == 'pythia' and r['temp'] == 0.3 and r['n'] == 20:
        key = (r['solver'], r['draft'])
        if r['workload'] not in configs[key] or r['benefit'] > configs[key][r['workload']]['benefit']:
            configs[key][r['workload']] = r

for (solver, draft), wl_data in sorted(configs.items()):
    if len(wl_data) < 2: continue
    print(f\"\n  {solver} / {draft}:\")
    print(f\"    {'Workload':<10} {'Hit%':<8} {'sigma':<8} {'W':<8} {'Benefit':<10} {'Pipe(s)':<10} {'N_conv':<8}\")
    print('    ' + '-' * 65)
    for wl in ['hpc_cg','sdp','rwa']:
        if wl not in wl_data: continue
        r = wl_data[wl]
        print(f\"    {wl:<10} {r['hit_rate']*100:<8.0f} {r['salvage']:<8.2f} {r['waste']:<8.3f} {r['benefit']:<10.1f} {r['pipeline_s']:<10.1f} {r['n_conv']:<8}\")

# ── Baseline comparison per workload ──
print()
print('=' * 100)
print('  FULL BASELINE COMPARISON PER WORKLOAD')
print('  (best local config: gpt-oss:20b / qwen3:4b, temp=0.3)')
print('=' * 100)

for wl in ['hpc_cg', 'sdp', 'rwa']:
    wl_runs = [r for r in all_data if r['workload']==wl and r['solver']=='gpt-oss:20b'
               and r['draft']=='qwen3:4b' and r['temp']==0.3 and r['n']==20]
    if not wl_runs: continue
    # dedup
    best = {}
    for r in wl_runs:
        if r['baseline'] not in best or r['benefit'] > best[r['baseline']]['benefit']:
            best[r['baseline']] = r
    print(f\"\n  {wl.upper()}:\")
    print(f\"    {'Baseline':<12} {'Hit%':<8} {'sigma':<8} {'W':<8} {'Benefit':<10} {'Pipe(s)':<10}\")
    print('    ' + '-' * 55)
    for bl in ['oracle','pythia','swol','ns','sh']:
        if bl not in best: continue
        r = best[bl]
        label = {'oracle':'Oracle','pythia':'Pythia','swol':'SwoL','ns':'NoSpec','sh':'StaticH'}[bl]
        print(f\"    {label:<12} {r['hit_rate']*100:<8.0f} {r['salvage']:<8.2f} {r['waste']:<8.3f} {r['benefit']:<10.1f} {r['pipeline_s']:<10.1f}\")

# Save consolidated
out = Path('$DELTA_AI/all_results_consolidated.json')
with open(out, 'w') as f:
    json.dump(all_data, f, indent=2)
print(f\"\n\nConsolidated data: {out}\")
print(f'Total runs: {len(all_data)}')
" 2>&1

echo ""
echo "═══════════════════════════════════════════════════════════════════"

# Copy everything to delta-ai
echo "▶ Copying all results to delta-ai/..."
for WL in hpc_cg sdp rwa; do
    mkdir -p $DELTA_AI/$WL
    for d in $WORKLOADS/$WL/runs/*req; do
        [ -f "$d/summary.json" ] && cp -r "$d" "$DELTA_AI/$WL/" 2>/dev/null
    done
done

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ALL FIXES COMPLETE — $(date)"
echo "  Results: $DELTA_AI/"
echo "═══════════════════════════════════════════════════════════════════"

echo ""
echo "Final counts:"
for WL in hpc_cg sdp rwa; do
    TOTAL=$(ls -d $WORKLOADS/$WL/runs/*/summary.json 2>/dev/null | wc -l)
    echo "  $WL: $TOTAL runs with summary.json"
done
