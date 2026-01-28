"""
Mock Indigo module for testing

This module provides mock implementations of the Indigo API
so that plugin code can be tested without a running Indigo server.
"""

from unittest.mock import MagicMock, Mock
import logging


class MockDevice:
    """Mock Indigo device for testing"""

    def __init__(self, device_id=12345, name="Test Device", enabled=True, **kwargs):
        self.id = device_id
        self.name = name
        self.enabled = enabled
        self.pluginProps = kwargs.get('pluginProps', {
            'darwinAPI': 'test_api_key',
            'darwinSite': 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',
            'stationImage': True,
            'updateFreq': 60,
            'imageFilename': '/tmp/test_images',
            'includeCalling': True,
            'createMaps': True
        })
        self.states = kwargs.get('states', {
            'stationCRS': 'PAD',  # London Paddington
            'destinationCRS': 'BRI',  # Bristol
            'stationLong': '',
            'timeGenerated': '',
            'train1Destination': '',
            'train1Operator': '',
            'train1Sch': '',
            'train1Est': '',
            'train1Delay': '',
            'train1Problem': False,
            'train1Reason': '',
            'train1Calling': '',
        })

        # Track state updates
        self._state_updates = []

    def updateStateOnServer(self, key, value):
        """Mock the state update method"""
        self.states[key] = value
        self._state_updates.append({'key': key, 'value': value})

    def stateListOrDisplayStateIdChanged(self):
        """Mock state list changed callback"""
        pass


class MockPluginBase:
    """Mock base class for Indigo plugins"""

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        self.pluginId = plugin_id
        self.pluginDisplayName = plugin_display_name
        self.pluginVersion = plugin_version
        self.pluginPrefs = plugin_prefs
        self.logger = logging.getLogger(plugin_id)

        # Mock methods
        self.sleep = Mock()
        self.errorLog = Mock()

    class StopThread(Exception):
        """Exception to signal thread stop"""
        pass


class MockServer:
    """Mock Indigo server object"""

    def __init__(self):
        self.log = Mock()
        self.getPlugin = Mock(return_value=MagicMock(
            pluginFolderPath='/test/path'
        ))


class MockDict(dict):
    """Mock Indigo.Dict - just a regular dict"""
    pass


class MockDevices:
    """Mock devices collection"""

    def __init__(self):
        self._devices = {}

    def __getitem__(self, device_id):
        return self._devices.get(device_id)

    def __setitem__(self, device_id, device):
        self._devices[device_id] = device

    def itervalues(self, filter_type=None):
        """Mock itervalues for device iteration"""
        return iter(self._devices.values())


# Create the mock indigo module
class MockIndigo:
    """Main mock Indigo module"""

    # Class attributes that will be accessed as module attributes
    PluginBase = MockPluginBase
    Dict = MockDict
    server = MockServer()
    devices = MockDevices()

    # Mock constants
    kDeviceGeneralPropertyChanged = "deviceGeneralPropertyChanged"
    kDeviceStateListChanged = "deviceStateListChanged"

    @staticmethod
    def debugger():
        """Mock debugger call"""
        pass


def create_mock_indigo():
    """Factory function to create a fresh mock Indigo module"""
    return MockIndigo()


def create_mock_device(**kwargs):
    """Factory function to create a mock device with custom properties"""
    return MockDevice(**kwargs)
