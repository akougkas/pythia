---
case: case_002_file_watcher
framework: gemini_adk
model: gemini-3.1-flash-lite-preview
provider: gemini
session_id: None
duration_ms: 9660
duration_wall_s: 9.7
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:04:27.958260+00:00
error: None
---

# Plan

This implementation plan outlines the development of the `File Watcher` CLI tool.

### Assumptions
1. **Environment:** The tool will be run in a Python 3.8+ environment.
2. **Dependencies:** `watchdog` and `PyYAML` are the required external libraries.
3. **Execution:** The tool will be executed from the command line, and the `watcher.yaml` file will be located in the current working directory by default.
4. **Debouncing:** The debounce mechanism will use a `threading.Timer` to ensure that if multiple events occur within the 300ms window, the command only triggers once after the window expires.

---

### Phase 1: Configuration Schema and Loader
*   **File:** `watcher.yaml`
    *   Define fields: `watch_dir` (string), `command` (string), `include_patterns` (list of strings), `exclude_patterns` (list of strings), `debounce_ms` (integer).
*   **File:** `config.py`
    *   Implement a `load_config(path)` function using `yaml.safe_load`.
    *   Add validation to ensure required fields exist and provide default values (e.g., 300ms for debounce).

### Phase 2: Core Watcher Logic (`watcher.py`)
*   **Event Handler:** Create a class `WatcherHandler(FileSystemEventHandler)` that:
    *   Overrides `on_modified`, `on_created`, and `on_deleted`.
    *   Implements a `should_process(path)` method using `fnmatch` to compare the file path against `include_patterns` and `exclude_patterns`.
    *   Implements a `trigger_command()` method using `subprocess.run` or `subprocess.Popen` to execute the configured command.
*   **Debouncing:** 
    *   Maintain a `threading.Timer` instance.
    *   On every relevant event, cancel the existing timer (if active) and start a new one for the duration of `debounce_ms`.
*   **CLI Entry Point:**
    *   Use `argparse` to accept an optional `--config` flag.
    *   Initialize `watchdog.observers.Observer` to monitor the `watch_dir`.
    *   Add a graceful shutdown mechanism (handling `KeyboardInterrupt`).

### Phase 3: Testing (`test_watcher.py`)
*   **Setup:** Use `pytest` as the testing framework.
*   **Mocking:**
    *   Mock `subprocess.run` to verify that the command is executed without actually running system commands.
    *   Mock the filesystem events to trigger the `WatcherHandler` methods.
*   **Test Cases:**
    *   Verify configuration loading with valid and invalid YAML.
    *   Verify that files matching `include_patterns` trigger the command.
    *   Verify that files matching `exclude_patterns` are ignored.
    *   Verify that rapid file changes only trigger the command once (debounce test).

### Phase 4: Final Assembly
1.  Create `requirements.txt` containing `watchdog` and `PyYAML`.
2.  Ensure `watcher.py` is executable via `python watcher.py`.
3.  Verify the directory structure matches the deliverables.

---

### Implementation Steps Summary
1.  **Step 1:** Create `watcher.yaml` example.
2.  **Step 2:** Develop `config.py` with YAML parsing and validation.
3.  **Step 3:** Develop `watcher.py` with `watchdog` integration, `fnmatch` filtering, and `threading.Timer` debouncing.
4.  **Step 4:** Implement `test_watcher.py` using `unittest.mock` to validate logic without side effects.
5.  **Step 5:** Final review of the code against constraints.
