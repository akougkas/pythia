---
case: case_002_file_watcher
framework: gemini_adk
model: gemini-2.5-flash
provider: gemini
session_id: None
duration_ms: 16309
duration_wall_s: 16.3
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T01:52:37.798515+00:00
error: None
---

# Plan

## Plan: File Watcher CLI Tool

The objective is to create a Python CLI tool that monitors a directory for file changes using `watchdog` and executes a configurable command. Configuration will be handled via `watcher.yaml`, supporting include/exclude glob patterns and debouncing.

### Assumptions

1.  The `watcher.yaml` file will be located in the current working directory by default, but its path can be overridden via a CLI argument.
2.  The `command` specified in `watcher.yaml` will be executed in the context of the monitored `directory`.
3.  Glob patterns for `include` and `exclude` will be relative to the monitored `directory`.
4.  The `debounce_ms` value will be an integer representing milliseconds.

### Step-by-Step Implementation Plan

#### 1. Project Setup and Dependencies

*   Create the project directory structure.
*   Install necessary libraries: `pip install watchdog PyYAML` (and `pytest` for testing).

#### 2. `config.py` - Configuration Loader

**Objective:** Load and validate `watcher.yaml`, providing a structured configuration object.

*   **Define `Config` Class:**
    *   Create a class (e.g., `WatcherConfig`) to hold configuration parameters: `directory`, `command`, `include_patterns`, `exclude_patterns`, `debounce_ms`.
    *   Use `pathlib.Path` for directory paths for easier manipulation.
*   **`load_config(config_path: Path)` Function:**
    *   Accepts a `Path` object to the `watcher.yaml` file.
    *   Read the YAML file using `PyYAML`.
    *   **Validation and Defaults:**
        *   Check for required fields: `directory`, `command`. Raise an error if missing.
        *   `directory`: Resolve to an absolute path. Ensure it exists and is a directory.
        *   `command`: Store as a string.
        *   `include`: Default to `['**/*']` if not provided. Ensure it's a list of strings.
        *   `exclude`: Default to `[]` if not provided. Ensure it's a list of strings.
        *   `debounce_ms`: Default to `300` if not provided. Ensure it's an integer and non-negative.
    *   Return an instance of the `WatcherConfig` class.
*   **Helper Method (Optional but Recommended):**
    *   Add a method to `WatcherConfig` to check if a given file path matches the include/exclude patterns. This method will take a `Path` object and return `True` if it should be processed, `False` otherwise. It should first check `include` patterns, then `exclude` patterns.

#### 3. `watcher.yaml` - Example Configuration

**Objective:** Provide a clear example of the configuration file.

*   Create `watcher.yaml` with the following structure:

    ```yaml
    directory: .
    command: echo "Files changed! Running tests..." && python -m pytest
    include:
      - "**/*.py"
      - "**/*.js"
    exclude:
      - "**/__pycache__/*"
      - "**/*.tmp"
      - ".git/**/*"
    debounce_ms: 500
    ```

#### 4. `watcher.py` - Main CLI Tool

**Objective:** Implement the CLI, `watchdog` integration, debouncing, and command execution.

*   **CLI Argument Parsing:**
    *   Use `argparse` to define a `--config` argument (defaulting to `watcher.yaml` in the current directory).
*   **Debouncer Class/Function:**
    *   Create a `Debouncer` class or a set of functions.
    *   It should take a callback function (the command executor) and a `delay` (from `debounce_ms`).
    *   When `debounce.call()` is invoked, it should:
        *   Cancel any previously scheduled timer.
        *   Start a new `threading.Timer` that will execute the callback after `delay`.
    *   Ensure thread safety for cancelling/starting timers.
*   **Custom `FileSystemEventHandler`:**
    *   Create a class `ChangeHandler` inheriting from `watchdog.events.FileSystemEventHandler`.
    *   Initialize it with the `WatcherConfig` instance and the `Debouncer`.
    *   Override `on_any_event(event)`:
        *   Filter out directory events (only care about file changes).
        *   Get the `Path` object for `event.src_path`.
        *   Use the `WatcherConfig`'s helper method to check if the file matches `include`/`exclude` patterns.
        *   If it matches, call `debouncer.call()`.
*   **Command Execution Function:**
    *   Create a function `execute_command(command: str, cwd: Path)`:
        *   Use `subprocess.run` to execute the `command`.
        *   Set `cwd` to the monitored directory.
        *   Print stdout/stderr to the console.
        *   Handle potential `subprocess.CalledProcessError` or other exceptions.
*   **Main `run_watcher()` Function:**
    *   Parse CLI arguments to get the config file path.
    *   Load configuration using `config.load_config()`.
    *   Initialize the `Debouncer` with `execute_command` (bound with the config's command and directory) and `config.debounce_ms / 1000.0` (convert ms to seconds).
    *   Initialize the `ChangeHandler` with the loaded config and the debouncer.
    *   Create an `Observer` from `watchdog.observers`.
    *   Schedule the `ChangeHandler` to watch `config.directory` recursively.
    *   Start the observer.
    *   Implement a `try...finally` block:
        *   Inside `try`: Loop indefinitely (e.g., `while True: time.sleep(1)`) to keep the main thread alive.
        *   Inside `finally`: Stop the observer and join it to ensure graceful shutdown on `KeyboardInterrupt`.
*   **Entry Point:**
    *   Add `if __name__ == "__main__":` block to call `run_watcher()`.

#### 5. `test_watcher.py` - Unit Tests

**Objective:** Ensure correctness of configuration loading, pattern matching, and debouncing.

*   **`config.py` Tests:**
    *   Test `load_config` with a valid `watcher.yaml`.
    *   Test `load_config` with missing required fields (e.g., `directory`, `command`).
    *   Test `load_config` with different `include`/`exclude` patterns.
    *   Test `load_config` with default values for optional fields.
    *   Test the `WatcherConfig`'s pattern matching helper method with various file paths.
*   **Debouncer Tests:**
    *   Test that the debouncer calls the callback only once after multiple rapid calls within the debounce period.
    *   Test that the debouncer calls the callback if calls are spaced out beyond the debounce period.
    *   Use `unittest.mock` or similar to mock the callback function and assert its call count and timing.
*   **`watcher.py` (Integration/Mocked Tests):**
    *   Mock `watchdog` events to simulate file changes and verify that the debouncer is triggered correctly.
    *   Mock `subprocess.run` to ensure the correct command is executed with the correct `cwd`.
    *   Test CLI argument parsing.

#### 6. Documentation and Refinement

*   Add docstrings to all functions and classes.
*   Add comments where necessary.
*   Ensure error messages are user-friendly.
*   Review code for clarity and maintainability.

This plan covers all requirements and constraints, providing a structured approach to building the file watcher CLI tool.
