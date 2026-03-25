---
case: case_002_file_watcher
framework: gemini_adk
model: gemini-3-flash-preview
provider: gemini
session_id: None
duration_ms: 5932
duration_wall_s: 5.9
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:04:15.016067+00:00
error: None
---

# Plan

# Implementation Plan: Case 002 - File Watcher

This plan outlines the development of a Python-based CLI tool that monitors a directory for file changes and executes a specified command based on configuration.

## 1. Assumptions & Technical Decisions
- **Python Version**: 3.10+ assumed.
- **Library**: `watchdog` for monitoring, `PyYAML` for configuration parsing, and `fnmatch` for glob pattern matching.
- **Debouncing Logic**: A timer-based approach will be used. When an event occurs, a timer starts. If another event occurs before the timer expires, the timer resets. The command executes only when the timer successfully reaches the threshold (default 300ms).
- **Working Directory**: The tool will assume the current working directory is the root of the project being monitored unless specified otherwise in the config.

## 2. File Structure
- `watcher.py`: CLI entry point, event handler logic, and debouncing.
- `config.py`: Logic to load and validate `watcher.yaml`.
- `watcher.yaml`: Configuration file defining paths, patterns, and commands.
- `test_watcher.py`: Unit tests for configuration loading and pattern matching.

---

## 3. Step-by-Step Implementation

### Step 1: Define Configuration Schema (`watcher.yaml`)
Create an example configuration file to guide development.
- `directory`: Path to monitor (default: `.`).
- `command`: String command to execute (e.g., `pytest`).
- `include`: List of glob patterns to monitor (e.g., `*.py`).
- `exclude`: List of glob patterns to ignore (e.g., `__pycache__/*`, `.git/*`).
- `debounce_ms`: Integer (default: 300).

### Step 2: Implement Configuration Loader (`config.py`)
- Use `yaml` (PyYAML) to load `watcher.yaml`.
- Implement a `WatcherConfig` class or dataclass.
- Provide default values for `debounce_ms` (300) and `directory` (`.`).
- Implement a method to validate that the `command` is present.

### Step 3: Implement Event Handling & Filtering (`watcher.py`)
- Create a class `FileChangeHandler` inheriting from `watchdog.events.FileSystemEventHandler`.
- Implement `on_modified`, `on_created`, and `on_deleted` methods.
- **Pattern Matching**: Use `fnmatch.fnmatch` to check if the changed file path matches any `include` patterns and does NOT match any `exclude` patterns.
- **Debouncing**: 
    - Use `threading.Timer` to manage the delay.
    - Maintain a reference to the current timer. If a new valid event arrives, cancel the existing timer and start a new one.
    - The timer's callback will trigger the execution of the configured `command`.

### Step 4: Implement Command Execution (`watcher.py`)
- Use `subprocess.run` or `subprocess.Popen` to execute the command.
- Ensure the command runs in a shell (`shell=True`) to support complex commands or pipes.
- Print the output of the command to the console for the user to see.

### Step 5: CLI Entry Point (`watcher.py`)
- Set up the `watchdog.observers.Observer`.
- Load configuration using `config.py`.
- Schedule the `FileChangeHandler` on the target directory.
- Handle `KeyboardInterrupt` (Ctrl+C) to stop the observer gracefully.

### Step 6: Unit Testing (`test_watcher.py`)
- Test `config.py`: Ensure YAML is parsed correctly and defaults are applied.
- Test Pattern Matching: Mock file paths and verify they are correctly included/excluded based on glob patterns.
- Test Debounce Logic: (Optional/Advanced) Use time mocking to ensure the command is not triggered multiple times for rapid events.

---

## 4. Execution Flow
1. User runs `python watcher.py`.
2. `watcher.py` calls `config.py` to load `watcher.yaml`.
3. `watchdog` starts monitoring the specified directory.
4. User modifies a file (e.g., `WorkingDir/src/app.py`).
5. `watchdog` triggers an event.
6. `FileChangeHandler` checks if `app.py` matches `include` and not `exclude`.
7. If valid, a 300ms timer starts.
8. If no other changes occur within 300ms, the `command` (e.g., `pytest`) is executed.
9. Output is printed to the terminal.

## 5. Dependencies
- `watchdog`
- `PyYAML`
- `pytest` (for running tests)
