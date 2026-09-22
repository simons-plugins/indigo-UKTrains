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
import tempfile
import subprocess
import threading
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

class _EventLogForwarder(logging.Handler):
	"""Forwards WARNING+ records from PluginLogger's file-only logger to
	Indigo's own Event Log handler, so PluginLogger keeps propagate=False
	(debug/info chatter stays file-only) while genuine problems still
	surface to the user. Reuses the plugin's real indigo_log_handler
	instance via handle() (not a second logger.log() call), so there's no
	recursion and the Event Log line looks identical to one logged via
	self.logger."""

	def __init__(self, indigo_log_handler: logging.Handler, level=logging.WARNING):
		super().__init__(level=level)
		self._indigo_log_handler = indigo_log_handler

	def emit(self, record: logging.LogRecord):
		try:
			self._indigo_log_handler.handle(record)
		except Exception:
			self.handleError(record)


class PluginLogger:
	"""Structured logger for UK-Trains plugin with rotating file handler"""

	def __init__(self, plugin_id: str, log_dir: Path, debug: bool = False,
				 event_log_handler: Optional[logging.Handler] = None):
		"""
		Initialize plugin logger.

		Args:
			plugin_id: Unique plugin identifier
			log_dir: Directory for log files
			debug: Enable debug-level logging
			event_log_handler: Indigo's own indigo_log_handler (self.indigo_log_handler
				on the Plugin instance). When given, WARNING+ records also reach the
				Indigo Event Log; DEBUG/INFO stay file-only (issue #26).
		"""
		self.logger = logging.getLogger(f'Plugin.{plugin_id}')
		self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
		self.logger.propagate = False  # Prevent messages leaking to Indigo Event Log

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

		# WARNING+ also reaches the Indigo Event Log (see _EventLogForwarder).
		# DEBUG/INFO stay file-only, same as before.
		self._event_log_handler = event_log_handler
		if event_log_handler is not None:
			self.logger.addHandler(_EventLogForwarder(event_log_handler))

		# Per-key state for log_failure()/log_recovery() throttling below.
		# Guarded by _failure_state_lock: clear_device() iterates it from
		# deviceStopComm/deviceDeleted while runConcurrentThread's polling
		# loop can be writing to it for a different device at the same time.
		self._failure_state: Dict[str, str] = {}
		self._failure_state_lock = threading.Lock()

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

	def log_failure(self, key: str, message: str, category: Optional[str] = None,
					 exc_info: bool = False):
		"""Log a failure that may repeat every polling cycle (e.g. image
		generation retried in routeUpdate). The file log gets every
		occurrence; the Event Log gets it only the first time for `key`,
		or again once the failure changes. Call log_recovery() on success so
		a later recurrence is treated as new again.

		`message` is always what gets logged (so callers can fold in
		varying detail like subprocess stderr). `category`, when given, is
		what decides whether this is an "unchanged repeat" -- pass a stable
		classifier (e.g. an exit code or exception type name) when `message`
		itself may vary cycle to cycle even though the underlying failure
		hasn't changed. Defaults to `message` when omitted, matching the old
		behaviour. `exc_info`, when True, keeps the traceback in the file
		log for an unexpected exception (#28 review) -- the Event Log line
		itself is still just `message`.
		"""
		compare_value = message if category is None else category
		with self._failure_state_lock:
			unchanged = self._failure_state.get(key) == compare_value
			if not unchanged:
				self._failure_state[key] = compare_value
		if unchanged:
			# Unchanged repeat: keep it in the file log only.
			self.logger.info(message, exc_info=exc_info)
		else:
			self.logger.error(message, exc_info=exc_info)

	def log_recovery(self, key: str, message: str):
		"""Call after a successful cycle for `key`. No-op unless `key` had
		a failure logged via log_failure(); otherwise clears that failure
		and emits one INFO line straight to the Event Log."""
		with self._failure_state_lock:
			had_failure = self._failure_state.pop(key, None) is not None
		if not had_failure:
			return
		self.logger.info(message)
		if self._event_log_handler is not None:
			record = self.logger.makeRecord(
				self.logger.name, logging.INFO, __file__, 0, message, (), None
			)
			self._event_log_handler.handle(record)

	def clear_failure(self, key: str):
		"""Silently clear a failure key without logging a recovery line.

		Use this for a finer-grained key (e.g. per-style image generation)
		whose recovery is already covered by a broader key's log_recovery()
		call (e.g. per-device) -- so a device shows exactly one "working
		again" Event Log line, not one per sub-key.
		"""
		with self._failure_state_lock:
			self._failure_state.pop(key, None)

	def clear_device(self, dev_id) -> None:
		"""Drop all throttle state belonging to `dev_id` (e.g.
		darwin_fetch:<id>, darwin_login:<id>, image_gen:<id>:classic,
		image_gen:<id>:config).

		Call from deviceStopComm/deviceDeleted so a stale failure recorded
		before the device stopped/was deleted doesn't suppress the same
		failure resurfacing when it (or a device that reuses the id) starts
		again (#28). Matches the id as its own colon-delimited key segment,
		not a bare substring, so clearing device 1 doesn't also clear
		device 12.
		"""
		target = str(dev_id)
		with self._failure_state_lock:
			stale = [key for key in self._failure_state if key.split(':')[1:2] == [target]]
			for key in stale:
				del self._failure_state[key]

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
from darwin_api import (
	darwin_api_retry, _fetch_station_board, _fetch_service_details,
	nationalRailLogin, MISSING_API_KEY_REASON,
)

