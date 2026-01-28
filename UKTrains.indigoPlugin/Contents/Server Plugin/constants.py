"""
Constants for UK-Trains Indigo Plugin

This module defines all magic numbers and configuration constants used throughout
the plugin, making them easier to maintain and understand.
"""
import sys
from enum import Enum
from dataclasses import dataclass
from typing import Dict

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

# Python executable path - use currently running interpreter
PYTHON3_PATH = sys.executable

# Special status strings
class TrainStatus(Enum):
    """Train service status codes returned by Darwin API"""
    ON_TIME = "On time"
    CANCELLED = "Cancelled"
    DELAYED = "Delayed"
    EARLY = "early"
    LATE = "late"

# Legacy constants for backward compatibility (deprecated - use TrainStatus enum)
STATUS_ON_TIME = TrainStatus.ON_TIME.value
STATUS_CANCELLED = TrainStatus.CANCELLED.value
STATUS_DELAYED = TrainStatus.DELAYED.value
STATUS_EARLY = TrainStatus.EARLY.value
STATUS_LATE = TrainStatus.LATE.value

@dataclass(frozen=True)
class ColorScheme:
    """Immutable color configuration for departure board images.

    All colors in hex format (e.g., '#0F0' for green).
    """
    foreground: str = '#0F0'      # Green - default text color
    background: str = '#000'      # Black - background
    issue: str = '#F00'           # Red - delays/cancellations
    calling_points: str = '#FFF'  # White - calling points text
    title: str = '#0FF'           # Cyan - board title

    def to_dict(self) -> dict:
        """Convert to dictionary for easy parameter passing"""
        return {
            'forcolour': self.foreground,
            'bgcolour': self.background,
            'isscolour': self.issue,
            'cpcolour': self.calling_points,
            'ticolour': self.title
        }

# CRS code for "all destinations"
ALL_DESTINATIONS_CRS = 'ALL'
