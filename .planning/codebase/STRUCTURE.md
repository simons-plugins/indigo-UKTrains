# Codebase Structure

**Analysis Date:** 2026-02-01

## Directory Layout

```
UK-Trains/                                          # Repository root
├── UKTrains.indigoPlugin/                          # Indigo plugin bundle
│   ├── Contents/
│   │   ├── Info.plist                              # Plugin metadata (bundle ID, version)
│   │   └── Server Plugin/
│   │       ├── plugin.py                           # Main plugin class & lifecycle
│   │       ├── config.py                           # Configuration dataclasses
│   │       ├── constants.py                        # Magic numbers & enums
│   │       ├── darwin_api.py                       # Darwin API wrapper with retry logic
│   │       ├── device_manager.py                   # Device state updates
│   │       ├── image_generator.py                  # PNG generation coordination
│   │       ├── text_formatter.py                   # Pure utility functions
│   │       ├── text2png.py                         # Subprocess for PIL image generation
│   │       ├── nredarwin/                          # SOAP client library
│   │       │   ├── __init__.py
│   │       │   └── webservice.py                   # DarwinLdbSession ZEEP wrapper
│   │       ├── tinydb/                             # Bundled TinyDB library
│   │       ├── Devices.xml                         # Device type definitions (trainTimetable)
│   │       ├── Actions.xml                         # Action definitions
│   │       ├── MenuItems.xml                       # Plugin menu items
│   │       ├── PluginConfig.xml                    # Plugin settings UI
│   │       ├── stationCodes.txt                    # CRS code to station name lookup
│   │       ├── BoardFonts/                         # Fonts for image generation
│   │       └── trainparameters.txt                 # Color/layout config for image gen
│
├── tests/                                          # Test suite
│   ├── conftest.py                                 # pytest fixtures & configuration
│   ├── mocks/
│   │   ├── mock_darwin.py                          # Mock Darwin API for testing
│   │   └── mock_indigo.py                          # Mock Indigo framework objects
│   ├── unit/
│   │   ├── test_text_formatting.py                 # Text utility tests
│   │   └── test_time_calculations.py               # Time/delay calculation tests
│   ├── integration/
│   │   ├── test_live_darwin_api.py                 # Live API tests
│   │   └── test_route_update.py                    # Full route update flow tests
│   └── fixtures/
│       └── darwin_responses/                       # SOAP response samples
│
├── .planning/                                      # GSD planning documents
│   └── codebase/
│       ├── ARCHITECTURE.md                         # This architecture document
│       ├── STRUCTURE.md                            # This structure document
│       ├── CONVENTIONS.md                          # Coding patterns & style
│       ├── TESTING.md                              # Test framework & patterns
│       ├── STACK.md                                # Technology stack
│       ├── INTEGRATIONS.md                         # External dependencies
│       └── CONCERNS.md                             # Technical debt & issues
│
├── .github/workflows/                              # CI/CD pipelines
├── README.md                                       # Project overview
├── CLAUDE.md                                       # Development guidance
├── BUGFIX_SUMMARY.md                               # Recent fixes
├── DIAGNOSIS_SUMMARY.md                            # Debugging logs
├── TESTING_GUIDE.md                                # Manual test procedures
└── requirements.txt                                # Python dependencies
```

## Directory Purposes

**UKTrains.indigoPlugin/Contents/Server Plugin:**
- Purpose: Main plugin logic and Indigo integration
- Contains: Plugin class, API wrappers, device management, image generation
- Key files: `plugin.py` (entry point), `config.py` (settings), `darwin_api.py` (API layer)

**tests/unit:**
- Purpose: Pure function unit tests without Indigo or Darwin dependencies
- Contains: Text formatter tests, time calculation tests
- Key files: `test_text_formatting.py`, `test_time_calculations.py`

**tests/integration:**
- Purpose: Full flow tests with mock or real Darwin API
- Contains: Route update flow tests, live API connection tests
- Key files: `test_route_update.py`, `test_live_darwin_api.py`

