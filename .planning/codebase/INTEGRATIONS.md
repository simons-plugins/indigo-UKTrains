# External Integrations

**Analysis Date:** 2026-02-01

## APIs & External Services

**National Rail Darwin API:**
- UK National Rail real-time departure and arrival information service
  - SDK/Client: zeep>=4.2.1 (SOAP client)
  - Endpoint: `https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx` (WSDL)
  - Auth: `DARWIN_WEBSERVICE_API_KEY` environment variable (free API key from https://www.nationalrail.co.uk/developers/)
  - API Type: SOAP webservice
  - Key operations:
    - `get_station_board()` - Fetch departure/arrival board for station with optional destination filtering
    - `get_service_details()` - Fetch calling points and additional details for a specific train service
  - Usage: `nredarwin.webservice.DarwinLdbSession` in `UKTrains.indigoPlugin/Contents/Server Plugin/nredarwin/webservice.py`

## Data Storage

**Databases:**
- None configured for production use
- TinyDB (embedded) - Bundled locally in `UKTrains.indigoPlugin/Contents/Server Plugin/tinydb/` for potential local JSON storage
  - Connection: File-based (not currently in active use)
  - Client: Custom TinyDB implementation (v3 fork)

**File Storage:**
- Local filesystem only
- Departure board images: `~/Documents/IndigoImages/` (configurable via `PluginConfig.xml`)
- Plugin logs: `~/Library/Application Support/Perceptive Automation/Indigo [VERSION]/Logs/`
- Station codes: `UKTrains.indigoPlugin/Contents/Server Plugin/stationCodes.txt`
- Parameters: `UKTrains.indigoPlugin/Contents/Server Plugin/trainparameters.txt`

**Caching:**
- None - Real-time data fetched on each poll cycle (configurable interval, default 60 seconds)

## Authentication & Identity

**Auth Provider:**
- Custom/Manual - Darwin API key required
  - Implementation: Token-based SOAP header authentication
  - Token header format: `<AccessToken><TokenValue>[API_KEY]</TokenValue></AccessToken>`
  - Code: `UKTrains.indigoPlugin/Contents/Server Plugin/nredarwin/webservice.py:54-71` (SOAP header construction)
  - Configured via plugin settings: `PluginConfig.xml`

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking)
- Manual logging to local files

**Logs:**
- Approach: Rotating file handler with size-based rotation (1MB max, 5 backups)
- Log file: `UKTrains.log` in Indigo Logs directory
- Code: `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py:69-95` (PluginLogger class)
- Also logs to stderr for subprocess output
- Debug flag in `PluginConfig.xml` controls verbosity

## CI/CD & Deployment

**Hosting:**
- Local macOS machine (runs within Indigo home automation system)
- Plugin distributed as `.indigoPlugin` bundle (macOS application bundle)

**CI Pipeline:**
- None (no external CI service configured)
- Manual testing via pytest in development environment

**Installation:**
- Copy `UKTrains.indigoPlugin` bundle to `/Library/Application Support/Perceptive Automation/Indigo [VERSION]/Plugins/`
- Enable in Indigo UI: Plugins → Manage Plugins

## Environment Configuration

**Required env vars (Development/Testing):**
- `DARWIN_WEBSERVICE_API_KEY` - Darwin API key (required to function)
- `DARWIN_WEBSERVICE_WSDL` - Darwin WSDL URL (optional, has default)

**Required env vars (Production/Plugin Runtime):**
- Configured via Indigo plugin preferences UI (`PluginConfig.xml`)
- No direct environment variable requirement in production

**Secrets location:**
- Development: `.env` file (git-ignored, see `.gitignore`)
- Production: Indigo plugin preferences database (encrypted by Indigo)
- Plugin security: API key stored in `plugin_prefs['darwinAPI']`

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## API Integration Details

### Darwin API Implementation

**Location:** `UKTrains.indigoPlugin/Contents/Server Plugin/`

**Main Integration Files:**
- `darwin_api.py` - Wrapper functions with retry logic
  - `nationalRailLogin()` - Authenticate and create DarwinLdbSession
  - `_fetch_station_board()` - Fetch departures with exponential backoff retry
  - `_fetch_service_details()` - Fetch calling points with retry
  - Decorator: `@darwin_api_retry()` handles transient failures (WebFault, ConnectionError, TimeoutError)

- `nredarwin/webservice.py` - Low-level SOAP client
  - `DarwinLdbSession` class wraps zeep SOAP client
  - Uses requests.Session for HTTP with 5-second timeout
  - zeep HistoryPlugin for debugging SOAP calls
  - SOAP authentication via AccessToken header

**Retry Strategy:**
- Uses tenacity library with exponential backoff
- Station board: max 3 attempts, 1-10 seconds between retries
- Service details: max 2 attempts, 1-10 seconds between retries
- Retries on: WebFault (SOAP), ConnectionError, TimeoutError
- Failures logged but don't stop plugin (graceful degradation)

**Error Handling:**
- Darwin API failures return False from `routeUpdate()`, skip update on next cycle
- SOAP timeouts are expected and handled gracefully
- Missing dependencies cause immediate plugin exit with logging
- Code: `UKTrains.indigoPlugin/Contents/Server Plugin/darwin_api.py:47-78` (retry decorator)

### Network Configuration

**SSL/TLS:**
- Enabled by default in zeep transport
- Code: `nredarwin/webservice.py:39` (`session.verify = True`)

**Timeouts:**
- Default 5 seconds for both connection and operation timeouts
- Configurable in `DarwinLdbSession.__init__()` via `timeout` parameter
- Code: `nredarwin/webservice.py:40` (transport timeout)

### Data Formats

**Darwin API Responses:**
- SOAP XML (zeep parses to Python objects)
- Station board returns: List of train services with times, delays, calling points
- Service details returns: Calling points with actual/estimated times

**Departure Board Output:**
- Text format: `[START_CRS][END_CRS]departureBoard.txt`
- PNG format: `[START_CRS][END_CRS]timetable.png` (subprocess-generated)
- Location: `~/Documents/IndigoImages/` (configurable)

---

*Integration audit: 2026-02-01*
