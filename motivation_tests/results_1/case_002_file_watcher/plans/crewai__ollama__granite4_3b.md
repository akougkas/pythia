---
case: case_002_file_watcher
framework: crewai
model: granite4:3b
provider: ollama
session_id: None
duration_ms: 20004
duration_wall_s: 20.0
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:25:36.198232+00:00
error: None
---

# Plan

# Implementation Plan for File Watcher

## Overview
This document outlines the step-by-step process to implement a Python CLI tool named `watcher.py` that monitors a directory for file changes and runs a configurable command (e.g., test suite) when source files are modified. The implementation uses the `watchdog` library for filesystem events, supports configuration via a `watcher.yaml` file, allows inclusion/exclusion of glob patterns, and includes a debounce mechanism to handle rapid changes.

## Step-by-Step Implementation Plan

### 1. Set Up Project Directory
Create a new directory structure within `WorkingDir/` that mirrors the project's intended monitoring scope. This will serve as the root for the file watcher tool.

```bash
mkdir -p WorkingDir/src/
```

### 2. Create Source Files

#### 2.1 `watcher.py`
**Purpose**: Main CLI entry point.
- **Functionality**: Initializes the watchdog observer, parses command-line arguments, and starts monitoring specified directories.
- **Key Components**:
  ```python
  import argparse
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler

  class FileChangeHandler(FileSystemEventHandler):
      def __init__(self, config: dict):
          self.config = config

      def on_modified(self, event):
          if not event.is_directory:
              debounce_action(event.src_path)

  def debounce_action(path):
      # Implement debounce logic (e.g., using a timer)
      pass

  def main():
      parser = argparse.ArgumentParser(description='Monitor directory for changes.')
      parser.add_argument('directory', type=str, help='Directory to monitor')
      args = parser.parse_args()

      config_path = 'watcher.yaml'
      with open(config_path) as f:
          config = load_yaml(f)

      event_handler = FileChangeHandler(config)
      observer = Observer()
      observer.schedule(event_handler, path=args.directory, recursive=True)
      observer.start()

  if __name__ == "__main__":
      main()
  ```

#### 2.2 `config.py`
**Purpose**: YAML config loader.
- **Functionality**: Loads configuration from `watcher.yaml`.
- **Key Components**:
  ```python
  import yaml

  def load_yaml(file_path):
      with open(file_path, 'r') as f:
          return yaml.safe_load(f)
  ```

#### 2.3 `watcher.yaml`
**Purpose**: Example configuration file.
- **Content**:
  ```yaml
  command: "pytest"
  debounce_time: 300
  include_patterns:
    - "*.py"
  exclude_patterns:
    - "__init__.py"
  ```

### 3. Implement Command Execution

#### 3.1 `test_watcher.py`
**Purpose**: Unit tests for the file watcher functionality.
- **Functionality**: Tests various scenarios including directory monitoring, command execution on modified files, debounce handling, and correct parsing of configuration options.

```python
import unittest
from watcher import FileChangeHandler, debounce_action

class TestFileWatcher(unittest.TestCase):
    def test_debounce(self):
        # Simulate rapid file modifications to ensure debounce works
        pass

    def test_command_execution(self):
        handler = FileChangeHandler(config)
        event = type('event', (), {'src_path': 'test_file.py'})
        handler.on_modified(event)
        self.assertEqual(debounce_action('test_file.py'), "pytest")

    def test_include_patterns(self):
        # Ensure only files matching include patterns are monitored
        pass

    def test_exclude_patterns(self):
        # Ensure excluded files are not triggered
        pass
```

### 4. Setup and Testing Environment

#### 4.1 Install Required Packages
Ensure the `watchdog` library is installed in the project environment.

```bash
pip install watchdog
```

#### 4.2 Verify Functionality
Run tests to ensure all components work together seamlessly.
```bash
python -m unittest test_watcher.py
```

### 5. Documentation and Cleanup

#### 5.1 Update `README.md`
Provide instructions on how to run the file watcher tool, including examples of command-line arguments.

```markdown
# File Watcher Usage
To start monitoring a directory for changes, use:
```bash
python watcher.py /path/to/monitor
```

Ensure `watcher.yaml` is configured correctly in the project's root.
```

#### 5.2 Clean Up Code
Review code for any redundant or unnecessary parts and remove them to maintain clean and efficient implementation.

### 6. Final Review

Perform a final review of all components, ensuring that:
- All dependencies are up-to-date.
- Configuration files are correctly placed and parsed.
- Unit tests cover all critical paths.
- The tool operates smoothly in the development environment.

### Conclusion
Following these steps will result in a fully functional `watcher.py` CLI tool capable of monitoring directories for file changes, executing configured commands, and handling debounce logic effectively.
