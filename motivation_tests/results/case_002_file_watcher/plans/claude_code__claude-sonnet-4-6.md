---
case: case_002_file_watcher
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: 5c256ad9-3725-46e4-accf-f6a123926d25
duration_ms: 203441
duration_wall_s: 215.0
cost_usd: 0.52302125
num_turns: 6
timestamp: 2026-03-18T00:41:23.767688+00:00
error: None
---

# Plan

# Plan: Case 002 — Python CLI File Watcher

## Context

Build a file-watching CLI tool that monitors a directory and runs a
configurable shell command whenever source files are modified. The tool
must debounce rapid file-system events so a burst of saves fires the
command only once.

The deliverables live in:
`/home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/`

`WorkingDir/` (currently empty) is the example directory to monitor.

---

## Critical Files

| File | Role |
|------|------|
| `config.py` | YAML loader, schema validation, defaults |
| `watcher.py` | CLI entry point, watchdog + debounce logic |
| `watcher.yaml` | Example configuration |
| `test_watcher.py` | Unit tests (unittest + unittest.mock) |

External dependencies: `watchdog`, `pyyaml` (both standard installs).

---

## Implementation Plan

### 1. `config.py`

**Exports:** `load_config(path: str) -> dict`, `DEFAULTS`, `REQUIRED_FIELDS`

```
DEFAULTS = {
    "include_patterns": ["*"],
    "exclude_patterns": ["*.pyc", "__pycache__/*", ".git/*"],
    "debounce_seconds": 0.3,
}
REQUIRED_FIELDS = ["watch_dir", "command"]
```

**`load_config` steps:**
1. `open(path)` — let `FileNotFoundError` propagate naturally.
2. `yaml.safe_load(f)` — use `safe_load` (not `load`) for security.
3. Guard `None` result (empty file) → treat as `{}`.
4. `_apply_defaults(raw)` — `result.setdefault(k, v)` for each default.
5. For each field in `REQUIRED_FIELDS`, raise `ValueError(f"Missing required config field: '{field}'")`  if absent.
6. Return merged dict.

> **Do not** resolve `watch_dir` here; `watcher.py` resolves it relative to
> the config file's directory so invocation from any cwd works.

---

### 2. `watcher.yaml`

```yaml
watch_dir: ./WorkingDir
command: echo "Files changed, running tests..." && python -m pytest
include_patterns:
  - "*.py"
  - "*.yaml"
exclude_patterns:
  - "*.pyc"
  - "__pycache__/*"
  - ".git/*"
debounce_seconds: 0.3
```

---

### 3. `watcher.py`

**Imports:** `argparse`, `fnmatch`, `os`, `subprocess`, `threading`, `time`,
`watchdog.events`, `watchdog.observers`, `from config import load_config`

#### `DebounceHandler(FileSystemEventHandler)`

```python
def __init__(self, config: dict, command_runner=None):
    self.config = config
    self._timer: threading.Timer | None = None
    self._lock = threading.Lock()           # guards _timer across threads
    self._command_runner = command_runner or self._run_command
```

**`on_any_event(event)`**
- Return early if `event.is_directory` (avoid double-triggers from
  `DirModifiedEvent`).
- Call `_schedule_command()` if `_should_handle(event.src_path)`.

**`_should_handle(path) -> bool`**
- `basename = os.path.basename(path)`
- `included = any(fnmatch.fnmatch(basename, p) OR fnmatch.fnmatch(path, p) for p in include_patterns)`
- `excluded = any(fnmatch.fnmatch(basename, p) OR fnmatch.fnmatch(path, p) for p in exclude_patterns)`
- Return `included and not excluded`
- *(Testing both basename and full path handles patterns like `__pycache__/*`)*

**`_schedule_command()`**
```python
with self._lock:
    if self._timer: self._timer.cancel()
    self._timer = threading.Timer(config["debounce_seconds"], self._command_runner)
    self._timer.daemon = True   # don't block exit
    self._timer.start()
```

**`_cancel_timer()`** — cancel + set `_timer = None` under lock.

**`_run_command()`**
```python
result = subprocess.run(config["command"], shell=True)
if result.returncode != 0:
    print(f"[watcher] Command exited with code {result.returncode}")
```
- Non-zero exit is logged but **never raises** (a failing test suite must
  not stop the watcher).

#### `build_observer(config, handler) -> Observer`
```python
obs = Observer()
obs.schedule(handler, path=config["watch_dir"], recursive=True)
obs.start()
return obs
```

#### `main(argv=None)`
1. `argparse` with `--config` (default `watcher.yaml`).
2. `load_config(args.config)`.
3. Resolve `watch_dir` relative to config file's directory:
   ```python
   config_dir = os.path.dirname(os.path.abspath(args.config))
   config["watch_dir"] = os.path.join(config_dir, config["watch_dir"])
   ```
4. Create handler, build observer, print banner.
5. `while True: time.sleep(0.5)` — block until `KeyboardInterrupt`.
6. `finally:` `observer.stop()`, `handler._cancel_timer()`, `observer.join()`.

---

### 4. `test_watcher.py`

Use `unittest` + `unittest.mock`. Five test classes:

| Class | Covers |
|-------|--------|
| `TestLoadConfig` | valid YAML, missing required field, defaults, empty file, FileNotFoundError |
| `TestShouldHandle` | include match, exclude blocks, exclude > include, wildcard |
| `TestDebounce` | single event fires once, rapid events coalesce, cancel prevents fire |
| `TestOnAnyEvent` | directory events ignored, matching file schedules, non-matching ignored |
| `TestRunCommand` | `subprocess.run` called with `shell=True`, non-zero exit doesn't raise |

**Key mocking patterns:**
- `config.py` tests: `@patch("builtins.open", mock_open(...))` + `@patch("yaml.safe_load", return_value={...})`
- `DebounceHandler` tests: inject `command_runner=MagicMock()` via constructor
- `subprocess.run` tests: `@patch("subprocess.run")`
- Debounce timing: use real `time.sleep` with small intervals
  (`debounce_seconds=0.1`, sleep `0.2` to assert)

---

## Pitfalls to Avoid

1. **Thread safety:** `_lock` around `_timer` is mandatory — two rapid events
   can both pass the `_timer is None` check without it.
2. **Path resolution:** `watch_dir` must be resolved relative to the YAML
   file location, not the shell's cwd.
3. **Directory events:** `watchdog` fires `DirModifiedEvent` for every file
   change inside a directory — guard `event.is_directory` to avoid double
   triggers.
4. **fnmatch scope:** Patterns like `__pycache__/*` need full-path matching,
   not just basename matching.
5. **Timer daemon flag:** Without `daemon=True`, a pending timer keeps the
   process alive after Ctrl-C.

---

## Verification

### Unit tests
```bash
cd case_002_file_watcher/
python -m pytest test_watcher.py -v
```
All tests should pass in < 2s.

### Live smoke test
```bash
# Terminal 1
python watcher.py --config watcher.yaml

# Terminal 2
touch WorkingDir/foo.py
```
Expect: `[watcher] Running: echo "Files changed..."` fires ~300ms after touch.

### Debounce test
```bash
for i in $(seq 1 10); do touch WorkingDir/foo.py; sleep 0.05; done
```
Command fires exactly **once**, not ten times.

### Exclude pattern test
```bash
touch WorkingDir/foo.pyc
```
Watcher produces no output.

### Error handling
```bash
python watcher.py --config missing.yaml    # → FileNotFoundError
# YAML without 'command' field             # → ValueError: Missing required config field: 'command'
```

