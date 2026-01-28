# coding=utf-8

###############################################################################################
# Plugin looks at the National rail database for a selected route and identifies the current
# schedule, issues (e.g. delays and disruption) for a designated route.  This information can
# be stored as an Indigo device.
#
# It also sets an alarm if there are any issues with trains on that route
#
# Functions are:
#   Downloads the latest live departure and arrival times for the next 60 mins
#   Calculates and displays any delays and sets a TrainDelays flag in indigo for triggering
#   Stores current values as indigo variables for display on control pages
#
# This plugin will be expanded to include other forms of transport in the coming months
#
# Credits:  1. 	National Rail/Darwin for real-time API (please read their T&C)
#			2. 	http://www.1001fonts.com/ - free royalty fonts used in the departure board display
#			3. 	Robert Clake for his excellent nredarwin github mobule that made reading SOAP responses
#				a lot simpler
#			4.	Matt and Jay for helping me sort out the complexities of subprocess shells and shared
#				libraries
#
# 			And all the ALPHA testers who helped get it running!
#
#  Version 0.3.01
#  Release: BETA Only
###############################################################################################

# Get system modules
import os, sys, time, datetime,traceback
import subprocess
from subprocess import call


try:
	import indigo
except ImportError as e:
	print(f"This programme must be run from inside indigo pro 6: {e}")
	sys.exit(0)
import logging
import constants

try:
	import pytz
except ImportError:
	pass

# Get the current python path for text files
# Set up globals
global nationalDebug,  stationDict
stationDict = {}
#todo delete below record
errorFile = '/Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/NationRailErrors.log'

global pypath
global failPYTZ
failPYTZ = True
nationalDebug = False # Logging enabled for testing purposes only

# Get the current python path for text files
pypath = os.path.realpath(sys.path[0])

# Now update the system path if necessary
sys.path.append(pypath)
pypath = pypath + '/'
#pypath = pypath2.replace(' ', '\ ')


# Create error log process for solution

def errorHandler(myError):
	global nationalDebug,  pypath

	if nationalDebug:
		with open(errorFile, 'a') as f:
			f.write('-' * 80 + '\n')
			f.write('Exception Logged:' + str(time.strftime(time.asctime())) + ' in ' + myError + ' module' + '\n\n')
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=f)


# Get darwin access modules and other standard dependencies in place
try:
	import nredarwin
	if nationalDebug:
		indigo.server.log('* Darwin present *', level=logging.INFO)
except ImportError as e:
	indigo.server.log(f"** Couldn't find nredarwin module: {e} - contact developer or check forums for support **", level=logging.CRITICAL)
	sys.exit(3)

try:
	import suds
	if nationalDebug:
		indigo.server.log('* Suds present *', level=logging.INFO)
