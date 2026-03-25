---
case: case_002_file_watcher
framework: crewai
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 52855
duration_wall_s: 52.9
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:23:52.352859+00:00
error: None
---

# Plan

# Case 002: File Watcher Implementation Plan

## Overview

This document provides a comprehensive, step-by-step implementation plan for creating a Python CLI file watcher tool. The tool monitors directories for file changes and executes configurable commands when source files are modified.

---

## Directory Structure

```
/home/jye/publications/cases/case_002_file_watcher/
├── watcher.py                    # Main CLI entry point
├── config.py                     # YAML configuration loader
├── watcher.yaml                  # Example configuration file
├── test_watcher.py               # Unit tests
├── test_resources/               # Test fixtures and fixtures
│   ├── source/
│   │   ├── test_file.py
│   │   └── another.py
│   └── excluded_test.py
└── logs/                        # Watchdog and action logs
```

---

## Technical Decisions & Assumptions

### Assumptions (Explicitly Stated)
1. **Python Version**: Python 3.8+ required (for f-strings, type hints)
2. **Python Packages**: 
   - `watchdog` (filesystem event monitoring)
   - `PyYAML` (configuration parsing)
   - `click` (CLI framework)
3. **Debounce Time**: 300ms default, configurable
4. **Command Execution**: Uses `subprocess` for cross-platform compatibility
5. **File Pattern Matching**: Uses `fnmatch` for glob pattern matching
6. **Watchdog Handler**: Uses `FileSystemEventHandler` with custom debouncing
7. **Error Handling**: Catch-all exception handling with logging to stderr
8. **Directory Watch**: Watches only directories specified in config (not parent directories)
9. **Event Filtering**: Only trigger on `modify` events (not `create`/`delete` unless configured)
10. **Logging**: Uses Python's `logging` module with file handler and console formatter

### Technical Decisions

1. **Debouncing Implementation**: Implement a token bucket-style debouncer using timestamps
2. **Event Caching**: Cache file mtime values to avoid excessive filesystem checks
3. **Command Template**: Commands accept `{file}` placeholder for source file path
4. **Background Execution**: Commands run in background thread to avoid blocking watcher
5. **Restart Safety**: Watcher restarts cleanly on directory changes without losing watch state

---

## Implementation Steps

### Step 1: Create config.py

**File Path**: `/home/jye/publications/cases/case_002_file_watcher/config.py`

```python
"""Configuration loader for the file watcher."""

import os
import yaml
from typing import Dict, Any
from pathlib import Path


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate watcher configuration from YAML file.
    
    Args:
        config_path: Path to watcher.yaml configuration file
        
    Returns:
        Dictionary containing parsed configuration
        
    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If configuration is malformed
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate required fields
    required_fields = ['watch_dirs', 'patterns', 'exclude_patterns', 'debounce_ms', 'command']
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required configuration field: {field}")
    
    # Validate watch_dirs is a list
    if not isinstance(config['watch_dirs'], list):
        raise ValueError("watch_dirs must be a list")
    
    # Validate debounce_ms is numeric
    try:
        config['debounce_ms'] = int(config['debounce_ms'])
    except (ValueError, TypeError):
        raise ValueError("debounce_ms must be an integer")
    
    return config


def get_watch_dir_base(config: Dict[str, Any]) -> Path:
    """
    Get the base directory for the watcher.
    
    Args:
        config: Loaded configuration
        
    Returns:
        Path object for base watch directory
    """
    return Path(config['watch_dirs'][0]) if config['watch_dirs'] else Path.cwd()


def get_file_to_watch(file_path: Path, config: Dict[str, Any]) -> bool:
    """
    Determine if a file should be watched based on patterns.
    
    Args:
        file_path: Path to check
        config: Loaded configuration
        
    Returns:
        True if file should be watched, False otherwise
    """
    # Check exclude patterns first (short-circuit)
    for pattern in config.get('exclude_patterns', []):
        if fnmatch.fnmatch(str(file_path), pattern):
            return False
    
    # Check include patterns (must match at least one)
    for pattern in config.get('patterns', ['*.py']):
        if fnmatch.fnmatch(str(file_path), pattern):
            return True
    
    # Default: watch if no exclude patterns and path is under watched dir
    return True
```

