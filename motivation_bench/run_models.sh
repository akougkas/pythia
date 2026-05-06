#!/usr/bin/env bash
# run_models.sh — Run plan-and-execute benchmark across selected models.
#
# Usage:
#   ./run_models.sh                   # all models, default settings
#   ./run_models.sh --repeats 1       # quick verification run
#   ./run_models.sh --max-tokens 2048 # cap output tokens

set -euo pipefail

MODELS=(
    "gemma4:e2b"
    "gpt-oss:20b"
    "gemma4:26b"
    "mistral-small3.2:24b"
)

# Default args (can be overridden via CLI)
REPEATS=3
MAX_TOKENS=2048
EXTRA_ARGS=""

# Parse optional overrides
while [[ $# -gt 0 ]]; do
    case $1 in
        --repeats)    REPEATS="$2"; shift 2 ;;
        --max-tokens) MAX_TOKENS="$2"; shift 2 ;;
        --queries)    EXTRA_ARGS="$EXTRA_ARGS --queries $2"; shift 2 ;;
        *)            EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
    esac
done

echo "=========================================="
echo "  Motivation Bench — Multi-Model Run"
echo "=========================================="
echo "Models:     ${MODELS[*]}"
echo "Repeats:    $REPEATS"
echo "Max tokens: $MAX_TOKENS"
echo ""

FAILED=()

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "=========================================="
    echo "  Running: $MODEL"
    echo "=========================================="

    # Pre-load model to avoid cold-start in timing
    echo "  Preloading model..."
    ollama run "$MODEL" "Say OK." > /dev/null 2>&1 || true

    if python3 bench_plan_execute.py \
        --model "$MODEL" \
        --repeats "$REPEATS" \
        --max-tokens "$MAX_TOKENS" \
        $EXTRA_ARGS; then
        echo "  Done: $MODEL"
    else
        echo "  FAILED: $MODEL"
        FAILED+=("$MODEL")
    fi
done

echo ""
echo "=========================================="
echo "  All runs complete"
echo "=========================================="

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "  Failed models: ${FAILED[*]}"
fi

echo ""
echo "Results in results/*/"
echo "Run 'python3 plot_results.py' to generate plots."