# ========== Failure classification (extracted to error_classification.py) ==========
from error_classification import classify_exception


# Get darwin access modules and other standard dependencies in place
# Note: Debug logging removed from import checks - happens before Plugin instance exists
try:
	import nredarwin
except ImportError as e:
	indigo.server.log(f"** Couldn't find nredarwin module: {e} - contact developer or check forums for support **", level=logging.CRITICAL)
	sys.exit(3)

from nredarwin.webservice import WebServiceError

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


def routeUpdate(dev, apiAccess, paths, logger, plugin_prefs=None):
	"""
	Update train departure device with latest information from Darwin API.

	Args:
		dev: Indigo device object
		apiAccess: Darwin API key (raildata.org.uk LDBWS consumer key)
		paths: PluginPaths object with all file paths
		logger: Plugin logger for error reporting
		plugin_prefs: Plugin preferences dictionary (self.pluginPrefs)

	Returns:
		True if update successful, False otherwise
	"""
	if not dev.enabled and dev.configured:
		# Device is currently disabled or new so ignore and move on
		return False

	# Login to Darwin
	accessLogin = nationalRailLogin(apiAccess)
	if not accessLogin[0]:
		# Login failed (missing/invalid API key, or the session couldn't be
		# created) -- nationalRailLogin returns the specific reason as its
		# second element instead of just None, so the Event Log line names
		# it instead of always saying "check the API key" (#28 review).
		# Retried every cycle same as a fetch failure, so it's throttled the
		# same way.
		reason = accessLogin[1] or "unknown error"
		category = "missing_key" if reason == MISSING_API_KEY_REASON else classify_exception(Exception(reason))
		login_msg = f"Darwin login failed for '{dev.name}': {reason} - will retry next cycle"
		logger.log_failure(f"darwin_login:{dev.id}", login_msg, category=category)
		return False

	darwinSession = accessLogin[1]
	logger.log_recovery(f"darwin_login:{dev.id}", f"Darwin login working again for '{dev.name}'")

	# Clear all previous train data on device
	_clear_device_states(dev)

	# Ok - now let's get the real data and store it

	# The CRS information will be held against the ROUTE device
	stationStartCrs = dev.states['stationCRS'] # Codes are found on the National Rail data site and will be provided as a drop list for users
	stationEndCrs = dev.states['destinationCRS']

	# Fetch station board with optional destination filter
	try:
		stationBoardDetails = _fetch_station_board(darwinSession, stationStartCrs, stationEndCrs)
	except (WebServiceError, Exception) as e:
		# Retried every cycle on a persistent Darwin outage -- throttled so
		# the Event Log gets it once (then again only on change/recovery),
		# while the file log still gets every occurrence. `category` uses
		# classify_exception() rather than the bare exception type name:
		# nredarwin/webservice.py raises WebServiceError for nearly
		# everything (network outage, HTTP errors, malformed JSON), so the
		# type name alone would suppress e.g. a genuine outage -> 401
		# transition as "the same failure" (#28 review).
		fetch_msg = f"Darwin REST request failed for '{dev.name}': {e} - will retry later when server less busy"
		logger.log_failure(f"darwin_fetch:{dev.id}", fetch_msg, category=classify_exception(e))
		return False

	logger.log_recovery(f"darwin_fetch:{dev.id}", f"Darwin REST request working again for '{dev.name}'")

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
	board_titles = f"Departures - {station_name} {via_station}\n"
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
		logger.debug(f"Board content changed for '{dev.name}', regenerating image")

		image_success = _generate_departure_image(
			paths.plugin_root,
			image_filename,
			train_text_file,
			parameters_file,
			departures_available=departures_found,
			device=dev,
			logger=logger,
			plugin_prefs=plugin_prefs
		)

		if image_success:
			# Update hash only after successful generation
			dev.updateStateOnServer('image_content_hash', current_hash)
			logger.debug(f"Updated content hash for '{dev.name}'")
		else:
			# Retried every cycle on a persistent failure. image_generator.py
			# already logs a specific throttled ERROR per failing style (with
			# stderr detail) -- this rollup would just be a second, less
			# specific Event Log line for the same event, so it stays
			# file-only (#28 review).
			logger.info(f"Image generation failed for '{dev.name}', will retry next cycle")
	else:
		# Content unchanged - skip generation
		logger.debug(f"Board content unchanged for '{dev.name}', skipping image generation")

	return True

