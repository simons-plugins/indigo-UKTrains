"""
Darwin LDBWS REST client.

Replaces the legacy SOAP/zeep client with the Rail Data Marketplace JSON API.
Authenticates via the `x-apikey` header against api1.raildata.org.uk.

The wrapper classes (`StationBoard`, `ServiceItem`, `ServiceLocation`,
`ServiceDetails`, `CallingPoint`, `CallingPointList`) preserve the public
attribute surface the rest of the plugin reads, so `device_manager.py` and
`plugin.py` keep working with minimal change.
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


log = logging.getLogger(__name__)

DARWIN_REST_BASE_URL_DEFAULT = (
    'https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120'
)


class WebServiceError(Exception):
    """Raised for any HTTP / network / response error from the LDBWS REST API."""


class DarwinLdbSession:
    """REST connection to the Rail Data Marketplace LDBWS service."""

    def __init__(self, api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 timeout: int = 10):
        if api_key is None:
            api_key = os.environ.get('DARWIN_API_KEY') \
                or os.environ.get('DARWIN_WEBSERVICE_API_KEY')
        if not api_key:
            raise WebServiceError('Darwin API key is required')
        if base_url is None:
            base_url = os.environ.get('DARWIN_REST_BASE_URL') \
                or DARWIN_REST_BASE_URL_DEFAULT

        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f'{self._base_url}/{path.lstrip("/")}'
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url = f'{url}?{urllib.parse.urlencode(cleaned)}'

        req = urllib.request.Request(
            url,
            headers={
                'x-apikey': self._api_key,
                'Accept': 'application/json',
                # Apigee at api1.raildata.org.uk rejects the default
                # `Python-urllib/x.y` agent with 403; send a plain UA.
                'User-Agent': 'UKTrains-IndigoPlugin/2026.1',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as e:
            detail = ''
            try:
                detail = e.read().decode('utf-8', errors='replace')[:200]
            except Exception:
                pass
            raise WebServiceError(
                f'Darwin REST {e.code} {e.reason}: {detail}'
            ) from e
        except urllib.error.URLError as e:
            raise WebServiceError(f'Darwin REST network error: {e.reason}') from e
        try:
            return json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as e:
            raise WebServiceError(f'Darwin REST returned non-JSON body: {e}') from e

    def get_station_board(self, crs, rows=10, include_departures=True,
                          include_arrivals=False, destination_crs=None,
                          origin_crs=None):
        """Fetch a station departure/arrival board with calling points inline.

        Uses `GetDepBoardWithDetails` so subsequent calling points arrive in
        the same request — no separate `GetServiceDetails` call needed.
        """
        if include_departures and include_arrivals:
            endpoint = 'GetArrDepBoardWithDetails'
        elif include_arrivals:
            endpoint = 'GetArrBoardWithDetails'
        else:
            endpoint = 'GetDepBoardWithDetails'

        params = {'numRows': rows}
        if destination_crs:
            params['filterCrs'] = destination_crs
            params['filterType'] = 'to'
        elif origin_crs:
            params['filterCrs'] = origin_crs
            params['filterType'] = 'from'

        data = self._get(f'{endpoint}/{urllib.parse.quote(crs, safe="")}', params)
        return StationBoard(data)

    def get_service_details(self, service_id):
        """Fetch detailed info for one service.

        Note: the basic "Live Departure Board" raildata product does not include
        this endpoint — `get_station_board` already returns calling points
        inline via `GetDepBoardWithDetails`. This method remains for callers
        that have subscribed to a fuller LDBWS product.
        """
        data = self._get(f'GetServiceDetails/{urllib.parse.quote(service_id, safe="")}')
        return ServiceDetails(data)


class _JsonBacked:
    """Read-only wrapper around a parsed JSON object."""

    def __init__(self, data: Optional[dict]):
        self._data = data or {}


class StationBoard(_JsonBacked):
    """A station departure (or arrival) board."""

    @property
    def generated_at(self):
        return self._data.get('generatedAt')

    @property
    def crs(self):
        return self._data.get('crs')

    @property
    def location_name(self):
        return self._data.get('locationName')

    @property
    def train_services(self):
        return [ServiceItem(s) for s in self._data.get('trainServices') or []]

    @property
    def bus_services(self):
        return [ServiceItem(s) for s in self._data.get('busServices') or []]

    @property
    def ferry_services(self):
        return [ServiceItem(s) for s in self._data.get('ferryServices') or []]

    @property
    def nrcc_messages(self):
        # JSON shape: array of {Value: "...", severity?: "..."}
        out = []
        for msg in self._data.get('nrccMessages') or []:
            if isinstance(msg, dict):
                out.append(msg.get('Value') or msg.get('value') or '')
            else:
                out.append(msg)
        return out

    def __str__(self):
        return f'{self.crs} - {self.location_name}'


class _ServiceCommon(_JsonBacked):
    """Fields shared by `ServiceItem` and `ServiceDetails`."""

    @property
    def sta(self): return self._data.get('sta')
    @property
    def eta(self): return self._data.get('eta')
    @property
    def std(self): return self._data.get('std')
    @property
    def etd(self): return self._data.get('etd')
    @property
    def platform(self): return self._data.get('platform')
    @property
    def operator_name(self): return self._data.get('operator')
    @property
    def operator_code(self): return self._data.get('operatorCode')
    @property
    def is_cancelled(self): return bool(self._data.get('isCancelled'))


class ServiceItem(_ServiceCommon):
    """A single service from a board.

    With `GetDepBoardWithDetails` this also exposes inline calling points,
    so callers can read `subsequent_calling_points` directly without a
    separate `GetServiceDetails` round-trip.
    """

    @property
    def is_circular_route(self):
        return bool(self._data.get('isCircularRoute'))

    @property
    def service_id(self):
        return self._data.get('serviceID') or self._data.get('serviceId')

    @property
    def origins(self):
        return [ServiceLocation(o) for o in self._data.get('origin') or []]

    @property
    def destinations(self):
        return [ServiceLocation(d) for d in self._data.get('destination') or []]

    @property
    def destination_text(self):
        return ', '.join(str(d) for d in self.destinations)

    @property
    def origin_text(self):
        return ', '.join(str(o) for o in self.origins)

    @property
    def subsequent_calling_point_lists(self):
        return [CallingPointList(cpl)
                for cpl in self._data.get('subsequentCallingPoints') or []]

    @property
    def previous_calling_point_lists(self):
        return [CallingPointList(cpl)
                for cpl in self._data.get('previousCallingPoints') or []]

    @property
    def subsequent_calling_points(self):
        out = []
        for cpl in self.subsequent_calling_point_lists:
            out.extend(cpl.calling_points)
        return out

    @property
    def previous_calling_points(self):
        out = []
        for cpl in self.previous_calling_point_lists:
            out.extend(cpl.calling_points)
        return out

    def __str__(self):
        return f'Service {self.service_id}'


class ServiceLocation(_JsonBacked):
    @property
    def location_name(self): return self._data.get('locationName')
    @property
    def crs(self): return self._data.get('crs')
    @property
    def via(self): return self._data.get('via')
    @property
    def future_change_to(self): return self._data.get('futureChangeTo')

    def __str__(self):
        name = self.location_name or ''
        return f'{name} {self.via}' if self.via else name


class ServiceDetails(_ServiceCommon):
    """Full service-detail response (legacy `GetServiceDetails`)."""

    @property
    def disruption_reason(self): return self._data.get('disruptionReason')
    @property
    def overdue_message(self): return self._data.get('overdueMessage')
    @property
    def ata(self): return self._data.get('ata')
    @property
    def atd(self): return self._data.get('atd')
    @property
    def location_name(self): return self._data.get('locationName')
    @property
    def crs(self): return self._data.get('crs')

    @property
    def previous_calling_point_lists(self):
        return [CallingPointList(cpl)
                for cpl in self._data.get('previousCallingPoints') or []]

    @property
    def subsequent_calling_point_lists(self):
        return [CallingPointList(cpl)
                for cpl in self._data.get('subsequentCallingPoints') or []]

    @property
    def previous_calling_points(self):
        out = []
        for cpl in self.previous_calling_point_lists:
            out.extend(cpl.calling_points)
        return out

    @property
    def subsequent_calling_points(self):
        out = []
        for cpl in self.subsequent_calling_point_lists:
            out.extend(cpl.calling_points)
        return out


class CallingPointList(_JsonBacked):
    @property
    def service_type(self):
        return self._data.get('serviceType') or self._data.get('_serviceType')

    @property
    def service_change_required(self):
        return bool(self._data.get('serviceChangeRequired')
                    or self._data.get('_serviceChangeRequired'))

    @property
    def association_is_cancelled(self):
        return bool(self._data.get('assocIsCancelled')
                    or self._data.get('_assocIsCancelled'))

    @property
    def calling_points(self):
        return [CallingPoint(cp) for cp in self._data.get('callingPoint') or []]


class CallingPoint(_JsonBacked):
    @property
    def location_name(self): return self._data.get('locationName')
    @property
    def crs(self): return self._data.get('crs')
    @property
    def at(self): return self._data.get('at')
    @property
    def et(self): return self._data.get('et')
    @property
    def st(self): return self._data.get('st')
