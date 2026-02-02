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
import os, sys, time, datetime, traceback, re
import subprocess
from subprocess import call
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, List, Any
import logging
from logging.handlers import RotatingFileHandler

try:
	from pydantic import BaseModel, Field, field_validator, HttpUrl
except ImportError:
	# Pydantic not available - will use basic validation only
	BaseModel = None
	Field = None
	field_validator = None
	HttpUrl = None

try:
	from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
	# Tenacity not available - retry logic will be disabled
	retry = None
	stop_after_attempt = None
	wait_exponential = None
	retry_if_exception_type = None


try:
	import indigo
except ImportError as e:
	print(f"This programme must be run from inside indigo pro 6: {e}")
	sys.exit(1)
import constants

try:
	import pytz
except ImportError:
	pass


# ========== Plugin Logger Class ==========

class PluginLogger:
	"""Structured logger for UK-Trains plugin with rotating file handler"""

	def __init__(self, plugin_id: str, log_dir: Path, debug: bool = False):
		"""
		Initialize plugin logger.

		Args:
			plugin_id: Unique plugin identifier
			log_dir: Directory for log files
			debug: Enable debug-level logging
		"""
		self.logger = logging.getLogger(f'Plugin.{plugin_id}')
		self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

		# Remove existing handlers
		self.logger.handlers.clear()

		# Create rotating file handler (1MB max, 5 backups)
		log_file = log_dir / 'UKTrains.log'
		file_handler = RotatingFileHandler(
			log_file,
			maxBytes=1_000_000,  # 1 MB
			backupCount=5
		)
		file_handler.setLevel(logging.DEBUG)

		# Create formatter with timestamp, level, function, line number
		formatter = logging.Formatter(
			'%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
			datefmt='%Y-%m-%d %H:%M:%S'
		)
		file_handler.setFormatter(formatter)

		self.logger.addHandler(file_handler)

	def debug(self, msg: str, **kwargs):
		"""Log debug message"""
		self.logger.debug(msg, **kwargs)

	def info(self, msg: str, **kwargs):
		"""Log info message"""
		self.logger.info(msg, **kwargs)

	def warning(self, msg: str, **kwargs):
		"""Log warning message"""
		self.logger.warning(msg, **kwargs)

	def error(self, msg: str, **kwargs):
		"""Log error message"""
		self.logger.error(msg, **kwargs)

	def exception(self, msg: str):
		"""Log exception with traceback"""
		self.logger.exception(msg)

	def set_debug(self, enabled: bool):
		"""Enable/disable debug logging"""
		level = logging.DEBUG if enabled else logging.INFO
		self.logger.setLevel(level)


# ========== Configuration Classes (extracted to config.py) ==========
# Import configuration classes from config module
from config import PluginConfig, PluginPaths, PluginConfiguration, RuntimeConfig


# ========== Module-level pytz check (runs at import time) ==========
# This must stay at module level because it runs before Plugin class instantiation
_MODULE_FAILPYTZ = True  # Will be set to False if pytz import succeeds below

# Get the current python path for text files
_MODULE_PYPATH = os.path.realpath(sys.path[0])

# Now update the system path if necessary
sys.path.append(_MODULE_PYPATH)
_MODULE_PYPATH = _MODULE_PYPATH + '/'


# ========== Error Handler (Module-level function) ==========
# Note: This function remains at module level for backward compatibility
# It will be refactored in a future phase

def errorHandler(error_msg: str):
	"""
	Legacy error handler for backward compatibility.
	Logs to plugin logger if available, otherwise falls back to print.
	"""
	# Try to get logger from global plugin instance
	try:
		if hasattr(sys.modules['__main__'], 'plugin'):
			plugin = sys.modules['__main__'].plugin
			if hasattr(plugin, 'plugin_logger'):
				# Log the exception traceback if available, otherwise just error
				exc_info = sys.exc_info()
				if exc_info[0] is not None:
					plugin.plugin_logger.exception(error_msg)
				else:
					plugin.plugin_logger.error(error_msg)
				return
		# Fallback: print to stderr
		print(f"ERROR: {error_msg}", file=sys.stderr)
		exc_info = sys.exc_info()
		if exc_info[0] is not None:
			traceback.print_exception(*exc_info, limit=2, file=sys.stderr)
	except Exception:
		# Last resort: just print
		print(f"ERROR: {error_msg}", file=sys.stderr)


