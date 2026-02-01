# Architecture

**Analysis Date:** 2026-02-01

## Pattern Overview

**Overall:** Modular Layered Architecture

**Key Characteristics:**
- Event-driven plugin lifecycle managed by Indigo framework
- Concurrent polling pattern for periodic API updates
- Separation of concerns with dedicated modules for each functional area
- Asynchronous subprocess spawning for image generation (avoids shared library conflicts)
- State-based device model mapping to Indigo's device/state abstraction

## Layers

**Plugin Base Layer:**
- Purpose: Indigo plugin lifecycle management and device control
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py` (main class at line 659+)
- Contains: Plugin class extending `indigo.PluginBase`, startup/shutdown hooks, concurrent thread loop
- Depends on: All other modules for delegated functionality
- Used by: Indigo framework; entry point for all plugin operations

**API Wrapper Layer:**
- Purpose: Encapsulate Darwin SOAP webservice communication with retry logic
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/darwin_api.py`
- Contains: `nationalRailLogin()`, `_fetch_station_board()`, `_fetch_service_details()` with retry decorators
- Depends on: `nredarwin.webservice.DarwinLdbSession` (ZEEP SOAP client)
- Used by: Device manager layer for fetching real-time train data

**SOAP Client Library:**
- Purpose: Low-level SOAP communication with National Rail Darwin API
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/nredarwin/webservice.py`
- Contains: `DarwinLdbSession` class wrapping ZEEP client with authentication header building
- Depends on: `zeep` (SOAP client library), `requests` (HTTP transport)
- Used by: Darwin API wrapper layer

**Device Management Layer:**
- Purpose: Update Indigo device states with train data; aggregate station-level status
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/device_manager.py`
- Contains: `_process_train_services()`, `_update_train_device_states()`, `_clear_device_states()`, calling point processing
- Depends on: Text formatter (for delay calculations), Darwin API wrapper (for service details)
- Used by: Main plugin loop via `routeUpdate()`

**Text Formatting Layer:**
- Purpose: Pure utility functions for time/date handling and delay calculations
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/text_formatter.py`
- Contains: `getUKTime()`, `delayCalc()`, `formatSpecials()` (HTML stripping)
- Depends on: `pytz` (optional; falls back to GMT), `constants` for status enums
- Used by: Device manager and image generator layers

**Image Generation Layer:**
- Purpose: Coordinate text file writing and subprocess spawning for PNG board generation
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/image_generator.py`
- Contains: `_write_departure_board_text()`, `_generate_departure_image()`, `_format_station_board()`
- Depends on: `text2png.py` subprocess (separate Python process), text formatter (for delays)
- Used by: Main route update flow

