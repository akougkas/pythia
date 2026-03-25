---
case: case_002_file_watcher
framework: aider
model: granite4:3b
provider: ollama
session_id: None
duration_ms: 6800
duration_wall_s: 6.8
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T15:28:48.617906+00:00
error: None
---

# Plan

### Implementation Plan for File Watcher

#### 1. Set Up Project Structure

- **Create the main script**: `watcher.py`
- **Create a configuration module**: `config.py`
- **Create an example YAML config file**: `watcher.yaml`
- **Create unit tests**: `test_watcher.py`

#### 2. Implement Configuration Loading (`config.py`)

1. **Import necessary libraries**:
   ```python
   import yaml
   from pathlib import Path
   ```

2. **Define a function to load configuration**:
   ```python
   def load_config(config_path: str) -> dict:
       """
       Load the YAML configuration file.

       Args:
           config_path (str): Path to the watcher.yaml file.

       Returns:
           dict: Configuration dictionary.
       """
       config_file = Path(config_path)
       if not config_file.is_file():
           raise FileNotFoundError(f"Configuration file {config_file} does not exist.")
       
       with open(config_file, 'r') as f:
           return yaml.safe_load(f)
   ```

#### 3. Implement File Watching Logic (`watcher.py`)

1. **Import necessary libraries**:
   ```python
   import time
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler
   ```

2. **Define a handler class for file changes**:
   ```python
   class WatcherHandler(FileSystemEventHandler):
       def __init__(self, config: dict):
           """
           Initialize the event handler with configuration.

           Args:
               config (dict): Configuration dictionary.
           """
           self.config = config

       def on_modified(self, event):
           """
           Trigger when a file is modified.

           Args:
               event (FileSystemEvent): Event object containing information about the modification.
           """
           # Check if the event path matches any include patterns
           for pattern in self.config.get('include', []):
               if any(event.src_path.endswith(pattern) for pattern in glob.glob(pattern)):
                   # Debounce logic
                   time.sleep(0.3)
                   run_command()
                   break

       def on_created(self, event):
           """
           Trigger when a file is created.

           Args:
               event (FileSystemEvent): Event object containing information about the creation.
           """
           # Check if the event path matches any include patterns
           for pattern in self.config.get('include', []):
               if any(event.src_path.endswith(pattern) for pattern in glob.glob(pattern)):
                   # Debounce logic
                   time.sleep(0.3)
                   run_command()
                   break

       def on_deleted(self, event):
           """
           Trigger when a file is deleted.

           Args:
               event (FileSystemEvent): Event object containing information about the deletion.
           """
           pass  # No action needed for deletion in this implementation
   ```

3. **Define a function to run the configured command**:
   ```python
   def run_command():
       """
       Execute the configured command, e.g., test suite.
       """
       config = load_config('watcher.yaml')
       command = config.get('command', 'pytest')
       subprocess.run(command, shell=True)
   ```

4. **Set up the main script logic**:
   ```python
   def main():
       config_path = 'watcher.yaml'
       config = load_config(config_path)

       event_handler = WatcherHandler(config)
       observer = Observer()
       paths_to_watch = [config.get('path', '/home/jye/publications/cases/case_002_file_watcher/WorkingDir')]

       for path in paths_to_watch:
           observer.schedule(event_handler, path, recursive=True)

       observer.start()
       print("Watching started. Press Ctrl+C to stop.")

       try:
           while True:
               time.sleep(1)
       except KeyboardInterrupt:
           observer.stop()

       observer.join()
   ```

#### 4. Create Example Configuration (`watcher.yaml`)

```yaml
path: /home/jye/publications/cases/case_002_file_watcher/WorkingDir
include:
  - '*.py'
exclude:
  - 'tests/**'
command: pytest
```

#### 5. Write Unit Tests (`test_watcher.py`)

1. **Import necessary libraries**:
   ```python
   import unittest
   from watcher import load_config, WatcherHandler, main
   ```

2. **Define test cases for configuration loading and event handling**:
   ```python
   class TestWatcher(unittest.TestCase):
       def test_load_config(self):
           config = load_config('watcher.yaml')
           self.assertIsInstance(config, dict)
           self.assertIn('path', config)
           self.assertIn('include', config)

       def test_on_modified(self):
           # Mock the event and command execution
           pass

       def test_main(self):
           # Verify that the main function runs without errors
           main()
   ```

#### 6. Run Unit Tests

- Execute `test_watcher.py` to ensure all tests pass.

### Summary

This plan outlines the steps needed to create a Python CLI tool for monitoring directory changes and executing commands based on those changes using the `watchdog` library. The implementation includes configuration loading, event handling with debounce logic, and unit testing to verify functionality.
