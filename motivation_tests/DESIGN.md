# Eval1 — Plan Quality Evaluation Harness

## Design Document

**Author:** Jaime  
**Status:** Phase 1 ready, Phase 2–3 designed  
**Last updated:** 2026-03-17

---

## 1. Overview

`eval1.py` is a harness that evaluates how well different **agentic coding
frameworks** and **models** produce implementation plans for a set of
standardized tasks ("cases").

The core loop is:

```
C cases  ×  F frameworks  ×  M models  =  C·F·M plans
```

For 3 cases, 2 frameworks, and 3 models you get 18 plans to compare.

---

## 2. Directory Layout

```
project_root/
│
├── eval1.py                          # Main harness (all phases)
│
├── cases/                            # Input: evaluation cases
│   ├── case_001_add_numbers/
│   │   ├── PROMPT.md                 # The task specification
│   │   └── WorkingDir/               # Context materials (papers, code, configs)
│   │
│   ├── case_002_file_watcher/
│   │   ├── PROMPT.md
│   │   └── WorkingDir/
│   │       └── README.md
│   │
│   └── case_003_data_pipeline/
│       ├── PROMPT.md
│       └── WorkingDir/
│           └── sample_data.csv
│
└── results/                          # Output: generated plans + grades
    ├── case_001_add_numbers/
    │   ├── plans/
    │   │   ├── claude_code__claude-sonnet-4-6.md
    │   │   ├── claude_code__claude-sonnet-4-6.json    # full metadata
    │   │   ├── claude_code__glm-4.7-flash.md
    │   │   ├── claude_code__glm-4.7-flash.json
    │   │   ├── aider__claude-sonnet-4-6.md            # future
    │   │   └── aider__glm-4.7-flash.md                # future
    │   ├── grades/
    │   │   ├── claude_code__glm-4.7-flash__graded.json
    │   │   └── aider__claude-sonnet-4-6__graded.json
    │   └── reference_plan.md          # human-selected best plan
    │
    └── eval_summary.json
```

---

## 3. The Three Phases

### Phase 1 — Plan Generation

**Goal:** Generate `C·F·M` plans without executing anything.

**How it works:**

1. Load all cases from `cases/` (each has `PROMPT.md` + `WorkingDir/`)
2. For each `(case, framework, model)` triple:
   - Call the framework in **planning mode**
   - Capture the plan text
   - Save to `results/<case>/plans/<framework>__<model>.md`
   - Save full metadata to the corresponding `.json` file

**Claude Code specifics:**
- Uses `permission_mode="plan"` in `ClaudeAgentOptions`
- The plan arrives via the `ExitPlanMode` tool call
- Captured from `ToolUseBlock.input["plan"]`
- Working directory pointed at the case's `WorkingDir/`

**Ollama specifics:**
- Injects env vars into the CLI subprocess: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`
- Model name passed via `model=` option (e.g., `glm-4.7-flash`, `qwen3-coder`)
- Requires Ollama v0.14+ for Anthropic Messages API compatibility
- Needs tool-calling support in the model

**Usage:**

```bash
# All cases, Anthropic models only
python eval1.py generate --cases-dir ./cases

# Include Ollama models
python eval1.py generate --cases-dir ./cases --include-ollama

# Specific models
python eval1.py generate --cases-dir ./cases \
    --models claude-sonnet-4-6 glm-4.7-flash qwen3-coder

# Single case
python eval1.py generate --cases-dir ./cases --case case_001_add_numbers
```

### Phase 2 — Reference Selection (Human-in-the-Loop)

**Goal:** For each case, a human picks the best plan as the "gold standard."

**How it works:**

1. Human reads the generated plans in `results/<case>/plans/`
2. Picks the best one
3. Marks it as reference:

```bash
# List available plans
python eval1.py list-plans --case case_001_add_numbers

# Set the reference
python eval1.py set-reference \
    --case case_001_add_numbers \
    --plan claude_code__claude-sonnet-4-6.md
