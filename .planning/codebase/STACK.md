# STACK

## Language & Runtime

- **Python 3.10+** (Indigo 2023+ requirement)
- Interpreter: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`
- Plugin host: `IndigoPluginHost3.app` (Indigo's wrapper — NOT a valid subprocess target)
- Indigo Server API version: `3.0` (from `Info.plist`)
- IWS API version: `1.0.0`

## Info.plist Metadata

File: `UKTrains.indigoPlugin/Contents/Info.plist`

| Key | Value |
|-----|-------|
| `PluginVersion` | `2026.0.4` |
| `CFBundleDisplayName` | `UK Trains` |
| `CFBundleIdentifier` | `com.simons-plugins.UKTrains` |
| `CFBundleVersion` | `1.0.1` |
| `ServerApiVersion` | `3.0` |
| `GithubUser` | `simons-plugins` |
| `GithubRepo` | `UKTrains` |

## Production Dependencies

Declared in `UKTrains.indigoPlugin/Contents/Server Plugin/requirements.txt`.
Must be installed manually into Indigo's Python environment — there is no `Contents/Packages/` bundle.

| Package | Version | Purpose |
|---------|---------|---------|
| `zeep` | `>=4.2.1` | Modern SOAP client for Darwin webservice |
| `lxml` | `>=4.9.0` | XML processing (required by zeep) |
| `requests` | `>=2.31.0` | HTTP transport (required by zeep) |
| `pytz` | `==2023.2` | UK timezone / BST handling (optional, falls back to GMT) |
| `pydantic` | `==2.5.3` | Plugin config validation (optional, gracefully absent) |
| `tenacity` | `==8.2.3` | Retry logic with exponential backoff (optional, gracefully absent) |
| `Pillow` | `>=10.0.0` | PNG image generation via subprocess |

## Bundled Libraries (in Server Plugin directory)

- `nredarwin/` — vendored fork of Robert Clake's nredarwin SOAP wrapper, modified to use zeep
- `tinydb/` — vendored TinyDB library (present but not actively used in main code paths)

## Test Dependencies

Declared in `tests/requirements-test.txt`:
- `pytest==7.4.3`, `pytest-mock==3.12.0`, `pytest-cov==4.1.0`
- `freezegun==1.4.0` (time mocking)
- `mock==5.1.0`
- `coverage[toml]==7.4.0`

## Install Command

```bash
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install -r requirements.txt
```
