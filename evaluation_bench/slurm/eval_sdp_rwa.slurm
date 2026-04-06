#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=18:00:00
#SBATCH --job-name=pythia-sdp-rwa
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/sdp_rwa_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/sdp_rwa_%j.err

# ═══════════════════════════════════════════════════════════════════
#  SDP + RWA EVALUATION (HPC-CG already done)
#  Same configs as the HPC-CG full eval
# ═══════════════════════════════════════════════════════════════════

set -e
module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

WORKLOADS=/u/sislam3/pythia/evaluation_bench/workloads
DELTA_AI=/u/sislam3/pythia/evaluation_bench/delta-ai
N=20

echo "═══ SDP + RWA EVALUATION — $(hostname) — $(date) ═══"
nohup ollama serve > /tmp/ollama_sdprwa_${SLURM_JOB_ID}.log 2>&1 &
for i in $(seq 1 60); do curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break; sleep 2; done
echo "Ollama ready"
ollama list
echo ""

run_config() {
    local WORKLOAD=$1 BASELINE=$2 SOLVER_PROVIDER=$3 SOLVER_MODEL=$4
    local DRAFT_MODEL=$5 DRAFT_PROVIDER=$6 TEMP=$7
    cd $WORKLOADS/$WORKLOAD
    echo "    $WORKLOAD/$BASELINE solver=$SOLVER_MODEL draft=$DRAFT_MODEL ($(date '+%H:%M'))"
    python3 run_full_eval.py \
        --baseline $BASELINE --n-requests $N --fleet-size 2 \
        --solver-provider $SOLVER_PROVIDER --solver-model $SOLVER_MODEL \
        --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
        --draft-model $DRAFT_MODEL --draft-provider $DRAFT_PROVIDER \
        --temperature $TEMP --prompt-mode original 2>&1 | tail -3
}

# Smoke test
echo "▶ Smoke test..."
cd $WORKLOADS/sdp
python3 run_full_eval.py --baseline pythia --n-requests 1 --fleet-size 2 \
    --solver-provider ollama --solver-model gpt-oss:20b \
    --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
    --draft-model qwen3:4b --draft-provider ollama \
    --temperature 0.3 --prompt-mode original 2>&1 | tail -3
echo "  ✓ Smoke test OK"
echo ""

# ═══ PHASE 1: Family comparison (solver=gpt-oss:20b, 4 draft families) ═══
echo "▶ PHASE 1: Family comparison"
for DRAFT in qwen3:4b llama3.2:3b gemma2:2b phi4-mini:3.8b; do
    echo "  ── Draft=$DRAFT ──"
    for WL in sdp rwa; do
        for BL in pythia ns; do
            run_config $WL $BL ollama gpt-oss:20b $DRAFT ollama 0.3
        done
    done
done
echo "  ✓ Phase 1 done at $(date '+%H:%M')"

# ═══ PHASE 2: Big solver (gpt-oss:120b) ═══
echo "▶ PHASE 2: Big solver"
for DRAFT in gpt-oss:20b qwen3:4b; do
    echo "  ── Draft=$DRAFT ──"
    for WL in sdp rwa; do
        for BL in pythia ns; do
            run_config $WL $BL ollama gpt-oss:120b $DRAFT ollama 0.3
        done
    done
done
echo "  ✓ Phase 2 done at $(date '+%H:%M')"

# ═══ PHASE 3: Cloud solvers ═══
echo "▶ PHASE 3: Cloud solvers"
for SOLVER in claude-sonnet-4-6 claude-haiku-4-5-20251001 claude-opus-4-6; do
    for DRAFT in qwen3:4b; do
        echo "  ── Solver=$SOLVER Draft=$DRAFT ──"
        for WL in sdp rwa; do
            for BL in pythia ns; do
                run_config $WL $BL claude $SOLVER $DRAFT ollama 0.3
            done
        done
    done
done

# sonnet + llama3.2:3b and gpt-oss:20b drafts
for DRAFT in llama3.2:3b gpt-oss:20b; do
    echo "  ── Solver=claude-sonnet Draft=$DRAFT ──"
    for WL in sdp rwa; do
        for BL in pythia ns; do
            run_config $WL $BL claude claude-sonnet-4-6 $DRAFT ollama 0.3
        done
    done
done
echo "  ✓ Phase 3 done at $(date '+%H:%M')"

# ═══ Copy results ═══
echo "▶ Copying results to delta-ai/"
for WL in sdp rwa; do
    mkdir -p $DELTA_AI/$WL
    cp -r $WORKLOADS/$WL/runs/*_${N}req $DELTA_AI/$WL/ 2>/dev/null || true
done

echo ""
echo "═══ SDP + RWA COMPLETE — $(date) ═══"
echo "Run counts:"
for WL in sdp rwa; do
    COUNT=$(ls -d $WORKLOADS/$WL/runs/*_${N}req 2>/dev/null | wc -l)
    echo "  $WL: $COUNT runs"
done