except ImportError as e:
	indigo.server.log(f"** Couldn't find suds module: {e} - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(4)

try:
	import functools
	if nationalDebug:
		indigo.server.log('* Functools present *', level=logging.INFO)
except ImportError as e:
	indigo.server.log(f"** Couldn't find functools module: {e} - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(5)

try:
	import os, logging
	if nationalDebug:
		indigo.server.log('* Logging and OS present *', level=logging.INFO)
except ImportError as e:
	indigo.server.log(f"** Couldn't find standard os or logging modules: {e} - contact the developer for support **", level=logging.CRITICAL)
	sys.exit(6)

try:
	from nredarwin.webservice import DarwinLdbSession
	if nationalDebug:
		indigo.server.log('* Darwin LDBS session ready *', level=logging.INFO)
except ImportError as e:
	indigo.server.log(f"** Error accessing nredarwin webservice: {e} - contact developer for support **", level=logging.CRITICAL)
	sys.exit(7)

# Import timezone checker
try:
	import pytz
	failPYTZ = False
except ImportError as e:
	indigo.server.log(f'WARNING - pytz not present ({e}), times will be in GMT only' , level=logging.INFO)
	failPYTZ = True
	pass

def getUKTime():
	### Checks time generated to allow for BST
	### Note - all times are UK Time
	### Get the current time in London as a basis
	global failPYTZ

	if failPYTZ:
		# Module isn't installed so we will return GMT time
		gmtTime = time.gmtime()
		return time.strftime('%a %H:%M:%S', gmtTime)+' GMT'
	else:
		timeZone = pytz.timezone('Europe/London')
		lonTime = datetime.datetime.now(timeZone)
		return lonTime.strftime('%a %H:%M:%S')+' UK Time'

def delayCalc(estTime, arrivalTime):

	global nationalDebug, pypath

	# Calculates time different between two times of the form HH:MM or handles On Time, Cancelled or Delayed message
	delayMessage = ''
	trainProblem = False

	# Check if times are valid HH:MM format or special status strings
	if not arrivalTime or not estTime or arrivalTime[0] not in '012' or estTime[0] not in '012':
		# Handle null/None values safely
		if arrivalTime and arrivalTime.find('On') != -1 or estTime and estTime.find('On') != -1:
			delayMessage = 'On time'
			trainProblem = False
		elif arrivalTime and arrivalTime.upper().find('CAN') != -1 or estTime and estTime.upper().find('CAN') != -1:
			delayMessage = 'Cancelled'
			trainProblem = True
		else:
			delayMessage = 'Delayed'
			trainProblem = True
	else:
		# It's a time so calculate the delay
		# Convert both to seconds
		ha, ma = [int(i) for i in arrivalTime.split(':')]
		timeValArrival = ha * 60 + ma
		he, me = [int(i) for i in estTime.split(':')]
		timeValEst = he * 60 + me

		# Check difference
		if timeValEst - timeValArrival < 0:
			# Delayed (mins)
			minsDelay = int(timeValEst - timeValArrival)  # Round up
			if abs(minsDelay) == 1:
				delayMessage = str(abs(minsDelay)) + ' min late'
				trainProblem = True
			else:
				delayMessage = str(abs(minsDelay)) + ' mins late'
				trainProblem = True

		elif timeValEst - timeValArrival > 0:
			# Early (mins)
			minsDelay = int(timeValEst - timeValArrival)  # Round up
			if abs(minsDelay) == 1:
				delayMessage = str(abs(minsDelay)) + ' min early'
				trainProblem = True
			else:
				delayMessage = str(abs(minsDelay)) + ' mins early'
				trainProblem = True
		else:
			delayMessage = 'On Time'
			trainProblem = False

	return trainProblem, delayMessage

def formatSpecials(longMessage):
	# Formats long messages into a readable format.  Maximum will be two lines in small font

	# Is the message blank?
	if len(longMessage.strip()) == 0:
		# Just return the message untouched
		return longMessage

	# Maximum line length
	maxLength = 130
	maxLines = 2

	# Remove the non breaking spaces
	nonBreakingSpace = u'&nbsp'
	longMessage = longMessage.replace(nonBreakingSpace,' ')
	longMessage = longMessage.replace('\n','')

	# Look at a more generic way to do this
	longMessage = longMessage.replace('<P>','')
	longMessage = longMessage.replace('</P>','')
	longMessage = longMessage.replace('<A>','')
	longMessage = longMessage.replace('</A>','')
	longMessage = longMessage.replace('href=','')
	longMessage = longMessage.replace('http','')
	longMessage = longMessage.replace('://','www.')
	longMessage = longMessage.replace('"','')
	longMessage = longMessage.replace('Travel News.','')
	longMessage = longMessage.replace('Latest','')
	longMessage = longMessage.replace('<A ','')
	longMessage = longMessage.replace('>','')

	# Now remove the []s
	longMessage = longMessage.replace('[','')
	longMessage = longMessage.replace(']','')

	# Ok now break up the message if required
	returnMessage = ''
	remaining = True
	remainingMessage = longMessage
	totalLines = 0

	while remaining:
		totalLines += 1

		if len(remainingMessage.strip())>maxLength:
			# Need to split the messsage more
			# Find the next space following the maxLength
			nextPartStart = remainingMessage.find(' ',maxLength)
			returnMessage += '+++'+remainingMessage[:nextPartStart] + '\n'

			if nextPartStart != -1:
				# More to process
				remainingMessage = remainingMessage[nextPartStart+1:]
			else:
				remainingMessage = ''
				remaining = False

			if totalLines == maxLines:
				# That's all we have room for
				remaining = False
				break

		else:
			returnMessage += '+++'+remainingMessage+'\n'

			# Forget the rest of the message
			remaining = False

	# Return the multi-line string
	if nationalDebug:
		indigo.server.log('Return message = '+returnMessage)
	return returnMessage


# ========== Phase 3 Refactoring: Extracted Helper Functions ==========

def _clear_device_states(dev):
	"""
	Clear all train states on device before update.

	Args:
		dev: Indigo device object to clear
	"""
	# Clear all train data (up to MAX_TRAINS_TRACKED)
	for trainNum in range(1, constants.MAX_TRAINS_TRACKED + 1):
		train_prefix = f'train{trainNum}'
		dev.updateStateOnServer(f'{train_prefix}Dest', value='')
		dev.updateStateOnServer(f'{train_prefix}Sch', value='')
		dev.updateStateOnServer(f'{train_prefix}Est', value='')
		dev.updateStateOnServer(f'{train_prefix}Delay', value='')
		dev.updateStateOnServer(f'{train_prefix}Issue', value=False)
		dev.updateStateOnServer(f'{train_prefix}Reason', value='')
		dev.updateStateOnServer(f'{train_prefix}Calling', value='')

	# Clear station issues flag
	dev.updateStateOnServer('stationIssues', value=False)


def _update_station_issues_flag(dev):
	"""
	Check if any train has issues and update station-level flag.

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


def _write_departure_board_text(text_path, station_start, station_end,
                                 titles, statistics, messages, board_content):
	"""
	Write formatted departure board to text file.

	Args:
		text_path: Full path to output text file
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


def _generate_departure_image(plugin_path, image_filename, text_filename,
                               parameters_filename, departures_available):
	"""
	Launch subprocess to generate PNG image from text file.

	Args:
		plugin_path: Path to plugin directory
		image_filename: Path where PNG will be saved
		text_filename: Path to input text file
		parameters_filename: Path to parameters configuration file
		departures_available: Boolean indicating if departures exist

	Returns:
		subprocess.CompletedProcess result
	"""
	dep_flag = 'YES' if departures_available else 'NO'

	with open(f'{plugin_path}{constants.IMAGE_OUTPUT_LOG}', 'w') as output_file, \
	     open(f'{plugin_path}{constants.IMAGE_ERROR_LOG}', 'w') as error_file:
		result = subprocess.run(
			[constants.PYTHON3_PATH,
			 f'{plugin_path}text2png.py',
			 image_filename,
			 text_filename,
			 parameters_filename,
			 dep_flag],
			stdout=output_file,
			stderr=error_file
		)
	return result


# ========== End of Phase 3 Helper Functions ==========


def _fetch_station_board(session, start_crs, end_crs=None, row_limit=100):
	"""
	Fetch station board with optional destination filter.

	Args:
		session: DarwinLdbSession object for API access
		start_crs: Starting station CRS code
		end_crs: Optional destination CRS code (None or 'ALL' for all destinations)
		row_limit: Maximum number of services to request

	Returns:
		StationBoard object from Darwin API

	Raises:
		suds.WebFault: If SOAP request fails
		Exception: For other API errors
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


def _process_special_messages(board, dev, testing_mode=False):
	"""
	Extract and format NRCC special messages from station board.

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


def _fetch_service_details(session, service_id):
	"""
	Fetch detailed service information from Darwin API.

	Args:
		session: DarwinLdbSession object for API access
		service_id: Unique service identifier

	Returns:
		ServiceDetails object or None if fetch failed
	"""
	try:
		service = session.get_service_details(service_id)
		return service
	except (suds.WebFault, Exception) as e:
		errorHandler(f'WARNING ** SOAP resolution failed: {e} - will retry later when server less busy **')
		return None


def _build_calling_points_string(service):
	"""
	Extract calling points from service and format as string.

	Args:
		service: ServiceDetails object from Darwin API

	Returns:
		Formatted calling points string (e.g., "Reading(10:15) Oxford(10:45)")
	"""
	try:
		# Check if subsequent_calling_points exists and is not None
		calling_points_list = getattr(service, 'subsequent_calling_points', [])
		if calling_points_list is None:
			calling_points_list = []

		calling_points = [cp.location_name for cp in calling_points_list]
		arrival_times = [arrival.st for arrival in calling_points_list]
		estimated_times = [arrival.et for arrival in calling_points_list]
	except AttributeError as e:
		errorHandler(f'WARNING ** SOAP failed on Calling Points access: {e} - try again later **')
		return ''

	cp_string = ''
	for cp_index, cpoint in enumerate(calling_points):
		try:
			if 'On' in estimated_times[cp_index]:
				cp_string += cpoint + '(' + arrival_times[cp_index] + ') '
			else:
				cp_string += cpoint + '(' + estimated_times[cp_index] + ') '
		except (AttributeError, IndexError):
			errorHandler('WARNING - Estimated Time for calling point returned NULL - not critical')
		except Exception as e:
			errorHandler(f'WARNING - Estimated Time for calling point - unknown error: {e} - advise developer')

	# Remove redundant "On time" text
	cp_string = cp_string.replace('On time', '')

	return cp_string


def _update_train_device_states(dev, train_num, destination, service, include_calling_points):
	"""
	Update all device states for a single train.

	Args:
		dev: Indigo device object
		train_num: Train number (1-10)
		destination: ServiceItem from station board
		service: ServiceDetails from API
		include_calling_points: Boolean for whether to include calling points
	"""
	# Build state key prefixes
	train_prefix = f'train{train_num}'

	# Extract service data with null safety
	dest_text = getattr(destination, 'destination_text', 'Unknown')
	dest_std = getattr(destination, 'std', '00:00')
	dest_etd = getattr(destination, 'etd', '00:00')
	dest_operator = getattr(destination, 'operator_name', 'Unknown')

	# Update basic states
	dev.updateStateOnServer(f'{train_prefix}Dest', value=dest_text)
	dev.updateStateOnServer(f'{train_prefix}Op', value=dest_operator)
	dev.updateStateOnServer(f'{train_prefix}Sch', value=dest_std)
	dev.updateStateOnServer(f'{train_prefix}Est', value=dest_etd)

	# Calculate and update delay
	has_problem, delay_msg = delayCalc(dest_std, dest_etd)
	dev.updateStateOnServer(f'{train_prefix}Delay', value=delay_msg)
	dev.updateStateOnServer(f'{train_prefix}Issue', value=has_problem)

	# Update reason
	if 'On Time' in delay_msg:
		dev.updateStateOnServer(f'{train_prefix}Reason', value='')
	else:
		dev.updateStateOnServer(f'{train_prefix}Reason', value='No reason provided')

	# Process calling points if requested
	if include_calling_points and service:
		calling_points_str = _build_calling_points_string(service)
		dev.updateStateOnServer(f'{train_prefix}Calling', value=calling_points_str)


def _append_train_to_image(image_content, destination, include_calling_points, service, word_length=80):
	"""
	Add train service data to image content array.

	Args:
		image_content: List to append formatted content to
		destination: ServiceItem from station board
		include_calling_points: Boolean for whether to include calling points
		service: ServiceDetails from API (may be None)
		word_length: Maximum line length for wrapping
	"""
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


def _process_train_services(dev, session, board, image_content, include_calling_points, word_length=80):
	"""
	Process all train services from station board.

	Main loop coordinator that fetches service details, updates device states,
	and builds image content for each train.

	Args:
		dev: Indigo device object
		session: DarwinLdbSession for API calls
		board: StationBoard object
		image_content: List to append formatted train data to
		include_calling_points: Boolean for whether to include calling points
		word_length: Maximum line length for image formatting

	Returns:
		Boolean indicating if any departures were found
	"""
	global nationalDebug

	departures_found = False
	services = getattr(board, 'train_services', [])

	if nationalDebug:
		indigo.server.log(f'Processing {len(services)} train services', level=logging.DEBUG)

	for train_num, destination in enumerate(services[:constants.MAX_TRAINS_TRACKED], start=1):
		if nationalDebug:
			indigo.server.log(f'Processing train {train_num}: {destination}', level=logging.DEBUG)

		departures_found = True

		# Fetch full service details from Darwin API
		service = _fetch_service_details(session, destination.service_id)
		if service is None:
			# API call failed, skip this service but continue with others
			continue

		# Update device states for this train
		_update_train_device_states(dev, train_num, destination, service, include_calling_points)

		# Build image content for this train
		_append_train_to_image(image_content, destination, include_calling_points, service, word_length)

	return departures_found


def _format_station_board(image_content, departures_found, via_station, board, base_via, max_lines=30):
	"""
	Format image content array into final departure board display.

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

		if current_line.find('Status') != -1:
			# Status/delay line - keep as is
			board_line = current_line

		elif current_line.find('>>>') == -1:
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


def routeUpdate(dev, apiAccess, networkrailURL, imagePath, parametersFileName):

	global nationalDebug, pypath
	indigo.debugger()
	if not dev.enabled and dev.configured:
		# Device is currently disabled or new so ignore and move on
		return False

	# Login to Darwin
	accessLogin = nationalRailLogin(networkrailURL, apiAccess)
	if not accessLogin[0]:
		# Login failed so ignore and return
		return False

	darwinSession = accessLogin[1]

	# Clear all previous train data on device
	_clear_device_states(dev)

	# Ok - now let's get the real data and store it

	# The CRS information will be held against the ROUTE device
	stationStartCrs = dev.states['stationCRS'] # Codes are found on the National Rail data site and will be provided as a drop list for users
	stationEndCrs = dev.states['destinationCRS']

	# Fetch station board with optional destination filter
	try:
		stationBoardDetails = _fetch_station_board(darwinSession, stationStartCrs, stationEndCrs)
	except (suds.WebFault, Exception) as e:
		errorHandler(f'WARNING ** SOAP resolution failed: {e} - will retry later when server less busy **')
		return False

	# Update station metadata on device
	station_name = getattr(stationBoardDetails, 'location_name', 'Unknown Station')
	time_generated = getUKTime()
	dev.updateStateOnServer('stationLong', value=station_name)
	dev.updateStateOnServer('timeGenerated', value=time_generated)

	# Calculate destination display strings
	base_via = dev.states.get('destinationLong', '')
	via_station = f'(via:{base_via})' if stationEndCrs != 'ALL' else ''

	if nationalDebug:
		indigo.server.log(f'Departures Board: {station_name} {via_station}', level=logging.DEBUG)

	# Initialize image content array
	image_content = ['Destination,Sch,Est,By']
	image_filename = f'{imagePath}/{stationStartCrs}{stationEndCrs}timetable.png'

	# Process all train services
	include_calling_points = dev.pluginProps.get('includeCalling', False)
	departures_found = _process_train_services(
		dev,
		darwinSession,
		stationBoardDetails,
		image_content,
		include_calling_points,
		word_length=80
	)

	# Update station-level issues flag
	_update_station_issues_flag(dev)

	# Process special messages and format board
	special_messages = _process_special_messages(stationBoardDetails, dev, testing_mode=False)
	board_titles = f"Departures - {station_name} {via_station}{' ' * 60}"[:60] + '\n'
	board_stats = f'Generated on:{time_generated}\n'
	station_board = _format_station_board(
		image_content,
		departures_found,
		via_station,
		stationBoardDetails,
		base_via,
		max_lines=30
	)

	# Write departure board text file
	train_text_file = f'{imagePath}/{stationStartCrs}{stationEndCrs}departureBoard.txt'
	_write_departure_board_text(
		train_text_file,
		station_start=stationStartCrs,
		station_end=stationEndCrs,
		titles=board_titles,
		statistics=board_stats,
		messages=special_messages + '\n',
		board_content=station_board
	)

	# Generate PNG image from text file
	indigo.debugger()
	_generate_departure_image(
		pypath,
		image_filename,
		train_text_file,
		parametersFileName,
		departures_available=departures_found
	)

	return True

def nationalRailLogin(wsdl = 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',api_key='NO KEY'):
	# Module forces a login to the National Rail darwin service.  An API key is needed and the plugin will
	# fail if it's not provided

	global nationalDebug, pypath

	if wsdl.find('realtime.nationalrail') == -1:
		# Darwin address is invalid
		# print error message and return
		if nationalDebug:
			indigo.server.log('Darwin address is invalid - please read forum for update or contact developer')

		errorHandler('CRITICAL FAILURE ** Darwin is invalid - please check or advise developer - '+wsdl+' **')

		return False, None

	# We have a site and a key now try to use it:
	try:
		darwin_sesh = DarwinLdbSession(wsdl, api_key)
		# Login successful
		if nationalDebug:
			indigo.server.log('Login successful - now processing routes...')

		return True, darwin_sesh

	except Exception as e:
		# Login failed. As the user to check details and try again
		if nationalDebug:
			indigo.server.log(f'Login failed: {e} - a) API key invalid, b) Darwin Offline or c) No Internet Access - Please check and reload plugin')

		errorHandler(f'WARNING ** Failed to log in to Darwin: {e} - check API key and internet connection')

		return False, None

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):

		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.validatePrefsConfigUi(pluginPrefs)
		global nationalDebug, stationDict, pypath
		self.pluginid = pluginId
		# Set up version checker
		travelVersionFile = 'https://www.dropbox.com/s/62kahe2nh848b65/iTravelVersionInfo.html?dl=1'

		if nationalDebug:
			indigo.server.log('Initiating Plugin Class...', level=logging.DEBUG)

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def validateDeviceConfigUi(self, devProps, typeId, devId):
		global nationalDebug, stationDict, pypath

		# Create station dictionary for lookup
		currentStationDict = self.createStationDict()

		# Create error dictionary
		errorDict = indigo.Dict()

		if 'trainRoute' in devProps:
			if len(devProps['trainRoute']) == 0:
				devProps['trainRoute']='Please enter valid name before continuing'
				errorDict = indigo.Dict()
				errorDict["trainRoute"] = "Enter a valid route name"
				errorDict["showAlertText"] = "You must enter a unique route name"
				return (False, devProps, errorDict)
		else:
			devProps['trainRoute'] = 'Unnamed Route:'+devId

		if 'stationName' in devProps:
			if len(devProps['stationName']) == 0 or devProps['stationName']=='All Destinations':
				devProps['stationCode']=''
				errorDict = indigo.Dict()
				errorDict["stationName"] = "Select a valid starting station"
				errorDict["showAlertText"] = "You must enter a unique start station name (not ALL or Blank)"
				return (False, devProps, errorDict)
			
			elif devProps['stationName'] in currentStationDict:

				# Name exists so get the code
				stationCRS = self.returnNetworkRailCode(devProps['stationName'], currentStationDict)
				devProps['stationCode'] = stationCRS

			else:
				devProps['stationName']='All Destinations'
				errorDict = indigo.Dict()
				errorDict["stationCode"] = "Select a valid starting station"
				errorDict["showAlertText"] = "You must select a unique start station name not All destinations"
				return (False, devProps, errorDict)

		else:
			devProps['stationCode'] = "WAT"
			devProps['stationName'] = 'London Waterloo'

		if 'destinationName' in devProps:
			if len(devProps['destinationName']) == 0 or devProps['destinationName']=='All Destinations':
				devProps['destinationName'] = 'All Destinations'
				devProps['destinationCode'] = 'ALL'
			
			elif devProps['destinationName'] in currentStationDict:
				# Code exists so update other information
				destStationCRS = self.returnNetworkRailCode(devProps['destinationName'], currentStationDict)
				devProps['destinationCode'] = destStationCRS

			else:
				devProps['destinationCode']='ZZZ'
				errorDict = indigo.Dict()
				errorDict["destinationName"] = "Select a valid destination station or leave blank"
				errorDict["showAlertText"] = "You must enter a unique destination station name or select ALL"
				return (False, devProps, errorDict)
		else:
			devProps['destinationCode'] = "ALL"
			devProps['destinationName'] = 'All destinations'

		# Finally update the states
		return True, devProps, errorDict

	def validatePrefsConfigUi(self, devProps):
		global nationalDebug, stationDict

		if nationalDebug:
			indigo.server.log('Validating Config file...')

		errorDict = indigo.Dict()
		if 'darwinAPI' in devProps:
			if len(devProps['darwinAPI']) == 0:
				devProps['darwinAPI']='Please enter valid name before continuing'
				errorDict = indigo.Dict()
				errorDict["darwinAPI"] = "Enter a valid API Key"
				errorDict["showAlertText"] ='You must enter a valid API key - see forum for details on obtaining a free key'
				return (False, devProps, errorDict)
		else:
			devProps['darwinAPI']='Please enter valid API before continuing'
			errorDict = indigo.Dict()
			errorDict["darwinAPI"] = "Invalid API Key"
			errorDict["showAlertText"] ='You must enter a valid API key - see forum for details on obtaining a free key'
			return (False, devProps, errorDict)

		if 'darwinSite' in devProps:
			if len(devProps['darwinSite']) == 0:
				devProps['darwinSite']='Please enter valid network site URL'
				errorDict = indigo.Dict()
				errorDict["darwinSite"] = "Invalid Darwin Network Rail URL"
				errorDict["showAlertText"] ='You must enter a valid Network Rail Darwin Site  - see forum for details on obtaining a free key'
				return (False, devProps, errorDict)
		else:
			devProps['darwinSite']='https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'

		if 'createMaps' in devProps:
			if devProps['createMaps']:
				# Check image file name
				if len(devProps['imageFilename']) == 0:
					errorDict = indigo.Dict()
					errorDict["stationCode"] = "No file path found for images"
					errorDict["showAlertText"] = "You must enter a path for your image (e.g. /Users/myIndigo) - no trailing '/'"
					return (False, devProps, errorDict)


				try:
					if nationalDebug:
						indigo.server.log('Trying to create file '+devProps['imageFilename']+'/filecheck.txt')

					f=open(devProps['imageFilename']+'/filecheck.txt','w')
					f.close()
				except (IOError, OSError) as e:
					# Can't open file in location report error to user
					errorDict = indigo.Dict()
					errorDict["imageFilename"] = "Invalid path for image files"
					errorDict["showAlertText"] = "You must enter a valid path for your image (e.g. /Users/myIndigo) - no trailing '/'"
					return (False, devProps, errorDict)

			else:
				# No maps
				devProps['imageFilename'] = 'No images being saved'
		else:
			devProps['createMaps'] = False

		if 'forcolour' in devProps:
			if devProps['forcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["forcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #0F0 default = Green)"
				return (False, devProps, errorDict)

		if 'bgcolour' in devProps:
			if devProps['bgcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["bgcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = Black)"
				return (False, devProps, errorDict)

		if 'isscolour' in devProps:
			if devProps['isscolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["isscolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #F00 default = Red)"
				return (False, devProps, errorDict)

		if 'cpcolour' in devProps:
			if devProps['cpcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["cpcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = White)"
				return (False, devProps, errorDict)

		if 'ticolour' in devProps:
			if devProps['ticolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["ticolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #0FF default = Cyan)"
				return (False, devProps, errorDict)

		return (True, devProps)

	########################################
	# Internal utility methods. Some of these are useful to provide
	# a higher-level abstraction for accessing/changing route
	# properties or states.
	######################

	# Now define the key functions used to manage Route Device
	######################
	# Poll all of the states from the devices and pass new values to
	# Indigo Server.
	def _refreshStatesFromHardware(self, dev):
		# Send status updates to the indigo log
		if nationalDebug:
			indigo.server.log(u"RGB States check called")

	########################################
	def deviceStartComm(self, dev):
		dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used
		if dev.pluginProps['routeActive']:
			dev.updateStateOnServer('deviceActive', True)
		else:
			dev.updateStateOnServer('deviceActive', False)

	def deviceStopComm(self, dev):
		return

	def deviceDeleted(self, dev):
		# Special routines for deleted devices
		pass

	########################################
	# Sensor Action callback
	######################
	def actionControlSensor(self, action, dev):
		###### TURN ON ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		if action.sensorAction == indigo.kSensorAction.TurnOn:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "on"), level=logging.DEBUG)

		###### TURN OFF ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "off"), level=logging.DEBUG)

		###### TOGGLE ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "toggle"), level=logging.DEBUG)

	########################################
	# General Action callback
	######################
	def actionControlGeneral(self, action, dev):
		###### BEEP ######
		if action.deviceAction == indigo.kDeviceGeneralAction.Beep:
			# Beep the hardware module (dev) here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "beep request"), level=logging.DEBUG)

		###### ENERGY UPDATE ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyUpdate:
			# Request hardware module (dev) for its most recent meter data here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "energy update request"), level=logging.DEBUG)

		###### ENERGY RESET ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyReset:
			# Request that the hardware module (dev) reset its accumulative energy usage data here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "energy reset request"), level=logging.DEBUG)

		###### STATUS REQUEST ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.RequestStatus:
			# Query hardware module (dev) for its current status here. This differs from the
			# indigo.kThermostatAction.RequestStatusAll action - for instance, if your thermo
			# is battery powered you might only want to update it only when the user uses
			# this status request (and not from the RequestStatusAll). This action would
			# get all possible information from the thermostat and the other call
			# would only get thermostat-specific information:
			# ** GET BATTERY INFO **
			# and call the common function to update the thermo-specific data
			self._refreshStatesFromHardware(dev)
			if nationalDebug:
				indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "status request"), level=logging.DEBUG)

	def startup(self):
		global nationalDebug, stationDict, pypath

		if nationalDebug:
			indigo.server.log('Initiating Plugin Startup module...', level=logging.DEBUG)

		if self.pluginPrefs.get('checkboxDebug1',False):
			indigo.server.log(u"startup called")

		# Get configuration
		apiKey = self.pluginPrefs.get('darwinAPI', 'NO KEY')
		dawinURL = self.pluginPrefs.get('darwinSite', 'No URL')
		stationImage = self.pluginPrefs.get('createMaps', "true")
		refreshFreq = int(self.pluginPrefs.get('updateFreq','60'))
		nationalDebug = self.pluginPrefs.get('checkboxDebug1', False)

		if stationImage:
			imagePath= self.pluginPrefs.get('imageFilename', '/Users')
		else:
			imagePath = 'No Image'

		try:
			self.pluginPrefs['checkboxDebug']='false'
			self.pluginPrefs['updaterEmail']=''
			self.pluginPrefs['updaterEmailsEnabled']='false'

		except Exception as e:
			if self.pluginPrefs.get('checkBoxDebug',False):
				self.errorLog(f"Update checker error: {e}")

		for dev in indigo.devices.itervalues("self"):
			# Now check states
			dev.stateListOrDisplayStateIdChanged()

	def shutdown(self):
		indigo.server.log(u"shutdown called")

	########################################
	def runConcurrentThread(self):
		# Get the most current information
		# Validate preferences exist
		global nationalDebug, stationDict, pypath

		# Empty log

		self.logger.info('New Log:'+str(time.strftime(time.asctime()))+'\n')

		logTimeNextReset = time.time()+int(3600)
		indigo.debugger()
		while True:
			# Get configuration
			apiKey = self.pluginPrefs.get('darwinAPI', 'NO KEY')
			darwinURL = self.pluginPrefs.get('darwinSite', 'No URL')
			stationImage = self.pluginPrefs.get('createMaps', "true")
			refreshFreq = int(self.pluginPrefs.get('updateFreq','60'))
			nationalDebug = self.pluginPrefs.get('checkboxDebug1', False)

			fontFullPath = pypath+'BoardFonts/MFonts/Lekton-Bold.ttf' # Regular
			fontFullPathTitle = pypath+'BoardFonts/MFonts/sui generis rg.ttf' # Bold Title
			fontCallingPoints = pypath+'BoardFonts/MFonts/Hack-RegularOblique.ttf' # Italic

			# Get colours for display or defaults
			forcolour = self.pluginPrefs.get('forcolour', '#0F0')
			bgcolour = self.pluginPrefs.get('bgcolour', '#000')
			isscolour = self.pluginPrefs.get('isscolour', '#F00')
			cpcolour = self.pluginPrefs.get('cpcolour', '#FFF')
			ticolour = self.pluginPrefs.get('ticolour', '#0FF')

			# Now create a parameters file - this is user changeable in the BETA version
			parametersFileName = pypath + 'trainparameters.txt'
			parametersFile = open(parametersFileName, 'w')
			parametersFile.write(
				forcolour + ',' + bgcolour + ',' + isscolour + ',' + ticolour + ',' + cpcolour + ',9,3,3,720')
			parametersFile.close()

			if stationImage:
				imagePath= self.pluginPrefs.get('imageFilename', '/Users')

				# Now create a parameters file - this is user changeable in the BETA version
				parametersFileName = pypath+'trainparameters.txt'
				parametersFile = open(parametersFileName,'w')
				parametersFile.write(forcolour+','+bgcolour+','+isscolour+','+ticolour+','+cpcolour+',9,3,3,720')
				parametersFile.close()

			else:
				imagePath = 'No Image'

			try:
				self.pluginPrefs['checkboxDebug']='false'
				self.pluginPrefs['updaterEmail']=''
				self.pluginPrefs['updaterEmailsEnabled']='false'
				self.updater.checkVersionPoll()

			except Exception as e:
				if self.pluginPrefs.get('checkBoxDebug',False):
					self.errorLog(f"Update checker error: {e}")

			# Reset the log?
			if logTimeNextReset<time.time():
				f = open(errorFile,'w')
				f.write('#'*80+'\n')
				f.write('Log reset:'+str(time.strftime(time.asctime()))+'\n')
				f.write('#'*80+'\n')
				f.close()
				logReset = False
				logTimeNextReset = time.time()+int(3600)

			for dev in indigo.devices.iter('self.trainTimetable'):
				# Refresh each of the timeTable route devices in turn

				# Set the state flag
				# Update the standard fields if they've been changed
				# Checking
				# Test mode only
				if nationalDebug:
					indigo.server.log('Device:'+dev.name+' being checked now...', level=logging.DEBUG)

				if nationalDebug:
					indigo.server.log(dev.name+' is '+ str(dev.states['deviceActive']), level=logging.DEBUG)

				if dev.states['deviceActive']:
					dev.updateStateOnServer('stationLong', value = dev.pluginProps['stationName'])
					dev.updateStateOnServer('stationCRS',value = dev.pluginProps['stationCode'])
					dev.updateStateOnServer('destinationLong', value  = dev.pluginProps['destinationName'])
					dev.updateStateOnServer('destinationCRS',value = dev.pluginProps['destinationCode'])

					# Update the device with the latest information
					deviceRefresh = routeUpdate(dev, apiKey, darwinURL, imagePath, parametersFileName)

					if not deviceRefresh:
						# Update failed - probably due to SOAP server timeout
						# Ignore and move onto the next device
						# Change the active icon on this round
						dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
						dev.updateStateOnServer('deviceStatus', value = 'Awaiting update')
						if nationalDebug:
							indigo.server.log('** Error updating device '+dev.name+' SOAP server failure **')
					else:
						# Success
						if dev.states["stationIssues"]:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
							dev.updateStateOnServer('deviceStatus', value = 'Delays or issues')
						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
							dev.updateStateOnServer('deviceStatus', value = 'Running on time')

						if nationalDebug:
							indigo.server.log('** Sucessfully updated:'+dev.name+' **')

				else:
					dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
					dev.updateStateOnServer('deviceStatus', value = 'Not active')

			self.sleep(refreshFreq)

		# Broken out of TRUE loop so shutdown
		self.shutdown()

	########################################
	# Menu. xls
	######################

	# Possible functionality
	# 	Active/Inactive Toggle
	# 	Print departure board to file or log


	########################################
	# Custom Plugin Action callbacks (defined in Actions.xml)
	######################
	# Possible functionality
	# 	Activate/Deactivate
	# 	Refresh Stationboard immediately

	# Selection actions for device configuration

	def selectStation(self, filter="", valuesDict=None, typeId="", targetId=0):
		global nationalDebug, stationDict, pypath

		# Refresh the station codes from file
		stationDict = {}

		# Open the station codes file
		stationCodesFile = pypath+'/stationCodes.txt'

		try:
			stations = open(stationCodesFile,"r")
		except (IOError, OSError) as e:
			# Couldn't find stations file - advise user and exit
			indigo.server.log(f"*** Could not open station code file {stationCodesFile}: {e} ***")
			errorHandler('CRITICAL FAILURE ** Station Code file missing - '+stationCodesFile)
			sys.exit(1)
		indigo.debugger()
		# Extract the data to dictionary
		# Data format is CRS,Station Name (csv)
		stationDict = {}
		stationList = []
		for line in stations:
			stationDetails = line
			stationCRS = stationDetails[:3]
			stationName = stationDetails[4:].replace('\r\n','')

			# Add to dictionary
			#
			stationDict[stationName]=stationName
			stationList.append(stationName)
		# Close the data file
		stations.close()

		if len(stationDict) == 0:
			# Dictionary is empty - advise user and exit
			indigo.server.log('*** Station File is empty - please reinstall '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station code file empty - '+stationCodesFile)
			sys.exit(1)
		indigo.debugger()
		#stationCodeArray = stationDict.items()
		#stationCodeArray.sort(key=lambda x: x.get('1'))
		#jmoistures.sort(key=lambda x: x.get('id'), reverse=True)

		return stationList

	def actionRefreshDevice(self, pluginAction, typeId, dev):
		# This immediately refreshes the device station board information

		return pluginAction

	def refreshDevice(self, valuesDict, typeId):
		# This refreshes the device station information as requested by the plugin

		return valuesDict

	def createStationDict(self):

		global nationalDebug, pypath

		# Refresh the station codes from file
		localStationDict = {}

		# Open the station codes file
		stationCodesFile = pypath+'/stationCodes.txt'

		try:
			stations = open(stationCodesFile,"r")
		except (IOError, OSError) as e:
			# Couldn't find stations file - advise user and exit
			indigo.server.log(f"*** Could not open station code file {stationCodesFile}: {e} ***")
			errorHandler('CRITICAL FAILURE ** Station Code file missing - '+stationCodesFile)
			sys.exit(1)

		# Extract the data to dictionary
		# Data format is CRS,Station Name (csv)
		for line in stations:
			stationDetails = line
			stationCRS = stationDetails[:3]
			stationName = stationDetails[4:].replace('\r\n','')

			# Add to dictionary
			localStationDict[stationName]=stationCRS

		# Close the data file
		stations.close()

		if len(localStationDict) == 0:
			# Dictionary is empty - advise user and exit
			indigo.server.log('*** Station File is empty - please reinstall '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station code file empty - '+stationCodesFile)
			sys.exit(1)

		return localStationDict

	def returnNetworkRailCode(self,fullStationName, localStationDict):
		# Returns a three digit code for a station name in local station dictionary
		global nationalDebug, pypath

		if len(fullStationName) == 0:
			# No station name sent through so return a blank code
			return 'ZZZ'

		if fullStationName in localStationDict:
			# Found the station name
			# return the 3 digital code
			return localStationDict[fullStationName]
		else:
			# Station Name not in Dictionary
			# Return error
			return 'ZZZ'

	def toggleDebugging(self):
		if self.debug:
			self.logger.info("Turning off debug logging")
			self.pluginPrefs["showDebugInfo"] = False
		else:
			self.logger.info("Turning on debug logging")
			self.pluginPrefs["showDebugInfo"] = True
		self.debug = not self.debug


def text2png(imageFileName, trainTextFile, parametersFileName, departuresAvailable):
	# Import the graphic conversion files
	try:
		import PIL
	except ImportError as e:
		print(f"** PILLOW or PIL must be installed: {e} - please see forum for details")
		sys.exit(21)

	# Now get the key modules we're using on this occasion
	from PIL import ImageFont
	from PIL import Image
	from PIL import ImageDraw

	# Get the current python path for text files
	pypath = os.path.realpath(sys.path[0]) + '/'
	indigo.debugger()
	# Get the passed parameters in the command line

	if nationalDebug:
		indigo.server.log(parametersFileName, level=logging.DEBUG)

	if departuresAvailable.find('YES') != -1:
		trainsFound = True
	else:
		trainsFound = False

	# Extract the standard parameters for the image from file
	# This file is used to communication between Indigo and this independant process
	# File format is:
	#   forcolour, bgcolour, isscolour, ticolour, cpcoloour, fontFullpath, fontFullPathTitle, fontSize,leftpadding,
	#   rightpadding, width, trainsfound, imageFileName, sourceDataName

	with open(parametersFileName, 'r') as f:
		parameterSplit = f.readline().split(',')
	forcolour = parameterSplit[0]
	bgcolour = parameterSplit[1]
	isscolour = parameterSplit[2]
	ticolour = parameterSplit[3]
	cpcolour = parameterSplit[4]
	fontsize = int(parameterSplit[5])
	leftpadding = int(parameterSplit[6])
	rightpadding = int(parameterSplit[7])
	width = int(parameterSplit[8])

	# Ok now we need to extract the station for the departure board
	# Extract station and route timetable information

	try:
		routeInfo = open(trainTextFile, 'r')
	except (IOError, OSError) as e:
		print(f"Something wrong with the text file {trainTextFile}: {e}")
		print(sys.exit(22))

	stationTitles = routeInfo.readline()
	stationStatistics = routeInfo.readline()

	timeTable = ''
	for fileEntry in trainTextFile:
		timeTable = timeTable + '\n' + routeInfo.readline()

	# Converts timeTable array into a departure board image for display
	# Work out formatting characters
	REPLACEMENT_CHARACTER = u'ZZFZ'
	NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '

	# Get the fonts for the board
	fontFullPath = pypath + 'BoardFonts/MFonts/Lekton-Bold.ttf'  # Regular
	fontFullPathTitle = pypath + 'BoardFonts/MFonts/sui generis rg.ttf'  # Bold Title
	fontCallingPoints = pypath + 'BoardFonts/MFonts/Hack-RegularOblique.ttf'  # Italic

	# Get the font for the image.  Must be a mono-spaced font for accuracy
	font = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
	titleFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPathTitle, fontsize + 12)
	statusFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 5)
	departFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPath, fontsize + 8)
	delayFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
	callingFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize + 2)
	messagesFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize)

	# Calculate image size
	timeTable = timeTable.replace('\n', NEWLINE_REPLACEMENT_STRING)
	lines = []
	line = u""

	for word in timeTable.split():
		# Check to see if the word is longer than the possible size of image
		if word == REPLACEMENT_CHARACTER:  # give a blank line
			lines.append(line[1:].replace('-', ' '))  # slice the white space in the begining of the line
			line = u""
		# lines.append( u"" ) #the blank line

		elif line.find('++') != -1:
			# This is a status line and can be longer
			# Width is controlled in the main plugin
			line += ' ' + word

		elif font.getsize(line + ' ' + word)[0] <= (width - rightpadding - leftpadding):
			line += ' ' + word

		else:  # start a new line because the word is longer than a line
			# Line splitting now managed in main code
			continue

	if len(line) != 0:
		lines.append(line[1:])  # add the last line

	# Calculate image proportions
	line_height = font.getsize(timeTable)[1]
	img_height = line_height * (30)
	line_height = int(line_height / 1.5 + 0.5)

	if not trainsFound:
		img_height = line_height * (30)

	# Draw the blank image
	img = Image.new("RGBA", (width, img_height), bgcolour)
	draw = ImageDraw.Draw(img)

	# Extract the station details
	# Remove the char returns
	titleLines = stationTitles.replace('\n', NEWLINE_REPLACEMENT_STRING)
	statsLines = stationStatistics.replace('\n', NEWLINE_REPLACEMENT_STRING)

	# Draw the titles in Cyan in title font
	y = 0
	stationName = stationTitles
	draw.text((leftpadding, y), stationName, ticolour, font=titleFont)
	y += line_height + 15
	stationStats = stationStatistics
	draw.text((leftpadding, y), stationStats, cpcolour, font=statusFont)
	y += line_height
	currentService = 0
	maxLines = 35
	maxServices = 5
	noMoreTrains = False

	# Now add the content
	for line in lines:

		# Is this the titles line for the columns?
		if line.find('Destination') != -1:

			# Column titles in cyan
			y += int(line_height * 0.5)
			draw.text((leftpadding, y), line, cpcolour, font=departFont)
			y += line_height

		elif len(line) == 0:
			# Blank line
			y += (line_height / 2 + 0.5)
			pass

		elif line.find('**') != -1:
			# No trains found message
			draw.text((leftpadding + 10, y), line, isscolour, font=statusFont)
			y += line_height * 1.2

		elif line.find('++') != -1:
			# Station Messages found
			draw.text((leftpadding+10, y), line.replace('+',''), isscolour, font=messagesFont)
			y += int(line_height * 0.5)

		elif line.find('Status') != -1:
			draw.text((leftpadding, y), line, ticolour, font=delayFont)
		# y += line_height

		elif line.find('>') == -1:
			if noMoreTrains:
				# Don't process this one onwards
				break

			# Draw a destination with details
			if line.find('On time') != - 1:
				# Train is running on time
				draw.text((leftpadding, y), line, forcolour, font=departFont)

			elif line.find('Special') != -1:
				draw.text((leftpadding, y), line, forcolour, font=callingFont)

			else:
				draw.text((leftpadding, y), line, isscolour, font=departFont)

			y += line_height + 5

			currentService += 1
			if currentService > maxServices:
				# Only five services per board
				noMoreTrains = True
		else:
			# Calling points
			draw.text((leftpadding + 5, y), line.replace('>', ' '), cpcolour, font=callingFont)
			y += line_height
	img1 = img.save(imageFileName, 'png')