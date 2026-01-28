"""
Pytest configuration and fixtures for UK-Trains plugin tests

This file is automatically loaded by pytest and provides fixtures
that are available to all test files.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add tests directory to path first (so we can import mocks)
tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))

# CRITICAL: Mock indigo module BEFORE adding plugin to path
# This must happen at import time, not as a fixture, because
# plugin.py imports indigo at module level
from mocks.mock_indigo import MockIndigo
mock_indigo_instance = MockIndigo()
sys.modules['indigo'] = mock_indigo_instance

# Now it's safe to add plugin directory to path
plugin_dir = tests_dir.parent / "UKTrains.indigoPlugin" / "Contents" / "Server Plugin"
sys.path.insert(0, str(plugin_dir))

# Import our mocks
from mocks.mock_indigo import create_mock_indigo, create_mock_device
from mocks.mock_darwin import (
    create_mock_darwin_session,
    create_on_time_service,
    create_delayed_service,
    create_cancelled_service,
    create_station_board_paddington,
)


@pytest.fixture(scope="session", autouse=True)
def mock_indigo_module():
    """
    Session-scoped fixture that mocks the Indigo module before any imports.
    This runs automatically for all tests.
    """
    # Create mock Indigo module
    mock_indigo = MockIndigo()

    # Inject it into sys.modules so imports find it
    sys.modules['indigo'] = mock_indigo

    # Also create a mock requirements module to prevent import errors
    mock_requirements = MagicMock()
    mock_requirements.requirements_check = Mock()
    sys.modules['requirements'] = mock_requirements

    yield mock_indigo

    # Cleanup (optional, pytest handles this)
    # sys.modules.pop('indigo', None)


@pytest.fixture
def mock_device():
    """
    Fixture that provides a mock Indigo device with default configuration.
    """
    return create_mock_device(
        device_id=12345,
        name="Test UK Trains Device",
        enabled=True,
        pluginProps={
            'darwinAPI': 'test_api_key_12345',
            'darwinSite': 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',
            'stationImage': True,
            'updateFreq': 60,
            'imageFilename': '/tmp/test_images',
            'includeCalling': True,
            'createMaps': True,
        },
        states={
            'stationCRS': 'PAD',
            'destinationCRS': 'BRI',
            'stationLong': '',
            'timeGenerated': '',
        }
    )


@pytest.fixture
def mock_darwin_normal():
    """
    Fixture providing a Darwin session with normal (on-time) services.
    """
    return create_mock_darwin_session(scenario="normal")


@pytest.fixture
def mock_darwin_delays():
    """
    Fixture providing a Darwin session with delayed services.
    """
    return create_mock_darwin_session(scenario="delays")


@pytest.fixture
def mock_darwin_cancellation():
    """
    Fixture providing a Darwin session with cancelled services.
    """
    return create_mock_darwin_session(scenario="cancellation")


@pytest.fixture
def mock_darwin_mixed():
    """
    Fixture providing a Darwin session with mixed service statuses.
    """
    return create_mock_darwin_session(scenario="mixed")


@pytest.fixture
def mock_darwin_empty():
    """
    Fixture providing a Darwin session with no services.
    """
    return create_mock_darwin_session(scenario="empty")


@pytest.fixture
def mock_darwin_session_factory():
    """
    Fixture that returns a factory function to create custom Darwin sessions.

    Usage in tests:
        session = mock_darwin_session_factory("delays")
    """
    return create_mock_darwin_session


@pytest.fixture
def sample_services():
    """
    Fixture providing sample service objects for testing.
    """
    return {
        'on_time': create_on_time_service(),
        'delayed': create_delayed_service(),
        'cancelled': create_cancelled_service(),
    }


@pytest.fixture
def mock_time():
    """
    Fixture for mocking time-related functions.
    Useful for testing time calculations.
    """
    with patch('time.time', return_value=1234567890.0):
        with patch('time.strftime', return_value='2009-02-13 23:31:30'):
            yield


@pytest.fixture
def temp_image_dir(tmp_path):
    """
    Fixture providing a temporary directory for image generation tests.
    """
    image_dir = tmp_path / "test_images"
    image_dir.mkdir()
    return str(image_dir)


@pytest.fixture
def mock_plugin_prefs():
    """
    Fixture providing mock plugin preferences.
    """
    return {
        'darwinAPI': 'test_api_key',
        'darwinSite': 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',
        'checkboxDebug1': True,
        'updateFreq': '60',
        'createMaps': 'true',
        'imageFilename': '/tmp/test_images',
    }


@pytest.fixture
def captured_logs(caplog):
    """
    Fixture that captures log output for assertions.

    Usage:
        def test_something(captured_logs):
            # ... code that logs ...
            assert "Expected message" in captured_logs.text
    """
    caplog.set_level('DEBUG')
    return caplog


# Helper functions for tests

def assert_state_updated(device, key, expected_value):
    """
    Helper to assert that a device state was updated with a specific value.
    """
    updates = [u for u in device._state_updates if u['key'] == key]
    assert len(updates) > 0, f"State '{key}' was never updated"
    assert updates[-1]['value'] == expected_value, \
        f"State '{key}' was updated to '{updates[-1]['value']}', expected '{expected_value}'"


def assert_state_contains(device, key, substring):
    """
    Helper to assert that a device state contains a substring.
    """
    updates = [u for u in device._state_updates if u['key'] == key]
    assert len(updates) > 0, f"State '{key}' was never updated"
    assert substring in str(updates[-1]['value']), \
        f"State '{key}' = '{updates[-1]['value']}' does not contain '{substring}'"


# Make helpers available to all tests
pytest.assert_state_updated = assert_state_updated
pytest.assert_state_contains = assert_state_contains
