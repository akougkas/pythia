---
case: case_002_file_watcher
framework: crewai
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 33393
duration_wall_s: 33.4
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:25:03.608049+00:00
error: None
---

# Plan

# Implementation Plan: Case 002 File Watcher Tool

## 1. Project Context and Technical Assumptions

### 1.1 Assumptions
1.  **Python Version:** Python 3.8 or higher (assuming `typing` and `pathlib` compatibility).
2.  **FS Library:** `watchdog` version 3.x is utilized.
3.  **Logging:** Python standard `logging` module configured with `logging.basicConfig`.
4.  **Config Loader:** `PyYAML` for parsing `watcher.yaml`.
5.  **Execution:** `subprocess` module for command execution.
6.  **Project Root:** `/home/jye/publications/cases/case_002_file_watcher/`
7.  **Watch Target Directory:** `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/` (or configurable via CLI).
8.  **Debounce Strategy:** Per-file timestamp comparison within a thread-safe context (using `threading.Event` or lock) to prevent rapid-fire command execution.
9.  **Error Handling:** `try/except` blocks surround `FileEvent` dispatch and `subprocess.run` to ensure CLI tool exits cleanly without crashing on single file access failures.

### 1.2 Dependency Management
*   **Core Packages:** `watchdog`, `PyYAML`, `argparse`, `subprocess`, `pathlib`, `logging`, `threading`.
*   **Installation Plan:**
    *   Create `requirements.txt` listing `watchdog>=3.0.0`, `PyYAML>=6.0`, `pytest>=7.0`.
    *   Command to install: `pip install -r requirements.txt`.

## 2. Directory Structure

The solution will be structured within `/home/jye/publications/cases/case_002_file_watcher/`.

```text
/home/jye/publications/cases/case_002_file_watcher/
│
├── watcher.py        # Main CLI entry point and logic
├── config.py         # YAML configuration loader
├── watcher.yaml      # Default configuration example
├── test_watcher.py   # Unit test suite
├── requirements.txt  # Python dependencies
└── WorkingDir/       # Target directory for monitoring (Example structure)
    ├── src/
    │   ├── __init__.py
    │   └── main.py
    └── test_suites/
        └── test_main.py
```

## 3. Implementation Steps

### Step 1: Define Configuration Schema (`config.py`)

**Objective:** Create a robust function to read `watcher.yaml` and return a dictionary of configuration values.

**File Path:** `/home/jye/publications/cases/case_002_file_watcher/config.py`

**Technical Decisions:**
*   **Loader:** `yaml.safe_load` for security against YAML syntax injection.
*   **Default Values:** Provide defaults if keys are missing in the YAML file (e.g., default debounce of 300ms).
*   **Error Handling:** Raise a `KeyError` or specific `ConfigError` if `command` or `target_dir` is missing.

**Function Signatures:**
```python
def load_config(config_path: str) -> dict:
    """
    Loads configuration from YAML file and returns a structured dictionary.
    
    Parameters:
    - config_path (str): Path to watcher.yaml
    
    Returns:
    - dict: Configuration object with keys: root, command, include, exclude
    
    Raises:
    - ConfigError: If YAML parsing or key validation fails.
    """
    ...
```

**Implementation Details:**
*   Import `os`, `pathlib`, `yaml`.
*   Define `ConfigError` class inheriting from `RuntimeError`.
*   Ensure `target_dir` is an absolute path relative to the script location if not provided.

---

### Step 2: Core File Watcher Logic (`watcher.py`)

**Objective:** Create the main CLI entry point and logic to handle file events and execute commands.

**File Path:** `/home/jye/publications/cases/case_002_file_watcher/watcher.py`

**Technical Decisions:**
*   **Observer:** Use `watchdog.observers.FileSystemObserver` on top of `PollingObserver` (default) or `InotifyOnlyObserver`/`FseventsObserver` depending on target OS. Assuming generic `PollingObserver` or OS-specific `FileSystemObserver` logic abstracted via `watcher.watch`.
*   **Debounce:** Use a dictionary `last_event_time = { 'file_path': timestamp }` protected by a `Lock`.
*   **Glob Matching:** Use `fnmatch.fnmatch` to match against `include` and `exclude` patterns.
*   **Command Execution:** Use `subprocess.run` with `stdout=subprocess.PIPE`, `stderr=subprocess.PIPE`.

**Function Signatures:**
```python
def main() -> None:
    """
    Main entry point: parses arguments, loads config, starts watcher.
    
    Parameters:
    - None
    
    Returns:
    - None
    """
    args = parse_args()
    config = load_config(args.config_path)
    start_watcher(config)

def parse_args() -> argparse.Namespace:
    """
    Defines CLI argument parsing.
    
    Parameters:
    - None
    
    Returns:
    - argparse.Namespace with attributes: config_path, target_dir, command
    """
    ...

def start_watcher(config: dict) -> None:
    """
    Initializes the watchdog observer and starts monitoring.
    
    Parameters:
    - config (dict): Parsed configuration dictionary
    
    Returns:
    - None
    """
    ...
```

