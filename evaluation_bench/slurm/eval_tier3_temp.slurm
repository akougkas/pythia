#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=06:00:00
#SBATCH --job-name=pythia-tier3-temp
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier3_temp_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/tier3_temp_%j.err

# ═══════════════════════════════════════════════════
#  TIER 3: TEMPERATURE SENSITIVITY (C1)
#  solver=gpt-oss:120b, draft=qwen3:4b
#  temps: 0.1, 0.3, 0.5, 0.7
#  baselines: pythia, swol
# ═══════════════════════════════════════════════════

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

echo "═══ TIER 3 TEMPERATURE — $(hostname) — $(date) ═══"
nohup ollama serve > /tmp/ollama_t3_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 30); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready"
ollama list
echo ""

cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg
N=20

for TEMP in 0.1 0.3 0.5 0.7; do
    echo "══════ TEMPERATURE=$TEMP ══════"
    for B in pythia swol; do
        echo "  → $B temp=$TEMP ($(date '+%H:%M'))"
        python3 run_full_eval.py --baseline $B --n-requests $N --fleet-size 2 \
            --solver-provider ollama --solver-model gpt-oss:120b \
            --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
            --draft-model qwen3:4b --draft-provider ollama \
            --temperature $TEMP --solver-temperature 0.1 \
            --prompt-mode original
    done
    echo "  ✓ temp=$TEMP done at $(date '+%H:%M')"
done

echo ""
echo "═══ TIER 3 COMPLETE — $(date) ═══"