# ========== Retry Logic with Exponential Backoff ==========

# ========== Darwin API Functions (extracted to darwin_api.py) ==========
# Import Darwin API wrapper functions and retry decorator
from darwin_api import darwin_api_retry, _fetch_station_board, _fetch_service_details, nationalRailLogin


# Get darwin access modules and other standard dependencies in place
# Note: Debug logging removed from import checks - happens before Plugin instance exists
try:
	import nredarwin
except ImportError as e:
	indigo.server.log(f"** Couldn't find nredarwin module: {e} - contact developer or check forums for support **", level=logging.CRITICAL)
	sys.exit(3)

try:
	from zeep.exceptions import Fault as WebFault
except ImportError as e:
	indigo.server.log(f"** Couldn't find zeep module: {e} - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(4)

try:
	import functools
except ImportError as e:
	indigo.server.log(f"** Couldn't find functools module: {e} - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(5)

try:
	import os, logging
except ImportError as e:
	indigo.server.log(f"** Couldn't find standard os or logging modules: {e} - contact the developer for support **", level=logging.CRITICAL)
	sys.exit(6)

try:
	from nredarwin.webservice import DarwinLdbSession
except ImportError as e:
	indigo.server.log(f"** Error accessing nredarwin webservice: {e} - contact developer for support **", level=logging.CRITICAL)
	sys.exit(7)

# Import timezone checker (module-level check before Plugin class exists)
try:
	import pytz
	_MODULE_FAILPYTZ = False
except ImportError as e:
	indigo.server.log(f'WARNING - pytz not present ({e}), times will be in GMT only' , level=logging.INFO)
	_MODULE_FAILPYTZ = True
	pass

# ========== Text Formatting Functions (extracted to text_formatter.py) ==========
# Import text formatting utilities
from text_formatter import getUKTime, delayCalc, formatSpecials


# ========== Device Management and Image Generation (extracted to modules) ==========
# Import device state management functions
from device_manager import (
	_clear_device_states,
	_update_station_issues_flag,
	_process_special_messages,
	_build_calling_points_string,
	_update_train_device_states,
	_process_train_services
)

# Import image generation functions
from image_generator import (
	_write_departure_board_text,
	_generate_departure_image,
	_append_train_to_image,
	_format_station_board,
	compute_board_content_hash,
)


# _fetch_station_board moved to darwin_api.py


# _process_special_messages moved to device_manager.py


# _fetch_service_details moved to darwin_api.py


# _build_calling_points_string moved to device_manager.py


# _update_train_device_states moved to device_manager.py


# _append_train_to_image moved to image_generator.py


# _process_train_services moved to device_manager.py


# _format_station_board moved to image_generator.py


def routeUpdate(dev, apiAccess, networkrailURL, paths, logger):
	"""
	Update train departure device with latest information from Darwin API.

	Args:
		dev: Indigo device object
		apiAccess: Darwin API key
		networkrailURL: Darwin WSDL URL
		paths: PluginPaths object with all file paths
		logger: Plugin logger for error reporting

	Returns:
		True if update successful, False otherwise
	"""
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
	except (WebFault, Exception) as e:
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

	# Debug logging removed - use plugin instance logger instead

	# Initialize image content array
	image_content = ['Destination,Sch,Est,By']
	image_filename = paths.get_image_path(stationStartCrs, stationEndCrs)

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
	train_text_file = paths.get_text_path(stationStartCrs, stationEndCrs)
	_write_departure_board_text(
		train_text_file,
		station_start=stationStartCrs,
		station_end=stationEndCrs,
		titles=board_titles,
		statistics=board_stats,
		messages=special_messages + '\n',
		board_content=station_board
	)

	# Check if image regeneration needed using content hash
	parameters_file = paths.get_parameters_file()
	current_hash = compute_board_content_hash(train_text_file, parameters_file)
	previous_hash = dev.states.get('image_content_hash', '')

	# Log hash comparison for debugging
	if logger:
		if previous_hash:
			logger.debug(f"Content hash for '{dev.name}': prev={previous_hash[:16]}... curr={current_hash[:16]}...")
		else:
			logger.debug(f"No previous hash for '{dev.name}' (first generation)")

	if current_hash != previous_hash:
		# Content changed - regenerate image
		logger.info(f"Board content changed for '{dev.name}', regenerating image")

		image_success = _generate_departure_image(
			paths.plugin_root,
			image_filename,
			train_text_file,
			parameters_file,
			departures_available=departures_found,
			device=dev,
			logger=logger
		)

		if image_success:
			# Update hash only after successful generation
			dev.updateStateOnServer('image_content_hash', current_hash)
			logger.debug(f"Updated content hash for '{dev.name}'")
		else:
			logger.error(f"Image generation failed for '{dev.name}', will retry next cycle")
	else:
		# Content unchanged - skip generation
		logger.debug(f"Board content unchanged for '{dev.name}', skipping image generation")

	return True

# nationalRailLogin moved to darwin_api.py

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):

		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.validatePrefsConfigUi(pluginPrefs)

		# Initialize paths first
		user_image_path = pluginPrefs.get('imageFilename')
		self.paths = PluginPaths.initialize(_MODULE_PYPATH.rstrip('/'), user_image_path)

		# Create structured logger using paths object
		debug_enabled = pluginPrefs.get('checkboxDebug1', False)
		self.plugin_logger = PluginLogger(pluginId, self.paths.log_dir, debug_enabled)
		self.plugin_logger.info(f"{pluginDisplayName} v{pluginVersion} initializing")

		# Validate configuration using Pydantic
		if PluginConfiguration is not None:
			try:
				self.validated_config = PluginConfiguration.from_plugin_prefs(pluginPrefs)
				self.plugin_logger.info("Configuration validated successfully")
			except Exception as e:
				self.plugin_logger.error(f"Configuration validation failed: {e}")
				self.plugin_logger.warning("Continuing with default configuration. Please check plugin settings.")
				# Continue with defaults but log error
				self.validated_config = None
		else:
			self.plugin_logger.warning("Pydantic not available - using basic validation only")
			self.validated_config = None

		# Initialize plugin configuration (replaces global variables)
		self.config = PluginConfig(
			debug=pluginPrefs.get('checkboxDebug1', False),
			plugin_path=Path(_MODULE_PYPATH),
			station_dict={},
			error_log_path=Path('/Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/NationRailErrors.log'),
			pytz_available=not _MODULE_FAILPYTZ
		)

		self.pluginid = pluginId
		# Set up version checker
		travelVersionFile = 'https://www.dropbox.com/s/62kahe2nh848b65/iTravelVersionInfo.html?dl=1'

		if self.config.debug:
			self.plugin_logger.debug('Initiating Plugin Class...')

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def validateDeviceConfigUi(self, devProps, typeId, devId):

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

		if hasattr(self, 'config') and self.config.debug:
			self.plugin_logger.debug('Validating Config file...')

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

				# Validate path using pathlib
				try:
					image_path = Path(devProps['imageFilename'])
					if hasattr(self, 'config') and self.config.debug:
						self.plugin_logger.debug(f'Validating image path: {image_path}')

					# Ensure directory exists or can be created
					image_path.mkdir(parents=True, exist_ok=True)

					# Test write permissions
					test_file = image_path / 'filecheck.txt'
					with open(test_file, 'w') as f:
						f.write('test')
					test_file.unlink()  # Remove test file
				except (IOError, OSError, PermissionError) as e:
					# Can't open file in location report error to user
					errorDict = indigo.Dict()
					errorDict["imageFilename"] = "Invalid path for image files"
					errorDict["showAlertText"] = f"Cannot write to path (e.g. /Users/myIndigo) - no trailing '/': {e}"
					return (False, devProps, errorDict)

			else:
				# No maps
				devProps['imageFilename'] = 'No images being saved'
		else:
			devProps['createMaps'] = False

		if 'forcolour' in devProps:
			if '#' not in devProps['forcolour']:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["forcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #0F0 default = Green)"
				return (False, devProps, errorDict)

		if 'bgcolour' in devProps:
			if '#' not in devProps['bgcolour']:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["bgcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = Black)"
				return (False, devProps, errorDict)

		if 'isscolour' in devProps:
			if '#' not in devProps['isscolour']:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["isscolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #F00 default = Red)"
				return (False, devProps, errorDict)

		if 'cpcolour' in devProps:
			if '#' not in devProps['cpcolour']:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["cpcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = White)"
				return (False, devProps, errorDict)

		if 'ticolour' in devProps:
			if '#' not in devProps['ticolour']:
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
		if self.config.debug:
			self.plugin_logger.debug("RGB States check called")

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
			if self.config.debug:
				self.plugin_logger.debug(f'ignored "{dev.name}" on request (sensor is read-only)')

		###### TURN OFF ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			if self.config.debug:
				self.plugin_logger.debug(f'ignored "{dev.name}" off request (sensor is read-only)')

		###### TOGGLE ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			if self.config.debug:
				self.plugin_logger.debug(f'ignored "{dev.name}" toggle request (sensor is read-only)')

	########################################
	# General Action callback
	######################
	def actionControlGeneral(self, action, dev):
		###### BEEP ######
		if action.deviceAction == indigo.kDeviceGeneralAction.Beep:
			# Beep the hardware module (dev) here:
			# ** IMPLEMENT ME **
			self.plugin_logger.debug(f'sent "{dev.name}" beep request')

		###### ENERGY UPDATE ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyUpdate:
			# Request hardware module (dev) for its most recent meter data here:
			# ** IMPLEMENT ME **
			self.plugin_logger.debug(f'sent "{dev.name}" energy update request')

		###### ENERGY RESET ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyReset:
			# Request that the hardware module (dev) reset its accumulative energy usage data here:
			# ** IMPLEMENT ME **
			self.plugin_logger.debug(f'sent "{dev.name}" energy reset request')

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
			if self.config.debug:
				self.plugin_logger.debug(f'sent "{dev.name}" status request')

	def startup(self):

		self.plugin_logger.info("UK-Trains plugin startup")

		# Update log level if debug setting changed
		debug_enabled = self.pluginPrefs.get('checkboxDebug1', False)
		self.plugin_logger.set_debug(debug_enabled)
		self.config.debug = debug_enabled

		if self.config.debug:
			self.plugin_logger.debug('Initiating Plugin Startup module...')

		# Get configuration
		apiKey = self.pluginPrefs.get('darwinAPI', 'NO KEY')
		dawinURL = self.pluginPrefs.get('darwinSite', 'No URL')
		stationImage = self.pluginPrefs.get('createMaps', "true")
		refreshFreq = int(self.pluginPrefs.get('updateFreq','60'))

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

		for dev in indigo.devices.iter("self"):
			# Now check states
			dev.stateListOrDisplayStateIdChanged()

	def shutdown(self):
		self.plugin_logger.info("UK-Trains plugin shutdown")

	########################################
	def runConcurrentThread(self):
		# Get the most current information
		# Validate preferences exist

		# Empty log

		self.logger.info('New Log:'+str(time.strftime(time.asctime()))+'\n')

		logTimeNextReset = time.time()+int(3600)
		indigo.debugger()
		while True:
			# Load configuration once per loop using RuntimeConfig
			runtime_config = RuntimeConfig.from_plugin_prefs(self.pluginPrefs)
			self.config.debug = self.pluginPrefs.get('checkboxDebug1', False)

			# Update image path if it changed in preferences
			user_image_path = self.pluginPrefs.get('imageFilename')
			if user_image_path and runtime_config.create_images:
				# User changed image path, reinitialize paths
				self.paths = PluginPaths.initialize(_MODULE_PYPATH.rstrip('/'), user_image_path)

			# Create parameters file using ColorScheme
			parameters_file = self.paths.get_parameters_file()
			colors = runtime_config.color_scheme
			with open(parameters_file, 'w') as f:
				f.write(f'{colors.foreground},{colors.background},{colors.issue},{colors.title},{colors.calling_points},9,3,3,720')

			# Note: Update checker functionality removed - self.updater was never initialized
			# If update checking is needed in the future, initialize self.updater in __init__

			# Reset the log?
			if logTimeNextReset<time.time():
				with open(self.config.error_log_path, 'w') as f:
					f.write('#'*80+'\n')
					f.write('Log reset:'+str(time.strftime(time.asctime()))+'\n')
					f.write('#'*80+'\n')
				logReset = False
				logTimeNextReset = time.time()+int(3600)

			for dev in indigo.devices.iter('self.trainTimetable'):
				# Refresh each of the timeTable route devices in turn

				# Set the state flag
				# Update the standard fields if they've been changed
				# Checking
				# Test mode only
				if self.config.debug:
					self.plugin_logger.debug('Device:'+dev.name+' being checked now...')

				if self.config.debug:
					self.plugin_logger.debug(dev.name+' is '+ str(dev.states['deviceActive']))

				if dev.states['deviceActive']:
					dev.updateStateOnServer('stationLong', value = dev.pluginProps['stationName'])
					dev.updateStateOnServer('stationCRS',value = dev.pluginProps['stationCode'])
					dev.updateStateOnServer('destinationLong', value  = dev.pluginProps['destinationName'])
					dev.updateStateOnServer('destinationCRS',value = dev.pluginProps['destinationCode'])

					# Update the device with the latest information
					deviceRefresh = routeUpdate(dev, runtime_config.api_key, runtime_config.darwin_url, self.paths, self.plugin_logger)

					if not deviceRefresh:
						# Update failed - probably due to SOAP server timeout
						# Ignore and move onto the next device
						# Change the active icon on this round
						dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
						dev.updateStateOnServer('deviceStatus', value = 'Awaiting update')
						if self.config.debug:
							self.plugin_logger.error('** Error updating device '+dev.name+' SOAP server failure **')
					else:
						# Success
						if dev.states["stationIssues"]:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
							dev.updateStateOnServer('deviceStatus', value = 'Delays or issues')
						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
							dev.updateStateOnServer('deviceStatus', value = 'Running on time')

						if self.config.debug:
							self.plugin_logger.debug('** Sucessfully updated:'+dev.name+' **')

				else:
					dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
					dev.updateStateOnServer('deviceStatus', value = 'Not active')

			self.sleep(runtime_config.refresh_freq)

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

		# Refresh the station codes from file
		self.config.station_dict = {}

		# Open the station codes file using pathlib
		station_codes_file = self.paths.station_codes_file

		try:
			with open(station_codes_file, "r") as stations:
				# Extract the data to dictionary
				# Data format is CRS,Station Name (csv)
				lines = stations.readlines()
				# Build station list using comprehension
				stationList = [line[4:].replace('\r\n', '') for line in lines]
				# Build dictionary for lookup (maps name to name for consistency)
				local_station_dict = {line[4:].replace('\r\n', ''): line[4:].replace('\r\n', '') for line in lines}
		except (IOError, OSError) as e:
			# Couldn't find stations file - advise user and exit
			self.plugin_logger.error(f"*** Could not open station code file {station_codes_file}: {e} ***")
			errorHandler(f'CRITICAL FAILURE ** Station Code file missing - {station_codes_file}')
			sys.exit(1)

		if len(local_station_dict) == 0:
			# Dictionary is empty - advise user and exit
			indigo.server.log(f'*** Station File is empty - please reinstall {station_codes_file} ***')
			errorHandler(f'CRITICAL FAILURE ** Station code file empty - {station_codes_file}')
			sys.exit(1)

		return stationList

	def actionRefreshDevice(self, pluginAction, typeId, dev):
		# This immediately refreshes the device station board information

		return pluginAction

	def refreshDevice(self, valuesDict, typeId):
		# This refreshes the device station information as requested by the plugin

		return valuesDict

	def createStationDict(self):

		# Refresh the station codes from file
		# Open the station codes file using pathlib
		station_codes_file = self.paths.station_codes_file

		try:
			with open(station_codes_file, "r") as stations:
				# Extract the data to dictionary
				# Data format is CRS,Station Name (csv)
				# Build dictionary using comprehension: {station_name: CRS_code}
				localStationDict = {
					line[4:].replace('\r\n', ''): line[:3]
					for line in stations
				}
		except (IOError, OSError) as e:
			# Couldn't find stations file - advise user and exit
			self.plugin_logger.error(f"*** Could not open station code file {station_codes_file}: {e} ***")
			errorHandler(f'CRITICAL FAILURE ** Station Code file missing - {station_codes_file}')
			sys.exit(1)

		if len(localStationDict) == 0:
			# Dictionary is empty - advise user and exit
			self.plugin_logger.error(f'*** Station File is empty - please reinstall {station_codes_file} ***')
			errorHandler(f'CRITICAL FAILURE ** Station code file empty - {station_codes_file}')
			sys.exit(1)

		return localStationDict

	def returnNetworkRailCode(self,fullStationName, localStationDict):
		# Returns a three digit code for a station name in local station dictionary

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
	# Get the passed parameters in the command line

	# Debug logging removed - this is a subprocess
	# Use subprocess output files instead

	if 'YES' in departuresAvailable:
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
		with open(trainTextFile, 'r') as routeInfo:
			stationTitles = routeInfo.readline()
			stationStatistics = routeInfo.readline()

			timeTable = ''
			for line in routeInfo:
				timeTable = timeTable + '\n' + line.rstrip('\n')
	except (IOError, OSError) as e:
		print(f"Something wrong with the text file {trainTextFile}: {e}")
		sys.exit(22)

	# Converts timeTable array into a departure board image for display
	# Work out formatting characters
	REPLACEMENT_CHARACTER = 'ZZFZ'
	NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '

	# Get the fonts for the board
	fontFullPath = pypath + 'BoardFonts/MFonts/Lekton-Bold.ttf'  # Regular
	fontFullPathTitle = pypath + 'BoardFonts/MFonts/sui generis rg.ttf'  # Bold Title
	fontCallingPoints = pypath + 'BoardFonts/MFonts/Hack-RegularOblique.ttf'  # Italic

	# Get the font for the image.  Must be a mono-spaced font for accuracy
	font = ImageFont.load_default() if fontFullPath is None else ImageFont.truetype(fontFullPath, fontsize + 4)
	titleFont = ImageFont.load_default() if fontFullPathTitle is None else ImageFont.truetype(fontFullPathTitle, fontsize + 12)
	statusFont = ImageFont.load_default() if fontFullPath is None else ImageFont.truetype(fontFullPath, fontsize + 5)
	departFont = ImageFont.load_default() if fontFullPathTitle is None else ImageFont.truetype(fontFullPath, fontsize + 8)
	delayFont = ImageFont.load_default() if fontFullPath is None else ImageFont.truetype(fontFullPath, fontsize + 4)
	callingFont = ImageFont.load_default() if fontFullPath is None else ImageFont.truetype(fontCallingPoints, fontsize + 2)
	messagesFont = ImageFont.load_default() if fontFullPath is None else ImageFont.truetype(fontCallingPoints, fontsize)

	# Calculate image size
	timeTable = timeTable.replace('\n', NEWLINE_REPLACEMENT_STRING)
	lines = []
	line = ""

	for word in timeTable.split():
		# Check to see if the word is longer than the possible size of image
		if word == REPLACEMENT_CHARACTER:  # give a blank line
			lines.append(line[1:].replace('-', ' '))  # slice the white space in the begining of the line
			line = ""
		# lines.append( "" ) #the blank line

		elif '++' in line:
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
		if 'Destination' in line:

			# Column titles in cyan
			y += int(line_height * 0.5)
			draw.text((leftpadding, y), line, cpcolour, font=departFont)
			y += line_height

		elif len(line) == 0:
			# Blank line
			y += (line_height / 2 + 0.5)
			pass

		elif '**' in line:
			# No trains found message
			draw.text((leftpadding + 10, y), line, isscolour, font=statusFont)
			y += line_height * 1.2

		elif '++' in line:
			# Station Messages found
			draw.text((leftpadding+10, y), line.replace('+',''), isscolour, font=messagesFont)
			y += int(line_height * 0.5)

		elif 'Status' in line:
			draw.text((leftpadding, y), line, ticolour, font=delayFont)
		# y += line_height

		elif '>' not in line:
			if noMoreTrains:
				# Don't process this one onwards
				break

			# Draw a destination with details
			if constants.TrainStatus.ON_TIME.value in line:
				# Train is running on time
				draw.text((leftpadding, y), line, forcolour, font=departFont)

			elif 'Special' in line:
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