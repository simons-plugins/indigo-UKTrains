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
3. **Diagnostic logging** is enabled by default for image generation (can be disabled after confirming stable)
4. **Test deployment** on actual Indigo Mac before assuming fixes work
5. **Version bumps** should follow semantic versioning in Info.plist
