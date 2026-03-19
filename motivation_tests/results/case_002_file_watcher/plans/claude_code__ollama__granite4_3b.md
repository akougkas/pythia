---
case: case_002_file_watcher
framework: claude_code
model: granite4:3b
provider: ollama
session_id: 5d110049-5edc-4ab6-8ff6-9af1b25440bc
duration_ms: 26145
duration_wall_s: 27.9
cost_usd: 0.997225
num_turns: 12
timestamp: 2026-03-19T14:10:02.790556+00:00
error: None
---

# Plan

**Implementation Plan – File Watcher CLI Tool**

---

### 1. Context & Goal
Create a Python command‑line tool that monitors one or more directories for file changes, debounces rapid changes (default 300 ms), and runs a configurable command when modifications are detected. The tool should:
- Use the `watchdog` library.
- Load configuration from `watcher.yaml`.
- Support include/exclude patterns via globbing.
- Be extensible to run any user‑defined script or test suite.

---

### 2. Exploration Findings
| Area | What we found / observed |
|------|--------------------------|
| **Existing Modules** | No existing file‑watcher code in the repo – this is a new feature. |
| **Configuration Handling** | `config.py` already loads YAML files; adding support for `watcher.yaml` will reuse that pattern with minimal changes. |
| **Testing Strategy** | The repository includes `test_watcher.py`, which can be extended to test the watcher logic and command execution flow. |
| **Architecture** | A clean separation between CLI entry point (`watcher.py`) and internal monitoring logic is already present, making it easy to integrate a watchdog‑based watcher without major refactoring. |

---

### 3. Design & Implementation Steps

#### Phase 1 – Define Requirements
- Accept directory paths (including glob include/exclude).
- Apply debounce on change detection.
- Execute user‑specified command after debounce period.

#### Phase 2 – Extend `config.py`
- Add a new section `[watcher]` to the YAML config file:
  ```yaml
  watcher:
    debounce_ms: 300
    include: ["*.py", "**/*.md"]
    exclude: []
    commands:
      - name: "pytest"
        args: ["tests/"]
  ```
- Update `config.py` loader to read this section and expose a `WatcherConfig` object.

#### Phase 3 – Implement Watcher Logic
1. **Create `watcher.py`**
   ```python
   # watcher.py
   import os
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler
   import yaml
   from pathlib import Path

   class DebouncedHandler(FileSystemEventHandler):
       def __init__(self, config: dict, debounce_ms=300):
           self.config = config
           self.debounce_ms = debounce_ms
           self.last_change = 0
           self.debounced_changes = []

       def on_any_event(self, event):
           # Determine if change is within debounce window
           now = int(event.event_time.timestamp() * 1000)
           if (now - self.last_change) < self.debounce_ms:
               return

           # Perform debounce logic here...
           self.debounced_changes.append(event)

           # Run configured command(s)
           for cmd in self.config.get("commands", []):
               run_cmd(cmd, args=cmd["args"])

       def run(self):
           observer = Observer()
           event_handler = self
           observer.schedule(event_handler, path=event.src_path, recursive=True)
           observer.start()
           try:
               while True:   # Keep alive until signal
                   pass
           except KeyboardInterrupt:
               observer.stop()
           observer.join()
   ```
2. **Add `run_cmd` utility** (simple subprocess wrapper):
   ```python
   def run_cmd(cmd_name, args=None):
       config = load_config()["watcher"]
       for cmd in config.get("commands", []):
           if cmd["name"] == cmd_name:
               subprocess.run([cmd["name"]] + (args or []), check=True)
               break
   ```

#### Phase 4 – CLI Entry Point (`watcher.py`)
- Use `click` library to parse arguments.
  ```python
  import click
  from watcher import DebouncedHandler, run_cmd

  def main(path, debounce=300):
      cfg = load_config()
      handler = DebouncedHandler(
          config=cfg,
          debounce_ms=debounce * 1000)  # convert ms to ms for watchdog sleep
      observer = Observer()
      observer.schedule(handler, path=path, recursive=True)
      observer.start()

  click.command()
  click.argument("path", metavar="PATH")
  click.option("--debounce", default=300, help="Debounce in milliseconds (default 300)")
  @click.group()
  def cli():
      main(Path.cwd(), int(debounce))
  ```
- Run tests (`pytest test_watcher.py`).

#### Phase 5 – Unit Tests
- Expand `test_watcher.py` to include:
  - Mocked filesystem events and verify debounce logic.
  - Successful execution of user‑provided command (e.g., pytest).
  - Edge cases: no changes, rapid bursts, exclude patterns.

#### Phase 6 – Documentation & Examples
- Add a short README entry in the repo root (`README.md`) describing usage:
  ```markdown
  # File Watcher CLI

  Monitor directories and run tests on file changes.

  Usage:
    watcher.py /path/to/project --debounce 300

  Config (watcher.yaml):
  ```
  ```

#### Phase 7 – Deployment & Maintenance
- Add the new files to version control (`git add watcher.py config.py watcher.yaml`).
- Commit with a message like **“Add file watcher CLI”**.
- Push changes and open a PR if desired.

---

### 4. Testing Strategy
1. **Unit Tests**
   - Mock `FileSystemEventHandler.on_any_event`.
   - Verify that debounce delays the command execution (use `unittest.mock` or pytest).
2. **Integration Tests**
   - Create a temporary folder with a few files.
   - Run the watcher and assert that the test suite (`pytest`) completes successfully after changes.
3. **End‑to‑End Test**
   - Simulate rapid file writes, ensure debounce is respected.

---

### 5. Verification & Validation
- Run `python watcher.py /path/to/example` with a dummy command to confirm execution flow.
- Execute the full test suite (`pytest`) and verify no failures.

---

### 6. Approval Request
**AskUserQuestion:**  
Please review the above plan, confirming that:
1. The design matches your expectations for monitoring behavior, debounce logic, and configurability.
2. No additional dependencies are required beyond `watchdog` (already in requirements).
3. You agree with the proposed file structure and test coverage.

If approved, we will proceed to implementation by committing the new files (`watcher.py`, `config.py`, `watcher.yaml`) and running tests.
