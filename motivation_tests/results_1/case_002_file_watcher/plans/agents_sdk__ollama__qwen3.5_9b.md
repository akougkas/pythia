---
case: case_002_file_watcher
framework: agents_sdk
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 42156
duration_wall_s: 42.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:07:25.725658+00:00
error: None
---

# Plan

# Case 002: File Watcher Implementation Plan

This plan details the step-by-step implementation of the Python CLI Directory File Watcher tool, adhering to the specified constraints and deliverables.

## 1. Assumptions & Pre-requisites

*   **Dependency Versions:** 
    *   `watchdog==3.0.0` (or latest stable)
    *   `PyYAML==6.0.1`
    *   `pytest==7.4.0`
    *   `click` (optional, but we will use `argparse` to minimize dependencies as per standard CLI practice unless specified otherwise. We will use `argparse`).
*   **Working Directory Path:** `/home/jye/publications/cases/case_002_file_watcher/WorkingDir`
*   **Command Execution:** Commands will be executed via `subprocess.run` with `shell=True` to allow shell expansions (e.g., variable expansion, piping) and chaining, which is standard for watch actions.
*   **Debouncing Logic:** Implemented via a `threading.Timer`. When a new event occurs, the previous timer is cancelled and a new one is set. If a new event occurs before the debounce window expires, the command does not run.
*   **Event Filtering:** File system event filtering will be handled by comparing the event path against glob patterns (relative to the watched root) using Python's `fnmatch`.
*   **Safety:** The watcher will run in a loop. If the watched directory is deleted, the program should catch `NotADirectoryError` or `PathError` and exit gracefully.
*   **Logging:** Output will use Python's `logging` module to keep the CLI clean, configured with `Rich`-style formatting (or standard console formatting).

---

## 2. File Structure & Locations

All files will be created in the `WatchingDir` root (or a sibling `src` folder if preferred, but per standard project structure, we will place these tools inside the project or a dedicated `utils` path). Based on the deliverables, we will place them in the project root:
*   `watcher.py`
*   `config.py`
*   `watcher.yaml`
*   `test_watcher.py`
*   `requirements.txt` (Optional but recommended for dependency management)

---

## 3. Implementation Detail: `config.py`

**Purpose:** Parse `watcher.yaml` and convert glob patterns into a usable filter structure.

**Steps:**
1.  **Imports:** Import `yaml`, `re`, `fnmatch`, `logging`.
2.  **Function: `load_config(path)`**
    *   Validate that the file exists.
    *   Read YAML content.
3.  **Validation Logic:**
    *   Extract `watched_dir` (optional, defaults to current dir if omitted in CLI).
    *   Extract `debounce_ms` (type cast to `int`).
    *   Extract `command` (string).
    *   Extract `include_patterns` and `exclude_patterns` (lists of strings).
4.  **Sanitization:**
    *   Ensure include/exclude patterns are strings.
    *   Return a dictionary object with these fields.
5.  **Helper: `is_ignored(path_str, config)`**
    *   Function to determine if a given OS path should trigger the event based on `include` and `exclude` lists.
    *   Logic:
        1.  Compute relative path: `path.relative_to(root)`.
        2.  If `include_patterns` exists, the relative path (filename only) must match at least one.
        3.  If `exclude_patterns` exists, the relative path must *not* match any.
        4.  If include is omitted (empty), ignore `exclude`? No, typically "no include" implies "all", but if include is empty list or missing key, we assume empty string matches everything or default to all. *Assumption:* If `include_patterns` is missing/empty, treat the filter as "only apply excludes". If present, apply both.
        5.  Implement logic: `match = fnmatch.fnmatch(rel_name, pattern)`.
6.  **Error Handling:** Raise `FileNotFoundError` or `ConfigError` if YAML parsing fails.

---

## 4. Implementation Detail: `watcher.py`

**Purpose:** Main entry point, CLI interface, and orchestration of `watchdog`.

**Steps:**
1.  **Imports:** `argparse`, `watchdog`, `config`, `subprocess`, `threading`, `time`, `logging`.
2.  **Class: `CommandDebounce`** (Private/Inner class or functional wrapper)
    *   Initialize `timer` attribute.
    *   Method `reset(duration)`: Cancel previous timer (using `timer.cancel()`) and schedule new one.
    *   Method `execute()`: Call the command.
3.  **Class: `FileWatcher`**
    *   Initialize with `watch_path` and `debounce_ms`.
    *   Initialize `debounce` object.
    *   Initialize `EventObserver` from `watchdog` (configured with `poll_events` or `inotify` logic).
4.  **Event Handler: `on_event(event)`**
    *   Triggered by `Observer`.
5.  **Filtration Logic (inside `on_event`)**:
    *   Extract `path` from event.
    *   Check against `config` patterns.
    *   If passed -> `debounce.reset(300ms)` (or config value).
    *   If `debounce` timeout fires -> `execute_command()`.
6.  **Command Execution (inside `execute`)**:
    *   Log "Running command: {cmd}".
    *   Use `subprocess.run([cmd], shell=True, capture_output=True, text=True)`.
    *   Output `stderr` if `returncode != 0`.
    *   Catch `Exception` (e.g., command not found) and log as error.
    *   Ensure `stdout` is logged if non-empty (for verbose mode).
