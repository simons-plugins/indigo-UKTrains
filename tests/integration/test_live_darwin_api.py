"""
Live Darwin API Integration Tests

These tests make REAL calls to the Darwin API and are SKIPPED by default.

To run these tests, you need:
1. A valid Darwin API key
2. Set environment variable: export DARWIN_API_KEY="your_key_here"
3. Run with: pytest -m live_api tests/integration/test_live_darwin_api.py

WARNING: These tests make real API calls and will:
- Use your API quota
- Depend on live train services (results vary by time of day)
- Require internet connection
- May be slower than mocked tests

Use these tests to:
- Verify mock responses match real API behavior
- Test with actual live data
- Discover edge cases in real responses
- Validate API integration before production
"""

import pytest
import os
from nredarwin.webservice import DarwinLdbSession


# Skip all tests in this file unless explicitly requested
pytestmark = pytest.mark.live_api


@pytest.fixture
def darwin_api_key():
    """Get Darwin API key from environment variable"""
    api_key = os.getenv('DARWIN_API_KEY')
    if not api_key:
        pytest.skip("DARWIN_API_KEY environment variable not set")
    return api_key


@pytest.fixture
def darwin_wsdl():
    """Darwin WSDL URL"""
    return os.getenv(
        'DARWIN_WSDL',
        'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'
    )


@pytest.fixture
def live_darwin_session(darwin_api_key, darwin_wsdl):
    """Create a live Darwin session"""
    try:
        session = DarwinLdbSession(darwin_wsdl, darwin_api_key)
        return session
    except Exception as e:
        pytest.fail(f"Failed to create Darwin session: {e}")


class TestLiveDarwinAPI:
    """Tests using real Darwin API calls"""

    def test_can_connect_to_darwin(self, live_darwin_session):
        """Test that we can successfully connect to Darwin API"""
        assert live_darwin_session is not None
        # If we got here, the session was created successfully

    def test_get_station_board_london_paddington(self, live_darwin_session):
        """Test getting station board for London Paddington (PAD)"""
        board = live_darwin_session.get_station_board('PAD')

        # Verify board structure
        assert hasattr(board, 'location_name')
        assert 'Paddington' in board.location_name

        # Board should have train services (unless it's very late at night)
        # We can't assert this because it depends on time of day
        if hasattr(board, 'train_services') and board.train_services:
            print(f"\nFound {len(board.train_services)} services at {board.location_name}")

            # Check first service structure
            service = board.train_services[0]
            assert hasattr(service, 'destination_text')
            assert hasattr(service, 'std')  # Scheduled departure
            assert hasattr(service, 'etd')  # Estimated departure
            assert hasattr(service, 'operator_name')

            print(f"Sample service: {service.destination_text} at {service.std} (est: {service.etd})")

    def test_get_filtered_station_board(self, live_darwin_session):
        """Test getting filtered station board (PAD to Bristol)"""
        # Paddington to Bristol Temple Meads
        board = live_darwin_session.get_station_board(
            crs_code='PAD',
            num_rows=10,
            include_departures=True,
            include_arrivals=False,
            destination_crs='BRI'
        )

        assert hasattr(board, 'location_name')
        assert 'Paddington' in board.location_name

        # Check that services are filtered (if any exist)
        if hasattr(board, 'train_services') and board.train_services:
            for service in board.train_services:
                # All services should mention Bristol in destination
                assert 'Bristol' in service.destination_text or \
                       'BRI' in str(service), \
                       f"Expected Bristol service, got: {service.destination_text}"

    def test_get_service_details(self, live_darwin_session):
        """Test getting detailed service information"""
        # First get a station board to get a service ID
        board = live_darwin_session.get_station_board('PAD', num_rows=5)

        if hasattr(board, 'train_services') and board.train_services:
            service_id = board.train_services[0].service_id

            # Get full service details
            details = live_darwin_session.get_service_details(service_id)

            # Verify details structure
            # Note: subsequent_calling_points might be None for some services
            if hasattr(details, 'subsequent_calling_points'):
                calling_points = details.subsequent_calling_points
                if calling_points:
                    print(f"\nService stops at {len(calling_points)} stations:")
                    for cp in calling_points[:3]:  # Show first 3
                        print(f"  - {cp.location_name} at {cp.st}")

    @pytest.mark.parametrize("crs_code,expected_name", [
        ("PAD", "Paddington"),
        ("VIC", "Victoria"),
        ("WAT", "Waterloo"),
        ("KGX", "King's Cross"),
        ("LST", "Liverpool Street"),
    ])
    def test_major_london_stations(self, live_darwin_session, crs_code, expected_name):
        """Test getting boards for major London stations"""
        board = live_darwin_session.get_station_board(crs_code, num_rows=5)

        assert hasattr(board, 'location_name')
        assert expected_name in board.location_name, \
            f"Expected {expected_name} in {board.location_name}"

    def test_invalid_crs_code(self, live_darwin_session):
        """Test that invalid CRS codes are handled properly"""
        with pytest.raises(Exception):
            # 'XXX' is not a valid CRS code
            live_darwin_session.get_station_board('XXX')

    def test_station_with_no_services(self, live_darwin_session):
        """Test station that might have no services (late at night)"""
        # Some small stations have limited services
        try:
            board = live_darwin_session.get_station_board('BDM')  # Bedwyn (small station)

            # Board should exist even if no services
            assert hasattr(board, 'location_name')

            # Services might be None or empty list
            if hasattr(board, 'train_services'):
                services = board.train_services
                if services:
                    print(f"\nBedwyn has {len(services)} services")
                else:
                    print("\nBedwyn has no current services (expected for small station)")
        except Exception as e:
            # If the station doesn't exist in Darwin, that's also valid
            print(f"\nStation not found in Darwin (expected): {e}")


