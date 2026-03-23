---
case: case_002_file_watcher
framework: agents_sdk
model: gpt-4o
provider: github_models
session_id: None
duration_ms: 11753
duration_wall_s: 11.8
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:38:47.118856+00:00
error: None
---

# Plan

### Step-by-Step Implementation Plan

To create the Python CLI tool for monitoring a directory and running commands on file changes, the following detailed steps will be implemented:

---

### **1. File Structure Design**
The project will be organized into a modular structure:
```
/case_002_file_watcher
    ├── watcher.py        # Main CLI entry point
    ├── config.py         # YAML config loader
    ├── watcher.yaml      # Example configuration file
    ├── test_watcher.py   # Unit tests for the functionality
    └── requirements.txt  # Required Python dependencies
```

---

### **2. Implementation Plan**

#### **Step 1: Install Required Python Packages**
- Use `watchdog` for monitoring file changes in the filesystem.
- Use `PyYAML` for parsing the `watcher.yaml` file.
- Add dependencies to `requirements.txt`:
    ```
    watchdog==2.3.0
    PyYAML==6.0
    ```
- This ensures dependency management through `pip install -r requirements.txt`.

#### **Step 2: Create Configuration Loader (`config.py`)**
- Create a Python module (`config.py`) to load and validate the `watcher.yaml` configuration file.
- Key features:
    - Load the YAML file using `yaml.safe_load()`.
    - Validate schema (keys such as `dir`, `include_patterns`, `exclude_patterns`, and `command`).
    - Provide sensible defaults, such as:
        ```yaml
        debounce: 300
        ```
- Example `watcher.yaml` structure to parse:
    ```yaml
    dir: ./src              # Directory to monitor
    include_patterns:       # Files to include (glob patterns)
      - "*.py"
    exclude_patterns:       # Files to exclude (glob patterns)
      - "*_test.py"
    debounce: 300           # Debounce duration in milliseconds
    command: "pytest"       # Command to run upon file changes
    ```

#### **Step 3: Main File Watcher (`watcher.py`)**
- Use `watchdog.observers.Observer` and `watchdog.events.FileSystemEventHandler` to monitor filesystem events.
- Key functionality includes:
    - **Directory Monitoring**: Dynamically watch the directory defined in `watcher.yaml`.
    - **Include/Exclude Patterns**: Filter events based on `include_patterns` and `exclude_patterns` using glob matching.
    - **Debouncing**: Prevent rapid triggering of events within the debounce delay (default: 300ms).
    - **Command Execution**: Run the configured command (`command`) via `subprocess.run()` when changes are detected.
- Flow:
    1. Load configuration from `watcher.yaml`.
    2. Begin monitoring the specified directory.
    3. Filter files for changes using patterns.
    4. Debounce rapid changes with a timer.
    5. Execute the associated command (`pytest`, etc.).
- CLI options:
    - Path to configuration file (`--config`).
    - Verbose logging (`--verbose`).

#### **Step 4: Example Configuration File (`watcher.yaml`)**
- Provide a sample `watcher.yaml` file with baseline configuration:
    ```yaml
    dir: ./src
    include_patterns:
      - "*.py"
    exclude_patterns:
      - "*_test.py"
    debounce: 300
    command: "pytest"
    ```

#### **Step 5: Unit Tests (`test_watcher.py`)**
- Create comprehensive unit tests to validate the functionality of the tool:
    - Test loading of valid/invalid `watcher.yaml` configuration files.
    - Test inclusion/exclusion filters.
    - Test debounce logic (mock filesystem events with rapid changes).
    - Test the command execution logic.
- Use `unittest` or `pytest` as the testing framework.
- Mock dependency functions:
    - `subprocess.run()` to test command execution.
    - File system events via `watchdog.events` using `unittest.mock`.

---

### **3. Detailed File and Function Design**

#### **File: config.py**
Functions:
```python
import yaml

def load_config(file_path):
    try:
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)
        # Validate and set defaults
        config.setdefault("debounce", 300)
        if "dir" not in config:
            raise ValueError("Directory ('dir') key is required.")
        return config
    except Exception as e:
        raise ValueError(f"Failed to load configuration: {e}")
```

---

#### **File: watcher.py**
Functions:
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch
import time
import subprocess
import os
from config import load_config

class WatcherEventHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.last_triggered = 0

    def on_modified(self, event):
        # Check include/exclude patterns
        if not self.is_interested(event.src_path):
            return
        
        # Debounce logic
        now = time.time() * 1000
        if now - self.last_triggered < self.config["debounce"]:
            return
        self.last_triggered = now

        # Execute the command
        subprocess.run(self.config["command"], shell=True)

    def is_interested(self, file_path):
        filename = os.path.basename(file_path)
        # Include files matching patterns
        if any(fnmatch.fnmatch(filename, pattern) for pattern in self.config["include_patterns"]):
            # Exclude files matching patterns
            if not any(fnmatch.fnmatch(filename, pattern) for pattern in self.config["exclude_patterns"]):
                return True
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="File Watcher CLI Tool")
    parser.add_argument("--config", default="watcher.yaml", help="Path to configuration file")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Watch the directory
    observer = Observer()
    event_handler = WatcherEventHandler(config)
    observer.schedule(event_handler, path=config["dir"], recursive=True)
    observer.start()

    print(f"Watching directory: {config['dir']}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

---

#### **File: test_watcher.py**
Example test cases:
```python
import unittest
from unittest.mock import patch, MagicMock
from watcher import WatcherEventHandler
from config import load_config

class TestFileWatcher(unittest.TestCase):
    def test_load_config_valid(self):
        config = load_config("example.yaml")
        self.assertIn("dir", config)
        self.assertEqual(config["debounce"], 300)  # Default debounce

    @patch("subprocess.run")
    def test_command_execution(self, mock_subprocess):
        handler = WatcherEventHandler({"command": "pytest", "include_patterns": ["*.py"], "exclude_patterns": ["*_test.py"], "debounce": 300})
        handler.on_modified(MagicMock(src_path="test.py"))
        mock_subprocess.assert_called_once_with("pytest", shell=True)
```

---

### **4. Final Deliverables**
- Complete implementation of:
    - `watcher.py`
    - `config.py`
    - `watcher.yaml`
    - `test_watcher.py`
- Ensure all functionality conforms to the requirements and behaves as outlined.

--- 

This plan outlines the entire implementation, ensuring the deliverables meet the expected functionality of the case.
