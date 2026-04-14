# TESTING

## Framework

- **pytest** `7.4.3` with `pytest-mock`, `pytest-cov`, `freezegun`, `mock`
- Config: `tests/pytest.ini`
- Run from `tests/` directory: `bash run_tests.sh` or `pytest`

## Test Layout

```
tests/
├── unit/                   # Pure function tests (no Indigo, no network)
│   ├── test_text_formatting.py   — delayCalc(), formatSpecials(), getUKTime()
│   └── test_time_calculations.py — time arithmetic helpers
├── integration/            # Component tests with mocked dependencies
│   ├── test_route_update.py      — routeUpdate() with mock Darwin sessions
│   └── test_live_darwin_api.py   — marked live_api (skipped by default)
├── mocks/
│   ├── mock_indigo.py      — MockIndigo class (injected as sys.modules['indigo'])
│   └── mock_darwin.py      — Factory functions for mock station boards and services
└── fixtures/
    └── darwin_responses/   — Static response fixtures
```

## Indigo Mock Strategy

`conftest.py` injects `MockIndigo` into `sys.modules['indigo']` **before** importing
`plugin.py`. This must happen at module level (not inside fixtures) because `plugin.py`
imports `indigo` at the top of the file.

The mock provides: `PluginBase`, `kStateImageSel`, `devices.iter()`, `server.log()`,
`Dict`, and other Indigo API surface needed by the plugin.

`create_mock_device()` in `mock_indigo.py` creates a device with configurable `pluginProps`,
`states`, `enabled`, `configured` flags, and a `_state_updates` list for assertions.

## Darwin Mock Strategy

`mock_darwin.py` provides:
- `create_mock_darwin_session(scenario)` — factory for scenarios: `normal`, `delays`,
  `cancellation`, `mixed`, `empty`
- `create_on_time_service()`, `create_delayed_service()`, `create_cancelled_service()`
- `create_station_board_paddington()` — fixed station board fixture

## Pytest Markers

| Marker | Meaning |
|--------|---------|
| `unit` | Pure function tests, no I/O |
| `integration` | Uses mock Darwin + Indigo |
| `api` | Darwin API tests (mocked) |
| `slow` | Long-running tests |
| `live_api` | Makes real Darwin API calls — **skipped by default** |

To run live API tests: `pytest -m live_api` (requires valid Darwin API key).

## Coverage

`pytest-cov` configured. Run with:
```bash
pytest --cov=. --cov-report=html
```

## Test Helper Assertions

`conftest.py` adds two helpers to the `pytest` namespace:
- `pytest.assert_state_updated(device, key, expected_value)` — asserts a specific state was updated
- `pytest.assert_state_contains(device, key, substring)` — asserts state contains substring

## Notable Gaps

- No tests for `image_generator.py` subprocess dispatch (would require Pillow + filesystem)
- No tests for `config.py` Pydantic validation paths
- No tests for `text2png.py` or `text2png_modern.py` rendering (visual output only)
- Live API tests exist but require manual key setup and are excluded from CI
- CLAUDE.md states "No automated test suite exists" — this is outdated; the suite in `tests/`
  is real but may not be wired to CI
