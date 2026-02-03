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

	Includes all inputs that affect visual output: board text and color scheme.
	Any change to either component produces a different hash.

	Args:
		board_text_path: Path to departure board text file
		parameters_file_path: Path to trainparameters.txt containing color config

	Returns:
		Lowercase hex-encoded SHA-256 hash (64 characters)
	"""
	hasher = hashlib.sha256()

	# Hash departure board text content
	with open(board_text_path, 'r', encoding='utf-8') as f:
		board_content = f.read()
	hasher.update(board_content.encode('utf-8'))

	# Hash color parameters from parameters file
	# File format: 'fg,bg,issue,title,calling_points,9,3,3,720'
	# We hash the first 5 comma-separated values (the colors)
	with open(parameters_file_path, 'r', encoding='utf-8') as f:
		params_content = f.read().strip()
	color_values = ','.join(params_content.split(',')[:5])
	hasher.update(color_values.encode('utf-8'))

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


def _generate_departure_image(
	plugin_root: Path,
	image_filename: Path,
	text_filename: Path,
	parameters_filename: Path,
	departures_available: bool,
	device,
	logger
) -> bool:
	"""Launch subprocess to generate PNG image from text file.

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
		dep_flag
	]

	# Log command for debugging (can be removed after confirming stable)
	logger.debug(f"Generating image: {image_filename.name}")

	try:
		result = subprocess.run(
			cmd,
			capture_output=True,  # Capture both stdout and stderr
			text=True,            # Decode as strings
			timeout=10,           # 10-second timeout for image generation
			check=False           # Handle exit codes manually
		)

		# Log subprocess errors only
		if result.stderr:
			logger.error(f"Image generation stderr: {result.stderr}")

		# Handle exit codes
		if result.returncode == 0:
			# Success
			logger.debug(f"Image generated successfully for '{device.name}'")
			device.updateStateOnServer('imageGenerationStatus', 'success')
			device.updateStateOnServer('imageGenerationError', '')
			return True

		elif result.returncode == 1:
			# File I/O error
			error_msg = "File I/O error: cannot read input files or write PNG"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			device.updateStateOnServer('imageGenerationStatus', 'failed')
			device.updateStateOnServer('imageGenerationError', error_msg)
			return False

		elif result.returncode == 2:
			# PIL/Pillow error
			error_msg = "PIL error: font loading or image creation failed"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			device.updateStateOnServer('imageGenerationStatus', 'failed')
			device.updateStateOnServer('imageGenerationError', error_msg)
			return False

		elif result.returncode == 3:
			# Other error (arguments, configuration)
			error_msg = "Configuration error in image generation"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			device.updateStateOnServer('imageGenerationStatus', 'failed')
			device.updateStateOnServer('imageGenerationError', error_msg)
			return False

		else:
			# Unknown exit code
			error_msg = f"Unknown error (exit code {result.returncode})"
			logger.error(f"{error_msg} for device '{device.name}'")
			if result.stderr:
				logger.error(f"Details: {result.stderr}")
			device.updateStateOnServer('imageGenerationStatus', 'failed')
			device.updateStateOnServer('imageGenerationError', error_msg)
			return False

	except subprocess.TimeoutExpired as e:
		error_msg = "Timeout after 10 seconds"
		logger.error(f"Image generation timed out for device '{device.name}'")
		if e.stderr:
			logger.error(f"stderr before timeout: {e.stderr}")
		device.updateStateOnServer('imageGenerationStatus', 'timeout')
		device.updateStateOnServer('imageGenerationError', error_msg)
		return False

	except FileNotFoundError:
		error_msg = f"Python interpreter not found: {constants.PYTHON3_PATH}"
		logger.error(error_msg)
		device.updateStateOnServer('imageGenerationStatus', 'config_error')
		device.updateStateOnServer('imageGenerationError', error_msg)
		return False

	except Exception as e:
		error_msg = f"Unexpected error: {str(e)}"
		logger.exception(f"Unexpected error generating image for device '{device.name}'")
		device.updateStateOnServer('imageGenerationStatus', 'error')
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

	# Calculate delay for display
	has_problem, delay_msg = delayCalc(dest_std, dest_etd)

	# Format main service line
	if len(delay_msg.strip()) == 0:
		destination_content = f"\n{dest_text},{dest_std},{dest_etd},{operator_code}\n"
		image_content.append(destination_content)
	else:
		destination_content = f"\n{dest_text},{dest_std},{dest_etd},{operator_name}"
		image_content.append(destination_content)
		delay_message = f'Status:{delay_msg}\n'
		image_content.append(delay_message)

	# Add calling points if requested
	if include_calling_points and service:
		cp_string = _build_calling_points_string(service)
		if len(cp_string) > 0:
			# Split long calling points into multiple lines
			if len(cp_string) <= word_length:
				# No need to split
				image_content.append('>>> ' + cp_string)
			else:
				# Split at word boundaries
				remaining = cp_string
				while len(remaining) > word_length:
					cut_point = remaining.find(')', word_length - 1)
					if cut_point != -1:
						image_content.append('>>> ' + remaining[:cut_point + 1])
						remaining = remaining[cut_point + 1:].lstrip()
					else:
						# No closing paren found, just break
						break

				# Add remaining text
				if len(remaining.strip()) != 0:
					image_content.append('>>> ' + remaining)


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
			if len(parts) >= 4:
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
