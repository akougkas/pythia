#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --job-name=pythia-pull-models
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/pull_models_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/pull_models_%j.err

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

echo "Starting Ollama on $(hostname)..."
nohup ollama serve > /tmp/ollama_pull_${SLURM_JOB_ID}.log 2>&1 &
OLLAMA_PID=$!
echo "Ollama PID: $OLLAMA_PID"
# Wait for Ollama to be ready
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama ready after ${i}s"
        break
    fi
    sleep 2
done

echo "=== Current models ==="
ollama list
echo ""

echo "=== Pulling qwen3:4b (~2GB) ==="
ollama pull qwen3:4b
echo ""

echo "=== Pulling gpt-oss:120b (~65GB) ==="
ollama pull gpt-oss:120b
echo ""

echo "=== Final model list ==="
ollama list
echo ""
echo "All models pulled successfully at $(date)"
