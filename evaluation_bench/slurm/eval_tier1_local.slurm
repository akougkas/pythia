#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=06:00:00
#SBATCH --job-name=pythia-tier1-local
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier1_local_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier1_local_%j.err

# ═══════════════════════════════════════════════════
#  TIER 1: LOCAL SOLVER CONFIGS (A1, A4, A5)
#  A1: solver=gpt-oss:120b  draft=gpt-oss:20b
#  A4: solver=gpt-oss:120b  draft=qwen3:4b
#  A5: solver=gpt-oss:20b   draft=qwen3:4b
# ═══════════════════════════════════════════════════

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

echo "═══ TIER 1 LOCAL — $(hostname) — $(date) ═══"
nohup ollama serve > /tmp/ollama_t1l_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 30); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready"
ollama list
echo ""

cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg
N=20
BASELINES="pythia ns sh swol oracle"

# ── A1: solver=gpt-oss:120b, draft=gpt-oss:20b ──
echo "══════ CONFIG A1: solver=gpt-oss:120b draft=gpt-oss:20b ══════"
for B in $BASELINES; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider ollama --solver-model gpt-oss:120b \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model gpt-oss:20b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ A1 done at $(date '+%H:%M')"

# ── A4: solver=gpt-oss:120b, draft=qwen3:4b ──
echo "══════ CONFIG A4: solver=gpt-oss:120b draft=qwen3:4b ══════"
for B in $BASELINES; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider ollama --solver-model gpt-oss:120b \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model qwen3:4b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ A4 done at $(date '+%H:%M')"

# ── A5: solver=gpt-oss:20b, draft=qwen3:4b ──
echo "══════ CONFIG A5: solver=gpt-oss:20b draft=qwen3:4b ══════"
for B in $BASELINES; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider ollama --solver-model gpt-oss:20b \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model qwen3:4b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ A5 done at $(date '+%H:%M')"

echo ""
echo "═══ TIER 1 LOCAL COMPLETE — $(date) ═══"
