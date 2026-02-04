# coding=utf-8
"""
Image generation coordination for departure boards

Handles text file writing and subprocess spawning for PNG generation.
"""
from pathlib import Path
import subprocess
from typing import List, Optional, Any
import hashlib
import constants
from text_formatter import delayCalc


def errorHandler(error_msg: str):
	"""
	Placeholder error handler for image_generator module.
	Will use the actual errorHandler from plugin.py when called from plugin context.
	"""
	import sys
	print(f"ERROR: {error_msg}", file=sys.stderr)


def compute_board_content_hash(
	board_text_path: Path,
	parameters_file_path: Path
) -> str:
	"""Compute SHA-256 hash of departure board content and rendering parameters.

	Includes all inputs that affect visual output: board text, colors, font size,
	padding, and width. Any change to these parameters produces a different hash.

	Args:
		board_text_path: Path to departure board text file
		parameters_file_path: Path to trainparameters.txt with all rendering params

	Returns:
		Lowercase hex-encoded SHA-256 hash (64 characters)
	"""
	hasher = hashlib.sha256()

	# Hash departure board text content
	with open(board_text_path, 'r', encoding='utf-8') as f:
		board_content = f.read()
	hasher.update(board_content.encode('utf-8'))

	# Hash all rendering parameters from parameters file
	# File format: 'fg,bg,issue,title,calling_points,fontsize,leftpad,rightpad,width'
	# Hash the entire line since all parameters affect visual output
	with open(parameters_file_path, 'r', encoding='utf-8') as f:
		params_content = f.read().strip()
	hasher.update(params_content.encode('utf-8'))

	return hasher.hexdigest()


def _write_departure_board_text(
	text_path: Path,
	station_start: str,
	station_end: str,
	titles: str,
	statistics: str,
	messages: str,
	board_content: str
) -> None:
	"""Write formatted departure board to text file.

	Args:
		text_path: Full path to output text file (Path object)
		station_start: Starting station CRS code
		station_end: Destination station CRS code
		titles: Column titles string
		statistics: Statistics/timestamp string
		messages: Special NRCC messages (may be empty)
		board_content: Main board content with train listings
	"""
	with open(text_path, 'w') as f:
		f.write(f"{station_start} to {station_end}\n")
		f.write(titles)
		f.write(statistics)
		if messages:
			f.write(messages)
		f.write(board_content)


def _generate_single_image(
	plugin_root: Path,
	image_filename: Path,
	text_filename: Path,
	parameters_filename: Path,
	departures_available: bool,
	board_style: str,
	device,
	logger,
	plugin_prefs=None
) -> bool:
	"""Generate a single departure board image with specified style.

	Handles text2png.py exit codes:
		0 = Success
		1 = File I/O error (read/write failures)
		2 = PIL/Pillow error (font loading, image creation)
		3 = Other error (arguments, configuration)

	Args:
		plugin_root: Path to plugin root directory (Path object)
		image_filename: Path where PNG will be saved (Path object)
		text_filename: Path to input text file (Path object)
		parameters_filename: Path to parameters configuration file (Path object)
		departures_available: Boolean indicating if departures exist
		board_style: Style to generate ('classic' or 'modern')
		device: Indigo device object for state updates
		logger: Plugin logger for error reporting

	Returns:
		True if image generated successfully, False otherwise
	"""
	dep_flag = 'YES' if departures_available else 'NO'

	cmd = [
		constants.PYTHON3_PATH,
		str(plugin_root / 'text2png.py'),
		str(image_filename),
		str(text_filename),
		str(parameters_filename),
		dep_flag,
		board_style
	]

	logger.debug(f"Generating {board_style} image: {image_filename.name}")

	try:
		result = subprocess.run(
			cmd,
			capture_output=True,
			text=True,
			timeout=10,
			check=False
		)

		if result.stderr:
			logger.error(f"Image generation stderr ({board_style}): {result.stderr}")

		if result.returncode == 0:
			logger.debug(f"{board_style.capitalize()} image generated successfully for '{device.name}'")
			return True

		elif result.returncode == 1:
			error_msg = f"File I/O error in {board_style} image generation"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			return False

		elif result.returncode == 2:
			error_msg = f"PIL error in {board_style} image generation"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			return False

		elif result.returncode == 3:
			error_msg = f"Configuration error in {board_style} image generation"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			return False

		else:
			error_msg = f"Unknown error in {board_style} image generation (exit code {result.returncode})"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			return False

	except subprocess.TimeoutExpired as e:
		logger.error(f"{board_style.capitalize()} image generation timed out for device '{device.name}'")
		if e.stderr:
			logger.error(f"stderr before timeout: {e.stderr}")
		return False

	except FileNotFoundError:
		logger.error(f"Python interpreter not found: {constants.PYTHON3_PATH}")
		return False

	except Exception as e:
		logger.exception(f"Unexpected error generating {board_style} image for device '{device.name}'")
		return False


