---
case: case_002_file_watcher
framework: langgraph
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 33822
duration_wall_s: 33.8
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T22:47:03.932698+00:00
error: None
---

# Plan

# Implementation Plan: Case 002 File Watcher

## 1. Assumptions & Scope Clarification
Before implementation, the following assumptions are made to resolve ambiguities in the objective:
*   **Command Execution:** The command specified in the config will be executed via `subprocess`. For safety, `shell=False` is preferred, but `shell=True` is allowed if the command is a simple string. If `shell=True`, input is sanitized.
*   **Debounce Mechanism:** A simple timestamp-based debounce will be used. If a new event occurs within 300ms of the last event, the command is not re-triggered. A `threading.Lock` will be used to ensure thread safety during the debounce check.
*   **File Filtering:** `include` and `exclude` patterns will be applied to the file path relative to the watched root. If a file matches an `exclude` pattern, it is ignored. If it matches `include`, it is watched. If neither is specified, all files are watched.
*   **Error Handling:** If the configured command fails (non-zero exit code), the watcher will log the error to `stderr` but continue monitoring. If the watcher process is interrupted (Ctrl+C), it will stop gracefully.
*   **Working Directory Context:** The tool will be developed in `/home/jye/publications/cases/case_002_file_watcher/`, but the `watcher.yaml` will define the *target* directory to monitor (e.g., `./WorkingDir`).
*   **Dependencies:** `watchdog` (for filesystem events), `pyyaml` (for config), `argparse` (standard library).

## 2. Project Structure
The following file structure will be created within the project root:

```text
case_002_file_watcher/
├── watcher.py          # Main CLI entry point
├── config.py           # YAML config loader & validation
├── watcher.yaml        # Example configuration file
├── test_watcher.py     # Unit tests
└── requirements.txt    # (Optional) Python dependencies
```

## 3. Implementation Steps

### Step 1: Environment Setup & Dependencies
1.  **Initialize Project:** Create the directory structure.
2.  **Install Dependencies:** Ensure `watchdog` and `pyyaml` are installed (`pip install watchdog pyyaml`).
3.  **Define Constants:** Create constants for `DEBOUNCE_DELAY` (300ms) and `LOG_FORMAT`.

### Step 2: Configuration Module (`config.py`)
1.  **Define Schema:** Define the expected structure for `watcher.yaml`:
    *   `root_path`: Absolute or relative path to the directory to watch.
    *   `command`: The shell command to run on change.
    *   `debounce_ms`: Integer (default 300).
    *   `include_patterns`: List of glob patterns (e.g., `*.py`, `*.js`).
    *   `exclude_patterns`: List of glob patterns (e.g., `__pycache__/*`, `.git/*`).
2.  **Implement `load_config(path)` Function:**
    *   Read the YAML file.
    *   Resolve `root_path` to an absolute path.
    *   Validate that `root_path` exists and is a directory.
    *   Validate that `command` is a non-empty string.
3.  **Implement `get_filtered_paths(root_path, patterns)` Function:**
    *   Helper to expand glob patterns against the root path to determine which files should trigger events.
    *   Logic: If a file matches an exclude pattern, skip it. If include patterns are defined, check against them.

### Step 3: Core Watcher Logic (Embedded in `watcher.py`)
1.  **Import `watchdog`:** Import `FileSystemEventHandler`, `Observer`, `Path`.
2.  **Create `EventHandler` Class:**
    *   Initialize with `debounce_delay`, `command`, `config`.
    *   Implement `on_any_event(event)`:
        *   Check if the event is a file (ignore directory creation/deletion unless specified).
        *   Check if the file matches include/exclude logic.
        *   Check debounce timer: Record `time.time()`. If `now - last_time > debounce_delay`, proceed.
        *   Execute command using `subprocess.run`.
        *   Capture exit code and log success/failure.
        *   Update `last_time`.
3.  **Create `Observer` Wrapper:**
    *   Instantiate `Observer`.
    *   Attach `EventHandler`.
    *   Start observing the `root_path`.
    *   Implement `start()` and `stop()` methods.
    *   Handle `SIGINT`/`SIGTERM` to call `stop()` and exit cleanly.

### Step 4: CLI Entry Point (`watcher.py`)
1.  **Setup `argparse`:**
    *   Argument: `--config` (path to `watcher.yaml`, default `./watcher.yaml`).
    *   Argument: `--verbose` (optional, to increase log level).
2.  **Main Function:**
    *   Parse arguments.
    *   Load config using `config.py`.
    *   Instantiate the watcher.
    *   Print startup message (e.g., "Watching directory: ...").
    *   Enter the main loop (keep running until interrupted).
    *   Handle exceptions (e.g., `FileNotFoundError`, `PermissionError`) and exit with code 1.
3.  **Logging:** Use Python's `logging` module to output events to `stdout`/`stderr`.

### Step 5: Configuration File (`watcher.yaml`)
1.  **Create Example Content:**
    *   Set `root_path` to `./WorkingDir`.
    *   Set `command` to `pytest`.
    *   Set `debounce_ms` to `300`.
    *   Set `include_patterns` to `['*.py', '*.md']`.
    *   Set `exclude_patterns` to `['__pycache__/*', '.git/*', 'venv/*']`.
2.  **Document Fields:** Add comments explaining each field.

### Step 6: Testing Strategy (`test_watcher.py`)
1.  **Setup Test Environment:** Create a temporary directory structure for testing.
2.  **Test Config Loading:**
    *   Test valid YAML parsing.
    *   Test validation (missing path, empty command).
3.  **Test Pattern Matching:**
    *   Mock file paths and verify `include`/`exclude` logic returns correct boolean results.
4.  **Test Debounce Logic:**
    *   Mock `time.time()` to simulate rapid events.
    *   Verify that the command is only triggered after the delay.
5.  **Test CLI Entry Point:**
    *   Mock the `Observer` to prevent actual filesystem watching during unit tests.
    *   Verify `argparse` arguments are parsed correctly.
6.  **Run Tests:** Execute `pytest` or `unittest` on `test_watcher.py`.

### Step 7: Integration & Validation
1.  **Manual Verification:**
    *   Run `watcher.py` with `--config watcher.yaml`.
    *   Modify a file in `WorkingDir` (e.g., touch a `.py` file).
    *   Verify the command (e.g., `pytest`) is executed once after 300ms.
    *   Verify that modifying a non-matching file (e.g., `.txt`) does not trigger the command.
2.  **Cleanup:** Ensure the watcher stops and files are not left in a zombie state.

## 4. Deliverable Checklist
- [ ] `watcher.py`: CLI entry point with signal handling.
- [ ] `config.py`: YAML loader with validation.
- [ ] `watcher.yaml`: Example configuration with comments.
- [ ] `test_watcher.py`: Unit tests covering logic and config.
- [ ] `requirements.txt`: Dependencies listed.

## 5. Risk Mitigation
*   **Risk:** `watchdog` might consume too many resources if the directory has thousands of files.
    *   *Mitigation:* Rely on `watchdog`'s default polling or inotify (Linux) efficiency. Add a note in `watcher.yaml` to limit watched extensions if performance is an issue.
*   **Risk:** Command execution might hang.
    *   *Mitigation:* Set `timeout` in `subprocess.run` (e.g., 60 seconds) to prevent the watcher from freezing if the test suite hangs.
*   **Risk:** Race conditions on debounce.
    *   *Mitigation:* Use `threading.Lock` around the `last_change_time` update and check.
