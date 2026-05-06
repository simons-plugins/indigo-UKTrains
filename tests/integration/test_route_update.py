"""
Integration tests for routeUpdate function.

Tests the main route update workflow with mocked Darwin REST responses.
"""

import pytest
from unittest.mock import Mock, patch
import plugin


@pytest.mark.integration
class TestRouteUpdateIntegration:
    """Integration tests for routeUpdate function"""

    def test_successful_route_update_on_time_trains(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        """Test successful route update with on-time trains"""
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_normal)):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                mock_plugin_paths,
                mock_device,  # logger placeholder
            )

        assert result is True, "routeUpdate should return True on success"
        assert len(mock_device._state_updates) > 0

        station_updates = [u for u in mock_device._state_updates if u['key'] == 'stationLong']
        assert len(station_updates) > 0
        assert station_updates[0]['value'] == "London Paddington"

        time_updates = [u for u in mock_device._state_updates if u['key'] == 'timeGenerated']
        assert len(time_updates) > 0

    def test_route_update_with_delays(self, mock_device, mock_darwin_delays, mock_plugin_paths):
        """Test route update handles delayed trains correctly"""
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_delays)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        assert result is True
        problem_updates = [u for u in mock_device._state_updates if 'Problem' in u['key']]
        assert len(problem_updates) > 0

        delay_updates = [u for u in mock_device._state_updates if 'Delay' in u['key']]
        assert len(delay_updates) > 0

    def test_route_update_with_cancelled_trains(self, mock_device, mock_darwin_cancellation, mock_plugin_paths):
        """Test route update handles cancelled trains"""
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_cancellation)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        assert result is True
        delay_updates = [u for u in mock_device._state_updates if 'Delay' in u['key']]
        cancelled_found = any('Cancelled' in str(u['value']) for u in delay_updates)
        assert cancelled_found, "Should have 'Cancelled' status for cancelled trains"

    def test_route_update_with_empty_board(self, mock_device, mock_darwin_empty, mock_plugin_paths):
        """Test route update with no trains at station"""
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_empty)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        assert result is True
        station_updates = [u for u in mock_device._state_updates if u['key'] == 'stationLong']
        assert len(station_updates) > 0

    def test_route_update_api_failure(self, mock_device, mock_plugin_paths):
        """Test route update when REST API fails"""
        api_key = "test_api_key"

        mock_session = Mock()
        mock_session.get_station_board.side_effect = Exception("REST request failed")

        with patch('plugin.nationalRailLogin', return_value=(True, mock_session)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        assert result is False

    def test_route_update_invalid_device(self, mock_plugin_paths):
        """Test route update with invalid/disabled device"""
        disabled_device = Mock()
        disabled_device.enabled = False

        result = plugin.routeUpdate(
            disabled_device, "api_key", mock_plugin_paths, disabled_device,
        )
        assert result is False

    def test_route_update_filters_by_destination(self, mock_device, mock_plugin_paths):
        """Test route update correctly filters trains by destination"""
        mock_device.states['destinationCRS'] = 'BRI'
        api_key = "test_api_key"

        from mocks.mock_darwin import (
            MockDarwinSession, station_board_dict, service_dict,
            create_calling_points_normal,
        )
        from nredarwin.webservice import StationBoard

        services = [
            service_dict("Bristol Temple Meads", "14:30",
                         service_id="srv-bri",
                         destination_crs="BRI",
                         calling_points=create_calling_points_normal()),
            service_dict("Oxford", "15:00", service_id="srv-oxf"),
            service_dict("Reading", "15:30", service_id="srv-rdg"),
        ]
        board = StationBoard(station_board_dict(services=services))
        mock_session = MockDarwinSession(station_board=board)

        with patch('plugin.nationalRailLogin', return_value=(True, mock_session)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        assert result is True
        dest_updates = [u for u in mock_device._state_updates if u['key'] == 'train1Destination']
        if dest_updates:
            assert 'Bristol' in dest_updates[0]['value']

    def test_route_update_clears_old_states(self, mock_device, mock_plugin_paths):
        """Test that old device states are cleared before update"""
        mock_device.states['train1Destination'] = 'Old Destination'
        mock_device.states['train2Destination'] = 'Old Destination'
        api_key = "test_api_key"

        from mocks.mock_darwin import create_mock_darwin_session
        mock_session = create_mock_darwin_session("empty")

        with patch('plugin.nationalRailLogin', return_value=(True, mock_session)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )

        train_updates = [u for u in mock_device._state_updates
                         if 'train' in u['key'].lower() and 'Destination' in u['key']]
        cleared_updates = [u for u in train_updates if u['value'] == '']
        assert len(cleared_updates) > 0, "Old train states should be cleared"


@pytest.mark.integration
class TestRouteUpdateWithCallingPoints:
    """Test route update with calling point information"""

    def test_calling_points_included(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        mock_device.pluginProps['includeCalling'] = True
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_normal)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )
        assert result is True

    def test_calling_points_excluded(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        mock_device.pluginProps['includeCalling'] = False
        api_key = "test_api_key"

        with patch('plugin.nationalRailLogin', return_value=(True, mock_darwin_normal)):
            result = plugin.routeUpdate(
                mock_device, api_key, mock_plugin_paths, mock_device,
            )
        assert result is True