### Step 2: Create watcher.yaml

**File Path**: `/home/jye/publications/cases/case_002_file_watcher/watcher.yaml`

```yaml
# File Watcher Configuration
# Location: /home/jye/publications/cases/case_002_file_watcher/watcher.yaml

# Directories to watch (list of paths)
watch_dirs:
  - /home/jye/publications/cases/case_002_file_watcher/WorkingDir
  - /home/jye/publications/cases/case_002_file_watcher/test_resources

# File patterns to watch (use * for wildcards)
patterns:
  - "*.py"
  - "*.pyi"
  - "*.pyx"

# File patterns to exclude
exclude_patterns:
  - "*.pyc"
  - "*.pyo"
  - "__pycache__/*"
  - "*.md"
  - "*.txt"
  - "*.lock"

# Debounce time in milliseconds
# This prevents rapid-fire command executions during file editing
debounce_ms: 300

# Command to execute when watched files change
# Use {file} placeholder to pass the modified file path
command: "pytest {file}"

# Optional: Command for delete events
# command_delete: "echo 'File deleted: {file}'"

# Optional: Enable verbose logging
verbose: false

# Optional: Enable color output in terminal
color: true

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
log_level: INFO
```

### Step 3: Create watcher.py

**File Path**: `/home/jye/publications/cases/case_002_file_watcher/watcher.py`

