---
case: case_002_file_watcher
framework: aider
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 24893
duration_wall_s: 24.9
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T15:28:23.724310+00:00
error: None
---

# Plan

### Implementation Plan: Case 002 File Watcher

**Assumptions & Constraints:**
1.  **Dependencies:** `watchdog` (>= 3.0), `pyyaml`, `argparse`, `subprocess`.
2.  **Default Command:** `pytest` (assumed to be installed in the environment).
3.  **Default Target Directory:** `WorkingDir` (as per the provided path).
4.  **Debounce Logic:** Reset timer on any file event (create, modify, delete).
5.  **Command Execution:** Run in a separate thread/process to avoid blocking the watcher loop.
6.  **Error Handling:** Log errors to `stderr` but do not terminate the watcher process.
7.  **CLI Flags:** `--config` (path to YAML), `--target-dir` (optional, defaults to `WorkingDir`).

---

### Step-by-Step Implementation Plan

#### Phase 1: Project Structure & Dependencies
1.  **Initialize Project:** Create the directory structure under `/home/jye/publications/cases/case_002_file_watcher/`.
2.  **Dependencies:** Ensure `requirements.txt` includes `watchdog`, `pyyaml`, `pytest`.
3.  **Working Directory:** Ensure the `WorkingDir` exists and contains the files to be monitored (e.g., `src/`).

#### Phase 2: Configuration Loader (`config.py`)
1.  **Create `config.py`:**
    *   Import `yaml`, `os`, `path`.
    *   Define a `Config` dataclass or dictionary structure to hold:
        *   `command`: The shell command to execute (default: `pytest`).
        *   `target_dir`: Directory to watch (default: `WorkingDir`).
        *   `include`: List of glob patterns (default: `['*.py']`).
        *   `exclude`: List of glob patterns (default: `['*.pyc', '__pycache__/*']`).
        *   `debounce_ms`: Integer (default: `300`).
    *   Implement `load_config(config_path)` function:
        *   Read YAML file.
        *   Validate required fields.
        *   Return parsed configuration object.

#### Phase 3: File Watcher Logic (`watcher.py`)
1.  **Create `watcher.py`:**
    *   **Imports:** `watchdog`, `os`, `subprocess`, `time`, `threading`, `config`.
    *   **Class `Debouncer`:**
        *   Initialize with `debounce_ms`.
        *   Method `schedule_run()`: Set a timer. If the timer fires, trigger the command.
        *   Method `reset()`: Clear the timer and set a new one.
    *   **Class `CommandRunner`:**
        *   Method `run_command(cmd)`: Execute the command using `subprocess.run()`. Capture stdout/stderr.
    *   **Class `FileEventHandler`:**
        *   Inherit from `watchdog.observers.FileSystemEventHandler`.
        *   Implement `on_created`, `on_modified`, `on_deleted`.
        *   In each method:
            *   Check if the file matches `include` patterns and does not match `exclude` patterns.
            *   If match, call `debouncer.reset()`.
    *   **Class `FileWatcher`:**
        *   Method `start(config)`:
            *   Initialize `watchdog` observer.
            *   Register `FileEventHandler`.
            *   Start observer thread.
            *   Start `Debouncer` thread.
            *   Start `CommandRunner` thread.
        *   Method `stop()`:
            *   Stop observer thread.
            *   Stop debouncer thread.
            *   Stop command runner thread.

#### Phase 4: CLI Entry Point (`watcher.py` Main)
1.  **Update `watcher.py` Main:**
    *   Add `argparse` setup.
    *   Arguments: `--config`, `--target-dir`.
    *   In `main()`:
        *   Load config using `config.py`.
        *   Instantiate `FileWatcher`.
        *   Call `start(config)`.
        *   Handle `Ctrl+C` to call `stop()`.

#### Phase 5: Unit Tests (`test_watcher.py`)
1.  **Create `test_watcher.py`:**
    *   **Test Config Loading:**
        *   Mock `yaml.safe_load`.
        *   Verify `Config` object is created with correct defaults and values.
    *   **Test Debounce:**
        *   Mock `time.sleep`.
        *   Verify `Debouncer` waits for `debounce_ms` before triggering.
    *   **Test File Events:**
        *   Mock `watchdog` events.
        *   Verify `FileEventHandler` calls `debouncer.reset()` on valid events.
    *   **Test Command Execution:**
        *   Mock `subprocess.run`.
        *   Verify `CommandRunner` executes the correct command.

#### Phase 6: Example Configuration (`watcher.yaml`)
1.  **Create `watcher.yaml`:**
    *   Define `command: pytest`.
    *   Define `target_dir: WorkingDir`.
    *   Define `include: ["*.py"]`.
    *   Define `exclude: ["*.pyc", "__pycache__/*"]`.
    *   Define `debounce_ms: 300`.

---

### Next Steps for Editor Engineer
1.  **Execute Phase 1:** Set up the environment and dependencies.
2.  **Execute Phase 2:** Implement `config.py` to handle YAML parsing.
3.  **Execute Phase 3:** Implement `watcher.py` logic using `watchdog`.
4.  **Execute Phase 4:** Add CLI argument parsing to `watcher.py`.
5.  **Execute Phase 5:** Write unit tests to verify functionality.
6.  **Execute Phase 6:** Create the example configuration file.