**tests/mocks:**
- Purpose: Test doubles for Indigo framework and Darwin API
- Contains: Mock objects matching real API interfaces
- Key files: `mock_indigo.py` (device/state mock), `mock_darwin.py` (SOAP response mock)

**nredarwin/:**
- Purpose: SOAP client library for Darwin webservice
- Contains: Zeep-based client with header building and service binding
- Key files: `webservice.py` (DarwinLdbSession class)

**tinydb/:**
- Purpose: Bundled embedded JSON database library
- Contains: TinyDB implementation (currently unused in active code)
- Key files: Middleware and database implementations

**BoardFonts/:**
- Purpose: Font files for departure board image generation
- Contains: Dot Matrix and other monospace fonts for board display
- Key files: Accessible via `PluginPaths.fonts_dir` path

## Key File Locations

**Entry Points:**
- `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py`: Main Plugin class (line 659+), extends indigo.PluginBase
- `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py:745`: `runConcurrentThread()` — infinite loop entry point

**Configuration:**
- `UKTrains.indigoPlugin/Contents/Info.plist`: Bundle identifier, plugin version, author
- `UKTrains.indigoPlugin/Contents/Server Plugin/PluginConfig.xml`: Plugin settings dialog UI
- `UKTrains.indigoPlugin/Contents/Server Plugin/config.py`: RuntimeConfig, PluginConfig, PluginPaths dataclasses

**Core Logic:**
- `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py:281`: `routeUpdate()` — main business logic orchestrator
- `UKTrains.indigoPlugin/Contents/Server Plugin/device_manager.py:185`: `_process_train_services()` — train processing loop
- `UKTrains.indigoPlugin/Contents/Server Plugin/darwin_api.py:150`: `nationalRailLogin()` — SOAP authentication

**Device Definitions:**
- `UKTrains.indigoPlugin/Contents/Server Plugin/Devices.xml`: Device type "trainTimetable" with 10 train states
- `UKTrains.indigoPlugin/Contents/Server Plugin/Actions.xml`: Custom action definitions

**Testing:**
- `tests/conftest.py`: pytest configuration with fixtures
- `tests/mocks/mock_indigo.py`: Mock Indigo device/state objects
- `tests/mocks/mock_darwin.py`: Mock Darwin SOAP responses

**Data Files:**
- `UKTrains.indigoPlugin/Contents/Server Plugin/stationCodes.txt`: Station CRS code ↔ name mapping
- `UKTrains.indigoPlugin/Contents/Server Plugin/trainparameters.txt`: Image generation parameters (colors, fonts)
- Generated files: `{CRS}{CRS}departureBoard.txt`, `{CRS}{CRS}timetable.png` (in user Documents or configured path)

## Naming Conventions

**Files:**
- `plugin.py`: Main plugin class (Indigo standard)
- `*_manager.py`: Manager classes (device_manager.py, not device.py)
- `*_api.py`: API wrapper modules (darwin_api.py)
- `*_formatter.py`: Pure utility modules (text_formatter.py)
- `*_generator.py`: Generators/builders (image_generator.py)
- `test_*.py`: Test files (pytest convention)
- `mock_*.py`: Mock objects for testing
- `conftest.py`: pytest configuration

**Functions:**
- `routeUpdate()`: Main orchestrator (camelCase, public)
- `_process_train_services()`: Internal helper (leading underscore prefix, camelCase)
- `_fetch_station_board()`: API wrappers (leading underscore, camelCase)
- `delayCalc()`: Pure utilities (camelCase, no prefix)
- `getUKTime()`: Accessor functions (get/set prefix, camelCase)

**Variables:**
- `stationStartCrs`, `stationEndCrs`: CRS codes (camelCase, descriptive)
- `dev`: Indigo device object (abbreviated due to frequent use)
- `station_dict`, `station_codes`: Dictionaries (snake_case when from config)
- `MAX_TRAINS_TRACKED`: Constants (UPPER_SNAKE_CASE)
- `departures_found`: Boolean flags (snake_case, descriptive)

