---
case: case_002_file_watcher
framework: langgraph
model: gpt-4o
provider: github_models
session_id: None
duration_ms: 12696
duration_wall_s: 12.7
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:52:31.089236+00:00
error: None
---

# Plan

# Implementation Plan for Case 002: File Watcher

Below is a detailed, step-by-step implementation plan to create the Python CLI tool as described in the objective.

---

## Assumptions

1. The `watchdog` library is already installed or will be installed as part of the setup process.
2. The `watcher.yaml` configuration file will be located in the same directory as `watcher.py` by default.
3. The tool will monitor the working directory (`WorkingDir`) unless otherwise specified in the configuration file.
4. The debounce time (300ms) will be configurable via the `watcher.yaml` file.
5. The tool will support Python 3.7+.

---

## Step-by-Step Plan

### 1. **Project Structure**
Create the following file structure:
```
/home/jye/publications/cases/case_002_file_watcher/
├── WorkingDir/
├── watcher.py
├── config.py
├── watcher.yaml
├── test_watcher.py
```

---

### 2. **Define `watcher.yaml` Configuration File**
Create an example `watcher.yaml` file with the following structure:
```yaml
# watcher.yaml
directory: ./WorkingDir  # Directory to monitor
command: pytest          # Command to execute on file changes
include_patterns:        # Glob patterns to include
  - "*.py"
exclude_patterns:        # Glob patterns to exclude
  - "*.tmp"
debounce: 300            # Debounce time in milliseconds
```

---

### 3. **Implement `config.py`**
Write a Python module to load and validate the `watcher.yaml` configuration file.

#### Steps:
1. Use the `yaml` library to parse the configuration file.
2. Validate required fields (`directory`, `command`, etc.).
3. Provide default values for optional fields (e.g., `debounce`).
4. Return the configuration as a dictionary.

#### Code:
```python
import yaml
import os

DEFAULT_CONFIG = {
    "directory": "./WorkingDir",
    "command": "pytest",
    "include_patterns": ["*.py"],
    "exclude_patterns": ["*.tmp"],
    "debounce": 300,
}

def load_config(config_path="watcher.yaml"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    
    # Merge with defaults
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    
    return config
```

---

### 4. **Implement `watcher.py`**
Write the main CLI entry point to monitor the directory and execute the command on file changes.

#### Steps:
1. Parse the configuration using `config.py`.
2. Use `watchdog` to monitor the directory for file changes.
3. Filter events based on include/exclude glob patterns.
4. Implement a debounce mechanism to prevent rapid execution of the command.
5. Execute the configured command using `subprocess`.

#### Code Outline:
```python
import os
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import load_config
from fnmatch import fnmatch

class WatcherHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.last_run = 0

    def on_any_event(self, event):
        # Check debounce
        now = time.time()
        if now - self.last_run < self.config["debounce"] / 1000:
            return
        
        # Check include/exclude patterns
        if not any(fnmatch(event.src_path, pattern) for pattern in self.config["include_patterns"]):
            return
        if any(fnmatch(event.src_path, pattern) for pattern in self.config["exclude_patterns"]):
            return
        
        # Execute command
        self.last_run = now
        print(f"Change detected: {event.src_path}. Running command...")
        subprocess.run(self.config["command"], shell=True)

def main():
    config = load_config()
    path = config["directory"]
    
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Directory does not exist: {path}")
    
    event_handler = WatcherHandler(config)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    
    print(f"Watching directory: {path}")
    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
```

---

### 5. **Write Unit Tests in `test_watcher.py`**
Create unit tests to validate the functionality of `config.py` and `watcher.py`.

#### Steps:
1. Use the `unittest` library for testing.
2. Mock file system events using `unittest.mock`.
3. Test `load_config` for various scenarios (e.g., missing fields, invalid files).
4. Test `WatcherHandler` for correct filtering and debounce behavior.

#### Code Outline:
```python
import unittest
from unittest.mock import patch, MagicMock
from config import load_config
from watcher import WatcherHandler

class TestConfig(unittest.TestCase):
    def test_load_config_defaults(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data="{}")):
            config = load_config()
            self.assertEqual(config["directory"], "./WorkingDir")
            self.assertEqual(config["command"], "pytest")
            self.assertEqual(config["debounce"], 300)

    def test_load_config_custom(self):
        yaml_data = """
        directory: ./src
        command: make test
        debounce: 500
        """
        with patch("builtins.open", unittest.mock.mock_open(read_data=yaml_data)):
            config = load_config()
            self.assertEqual(config["directory"], "./src")
            self.assertEqual(config["command"], "make test")
            self.assertEqual(config["debounce"], 500)

class TestWatcherHandler(unittest.TestCase):
    def test_event_handling(self):
        config = {
            "directory": "./WorkingDir",
            "command": "pytest",
            "include_patterns": ["*.py"],
            "exclude_patterns": ["*.tmp"],
            "debounce": 300,
        }
        handler = WatcherHandler(config)
        handler.last_run = 0

        mock_event = MagicMock()
        mock_event.src_path = "test.py"
        
        with patch("subprocess.run") as mock_run:
            handler.on_any_event(mock_event)
            mock_run.assert_called_once_with("pytest", shell=True)

if __name__ == "__main__":
    unittest.main()
```

---

### 6. **Test the Tool**
1. Run `test_watcher.py` to ensure all tests pass.
2. Manually test `watcher.py` by creating/modifying files in `WorkingDir` and verifying that the command runs as expected.

---

### 7. **Document Usage**
Add a usage section to the top of `watcher.py`:
```python
"""
Usage:
    python watcher.py

Description:
    Monitors a directory for file changes and runs a configured command.

Configuration:
    Edit the watcher.yaml file to specify the directory, command, and patterns.
"""
```

---

### 8. **Deliverables**
1. `watcher.py` — CLI tool.
2. `config.py` — YAML configuration loader.
3. `watcher.yaml` — Example configuration file.
4. `test_watcher.py` — Unit tests.

---

This plan provides a complete roadmap to implement the File Watcher tool.
