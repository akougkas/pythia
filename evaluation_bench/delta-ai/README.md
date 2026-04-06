# Delta AI Evaluation Results — Pythia

## What We Evaluate

Pythia is a **speculative dispatch** system for multi-agent LLM orchestration. The core idea: while the expensive **Solver** (target model) figures out which agents to dispatch, a cheap **Speculator** (draft model) guesses the dispatch plan from cache or a fast LLM. If the guess is right, we skip the solver's latency entirely.

We evaluate whether this speculation **actually helps** across different model combinations, providers, and temperatures.

## Hardware

- **NVIDIA GH200 120GB** (Grace Hopper Superchip)
- **NCSA Delta AI** cluster, `ghx4` partition
- ARM (aarch64) architecture
- All local inference via Ollama

## Evaluation Dimensions

### Dimension 1: Model Pairing (Solver × Draft)
The key question: does a fast/cheap draft model predict what an expensive/slow solver will decide?

| Solver (expensive, accurate) | Draft (cheap, fast) | Why Test |
|-----|-----|-----|
| gpt-oss:120b (local, 120B) | gpt-oss:20b (local, 20B) | Large gap, same family |
| gpt-oss:120b | qwen3:4b (local, 4B) | Maximum gap, cross-family |
| gpt-oss:20b | qwen3:4b | Moderate gap |
| claude-sonnet-4-6 (cloud) | gpt-oss:20b (local) | Cloud solver, local draft |
| claude-sonnet-4-6 | qwen3:4b | Cloud solver, tiny draft |
| claude-haiku (cloud, fast) | qwen3:4b | Cheap cloud solver |
| claude-opus (cloud, best) | qwen3:4b | Premium cloud solver |
| claude-opus | gpt-oss:20b | Premium solver, medium draft |

### Dimension 2: Baselines (5 strategies)
Each model pair is tested across 5 dispatch strategies:

