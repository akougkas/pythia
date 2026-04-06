#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --job-name=pythia-figures
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/figures_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/figures_%j.err

module load python/anaconda3/2.10.0
cd /u/sislam3/pythia/evaluation_bench/delta-ai
python3 generate_figures.py
echo ""
echo "Figures at: $(pwd)/figures/"
ls -la figures/
