---
case: case_002_file_watcher
framework: claude_code
model: openai/gpt-oss-20b
provider: lm_studio
session_id: f0440fd0-a3b7-4a46-b2fb-203b7006db36
duration_ms: 82150
duration_wall_s: 88.6
cost_usd: 0.8162808
num_turns: 6
timestamp: 2026-03-18T15:26:46.115934+00:00
error: None
---

# Plan

# File Watcher CLI Implementation Plan

## 1. Context
The user wants a lightweight Python command‑line tool that monitors a directory for file changes and automatically runs a configurable command (e.g., test suite). The solution must use the `watchdog` library, load configuration from a YAML file (`watcher.yaml`), support include/exclude glob patterns, and debounce rapid events with a 300 ms default.

## 2. Project Layout
```
/watch/          # top‑level project directory (the repo root)
└── watcher/
    ├── __init__.py
    ├── config.py        # YAML loader & validation
    ├── watcher.py       # CLI entry point and watchdog logic
    ├── watcher.yaml.example  # Sample configuration
    ├── README.md        # Usage guide
    └── tests/
        ├── conftest.py  # pytest fixtures (mocks)
        ├── test_config.py
        └── test_watcher.py
```
All source files live under the `watcher/` package so it can be installed with `pip install .`.

## 3. Dependencies
| Package | Purpose |
|---------|---------|
| `watchdog` | File‑system event monitoring |
| `pyyaml` | YAML parsing |
| `typer`   | Modern CLI with type hints |
| `pydantic` or simple validation logic | Configuration schema enforcement |
| `pytest`, `pytest-mock` | Unit tests |

Add them to the project’s `pyproject.toml` under `[tool.poetry.dependencies]`.

## 4. Core Modules
### 4.1 `watcher/config.py`
- Load a YAML file (default `watcher.yaml` in cwd).
- Validate presence of required keys: `watch_dir`, `command`.
- Normalise optional `include`/`exclude` into lists.
- Raise a custom `ConfigError` with clear messages on problems.

### 4.2 `watcher/watcher.py`
- Use `typer.Typer()` as the CLI entry point.
- Read config via `config.load_config`.
- Validate that `watch_dir` exists.
- Create a `DebouncedHandler(FileSystemEventHandler)`:
  - Debounce rapid events (default 300 ms, overridable via CLI flag).
  - Filter events using glob patterns (`path.match(pattern)`).
  - Execute the configured command with `subprocess.run(..., shell=True, check=True)`.
- Start a `watchdog.Observer` on the target directory and run until interrupted.

### 4.3 `watcher/watcher.yaml.example`
```yaml
watch_dir: ./src
command: python -m mypackage.main
include:
  - "*.py"
exclude:
  - "__pycache__/*"
  - ".git/*"
```

### 4.4 `README.md`
- Brief install & usage instructions.
- Explain CLI options (`--config`, `--debounce`).
- Detail how include/exclude patterns work.

## 5. Tests (under `watcher/tests/`)
| Test | What it covers |
|------|----------------|
| `test_config_load_valid` | Proper YAML loads and normalises lists |
| `test_config_missing_keys` | Raises `ConfigError` when required keys are missing |
| `test_config_bad_yaml` | Syntax errors raise `ConfigError` |
| `test_watcher_includes_excludes` | Handler triggers only on matching paths |
| `test_debounce_behavior` | Rapid events cause a single command run after debounce interval |
| `test_command_success_and_failure` | Correct handling of subprocess exit codes |
| `test_watch_dir_validation` | CLI exits when watch directory does not exist |

Use `pytest-mock` to patch `subprocess.run` and `watchdog.observers.Observer` so tests run fast and deterministically.

## 6. Edge‑Case Handling
- Empty include/exclude lists → monitor all files.
- Include patterns that never match → no command runs.
- Exclude patterns that block everything → no command runs.
- Large debounce interval → respected by handler.
- Command outputs to stdout/stderr → forwarded via `subprocess.run`.

## 7. Verification Steps
1. Install the package locally (`pip install .`).
2. Run `watcher run` with the example config; modify a Python file and confirm the command executes.
3. Verify that rapid edits trigger only one execution (debounce). Use `pytest-mock` to assert `subprocess.run` call count.
4. Run unit tests: `pytest`. All should pass.

## 8. Summary of Critical Files
- `watcher/watcher.py` – core CLI and event handling logic.
- `watcher/config.py` – configuration loader/validator.
- `watcher/tests/test_watcher.py` – handler, debounce, include/exclude tests.
- `watcher/tests/test_config.py` – YAML parsing tests.

---
This plan provides a clear, step‑by‑step implementation strategy that meets all constraints and delivers the required functionality with robust testing.