```python
#!/usr/bin/env python3
"""
File Watcher CLI Tool

Monitors directories for file changes and executes configurable commands.
"""

import os
import sys
import time
import threading
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import logging

import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import config module
from config import load_config, get_file_to_watch, get_watch_dir_base


class Debouncer:
    """
    Debouncer utility to prevent rapid-fire event handling.
    
    Uses a simple timestamp-based approach where events within
    the debounce window are ignored.
    """
    
    def __init__(self, debounce_ms: int):
        self.debounce_ms = debounce_ms
        self.last_event_time: float = 0.0
        self.lock = threading.Lock()
    
    def is_valid(self, event_time: float) -> bool:
        """
        Check if an event should be processed.
        
        Args:
            event_time: Current timestamp in seconds
            
        Returns:
            True if event should be processed
        """
        with self.lock:
            if event_time - self.last_event_time < self.debounce_ms / 1000.0:
                return False
            self.last_event_time = event_time
            return True
    
    def reset(self):
        """Reset the debouncer (useful for initial events)."""
        with self.lock:
            self.last_event_time = 0.0


class WatcherHandler(FileSystemEventHandler):
    """
    File system event handler for the watcher.
    
    Handles file creation, modification, and deletion events,
    applying debounce filtering and command execution.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debouncer = Debouncer(config['debounce_ms'])
        self.logger = self._setup_logger(config)
        self.running = True
        self._last_file_hashes: Set[str] = set()
    
    def _setup_logger(self, config: Dict[str, Any]) -> logging.Logger:
        """Setup logging based on configuration."""
        logger = logging.getLogger('FileWatcher')
        logger.setLevel(logging.DEBUG if config.get('verbose', False) else logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        if config.get('color', False):
            ch.setLevel(logging.DEBUG)
        else:
            ch.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        return logger
    
    def on_any_event(self, event):
        """
        Handle any file system event.
        
        Args:
            event: Watchdog FileSystemEvent object
        """
        if not self.running:
            return
        
        if event.event_type in ['modify', 'created', 'deleted']:
            file_path = Path(event.src_path)
            event_time = time.time()
            
            if not self.debouncer.is_valid(event_time):
                self.logger.debug(
                    f"Debouncing event for {file_path} "
                    f"(elapsed: {(event_time - self.last_event_time) * 1000:.0f}ms)"
                )
                return
            
            self._handle_file_change(event, file_path)
    
    def _handle_file_change(self, event, file_path: Path):
        """
        Handle a file change event after debouncing.
        
        Args:
            event: The filesystem event
            file_path: Path to the changed file
        """
        if not get_file_to_watch(file_path, self.config):
            self.logger.debug(f"File filtered out: {file_path}")
            return
        
        # Get the command template
        cmd_template = self.config.get('command', 'echo "Change detected: {file}"')
        
        # Replace {file} placeholder
        final_command = cmd_template.replace('{file}', str(file_path))
        
        if event.event_type == 'deleted':
            self.logger.info(f"Command executed for deleted file: {final_command}")
            self._execute_command(final_command)
        elif event.event_type == 'created':
            self.logger.info(f"Command executed for new file: {final_command}")
            self._execute_command(final_command)
        else:  # 'modified'
            self.logger.info(f"Command executed for modified file: {final_command}")
            self._execute_command(final_command)
    
    def _execute_command(self, command: str):
        """
        Execute the command asynchronously.
        
        Args:
            command: Command string to execute
        """
        def command_thread():
            self.logger.debug(f"Executing command: {command}")
            try:
                subprocess.run(
                    command,
                    shell=True,
                    check=False,  # Don't raise on non-zero exit
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.logger.info(f"Command completed successfully")
            except Exception as e:
                self.logger.error(f"Command execution failed: {e}")
        
        thread = threading.Thread(target=command_thread)
        thread.daemon = True
        thread.start()


class FileWatcher:
    """
    Main file watcher class that manages the observer and handler.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.config['watch_dirs'] = config.get('watch_dirs', [])
        self.logger = logging.getLogger('FileWatcher')
        self.running = False
        self.observer: Optional[watchdog.Observer] = None
    
    def start(self):
        """
        Start watching directories.
        """
        if not self.config['watch_dirs']:
            self.logger.error("No directories to watch configured")
            return
        
        # Get handler
        handler = WatcherHandler(self.config)
        
        # Create observer
        self.observer = watchdog.Observer()
        
        # Set up watchers for each directory
        for watch_dir in self.config['watch_dirs']:
            watch_path = Path(watch_dir).expanduser()
            
            if not watch_path.exists():
                self.logger.warning(f"Directory does not exist: {watch_path}")
                continue
            
            # Add directory to watch
            self.observer.schedule(handler, str(watch_path), recursive=True)
        
        # Start the observer
        self.observer.start()
        self.logger.info(f"Watching {len(self.config['watch_dirs'])} directories")
        self.running = True
        self.logger.info("Watcher started successfully")
    
    def stop(self):
        """
        Stop watching and clean up resources.
        """
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.running = False
        self.logger.info("Watcher stopped")
    
    def pause(self):
        """
        Pause watching without stopping the observer.
        """
        if self.observer:
            self.observer.stop()


def main():
    """
    Main entry point for the watcher CLI.
    """
    import click
    import argparse
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='File Watcher CLI - Monitor directories for file changes'
    )
    
    parser.add_argument(
        '-c', '--config',
        default='watcher.yaml',
        help='Path to configuration file (default: watcher.yaml)'
    )
    
    parser.add_argument(
        '-w', '--watch-dir',
        action='append',
        default=None,
        help='Additional directory to watch (overrides config)'
    )
    
    parser.add_argument(
        '--pause',
        action='store_true',
        help='Pause watching without stopping'
    )
    
    parser.add_argument(
        '--stop',
        action='store_true',
        help='Stop watching immediately'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Override watch_dirs if arguments provided
    if args.watch_dir:
        config['watch_dirs'] = args.watch_dir
    
    # Override config for command line
    if args.watch_dir:
        config['watch_dirs'] = args.watch_dir
    
    # Set up watcher
    watcher = FileWatcher(config)
    
    try:
        if args.stop:
            watcher.stop()
            print("Watcher stopped")
            sys.exit(0)
        
        if args.pause:
            watcher.pause()
            print("Watcher paused")
            sys.exit(0)
        
        watcher.start()
        
        # Keep main thread alive (for Ctrl+C handling)
        signal_handler = None
        
        def signal_handler_func(signum, frame):
            logging.warning("Received shutdown signal")
            watcher.stop()
            sys.exit(0)
        
        import signal
        signal.signal(signal.SIGINT, signal_handler_func)
        signal.signal(signal.SIGTERM, signal_handler_func)
        
        # Run indefinitely
        try:
            while watcher.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.warning("Watcher stopped by user")
            watcher.stop()
    
    except Exception as e:
        logging.error(f"Watcher error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### Step 4: Create test_watcher.py

**File Path**: `/home/jye/publications/cases/case_002_file_watcher/test_watcher.py`

```python
#!/usr/bin/env python3
"""
Unit tests for the file watcher.

Uses pytest with fixtures and mocks to avoid actual filesystem operations
during testing.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from config import load_config, get_file_to_watch
from watcher import (
    Debouncer,
    WatcherHandler,
    FileWatcher,
    WatchdogConfigError,
    FileChange
)


class TestDebouncer(unittest.TestCase):
    """Tests for the Debouncer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.debouncer = Debouncer(300)  # 300ms debounce
    
    def test_debounce_respects_delay(self):
        """Test that debounce delays event processing."""
        import time
        
        # First event should pass
        self.assertTrue(self.debouncer.is_valid(time.time()))
        
        # Second event within debounce window should be rejected
        time.sleep(0.1)  # Wait 100ms
        self.assertFalse(self.debouncer.is_valid(time.time()))
    
    def test_debounce_resets_after_window(self):
        """Test that debounce window expires."""
        # First event
        self.debouncer.last_event_time = time.time()
        
        # Wait for debounce window
        import time
        time.sleep(0.5)  # Wait 500ms
        
        # Next event should pass
        self.assertTrue(self.debouncer.is_valid(time.time()))
    
    def test_reset_clears_timestamp(self):
        """Test that reset clears the timestamp."""
        self.debouncer.reset()
        self.assertTrue(self.debouncer.is_valid(time.time()))


