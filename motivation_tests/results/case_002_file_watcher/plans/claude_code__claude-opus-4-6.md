---
case: case_002_file_watcher
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: 5665b15b-e160-48e4-b6b1-feac3d381972
duration_ms: 155273
duration_wall_s: 164.0
cost_usd: 0.44387835000000003
num_turns: 10
timestamp: 2026-03-18T00:44:48.344473+00:00
error: None
---

# Plan

# Plan: Case 002 — File Watcher CLI Tool

## Context
Create a Python CLI tool that monitors a directory for file changes using `watchdog` and runs a configurable command (e.g., test suite) on source file modifications. All files are created from scratch in the empty `WorkingDir/`.

**Base path**: `/home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/WorkingDir/`

---

## Step 1: Create `config.py` — YAML Config Loader

- Define a `WatcherConfig` dataclass with fields:
  - `watch_dir: str` (required)
  - `command: str` (required)
  - `include: list[str]` (default `["*"]`)
  - `exclude: list[str]` (default `[]`)
  - `debounce_ms: int` (default `300`)
- `from_dict(data)` classmethod: validate required fields, apply defaults, raise `ValueError` on missing/invalid fields
- `load(path)` classmethod: read YAML with `yaml.safe_load`, delegate to `from_dict`
- `debounce_seconds` property: `debounce_ms / 1000.0`
- Dependencies: `pyyaml`

## Step 2: Create `watcher.yaml` — Example Configuration

```yaml
watch_dir: src/
command: python -m pytest
include:
  - "*.py"
exclude:
  - "__pycache__"
debounce_ms: 300
```

## Step 3: Create `watcher.py` — Main CLI Entry Point

### `matches_globs(filepath, patterns) -> bool`
- Check filename, full path, AND each path component against each pattern using `fnmatch.fnmatch`
- Checking path components handles directory-name excludes like `__pycache__`

### `ChangeHandler(FileSystemEventHandler)`
- `__init__(config)`: store config, init `_timer: Timer | None`, `_lock: threading.Lock`
- `_qualifies(event)`: skip directories; compute relative path from `watch_dir`; check include (must match ≥1) then exclude (must match none)
- `_schedule()`: cancel pending timer, start new `threading.Timer(debounce_seconds, _run_command)` — daemon thread
- `_run_command()`: `subprocess.run(command, shell=True)` with stdout/stderr streaming to terminal
- `on_modified/on_created/on_deleted` → `_handle(event)`: if qualifies, print change info and call `_schedule()`

### `main()`
- `argparse` with `--config` (default `watcher.yaml`)
- Load config, resolve `watch_dir`, print startup info
- Create `Observer`, schedule handler recursively, start
- Main loop: `observer.join(timeout=1)` in try/except `KeyboardInterrupt` for clean shutdown

## Step 4: Create `test_watcher.py` — Unit Tests

Four test classes using `pytest` + `unittest.mock`:

1. **TestConfigLoading** — valid config, defaults applied, missing `watch_dir`/`command` raise `ValueError`, `debounce_seconds` property, load from temp YAML file
2. **TestGlobMatching** — `*.py` matches `.py`, rejects `.txt`; `__pycache__` matches path containing it; multiple patterns
3. **TestDebounce** — two rapid `_schedule()` calls → `_run_command` fires only once; single call fires after delay
4. **TestEventHandler** — directory events rejected; matching file accepted; excluded file rejected

---

## Verification

```bash
cd WorkingDir/

# Install dependencies
pip install watchdog pyyaml pytest

# Run unit tests
python -m pytest test_watcher.py -v

# Manual smoke test: create src/ with a .py file, run watcher, edit the file
mkdir -p src && echo "x = 1" > src/app.py
python watcher.py --config watcher.yaml
# In another terminal: echo "x = 2" > src/app.py → should see watcher trigger
```

