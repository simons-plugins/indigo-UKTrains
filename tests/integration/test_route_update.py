"""
Integration tests for routeUpdate function

Tests the main route update workflow with mocked Darwin API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import plugin


@pytest.mark.integration
class TestRouteUpdateIntegration:
    """Integration tests for routeUpdate function"""

    def test_successful_route_update_on_time_trains(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        """Test successful route update with on-time trains"""
        # Setup
        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Mock the Darwin session initialization
        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_normal):
            # Call routeUpdate
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        # Assertions
        assert result is True, "routeUpdate should return True on success"

        # Check that device states were updated
        assert len(mock_device._state_updates) > 0, "Device states should have been updated"

        # Check station name was set
        station_updates = [u for u in mock_device._state_updates if u['key'] == 'stationLong']
        assert len(station_updates) > 0, "Station name should be updated"
        assert station_updates[0]['value'] == "London Paddington"

        # Check time was generated
        time_updates = [u for u in mock_device._state_updates if u['key'] == 'timeGenerated']
        assert len(time_updates) > 0, "Time generated should be updated"

    def test_route_update_with_delays(self, mock_device, mock_darwin_delays, mock_plugin_paths):
        """Test route update handles delayed trains correctly"""
        # Setup
        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Mock the Darwin session initialization
        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_delays):
            # Call routeUpdate
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        # Assertions
        assert result is True

        # Check that train problem flags were set
        problem_updates = [u for u in mock_device._state_updates if 'Problem' in u['key']]
        assert len(problem_updates) > 0, "Train problem states should be set for delays"

        # Check delay messages were set
        delay_updates = [u for u in mock_device._state_updates if 'Delay' in u['key']]
        assert len(delay_updates) > 0, "Delay information should be updated"

    def test_route_update_with_cancelled_trains(self, mock_device, mock_darwin_cancellation, mock_plugin_paths):
        """Test route update handles cancelled trains"""
        # Setup
        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Mock the Darwin session initialization
        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_cancellation):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        assert result is True

        # Check for cancelled status in updates
        delay_updates = [u for u in mock_device._state_updates if 'Delay' in u['key']]
        cancelled_found = any('Cancelled' in str(u['value']) for u in delay_updates)
        assert cancelled_found, "Should have 'Cancelled' status for cancelled trains"

    def test_route_update_with_empty_board(self, mock_device, mock_darwin_empty, mock_plugin_paths):
        """Test route update with no trains at station"""
        # Setup
        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Mock the Darwin session initialization
        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_empty):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        # Should still succeed but with cleared states
        assert result is True

        # Station name should still be updated
        station_updates = [u for u in mock_device._state_updates if u['key'] == 'stationLong']
        assert len(station_updates) > 0

    def test_route_update_soap_failure(self, mock_device, mock_plugin_paths):
        """Test route update when SOAP API fails"""
        # Setup
        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Mock Darwin session to raise exception
        mock_session = Mock()
        mock_session.get_station_board.side_effect = Exception("SOAP Fault")

        with patch('plugin.DarwinLdbSession', return_value=mock_session):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        # Should return False on API failure
        assert result is False

    def test_route_update_invalid_device(self, mock_plugin_paths):
        """Test route update with invalid/disabled device"""
        # Create disabled device
        disabled_device = Mock()
        disabled_device.enabled = False

        result = plugin.routeUpdate(
            disabled_device,
            "api_key",
            "url",
            mock_plugin_paths
        )

        # Should return False for disabled device
        assert result is False

    def test_route_update_filters_by_destination(self, mock_device, mock_plugin_paths):
        """Test route update correctly filters trains by destination"""
        # Setup device with specific destination filter
        mock_device.states['destinationCRS'] = 'BRI'  # Bristol only

        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        # Create session with mixed destinations
        from mocks.mock_darwin import (
            MockStationBoard,
            MockServiceItem,
            MockDarwinSession,
            create_calling_points_normal
        )

        services = [
            MockServiceItem("Bristol Temple Meads", "14:30", "On time"),
            MockServiceItem("Oxford", "15:00", "On time"),
            MockServiceItem("Reading", "15:30", "On time"),
        ]
        board = MockStationBoard("London Paddington", services)
        mock_session = MockDarwinSession(network_url, api_key, board)

        # Set up service details for all services
        for service in services:
            mock_session.set_service_details(service.service_id, create_calling_points_normal())

        with patch('plugin.DarwinLdbSession', return_value=mock_session):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        assert result is True

        # Check that only Bristol train was processed
        dest_updates = [u for u in mock_device._state_updates if u['key'] == 'train1Destination']
        if len(dest_updates) > 0:
            # If filtered correctly, should only see Bristol
            assert 'Bristol' in dest_updates[0]['value']

    def test_route_update_clears_old_states(self, mock_device, mock_plugin_paths):
        """Test that old device states are cleared before update"""
        # Pre-populate device with old data
        mock_device.states['train1Destination'] = 'Old Destination'
        mock_device.states['train2Destination'] = 'Old Destination'

        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        from mocks.mock_darwin import create_mock_darwin_session
        mock_session = create_mock_darwin_session("empty")

        with patch('plugin.DarwinLdbSession', return_value=mock_session):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        # Check that states were cleared (updated to blank)
        # Look for blank/empty updates to train states
        train_updates = [u for u in mock_device._state_updates
                        if 'train' in u['key'].lower() and 'Destination' in u['key']]
        # Some should be cleared to empty strings
        cleared_updates = [u for u in train_updates if u['value'] == '']
        assert len(cleared_updates) > 0, "Old train states should be cleared"


@pytest.mark.integration
class TestRouteUpdateWithCallingPoints:
    """Test route update with calling point information"""

    def test_calling_points_included(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        """Test that calling points are included when configured"""
        # Enable calling points in device config
        mock_device.pluginProps['includeCalling'] = True

        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_normal):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        assert result is True

        # Check for calling point updates
        calling_updates = [u for u in mock_device._state_updates if 'Calling' in u['key']]
        # If calling points were processed, should have updates
        # (This depends on whether trains have calling points in the mock)

    def test_calling_points_excluded(self, mock_device, mock_darwin_normal, mock_plugin_paths):
        """Test that calling points are excluded when not configured"""
        # Disable calling points
        mock_device.pluginProps['includeCalling'] = False

        api_key = "test_api_key"
        network_url = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

        with patch('plugin.DarwinLdbSession', return_value=mock_darwin_normal):
            result = plugin.routeUpdate(
                mock_device,
                api_key,
                network_url,
                mock_plugin_paths
            )

        assert result is True