# nationalRailLogin moved to darwin_api.py

# ========== Bundled HTML status page ==========
# The trains.html dashboard shipped in the plugin bundle, and where it gets
# copied into Indigo's shared Web Assets folder. Mirrors the pattern used by
# indigo-lamplighter's lamplighter.html.
WEB_PAGE_FILENAME = "trains.html"
WEB_PAGE_BUNDLE_DIR = "UKTrains.indigoPlugin"

_TRUTHY_STRINGS = ("true", "1", "yes")
_FALSY_STRINGS = ("false", "0", "no")


def _truthy(value, default=True, logger=None):
	"""Coerce a prefs checkbox value to bool.

	Indigo can hand a checkbox prop back as the STRING "false" rather than
	the bool False, and `bool("false")` is True - so a naive `.get(key,
	True)` would silently ignore a user unticking the box. None (the pref
	was never set, e.g. an existing install upgrading past this feature)
	resolves to `default`.
	"""
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		normalized = value.strip().lower()
		if normalized in _TRUTHY_STRINGS or normalized in _FALSY_STRINGS:
			return normalized in _TRUTHY_STRINGS
		if logger is not None:
			logger.debug(f"_truthy: unrecognised value {value!r}, treating as false")
		return False
	if logger is not None:
		logger.debug(
			f"_truthy: unexpected type {type(value).__name__} for {value!r}, "
			"coercing with bool()"
		)
	return bool(value)


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
		# indigo.PluginBase.__init__ above sets up self.indigo_log_handler; pass it
		# through so WARNING+ from plugin_logger also reaches the Event Log (#26).
		# getattr guards test doubles that don't set the attribute.
		self.plugin_logger = PluginLogger(
			pluginId, self.paths.log_dir, debug_enabled,
			event_log_handler=getattr(self, 'indigo_log_handler', None)
		)
		self.plugin_logger.info(f"{pluginDisplayName} v{pluginVersion} initializing")
		self._warn_if_image_path_fallback()

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
			pytz_available=not _MODULE_FAILPYTZ
		)

		self.pluginid = pluginId
		# Set up version checker
		travelVersionFile = 'https://www.dropbox.com/s/62kahe2nh848b65/iTravelVersionInfo.html?dl=1'

		if self.config.debug:
			self.plugin_logger.debug('Initiating Plugin Class...')

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def _warn_if_image_path_fallback(self):
		"""Surface a silent redirect: PluginPaths.initialize() falls back to
		the default image_output_dir for a misconfigured imageFilename pref
		with no log of its own (there's no logger yet at that point). Call
		this only from __init__ - runConcurrentThread re-initializes
		self.paths every loop, and repeating the warning there would spam
		the log for a pref that hasn't changed."""
		fallback_from = self.paths.image_output_fallback_from
		if fallback_from:
			self.logger.warning(
				f"Image path '{fallback_from}' is not a full path; writing "
				f"departure boards to {self.paths.image_output_dir} instead "
				f"- fix it in Plugin Config"
			)

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

		if 'updateFreq' in devProps:
			try:
				updateFreq = int(devProps['updateFreq'])
			except (TypeError, ValueError):
				errorDict = indigo.Dict()
				errorDict["updateFreq"] = "Enter a whole number of seconds"
				errorDict["showAlertText"] = "Update frequency must be a whole number of seconds (minimum 30)"
				return (False, devProps, errorDict)

			if updateFreq < 30:
				errorDict = indigo.Dict()
				errorDict["updateFreq"] = "Update frequency must be at least 30 seconds"
				errorDict["showAlertText"] = "Update frequency must be at least 30 seconds"
				return (False, devProps, errorDict)

		if 'createMaps' in devProps:
			if devProps['createMaps']:
				# Check image file name
				if len(devProps.get('imageFilename', '')) == 0:
					errorDict = indigo.Dict()
					errorDict["imageFilename"] = "No file path found for images"
					errorDict["showAlertText"] = "You must enter a path for your image (e.g. /Users/myIndigo) - no trailing '/'"
					return (False, devProps, errorDict)

				# Validate path using pathlib, expanding '~' so the pref is
				# always stored as an absolute path (see #26 - an unexpanded
				# '~' silently created a literal '~' folder under the cwd).
				try:
					image_path = Path(devProps['imageFilename'].strip()).expanduser()
				except RuntimeError:
					# e.g. '~nosuchuser/x' - expanduser() raises RuntimeError
					# (not OSError) for an unknown user in a '~name' path.
					errorDict = indigo.Dict()
					errorDict["imageFilename"] = (
						"Unknown user in '~name' path — enter a full path like "
						"/Users/<name>/Documents/IndigoImages"
					)
					errorDict["showAlertText"] = errorDict["imageFilename"]
					return (False, devProps, errorDict)

				try:
					if not image_path.is_absolute():
						errorDict = indigo.Dict()
						errorDict["imageFilename"] = "Enter a full path for image files"
						errorDict["showAlertText"] = (
							"You must enter a full path for your image, e.g. "
							"/Users/<name>/Documents/IndigoImages - no trailing '/'"
						)
						return (False, devProps, errorDict)

					devProps['imageFilename'] = str(image_path)

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
		# Exclude train devices from SQL Logger (frequent updates with many empty states cause errors)
		if dev.sharedProps.get("sqlLoggerIgnoreStates") != "*":
			shared = dev.sharedProps
			shared["sqlLoggerIgnoreStates"] = "*"
			dev.replaceSharedPropsOnServer(shared)
		if dev.pluginProps['routeActive']:
			dev.updateStateOnServer('deviceActive', True)
		else:
			dev.updateStateOnServer('deviceActive', False)

	def deviceStopComm(self, dev):
		# Drop throttle state for this device (darwin_fetch/darwin_login/
		# image_gen keys) so a failure recorded before it stopped doesn't
		# suppress the same failure resurfacing once it's communicating
		# again (#28).
		self.plugin_logger.clear_device(dev.id)

	def deviceDeleted(self, dev):
		# Special routines for deleted devices
		super().deviceDeleted(dev)
		self.plugin_logger.clear_device(dev.id)

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

	########################################
	# Bundled HTML status page (trains.html) - install/update into Indigo's
	# shared Web Assets folder, matching indigo-lamplighter's pattern.
	######################

	@staticmethod
	def _web_page_paths(install):
		source = os.path.join(
			install, "Plugins", WEB_PAGE_BUNDLE_DIR, "Contents",
			"Resources", "pages", WEB_PAGE_FILENAME,
		)
		dest_dir = os.path.join(install, "Web Assets", "static", "pages")
		return source, dest_dir, os.path.join(dest_dir, WEB_PAGE_FILENAME)

	def _warn_if_managed_page_is_stale(self):
		"""Pref is OFF, so no write happens - but a stale installed page is
		worth one INFO. Read-only and best-effort: ANY failure here (including
		one that has nothing to do with the filesystem, e.g.
		getInstallFolderPath() itself raising) is DEBUG only, with exc_info,
		because an opted-out user must not get WARNINGs/ERRORs about a file
		the plugin isn't managing. The one exception is a missing or empty
		bundled page, which is INFO regardless of the pref - that is a
		damaged install, not a management choice."""
		try:
			install = indigo.server.getInstallFolderPath()
			source, _dest_dir, dest = self._web_page_paths(install)

			if not os.path.isfile(source):
				self.logger.info(
					f"Bundled UK Trains status page missing at {source}; "
					"reinstalling the plugin restores it."
				)
				return

			with open(source, "rb") as handle:
				source_bytes = handle.read()

			if not source_bytes:
				self.logger.info(
					f"Bundled UK Trains status page at {source} is empty "
					"(damaged install); reinstalling the plugin restores it."
				)
				return

			if not os.path.isfile(dest):
				self.logger.debug(
					f"No installed UK Trains status page at {dest} to check for staleness."
				)
				return

			with open(dest, "rb") as handle:
				dest_bytes = handle.read()

			if source_bytes != dest_bytes:
				self.logger.info(
					f"UK Trains status page management is off, and the installed "
					f"page ({dest}) differs from the bundled one (v{self.pluginVersion}) "
					"- update it by hand, or re-tick 'Manage the status page' to have "
					"the plugin do it."
				)
			else:
				self.logger.debug(f"UK Trains status page at {dest} matches the bundled copy.")
		except Exception as exc:
			self.logger.debug(
				f"Could not check the installed status page for staleness: {exc}",
				exc_info=True,
			)

	def _sync_web_page(self, prefs=None):
		"""Install/update the bundled trains.html status page into Web Assets
		on startup and on every prefs save, so the page stops needing a
		manual copy after each change.

		Must NEVER raise: a filesystem problem is a WARNING naming the
		affected path and the way out. When the pref is off, no write
		happens, but `_warn_if_managed_page_is_stale` still flags a stale
		installed copy at INFO.
		"""
		prefs = self.pluginPrefs if prefs is None else prefs
		if not _truthy(prefs.get("managePage"), logger=self.logger):
			self._warn_if_managed_page_is_stale()
			return

		dest = None
		tmp = None
		try:
			try:
				install = indigo.server.getInstallFolderPath()
			except Exception as exc:
				self.logger.warning(
					"Could not determine the Indigo install folder "
					f"({exc}) - cannot install/update the UK Trains status page "
					f"at Web Assets/static/pages/{WEB_PAGE_FILENAME} under your "
					"Indigo installation folder. The plugin will retry at the next "
					"config save or plugin restart."
				)
				return

			source, dest_dir, dest = self._web_page_paths(install)

			if not os.path.isfile(source):
				self.logger.warning(
					f"UK Trains status page not found in the plugin bundle ({source}) "
					f"- cannot install/update it at {dest}. Reinstalling the plugin "
					"should restore the bundled copy."
				)
				return

			try:
				with open(source, "rb") as handle:
					source_bytes = handle.read()
			except OSError as exc:
				self.logger.warning(
					f"The bundled UK Trains status page at {source} cannot be "
					f"read ({exc}) - reinstalling the plugin restores it."
				)
				return

			if not source_bytes:
				self.logger.warning(
					f"Bundled UK Trains status page at {source} is empty (truncated "
					f"or corrupt) - refusing to install it over {dest}. Reinstalling "
					"the plugin should restore the bundled copy."
				)
				return

			dest_bytes = None
			if os.path.isfile(dest):
				try:
					with open(dest, "rb") as handle:
						dest_bytes = handle.read()
				except OSError as exc:
					self.logger.warning(
						f"The installed UK Trains status page at {dest} could not "
						f"be read to check whether it needs updating ({exc}) - "
						"likely a permissions problem. The plugin will retry at "
						"the next config save or plugin restart."
					)
					return

			if dest_bytes == source_bytes:
				self.logger.debug(f"UK Trains status page already up to date in Web Assets ({dest})")
				return

			os.makedirs(dest_dir, exist_ok=True)
			fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".trains.", suffix=".tmp")
			with os.fdopen(fd, "wb") as handle:
				handle.write(source_bytes)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(tmp, dest)
			tmp = None  # installed -- nothing left to clean up

			self.logger.info(
				f"Installed/updated the UK Trains status page at {dest} "
				f"(v{self.pluginVersion} -> managed by the plugin; untick 'Manage the "
				"status page' to hand-edit it)"
			)
		except OSError as exc:
			leftover = ""
			if tmp is not None:
				try:
					os.remove(tmp)
				except FileNotFoundError:
					pass
				except OSError:
					leftover = f" A partial file was left at {tmp}; delete it by hand."
			where = dest or f"Web Assets/static/pages/{WEB_PAGE_FILENAME}"
			self.logger.warning(
				f"Could not install/update the UK Trains status page at {where}: "
				f"{exc}.{leftover} Copy the bundled copy (Contents/Resources/pages/"
				f"{WEB_PAGE_FILENAME} inside the plugin bundle) there by hand, or "
				"untick 'Manage the status page' to stop the plugin trying. The "
				"plugin will retry at the next config save or plugin restart."
			)
		except Exception:
			if tmp is not None:
				try:
					os.remove(tmp)
				except OSError:
					pass
			self.logger.exception("UK Trains status page sync failed unexpectedly")

	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		super().closedPrefsConfigUi(valuesDict, userCancelled)
		if userCancelled:
			return
		# Sync from the just-saved valuesDict, not self.pluginPrefs -- Indigo
		# updates self.pluginPrefs from this same valuesDict, but doing it
		# ourselves means we don't depend on that having happened yet.
		self._sync_web_page(valuesDict)

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
		stationImage = self.pluginPrefs.get('createMaps', "true")

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

		self._sync_web_page()

	def shutdown(self):
		self.plugin_logger.info("UK-Trains plugin shutdown")

	########################################
	def runConcurrentThread(self):
		# Get the most current information
		# Validate preferences exist

		# Empty log

		self.logger.info('New Log:'+str(time.strftime(time.asctime()))+'\n')

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
					deviceRefresh = routeUpdate(dev, runtime_config.api_key, self.paths, self.plugin_logger, self.pluginPrefs)

					if not deviceRefresh:
						# Update failed - probably due to SOAP server timeout
						# Ignore and move onto the next device
						# Change the active icon on this round
						dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
						dev.updateStateOnServer('deviceStatus', value = 'Awaiting update')
						if self.config.debug:
							# routeUpdate() already logged the specific reason
							# (login/fetch/image-gen) via the plugin logger's
							# throttled ERROR path -- this is just a debug-only
							# breadcrumb, not a second Event Log line (#28 review).
							self.plugin_logger.debug('** Update failed for '+dev.name+'; see earlier message **')
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