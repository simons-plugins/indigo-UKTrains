# UK-Trains Plugin Test Suite

Comprehensive test suite for the UK-Trains Indigo plugin using pytest.

## Overview

This test suite provides:
- **Unit tests** for pure functions (time calculations, text formatting)
- **Integration tests** for main workflows (route updates, API interactions)
- **Mocked dependencies** (Indigo API, Darwin SOAP API)
- **Fixtures** for common test scenarios

## Directory Structure

```
tests/
├── README.md                   # This file
├── conftest.py                 # Pytest configuration and fixtures
├── pytest.ini                  # Pytest settings
├── requirements-test.txt       # Test dependencies
│
├── unit/                       # Unit tests for pure functions
│   ├── test_time_calculations.py
│   └── test_text_formatting.py
│
├── integration/                # Integration tests with mocked deps
│   └── test_route_update.py
│
├── mocks/                      # Mock implementations
│   ├── mock_indigo.py         # Mock Indigo API
│   └── mock_darwin.py         # Mock Darwin SOAP responses
│
└── fixtures/                   # Test data and fixtures
    └── darwin_responses/       # Sample API responses
```

## Installation

### 1. Install Test Dependencies

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/tests
pip3 install -r requirements-test.txt
```

Or if you're using a specific Python version:

```bash
pip3.10 install -r requirements-test.txt
```

### 2. Verify Installation

```bash
pytest --version
```

Should show pytest 7.4.3 or later.

## Running Tests

### Run All Tests

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/tests
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Specific test file
pytest unit/test_time_calculations.py

# Specific test class
pytest unit/test_time_calculations.py::TestDelayCalc

# Specific test function
pytest unit/test_time_calculations.py::TestDelayCalc::test_on_time_string
```

### Run with Coverage Report

```bash
# Terminal coverage report
pytest --cov

# HTML coverage report (opens in browser)
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Run with Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Fast Tests Only (Skip Slow Tests)

```bash
pytest -m "not slow"
```

## Test Scenarios

### Mock Darwin API Scenarios

The test suite includes several pre-configured Darwin API scenarios:

1. **normal** - On-time services with normal calling points
2. **delays** - Services with various delays
3. **cancellation** - Includes cancelled services
4. **empty** - No services at station
5. **mixed** - Mix of on-time, delayed, and cancelled

Use these in tests via fixtures:

```python
def test_something(mock_darwin_delays):
    # Test with delayed services
    ...
```

### Mock Devices

Create custom mock devices for testing:

```python
def test_custom_device(mock_device):
    # Modify device properties
    mock_device.states['stationCRS'] = 'VIC'  # Victoria
    mock_device.pluginProps['includeCalling'] = False

    # Use in test
    ...
```

## Writing New Tests

### Unit Test Example

```python
import pytest
import plugin

@pytest.mark.unit
def test_my_function():
    """Test description"""
    result = plugin.my_function("input")
    assert result == "expected"
```

### Integration Test Example

```python
import pytest
from unittest.mock import patch

@pytest.mark.integration
def test_workflow(mock_device, mock_darwin_normal):
    """Test complete workflow"""
    with patch('plugin.DarwinLdbSession', return_value=mock_darwin_normal):
        result = plugin.routeUpdate(mock_device, ...)
        assert result is True
```

### Parametrized Test Example

```python
@pytest.mark.parametrize("input,expected", [
    ("14:30", "On time"),
    ("Cancelled", "Cancelled"),
    ("Delayed", "Delayed"),
])
def test_multiple_cases(input, expected):
    result = plugin.process(input)
    assert result == expected
```

## Continuous Integration

To run tests automatically on every commit:

```bash
# In repository root
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains

# Run tests before committing
tests/run_tests.sh

# Or add to git pre-commit hook
ln -s ../../tests/pre-commit.sh .git/hooks/pre-commit
```

## Coverage Goals

- **Phase 2 Target**: 80% coverage on core functions
- **Current Coverage**: Run `pytest --cov` to see

### Priority Areas for Testing

1. ✅ `delayCalc()` - Time calculation (DONE)
2. ✅ `formatSpecials()` - Text formatting (DONE)
3. ✅ `routeUpdate()` - Main workflow (DONE)
4. 🔲 `getUKTime()` - Timezone handling
5. 🔲 `darwinAccess()` - Authentication
6. 🔲 Device lifecycle methods
7. 🔲 Configuration validation

## Debugging Tests

### Run with Python Debugger

```bash
pytest --pdb
```

Drops into debugger on first failure.

### Print Debug Output

```python
def test_with_debug(caplog):
    caplog.set_level('DEBUG')
    # ... test code ...
    print(caplog.text)  # See all log output
```

### Inspect Fixtures

```bash
pytest --fixtures
```

Shows all available fixtures and their docstrings.

## Common Issues

### ImportError: No module named 'indigo'

**Fix**: The mock indigo module should be injected automatically by `conftest.py`. Make sure tests are run from the `tests/` directory.

### Tests Pass Locally But Fail in CI

**Check**:
- Python version (should be 3.10+)
- Dependencies installed (`requirements-test.txt`)
- Working directory is correct

### Coverage Not Generated

**Fix**: Make sure `pytest-cov` is installed:

```bash
pip3 install pytest-cov
```

## Next Steps

After Phase 2 test infrastructure is complete:

1. **Add more test coverage** - Aim for 80%+ on critical paths
2. **Test edge cases** - Midnight crossing, timezone changes
3. **Performance tests** - Ensure route updates complete quickly
4. **Integration with live API** - Optional tests with real Darwin API

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Indigo Plugin API](https://www.indigodomo.com/docs/plugin_guide)
- [Darwin API Documentation](https://www.nationalrail.co.uk/developers/)
