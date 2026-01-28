"""
Constants for UK-Trains Indigo Plugin

This module defines all magic numbers and configuration constants used throughout
the plugin, making them easier to maintain and understand.
"""

# Train limits
MAX_TRAINS_TRACKED = 10  # Maximum number of trains to track per device
MAX_TRAINS_DISPLAYED = 5  # Maximum number of trains to display

# Update intervals (in seconds)
DEFAULT_UPDATE_FREQ_SECONDS = 60
MIN_UPDATE_FREQ_SECONDS = 30
MAX_UPDATE_FREQ_SECONDS = 600

# Darwin API configuration
DARWIN_WSDL_DEFAULT = 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'
DARWIN_ROW_LIMIT = 10  # Number of services to request from API
STATION_CODES_FILE = 'stationCodes.txt'

# Image generation - dimensions
DEFAULT_IMAGE_WIDTH = 720
DEFAULT_IMAGE_HEIGHT = 400

# Image generation - fonts
DEFAULT_FONT_SIZE = 9
DEFAULT_FONT_NAME = 'Dot Matrix Regular'
TITLE_FONT_SIZE = 12
CALLING_POINTS_FONT_SIZE = 7

# Image generation - colors (hex format)
DEFAULT_FOREGROUND_COLOR = '#0F0'  # Green
DEFAULT_BACKGROUND_COLOR = '#000'  # Black
DEFAULT_ISSUE_COLOR = '#F00'  # Red
DEFAULT_TEXT_COLOR = '#0F0'  # Green

# Image generation - layout
DEST_PAD_WIDTH = 40  # Padding for destination column
TIME_PAD_WIDTH = 10  # Padding for time columns
LINE_HEIGHT = 20  # Height of each line in pixels

# Text formatting
MAX_MESSAGE_LINES = 2  # Maximum lines for special messages
MAX_LINE_LENGTH = 130  # Maximum characters per line

# File paths
ERROR_LOG_FILENAME = 'UKTrainsErrors.log'
IMAGE_OUTPUT_LOG = 'myImageOutput.txt'
IMAGE_ERROR_LOG = 'myImageErrors.txt'

# Python executable path
PYTHON3_PATH = '/Library/Frameworks/Python.framework/Versions/Current/bin/python3'

# Special status strings
STATUS_ON_TIME = 'On time'
STATUS_CANCELLED = 'Cancelled'
STATUS_DELAYED = 'Delayed'

# CRS code for "all destinations"
ALL_DESTINATIONS_CRS = 'ALL'
