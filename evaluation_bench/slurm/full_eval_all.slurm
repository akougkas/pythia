#!/bin/bash
#SBATCH --account=bekn-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --job-name=pythia-full-eval
#SBATCH --output=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/full_eval_%j.out
#SBATCH --error=/u/sislam3/pythia/evaluation_bench/delta-ai/logs/full_eval_%j.err

# ═══════════════════════════════════════════════════════════════════════
#  PYTHIA FULL MODEL COMPARISON EVALUATION
#  SC26 Paper — Comprehensive across models, families, workloads
#  Self-contained: pulls models, tests, runs all configs, generates report
#  Runs entirely on compute node — safe to close terminal
# ═══════════════════════════════════════════════════════════════════════

set -e  # stop on first error

module load python/anaconda3/2.10.0
export OLLAMA_MODELS=/work/hdd/bekn/sislam3/ollama-models
export PATH=/work/hdd/bekn/sislam3/ollama/bin:$PATH
export LD_LIBRARY_PATH=/work/hdd/bekn/sislam3/ollama/lib:$LD_LIBRARY_PATH

DELTA_AI=/u/sislam3/pythia/evaluation_bench/delta-ai
WORKLOADS=/u/sislam3/pythia/evaluation_bench/workloads
N=20

echo "═══════════════════════════════════════════════════════════════════"
echo "  PYTHIA FULL EVALUATION"
echo "  Node: $(hostname) | GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null)"
echo "  Job: $SLURM_JOB_ID | Started: $(date)"
echo "  Time limit: 24 hours"
echo "═══════════════════════════════════════════════════════════════════"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 0: START OLLAMA + PULL ALL MODELS
# ═══════════════════════════════════════════════════════════════════════
echo ""
echo "▶ PHASE 0: Starting Ollama and pulling models..."
nohup ollama serve > /tmp/ollama_full_${SLURM_JOB_ID}.log 2>&1 &
OLLAMA_PID=$!
for i in $(seq 1 60); do
    curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break
    sleep 2
done
echo "  Ollama ready (PID=$OLLAMA_PID)"

# Pull all needed models
MODELS="gpt-oss:120b gpt-oss:20b qwen3:4b qwen3:1.7b llama3.2:3b gemma2:2b phi4-mini:3.8b"
for MODEL in $MODELS; do
    echo "  Pulling $MODEL..."
    ollama pull $MODEL 2>&1 | tail -1
done
echo ""
echo "  Models available:"
ollama list
echo ""

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 1: SMOKE TEST (1 request, verify everything works)
# ═══════════════════════════════════════════════════════════════════════
echo "▶ PHASE 1: Smoke test (1 request)..."
cd $WORKLOADS/hpc_cg
python3 run_full_eval.py --baseline pythia --n-requests 1 --fleet-size 2 \
    --solver-provider ollama --solver-model gpt-oss:20b \
    --primary-local gpt-oss:20b --secondary-local gpt-oss:20b \
    --draft-model qwen3:4b --draft-provider ollama \
    --temperature 0.3 --prompt-mode original 2>&1 | tail -5
echo "  ✓ Smoke test passed at $(date '+%H:%M')"
echo ""

# ═══════════════════════════════════════════════════════════════════════
#  HELPER FUNCTION
# ═══════════════════════════════════════════════════════════════════════
run_config() {
    local WORKLOAD=$1
    local BASELINE=$2
    local SOLVER_PROVIDER=$3
    local SOLVER_MODEL=$4
    local DRAFT_MODEL=$5
    local DRAFT_PROVIDER=$6
    local TEMP=$7
    local PRIMARY=${8:-gpt-oss:20b}
    local SECONDARY=${9:-gpt-oss:20b}

    cd $WORKLOADS/$WORKLOAD
    echo "    $WORKLOAD/$BASELINE solver=$SOLVER_MODEL draft=$DRAFT_MODEL temp=$TEMP ($(date '+%H:%M'))"
    python3 run_full_eval.py \
        --baseline $BASELINE \
        --n-requests $N \
        --fleet-size 2 \
        --solver-provider $SOLVER_PROVIDER \
        --solver-model $SOLVER_MODEL \
        --primary-local $PRIMARY \
        --secondary-local $SECONDARY \
        --draft-model $DRAFT_MODEL \
        --draft-provider $DRAFT_PROVIDER \
        --temperature $TEMP \
        --prompt-mode original 2>&1 | tail -3
}

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 2: GROUP 1 — WITHIN-FAMILY & CROSS-FAMILY (F1-F5)
#  Solver=gpt-oss:20b, Draft=each family's small model
#  All 3 workloads × 5 baselines = 75 runs
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 2: FAMILY COMPARISON (F1-F5) — Started $(date '+%H:%M')"
echo "═══════════════════════════════════════════════════════════════════"