| Baseline | What It Does | Why |
|----------|-------------|-----|
| **Pythia** | Full system: speculation + learning + reconciliation | The complete system |
| **NS (No Speculation)** | Solver only, no speculative dispatch | Lower bound — what if we never speculate? |
| **SH (Static Heuristic)** | Rule-based dispatch, no LLM solver | What if we skip the LLM entirely? |
| **SwoL (Spec w/o Learning)** | Speculation at fixed confidence (0.5) | Does the learner actually help? |
| **Oracle** | Perfect prediction (knows solver's answer) | Upper bound — best possible speculation |

### Dimension 3: Temperature
- 0.1 (deterministic) → 0.3 (default) → 0.5 → 0.7 (creative)
- Higher temperature = more random LLM outputs = harder to predict = lower speculation accuracy

## The 7 Metrics (from Paper §6)

### L — Dispatch Latency (ms)
**What**: Time from receiving a request to having a dispatch plan.
**Why**: The whole point of speculation is to hide solver latency. If L_spec ≈ L_solver, speculation is pointless.
**Good**: L_speculator << L_solver (100x+ faster)

### H — Hit Rate (%)
**What**: Fraction of interactions where speculation was correct (COMMIT or PARTIAL verdict).
**Why**: High hit rate = speculation is accurate = less wasted work.
**Good**: H > 80%

### W — Wasted Compute Ratio
**What**: Fraction of speculative compute that gets discarded.
**Formula**: W = (discarded speculative work) / (total speculative work)
**Why**: Low waste means speculation is cost-effective.
**Good**: W < 0.2 (less than 20% waste)

### σ — Salvage Ratio
**What**: Fraction of speculative work retained when partially correct.
**Formula**: σ = |matching assignments| / |speculated assignments|
**Why**: Even wrong speculations can be partially useful.
**Good**: σ > 0.7

### N_conv — Convergence Speed
**What**: Number of interactions before the learner reaches stable prediction accuracy.
**Why**: Fast convergence = the system adapts quickly to workload patterns.
**Good**: N_conv < 10 for regular workloads

### E — Cost (tokens × rate)
**What**: Total token consumption weighted by model cost rates.
**Why**: Speculation should not cost more than it saves.
**Good**: Pythia cost ≤ NS cost

### Net Benefit
**What**: Cumulative reward from speculation decisions.
**Formula**: +L_saved for COMMIT, +σ·L_saved - (1-σ)·C_redirect for PARTIAL, -C_flush for FLUSH
**Why**: Summarizes whether speculation was profitable overall.
**Good**: Positive and higher than SwoL

## Infrastructure & Model Comparison Tables

The evaluation produces **3 levels of comparison tables**: infrastructure, model, and system.

### Table A: Infrastructure Profile (per model)

Every model we test gets characterized along these axes:

| Property | gpt-oss:20b | gpt-oss:120b | qwen3:4b | claude-haiku | claude-sonnet | claude-opus |
|----------|------------|-------------|----------|-------------|--------------|------------|
| **Provider** | Ollama (local) | Ollama (local) | Ollama (local) | Anthropic API | Anthropic API | Anthropic API |
| **Inference Location** | Edge (on-prem) | Edge (on-prem) | Edge (on-prem) | Cloud | Cloud | Cloud |
| **Parameters** | 20B | 120B | 4B | undisclosed | undisclosed | undisclosed |
| **Quantization** | MXFP4 (4.25 bpw) | MXFP4 (4.25 bpw) | Q4_K_M | N/A (API) | N/A (API) | N/A (API) |
| **Model Size on Disk** | 13 GB | 65 GB | ~2.5 GB | N/A | N/A | N/A |
| **VRAM Usage** | ~16 GB | ~75 GB | ~3 GB | N/A | N/A | N/A |
| **Context Window** | 128K | 128K | 32K | 200K | 200K | 200K |
| **Architecture** | MoE (Transformer) | MoE (Transformer) | Dense (Transformer) | undisclosed | undisclosed | undisclosed |
| **Model Family** | OpenAI GPT-OSS | OpenAI GPT-OSS | Alibaba Qwen3 | Anthropic Claude | Anthropic Claude | Anthropic Claude |
| **License** | Apache 2.0 | Apache 2.0 | Apache 2.0 | Proprietary | Proprietary | Proprietary |
| **GPU** | GH200 120GB | GH200 120GB | GH200 120GB | Cloud GPU | Cloud GPU | Cloud GPU |
| **CPU** | ARM Grace (aarch64) | ARM Grace (aarch64) | ARM Grace (aarch64) | N/A | N/A | N/A |
| **Network Latency** | 0ms (local) | 0ms (local) | 0ms (local) | ~50-200ms | ~50-200ms | ~50-200ms |
| **Cost Model** | $0/token (local HW) | $0/token (local HW) | $0/token (local HW) | $0.25/M input | $3/M input | $15/M input |

### Table B: Per-Model Performance Profile (measured)

Collected during evaluation — actual latencies, throughput, quality:

| Metric | gpt-oss:20b | gpt-oss:120b | qwen3:4b | claude-haiku | claude-sonnet | claude-opus |
|--------|------------|-------------|----------|-------------|--------------|------------|
| **Solver Latency (ms)** | measured | measured | N/A (too small) | measured | measured | measured |
| **Draft Latency (ms)** | measured | N/A (too large) | measured | N/A | N/A | N/A |
| **Agent Exec Time (s)** | measured | measured | measured | measured | measured | measured |
| **Tokens/sec** | measured | measured | measured | measured | measured | measured |
| **JSON Parse Success %** | measured | measured | measured | N/A (reliable) | N/A (reliable) | N/A (reliable) |
| **Code Gen Quality (1-5)** | from reviewer agent | from reviewer agent | from reviewer agent | from reviewer agent | from reviewer agent | from reviewer agent |
| **Fallback-to-Rule Rate** | measured | measured | measured | measured | measured | measured |

### Table C: Model Pair Comparison (Solver × Draft)

The core speculation comparison — crossing solver and draft models:

| Solver → | Draft → | L_solver(ms) | L_draft(ms) | Ratio | Hit% | σ | W | Benefit | Temp |
|----------|---------|-------------|------------|-------|------|---|---|---------|------|
| gpt-oss:120b | gpt-oss:20b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| gpt-oss:120b | qwen3:4b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| gpt-oss:20b | qwen3:4b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| claude-sonnet | gpt-oss:20b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| claude-sonnet | qwen3:4b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| claude-haiku | qwen3:4b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| claude-opus | qwen3:4b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| claude-opus | gpt-oss:20b | ? | ? | ? | ? | ? | ? | ? | 0.3 |
| gpt-oss:20b | gpt-oss:20b | 3996 | 5919 | 0.7x | 100% | 0.80 | 0.31 | 14.7 | 0.3 |

_(? = pending, will be filled by `compare_models.py` after SLURM jobs complete)_

### Table D: Temperature Sensitivity (fixed solver/draft pair)

| Temperature | Solver | Draft | Hit% | σ | W | N_conv | Benefit | Confidence |
|-------------|--------|-------|------|---|---|--------|---------|------------|
| 0.1 | gpt-oss:120b | qwen3:4b | ? | ? | ? | ? | ? | ? |
| 0.3 | gpt-oss:120b | qwen3:4b | ? | ? | ? | ? | ? | ? |
| 0.5 | gpt-oss:120b | qwen3:4b | ? | ? | ? | ? | ? | ? |
| 0.7 | gpt-oss:120b | qwen3:4b | ? | ? | ? | ? | ? | ? |

### Table E: Provider Comparison (Cloud vs Edge)

| Property | Edge (Ollama on GH200) | Cloud (Claude API) |
|----------|----------------------|-------------------|
| **Latency Profile** | Low, predictable (no network) | Higher, variable (network + queue) |
| **Cost Structure** | Fixed (hardware amortization) | Per-token (usage-based) |
| **Scalability** | Limited by local GPU count | Elastic (API rate limits) |
| **Privacy** | Data stays on-prem | Data sent to cloud |
| **Model Selection** | Open-weight models only | Proprietary models |
| **Speculation Benefit** | Less (solver is already fast) | More (hides cloud latency) |
| **Best Solver Latency** | gpt-oss:20b ~4s | claude-haiku ~3s |
| **Worst Solver Latency** | gpt-oss:120b ~?s | claude-opus ~?s |

### Table F: Compute Resource Usage

| Model | GPU Memory Used | GPU Utilization | CPU Threads | Peak RAM | Power Draw |
|-------|----------------|-----------------|-------------|----------|------------|
| gpt-oss:20b | ~16 GB / 120 GB | measured | 288 | ~20 GB | measured |
| gpt-oss:120b | ~75 GB / 120 GB | measured | 288 | ~80 GB | measured |
| qwen3:4b | ~3 GB / 120 GB | measured | 288 | ~5 GB | measured |
| Multiple (20b+4b) | ~19 GB / 120 GB | measured | 288 | ~25 GB | measured |
| Multiple (120b+20b) | ~91 GB / 120 GB | measured | 288 | ~95 GB | measured |

## What Each Run Directory Contains

```
runs/<timestamp>_<baseline>_<solver>_<draft>_<nreq>/
├── config.json                   # Full config: models, temps, fleet, thresholds
├── summary.json                  # Aggregate metrics (all 7 above)
├── all_results.json              # Per-interaction event log
└── interaction_001/
    ├── layer1_intent.json        # Intent detection output
    ├── layer2_solver.json        # Solver's dispatch plan (the "answer")
    ├── layer2_solver_plan.md     # Human-readable solver plan
    ├── layer2_speculator.json    # Speculator's draft plan (the "guess")
    ├── layer2_speculator_plan.md # Human-readable draft plan
    ├── layer3_reconciliation.json # COMMIT/PARTIAL/FLUSH verdict
    ├── layer4_execution.json     # Real agent outputs + timings
    ├── layer4_mode3_draft.json   # Draft execution output (Mode 3 only)
    ├── layer5_learner.json       # Learner state update
    └── timing.json               # Layer-by-layer latency breakdown
```

## Existing Results

### Completed (gpt-oss:20b homogeneous fleet, n=5 and n=20)
- `20260401_*_fleet2_5req/` — Initial 5-request runs, all 5 baselines
- `20260401_*_fleet2_20req/` — Full 20-request runs, all 5 baselines
- `comparison_gptoss_vs_original.json` — Comparison vs original qwen2.5+llama3.1+Claude fleet
- `full_eval_gptoss_20b_summary.json` — Consolidated n=20 results

### Pending (heterogeneous fleet, queued on SLURM)
- Tier 1: 3 local solver configs × 5 baselines = 15 runs
- Tier 1: 2 cloud solver configs × 5 baselines = 10 runs
- Tier 2: 3 Claude tier configs × 2 baselines = 6 runs
- Tier 3: 4 temperatures × 2 baselines = 8 runs
- **Total: 39 new runs, ~780 interactions**

## Key Claims to Verify

1. **L_spec << L_s** — Speculation is orders of magnitude faster than solving (requires heterogeneous models)
2. **Hit rate ≥ 80%** — Speculation is accurate enough to be profitable
3. **Pythia > SwoL** — The learner improves over static speculation
4. **Oracle ≥ Pythia** — Oracle is the upper bound
5. **Lower temperature → higher hit rate** — More deterministic = more predictable
6. **Mode progression 1→2→3** — System progressively activates more aggressive speculation

## How to Run Comparison

```bash
# After all SLURM jobs complete:
module load python/anaconda3/2.10.0
python3 /u/sislam3/pythia/evaluation_bench/compare_models.py \
    --runs-dir /u/sislam3/pythia/evaluation_bench/workloads/hpc_cg/runs
```
