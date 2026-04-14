# CONVENTIONS

## Python Style

- Python 3 syntax throughout (f-strings, `pathlib.Path`, type hints, dataclasses)
- `# coding=utf-8` header on all source files
- Type hints used in function signatures for new/refactored code (not uniformly applied in older code)
- `from typing import Dict, Tuple, Optional, List, Any` imports are common
- `@dataclass` and `@dataclass(frozen=True)` used for config/color objects in `constants.py` and `config.py`
- Enums used for train status codes: `TrainStatus` in `constants.py`

## Module-Level Imports with Graceful Fallback

Optional dependencies are wrapped in try/except at module level:

```python
try:
    from pydantic import BaseModel, Field, field_validator, HttpUrl
except ImportError:
    BaseModel = None
    ...
```

Code paths that use optional deps check `if BaseModel is not None:` or equivalent.
This pattern applies to: `pydantic`, `tenacity`, `pytz`.

Hard-required deps (zeep, nredarwin, functools, indigo) exit via `sys.exit(N)` if missing.

## Logging

**Two parallel logging systems** — both are in use:

1. **`self.logger`** (Indigo built-in, via `PluginBase`) — writes to Indigo Event Log. Used for
   a handful of legacy calls (e.g., `self.logger.info(...)` in `runConcurrentThread()`).

2. **`self.plugin_logger`** (custom `PluginLogger` class in `plugin.py`) — `RotatingFileHandler`
   writing to `UKTrains.log`. Used for most new/refactored code paths.

The `PluginLogger` wrapper exposes: `debug()`, `info()`, `warning()`, `error()`, `exception()`, `set_debug()`.

Debug logging is controlled by plugin pref `checkboxDebug1`. The `set_debug()` method is called
on `startup()` and at the start of each polling cycle.

Module-level functions (`errorHandler`, placeholder handlers in `darwin_api.py`, `device_manager.py`,
`image_generator.py`) fall back to `print(..., file=sys.stderr)` when the plugin logger is
not available.

## Error Handling

- SOAP/network errors: caught as `(WebFault, Exception)`, logged, `routeUpdate()` returns `False`
- Missing station file: `sys.exit(1)` — hard stop
- Missing required deps: `sys.exit(N)` with distinct codes (3..7) per dep
- Image generation errors: caught by subprocess exit code, logged, device state updated
- Per-service errors: isolated — one service failure does not abort remaining services
- `logger.exception()` used for unexpected exceptions (includes full traceback)

## Device State Updates

Always via `dev.updateStateOnServer(key, value=...)`. Never write to `dev.states` directly.
All states defined in `Devices.xml` with `readonly="YES"` (plugin is the only writer).

## Plugin Prefs vs Device Props

Critical distinction documented in `CLAUDE.md`:
- Plugin-wide settings: `self.pluginPrefs.get(key, default)` — available only in Plugin class methods
- Device-specific settings: `device.pluginProps.get(key, default)`
- Module-level functions receive `plugin_prefs` as explicit parameter — never access `self`

## Path Handling

All file paths use `pathlib.Path` objects. String conversion (`str(path)`) only at subprocess
call boundaries. Directory creation via `path.mkdir(parents=True, exist_ok=True)`.

## Subprocess Calls

Always use `constants.PYTHON3_PATH` (hardcoded `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`).
Never use `sys.executable` — it points to `IndigoPluginHost3.app`.
Use `subprocess.run(..., capture_output=True, text=True, timeout=10, check=False)`.

## Departure Board Text Format

Dash-padded CSV written by `_write_departure_board_text()`:
- Service lines: `Destination-------Platform-----Time-----Status---Operator`
- Status lines: `Status:<message>`
- Calling points lines: `>>> Station(HH:MM) Station(HH:MM) ...`

Both `text2png.py` and `text2png_modern.py` parse this format.
`text2png_modern.py` uses `re.split(r'-{3,}', line)` to split on 3+ consecutive dashes.