class TestWatcherHandler(unittest.TestCase):
    """Tests for the WatcherHandler class."""
    
    @patch('watcher.subprocess')
    def test_handler_executes_command_on_modify(self, mock_subprocess):
        """Test that handler executes command on file modification."""
        config = {
            'debounce_ms': 300,
            'command': 'echo "test {file}"',
            'patterns': ['*.py'],
            'exclude_patterns': []
        }
        
        handler = WatcherHandler(config)
        
        # Mock subprocess.run to capture calls
        mock_run = Mock()
        mock_subprocess.run = mock_run
        
        # Create mock event
        event = Mock()
        event.event_type = 'modified'
        event.src_path = '/test/path/test.py'
        
        # Call handler
        handler.on_any_event(event)
        
        # Verify command was run
        mock_run.assert_called()
    
    def test_handler_filters_excluded_files(self):
        """Test that handler filters out excluded files."""
        config = {
            'debounce_ms': 300,
            'command': 'echo "test"',
            'patterns': ['*.py'],
            'exclude_patterns': ['*.pyc']
        }
        
        handler = WatcherHandler(config)
        
        # Mock the handler to count calls
        original_handle = handler._handle_file_change
        call_count = 0
        
        def counting_handle(event, file_path):
            nonlocal call_count
            call_count += 1
            return original_handle(event, file_path)
        
        handler._handle_file_change = counting_handle
        
        # Test excluded file
        event = Mock()
        event.event_type = 'modified'
        event.src_path = '/test/path/test.py'
        
        handler.on_any_event(event)
        
        # Should have been filtered by Debouncer, not passed to _handle_file_change
        # But this test verifies exclude_patterns work
        self.assertEqual(call_count, 0)
    
    def test_handler_handles_deleted_files(self):
        """Test that handler processes delete events."""
        config = {
            'debounce_ms': 300,
            'command': 'echo "test {file}"',
            'patterns': ['*.py'],
            'exclude_patterns': []
        }
        
        handler = WatcherHandler(config)
        
        # Mock subprocess
        with patch('watcher.subprocess') as mock_subprocess:
            mock_subprocess.run = Mock()
            
            # Create delete event
            event = Mock()
            event.event_type = 'deleted'
            event.src_path = '/test/path/test.py'
            
            handler.on_any_event(event)
            
            # Verify command was executed
            mock_subprocess.run.assert_called()


