# STRUCTURE

## Repository Root

```
UK-Trains/
├── UKTrains.indigoPlugin/          # Indigo plugin bundle
├── tests/                          # Test suite (pytest)
├── CLAUDE.md                       # Project-specific Claude Code guidance
├── README.md
├── TESTING_GUIDE.md
├── RUN_LIVE_TEST.md
├── test_darwin_live.py             # Ad-hoc live API test script (root level)
├── inspect_wsdl.py                 # Dev utility to inspect Darwin WSDL
├── .env                            # API key (not committed)
├── .env.example                    # Template for .env
└── license.txt
```

## Plugin Bundle

```
UKTrains.indigoPlugin/
└── Contents/
    ├── Info.plist                  # Plugin metadata (CFBundleIdentifier, PluginVersion)
    └── Server Plugin/              # All Python source and assets
        ├── plugin.py               # Main Plugin class + routeUpdate() + PluginLogger
        ├── config.py               # PluginConfig, PluginPaths, RuntimeConfig, Pydantic models
        ├── constants.py            # Magic numbers, TrainStatus enum, ColorScheme dataclasses
        ├── darwin_api.py           # nationalRailLogin(), _fetch_station_board(), _fetch_service_details()
        ├── device_manager.py       # Device state management functions
        ├── image_generator.py      # PNG generation coordination + content hashing
        ├── text_formatter.py       # Pure text utilities: getUKTime(), delayCalc(), formatSpecials()
        ├── text2png.py             # Classic board renderer (720×400, Dot Matrix font, green-on-black)
        ├── text2png_modern.py      # Modern board renderer (414×variable, card-based, WCAG AA colors)
        ├── Devices.xml             # trainTimetable device type definition
        ├── Actions.xml             # Plugin action definitions
        ├── MenuItems.xml           # Plugin menu items
        ├── PluginConfig.xml        # Plugin preferences UI
        ├── stationCodes.txt        # CRS→Station Name lookup (~2700+ stations, CSV format)
        ├── trainparameters.txt     # Runtime-written color/font config for image renderer
        ├── requirements.txt        # Production pip dependencies
        ├── __init__.py
        ├── BoardFonts/             # Font assets for classic board renderer
        │   └── MFonts/             # Dot Matrix and other monospace fonts
        ├── nredarwin/              # Vendored Darwin SOAP wrapper
        │   ├── __init__.py
        │   └── webservice.py       # DarwinLdbSession class
        ├── tinydb/                 # Vendored TinyDB (present, not actively used)
        ├── myImageErrors.txt       # Legacy image subprocess error log (superseded by RotatingFileHandler)
        ├── myImageOutput.txt       # Legacy image subprocess output log
        └── test_zeep_connection.py # Ad-hoc dev script for testing zeep connection
```

## Tests

```
tests/
├── conftest.py                     # Session fixtures, mock injection, helpers
├── pytest.ini                      # Pytest config, markers, pythonpath
├── requirements-test.txt           # Test-only pip dependencies
├── run_tests.sh                    # Shell script to run test suite
├── __init__.py
├── unit/
│   ├── test_text_formatting.py     # Tests for delayCalc(), formatSpecials(), getUKTime()
│   └── test_time_calculations.py   # Time arithmetic unit tests
├── integration/
│   ├── test_route_update.py        # routeUpdate() integration tests (mocked Darwin)
│   └── test_live_darwin_api.py     # Live API tests (marked live_api, skipped by default)
├── mocks/
│   ├── mock_indigo.py              # MockIndigo module (injected as sys.modules['indigo'])
│   └── mock_darwin.py              # Factory functions for mock Darwin sessions/services
└── fixtures/
    └── darwin_responses/           # Static response fixtures for tests
```

## Output Files (runtime, not in repo)

Written to the user-configured image directory (default `~/Documents/IndigoImages/`):

```
<image_dir>/
├── {CRS1}{CRS2}departureBoard.txt  # Departure board text data (e.g., WALWATdepartureBoard.txt)
├── {CRS1}{CRS2}timetable.png       # Classic departure board image
└── {CRS1}{CRS2}timetable_mobile.png  # Modern departure board image (when enabled)
```

Log file: `~/Library/Application Support/Perceptive Automation/Indigo <version>/Logs/UKTrains.log`
(RotatingFileHandler, 1 MB max, 5 backups)

## Naming Conventions

- Plugin bundle: `UKTrains.indigoPlugin` (PascalCase, `.indigoPlugin` extension)
- Python modules: `snake_case.py`
- Device type ID: `trainTimetable` (camelCase, used in `indigo.devices.iter('self.trainTimetable')`)
- Device states: camelCase (e.g., `train1Dest`, `stationIssues`, `deviceActive`)
- Plugin pref keys: camelCase (e.g., `darwinAPI`, `checkboxDebug1`, `generateClassicBoard`)
- CRS codes: UPPERCASE 3-letter (e.g., `WAT`, `PAD`, `BRI`)
- Image file pattern: `{STARTCRS}{ENDCRS}timetable.png` (e.g., `WALWATtimetable.png`)