DRAFT_MODELS="qwen3:4b llama3.2:3b gemma2:2b phi4-mini:3.8b"

# hpc_cg: all baselines (most important workload)
for DRAFT in $DRAFT_MODELS; do
    echo ""
    echo "  ── Draft: $DRAFT (solver=gpt-oss:20b, hpc_cg all baselines) ──"
    for BL in pythia ns sh swol oracle; do
        run_config hpc_cg $BL ollama gpt-oss:20b $DRAFT ollama 0.3
    done
    echo "  ✓ hpc_cg done"
done

# sdp + rwa: pythia and ns only (key comparison)
for DRAFT in $DRAFT_MODELS; do
    echo ""
    echo "  ── Draft: $DRAFT (solver=gpt-oss:20b, sdp+rwa pythia/ns) ──"
    for WL in sdp rwa; do
        for BL in pythia ns; do
            run_config $WL $BL ollama gpt-oss:20b $DRAFT ollama 0.3
        done
    done
    echo "  ✓ sdp+rwa done"
done

echo ""
echo "▶ PHASE 2 COMPLETE at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 3: GROUP 1b — BIG LOCAL SOLVER (gpt-oss:120b)
#  Solver=gpt-oss:120b, Draft=gpt-oss:20b and qwen3:4b
#  All 3 workloads × 5 baselines × 2 drafts = 30 runs
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 3: BIG SOLVER (gpt-oss:120b) — Started $(date '+%H:%M')"
echo "═══════════════════════════════════════════════════════════════════"

for DRAFT in gpt-oss:20b qwen3:4b; do
    echo ""
    echo "  ── Draft: $DRAFT (solver=gpt-oss:120b) ──"
    # hpc_cg: all baselines
    for BL in pythia ns sh swol oracle; do
        run_config hpc_cg $BL ollama gpt-oss:120b $DRAFT ollama 0.3
    done
    # sdp + rwa: pythia and ns
    for WL in sdp rwa; do
        for BL in pythia ns; do
            run_config $WL $BL ollama gpt-oss:120b $DRAFT ollama 0.3
        done
    done
    echo "  ✓ Draft=$DRAFT done at $(date '+%H:%M')"
done

echo ""
echo "▶ PHASE 3 COMPLETE at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 4: GROUP 2 — CLOUD SOLVER × LOCAL DRAFT
#  All 3 workloads
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 4: CLOUD SOLVERS — Started $(date '+%H:%M')"
echo "═══════════════════════════════════════════════════════════════════"

# C1: claude-sonnet × qwen3:4b
echo "  ── C1: solver=claude-sonnet draft=qwen3:4b ──"
for BL in pythia ns sh swol oracle; do
    run_config hpc_cg $BL claude claude-sonnet-4-6 qwen3:4b ollama 0.3
done
for WL in sdp rwa; do
    for BL in pythia ns; do
        run_config $WL $BL claude claude-sonnet-4-6 qwen3:4b ollama 0.3
    done
done
echo "  ✓ C1 done at $(date '+%H:%M')"

# C2: claude-sonnet × llama3.2:3b
echo "  ── C2: solver=claude-sonnet draft=llama3.2:3b ──"
for BL in pythia ns sh swol oracle; do
    run_config hpc_cg $BL claude claude-sonnet-4-6 llama3.2:3b ollama 0.3
done
for WL in sdp rwa; do
    for BL in pythia ns; do
        run_config $WL $BL claude claude-sonnet-4-6 llama3.2:3b ollama 0.3
    done
done
echo "  ✓ C2 done at $(date '+%H:%M')"

# C3: claude-sonnet × gpt-oss:20b
echo "  ── C3: solver=claude-sonnet draft=gpt-oss:20b ──"
for BL in pythia ns sh swol oracle; do
    run_config hpc_cg $BL claude claude-sonnet-4-6 gpt-oss:20b ollama 0.3
