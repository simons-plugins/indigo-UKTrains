# coding=utf-8
"""
Image generation coordination for departure boards

Handles text file writing and subprocess spawning for PNG generation.
"""
from pathlib import Path
import subprocess
from typing import List, Optional, Any
import constants
from text_formatter import delayCalc


def errorHandler(error_msg: str):
	"""
	Placeholder error handler for image_generator module.
	Will use the actual errorHandler from plugin.py when called from plugin context.
	"""
	import sys
	print(f"ERROR: {error_msg}", file=sys.stderr)


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
	departures_available: bool
) -> subprocess.CompletedProcess:
	"""Launch subprocess to generate PNG image from text file.

	Args:
		plugin_root: Path to plugin root directory (Path object)
		image_filename: Path where PNG will be saved (Path object)
		text_filename: Path to input text file (Path object)
		parameters_filename: Path to parameters configuration file (Path object)
		departures_available: Boolean indicating if departures exist

	Returns:
		subprocess.CompletedProcess result
	"""
	dep_flag = 'YES' if departures_available else 'NO'

	# Use Path objects for subprocess files
	output_log = plugin_root / constants.IMAGE_OUTPUT_LOG
	error_log = plugin_root / constants.IMAGE_ERROR_LOG

	with open(output_log, 'w') as output_file, \
	     open(error_log, 'w') as error_file:
		result = subprocess.run(
			[constants.PYTHON3_PATH,
			 str(plugin_root / 'text2png.py'),
			 str(image_filename),
			 str(text_filename),
			 str(parameters_filename),
			 dep_flag],
			stdout=output_file,
			stderr=error_file
		)
	return result


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