class TestLiveAPIResponseFormats:
    """Tests to verify our mocks match real API response formats"""

    def test_on_time_service_format(self, live_darwin_session):
        """Verify format of on-time services matches our mocks"""
        board = live_darwin_session.get_station_board('PAD', num_rows=20)

        if hasattr(board, 'train_services') and board.train_services:
            for service in board.train_services:
                if hasattr(service, 'etd') and 'On time' in service.etd:
                    # Verify our mock matches real format
                    assert hasattr(service, 'destination_text')
                    assert hasattr(service, 'std')
                    assert hasattr(service, 'operator_name')
                    print(f"\nOn-time service found: {service.destination_text}")
                    break

    def test_delayed_service_format(self, live_darwin_session):
        """Verify format of delayed services matches our mocks"""
        board = live_darwin_session.get_station_board('PAD', num_rows=50)

        if hasattr(board, 'train_services') and board.train_services:
            for service in board.train_services:
                # Look for actual time (HH:MM format) instead of "On time"
                if hasattr(service, 'etd') and ':' in service.etd and \
                   service.etd != service.std:
                    print(f"\nDelayed service found:")
                    print(f"  Destination: {service.destination_text}")
                    print(f"  Scheduled: {service.std}")
                    print(f"  Estimated: {service.etd}")

                    # Calculate delay manually
                    import plugin
                    has_problem, delay_msg = plugin.delayCalc(service.etd, service.std)
                    print(f"  Delay: {delay_msg}")
                    assert has_problem  # Should be marked as problem
                    break


# Example usage documentation
"""
How to run these tests:

1. Get a Darwin API key from:
   https://www.nationalrail.co.uk/developers/

2. Set your API key:
   export DARWIN_API_KEY="your_actual_key_here"

3. Run the live API tests:
   cd tests
   pytest -m live_api integration/test_live_darwin_api.py -v

4. Run a specific test:
   pytest -m live_api integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_get_station_board_london_paddington -v

5. Run with output:
   pytest -m live_api integration/test_live_darwin_api.py -v -s

6. To skip these tests (default behavior):
   pytest  # These tests are automatically skipped

Note: These tests may fail outside UK working hours when few trains run.
"""
