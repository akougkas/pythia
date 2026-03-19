---
case: case_002_file_watcher
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: 47226cd5-a3b1-4716-947b-eeea3ab5345d
duration_ms: 430251
duration_wall_s: 440.5
cost_usd: 0.815368
num_turns: 6
timestamp: 2026-03-19T13:55:11.112663+00:00
error: None
---

# Plan

# Plan: Case 002 — File Watcher CLI Tool

## Context

Build a Python CLI tool that watches a directory for file changes and automatically runs a configurable command when source files are modified. The tool uses `watchdog` for filesystem events, reads its configuration from a `watcher.yaml` file, supports include/exclude glob patterns, and debounces rapid changes (300ms default). All files are created in the empty working directory at `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/`.

---

## Deliverables & File Locations

| File | Path |
|---|---|
| `watcher.yaml` | `WorkingDir/watcher.yaml` |
| `config.py` | `WorkingDir/config.py` |
| `watcher.py` | `WorkingDir/watcher.py` |
| `test_watcher.py` | `WorkingDir/test_watcher.py` |

**Dependencies (not stdlib):** `watchdog >= 3.0`, `PyYAML >= 6.0`

---

## Architecture

```
WorkingDir/
├── watcher.yaml      # Runtime config (watched by the tool itself for demo)
├── config.py         # YAML loader → nested dataclass tree
├── watcher.py        # Pattern matching + Debouncer + ChangeHandler + CLI main()
└── test_watcher.py   # Unit tests (all I/O mocked)
```

---

## File 1: `watcher.yaml`

Example configuration covering all supported keys:

```yaml
watch:
  paths:
    - "."
  recursive: true

patterns:
  include:
    - "**/*.py"
    - "**/*.yaml"
  exclude:
    - "**/__pycache__/**"
    - "**/*.pyc"
    - "**/.git/**"

debounce_ms: 300

on_change:
  command: "echo 'Changed: {file}'"

events:
  modified: true
  created: true
  deleted: true
  moved: true
```

- `{file}` in `command` is substituted with the absolute path of the changed file.
- All keys have defaults in `config.py` so a minimal YAML (or missing file) is valid.

---

## File 2: `config.py`

### Design

Five nested dataclasses mirroring the YAML structure:

```
WatchConfig      → paths: List[str], recursive: bool
PatternConfig    → include: List[str], exclude: List[str]
OnChangeConfig   → command: str
EventConfig      → modified/created/deleted/moved: bool
Config           → watch, patterns, debounce_ms, on_change, events
```

### Key functions

- `_build_config(raw: dict) -> Config` — constructs dataclasses from parsed YAML dict
- `Config.validate()` — raises `ValueError` for: `debounce_ms < 0`, empty `watch.paths`, non-string patterns
- `load_config(path) -> Config` — opens YAML file; returns defaults if file missing

### Defaults

| Field | Default |
|---|---|
| `watch.paths` | `["."]` |
| `watch.recursive` | `True` |
| `patterns.include` | `["**/*"]` |
| `patterns.exclude` | `[]` |
| `debounce_ms` | `300` |
| `on_change.command` | `"echo 'Changed: {file}'"` |
| all `events.*` | `True` |

---

## File 3: `watcher.py`

### Component 1: Pattern Matching

**Design decision:** Use `pathlib.PurePosixPath.match()` on backslash-normalized paths.
`PurePath.match("**/*.py")` matches from the right, works correctly on absolute paths, and handles `**` in Python 3.10+.

```python
def matches_pattern(abs_path: str, pattern: str) -> bool:
    return PurePosixPath(abs_path.replace("\\", "/")).match(pattern)

def should_handle(abs_path: str, include: list[str], exclude: list[str]) -> bool:
    included = any(matches_pattern(abs_path, p) for p in include)
    excluded = any(matches_pattern(abs_path, p) for p in exclude)
    return included and not excluded
```

### Component 2: `Debouncer` class

Cancel/restart `threading.Timer` per file path. Thread-safe via `threading.Lock`.

```python
class Debouncer:
    def __init__(self, delay_ms: int, callback): ...
    def trigger(self, path: str) -> None:   # cancel existing timer, start new one
    def _fire(self, path: str) -> None:     # clears self._timer, calls callback
    def cancel(self) -> None:               # cancel without firing
```

- Timer delay = `delay_ms / 1000.0`
- Timer is set as `daemon = True` so it doesn't block process exit

### Component 3: `ChangeHandler(FileSystemEventHandler)`

- One `Debouncer` instance per unique `src_path` (stored in `self._debouncers` dict)
- Handles `on_modified`, `on_created`, `on_deleted`, `on_moved`
- All four delegate to `_dispatch(event, kind)`:
  1. Skip if `event.is_directory`
  2. Skip if `config.events.<kind>` is `False`
  3. Skip if `should_handle()` returns `False`
  4. Look up/create `Debouncer` for `event.src_path`, call `.trigger(path)`

