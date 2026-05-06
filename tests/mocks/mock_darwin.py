"""
Mock Darwin REST responses for testing.

Builds JSON dicts in the shape returned by the raildata.org.uk LDBWS REST
service (`GetDepBoardWithDetails`) and wraps them in the real
`nredarwin.webservice` classes — so tests exercise the production wrapper
layer rather than a parallel mock hierarchy.
"""

from typing import Iterable, List, Optional

# Production wrappers — tests use the real classes against synthetic JSON
from nredarwin.webservice import StationBoard, ServiceItem, CallingPoint


# ---------------------------------------------------------------------------
# Calling-point and service factories (return raw dicts)
# ---------------------------------------------------------------------------

def calling_point_dict(location_name: str, st: str, et: str = "On time",
                       crs: str = "") -> dict:
    return {
        "locationName": location_name,
        "crs": crs,
        "st": st,
        "et": et,
        "isCancelled": False,
    }


def service_dict(destination_name: str,
                 std: str,
                 etd: str = "On time",
                 operator: str = "Great Western Railway",
                 operator_code: str = "GW",
                 service_id: str = "service_on_time_001",
                 platform: Optional[str] = None,
                 calling_points: Optional[Iterable[dict]] = None,
                 is_cancelled: bool = False,
                 destination_crs: str = "") -> dict:
    return {
        "std": std,
        "etd": etd,
        "operator": operator,
        "operatorCode": operator_code,
        "serviceID": service_id,
        "platform": platform,
        "isCancelled": is_cancelled,
        "isCircularRoute": False,
        "destination": [{"locationName": destination_name, "crs": destination_crs}],
        "origin": [{"locationName": "London Paddington", "crs": "PAD"}],
        "subsequentCallingPoints": (
            [{"callingPoint": list(calling_points)}] if calling_points else []
        ),
    }


def station_board_dict(location_name: str = "London Paddington",
                       crs: str = "PAD",
                       services: Optional[List[dict]] = None,
                       nrcc_messages: Optional[List[str]] = None) -> dict:
    return {
        "locationName": location_name,
        "crs": crs,
        "generatedAt": "2026-05-06T10:30:00.0000000+01:00",
        "trainServices": services or [],
        "nrccMessages": [{"Value": m} for m in (nrcc_messages or [])],
    }


# ---------------------------------------------------------------------------
# Backwards-compat helpers (legacy names used by existing tests)
# ---------------------------------------------------------------------------

def create_calling_points_normal() -> List[dict]:
    return [
        calling_point_dict("Slough", "14:35"),
        calling_point_dict("Reading", "14:45"),
        calling_point_dict("Didcot Parkway", "15:05"),
        calling_point_dict("Swindon", "15:25"),
        calling_point_dict("Bristol Temple Meads", "16:00"),
    ]


def create_calling_points_delayed() -> List[dict]:
    return [
        calling_point_dict("Slough", "15:50", "15:55"),
        calling_point_dict("Reading", "16:00", "16:10"),
        calling_point_dict("Oxford", "16:30", "16:50"),
    ]


def create_on_time_service() -> ServiceItem:
    return ServiceItem(service_dict(
        destination_name="Bristol Temple Meads",
        std="14:30",
        etd="On time",
        service_id="service_on_time_001",
        calling_points=create_calling_points_normal(),
    ))


def create_delayed_service() -> ServiceItem:
    return ServiceItem(service_dict(
        destination_name="Oxford",
        std="15:45",
        etd="16:05",
        service_id="service_delayed_001",
        calling_points=create_calling_points_delayed(),
    ))


def create_cancelled_service() -> ServiceItem:
    return ServiceItem(service_dict(
        destination_name="Reading",
        std="12:15",
        etd="Cancelled",
        service_id="service_cancelled_001",
        is_cancelled=True,
    ))


def create_early_service() -> ServiceItem:
    return ServiceItem(service_dict(
        destination_name="Swansea",
        std="16:00",
        etd="15:57",
        service_id="service_early_001",
        calling_points=create_calling_points_normal(),
    ))


def create_station_board_paddington() -> StationBoard:
    services = [
        service_dict("Bristol Temple Meads", "14:30",
                     service_id="service_on_time_001",
                     calling_points=create_calling_points_normal()),
        service_dict("Oxford", "15:45", etd="16:05",
                     service_id="service_delayed_001",
                     calling_points=create_calling_points_delayed()),
        service_dict("Swansea", "16:00", etd="15:57",
                     service_id="service_early_001",
                     calling_points=create_calling_points_normal()),
    ]
    return StationBoard(station_board_dict(services=services))


def create_station_board_with_cancellation() -> StationBoard:
    services = [
        service_dict("Bristol Temple Meads", "14:30",
                     service_id="service_on_time_001",
                     calling_points=create_calling_points_normal()),
        service_dict("Reading", "12:15", etd="Cancelled",
                     service_id="service_cancelled_001",
                     is_cancelled=True),
        service_dict("Oxford", "15:45", etd="16:05",
                     service_id="service_delayed_001",
                     calling_points=create_calling_points_delayed()),
    ]
    return StationBoard(station_board_dict(services=services))


def create_empty_station_board() -> StationBoard:
    return StationBoard(station_board_dict(services=[]))


# ---------------------------------------------------------------------------
# Mock REST session — matches the new DarwinLdbSession surface
# ---------------------------------------------------------------------------

class MockDarwinSession:
    """Test double for the new REST-based DarwinLdbSession."""

    def __init__(self, api_key: str = "test_api_key",
                 base_url: Optional[str] = None,
                 station_board: Optional[StationBoard] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._station_board = station_board or create_station_board_paddington()

    def get_station_board(self, crs, rows=10, include_departures=True,
                          include_arrivals=False, destination_crs=None,
                          origin_crs=None):
        if destination_crs and destination_crs != "ALL":
            filtered = [
                svc for svc in self._station_board.train_services
                if destination_crs.lower() in svc.destination_text.lower()
            ]
            data = station_board_dict(
                location_name=self._station_board.location_name,
                crs=self._station_board.crs or "PAD",
                services=[svc._data for svc in filtered],
            )
            return StationBoard(data)
        return self._station_board

    def get_service_details(self, service_id):
        # Calling points are inline on ServiceItem in the new flow,
        # so this method is rarely used. Return the matching ServiceItem
        # if present, else None.
        for svc in self._station_board.train_services:
            if svc.service_id == service_id:
                return svc
        return None


def create_mock_darwin_session(scenario: str = "normal") -> MockDarwinSession:
    """Build a MockDarwinSession for a named scenario."""
    delay = service_dict("Oxford", "15:45", etd="16:05",
                         service_id="service_delayed_001",
                         calling_points=create_calling_points_delayed())
    cancel = service_dict("Reading", "12:15", etd="Cancelled",
                          service_id="service_cancelled_001",
                          is_cancelled=True)
    on_time = service_dict("Bristol Temple Meads", "14:30",
                           service_id="service_on_time_001",
                           calling_points=create_calling_points_normal())
    early = service_dict("Swansea", "16:00", etd="15:57",
                         service_id="service_early_001",
                         calling_points=create_calling_points_normal())

    boards = {
        "normal": create_station_board_paddington(),
        "delays": StationBoard(station_board_dict(services=[delay, delay])),
        "cancellation": create_station_board_with_cancellation(),
        "empty": create_empty_station_board(),
        "mixed": StationBoard(station_board_dict(services=[on_time, delay, cancel, early])),
    }
    return MockDarwinSession(station_board=boards.get(scenario, boards["normal"]))
