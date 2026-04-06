#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --job-name=pythia-pull-all
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/pull_all_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/pull_all_%j.err

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

nohup ollama serve > /tmp/ollama_pull_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 30); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready on $(hostname) at $(date)"
echo ""

echo "=== Current models ==="
ollama list
echo ""

# Draft models (small, one per family)
echo "=== Pulling draft models ==="

echo "1/5 qwen3:1.7b (Qwen family, 1.4GB)..."
ollama pull qwen3:1.7b
echo "   done"

echo "2/5 llama3.2:3b (Llama family, 2.0GB)..."
ollama pull llama3.2:3b
echo "   done"

echo "3/5 gemma2:2b (Gemma family, 1.6GB)..."
ollama pull gemma2:2b
echo "   done"

echo "4/5 phi4-mini:3.8b (Phi family, 2.5GB)..."
ollama pull phi4-mini:3.8b
echo "   done"

echo "5/5 qwen3:4b (already pulled, verifying)..."
ollama pull qwen3:4b
echo "   done"

echo ""
echo "=== Final model list ==="
ollama list
echo ""
echo "All models pulled at $(date)"
