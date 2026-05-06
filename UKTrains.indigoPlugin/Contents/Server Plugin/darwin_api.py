# coding=utf-8
"""
Darwin API wrapper functions.

Handles authentication and HTTP calls to the Rail Data Marketplace LDBWS
REST service. Uses `GetDepBoardWithDetails` so calling points arrive
inline — the legacy SOAP workflow's separate `GetServiceDetails` call per
train is no longer needed for the basic departure-board flow.
"""
import sys
from typing import Any, Optional, Tuple

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
    retry = None
    stop_after_attempt = None
    wait_exponential = None
    retry_if_exception_type = None

from nredarwin.webservice import DarwinLdbSession, WebServiceError
import constants


def _log_retry_attempt(retry_state):
    """Callback to log retry attempts for Darwin API calls."""
    attempt_number = retry_state.attempt_number
    if attempt_number > 1:
        try:
            if hasattr(sys.modules['__main__'], 'plugin'):
                plugin = sys.modules['__main__'].plugin
                if hasattr(plugin, 'plugin_logger'):
                    plugin.plugin_logger.warning(
                        f"API call failed (attempt {attempt_number}), retrying in "
                        f"{retry_state.next_action.sleep} seconds..."
                    )
                    return
        except Exception:
            pass
        print(f"WARNING: API call failed (attempt {attempt_number}), retrying...", file=sys.stderr)


def darwin_api_retry(max_attempts: int = 3):
    """Decorator for Darwin API calls with exponential backoff.

    Retries on transient REST/network failures. Falls back to an identity
    decorator if `tenacity` is not installed.
    """
    if retry is None:
        def identity_decorator(func):
            return func
        return identity_decorator

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((WebServiceError, ConnectionError, TimeoutError)),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )


@darwin_api_retry(max_attempts=3)
def _fetch_station_board(
    session: Any,
    start_crs: str,
    end_crs: Optional[str] = None,
    row_limit: int = 100,
) -> Any:
    """Fetch station board with optional destination filter.

    Returns a `StationBoard` whose train services already include inline
    `subsequent_calling_points` (via `GetDepBoardWithDetails`).
    """
    if end_crs and end_crs != constants.ALL_DESTINATIONS_CRS:
        return session.get_station_board(
            start_crs,
            row_limit,
            True,   # include_departures
            False,  # include_arrivals
            end_crs,
        )
    return session.get_station_board(
        start_crs,
        row_limit,
        True,   # include_departures
        False,  # include_arrivals
    )


@darwin_api_retry(max_attempts=2)
def _fetch_service_details(session: Any, service_id: str) -> Optional[Any]:
    """Fetch detailed service info — kept as a compatibility shim.

    The basic raildata "Live Departure Board" product does not include
    `GetServiceDetails`. With `GetDepBoardWithDetails`, the `ServiceItem`
    objects on the board already expose `subsequent_calling_points` directly,
    so the per-service second call is unnecessary in normal use.

    Returns `None` if the endpoint is not available for the subscribed product.
    """
    try:
        return session.get_service_details(service_id)
    except (WebServiceError, ConnectionError, TimeoutError) as e:
        print(f'INFO: Service details endpoint unavailable: {e}', file=sys.stderr)
        return None
    except Exception as e:
        print(f'ERROR: Unexpected error fetching service details: {e}', file=sys.stderr)
        return None


@darwin_api_retry(max_attempts=2)
def nationalRailLogin(api_key: str = 'NO KEY',
                      base_url: Optional[str] = None) -> Tuple[bool, Optional[Any]]:
    """Create a Darwin LDBWS REST session.

    Args:
        api_key: Consumer key issued for the LDBWS product on raildata.org.uk.
        base_url: Optional override for the REST base URL (defaults to the
            "Live Departure Board" product path).

    Returns:
        Tuple of (success, session). `session` is None on failure.
    """
    if not api_key or api_key in ('NO KEY', 'NO KEY ENTERED'):
        print('CRITICAL FAILURE ** Darwin API key is missing — set it in plugin config **',
              file=sys.stderr)
        return False, None

    try:
        return True, DarwinLdbSession(api_key=api_key, base_url=base_url)
    except WebServiceError as e:
        print(f'WARNING ** Failed to create Darwin REST session: {e} **', file=sys.stderr)
        return False, None
    except Exception as e:
        print(f'WARNING ** Failed to log in to Darwin: {e} - check API key and internet connection **',
              file=sys.stderr)
        return False, None
