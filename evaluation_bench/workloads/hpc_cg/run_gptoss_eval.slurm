#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --job-name=pythia-gptoss-eval
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/gptoss_eval_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/gptoss_eval_%j.err

# ── Environment ──
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

# ── Start Ollama ──
echo "Starting Ollama on $(hostname)..."
ollama serve > /tmp/ollama_${SLURM_JOB_ID}.log 2>&1 &
sleep 8
ollama list
echo ""

cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg

COMMON_ARGS="--n-requests 5 --solver-provider ollama --solver-model gpt-oss:20b --primary-local gpt-oss:20b --secondary-local gpt-oss:20b --fleet-size 2 --prompt-mode original"

# ── Baseline 1: No Speculation (NS) ──
echo "============================================"
echo "  BASELINE: No Speculation (NS)"
echo "============================================"
python3 run_full_eval.py --baseline ns $COMMON_ARGS
echo ""

# ── Baseline 2: Static Heuristic (SH) ──
echo "============================================"
echo "  BASELINE: Static Heuristic (SH)"
echo "============================================"
python3 run_full_eval.py --baseline sh $COMMON_ARGS
echo ""

# ── Baseline 3: Speculation without Learning (SwoL) ──
echo "============================================"
echo "  BASELINE: Speculation without Learning (SwoL)"
echo "============================================"
python3 run_full_eval.py --baseline swol $COMMON_ARGS
echo ""

# ── Baseline 4: Oracle ──
echo "============================================"
echo "  BASELINE: Oracle"
echo "============================================"
python3 run_full_eval.py --baseline oracle $COMMON_ARGS
echo ""

echo "============================================"
echo "  ALL BASELINES COMPLETE"
echo "============================================"
echo "Results in: $(pwd)/runs/"
ls -lt runs/ | head -10