**Types/Classes:**
- `Plugin(indigo.PluginBase)`: Main plugin class
- `RuntimeConfig`: Configuration dataclass
- `PluginPaths`: Path management dataclass
- `DarwinLdbSession`: SOAP client wrapper
- `PluginLogger`: Custom logger wrapper
- `TrainStatus`: Enum for status constants

**Device States:**
- `train{N}Dest`, `train{N}Sch`, `train{N}Est`: Per-train states (1-10 trains)
- `stationIssues`: Boolean flag (no train number prefix)
- `deviceActive`: Device enable/disable flag
- `deviceStatus`: Human-readable status string

## Where to Add New Code

**New Feature (route logic/Darwin API):**
- Primary code: `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py` or new module
- If new API call: Add wrapper in `darwin_api.py` with retry decorator
- If new device state: Add definition in `Devices.xml`, update in `device_manager.py`
- Tests: `tests/integration/test_route_update.py` for flow tests

**New Component/Module:**
- Implementation: `UKTrains.indigoPlugin/Contents/Server Plugin/{feature}_manager.py` or `{feature}_api.py`
- Import in: `plugin.py` main file (see import block at line 232-254)
- Tests: Create `tests/unit/test_{feature}.py` for unit tests

**Utilities:**
- Pure functions: `text_formatter.py` (already contains time, delay, formatting utilities)
- Config: `config.py` (add new dataclass or Pydantic model)
- Constants: `constants.py` (add to enums or dataclasses)

**Tests:**
- Unit tests: `tests/unit/test_*.py` for pure functions
- Integration tests: `tests/integration/test_*.py` for full flows
- Fixtures: `tests/fixtures/darwin_responses/` for SOAP response samples
- Mocks: `tests/mocks/mock_*.py` for test doubles

## Special Directories

**BoardFonts/:**
- Purpose: Font files for image generation
- Generated: No (bundled with plugin)
- Committed: Yes
- Access: Via `config.PluginPaths.fonts_dir`

**tinydb/:**
- Purpose: Embedded JSON database library
- Generated: No (bundled dependency)
- Committed: Yes
- Usage: Currently not used in active code paths

**Generated Image Output (configurable):**
- Purpose: PNG departure board images and text intermediaries
- Default location: `~/Documents/IndigoImages/`
- User-configurable: Via PluginConfig.xml `imageFilename` setting
- Lifetime: Overwritten on each route update cycle
- Not committed: These are runtime artifacts

**.planning/codebase/:**
- Purpose: GSD codebase mapping documents (architecture, structure, conventions, etc.)
- Generated: By GSD mapping command
- Committed: Yes (tracking design decisions and patterns)

## Import Organization

**Standard pattern in plugin.py (lines 30-70):**
1. System modules: `os`, `sys`, `time`, `datetime`, `traceback`, `re`, `subprocess`, `dataclasses`, `pathlib`, `typing`, `logging`
2. Try/except optional: `pydantic`, `tenacity`, `indigo` (required)
3. Local module: `import constants`
4. Conditional: `import pytz`

**Module import pattern in device_manager.py:**
1. System: `typing`
2. Local config: `import constants`
3. Local functions: `from text_formatter import ...`
4. Local modules: `from darwin_api import ...`

**Path aliases:**
- None used; all imports relative to plugin module directory
- Absolute paths used for file system operations via `Path()` objects

## Path Resolution

All paths centralized in `config.PluginPaths`:

- Plugin bundle: Detected at runtime via `_MODULE_PYPATH` (plugin.py:230)
- Station codes: `plugin_root / 'stationCodes.txt'`
- Fonts: `plugin_root / 'BoardFonts' / 'MFonts'`
- Image output: User-configured via `imageFilename` pref, defaults to `~/Documents/IndigoImages/`
- Logs: Dynamic Indigo version detection (e.g., `~/Library/Application Support/Perceptive Automation/Indigo 2024.1/Logs/`)
- Parameters: `plugin_root / 'trainparameters.txt'`

---

*Structure analysis: 2026-02-01*