7.  **Entry Point: `main()`**
    *   Define CLI args:
        *   `--config`: Path to config file (Optional, defaults to `watcher.yaml`).
        *   `--path`: Directory to watch (Optional, defaults to `config`).
    *   Parse args.
    *   Load config using `config.load()`.
    *   Instantiate `FileWatcher`.
    *   Start Observer loop (daemon=True=False is usually better for the process to exist).
    *   Print startup message.
    *   Wait for interrupts (Ctrl+C).
8.  **Argument Parsing:**
    *   Use `argparse`.
    *   Add `--version` and `--help`.
9.  **Logging Setup:**
    *   Configure `logging.basicConfig` with level `INFO` or `DEBUG`.
10. **Signal Handling:**
    *   Catch `KeyboardInterrupt` to stop the observer loop gracefully (`observer.stop()`).

---

## 5. Implementation Detail: `watcher.yaml` (Example Configuration)

**Purpose:** Demonstrate the expected YAML structure for the user.

**Content Structure:**
*   `watched_dir`: Relative or absolute path (e.g., `.`)
*   `command`: The script/command to run (e.g., `pytest --watch=false`).
*   `debounce_ms`: `300`
*   `include_patterns`: `[ "*.py", "*.txt" ]`
*   `exclude_patterns`: `[ "__pycache__", ".git", "test_*.py" ]`
*   `verbose`: `false`

**Reasoning:** 
*   `*` patterns should be handled correctly.
*   The example should point to files that would logically exist in a Python project.

---

## 6. Implementation Detail: `test_watcher.py`

**Purpose:** Validate functionality without requiring a real running daemon indefinitely.

**Steps:**
1.  **Imports:** `pytest`, `watchdog`, `unittest.mock` (or `unittest.mock`).
2.  **Test: `test_config_loading`**:
    *   Create a temporary file with sample YAML content.
    *   Call `config.load()`.
    *   Assert expected fields are present.
    *   Assert invalid YAML raises error.
3.  **Test: `test_pattern_matching`**:
    *   Hardcode a path string.
    *   Verify `fnmatch` logic works as expected against `*.py` etc.
4.  **Test: `test_debounce`**:
    *   Create a mock `Debounce` class or mock the actual `watchdog` `run_callback`.
    *   Simulate Event 1 (Start Timer).
    *   Simulate Event 2 (before 300ms) -> Ensure Command Not Called.
    *   Simulate Timer Expiry -> Ensure Command Called.
5.  **Test: `test_command_execution`**:
    *   Mock `subprocess.run`.
    *   Verify command string passed to subprocess matches input.
    *   Verify error logs are written when `returncode != 0`.
6.  **Integration Test (Optional but good):**
    *   Create a temporary directory using `tempfile`.
    *   Write a file.
    *   Start watcher as a subprocess or thread.
    *   Poll file system.
    *   Wait for command output.
    *   Verify command was likely called.

---

## 7. Error Handling & Edge Cases

*   **Scenario:** Directory no longer exists upon start.
    *   *Plan:* `observer` will raise `PathError` (or `NotAWatched`). Catch this in CLI `try/except` block and exit with "directory not found".
*   **Scenario:** Debounce fires, command runs and blocks for 30 seconds.
    *   *Plan:* The `subprocess` call is synchronous. If the command hangs indefinitely, the watcher thread will hang. *Solution:* Add a `timeout` argument to `subprocess.run` (e.g., 250ms) or log a warning. Since it's a watcher, blocking is usually expected if the build/test takes time, but we must prevent the process from dying.
    *   *Correction:* The `watchdog` thread *runs* the event. If event processing blocks, the observer loop might hang (if it's not multi-threaded). Standard `Observer` is single-threaded. Blocking IO on the event handler thread kills the watcher.
    *   *Refinement:* We must ensure `subprocess.run` returns relatively quickly. We will not suppress command output, but if the command hangs for > 10 seconds, we might interrupt? No, standard behavior is block. The user command *should* be fast. We will not add a `timeout` constraint unless explicitly requested, but will assume the command completes in `< 5s` to allow the user to debug.
*   **Scenario:** Python syntax in command.
    *   *Plan:* The command is assumed to be a shell command (bash). If they want python script execution, they write `python3 path/to/script.py`.

---

## 8. Final Execution Checklist

1.  **Setup Virtual Environment** (implied).
2.  **Create `requirements.txt`**: Add `watchdog`, `pyyaml`, `pytest`.
3.  **Write `config.py`**: Verify YAML parsing logic.
4.  **Write `watcher.py`**: 
    *   Ensure imports are correct.
    *   Verify `os` path handling (Linux specific paths).
    *   Test CLI help output.
5.  **Write `watcher.yaml`**: Ensure syntax is valid.
6.  **Write `test_watcher.py`**: Run `pytest`.
7.  **Review**: Check that `300ms` default is in config and `watchdog` is imported correctly.
8.  **Documentation**: Add a shebang line to `watcher.py` (`#!/usr/bin/env python3`) to make it executable.

This plan ensures all deliverables are created with the specified constraints (watchdog, yaml, debounce, patterns) and robust error handling.

<Plan End>
