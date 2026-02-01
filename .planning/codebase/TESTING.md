# Testing Patterns

**Analysis Date:** 2026-02-01

## Test Framework

**Runner:**
- pytest 7.4.3
- Config: `tests/pytest.ini`

**Assertion Library:**
- pytest's built-in assertions (no special assertion library)

**Run Commands:**
```bash
cd tests
pytest                           # Run all tests
pytest -m unit                   # Run unit tests only
pytest -m integration            # Run integration tests only
pytest -m live_api               # Run REAL Darwin API tests (skipped by default)
pytest -v                        # Verbose output
pytest --co                      # Collect tests without running
pytest -m "not live_api"         # Run everything except live API tests
```

## Test File Organization

**Location:**
- Separate from source code: `tests/` directory at project root
- Mirror structure not enforced; grouped by type instead

**Naming:**
- Test files: `test_*.py` pattern
- Test classes: `Test*` pattern
- Test functions: `test_*` pattern
- Fixtures: `conftest.py` at `tests/` directory level

**Structure:**
```
tests/
├── conftest.py                    # Global fixtures and mocking setup
├── pytest.ini                     # Pytest configuration
├── fixtures/                      # Test data (unused currently)
│   └── __init__.py
├── mocks/                         # Mock implementations
│   ├── __init__.py
│   ├── mock_indigo.py             # Indigo API mocks
│   └── mock_darwin.py             # Darwin API mocks
├── unit/                          # Pure function tests
│   ├── __init__.py
│   ├── test_text_formatting.py    # formatSpecials() function tests
│   └── test_time_calculations.py  # delayCalc() function tests
└── integration/                   # Full workflow tests with mocks
    ├── __init__.py
    ├── test_live_darwin_api.py    # Tests with REAL Darwin API
    └── test_route_update.py       # routeUpdate() workflow tests
```

## Test Structure

**Suite Organization:**
```python
@pytest.mark.unit
class TestDelayCalc:
    """Test cases for delayCalc function"""

    def test_on_time_string(self):
        """Test when service is exactly on time (string 'On time')"""
        has_problem, message = plugin.delayCalc("14:30", "On time")
        assert has_problem is False
        assert message == "On time"
```

**Patterns:**
- Classes group related test methods for organization
- Docstrings document individual test purpose
- Class-level marker (`@pytest.mark.unit`) applied to all methods
- No setup/teardown methods observed; fixtures used instead

**Fixtures:**
- Session-scoped: `mock_indigo_module()` - must run first for import ordering
- Function-scoped: `mock_device()`, `mock_darwin_normal()`, `mock_darwin_delays()` - created fresh per test
- Parametrized tests use `@pytest.mark.parametrize` decorator

```python
@pytest.mark.parametrize("scheduled,estimated,expected_problem,expected_msg", [
    ("10:00", "10:00", False, "On Time"),
    ("10:00", "10:05", True, "5 mins late"),
    ("10:00", "Cancelled", True, "Cancelled"),
])
def test_common_scenarios(self, scheduled, estimated, expected_problem, expected_msg):
    has_problem, message = plugin.delayCalc(scheduled, estimated)
    assert has_problem == expected_problem
    assert message == expected_msg
```

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**
- **Module-level mocking (CRITICAL):** `conftest.py` injects mock indigo before plugin import:
  ```python
  from mocks.mock_indigo import MockIndigo
  mock_indigo_instance = MockIndigo()
  sys.modules['indigo'] = mock_indigo_instance  # Before plugin imports
  ```
- **Fixture-based:** `@pytest.fixture` provides pre-configured mocks
- **Patch-based:** `@patch('plugin.DarwinLdbSession', return_value=mock_darwin_normal)` for function replacement

**Mock Objects:**
- `MockDevice`: Indigo device with state tracking
  ```python
  class MockDevice:
      def __init__(self, device_id=12345, name="Test Device", ...):
          self.states = {...}
          self._state_updates = []  # Tracks all state changes for assertions

      def updateStateOnServer(self, key, value):
          self.states[key] = value
          self._state_updates.append({'key': key, 'value': value})
  ```
- `MockStationBoard`, `MockServiceItem`, `MockCallingPoint`: Darwin API response objects
- `MockPluginBase`, `MockServer`, `MockDict`: Indigo API infrastructure mocks

**What to Mock:**
- External APIs: Darwin SOAP webservice (expensive, non-deterministic)
- Indigo plugin infrastructure: `indigo.PluginBase`, device state management
- File system operations: image output paths, log directories
- Time-dependent functions: `time.time()`, `time.strftime()` for reproducible tests

**What NOT to Mock:**
- Pure calculation functions: `delayCalc()`, `formatSpecials()` - test directly
- String manipulation: test actual formatting output
- Configuration parsing: validate actual config classes work correctly
- Constants and enums: use real values for semantic verification

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def mock_device():
    """Fixture that provides a mock Indigo device with default configuration."""
    return create_mock_device(
        device_id=12345,
        name="Test UK Trains Device",
        enabled=True,
        pluginProps={
            'darwinAPI': 'test_api_key_12345',
            'stationImage': True,
            'updateFreq': 60,
        },
        states={
            'stationCRS': 'PAD',
            'destinationCRS': 'BRI',
            'stationLong': '',
        }
    )

