# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🔧 Development Tools

**IMPORTANT: Use the `/indigo` skill when working on this plugin!**

The `/indigo` skill provides:
- Comprehensive Indigo plugin development documentation
- 16 official SDK example plugins with best practices
- API reference and troubleshooting guides
- Pattern matching for common plugin tasks

To access: Type `/indigo` in Claude Code to load the Indigo development skill.

See: [../Indigo-skill/README.md](../Indigo-skill/README.md) for installation and usage.

## Project Overview

This is an Indigo home automation plugin that integrates with the UK National Rail Darwin information engine to provide real-time train departure and arrival information. It's an updated version of Chameleon's iTravel plugin, modernized for macOS Monterey and Python 3.

## Key Dependencies

- **National Rail Darwin API**: Requires a free API key from National Rail for accessing real-time train data
- **zeep>=4.2.1**: SOAP client library for Darwin webservice interaction (ZEEP 4.x required)
- **pytz==2023.2**: Timezone handling (optional, falls back to GMT if missing)
- **PIL/Pillow**: Required for generating departure board images (handled via subprocess)

## Architecture Overview

### Plugin Structure

This is an Indigo plugin packaged as a `.indigoPlugin` bundle with the following key components:

1. **Main Plugin Class** ([plugin.py:659-1236](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L659-L1236)): `Plugin(indigo.PluginBase)` manages the lifecycle, device communication, and concurrent thread operations.

2. **Darwin API Wrapper** ([nredarwin/webservice.py](UKTrains.indigoPlugin/Contents/Server%20Plugin/nredarwin/webservice.py)): `DarwinLdbSession` provides SOAP webservice access to National Rail data, wrapping station boards and service details.

3. **Device Model** ([Devices.xml](UKTrains.indigoPlugin/Contents/Server%20Plugin/Devices.xml)): Defines "trainTimetable" device type with states for up to 10 trains, including destination, operator, scheduled/estimated times, delays, and calling points.

4. **Image Generation** ([text2png.py](UKTrains.indigoPlugin/Contents/Server%20Plugin/text2png.py)): Standalone subprocess that converts departure board text data to PNG images using PIL for control page display.

### Data Flow

1. Plugin runs in concurrent thread ([plugin.py:979](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L979)), polling at configured intervals (default 60 seconds)
2. For each active route device, calls `routeUpdate()` ([plugin.py:272](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L272)) which:
   - Authenticates with Darwin API via `nationalRailLogin()` ([plugin.py:624](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L624))
   - Fetches station board data using CRS (Computer Reservation System) codes
   - Optionally filters by destination station
   - Calculates delays via `delayCalc()` ([plugin.py:147](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L147))
   - Updates Indigo device states for each train service
   - Spawns subprocess to generate departure board PNG if enabled

3. Image generation runs as separate Python process to avoid shared library conflicts with Indigo's embedded Python environment

### Key Concepts

- **CRS Codes**: Three-letter station identifiers (e.g., "WAT" for London Waterloo) stored in [stationCodes.txt](UKTrains.indigoPlugin/Contents/Server%20Plugin/stationCodes.txt)
- **Route Devices**: Each device represents a specific station-to-destination route, tracking next 10 departures
- **Station Issues Flag**: Aggregated boolean indicating if any trains on the route have delays/cancellations
- **Calling Points**: Intermediate stops between origin and destination, optionally displayed

## Dual-Style Departure Boards (v2025.1.6+)

### Overview

The plugin supports generating **two departure board styles simultaneously**:

1. **Classic Style**: 720×400px landscape (retro green terminal aesthetic for dashboards)
   - File: `{station}_departure_board.png`
   - Renderer: `text2png.py` (original)
   - Colors: Green on black, retro terminal style

2. **Modern Style**: 414×variable portrait (mobile-optimized for messaging apps)
   - File: `{station}_departure_board_mobile.png`
   - Renderer: `text2png_modern.py` (new)
   - Colors: Dark theme with WCAG AA accessible colors
   - Layout: Card-based with rounded corners

### Configuration

Plugin preferences (PluginConfig.xml) provide two checkboxes:
- ✅ **Generate Classic Board Image** (default: enabled)
- ☐ **Generate Modern Board Image** (default: disabled)

Both can be enabled simultaneously to generate both styles with different filenames.

### Implementation Architecture

