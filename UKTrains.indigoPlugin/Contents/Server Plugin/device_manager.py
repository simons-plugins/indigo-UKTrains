# coding=utf-8
"""
Device state management for UK-Trains plugin

Functions for updating Indigo device states.
"""
from typing import Any, Optional, List
import constants
from constants import TrainStatus
from text_formatter import delayCalc, formatSpecials
from darwin_api import _fetch_service_details
from error_classification import classify_exception


def _clear_device_states(dev: Any) -> None:
	"""Clear all train states on device before update.

	Args:
		dev: Indigo device object to clear
	"""
	# Clear all train data (up to MAX_TRAINS_TRACKED)
	for trainNum in range(1, constants.MAX_TRAINS_TRACKED + 1):
		train_prefix = f'train{trainNum}'
		dev.updateStateOnServer(f'{train_prefix}Dest', value='')
		dev.updateStateOnServer(f'{train_prefix}Op', value='')
		dev.updateStateOnServer(f'{train_prefix}Sch', value='')
		dev.updateStateOnServer(f'{train_prefix}Est', value='')
		dev.updateStateOnServer(f'{train_prefix}Delay', value='')
		dev.updateStateOnServer(f'{train_prefix}Issue', value=False)
		dev.updateStateOnServer(f'{train_prefix}Reason', value='')
		dev.updateStateOnServer(f'{train_prefix}Calling', value='')
		dev.updateStateOnServer(f'{train_prefix}Platform', value='')

	# Clear station issues flag
	dev.updateStateOnServer('stationIssues', value=False)


def _update_station_issues_flag(dev: Any) -> None:
	"""Check if any train has issues and update station-level flag.

	Args:
		dev: Indigo device object to update
	"""
	# Check all trains for issues
	for trainNum in range(1, constants.MAX_TRAINS_TRACKED + 1):
		train_issue_state = f'train{trainNum}Issue'
		if dev.states.get(train_issue_state, False):
			dev.updateStateOnServer('stationIssues', value=True)
			return
	# If we get here, no issues found
	dev.updateStateOnServer('stationIssues', value=False)


def _process_special_messages(board: Any, dev: Any, testing_mode: bool = False) -> str:
	"""Extract and format NRCC special messages from station board.

	Args:
		board: StationBoard object from Darwin API
		dev: Indigo device object to update with messages
		testing_mode: Boolean flag for testing (default: False)

	Returns:
		Formatted special messages string (empty if no messages)
	"""
	# Check if there are messages to process
	has_messages = (hasattr(board, 'nrcc_messages') and
	                len(board.nrcc_messages) > 0)

	if not has_messages and not testing_mode:
		return ''

	if testing_mode:
		# Test message for BETA
		special_messages = ('This is a test message that would span a lot of lines in the display.  '
		                   'We need to format it correctly and remove any special characters&nbspBecause '
		                   'it is so long it will take a lot of lines on the display and this should be managed'
		                   ' through the maxLines element')
	else:
		# Extract real messages from board
		special_messages = str(board.nrcc_messages)

	# Format the messages (removes HTML, wraps lines, etc.)
	formatted_messages = formatSpecials(special_messages)

	# Update device state with cleaned messages
	dev.updateStateOnServer('stationMessages', value=formatted_messages.replace('+', ''))

	return formatted_messages


def _build_calling_points_string(service: Any, dev: Any, logger: Any) -> str:
	"""Extract calling points from service and format as string.

	Args:
		service: ServiceDetails object from Darwin API
		dev: Indigo device object (for the failure-throttle key and messages)
		logger: PluginLogger for error reporting

	Returns:
		Formatted calling points string (e.g., "Reading(10:15) Oxford(10:45)")
	"""
	failure_key = f"calling_points:{dev.id}"
	try:
		# Check if subsequent_calling_points exists and is not None
		calling_points_list = getattr(service, 'subsequent_calling_points', [])
		if calling_points_list is None:
			calling_points_list = []

		calling_points = [cp.location_name for cp in calling_points_list]
		arrival_times = [arrival.st for arrival in calling_points_list]
		estimated_times = [arrival.et for arrival in calling_points_list]
	except AttributeError as e:
		# Retried every refresh cycle same as darwin_fetch/darwin_login, so
		# throttle it the same way: file log gets every occurrence, Event
		# Log gets one ERROR per distinct failure (#30).
		logger.log_failure(
			failure_key,
			f"SOAP failed on Calling Points access for '{dev.name}': {e} - try again later",
			category=classify_exception(e),
		)
		return ''

	cp_string = ''
	had_failure = False
	for cp_index, cpoint in enumerate(calling_points):
		try:
			if 'On' in estimated_times[cp_index]:
				cp_string += cpoint + '(' + arrival_times[cp_index] + ') '
			else:
				cp_string += cpoint + '(' + estimated_times[cp_index] + ') '
		except (AttributeError, IndexError):
			# Expected Darwin behaviour (a calling point simply has no
			# estimated time yet), not a failure -- file log only (#30).
			logger.debug(
				f"Estimated Time for calling point returned NULL for '{dev.name}' - not critical"
			)
		except Exception as e:
			had_failure = True
			logger.log_failure(
				failure_key,
				f"Estimated Time for calling point - unknown error for '{dev.name}': {e} - advise developer",
				category=classify_exception(e),
			)

	if not had_failure:
		# No-op unless `failure_key` had an outstanding failure -- a clean
		# run stays silent exactly like before (#30).
		logger.log_recovery(failure_key, f"Calling points working again for '{dev.name}'")

	# Remove redundant "On time" text
	cp_string = cp_string.replace(TrainStatus.ON_TIME.value, '')

	return cp_string


