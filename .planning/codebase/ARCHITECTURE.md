# ARCHITECTURE

## Plugin Lifecycle

Standard Indigo `PluginBase` subclass in `plugin.py`:

```
__init__()      — initialize PluginConfig, PluginPaths, PluginLogger, Pydantic validation
startup()       — update log level, iterate devices for state refresh
runConcurrentThread()  — main polling loop (runs forever until StopThread)
shutdown()      — log shutdown
deviceStartComm()  — set sqlLoggerIgnoreStates="*", sync deviceActive state
deviceStopComm()   — no-op
```

`runConcurrentThread()` is the heartbeat. Each iteration:
1. Loads `RuntimeConfig` from `self.pluginPrefs`
2. Writes `trainparameters.txt` (color/font config for image generation)
3. Iterates `indigo.devices.iter('self.trainTimetable')`
4. Calls `routeUpdate(dev, ...)` for each active device
5. Sleeps `runtime_config.refresh_freq` seconds (default 60, min 30, max 600)

**Known issue**: `indigo.debugger()` is called unconditionally at line 789 inside
`runConcurrentThread()` — this will pause the plugin waiting for a debugger connection.

## Device Types

One device type: `trainTimetable` (defined in `Devices.xml`).

Each device represents a single departure route:
- **Origin station**: CRS code + long name stored in device states
- **Destination**: CRS code + long name (or `ALL` for all destinations)
- **Active toggle**: `routeActive` prop / `deviceActive` state
- **States**: 10 train slots × 9 states each + station-level metadata

Per-train states (trainN prefix, N=1..10):
`Dest`, `Op`, `Sch`, `Est`, `Delay`, `Issue` (bool), `Reason`, `Calling`, `Platform`

Station-level states:
`stationLong`, `stationCRS`, `destinationLong`, `destinationCRS`, `timeGenerated`,
`stationMessages`, `stationIssues` (bool), `imageGenerationStatus`, `imageGenerationError`,
`image_content_hash`, `deviceStatus`, `deviceActive`

Device status icons:
- `SensorOn` = on time
- `SensorTripped` = delays/issues
- `SensorOff` = inactive or update failed

SQL Logger is disabled for all states (`sqlLoggerIgnoreStates = "*"`) because frequent
updates across 90 states cause errors.

## Data Flow

```
runConcurrentThread()
  └─ routeUpdate(dev, api_key, darwin_url, paths, logger, plugin_prefs)   [plugin.py]
       ├─ nationalRailLogin(url, key)                                       [darwin_api.py]
       ├─ _clear_device_states(dev)                                        [device_manager.py]
       ├─ _fetch_station_board(session, start_crs, end_crs)                [darwin_api.py]
       ├─ _process_train_services(dev, session, board, image_content, ...) [device_manager.py]
       │    └─ for each service:
       │         ├─ _fetch_service_details(session, service_id)            [darwin_api.py]
       │         ├─ _update_train_device_states(dev, trainNum, ...)        [device_manager.py]
       │         └─ _append_train_to_image(image_content, ...)             [image_generator.py]
       ├─ _update_station_issues_flag(dev)                                 [device_manager.py]
       ├─ _process_special_messages(board, dev)                            [device_manager.py]
       ├─ _format_station_board(image_content, ...)                        [image_generator.py]
       ├─ _write_departure_board_text(text_path, ...)                      [image_generator.py]
       ├─ compute_board_content_hash(text_path, params_path)               [image_generator.py]
       └─ _generate_departure_image(...)                                   [image_generator.py]
            └─ _generate_single_image(..., board_style='classic'|'modern')
                 └─ subprocess: python3 text2png.py [args]
                      └─ (if modern) text2png_modern.py
```

## Image Generation Subsystem

Images are generated in a **separate Python subprocess** to avoid shared library conflicts
between Pillow and Indigo's embedded Python environment.

- Subprocess command: `PYTHON3_PATH text2png.py <image_path> <text_path> <params_path> YES|NO classic|modern`
- `PYTHON3_PATH` = `/Library/Frameworks/Python.framework/Versions/Current/bin/python3` (never `sys.executable`)
- `text2png.py` dispatches to `text2png_modern.py` if `board_style == 'modern'`
- Exit codes: 0=success, 1=file I/O error, 2=PIL error, 3=config error
- Timeout: 10 seconds

**Content-hash optimization**: SHA-256 of board text + parameters file. Image regeneration
is skipped if hash matches `image_content_hash` device state (avoids redundant disk writes).

### Board Styles

| Style | Dimensions | File suffix | Renderer |
|-------|-----------|-------------|----------|
| Classic | 720×400px landscape | `{CRS1}{CRS2}timetable.png` | `text2png.py` (original) |
| Modern | 414×variable portrait | `{CRS1}{CRS2}timetable_mobile.png` | `text2png_modern.py` |

Both styles read the same `.txt` text file written by `_write_departure_board_text()`.

Output directory: user-configured `imageFilename` pref, defaulting to `~/Documents/IndigoImages/`.

## Configuration Architecture

Three layers:
1. **`PluginConfig` dataclass** (`config.py`) — mutable runtime state (debug flag, paths, station dict)
2. **`RuntimeConfig` dataclass** (`config.py`) — snapshot of plugin prefs per polling cycle
3. **`PluginConfiguration` Pydantic model** (`config.py`) — startup validation (optional, skipped if pydantic absent)

**`PluginPaths` dataclass** (`config.py`) — all file paths centralized, auto-detects newest
Indigo version folder under `~/Library/Application Support/Perceptive Automation/`.

## Module Decomposition

`plugin.py` imports from five supporting modules:
- `config.py` — dataclasses + Pydantic models
- `constants.py` — magic numbers, enums, color schemes
- `darwin_api.py` — SOAP authentication and fetching
- `device_manager.py` — state clearing, updating, calling points
- `image_generator.py` — text file writing, subprocess dispatch, content hashing
- `text_formatter.py` — pure functions: `getUKTime()`, `delayCalc()`, `formatSpecials()`
