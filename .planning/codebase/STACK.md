# Technology Stack

**Analysis Date:** 2026-02-01

## Languages

**Primary:**
- Python 3.10+ - Main plugin implementation and Darwin API integration
- XML - Device, action, and UI configuration (`Devices.xml`, `Actions.xml`, `PluginConfig.xml`, `MenuItems.xml`)

**Secondary:**
- Plist (XML) - Plugin metadata and configuration (`Info.plist`)

## Runtime

**Environment:**
- macOS (Monterey+)
- Indigo 2023.2+ (home automation platform)
- Python 3.10+ via Indigo's embedded Python environment: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`

**Package Manager:**
- pip
- Lockfile: requirements.txt in `UKTrains.indigoPlugin/Contents/Server Plugin/requirements.txt`

## Frameworks

**Core:**
- Indigo API 3.0 - Plugin lifecycle, device state management, logging
- zeep>=4.2.1 - SOAP client for Darwin webservice (replaces deprecated SUDS library)

**Testing:**
- pytest==7.4.3 - Test runner
- pytest-mock==3.12.0 - Mock fixtures for testing
- pytest-cov==4.1.0 - Code coverage reporting
- freezegun==1.4.0 - Time mocking for time-dependent tests
- mock==5.1.0 - Test doubles

**Build/Dev:**
- Pillow>=10.0.0 - Image generation for departure board PNG creation (subprocess-based)

## Key Dependencies

**Critical:**
- zeep>=4.2.1 - SOAP client for National Rail Darwin API (required, replaces old SUDS library)
- lxml>=4.9.0 - XML processing required by zeep
- requests>=2.31.0 - HTTP transport required by zeep

**Infrastructure:**
- pytz==2023.2 - Timezone handling for UK time (BST/GMT) display; gracefully falls back to GMT if unavailable
- pydantic==2.5.3 - Configuration validation for Darwin API settings and plugin preferences
- tenacity==8.2.3 - Retry logic with exponential backoff for transient Darwin API failures
- Pillow>=10.0.0 - PIL image generation for departure board PNG output

**Data Storage:**
- TinyDB (bundled) - Embedded in plugin at `UKTrains.indigoPlugin/Contents/Server Plugin/tinydb/` for local JSON-based data persistence

## Configuration

**Environment:**
- `.env` file (development only) - For Darwin API credentials during local testing
- Environment variables:
  - `DARWIN_WEBSERVICE_API_KEY` - Darwin API authentication key
  - `DARWIN_WEBSERVICE_WSDL` - Darwin WSDL endpoint URL (defaults to `https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx`)

**Build:**
- `Info.plist` - Plugin metadata (version 2025.1.3, API version 3.0)
- `PluginConfig.xml` - Plugin preferences UI for Darwin API key, update frequency, image colors
- Devices.xml - "trainTimetable" device type with state definitions for 10 trains per route

**Runtime Config Files:**
- `trainparameters.txt` - Color and font parameters for image generation subprocess
- `stationCodes.txt` - CRS (Computer Reservation System) station codes for validation

## Platform Requirements

**Development:**
- macOS Monterey or later
- Xcode command-line tools (for building)
- Python 3.10+ development headers
- Valid Darwin API key from National Rail (free at https://www.nationalrail.co.uk/developers/)

**Production:**
- macOS Monterey or later
- Indigo 2023.2+ running on macOS
- Network connection to Darwin API (realtime.nationalrail.co.uk)
- Subprocess spawning capability (for image generation via PIL)

---

*Stack analysis: 2026-02-01*
