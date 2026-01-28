"""
Mock Darwin API responses for testing

Provides mock SOAP responses that simulate the National Rail Darwin API
"""

from unittest.mock import Mock


class MockCallingPoint:
    """Mock calling point (station) on a route"""

    def __init__(self, location_name, st, et="On time"):
        self.location_name = location_name
        self.st = st  # Scheduled time
        self.et = et  # Estimated time


class MockServiceItem:
    """Mock service item (train) from station board"""

    def __init__(self, destination_text, std, etd, operator_name="GWR", service_id="test_service_123"):
        self.destination_text = destination_text
        self.std = std  # Scheduled departure
        self.etd = etd  # Estimated departure
        self.operator_name = operator_name
        self.service_id = service_id


class MockServiceDetails:
    """Mock detailed service information"""

    def __init__(self, calling_points=None):
        self.subsequent_calling_points = calling_points or []


class MockStationBoard:
    """Mock station departure board"""

    def __init__(self, location_name, train_services=None):
        self.location_name = location_name
        self.train_services = train_services or []


# Sample fixture data

def create_on_time_service():
    """Create a service that's running on time"""
    return MockServiceItem(
        destination_text="Bristol Temple Meads",
        std="14:30",
        etd="On time",
        operator_name="Great Western Railway",
        service_id="service_on_time_001"
    )


def create_delayed_service():
    """Create a service that's delayed"""
    return MockServiceItem(
        destination_text="Oxford",
        std="15:45",
        etd="16:05",  # 20 minutes late
        operator_name="Great Western Railway",
        service_id="service_delayed_001"
    )


def create_cancelled_service():
    """Create a cancelled service"""
    return MockServiceItem(
        destination_text="Reading",
        std="12:15",
        etd="Cancelled",
        operator_name="Great Western Railway",
        service_id="service_cancelled_001"
    )


def create_early_service():
    """Create a service running early"""
    return MockServiceItem(
        destination_text="Swansea",
        std="16:00",
        etd="15:57",  # 3 minutes early
        operator_name="Great Western Railway",
        service_id="service_early_001"
    )


def create_calling_points_normal():
    """Create normal calling points for a service"""
    return [
        MockCallingPoint("Slough", "14:35", "On time"),
        MockCallingPoint("Reading", "14:45", "On time"),
        MockCallingPoint("Didcot Parkway", "15:05", "On time"),
        MockCallingPoint("Swindon", "15:25", "On time"),
        MockCallingPoint("Bristol Temple Meads", "16:00", "On time"),
    ]


def create_calling_points_delayed():
    """Create delayed calling points"""
    return [
        MockCallingPoint("Slough", "15:50", "15:55"),  # 5 min delay
        MockCallingPoint("Reading", "16:00", "16:10"),  # 10 min delay
        MockCallingPoint("Oxford", "16:30", "16:50"),  # 20 min delay
    ]


def create_station_board_paddington():
    """Create a mock station board for London Paddington"""
    services = [
        create_on_time_service(),
        create_delayed_service(),
        create_early_service(),
    ]
    return MockStationBoard("London Paddington", services)


def create_station_board_with_cancellation():
    """Create a station board including a cancelled service"""
    services = [
        create_on_time_service(),
        create_cancelled_service(),
        create_delayed_service(),
    ]
    return MockStationBoard("London Paddington", services)


def create_empty_station_board():
    """Create an empty station board (no services)"""
    return MockStationBoard("London Paddington", [])


class MockDarwinSession:
    """Mock Darwin SOAP session"""

    def __init__(self, wsdl, api_key, station_board=None):
        self.wsdl = wsdl
        self.api_key = api_key
        self._station_board = station_board or create_station_board_paddington()
        self._service_details = {}

    def get_station_board(self, crs_code, num_rows=100, include_departures=True,
                          include_arrivals=False, destination_crs=None):
        """Mock get_station_board SOAP call"""
        if destination_crs and destination_crs != 'ALL':
            # Filter services to destination
            filtered_services = [
                svc for svc in self._station_board.train_services
                if destination_crs.lower() in svc.destination_text.lower()
            ]
            return MockStationBoard(self._station_board.location_name, filtered_services)

        return self._station_board

    def get_service_details(self, service_id):
        """Mock get_service_details SOAP call"""
        # Return cached service details or create default
        if service_id in self._service_details:
            return self._service_details[service_id]

        # Default: service with normal calling points
        return MockServiceDetails(create_calling_points_normal())

    def set_service_details(self, service_id, calling_points):
        """Helper to set specific calling points for a service"""
        self._service_details[service_id] = MockServiceDetails(calling_points)


def create_mock_darwin_session(scenario="normal"):
    """
    Factory to create mock Darwin session with different scenarios

    Scenarios:
    - "normal": On-time services with normal calling points
    - "delays": Services with various delays
    - "cancellation": Includes cancelled services
    - "empty": No services
    - "mixed": Mix of on-time, delayed, and cancelled
    """
    scenarios = {
        "normal": create_station_board_paddington(),
        "delays": MockStationBoard("London Paddington", [
            create_delayed_service(),
            create_delayed_service(),
        ]),
        "cancellation": create_station_board_with_cancellation(),
        "empty": create_empty_station_board(),
        "mixed": MockStationBoard("London Paddington", [
            create_on_time_service(),
            create_delayed_service(),
            create_cancelled_service(),
            create_early_service(),
        ]),
    }

    board = scenarios.get(scenario, create_station_board_paddington())
    session = MockDarwinSession(
        wsdl="https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx",
        api_key="test_api_key",
        station_board=board
    )

    # Set up service details for each service
    for service in board.train_services:
        if "delayed" in service.service_id.lower():
            session.set_service_details(service.service_id, create_calling_points_delayed())
        else:
            session.set_service_details(service.service_id, create_calling_points_normal())

    return session