**Configuration Layer:**
- Purpose: Centralize configuration management and path resolution
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/config.py`
- Contains: `RuntimeConfig`, `PluginConfig`, `PluginPaths` dataclasses with validation
- Depends on: `constants` (for defaults)
- Used by: Plugin main class and concurrent thread for reading preferences

**Constants Layer:**
- Purpose: Single source of truth for magic numbers, API endpoints, color schemes
- Location: `UKTrains.indigoPlugin/Contents/Server Plugin/constants.py`
- Contains: Train limits, Darwin API config, image dimensions, color schemes as dataclasses
- Depends on: Nothing (leaf module)
- Used by: All other modules

## Data Flow

**Route Update Cycle (main business process):**

1. **Trigger:** Plugin concurrent thread at line 745 loops every N seconds
2. **Load Config:** RuntimeConfig loaded from pluginPrefs
3. **For each device:** Call `routeUpdate()` at line 281
4. **Authenticate:** `nationalRailLogin()` opens SOAP session (darwin_api.py:150)
5. **Fetch Board:** `_fetch_station_board()` queries Darwin API for station departures (darwin_api.py:82)
6. **Process Services Loop:** For each train (up to 10):
   - `_fetch_service_details()` fetches full service info with calling points (darwin_api.py:124)
   - `_update_train_device_states()` updates device states with time/delay/operator info (device_manager.py:137)
   - `_append_train_to_image()` formats train for image output (image_generator.py)
7. **Update Station Status:** `_update_station_issues_flag()` aggregates all trains for delays flag (device_manager.py:44)
8. **Generate Image:** Subprocess spawned to convert text file to PNG via `text2png.py` (image_generator.py:52)
9. **Next Cycle:** Sleep for refresh_freq seconds (plugin.py:830)

**State Management:**

- Device state: Organized as train1-train10 with suffixes (Dest, Sch, Est, Delay, Issue, Reason, Calling, Op)
- Station-level state: stationIssues boolean aggregates all train Issues; deviceStatus shows human-readable status
- Config state: RuntimeConfig constructed fresh each cycle from pluginPrefs
- File state: Text and image files written to disk for control page display

## Key Abstractions

**StationBoard (Darwin API response):**
- Purpose: Represents all departures from a given station
- Examples: `device_manager.py` line 213 accesses `board.train_services` list
- Pattern: Navigated via getattr() for null-safety

**ServiceItem (Darwin API response):**
- Purpose: Single train service with basic info (destination, times, operator)
- Examples: `device_manager.py` line 157-160 extracts destination_text, std, etd
- Pattern: Short-lived objects from API, stored as device state strings

**ServiceDetails (Darwin API response):**
- Purpose: Full service info including calling points and cancellation/delay reasons
- Examples: `device_manager.py` line 108-113 accesses subsequent_calling_points
- Pattern: Fetched separately for each service after main board query

**PluginPaths (configuration object):**
- Purpose: Centralized path management with lazy directory creation
- Examples: `plugin.py` line 764 `self.paths.get_parameters_file()`
- Pattern: Immutable dataclass with convenience getters

**ColorScheme (configuration object):**
- Purpose: Immutable color configuration for image generation
- Examples: `constants.py` line 76-85 defines defaults; `config.py` line 62-68 loads from prefs
- Pattern: Passed through layers via RuntimeConfig

## Entry Points

**Plugin Startup:**
- Location: `plugin.py:705 def startup()`
- Triggers: Indigo framework calls when plugin enabled
- Responsibilities: Initialize logger, load preferences, register device state changes

**Concurrent Thread Loop:**
- Location: `plugin.py:745 def runConcurrentThread()`
- Triggers: Indigo framework spawns on plugin load
- Responsibilities: Infinite loop polling each route device at refresh_freq interval

**Device Add/Modify Callbacks:**
- Location: `plugin.py:536 def deviceStartComm()` and `deviceStopComm()`
- Triggers: Indigo framework when user adds/removes/disables device
- Responsibilities: Track active devices for polling loop

**Action Callbacks:**
- Location: `plugin.py:650-703` (sensor action handlers)
- Triggers: Indigo UI or automation rules when user requests action
- Responsibilities: Validate/log read-only sensor requests (no actual control)

## Error Handling

**Strategy:** Graceful degradation with per-service fault tolerance

**Patterns:**

- API Retry: Exponential backoff via tenacity decorator (darwin_api.py:47-78) — up to 3 attempts on transient errors
- Silent Service Skip: When `_fetch_service_details()` fails, skip that train but continue with others (device_manager.py:222-224)
- Device Skip: If device update fails (`routeUpdate()` returns False), mark device as "Awaiting update" and move to next device (plugin.py:806-811)
- Fallback Timezone: If pytz import fails, use GMT instead of BST (text_formatter.py:31-38)
- Graceful Dependency Handling: If pydantic or tenacity missing, validate manually or skip retry logic (plugin.py:40-56, darwin_api.py:62-67)

## Cross-Cutting Concerns

**Logging:** PluginLogger class at `plugin.py:74-100` writes rotating file logs to Indigo Logs directory; debug flag controls verbosity throughout

**Validation:** Pydantic models in `config.py:154-241` validate API keys, paths, update frequency; device properties validated in Indigo UI via Devices.xml schema

**Authentication:** Darwin API token passed via ZEEP SOAP header (nredarwin/webservice.py:52-71); no session persistence (new session per route update)

**Time Handling:** All times displayed in UK timezone using pytz (text_formatter.py:20-38); Darwin API returns times as strings requiring parsing

**Image Generation:** Subprocess isolation to avoid PIL/library conflicts with Indigo's embedded Python (image_generator.py:52-95); text file intermediary used for IPC

---

*Architecture analysis: 2026-02-01*
