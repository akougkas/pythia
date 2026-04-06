#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:05:00
#SBATCH --job-name=pythia-compare
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/comparison_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs/comparison_%j.err

module load python/anaconda3/2.10.0
cd /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg
python3 compare_gptoss.py