@pytest.fixture
def mock_darwin_normal():
    """Fixture providing a Darwin session with normal (on-time) services."""
    return create_mock_darwin_session(scenario="normal")

@pytest.fixture
def mock_darwin_delays():
    """Fixture providing a Darwin session with delayed services."""
    return create_mock_darwin_session(scenario="delays")
```

**Factory Functions:**
- Located in `tests/mocks/mock_darwin.py` and `tests/mocks/mock_indigo.py`
- Named with `create_*` pattern: `create_mock_device()`, `create_mock_darwin_session()`, `create_on_time_service()`
- Support scenarios: "normal", "delays", "cancellation", "mixed", "empty"
- Return configured objects ready for immediate use

**Location:**
- Test fixtures: `tests/conftest.py`
- Mock factories: `tests/mocks/mock_indigo.py`, `tests/mocks/mock_darwin.py`
- Sample services: `create_on_time_service()`, `create_delayed_service()`, `create_cancelled_service()`

## Coverage

**Requirements:** No explicit coverage target enforced

**View Coverage:**
```bash
pytest --cov=../UKTrains.indigoPlugin/Contents/Server\ Plugin --cov-report=html
# or
coverage run -m pytest
coverage report
coverage html
```

## Test Types

**Unit Tests:**
- Scope: Pure functions with no external dependencies
- Location: `tests/unit/`
- Examples:
  - `test_text_formatting.py`: Tests `formatSpecials()` - HTML removal, whitespace handling, URL cleaning
  - `test_time_calculations.py`: Tests `delayCalc()` - time parsing, delay calculation, edge cases (midnight crossing, null values)
- Approach: Direct function calls with simple assert statements
- 30+ test cases covering normal paths, edge cases, parametrized scenarios

**Integration Tests:**
- Scope: Full workflows with mocked dependencies
- Location: `tests/integration/`
- Examples:
  - `test_route_update.py`: Tests `routeUpdate()` with mocked Darwin API responses
  - Mock Darwin sessions injected: on-time, delayed, cancelled, mixed scenarios
  - Assertions verify device state updates occur correctly
- Approach: Patch external dependencies, verify full function behavior and side effects

**E2E Tests:**
- Framework: Not used for automated CI
- Manual alternative: `test_darwin_live.py` at project root makes REAL Darwin API calls
- Skipped by default; enabled with `pytest -m live_api` and `DARWIN_API_KEY` env var
- Purpose: Verify mock responses match real API behavior before production

## Common Patterns

**Async Testing:**
Not applicable (Python 3 synchronous code; Indigo plugin runs in concurrent thread managed by framework)

**Error Testing:**
```python
def test_cancelled_service(self):
    """Test when service is cancelled"""
    has_problem, message = plugin.delayCalc("14:30", "Cancelled")
    assert has_problem is True
    assert message == "Cancelled"

def test_null_est_time(self):
    """Test with null/None estimated time"""
    has_problem, message = plugin.delayCalc("14:30", None)
    assert has_problem is True
    assert message == "Delayed"
```

**Assertion Helpers:**
Custom helpers injected in `conftest.py` for device state assertions:
```python
def assert_state_updated(device, key, expected_value):
    """Helper to assert that a device state was updated with a specific value."""
    updates = [u for u in device._state_updates if u['key'] == key]
    assert len(updates) > 0, f"State '{key}' was never updated"
    assert updates[-1]['value'] == expected_value

pytest.assert_state_updated = assert_state_updated
```

Usage in tests:
```python
def test_successful_route_update_on_time_trains(self, mock_device, ...):
    result = plugin.routeUpdate(mock_device, api_key, network_url, paths)
    assert result is True
    assert len(mock_device._state_updates) > 0
    station_updates = [u for u in mock_device._state_updates if u['key'] == 'stationLong']
    assert station_updates[0]['value'] == "London Paddington"
```

## Test Markers

**Available:**
- `@pytest.mark.unit` - Pure function tests
- `@pytest.mark.integration` - Workflow tests with mocks
- `@pytest.mark.api` - Tests interacting with Darwin API (mocked)
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.live_api` - Tests making REAL Darwin API calls (skipped by default)

**Usage:**
```python
@pytest.mark.unit
class TestDelayCalc:
    def test_on_time_string(self):
        ...

@pytest.mark.integration
class TestRouteUpdateIntegration:
    def test_successful_route_update_on_time_trains(self):
        ...

@pytest.mark.live_api
def test_can_connect_to_darwin():
    # Only runs with: pytest -m live_api
    ...
```

## Pytest Configuration

**File:** `tests/pytest.ini`

**Key Settings:**
```ini
[pytest]
# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Paths
testpaths = .
pythonpath = ../UKTrains.indigoPlugin/Contents/Server Plugin

# Output
addopts = --verbose --strict-markers

# Markers
markers =
    unit: Unit tests for pure functions
    integration: Integration tests with mocked dependencies
    api: Tests that interact with Darwin API (mocked)
    slow: Tests that take longer to run
    live_api: Tests that make REAL calls to Darwin API (skipped by default)

# Logging
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)8s] %(message)s

# Exclusions
norecursedirs = .git __pycache__ *.egg-info
```

---

*Testing analysis: 2026-02-01*