**Key Files**:
- `text2png.py`: Dispatches to appropriate renderer based on `boardStyle` parameter
- `text2png_modern.py`: Modern card-based renderer (new)
- `image_generator.py`: Coordinates subprocess calls for image generation
- `constants.py`: Defines color schemes and dimensions for both styles

**Call Chain**:
```
Plugin.runConcurrentThread()
  → routeUpdate(dev, ..., plugin_prefs=self.pluginPrefs)
    → _generate_departure_image(..., plugin_prefs=plugin_prefs)
      → _generate_single_image(..., board_style='classic'|'modern')
        → subprocess: text2png.py → text2png_modern.py (if modern)
```

### Text File Format Parsing

Departure board data is written to text files using **dash-padded format**:

```
London Waterloo------------------- 17:09-----On time---South Western Railway
Status:On time

>>> Surbiton(17:15) Clapham Junction(17:27) London Waterloo(17:36)
```

**Format Structure**:
- **Service line**: `Destination-------Time-----Status---Operator`
  - Fields separated by 3+ consecutive dashes
  - Spaces within fields preserved
- **Status line**: `Status:` prefix followed by status text
- **Calling points**: `>>>` prefix, station names with times in parentheses

**Parsing Logic** (`parse_service_data()` in `text2png_modern.py`):
1. Split service lines on runs of 3+ dashes: `re.split(r'-{3,}', line)`
2. Extract: destination, scheduled time, estimated time, operator
3. Status lines override the estimated time field
4. Calling points lines are concatenated (may span multiple lines)

### Plugin Preferences vs Device Properties

**Critical Distinction**:
- **Plugin preferences** (`self.pluginPrefs`): Plugin-wide settings from `PluginConfig.xml`
  - Accessed via `self.pluginPrefs.get('generateClassicBoard', True)` in Plugin class
  - Must be passed as parameters to module-level functions
- **Device properties** (`device.pluginProps`): Device-specific settings from `Devices.xml`
  - Accessed via `device.pluginProps.get('includeCalling', False)`

**Common Mistake**: Trying to access plugin preferences from device object:
```python
# WRONG ❌
generate_modern = device.pluginProps.get('generateModernBoard', False)  # Always returns False

# CORRECT ✅
generate_modern = self.pluginPrefs.get('generateModernBoard', False)    # From Plugin class
generate_modern = plugin_prefs.get('generateModernBoard', False)        # From module function
```

### Modern Board Design Specifications

**Dimensions**:
- Width: 414px (iPhone 15 Pro Max standard)
- Height: Dynamic based on content (600-900px typical)
- Card height: 120px per service + 12px spacing

**Color Scheme** (WCAG AA compliant):
- Background: `#1A1D29` (dark blue-grey)
- Cards: `#252938` (elevated surface)
- On time: `#00C853` (green, 4.7:1 contrast)
- Delayed: `#FF6B00` (orange, 5.3:1 contrast)
- Cancelled: `#F44336` (red, 4.9:1 contrast)

**Typography** (Hack font family):
- Station name: 26pt Bold
- Destination: 18pt Bold
- Platform: 20pt Bold
- Times: 16pt Regular
- Status: 14pt Bold
- Operator: 12pt Regular
- Calling points: 11pt RegularOblique

### Troubleshooting

**Issue**: Modern board shows "No trains" but classic board has trains
**Cause**: Text parsing failed to extract service data
**Solution**:
1. Check text file format in `/Volumes/simon/Documents/iTravel/{station}departureBoard.txt`
2. Verify dash-padded format (not comma-separated)
3. Check Indigo log for parsing warnings
4. Ensure `text2png_modern.py` uses correct regex: `r'-{3,}'`

**Issue**: Modern board not generated despite checkbox enabled
**Cause**: Plugin preferences not passed through call chain
**Solution**: Verify `routeUpdate()` receives `plugin_prefs=self.pluginPrefs` parameter

**Issue**: Both checkboxes checked but only one image generated
**Cause**: One renderer failed silently
**Solution**: Check Indigo log for subprocess errors (exit codes 1=IO, 2=PIL, 3=config)

### File Naming Convention