def _update_train_device_states(
	dev: Any,
	train_num: int,
	destination: Any,
	service: Optional[Any],
	include_calling_points: bool,
	logger: Any
) -> None:
	"""Update all device states for a single train.

	Args:
		dev: Indigo device object
		train_num: Train number (1-10)
		destination: ServiceItem from station board
		service: ServiceDetails from API
		include_calling_points: Boolean for whether to include calling points
		logger: PluginLogger for error reporting
	"""
	# Build state key prefixes
	train_prefix = f'train{train_num}'

	# Extract service data with null safety
	dest_text = getattr(destination, 'destination_text', 'Unknown')
	dest_std = getattr(destination, 'std', '00:00')
	dest_etd = getattr(destination, 'etd', '00:00')
	dest_operator = getattr(destination, 'operator_name', 'Unknown')
	dest_platform = getattr(destination, 'platform', '')  # Platform number (may be None/empty)

	# Update basic states
	dev.updateStateOnServer(f'{train_prefix}Dest', value=dest_text)
	dev.updateStateOnServer(f'{train_prefix}Op', value=dest_operator)
	dev.updateStateOnServer(f'{train_prefix}Sch', value=dest_std)
	dev.updateStateOnServer(f'{train_prefix}Est', value=dest_etd)
	dev.updateStateOnServer(f'{train_prefix}Platform', value=dest_platform if dest_platform else '')

	# Calculate and update delay
	has_problem, delay_msg = delayCalc(dest_std, dest_etd)
	dev.updateStateOnServer(f'{train_prefix}Delay', value=delay_msg)
	dev.updateStateOnServer(f'{train_prefix}Issue', value=has_problem)

	# Update reason
	if TrainStatus.ON_TIME.value in delay_msg:
		dev.updateStateOnServer(f'{train_prefix}Reason', value='')
	else:
		dev.updateStateOnServer(f'{train_prefix}Reason', value='No reason provided')

	# Process calling points if requested
	if include_calling_points and service:
		calling_points_str = _build_calling_points_string(service, dev, logger)
		dev.updateStateOnServer(f'{train_prefix}Calling', value=calling_points_str)


def _process_train_services(
	dev: Any,
	session: Any,
	board: Any,
	image_content: List[str],
	include_calling_points: bool,
	logger: Any,
	word_length: int = 80
) -> bool:
	"""Process all train services from station board.

	Main loop coordinator that fetches service details, updates device states,
	and builds image content for each train.

	Args:
		dev: Indigo device object
		session: DarwinLdbSession for API calls
		board: StationBoard object
		image_content: List to append formatted train data to
		include_calling_points: Boolean for whether to include calling points
		logger: PluginLogger for error reporting
		word_length: Maximum line length for image formatting

	Returns:
		Boolean indicating if any departures were found
	"""
	# Import here to avoid circular dependency
	from image_generator import _append_train_to_image

	departures_found = False
	services = getattr(board, 'train_services', [])

	# Debug logging removed - use plugin instance logger instead

	for train_num, destination in enumerate(services[:constants.MAX_TRAINS_TRACKED], start=1):
		# Debug logging removed - use plugin instance logger instead

		# Calling points are inline on the ServiceItem (GetDepBoardWithDetails),
		# so the destination object also serves as the service for the rest
		# of the per-train processing — no second API call needed.
		service = destination
		departures_found = True

		# Update device states for this train
		_update_train_device_states(dev, train_num, destination, service, include_calling_points, logger)

		# Build image content for this train
		_append_train_to_image(image_content, destination, include_calling_points, service, dev, logger, word_length)

	return departures_found
