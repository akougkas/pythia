#!/bin/bash
# run_plan.sh — Time Claude Code plan generation with folder parameter
#
# Usage:
#   ./run_plan.sh /home/jye/publications/pythia/motivation_tests/results/ claude opus

set -euo pipefail

# ── Argument handling ───────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <folder> <provider> <model>"
    echo "  e.g. $0 /home/jye/publications/pythia/motivation_tests/results/ claude opus"
    exit 1
fi

FOLDER="$1"
PROVIDER="${2}"
MODEL="${3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/Case_1/prompt.md"
OUTPUT_FILE="${FOLDER}/${PROVIDER}_${MODEL}/plan_output.md"

# ── Ensure output folder exists ─────────────────────────────────────
mkdir -p "${FOLDER}/${PROVIDER}_${MODEL}"

# ── Substitute $folder in the template ──────────────────────────────
#   Using envsubst so only $folder is replaced (not other $ variables)
# export folder="${FOLDER}"
# PROMPT=$(envsubst '$folder' < "${TEMPLATE}")
PROMPT=$(cat "${TEMPLATE}")

# ── Time the Claude Code invocation ─────────────────────────────────
echo "============================================"
echo "  Claude Code Plan Generator"
echo "============================================"
echo "Folder:   ${FOLDER}"
echo "Template: ${TEMPLATE}"
echo "Output:   ${OUTPUT_FILE}"
echo "Model:    ${MODEL}"
echo "--------------------------------------------"
echo "Starting at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

START_NS=$(date +%s%N)

# Send prompt to Claude Code CLI
# --print flag: just print the response (non-interactive)
# Adjust flags as needed for your Claude Code version
if [[ "${PROVIDER}" == "claude" ]]; then
    # We cannot use --permission-mode plan because it is used for interactive sessions and causes the CLI to wait for user input on permissions.
    # claude -p "${PROMPT}" --model "${MODEL}" --permission-mode "plan" > "${OUTPUT_FILE}" 2>/dev/null
    claude -p "${PROMPT}" --model "${MODEL}" --dangerously-skip-permissions --allowedTools "" > "${OUTPUT_FILE}" 2>/dev/null
else
    echo "Unsupported provider: ${PROVIDER}"
    exit 1
fi

END_NS=$(date +%s%N)

# ── Calculate elapsed time ──────────────────────────────────────────
ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))
ELAPSED_S=$(echo "scale=2; ${ELAPSED_MS} / 1000" | bc)

echo ""
echo "--------------------------------------------"
echo "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Elapsed:     ${ELAPSED_S}s (${ELAPSED_MS}ms)"
echo "Output saved to: ${OUTPUT_FILE}"
echo "============================================"

# ── Optional: save timing metadata ──────────────────────────────────
cat > "${FOLDER}/${PROVIDER}_${MODEL}/timing.json" <<JSONEOF
{
  "template": "${TEMPLATE}",
  "model": "${MODEL}",
  "start_epoch_ns": ${START_NS},
  "end_epoch_ns": ${END_NS},
  "elapsed_ms": ${ELAPSED_MS},
  "elapsed_s": ${ELAPSED_S},
  "timestamp": "$(date -Iseconds)"
}
JSONEOF

echo "Timing metadata saved to: ${FOLDER}/${PROVIDER}_${MODEL}/timing.json"