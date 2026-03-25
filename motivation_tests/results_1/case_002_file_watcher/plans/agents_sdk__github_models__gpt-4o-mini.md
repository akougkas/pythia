---
case: case_002_file_watcher
framework: agents_sdk
model: gpt-4o-mini
provider: github_models
session_id: None
duration_ms: 12708
duration_wall_s: 12.7
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:38:33.717978+00:00
error: None
---

# Plan

# Implementation Plan for File Watcher CLI Tool

## Step 1: Initial Setup

1. **Create Project Directory Structure**  
   - Navigate to the working directory: `/home/jye/publications/cases/case_002_file_watcher/WorkingDir`
   - Create a new directory named `file_watcher`:  
     ```bash
     mkdir file_watcher
     cd file_watcher
     ```
   - Inside `file_watcher`, create the necessary files:
     ```bash
     touch watcher.py config.py watcher.yaml test_watcher.py
     ```

## Step 2: Create `watcher.yaml` Configuration File

1. **Structure Configuration File**  
   - Define the structure of `watcher.yaml` to include the following:
     - `directory`: Directory to monitor.
     - `command`: Command to execute on file changes (e.g., run tests).
     - `include_patterns`: Glob patterns for files to include.
     - `exclude_patterns`: Glob patterns for files to exclude.
     - `debounce_time`: Debounce time in milliseconds (default to 300).
   - Example content for `watcher.yaml`:
     ```yaml
     directory: "/path/to/source"
     command: "pytest"
     include_patterns:
       - "*.py"
     exclude_patterns:
       - "*.test.py"
     debounce_time: 300
     ```

## Step 3: Implement `config.py` for YAML Loading

1. **Install Required Libraries**  
   - Ensure that `pyyaml` is available for loading YAML configurations.  
   ```bash
   pip install pyyaml
   ```

2. **Develop `config.py`**  
   - Import necessary modules (yaml).
   - Define a function to load the YAML configuration and handle missing values or incorrect formats.
   - Implement checks for required fields and set default values where applicable.

3. **Sample Code for `config.py`**  
   ```python
   import yaml
   import os

   def load_config(config_file):
       with open(config_file, 'r') as file:
           config = yaml.safe_load(file)
       
       # Set default values
       config.setdefault('debounce_time', 300)
       return config
   ```

## Step 4: Create `watcher.py`

1. **Import Required Libraries**  
   - Install and import `watchdog` for filesystem monitoring.  
   ```bash
   pip install watchdog
   ```
   - Import `os`, `subprocess`, and the configuration loader from `config.py`.

2. **Develop Watcher Class**  
   - Create a Watcher class that extends `watchdog.observers.Observer`.
   - Implement:
     - Method to load configurations using `config.load_config()`.
     - Method to define include/exclude patterns and debounce logic using `watchdog`.
     - Event handler that listens for changes in the specified directory.
     - In the event handler, implement logic to execute the configured command after a debounce period.

3. **Sample Code for `watcher.py`**  
   ```python
   import time
   import subprocess
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler
   from config import load_config

   class FileChangeHandler(FileSystemEventHandler):
       def __init__(self, command, debounce_time):
           self.command = command
           self.debounce_time = debounce_time
           self.last_modified = 0

       def on_modified(self, event):
           current_time = time.time()
           if current_time - self.last_modified > self.debounce_time / 1000:
               self.last_modified = current_time
               self.run_command()

       def run_command(self):
           subprocess.run(self.command, shell=True)

   if __name__ == "__main__":
       config = load_config('watcher.yaml')
       observer = Observer()
       event_handler = FileChangeHandler(config['command'], config['debounce_time'])
       
       observer.schedule(event_handler, config['directory'], recursive=True)
       observer.start()

       try:
           while True:
               time.sleep(1)
       except KeyboardInterrupt:
           observer.stop()
       observer.join()
   ```

## Step 5: Implement Unit Tests in `test_watcher.py`

1. **Setup Testing Framework**  
   - Use `pytest` for writing unit tests. Ensure it's installed if not already.
   ```bash
   pip install pytest
   ```

2. **Develop Unit Tests**  
   - Write tests to verify loading of YAML configurations.
   - Create mock tests for file changes and command execution without actually running the commands.
   - Ensure to add cases for inclusion and exclusion patterns.

3. **Sample Test Code for `test_watcher.py`**  
   ```python
   import pytest
   from config import load_config

   def test_load_config():
       config = load_config('watcher.yaml')
       assert 'directory' in config
       assert 'command' in config
       assert config['debounce_time'] == 300  # Default value

   # Additional tests will go here
   ```

## Step 6: Review and Finalize

1. **Testing**  
   - Run unit tests using `pytest` to ensure all functions work as expected.
   - Simulate file changes to check if the specified command runs correctly.

2. **Documentation**  
   - Document code and provide inline comments where necessary.
   - Create a basic README file to explain how to use the CLI tool and its configuration.

3. **Version Control**  
   - Initialize a Git repository and commit all changes.
   ```bash
   git init
   git add .
   git commit -m "Initial commit of file watcher"
   ``` 

4. **Plan Deployment**  
   - Determine how the tool will be shared or deployed (e.g., packaging or sharing via a code repository). 

By following this structured plan, the File Watcher CLI tool will meet the specified requirements and be ready for use.