def _generate_departure_image(
	plugin_root: Path,
	image_filename: Path,
	text_filename: Path,
	parameters_filename: Path,
	departures_available: bool,
	device,
	logger,
	plugin_prefs=None
) -> bool:
	"""Generate departure board image(s) based on plugin configuration.

	Can generate classic (720×400 landscape) and/or modern (414×variable portrait)
	board styles simultaneously with different filenames.

	Args:
		plugin_root: Path to plugin root directory (Path object)
		image_filename: Base path for PNG (Path object) - suffix added for modern
		text_filename: Path to input text file (Path object)
		parameters_filename: Path to parameters configuration file (Path object)
		departures_available: Boolean indicating if departures exist
		device: Indigo device object for state updates
		logger: Plugin logger for error reporting
		plugin_prefs: Plugin preferences dictionary (self.pluginPrefs from plugin.py)

	Returns:
		True if at least one image generated successfully, False if all failed
	"""
	# Get plugin preferences (default to empty dict if not provided for backwards compatibility)
	if plugin_prefs is None:
		plugin_prefs = {}

	# Check which board styles to generate (default to classic only for backwards compatibility)
	generate_classic = plugin_prefs.get('generateClassicBoard', True)
	generate_modern = plugin_prefs.get('generateModernBoard', False)

	# Track success for each style
	classic_success = False
	modern_success = False

	# Generate classic board if enabled
	if generate_classic:
		classic_success = _generate_single_image(
			plugin_root,
			image_filename,
			text_filename,
			parameters_filename,
			departures_available,
			'classic',
			device,
			logger,
			plugin_prefs
		)

	# Generate modern board if enabled (with _mobile suffix)
	if generate_modern:
		# Add _mobile suffix before .png extension
		modern_filename = image_filename.parent / (image_filename.stem + '_mobile.png')
		modern_success = _generate_single_image(
			plugin_root,
			modern_filename,
			text_filename,
			parameters_filename,
			departures_available,
			'modern',
			device,
			logger,
			plugin_prefs
		)

	# Update device status based on results
	if classic_success or modern_success:
		# At least one succeeded
		status_msg = []
		if classic_success:
			status_msg.append('classic')
		if modern_success:
			status_msg.append('modern')

		device.updateStateOnServer('imageGenerationStatus', 'success')
		device.updateStateOnServer('imageGenerationError', '')
		logger.debug(f"Generated {' and '.join(status_msg)} image(s) for '{device.name}'")
		return True
	else:
		# Both failed (or none were enabled)
		if not generate_classic and not generate_modern:
			error_msg = "No board styles enabled"
			logger.warning(f"{error_msg} for device '{device.name}'")
		else:
			error_msg = "All enabled board styles failed to generate"
			logger.error(f"{error_msg} for device '{device.name}'")

		device.updateStateOnServer('imageGenerationStatus', 'failed')
		device.updateStateOnServer('imageGenerationError', error_msg)
		return False


