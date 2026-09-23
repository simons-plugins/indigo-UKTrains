"""
Integration tests for station-code-file error logging in
createStationDict()/selectStation() (GitHub issue #30, follow-up to #23).

Background: both methods previously logged via self.plugin_logger.error()
*and* the legacy module-level errorHandler() -- a redundant second log call
whose own path back to the Event Log depended on a sys.modules['__main__']
lookup that mostly no-op'd in production (it only worked if something had
already set `sys.modules['__main__'].plugin`, which nothing in this plugin
does). errorHandler() is now deleted; these are Plugin methods, so a single
self.plugin_logger.error() call reaches the Event Log directly (WARNING+
forwarding wired up in issue #26) -- and these are fatal misconfigurations
(the plugin calls sys.exit(1) right after), so ERROR is correct.

Constructs a real Plugin instance the same way as
test_plugin_logger_wiring.py, so this exercises the actual __init__ wiring
between plugin_logger and indigo_log_handler, not a synthetic double.
"""

import logging
import uuid
from unittest.mock import patch

import pytest

import plugin


@pytest.fixture
def real_plugin(tmp_path):
    fake_paths = plugin.PluginPaths(
        plugin_root=tmp_path,
        fonts_dir=tmp_path,
        station_codes_file=tmp_path / "stationCodes.txt",
        image_output_dir=tmp_path,
        log_dir=tmp_path,
    )
    with patch.object(plugin.PluginPaths, "initialize", return_value=fake_paths):
        p = plugin.Plugin(
            f"com.test.uktrains.{uuid.uuid4().hex}",
            "UK Trains",
            "2026.3.1",
            {"darwinAPI": "a_real_looking_key_1234567890"},
        )
    # __init__ itself may already have logged (e.g. the "vX.Y.Z
    # initializing" INFO line) -- start counting from a clean slate so the
    # assertions below are about the station-file error, not init noise.
    p.indigo_log_handler.records.clear()
    return p


@pytest.mark.integration
class TestCreateStationDictErrors:
    def test_missing_file_reaches_event_log_as_error_and_exits(self, real_plugin):
        # station_codes_file was never created on disk.
        with pytest.raises(SystemExit):
            real_plugin.createStationDict()

        assert len(real_plugin.indigo_log_handler.records) == 1
        record = real_plugin.indigo_log_handler.records[0]
        assert record.levelno == logging.ERROR
        assert "Could not open station code file" in record.getMessage()

    def test_empty_file_reaches_event_log_as_error_and_exits(self, real_plugin):
        real_plugin.paths.station_codes_file.write_text("")

        with pytest.raises(SystemExit):
            real_plugin.createStationDict()

        assert len(real_plugin.indigo_log_handler.records) == 1
        record = real_plugin.indigo_log_handler.records[0]
        assert record.levelno == logging.ERROR
        assert "Station File is empty" in record.getMessage()


@pytest.mark.integration
class TestSelectStationErrors:
    def test_missing_file_reaches_event_log_as_error_and_exits(self, real_plugin):
        with pytest.raises(SystemExit):
            real_plugin.selectStation()

        assert len(real_plugin.indigo_log_handler.records) == 1
        record = real_plugin.indigo_log_handler.records[0]
        assert record.levelno == logging.ERROR
        assert "Could not open station code file" in record.getMessage()

    def test_empty_file_reaches_event_log_as_error_and_exits(self, real_plugin):
        real_plugin.paths.station_codes_file.write_text("")

        with pytest.raises(SystemExit):
            real_plugin.selectStation()

        assert len(real_plugin.indigo_log_handler.records) == 1
        record = real_plugin.indigo_log_handler.records[0]
        assert record.levelno == logging.ERROR
        assert "Station File is empty" in record.getMessage()
