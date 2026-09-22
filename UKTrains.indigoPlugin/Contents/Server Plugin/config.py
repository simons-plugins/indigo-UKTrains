# coding=utf-8
"""
Configuration management for UK-Trains plugin

Provides dataclasses and Pydantic models for plugin configuration.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

try:
	from pydantic import BaseModel, Field, field_validator, HttpUrl
except ImportError:
	# Pydantic not available - will use basic validation only
	BaseModel = None
	Field = None
	field_validator = None
	HttpUrl = None

import constants


# ========== Plugin Configuration Class ==========

@dataclass
class PluginConfig:
	"""Centralized plugin configuration to replace global variables."""
	debug: bool
	plugin_path: Path
	station_dict: Dict[str, str]
	pytz_available: bool


@dataclass
class RuntimeConfig:
	"""Runtime configuration loaded from plugin preferences.

	Consolidates all preference reads in one place for efficiency.
	"""
	api_key: str
	create_images: bool
	refresh_freq: int
	color_scheme: 'constants.ColorScheme'  # Forward reference

	@classmethod
	def from_plugin_prefs(cls, prefs: Dict[str, any]) -> 'RuntimeConfig':
		"""Load configuration from plugin preferences dictionary.

		Args:
			prefs: Plugin preferences dictionary

		Returns:
			RuntimeConfig instance with current preferences
		"""
		try:
			refresh_freq = max(30, int(prefs.get('updateFreq', '60')))
		except (ValueError, TypeError):
			refresh_freq = 60

		return cls(
			api_key=prefs.get('darwinAPI', 'NO KEY'),
			create_images=prefs.get('createMaps', "true") == "true",
			refresh_freq=refresh_freq,
			color_scheme=constants.ColorScheme(
				foreground=prefs.get('forcolour', '#0F0'),
				background=prefs.get('bgcolour', '#000'),
				issue=prefs.get('isscolour', '#F00'),
				calling_points=prefs.get('cpcolour', '#FFF'),
				title=prefs.get('ticolour', '#0FF')
			)
		)


@dataclass
class PluginPaths:
	"""Centralized path management for UK-Trains plugin"""

	plugin_root: Path
	fonts_dir: Path
	station_codes_file: Path
	image_output_dir: Path
	log_dir: Path
	# Set when initialize() had to fall back to the default image_output_dir
	# for a *misconfigured* user_image_path - i.e. not empty/whitespace and
	# not the "No images being saved" placeholder validatePrefsConfigUi
	# writes when createMaps is unticked. Holds the raw rejected value so the
	# caller can warn the user; None means no fallback happened, or it
	# happened for an expected reason that doesn't warrant a warning.
	image_output_fallback_from: Optional[str] = None

	@classmethod
	def initialize(cls, plugin_path: str, user_image_path: Optional[str] = None) -> 'PluginPaths':
		"""
		Initialize plugin paths with validation.

		Args:
			plugin_path: Root path of plugin bundle
			user_image_path: User-configured image output directory

		Returns:
			Initialized PluginPaths object
		"""
		root = Path(plugin_path)

		# Standard plugin directories
		fonts = root / 'BoardFonts' / 'MFonts'
		station_codes = root / constants.STATION_CODES_FILE

		# User-configurable image output. Anything that doesn't resolve to an
		# absolute path after stripping whitespace and expanding '~' - empty,
		# whitespace-only, or the "No images being saved" placeholder
		# validatePrefsConfigUi writes when createMaps is unticked (see #21) -
		# falls back to the default instead of being mkdir'd as a relative
		# path under the process's cwd. A '~name' path for an unknown user
		# makes expanduser() raise RuntimeError rather than return a relative
		# path, so that's caught and treated the same as any other
		# non-absolute value.
		default_image_output = Path.home() / 'Documents' / 'IndigoImages'
		image_output = default_image_output
		fallback_from: Optional[str] = None
		if user_image_path:
			stripped = user_image_path.strip()
			candidate = None
			if stripped:
				try:
					candidate = Path(stripped).expanduser()
				except RuntimeError:
					candidate = None

			if candidate is not None and candidate.is_absolute():
				image_output = candidate
			elif stripped and stripped != 'No images being saved':
				fallback_from = user_image_path

		# Ensure image output directory exists
		image_output.mkdir(parents=True, exist_ok=True)

		# Log directory: ask Indigo for its install folder rather than guessing.
		# Older code probed `~/Library/Application Support/Perceptive Automation`,
		# but the real install lives under system `/Library`, not the user home.
		import indigo  # available at plugin runtime
		log_dir = Path(indigo.server.getInstallFolderPath()) / 'Logs'
		log_dir.mkdir(parents=True, exist_ok=True)

		return cls(
			plugin_root=root,
			fonts_dir=fonts,
			station_codes_file=station_codes,
			image_output_dir=image_output,
			log_dir=log_dir,
			image_output_fallback_from=fallback_from
		)

	def get_image_path(self, start_crs: str, end_crs: str) -> Path:
		"""Get path for departure board image"""
		return self.image_output_dir / f'{start_crs}{end_crs}timetable.png'

	def get_text_path(self, start_crs: str, end_crs: str) -> Path:
		"""Get path for departure board text file"""
		return self.image_output_dir / f'{start_crs}{end_crs}departureBoard.txt'

	def get_parameters_file(self) -> Path:
		"""Get path for image generation parameters"""
		return self.plugin_root / 'trainparameters.txt'

	def get_output_log(self) -> Path:
		"""Get path for image generation output log"""
		return self.plugin_root / constants.IMAGE_OUTPUT_LOG

	def get_error_log(self) -> Path:
		"""Get path for image generation error log"""
		return self.plugin_root / constants.IMAGE_ERROR_LOG


# ========== Pydantic Configuration Models ==========

if BaseModel is not None:
	class DarwinAPIConfig(BaseModel):
		"""Configuration for Darwin API access"""
		api_key: str = Field(min_length=10, description="Darwin LDBWS consumer key")
		base_url: str = Field(
			default="https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120",
			description="Rail Data Marketplace LDBWS REST base URL"
		)

		@field_validator('api_key')
		@classmethod
		def validate_api_key(cls, v: str) -> str:
			if v == 'NO KEY' or v == 'NO KEY ENTERED' or v.strip() == '':
				raise ValueError('Valid Darwin API key required')
			if len(v) < 10:
				raise ValueError('Darwin API key must be at least 10 characters')
			return v


	class UpdateConfig(BaseModel):
		"""Configuration for update frequency"""
		frequency_seconds: int = Field(
			default=60,
			ge=30,  # Greater than or equal to 30
			le=600,  # Less than or equal to 600
			description="Update frequency in seconds"
		)


	class ImageConfig(BaseModel):
		"""Configuration for image generation"""
		create_images: bool = Field(default=True, description="Enable image generation")
		image_path: Optional[str] = Field(default=None, description="Path for generated images")
		font_path: str = Field(default="/Library/Fonts", description="Path to fonts directory")
		include_calling_points: bool = Field(default=False, description="Include calling points in display")

		# Color configurations
		normal_color: str = Field(default="#0F0", description="Normal service foreground color")
		background_color: str = Field(default="#000", description="Background color")
		issue_color: str = Field(default="#F00", description="Issue/problem color")
		calling_points_color: str = Field(default="#FFF", description="Calling points color")
		title_color: str = Field(default="#0FF", description="Title text color")

		@field_validator('image_path')
		@classmethod
		def validate_image_path(cls, v: Optional[str]) -> Optional[str]:
			if v is not None and v.strip() != '':
				path = Path(v)
				if not path.parent.exists() and not path.exists():
					raise ValueError(f'Directory does not exist: {v}')
			return v


	class PluginConfiguration(BaseModel):
		"""Complete plugin configuration with validation"""
		darwin: DarwinAPIConfig
		update: UpdateConfig
		image: ImageConfig
		debug: bool = Field(default=False, description="Enable debug logging")

		@classmethod
		def from_plugin_prefs(cls, prefs: dict) -> 'PluginConfiguration':
			"""Create configuration from Indigo plugin preferences"""
			return cls(
				darwin=DarwinAPIConfig(
					api_key=prefs.get('darwinAPI', 'NO KEY'),
					base_url=prefs.get('darwinBaseUrl',
						'https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120')
				),
				update=UpdateConfig(
					frequency_seconds=int(prefs.get('updateFreq', 60))
				),
				image=ImageConfig(
					create_images=prefs.get('createMaps', True) in [True, 'true', 'YES', 'yes'],
					image_path=prefs.get('imageFilename'),
					font_path=prefs.get('fontPath', '/Library/Fonts'),
					include_calling_points=prefs.get('includeCalling', False),
					normal_color=prefs.get('forcolour', '#0F0'),
					background_color=prefs.get('bgcolour', '#000'),
					issue_color=prefs.get('isscolour', '#F00'),
					calling_points_color=prefs.get('cpcolour', '#FFF'),
					title_color=prefs.get('ticolour', '#0FF')
				),
				debug=prefs.get('checkboxDebug1', False)
			)
else:
	# Pydantic not available - define placeholder
	PluginConfiguration = None
