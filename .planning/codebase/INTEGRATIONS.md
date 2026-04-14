# INTEGRATIONS

## National Rail Darwin LDB Webservice

The only external service. Provides real-time UK train departure/arrival data via SOAP.

- **WSDL endpoint**: `https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx`
  (configurable in plugin prefs, stored as `darwinSite`)
- **Authentication**: API key header injection via zeep's `BearerKeyPlugin`
  (handled in `nredarwin/webservice.py`, key stored as plugin pref `darwinAPI`)
- **Protocol**: SOAP over HTTPS
- **Namespace**: `http://thalesgroup.com/RTTI/2010-11-01/ldb/commontypes`

### API Key

Free registration at National Rail developer portal. Stored in Indigo plugin preferences —
not in any dotenv or config file. No secrets should be committed to the repo (see `.env.example`).

### Methods Used

| Method | Darwin Operation | Wrapper |
|--------|-----------------|---------|
| Get departures board (all destinations) | `get_station_board(crs, row_limit, True, False)` | `_fetch_station_board()` in `darwin_api.py` |
| Get departures board (filtered by destination) | `get_station_board(crs, row_limit, True, False, dest_crs)` | `_fetch_station_board()` |
| Get individual service details (calling points) | `get_service_details(service_id)` | `_fetch_service_details()` in `darwin_api.py` |

### Session Management

`nredarwin/webservice.py` `DarwinLdbSession` wraps zeep `Client`. Session is created
per polling cycle (not persistent) via `nationalRailLogin()` in `darwin_api.py`.

### Station Codes

CRS (Computer Reservation System) 3-letter codes (e.g., `WAT` = London Waterloo).
Full list in `UKTrains.indigoPlugin/Contents/Server Plugin/stationCodes.txt`
(format: `CRS,Station Name`, ~2700+ entries). Special value `ALL` means all destinations.

### Error Handling

- SOAP faults (`zeep.exceptions.Fault`) trigger retry via tenacity decorator
- Up to 3 retries with exponential backoff (1s, 2s, 4s) for station board
- Up to 2 retries for service details
- After all retries exhausted, `routeUpdate()` returns `False` and the device is
  marked inactive for that polling cycle

### Retry Decorator

`darwin_api_retry(max_attempts)` in `darwin_api.py` — wraps tenacity. Falls back to
identity decorator if tenacity is not installed.

## No Other External Services

- No version-check service (references to `updater` and `dropbox` URL were removed)
- No push notifications
- No cloud relay
- All image output is local filesystem writes