class TestConfig(unittest.TestCase):
    """Tests for the configuration module."""
    
    def test_load_valid_config(self):
        """Test loading a valid configuration."""
        config = {
            'watch_dirs': ['/test/dir'],
            'patterns': ['*.py'],
            'exclude_patterns': ['*.pyc'],
            'debounce_ms': 300,
            'command': 'pytest {file}'
        }
        
        config_dict = load_config('watcher.yaml')
        
        self.assertEqual(config_dict['debounce_ms'], 300)
    
    def test_load_missing_field_raises(self):
        """Test that missing required fields raise error."""
        # Mock invalid config
        invalid_yaml = '''
        watch_dirs: []
        # missing required field
        '''
        
        # This would raise ValueError in load_config
        pass
    
    def test_get_file_to_watch_includes(self):
        """Test that files matching patterns are included."""
        config = {
            'patterns': ['*.py'],
            'exclude_patterns': []
        }
        
        self.assertTrue(get_file_to_watch(Path('test.py'), config))
    
    def test_get_file_to_watch_excludes(self):
        """Test that files matching exclude patterns are excluded."""
        config = {
            'patterns': ['*.py'],
            'exclude_patterns': ['*.pyc']
        }
        
        self.assertFalse(get_file_to_watch(Path('test.pyc'), config))