**Implementation Details:**
*   **Event Handler Class:** Create `FileEventHandler` subclassing `watchdog.watch()` method.
*   **Method `_on_created` / `_on_modified`:**
    *   Check if event path matches `include` patterns.
    *   Check if event path matches `exclude` patterns.
    *   Implement Debounce: `if time.time() - self.last_event_time.get(file_path, 0) < self.debounce_ms:` return.
*   **CLI Arguments:** Add `--config`, `--target`, `--command` flags.

---

### Step 3: Create Sample Configuration (`watcher.yaml`)

**Objective:** Provide a valid example configuration that demonstrates the tool's capabilities.

**File Path:** `/home/jye/publications/cases/case_002_file_watcher/watcher.yaml`

**Content Structure:**
*   **Target Directory:** Default to `./WorkingDir` (relative to script) or absolute if specified.
*   **Command:** `pytest` or `python -m test_runner`.
*   **Include:** `*.py`.
*   **Exclude:** `__pycache__/*`, `*.pyc`, `node_modules/*`, `logs/*`.
*   **Debounce:** `300`.

---

### Step 4: Write Unit Tests (`test_watcher.py`)

**Objective:** Validate configuration loading and debounce logic.

**File Path:** `/home/jye/publications/cases/case_002_file_watcher/test_watcher.py`

**Technical Decisions:**
*   **Testing Framework:** Use `pytest` or `unittest`.
*   **Mocking:** Mock `watchdog.FileSystemObserver` and `config.load_config` if testing complex scenarios.
*   **Debounce Simulation:** Use `time.sleep` to simulate rapid file access events.

**Function Signatures (Test Functions):**
```python
def test_load_config_valid(yaml_content):
    """
    Tests that valid YAML loads correctly.
    """
    ...

def test_config_missing_required_key():
    """
    Tests that missing 'command' raises error.
    """
    ...

def test_debounce_ignore_event():
    """
    Tests that rapid events within 300ms are ignored.
    """
    ...
```

**Implementation Details:**
*   Import `pytest`.
*   Use `assert` statements.
*   Use `os.path.exists` mocks for `pathlib` if needed.
*   Include a test that verifies `include` and `exclude` glob logic.

---

### Step 5: Assembly and Validation

**Objective:** Integrate files and verify the CLI tool works as expected.

**Technical Decisions:**
*   **Entry Point:** Ensure `watcher.py` contains the `if __name__ == "__main__"` block.
*   **Permissions:** Ensure directories are readable/writable.
*   **Path Handling:** Ensure relative paths in `config` are resolved to absolute paths before passing to `watchdog`.

**Steps:**
1.  Create `requirements.txt`.
2.  Create the directory structure (`config.py`, `watcher.py`, `test_watcher.py`, `watcher.yaml`, `WorkingDir/`).
3.  Run `pip install -r requirements.txt`.
4.  Run `pytest test_watcher.py -v` to verify unit tests.
5.  Run `python watcher.py --help` to verify CLI help.
6.  Create a file in `WorkingDir/` manually and observe if a command is triggered (manual validation).

## 4. Deliverables Checklist

- [ ] `watcher.py`: Contains `main()`, `parse_args()`, `start_watcher()`, and `FileEventHandler`.
- [ ] `config.py`: Contains `load_config()` and validation logic.
- [ ] `watcher.yaml`: Contains example `target`, `command`, `include`, `exclude`, `debounce`.
- [ ] `test_watcher.py`: Contains tests for config loading and debounce logic.
- [ ] `requirements.txt`: Lists `watchdog`, `PyYAML`, `pytest`.

## 5. Risk Mitigation

| Risk | Mitigation |
| :--- | :--- |
| **False Positives (Debounce)** | Ensure debounce logic resets correctly if the same file is modified twice in a short window. If the *same* file is modified, `last_event_time` should not be reset for that file immediately (debounce is per-file). |
| **Path Traversal** | Validate that `target_dir` is within the allowed project boundary. Reject paths that resolve outside the root. |
| **OS Incompatibility** | `watchdog` abstracts OS events (`PollingObserver` for Linux/Mac, `PollingObserver` default). The plan assumes a Linux environment but notes `PollingObserver` works cross-platform. |
| **Deadlock** | Ensure the main thread does not block while `subprocess.run` executes the command (use background thread for command execution if the watch must be persistent). **Decision:** Background the subprocess call to avoid blocking the watch thread on `polling`. |
