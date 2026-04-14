# CONCERNS

## Critical Bugs

### `indigo.debugger()` left in `runConcurrentThread()`
**File**: `plugin.py` line 789
**Impact**: CRITICAL — plugin will stall waiting for a debugger to attach every time it starts.
This call is unconditional inside the main polling loop, not guarded by any debug flag.

### Two conflicting logging systems
**Files**: `plugin.py` (`self.logger` vs `self.plugin_logger`)
`self.logger` is the Indigo built-in; `self.plugin_logger` is the custom `PluginLogger`.
Both are used inconsistently. In `runConcurrentThread()` there is `self.logger.info(...)` 
alongside `self.plugin_logger.debug(...)`. Risk of log messages being silenced or duplicated.

### `errorHandler` has duplicated placeholder copies
`errorHandler` is defined at module level in `plugin.py` as the real implementation.
Identical placeholder stubs also exist in `darwin_api.py`, `device_manager.py`, and
`image_generator.py`. The stubs only print to stderr — they do not use the rotating
file logger. Any call to `errorHandler` inside those modules silently skips proper logging.

## Tech Debt

### Dependencies not bundled in `Contents/Packages/`
zeep, lxml, requests, pytz, pydantic, tenacity, Pillow all require manual `pip install`.
Standard Indigo packaging practice bundles them. This breaks on fresh Indigo installs
and after Python upgrades.

### `tinydb` vendored but unused
`tinydb/` is fully bundled in `Server Plugin/` but no production code imports it.
Dead weight that will confuse future maintainers.

### Legacy global constants in `constants.py`
```python
STATUS_ON_TIME = TrainStatus.ON_TIME.value  # deprecated
STATUS_CANCELLED = TrainStatus.CANCELLED.value  # deprecated
```
These remain "for backward compatibility" with no removal plan.

### Station code parsing bug in `selectStation()`
`stationList` is built as `line[4:]` (skipping 4 chars = `CRS,` prefix), but the CSV
format is `CRS,Station Name` — CRS codes are 3 chars + comma = 4 chars. This works
for most codes but will silently fail for any station whose name starts differently.
`createStationDict()` uses the same `line[4:]` offset for name extraction.

### Image generation limited to 5 trains displayed
`constants.MAX_TRAINS_DISPLAYED = 5` while `MAX_TRAINS_TRACKED = 10`. The classic board
renderer only renders the first 5 even though up to 10 are stored in device states.
No current plans to reconcile this.

### No arrivals board support
Only departures are fetched (`include_arrivals=False` hardcoded in `_fetch_station_board()`).

### HTML in NRCC messages not fully stripped
`formatSpecials()` in `text_formatter.py` removes HTML tags and some entities but uses
a simple regex. Malformed HTML, attribute patterns like `href=`, or unusual entities
can leak into the output text. Acknowledged in `CLAUDE.md` known limitations.

### `runConcurrentThread()` calls `self.shutdown()` on exit
At the end of the `while True` loop (after `StopThread` breaks it), `self.shutdown()` is
called manually. Indigo already calls `shutdown()` — this may result in double-shutdown.

### Version checker remnants
`plugin.py` line 465 sets `travelVersionFile = 'https://www.dropbox.com/...'` but is never
used (the `self.updater` initialization was removed). Dead reference.

### `validatePrefsConfigUi()` called in `__init__`
Calling preference validation inside `__init__` is non-standard Indigo pattern. This should
be driven by Indigo's UI callback, not the constructor.

## TODOs in Source

- `nredarwin/webservice.py` line 11: `# TODO - timeouts and error handling`
- `nredarwin/webservice.py` line 207: `# TODO - would be nice to strip HTML from NRCC messages`
- `nredarwin/webservice.py` line 364: `# TODO - Adhoc alerts, datetime inflators`
- `image_generator.py` line 334: `DEBUG:` print to stderr during service hours for missing platforms

## Fragile Areas

### Time parsing in `delayCalc()`
The first-character check `scheduled_time[0] not in '012'` is fragile — a time like `23:xx`
would pass, but an unusual Darwin response string could produce incorrect delay calculations.

### `text2png_modern.py` parsing relies on dash-padding
If `_format_station_board()` changes its padding length below 3 dashes, `re.split(r'-{3,}', line)`
in `text2png_modern.py` would fail to parse. The two renderers are coupled by this format.

### `trainparameters.txt` written on every polling cycle
The parameters file is overwritten at the top of each `runConcurrentThread()` loop with
hardcoded string: `f'{colors.foreground},{colors.background},...,9,3,3,720'`. Any mid-cycle
subprocess call reads an already-valid file, but this is not atomic.

### Subprocess Python path hardcoded
`PYTHON3_PATH = '/Library/Frameworks/Python.framework/Versions/Current/bin/python3'`
If Indigo uses a different Python install location (e.g., after macOS upgrade), image
generation silently fails with `FileNotFoundError`.