```
/Volumes/simon/Documents/iTravel/
├── WALWATdepartureBoard.txt        # Text data (shared by both renderers)
├── WALWATtimetable.png             # Classic: 720×400 landscape
├── WALWATtimetable_mobile.png      # Modern: 414×variable portrait
├── WATWALdepartureBoard.txt
├── WATWALtimetable.png
└── WATWALtimetable_mobile.png
```

**Suffix Pattern**: Modern images always end with `_mobile.png` to prevent conflicts.

## Development Commands

### Installation
This plugin is installed through Indigo's plugin manager. For development:
- Place the `UKTrains.indigoPlugin` bundle in Indigo's plugin directory
- Reload plugins from Indigo interface
- Configure with Darwin API key in plugin settings

### Dependencies Installation
Dependencies must be installed in Indigo's Python environment:
```bash
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install -r requirements.txt
```

### Testing
No automated test suite exists. Testing is manual:
1. Configure plugin with valid Darwin API key
2. Create a route device with valid CRS codes
3. Monitor Indigo log for errors
4. Verify device states update correctly

### Debugging
- Enable debug mode in plugin configuration ([PluginConfig.xml:129](UKTrains.indigoPlugin/Contents/Server%20Plugin/PluginConfig.xml#L129))
- Debug logs written to `/Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/NationRailErrors.log`
- Global `nationalDebug` flag controls verbose logging throughout codebase

## Important Implementation Details

### Error Handling
- SOAP server timeouts are expected and handled gracefully by skipping device updates
- Darwin API failures return `False` from `routeUpdate()`, allowing retry on next cycle
- Missing dependencies (suds, functools) cause immediate plugin exit with logging

### Subprocess Image Generation
The image generation runs in a separate Python process to avoid shared library conflicts. Communication happens via:
- Text file containing departure board data
- Parameters file with color/font configuration
- Stdout/stderr captured for logging

**CRITICAL:** Must use actual Python interpreter path, NOT `sys.executable`!
- `sys.executable` points to `IndigoPluginHost3.app` (Indigo's plugin wrapper)
- IndigoPluginHost3 has its own argument parser that conflicts with subprocess calls
- Always use: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`
- See: [constants.py:56-60](UKTrains.indigoPlugin/Contents/Server%20Plugin/constants.py#L56-L60)

### Time Handling
- All times displayed in UK time (handles BST automatically with pytz)
- Falls back to GMT if pytz unavailable
- Time parsing is fragile - Darwin returns strings like "On time", "Cancelled", or actual times

### Device State Management
- Maximum 10 train services tracked per device
- Each train has 8 states: Dest, Op, Sch, Est, Delay, Issue, Reason, Calling
- Device status icon changes based on delays (SensorOn=on time, SensorTripped=issues, SensorOff=inactive)

### Station Code Dictionary
Station codes loaded from [stationCodes.txt](UKTrains.indigoPlugin/Contents/Server%20Plugin/stationCodes.txt) (format: `CRS,Station Name`). Dictionary built dynamically in `createStationDict()` ([plugin.py:1172](UKTrains.indigoPlugin/Contents/Server%20Plugin/plugin.py#L1172)) and used for validation.

## Known Limitations

- Image generation limited to 5 services despite 10 being stored in device states
- No support for arrivals board (only departures)
- HTML in NRCC messages not properly stripped
- Timezone handling requires pytz, otherwise falls back to GMT only
- No automated testing or CI/CD

## Recent Fixes

### Version 2025.1.5 (Feb 2026)
**Fixed: Image generation "--folder" error**
- Root cause: `sys.executable` pointed to IndigoPluginHost3 wrapper, not Python
- IndigoPluginHost3's argparse was parsing subprocess arguments incorrectly
- Solution: Use explicit Python 3 path in [constants.py](UKTrains.indigoPlugin/Contents/Server%20Plugin/constants.py)
- Added diagnostic logging in [image_generator.py](UKTrains.indigoPlugin/Contents/Server%20Plugin/image_generator.py) for future debugging

**Key Learning:** Never use `sys.executable` for subprocess calls in Indigo plugins!

## Best Practices for This Plugin

1. **Use `/indigo` skill** for all Indigo plugin development tasks
2. **Subprocess calls** must use explicit Python path, not `sys.executable`
3. **Diagnostic logging** for image generation only appears when debug mode is enabled
4. **Test deployment** on actual Indigo Mac before assuming fixes work
5. **Version bumps** should follow semantic versioning in Info.plist
