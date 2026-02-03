# Coding Conventions

**Analysis Date:** 2026-02-01

## Naming Patterns

**Files:**
- Lowercase with underscores: `device_manager.py`, `text_formatter.py`, `darwin_api.py`
- Mock files prefixed: `mock_indigo.py`, `mock_darwin.py`
- Test files prefixed: `test_*.py`, `conftest.py`
- Plugin main entry point: `plugin.py`

**Functions:**
- Snake case: `delayCalc()`, `routeUpdate()`, `getUKTime()`, `_fetch_station_board()`
- Private functions prefixed with underscore: `_clear_device_states()`, `_update_station_issues_flag()`, `_process_special_messages()`
- Descriptive verb-based names: `errorHandler()`, `createStationDict()`, `formatSpecials()`

**Variables:**
- Snake case: `api_key`, `darwin_url`, `station_dict`, `error_log_path`
- Constants in ALL_CAPS: `MAX_TRAINS_TRACKED`, `DEFAULT_UPDATE_FREQ_SECONDS`, `DARWIN_WSDL_DEFAULT`
- State dictionary keys: `stationCRS`, `destinationCRS`, `train1Dest`, `train1Est` (camelCase for device state keys)
- Private module variables prefixed with underscore: `_MODULE_FAILPYTZ`, `_MODULE_PYPATH`

**Types:**
- Dataclasses for immutable config: `ColorScheme(frozen=True)` in `constants.py`
- Model classes: `RuntimeConfig`, `DarwinAPIConfig`, `PluginConfig`, `PluginPaths`
- Enum for status values: `TrainStatus` enum with `.value` access for backward compatibility
- Service/Mock classes: `DarwinLdbSession`, `MockDevice`, `MockStationBoard`

## Code Style

**Formatting:**
- Python 3 style (no `print` statements in production code, use `logger`)
- UTF-8 encoding declared: `# coding=utf-8` at file top
- File header comments explain module purpose
- 120-character line length (inferred from code samples)

**Linting:**
- No explicit linting config detected (.eslintrc, .flake8, etc.)
- Type hints used consistently: `def __init__(self, plugin_id: str, log_dir: Path, debug: bool = False)`
- Optional/Union types explicitly annotated: `Optional[str]`, `Any`, `List`, `Dict`, `Tuple`

## Import Organization

**Order:**
1. System modules: `import os, sys, time, datetime, traceback, re`
2. Standard library with explicit imports: `from pathlib import Path`, `from typing import Dict, Tuple, Optional, List, Any`
3. Third-party libraries with fallback handling:
   ```python
   try:
       import pytz
   except ImportError:
       pytz = None
       _MODULE_FAILPYTZ = True
   ```
4. Local imports: `import constants`, `from config import PluginConfig`, `from darwin_api import darwin_api_retry`

**Path Aliases:**
- No explicit path aliases detected; uses relative imports within plugin bundle
- Test imports use `sys.path.insert()` to add directories: `sys.path.insert(0, str(plugin_dir))`

## Error Handling

**Patterns:**
- Module-level `try/except` for optional dependencies with graceful degradation:
  - `try: import pytz except ImportError: pass` - falls back to GMT
  - `try: from pydantic import BaseModel except ImportError: BaseModel = None` - disables validation if unavailable
- Function returns tuple `(success: bool, message: str)` for status reporting: `delayCalc()` returns `(has_problem, message)`
- Explicit error logging with context via `PluginLogger` class wrapping Python's logging module
- Exception chaining with `sys.exc_info()` capture and `traceback.print_exception()`

**Logging:**
```python
# Error logging with traceback:
plugin.plugin_logger.exception(error_msg)
plugin.plugin_logger.error(error_msg)

# Fallback to print if logger unavailable:
print(f"ERROR: {error_msg}", file=sys.stderr)
traceback.print_exception(*exc_info, limit=2, file=sys.stderr)
```

## Logging

**Framework:** Python's `logging` module with `RotatingFileHandler`

**Patterns:**
- Centralized logger class: `PluginLogger` wraps `logging.getLogger(f'Plugin.{plugin_id}')`
- Methods: `.debug()`, `.info()`, `.warning()`, `.error()`, `.exception()` (passes traceback)
- Log format: `'%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'`
- File rotation: 1MB max file size with 5 backup files retained
- Debug flag controls logging level: `logging.DEBUG` if debug enabled, else `logging.INFO`
- Logs written to: `/Library/Application Support/Perceptive Automation/Indigo [version]/Logs/UKTrains.log`

## Comments

**When to Comment:**
- Module docstrings explain purpose and scope
- Function docstrings with Args/Returns/Raises sections (Google-style)
- Complex logic with inline comments explaining "why" not "what"
- Section headers like `# ========== Darwin API Functions ==========` organize code logically

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Uses Python docstrings with type hints in function signatures instead
- Example:
  ```python
  def delayCalc(scheduled_time: str, estimated_time: str) -> Tuple[bool, str]:
      """Calculate delay between scheduled and estimated times.

      Args:
          scheduled_time: Scheduled time string (HH:MM format or status)
          estimated_time: Estimated time string (HH:MM format or status like "On time")

      Returns:
          Tuple of (has_problem: bool, message: str)
      """
  ```

## Function Design

**Size:**
- Small focused functions (30-50 lines typical)
- Examples: `getUKTime()` (18 lines), `delayCalc()` (40 lines), `_clear_device_states()` (12 lines)

**Parameters:**
- Use type hints for all parameters
- Prefer dataclass objects over many primitional parameters: `RuntimeConfig` bundles 4 params
- Optional parameters explicitly typed: `Optional[str] = None`
- Functions accept mock-friendly objects to enable testing

**Return Values:**
- Explicit return types: `-> bool`, `-> str`, `-> Tuple[bool, str]`, `-> Optional[Any]`
- Status functions return `(success: bool, message: str)` tuple for clarity
- Device update functions return `True` on success, `False` on failure with logging for errors

## Module Design

**Exports:**
- Clear separation of concerns: `darwin_api.py` for API calls, `text_formatter.py` for text processing, `device_manager.py` for device updates
- Public functions documented at module top with clear purpose
- Retry decorators abstracted to module level: `@darwin_api_retry()` applied selectively

**Barrel Files:**
- Not detected; direct imports from source modules preferred
- Example: `from darwin_api import darwin_api_retry, _fetch_station_board, _fetch_service_details, nationalRailLogin`

**Constants Module:**
- Centralized configuration: `constants.py` contains `MAX_TRAINS_TRACKED`, color schemes, file paths
- Enum for status strings with backward-compatible `.value` properties
- Dataclass for immutable configuration: `ColorScheme(frozen=True)`

## Configuration Management

**Approach:**
- Dataclasses for configuration objects: `PluginConfig`, `RuntimeConfig`, `PluginPaths`
- Pydantic models for validation when available (optional): `DarwinAPIConfig`, `UpdateConfig`, `ImageConfig`
- Factory methods for initialization: `RuntimeConfig.from_plugin_prefs(prefs)`, `PluginPaths.initialize(plugin_path)`
- Dictionary-based fallback for Indigo plugin preferences with explicit keys

**Indigo Plugin Prefs Keys:**
- API: `darwinAPI` (API key), `darwinSite` (WSDL URL)
- Image: `createMaps` (bool as string "true"/"false"), `imageFilename` (path)
- Colors: `forcolour`, `bgcolour`, `isscolour`, `cpcolour`, `ticolour` (hex strings)
- Update: `updateFreq` (seconds as string), `checkboxDebug1` (debug flag)

---

*Convention analysis: 2026-02-01*
