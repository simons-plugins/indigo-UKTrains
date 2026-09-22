"""
Integration test for Plugin.__init__ wiring plugin_logger to Indigo's real
Event Log handler (GitHub issue #28 review).

Every other test in this suite constructs PluginLogger directly and hands
it a RecordingHandler standing in for indigo_log_handler -- that exercises
PluginLogger's own forwarding logic, but never the __init__ wiring that
connects the two in the first place (`event_log_handler=getattr(self,
'indigo_log_handler', None)`). This test constructs a real Plugin instance
through indigo.PluginBase (mocked) to prove that wiring actually happens.

Plugin.__init__ also calls PluginPaths.initialize(), which would otherwise
touch the real filesystem (indigo.server.getInstallFolderPath() and
Path.home()) -- patched to hand back a tmp_path-backed PluginPaths instead,
per CLAUDE.md's "patch minimally, but test the real __init__ wiring".
"""

import logging
import uuid
from unittest.mock import patch

import pytest

import plugin
from mocks.mock_indigo import RecordingHandler


@pytest.mark.integration
class TestPluginLoggerWiring:
    def test_plugin_init_wires_plugin_logger_to_indigo_log_handler(self, tmp_path):
        fake_paths = plugin.PluginPaths(
            plugin_root=tmp_path,
            fonts_dir=tmp_path,
            station_codes_file=tmp_path / "stationCodes.txt",
            image_output_dir=tmp_path,
            log_dir=tmp_path,
        )

        # A recorder on the "Plugin" namespace itself -- PluginLogger's
        # logger is "Plugin.<plugin_id>" with propagate=False, so this
        # would only ever see something if that guard broke and records
        # leaked upward. No duplicate delivery via propagation, in other
        # words.
        parent_recorder = RecordingHandler()
        parent_logger = logging.getLogger("Plugin")
        parent_logger.addHandler(parent_recorder)

        try:
            with patch.object(plugin.PluginPaths, "initialize", return_value=fake_paths):
                p = plugin.Plugin(
                    f"com.test.uktrains.{uuid.uuid4().hex}",
                    "UK Trains",
                    "2026.3.0",
                    {"darwinAPI": "a_real_looking_key_1234567890"},
                )

            # The wiring itself: PluginLogger was constructed with THIS
            # Plugin instance's indigo_log_handler, not none/something else.
            assert p.plugin_logger._event_log_handler is p.indigo_log_handler

            # __init__ itself may already have logged (e.g. the "vX.Y.Z
            # initializing" INFO line) -- start counting from a clean slate
            # so the assertions below are about OUR call, not init noise.
            p.indigo_log_handler.records.clear()
            parent_recorder.records.clear()

            p.plugin_logger.error("x")

            assert len(p.indigo_log_handler.records) == 1
            assert p.indigo_log_handler.records[0].getMessage() == "x"

            # And it reached there exactly once -- nothing duplicated via
            # propagation to the "Plugin" parent logger.
            total_records = len(p.indigo_log_handler.records) + len(parent_recorder.records)
            assert total_records == 1
        finally:
            parent_logger.removeHandler(parent_recorder)
