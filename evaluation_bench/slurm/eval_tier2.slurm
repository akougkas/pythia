#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --job-name=pythia-tier2-claude
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier2_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier2_%j.err

# ═══════════════════════════════════════════════════
#  TIER 2: CLAUDE SOLVER SCALING (B1, B2, B3)
#  B1: solver=claude-haiku   draft=qwen3:4b
#  B2: solver=claude-opus    draft=qwen3:4b
#  B3: solver=claude-opus    draft=gpt-oss:20b
# ═══════════════════════════════════════════════════

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

echo "═══ TIER 2 CLAUDE SCALING — $(hostname) — $(date) ═══"
nohup ollama serve > /tmp/ollama_t2_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 30); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready"
ollama list
echo ""

cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg
N=20

# ── B1: solver=claude-haiku, draft=qwen3:4b ──
echo "══════ CONFIG B1: solver=claude-haiku draft=qwen3:4b ══════"
for B in pythia ns; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider claude --solver-model claude-haiku-4-5-20251001 \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model qwen3:4b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ B1 done at $(date '+%H:%M')"

# ── B2: solver=claude-opus, draft=qwen3:4b ──
echo "══════ CONFIG B2: solver=claude-opus draft=qwen3:4b ══════"
for B in pythia ns; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider claude --solver-model claude-opus-4-6 \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model qwen3:4b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ B2 done at $(date '+%H:%M')"

# ── B3: solver=claude-opus, draft=gpt-oss:20b ──
echo "══════ CONFIG B3: solver=claude-opus draft=gpt-oss:20b ══════"
for B in pythia ns; do
    echo "  → $B ($(date '+%H:%M'))"
    python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
        --solver-provider claude --solver-model claude-opus-4-6 \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model gpt-oss:20b --draft-provider ollama \
        --temperature 0.3 --prompt-mode original
done
echo "  ✓ B3 done at $(date '+%H:%M')"

echo ""
echo "═══ TIER 2 COMPLETE — $(date) ═══"
