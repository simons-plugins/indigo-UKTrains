# coding=utf-8
"""
Darwin API wrapper functions

Handles authentication and SOAP calls to National Rail Darwin service.
"""
import sys
from typing import Optional, Any, Tuple

try:
	from zeep.exceptions import Fault as WebFault
except ImportError:
	WebFault = None

try:
	from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
	retry = None
	stop_after_attempt = None
	wait_exponential = None
	retry_if_exception_type = None

from nredarwin.webservice import DarwinLdbSession
import constants


def _log_retry_attempt(retry_state):
	"""Callback to log retry attempts for Darwin API calls."""
	attempt_number = retry_state.attempt_number
	if attempt_number > 1:
		# Get logger from plugin instance if available
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
		# Fallback to print if logger not available
		print(f"WARNING: API call failed (attempt {attempt_number}), retrying...", file=sys.stderr)


def darwin_api_retry(max_attempts: int = 3):
	"""
	Decorator for Darwin API calls with exponential backoff.

	Retries on SOAP/network failures with exponential backoff:
	- Wait 1s, then 2s, then 4s between retries
	- Max 3 attempts by default
	- Only retries on transient errors (network, SOAP faults)

	Args:
		max_attempts: Maximum number of retry attempts (default: 3)

	Returns:
		Retry decorator if tenacity is available, otherwise identity function
	"""
	# Check if tenacity is available
	if retry is None:
		# Tenacity not available, return identity decorator
		def identity_decorator(func):
			return func
		return identity_decorator

	# Import zeep WebFault here to avoid circular dependency
	from zeep.exceptions import Fault as WebFault

	return retry(
		stop=stop_after_attempt(max_attempts),
		wait=wait_exponential(multiplier=1, min=1, max=10),
		retry=retry_if_exception_type((WebFault, ConnectionError, TimeoutError)),
		before_sleep=_log_retry_attempt,
		reraise=True
	)


@darwin_api_retry(max_attempts=3)
def _fetch_station_board(
	session: Any,
	start_crs: str,
	end_crs: Optional[str] = None,
	row_limit: int = 100
) -> Any:
	"""Fetch station board with optional destination filter.
	Retries up to 3 times with exponential backoff on API failures.

	Args:
		session: DarwinLdbSession object for API access
		start_crs: Starting station CRS code
		end_crs: Optional destination CRS code (None or 'ALL' for all destinations)
		row_limit: Maximum number of services to request

	Returns:
		StationBoard object from Darwin API

	Raises:
		zeep.exceptions.Fault: If SOAP request fails after all retries
		Exception: For other API errors after all retries
	"""
	if end_crs and end_crs != constants.ALL_DESTINATIONS_CRS:
		# Filtered by destination
		board = session.get_station_board(
			start_crs,
			row_limit,
			True,   # include_departures
			False,  # include_arrivals
			end_crs
		)
	else:
		# All destinations
		board = session.get_station_board(
			start_crs,
			row_limit,
			True,   # include_departures
			False   # include_arrivals
		)
	return board


@darwin_api_retry(max_attempts=2)
def _fetch_service_details(session: Any, service_id: str) -> Optional[Any]:
	"""Fetch detailed service information from Darwin API.
	Retries up to 2 times with exponential backoff on API failures.

	Args:
		session: DarwinLdbSession object for API access
		service_id: Unique service identifier

	Returns:
		ServiceDetails object or None if fetch failed after all retries
	"""
	try:
		service = session.get_service_details(service_id)
		return service
	except (WebFault, ConnectionError, TimeoutError) as e:
		# Log the error but return None to allow other services to process
		# Note: errorHandler function is in plugin.py - will need to pass or use logger
		print(f'ERROR: Service details fetch failed after retries: {e}', file=sys.stderr)
		return None
	except Exception as e:
		print(f'ERROR: Unexpected error fetching service details: {e}', file=sys.stderr)
		return None


@darwin_api_retry(max_attempts=2)
def nationalRailLogin(wsdl = 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',api_key='NO KEY'):
	"""Login to National Rail Darwin service.
	Retries up to 2 times on connection failures.

	Args:
		wsdl: Darwin WSDL URL
		api_key: Darwin API key

	Returns:
		Tuple of (success: bool, session: DarwinLdbSession or None)
	"""
	if 'realtime.nationalrail' not in wsdl:
		# Darwin address is invalid
		# print error message and return
		# Debug logging removed - use plugin instance logger instead

		# Note: errorHandler function is in plugin.py - will need to pass or use logger
		print(f'CRITICAL FAILURE ** Darwin is invalid - please check or advise developer - {wsdl} **', file=sys.stderr)

		return False, None

	# We have a site and a key now try to use it:
	try:
		darwin_sesh = DarwinLdbSession(wsdl, api_key)
		# Login successful
		# Debug logging removed - use plugin instance logger instead

		return True, darwin_sesh

	except Exception as e:
		# Login failed. As the user to check details and try again
		# Debug logging removed - use plugin instance logger instead

		print(f'WARNING ** Failed to log in to Darwin: {e} - check API key and internet connection', file=sys.stderr)

		return False, None
