#!/usr/bin/env bash
# run_debug.sh — Plan-only benchmark across all models and backends
#
# Comment/uncomment lines to select which models to run.
# Usage: cd motivation_bench && bash run_debug.sh

REPEATS=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
# WORKLOAD="hpc_cg"
# WORKLOAD="sdp"
WORKLOAD="rwa"

# ── Claude backend (Agent SDK) ───────────────────────────────────
# claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-6
# python bench_plan_execute.py --backend claude --model claude-opus-4-6 --repeats $REPEATS --results-dir $RESULTS_DIR --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend claude --model claude-sonnet-4-6 --repeats $REPEATS --results-dir $RESULTS_DIR --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend claude --model claude-haiku-4-5-20251001 --repeats $REPEATS --results-dir $RESULTS_DIR --plan-only --workload $WORKLOAD
# sleep 10

# # ── Ollama-SDK backend (local model via Agent SDK) ───────────────
# python bench_plan_execute.py --backend ollama-sdk --model gemma4:e2b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama-sdk --model gemma4:26b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama-sdk --model gpt-oss:20b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama-sdk --model nemotron-3-nano:4b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama-sdk --model mistral-small3.2:24b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 10

# ── Gemini backend (Google AI) ──────────────────────────────────
# python bench_plan_execute.py --backend gemini --model gemini-2.5-flash --repeats $REPEATS --results-dir $RESULTS_DIR --plan-only --workload $WORKLOAD
# sleep 10
python bench_plan_execute.py --backend gemini --model gemini-2.5-flash-lite --repeats $REPEATS --results-dir $RESULTS_DIR --plan-only --workload $WORKLOAD

# # ── Ollama backend (LangGraph + Ollama) ──────────────────────────
# python bench_plan_execute.py --backend ollama --model gemma4:e2b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama --model gemma4:26b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama --model gpt-oss:20b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama --model nemotron-3-nano:4b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
# sleep 5
# python bench_plan_execute.py --backend ollama --model mistral-small3.2:24b --repeats $REPEATS --results-dir $RESULTS_DIR --max-tokens 2048 --plan-only --workload $WORKLOAD