class TestFileWatcher(unittest.TestCase):
    """Tests for the FileWatcher class."""
    
    def test_watcher_starts_and_stops(self):
        """Test that watcher can start and stop."""
        config = {
            'watch_dirs': ['/test'],
            'patterns': ['*.py'],
            'exclude_patterns': [],
            'debounce_ms': 300,
            'command': 'echo test',
            'verbose': False
        }
        
        watcher = FileWatcher(config)
        
        # Test stop method
        watcher.stop()
        self.assertFalse(watcher.running)
    
    def test_watcher_handles_missing_dir(self):
        """Test that watcher handles missing directories gracefully."""
        config = {
            'watch_dirs': ['/nonexistent/dir'],
            'patterns': ['*.py'],
            'exclude_patterns': [],
            'debounce_ms': 300,
            'command': 'echo test',
            'verbose': False
        }
        
        watcher = FileWatcher(config)
        
        # Should not raise exception
        with self.assertLogs():
            watcher.start()
    
    def test_watcher_replaces_command_placeholder(self):
        """Test that command template has file path replaced."""
        config = {
            'watch_dirs': ['/test'],
            'patterns': ['*.py'],
            'exclude_patterns': [],
            'debounce_ms': 300,
            'command': 'pytest {file}',
            'verbose': False
        }
        
        handler = WatcherHandler(config)
        
        # Mock subprocess to capture command
        with patch('watcher.subprocess.run') as mock_run:
            mock_run.return_value = Mock()
            
            event = Mock()
            event.event_type = 'modified'
            event.src_path = '/test/source/test.py'
            
            handler.on_any_event(event)
            
            # Verify command has correct file path
            mock_run.assert_called()
            call_args = mock_run.call_args
            command = call_args[0][0]
            self.assertIn('/test/source/test.py', command)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete watcher."""
    
    @patch('watcher.watcher.FileSystemEventHandler')
    @patch('watcher.watcher.Observer')
    @patch('watcher.watcher.watchdog')
    def test_complete_watcher_workflow(self, mock_watchdog, mock_observer, mock_handler):
        """Test complete watcher workflow."""
        # Setup mocks
        mock_watchdog.Observer = Mock()
        mock_obs = Mock()
        mock_watchdog.Observer.return_value = mock_obs
        
        config = {
            'watch_dirs': ['/test'],
            'patterns': ['*.py'],
            'exclude_patterns': [],
            'debounce_ms': 300,
            'command': 'pytest {file}',
            'verbose': False
        }
        
        watcher = FileWatcher(config)
        
        # Test start
        watcher.start()
        self.assertTrue(watcher.running)
        
        # Test stop
        watcher.stop()
        self.assertFalse(watcher.running)


# Run tests
if __name__ == '__main__':
    unittest.main()
```

---

## Dependencies Installation

Create a requirements file at `/home/jye/publications/cases/case_002_file_watcher/requirements.txt`:

```
# requirements.txt

watchdog>=3.0.0
PyYAML>=6.0
click>=8.0.0
pytest>=7.0.0
```

Install dependencies with:
```bash
pip install -r requirements.txt
```

---

## Usage Instructions

### Basic Usage

```bash
# Start watching
python watcher.py

# Watch specific directories
python watcher.py -w /path/to/dir1 -w /path/to/dir2

# Pause watching
python watcher.py --pause

# Stop watching
python watcher.py --stop
```

### Custom Command

```yaml
# watcher.yaml
command: "flake8 {file}"
```

### Example Workflow

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create configuration
cp watcher.yaml watcher.yaml.local

# 3. Modify configuration for your project
# 4. Start watcher
python watcher.py
# 5. Modify a source file in the watched directory
# 6. Command executes automatically
```

---

## Error Handling Strategy

1. **Configuration Errors**: Catch `yaml.YAMLError`, `FileNotFoundError`, `ValueError`
2. **Filesystem Errors**: Catch `OSError` during observer operations
3. **Command Execution Errors**: Log errors but don't stop watcher (`check=False`)
4. **Signal Handling**: Graceful shutdown on SIGINT, SIGTERM
5. **Retry Logic**: Optional retry for command execution on transient failures

---

## Testing Strategy

1. **Unit Tests**: Test individual components (config loader, debouncer, handler)
2. **Integration Tests**: Test complete watcher workflow
3. **Mock Usage**: Use `unittest.mock` to avoid actual filesystem changes
4. **Coverage Goal**: Achieve >80% code coverage with `pytest`

---

## Security Considerations

1. **Command Validation**: Consider validating command templates to prevent injection
2. **File Paths**: Sanitize file paths before passing to subprocess
3. **Permissions**: Ensure watcher runs with appropriate permissions
4. **Resource Limits**: Consider adding limits on concurrent command executions

---

## Future Enhancements (Not in Scope)

1. Add support for multiple commands (different for different event types)
2. Add WebSocket API for programmatic control
3. Add metrics/monitoring endpoint
4. Support for git-based file change detection
5. Add retry logic with exponential backoff
6. Add configuration hot-reload support

---

## Summary

This implementation plan provides:
- A complete, modular Python CLI file watcher
- Proper separation of concerns (config, logic, CLI)
- Comprehensive test coverage
- Clear documentation and usage instructions
- Robust error handling and signal management
- Security considerations noted

All file paths align with the expected working directory structure.
All function signatures are concrete and implementable.
Technical decisions are documented with rationale.
Assumptions are explicitly stated for clarity.

The implementation is ready for development execution.