done
for WL in sdp rwa; do
    for BL in pythia ns; do
        run_config $WL $BL claude claude-sonnet-4-6 gpt-oss:20b ollama 0.3
    done
done
echo "  ✓ C3 done at $(date '+%H:%M')"

# C4: claude-haiku × qwen3:4b (pythia, ns)
echo "  ── C4: solver=claude-haiku draft=qwen3:4b ──"
for WL in hpc_cg sdp rwa; do
    for BL in pythia ns; do
        run_config $WL $BL claude claude-haiku-4-5-20251001 qwen3:4b ollama 0.3
    done
done
echo "  ✓ C4 done at $(date '+%H:%M')"

# C5: claude-opus × qwen3:4b (pythia, ns)
echo "  ── C5: solver=claude-opus draft=qwen3:4b ──"
for WL in hpc_cg sdp rwa; do
    for BL in pythia ns; do
        run_config $WL $BL claude claude-opus-4-6 qwen3:4b ollama 0.3
    done
done
echo "  ✓ C5 done at $(date '+%H:%M')"

echo ""
echo "▶ PHASE 4 COMPLETE at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 5: GROUP 3 — DRAFT SIZE SWEEP
#  Solver=gpt-oss:120b, Draft sizes: 1.7B, 4B, 20B
#  hpc_cg only × pythia, ns, swol = 9 runs
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 5: DRAFT SIZE SWEEP — Started $(date '+%H:%M')"
echo "═══════════════════════════════════════════════════════════════════"

for DRAFT in qwen3:1.7b qwen3:4b gpt-oss:20b; do
    echo "  ── Draft=$DRAFT (solver=gpt-oss:120b) ──"
    for BL in pythia ns swol; do
        run_config hpc_cg $BL ollama gpt-oss:120b $DRAFT ollama 0.3
    done
    echo "  ✓ done"
done

echo ""
echo "▶ PHASE 5 COMPLETE at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 6: GROUP 4 — TEMPERATURE SWEEP
#  Solver=gpt-oss:120b, Draft=qwen3:4b
#  temps: 0.1, 0.3, 0.5, 0.7 × pythia, swol = 8 runs
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 6: TEMPERATURE SWEEP — Started $(date '+%H:%M')"
echo "═══════════════════════════════════════════════════════════════════"

for TEMP in 0.1 0.3 0.5 0.7; do
    echo "  ── temp=$TEMP ──"
    for BL in pythia swol; do
        run_config hpc_cg $BL ollama gpt-oss:120b qwen3:4b ollama $TEMP
    done
    echo "  ✓ done"
done

echo ""
echo "▶ PHASE 6 COMPLETE at $(date '+%H:%M')"

# ═══════════════════════════════════════════════════════════════════════
#  PHASE 7: GENERATE COMPARISON REPORT
# ═══════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════"
echo "▶ PHASE 7: GENERATING COMPARISON REPORTS"
echo "═══════════════════════════════════════════════════════════════════"

for WL in hpc_cg sdp rwa; do
    echo "  Comparing $WL..."
    python3 /u/sislam3/pythia/evaluation_bench/compare_models.py \
        --runs-dir $WORKLOADS/$WL/runs 2>&1 | tail -5
done

# Copy all new results to delta-ai
echo ""
echo "  Copying results to delta-ai/..."
for WL in hpc_cg sdp rwa; do
    mkdir -p $DELTA_AI/$WL
    cp -r $WORKLOADS/$WL/runs/*_20req $DELTA_AI/$WL/ 2>/dev/null || true
    cp $WORKLOADS/$WL/runs/all_model_comparison.json $DELTA_AI/$WL/ 2>/dev/null || true
done

# ═══════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ALL PHASES COMPLETE"
echo "  Job: $SLURM_JOB_ID"
echo "  Finished: $(date)"
echo "  Results: $DELTA_AI/"
echo "═══════════════════════════════════════════════════════════════════"

echo ""
echo "Run counts per workload:"
for WL in hpc_cg sdp rwa; do
    COUNT=$(ls -d $WORKLOADS/$WL/runs/*_${N}req 2>/dev/null | wc -l)
    echo "  $WL: $COUNT runs"
done

echo ""
echo "Total run directories:"
ls -d $WORKLOADS/*/runs/*_${N}req 2>/dev/null | wc -l

kill $OLLAMA_PID 2>/dev/null || true
