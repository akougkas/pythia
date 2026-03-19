---
case: case_002_file_watcher
framework: claude_code
model: gpt-oss:20b
provider: ollama
session_id: 5a6f2122-8d06-431e-a945-b989d68f21a9
duration_ms: 39505
duration_wall_s: 41.2
cost_usd: 0.859135
num_turns: 4
timestamp: 2026-03-19T14:07:51.929654+00:00
error: None
---

# Plan

# Plan: File Watcher CLI Tool

## Context
The project requires a lightweight Python command‑line interface that monitors a directory for file changes and automatically runs a user‑configured command (e.g., running tests).  The watcher should be simple to configure, robust against rapid successive file events, and portable across common OSes.

## Requirements
- Use the `watchdog` library for filesystem events.
- Load settings from a `watcher.yaml` configuration file.
- Support `include` and `exclude` glob patterns to filter which files trigger the command.
- Debounce rapid events – default debounce interval 300 ms.
- Expose a minimal CLI (`watcher.py`) that accepts optional arguments for directory, config file, and debug mode.
- Provide unit tests (`test_watcher.py`) that cover configuration parsing, pattern matching, and debounce logic.

## Design Decisions
| Decision | Rationale |
|---|---|
| **Location of source code** | All new files live under the working‑dir root to keep the example self‑contained. |
| **Configuration format** | YAML for readability and wide support (`pyyaml`). |
| **Debounce implementation** | `threading.Timer` to schedule command execution after the last event within the debounce window. |
| **Command execution** | `subprocess.run` with `shell=True` to allow arbitrary shell commands. |
| **Testing strategy** | Use `pytest` with temporary directories and monkeypatching of `subprocess.run` to capture invocation. |

## File Map & Responsibilities
| File | Purpose |
|------|---------|
| `watcher.py` | CLI entry point, parses args, loads config, starts the watchdog observer, and sets up the event handler. |
| `config.py` | Reads `watcher.yaml`, validates schema, and exposes a `Config` dataclass with fields: `paths`, `include`, `exclude`, `command`, `debounce_ms`. |
| `watcher.yaml` | Example configuration file with documentation comments. |
| `test_watcher.py` | Test suite for `config.py` and the event handler logic. |
| `README.md` (optional) | Usage instructions. |

## Implementation Outline
1. **config.py**
   * Define a `Config` dataclass.
   * Implement `load_config(path: str) -> Config` that uses `yaml.safe_load`.
   * Provide default values (empty include/exclude, 300 ms debounce, command `pytest`).
   * Validate that `paths` is a list of existing directories.

2. **watcher.py**
   * Use `argparse` to accept:
     - `--dir` (default `.`)
     - `--config` (default `watcher.yaml` in watched dir)
     - `--debug` (flag to print event details)
   * Load config via `config.load_config`.
   * Create a custom `PatternEventHandler` subclassing `watchdog.events.FileSystemEventHandler`.
     - On `on_modified`, `on_created`, `on_deleted`, filter paths using glob patterns from config.
     - If event passes filters, schedule command execution with debounce.
   * Use `threading.Timer` to implement debounce: cancel any existing timer and start a new one for `debounce_ms`.
   * Run the command via `subprocess.run(config.command, shell=True, cwd=watch_dir)`.
   * Start `Observer`, schedule the handler on the watched directory, and keep running until `KeyboardInterrupt`.

3. **watcher.yaml**
   ```yaml
   # Directory (or list of directories) to watch – relative to the config file location
   paths:
     - .
   # Glob patterns to include – empty means all files
   include: []
   # Glob patterns to exclude – e.g. ['*.pyc', '__pycache__']
   exclude: []
   # Command to run when a change is detected
   command: pytest
   # Debounce interval in milliseconds
   debounce_ms: 300
   ```

4. **test_watcher.py**
   * Test `Config.load_config` with various YAML snippets.
   * Test pattern matching logic in the handler (include/exclude).
   * Test debounce behavior: simulate rapid consecutive events and ensure the command runs only once after the last event.
   * Use `pytest` fixtures to create temporary directories and monkeypatch `subprocess.run` to record calls.

## Verification
1. **Manual run**:
   ```bash
   python watcher.py --dir tests --debug
   ```
   Create/modify files in `tests` and observe that the configured command is executed after a 300 ms pause.
2. **Unit tests**:
   ```bash
   pytest test_watcher.py
   ```
   All tests should pass, confirming config parsing, pattern filtering, and debounce logic.
3. **Cross‑platform**:
   Verify on at least Linux and macOS. Watchdog uses platform‑specific backends but exposes a consistent API.

## Assumptions
- The working directory will contain a `watcher.yaml` or the user will provide a path.
- The user has `watchdog`, `pyyaml`, and `pytest` installed; otherwise `pip install -r requirements.txt` will be documented.
- The command to run is safe to execute with `shell=True`.

## Next Steps
Once the plan file is saved, the implementation phase can begin. The plan will be used to guide the creation of the four files and the accompanying tests.