`_run_command(path)`:
- Formats `config.on_change.command.format(file=path)`
- Runs via `subprocess.run(shlex.split(cmd), check=False, capture_output=False)`
- Catches `FileNotFoundError` and generic `Exception`, prints errors without crashing

### Component 4: CLI `main()`

`argparse` with arguments:
- `-c/--config FILE` (default: `watcher.yaml`)
- `--paths PATH [PATH ...]` — overrides `watch.paths`
- `--command CMD` — overrides `on_change.command`
- `--debounce-ms MS` — overrides `debounce_ms`

Setup:
```python
cfg = load_config(args.config)
# apply CLI overrides
handler = ChangeHandler(cfg)
observer = Observer()
for path in cfg.watch.paths:
    resolved = str(Path(path).resolve())
    observer.schedule(handler, resolved, recursive=cfg.watch.recursive)
observer.start()
while observer.is_alive():
    observer.join(timeout=1.0)   # blocks until KeyboardInterrupt
# finally: observer.stop(), observer.join()
```

---

## File 4: `test_watcher.py`

All tests use `unittest`. All real I/O and subprocess calls are mocked.

### Test Groups

**`TestBuildConfig`** — `_build_config({})` produces correct defaults; overrides for paths, patterns, debounce, command, event flags, recursive.

**`TestConfigValidation`** — `ValueError` for negative debounce, empty paths, non-string patterns; zero debounce is valid.

**`TestLoadConfig`** — returns defaults when file is missing.

**`TestMatchesPattern`** — `**/*.py` matches `.py` files at any depth; doesn't match `.yaml`; Windows backslashes normalized; `**/__pycache__/**` matches cache files; `**/*` matches everything.

**`TestShouldHandle`** — excluded overrides included; not in include returns False; multiple include patterns; empty include returns False.

**`TestDebouncer`**:
- `patch("watcher.threading.Timer")` — assert `Timer(0.3, d._fire, args=(path,))` called on trigger
- Second trigger cancels first timer before starting new one
- `_fire()` directly invokes callback
- `cancel()` calls `timer.cancel()`
- Zero delay produces `0.0` second timer

**`TestChangeHandlerDispatch`**:
- `DirModifiedEvent` ignored (is_directory=True)
- File matching include → `debouncer.trigger()` called
- File matching exclude → `debouncer.trigger()` NOT called
- `events.modified = False` → event ignored
- Tests for created/deleted/moved event dispatch
- Pattern mismatch → not dispatched

**`TestChangeHandlerRunCommand`**:
- `{file}` placeholder substituted with path
- Command without placeholder passed as-is
- `FileNotFoundError` caught gracefully
- Non-zero exit code printed (mocked `builtins.print`)

**`TestDebouncerIntegration`**:
- Same path → same `Debouncer` instance reused
- Different paths → different `Debouncer` instances

### Mocking strategy

```python
# Mock the Timer at the watcher module level (not threading module level)
with patch("watcher.threading.Timer") as MockTimer:
    mock_timer = MagicMock()
    MockTimer.return_value = mock_timer
    ...

# Mock subprocess at watcher module level
with patch("watcher.subprocess.run") as mock_run:
    mock_run.return_value = MagicMock(returncode=0)
    ...
```

Watchdog event objects (`FileModifiedEvent("/abs/path/file.py")`) are constructed directly — no mocking needed.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| `**` glob matching | `PurePosixPath.match()` with backslash normalization | Matches from right; `**` supported in Python 3.10+; cross-platform |
| Debounce per path | One `Debouncer` per unique `src_path` | Prevents unrelated file changes from coalescing |
| Directory events | Skipped via `event.is_directory` | Directory events are noisy and cause false positives in pattern matching |
| Moved event path | Uses `src_path` for pattern check | Identifies "what left"; `{dest}` extension possible in future |
| Config library | Stdlib `dataclasses` + `PyYAML` | Minimizes deps beyond `watchdog`; explicit defaults are self-documenting |
| Sample project | Not created | `watcher.yaml` uses `"."` for self-referential demo; keeps dir clean |

---

## Verification

1. **Install deps:** `pip install watchdog pyyaml`
2. **Run tests:** `python -m pytest test_watcher.py -v` (or `python -m unittest test_watcher`)
3. **Smoke test:**
   ```bash
   cd WorkingDir
   python watcher.py --config watcher.yaml
   # In another terminal: touch test_file.py
   # Expected: "[watcher] Running: echo 'Changed: /abs/path/test_file.py'"
   ```
4. **CLI override test:** `python watcher.py --command "pytest" --debounce-ms 500`
5. **Exclusion test:** Create `__pycache__/foo.pyc` — should NOT trigger command
6. **Debounce test:** Rapidly save the same file multiple times — command should fire only once