```

This copies the plan to `results/<case>/reference_plan.md`.

**Open question for the future:** Is the best framework-model combo consistent
across cases? Phase 3 grading data will let us answer this.

### Phase 3 — Semantic Grading

**Goal:** Have Opus judge every plan against the reference.

**How it works:**

1. For each case with a `reference_plan.md`:
2. For each candidate plan in `plans/`:
3. Build a grading prompt with the objective, reference, candidate, and categories
4. Send to Opus (via Claude Agent SDK, also in planning mode for safety)
5. Parse the JSON response with per-category scores
6. Save to `results/<case>/grades/<framework>__<model>__graded.json`

**Usage:**

```bash
# Grade all cases
python eval1.py grade --cases-dir ./cases

# Grade one case
python eval1.py grade --cases-dir ./cases --case case_001_add_numbers

# Use a different judge model
python eval1.py grade --judge-model claude-opus-4-6
```

---

## 4. Grading Categories

These are the dimensions Opus evaluates each plan on (1–5 scale):

| Category | What it measures |
|----------|-----------------|
| **Completeness** | Does the plan cover ALL deliverables and requirements? Are any steps or outputs missing? |
| **Correctness** | Are the proposed steps technically sound? Would following them actually achieve the objective? |
| **Specificity** | Does the plan give concrete, actionable steps (file names, function signatures, library choices) vs. vague intentions? |
| **Ordering & Dependencies** | Are steps in a logical order? Are dependencies correctly identified and sequenced? |
| **Error Handling** | Does the plan account for edge cases, input validation, and error handling as required? |
| **Testability** | Does the plan include a testing strategy? Are proposed tests sufficient? |
| **Clarity** | Is the plan well-organized and easy to follow? Could another developer execute it without ambiguity? |

**Possible future categories to consider:**

- **Efficiency** — Does the plan avoid unnecessary steps? Is the approach reasonably optimal?
- **Extensibility** — Does the plan set up the code for future modifications?
- **Idiomatic style** — Does the plan follow language/framework conventions?
- **Resource awareness** — Does the plan consider memory, disk, network constraints?

---

## 5. Framework Abstraction

The key extensibility point. Each framework is a subclass of `PlanningFramework`:

```python
class PlanningFramework(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput: ...
```

### Currently Implemented

| Framework | Class | Status |
|-----------|-------|--------|
| Claude Code (Agent SDK) | `ClaudeCodeFramework` | ✅ Working |
| Aider | `AiderFramework` | 🔲 Stub |
| OpenHands | `OpenHandsFramework` | 🔲 Stub |

### Adding a New Framework

1. Create a new class inheriting from `PlanningFramework`
2. Implement `name` property and `generate_plan()` method
3. Register in `FRAMEWORK_REGISTRY`
4. Add to `DEFAULT_FRAMEWORKS` if desired

**Example — Aider integration sketch:**

```python
class AiderFramework(PlanningFramework):
    @property
    def name(self) -> str:
        return "aider"

    async def generate_plan(self, case, model):
        # Aider's --architect mode produces plans
        proc = await asyncio.create_subprocess_exec(
            "aider", "--architect", "--yes",
            "--model", model.name,
            "--message", case.prompt,
            cwd=str(case.working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            plan_text=stdout.decode(),
        )
```

**Example — SWE-agent integration sketch:**

```python
class SWEAgentFramework(PlanningFramework):
    @property
    def name(self) -> str:
        return "swe_agent"

    async def generate_plan(self, case, model):
        # SWE-agent with --plan-only flag (hypothetical)
        # Or parse the trajectory for planning steps
        ...
```

---

## 6. Model Configuration

Models are defined as `ModelSpec` objects:

```python
@dataclass
class ModelSpec:
    name: str         # "claude-sonnet-4-6", "glm-4.7-flash"
    provider: str     # "anthropic" | "ollama"
    ollama_url: str = "http://localhost:11434"
```

### Anthropic Models

Edit `ANTHROPIC_MODELS` in `eval1.py`:

```python
ANTHROPIC_MODELS = [
    ModelSpec(name="claude-sonnet-4-6", provider="anthropic"),
    ModelSpec(name="claude-opus-4-6", provider="anthropic"),
    ModelSpec(name="claude-haiku-4-5-20251001", provider="anthropic"),
]
```

### Ollama Models

Edit `OLLAMA_MODELS` in `eval1.py`:

```python
OLLAMA_MODELS = [
    ModelSpec(name="glm-4.7-flash", provider="ollama"),
    ModelSpec(name="qwen3-coder", provider="ollama"),
    ModelSpec(name="devstral-small", provider="ollama"),
]
```

**Requirements for Ollama models:**
- Ollama v0.14+ (Anthropic Messages API compatibility)
- Tool-calling / function-calling support
- Minimum 32K context window (64K+ recommended)
- Model must be pulled: `ollama pull glm-4.7-flash`

---

## 7. Output Formats

### Plan file (`*.md`)

```markdown
---
case: case_001_add_numbers
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: abc123
duration_ms: 4523
duration_wall_s: 5.1
cost_usd: 0.0032
num_turns: 2
timestamp: 2026-03-17T15:30:00+00:00
error: None
---

# Plan

1. Create `add.py` with argparse setup...
2. Add input validation for non-numeric args...
...
```

### Grade file (`*__graded.json`)

```json
{
  "case_name": "case_001_add_numbers",
  "framework_name": "claude_code",
  "model_name": "glm-4.7-flash",
  "grades": {
    "completeness": {"score": 4, "reasoning": "Covers all deliverables..."},
    "correctness": {"score": 3, "reasoning": "Missing edge case for..."},
    ...
  },
  "overall_score": 3.7,
  "judge_reasoning": "The plan is solid but lacks..."
}
```

### Report (`report` command)

```
# Eval1 — Plan Quality Report

## case_001_add_numbers

| Framework  | Model             | Overall | Compl. | Corr. | Spec. | ...
|------------|-------------------|---------|--------|-------|-------|
| claude_code| claude-sonnet-4-6 | 4.3     | 5      | 4     | 4     | ...
| claude_code| glm-4.7-flash     | 3.7     | 4      | 3     | 4     | ...
| aider      | claude-sonnet-4-6 | 3.9     | 4      | 4     | 3     | ...
```

---

## 8. Open Questions

### Q1: Is the best framework-model combo consistent across cases?

Once we have grades for multiple cases, we can compute:
- Per-model average across cases
- Per-framework average across models
- Variance / standard deviation of scores per combo across cases
- Kendall's tau rank correlation between case rankings

If a combo ranks #1 on simple cases but #5 on complex ones, the answer is no.

### Q2: What should the grading categories be?

The current set (completeness, correctness, specificity, ordering, error
handling, testability, clarity) is a starting point. Potential additions:

- **Efficiency** — avoids unnecessary work
- **Extensibility** — sets up for future changes
- **Idiomatic style** — follows conventions
- **Security awareness** — considers security implications
- **Documentation** — plan includes comments/docs strategy

The categories can evolve as we learn what differentiates good plans.

### Q3: LLM-as-judge reliability

Opus grading introduces its own biases. Future work:
- Run grading multiple times and check consistency
- Compare Opus grades with human grades on a subset
- Try different judge models (Sonnet, GPT-4o) for calibration
- Consider pairwise comparison instead of absolute scoring

### Q4: Planning mode fidelity across local models

Smaller Ollama models may not reliably emit `ExitPlanMode` tool calls.
Fallback: capture reasoning text as the plan when no tool call arrives.
This is already handled in the code.

---

## 9. Quick Start

```bash
# 1. Install dependencies
pip install claude-agent-sdk

# 2. Set up cases (already provided)
ls cases/

# 3. Generate plans (Phase 1)
python eval1.py generate --cases-dir ./cases

# 4. Review plans
python eval1.py list-plans --case case_001_add_numbers
cat results/case_001_add_numbers/plans/claude_code__claude-sonnet-4-6.md

# 5. Pick the best (Phase 2)
python eval1.py set-reference \
    --case case_001_add_numbers \
    --plan claude_code__claude-sonnet-4-6.md

# 6. Grade all plans (Phase 3)
python eval1.py grade --cases-dir ./cases

# 7. Generate report
python eval1.py report
python eval1.py report --output report.md
```

---

## 10. Future Work

- **Phase 4: Execution evaluation** — Actually run the plans and check if
  the deliverables are correct (tests pass, code runs, etc.)
- **b) Execution-based validation** — The second way to validate a plan's
  correctness: execute it and run the test suite
- **Parallel generation** — Run multiple framework-model combos concurrently
  with `asyncio.gather()`
- **Cost tracking dashboard** — Aggregate cost data across all runs
- **CI integration** — Run eval1 in CI on every push to catch regressions
- **Case difficulty taxonomy** — Tag cases by complexity level and domain
