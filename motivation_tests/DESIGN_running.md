# DESIGN: Plan Execution Experiments

## Motivation

eval1.py measures **plan quality** — how good a plan each framework+model produces.
This experiment measures **execution quality** — given the *same* plan, how much
working code does each model produce within a time budget?

This directly motivates Pythia's speculative dispatch thesis: a cheap/fast model
generates a plan quickly, then a capable model executes it. The question is whether
a pre-made plan (even from a weaker model) lets the executor produce better results
than starting from scratch.

## Plan Under Test

```
Source: results/case_002_file_watcher/plans/claude_code__ollama__gpt-oss_20b.md
Model:  gpt-oss:20b (local, via Ollama)
Time:   41.2s to generate
Score:  graded separately (see grades/)
```

The plan describes building a Python CLI file-watcher tool with config loading,
glob-based filtering, debounced event handling, and unit tests.

---

## Test 1: Opus Executes gpt-oss Plan (3-minute cutoff)

**Goal**: Measure how much working code Opus produces in 3 minutes when given
a pre-made plan from a cheap local model.

### Protocol

1. Create a fresh working directory: `runs/test1_opus_3min/`
2. Copy the gpt-oss plan into `runs/test1_opus_3min/PLAN.md`
3. Start a Claude Code session via Agent SDK:
   - Model: `claude-opus-4-6`
   - Permission mode: `bypassPermissions` (allow all tool use without prompts)
   - Prompt: `"Can you run the plan at PLAN.md"`
4. After **180 seconds** wall-clock, terminate the session
5. Snapshot the working directory

### What We Measure

| Metric | How |
|--------|-----|
| Files created | `ls` the working directory |
| Lines of code | `wc -l *.py` |
| Tests passing | `pytest --tb=short` exit code + count |
| Wall time used | `time.monotonic()` delta |
| API cost | From `ResultMessage.total_cost_usd` |
| Turns completed | From `ResultMessage.num_turns` |

---

## Test 2: Opus vs gpt-oss Executing Same Plan (parallel)

**Goal**: Compare execution quality of Opus vs gpt-oss when both get the same
plan and the same wall-clock budget (Opus's natural finish time).

### Protocol

1. Create two fresh working directories:
   - `runs/test2_opus/`
   - `runs/test2_gptoss/`
2. Copy the same gpt-oss plan into both as `PLAN.md`
3. Start **two** Claude Code sessions in parallel:
   - Session A: `claude-opus-4-6` (Anthropic API)
   - Session B: `gpt-oss:20b` (Ollama local)
   - Same prompt: `"Can you run the plan at PLAN.md"`
   - Same permission mode: `auto`
4. When **Opus finishes naturally**, terminate the gpt-oss session
5. Snapshot both working directories

### What We Compare

| Metric | Opus | gpt-oss |
|--------|------|---------|
| Files created | ... | ... |
| Lines of code | ... | ... |
| Tests passing | ... | ... |
| Code correctness | ... | ... |
| Wall time used | natural | same as Opus |
| Cost | $X.XX | $0.00 (local) |

---

## Implementation

### Runner Script: `eval_execution.py`

```
Usage:
  python eval_execution.py test1 --case case_002_file_watcher [--timeout 180]
  python eval_execution.py test2 --case case_002_file_watcher
  python eval_execution.py snapshot --dir runs/test1_opus_3min
```

### Key Functions

```python
async def run_session(
    model_name: str,
    provider: str,
    plan_path: Path,
    working_dir: Path,
    prompt: str,
    timeout_s: float | None = None,
    api_base_url: str = "",
) -> ExecutionResult:
    """
    Start a Claude Code session to execute a plan.
    Optionally terminates after timeout_s seconds.
    Returns session metadata + working dir path.
    """

def snapshot_workdir(working_dir: Path) -> dict:
    """
    Capture the state of a working directory after execution:
    - File list with sizes
    - Total lines of code
    - pytest results (if test files exist)
    """

async def test1_baseline(
    plan_path: Path,
    case_dir: Path,
    timeout_s: float = 180.0,
) -> ExecutionResult:
    """Test 1: Opus executes plan with 3-min cutoff."""

async def test2_parallel(
    plan_path: Path,
    case_dir: Path,
) -> tuple[ExecutionResult, ExecutionResult]:
    """Test 2: Opus and gpt-oss execute same plan in parallel."""
```

### Session Configuration

**Opus (Anthropic API)**:
```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",
    model="claude-opus-4-6",
    cwd=str(working_dir),
    disallowed_tools=["AskUserQuestion"],
)
```

**gpt-oss (Ollama local)**:
```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",
    model="gpt-oss:20b",
    cwd=str(working_dir),
    disallowed_tools=["AskUserQuestion"],
    env={
        "ANTHROPIC_BASE_URL": "http://localhost:11434/v1",
        "ANTHROPIC_AUTH_TOKEN": "local",
        "ANTHROPIC_API_KEY": "local",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-oss:20b",
        "CLAUDE_CODE_SUBAGENT_MODEL": "gpt-oss:20b",
    },
)
```

### Timeout Mechanism (Test 1)

```python
try:
    result = await asyncio.wait_for(run_session(...), timeout=180)
except asyncio.TimeoutError:
    result = partial_result  # whatever was captured before timeout
```

### Parallel Execution (Test 2)

```python
opus_task = asyncio.create_task(run_session("claude-opus-4-6", ...))
gptoss_task = asyncio.create_task(run_session("gpt-oss:20b", ...))

# Wait for Opus to finish, then cancel gpt-oss
opus_result = await opus_task
gptoss_task.cancel()
try:
    gptoss_result = await gptoss_task
except asyncio.CancelledError:
    gptoss_result = partial_result
```

---

## Output Structure

```
motivation_tests/
  runs/
    test1_opus_3min/          # Test 1 output
      PLAN.md                 # copied plan
      config.py               # generated by Opus
      watcher.py              # generated by Opus
      test_watcher.py         # generated by Opus
      ...
      _result.json            # session metadata
      _snapshot.json           # file manifest + pytest results
    test2_opus/               # Test 2, Opus output
      PLAN.md
      ...
      _result.json
      _snapshot.json
    test2_gptoss/             # Test 2, gpt-oss output
      PLAN.md
      ...
      _result.json
      _snapshot.json
```

---

## How to Run

```bash
# Prerequisite: Ollama running with gpt-oss:20b pulled
ollama list | grep gpt-oss

# Test 1: Opus with 3-min cutoff
python eval_execution.py test1 --case case_002_file_watcher --timeout 180

# Test 2: Opus vs gpt-oss parallel
python eval_execution.py test2 --case case_002_file_watcher

# Inspect results
python eval_execution.py snapshot --dir runs/test1_opus_3min
python eval_execution.py snapshot --dir runs/test2_opus
python eval_execution.py snapshot --dir runs/test2_gptoss
```

---

## Expected Insights

- **Test 1**: How much can Opus accomplish in 3 minutes with a pre-made plan?
  If it completes the full implementation, the speculative-dispatch pipeline
  (fast planner + capable executor) is viable.

- **Test 2**: Given the same plan and same wall-clock budget, does Opus
  produce meaningfully better code than gpt-oss? If yes, the cost premium
  for Opus execution is justified. If gpt-oss produces comparable results,
  the entire pipeline could run locally at zero cost.