def _append_train_to_image(
	image_content: List[str],
	destination: Any,
	include_calling_points: bool,
	service: Optional[Any],
	word_length: int = 80
) -> None:
	"""Add train service data to image content array.

	Args:
		image_content: List to append formatted content to
		destination: ServiceItem from station board
		include_calling_points: Boolean for whether to include calling points
		service: ServiceDetails from API (may be None)
		word_length: Maximum line length for wrapping
	"""
	# Import here to avoid circular dependency
	from device_manager import _build_calling_points_string

	# Extract destination data
	dest_text = getattr(destination, 'destination_text', 'Unknown')
	dest_std = getattr(destination, 'std', '00:00')
	dest_etd = getattr(destination, 'etd', '00:00')
	operator_code = getattr(destination, 'operator_code', 'Unknown')
	operator_name = getattr(destination, 'operator_name', 'Unknown')

	# Extract platform with logging for missing data
	try:
		dest_platform = destination.platform
	except AttributeError:
		# Destination object doesn't have platform attribute at all
		import sys
		print(f"WARNING: Destination object for '{dest_text}' missing platform attribute - Darwin API may have changed", file=sys.stderr)
		dest_platform = None

	# Calculate delay for display
	has_problem, delay_msg = delayCalc(dest_std, dest_etd)

	# Format platform for display with conditional logging
	if dest_platform is None or dest_platform == '':
		platform_text = ''
		# Log if platform missing during service hours (when platforms should be assigned)
		import sys
		import datetime
		current_hour = datetime.datetime.now().hour
		if 6 <= current_hour <= 23:  # Service hours 6am-11pm
			print(f"DEBUG: No platform assigned for {dest_text} at {dest_std}", file=sys.stderr)
	else:
		platform_text = str(dest_platform)

	# Format main service line (now includes platform)
	if len(delay_msg.strip()) == 0:
		destination_content = f"\n{dest_text},{platform_text},{dest_std},{dest_etd},{operator_code}\n"
		image_content.append(destination_content)
	else:
		destination_content = f"\n{dest_text},{platform_text},{dest_std},{dest_etd},{operator_name}"
		image_content.append(destination_content)
		delay_message = f'Status:{delay_msg}\n'
		image_content.append(delay_message)

	# Add calling points if requested
	if include_calling_points and service:
		cp_string = _build_calling_points_string(service)
		if len(cp_string) > 0:
			# Guard against invalid word_length to prevent infinite loops
			safe_word_length = max(20, word_length)  # Minimum 20 chars for safety

			# Split long calling points into multiple lines at station boundaries
			if len(cp_string) <= safe_word_length:
				# No need to split - add as single line
				image_content.append('>>> ' + cp_string.strip())
			else:
				# Split at station boundaries (after closing paren + space)
				remaining = cp_string.strip()
				while len(remaining) > 0:
					if len(remaining) <= safe_word_length:
						# Remaining text fits on one line
						image_content.append('>>> ' + remaining)
						break

					# Find last complete station entry that fits
					cut_point = -1
					for i in range(safe_word_length - 1, 0, -1):
						if remaining[i] == ')' and i + 1 < len(remaining) and remaining[i + 1] == ' ':
							cut_point = i + 1
							break

					if cut_point > 0:
						# Found a good split point
						image_content.append('>>> ' + remaining[:cut_point].strip())
						remaining = remaining[cut_point:].lstrip()
					else:
						# No good split point found, take what we can
						image_content.append('>>> ' + remaining[:safe_word_length].strip())
						remaining = remaining[safe_word_length:].lstrip()


def _format_station_board(
	image_content: List[str],
	departures_found: bool,
	via_station: str,
	board: Any,
	base_via: str,
	max_lines: int = 30
) -> str:
	"""Format image content array into final departure board display.

	Args:
		image_content: List of strings containing board data
		departures_found: Boolean indicating if any departures exist
		via_station: Display string for destination filter (e.g., "(via: London)")
		board: StationBoard object for station name
		base_via: Base destination name without formatting
		max_lines: Maximum number of lines to include in board

	Returns:
		Formatted station board string
	"""
	if not departures_found:
		# No trains found - generate appropriate message
		if len(via_station) != 0:
			return ("** No departures found from " + board.location_name + " direct to " + base_via +
			        " today **\n** Check Operators website for more information on current schedule and issues **")
		else:
			return ("** No departures found from " + board.location_name +
			        " today **\n** Check Operators website for more information on current schedule and issues **")

	# Format the departure board from image content
	station_board = ''
	tot_lines = 0

	for line_index in range(len(image_content)):
		current_line = image_content[line_index]

		if 'Status' in current_line:
			# Status/delay line - keep as is
			board_line = current_line

		elif '>>>' not in current_line:
			# Regular destination line - parse and format columns
			parts = current_line.split(',')
			if len(parts) >= 5:
				# New format with platform: Destination,Platform,Time,Status,Operator
				destination = parts[0] + '-' * 50
				platform = parts[1] + '-' * 10  # Platform field
				schedule = parts[2] + '-' * 10
				estimated = parts[3] + '-' * 10
				operator = parts[4]
				board_line = destination[:25] + platform[:5] + ' ' + schedule[:10] + estimated[:10] + operator
			elif len(parts) >= 4:
				# Legacy format without platform (backwards compatibility)
				destination = parts[0] + '-' * 50
				schedule = parts[1] + '-' * 10
				estimated = parts[2] + '-' * 10
				operator = parts[3]
				board_line = destination[:35] + ' ' + schedule[:10] + estimated[:10] + operator
			else:
				# Malformed line, keep as is
				board_line = current_line

		else:
			# Calling points line (contains '>>>')
			board_line = current_line

		station_board = station_board + board_line + '\n'

		# Check line limit
		tot_lines += 1
		if tot_lines > max_lines:
			break

	return station_board
