"""
Integration tests for GitHub issue #28 review items 3 and 4:

  3. deviceStopComm/deviceDeleted must clear all per-device throttle state
     (PluginLogger.clear_device()) so a stale failure recorded before the
     device stopped/was deleted doesn't suppress the same failure
     resurfacing once it's communicating again.

  4. The device-level "Image generation failed ... will retry next cycle"
     rollup in routeUpdate() must not duplicate the specific per-style
     ERROR image_generator.py already logs -- a total image-gen failure
     must reach the Event Log as exactly one ERROR, not two.

Plugin.deviceStopComm/deviceDeleted are exercised via Plugin.__new__() (no
__init__) with just `plugin_logger` set -- deviceDeleted calls
super().deviceDeleted(dev), which requires a real Plugin instance (for
super() to resolve), not a bare stand-in object.
"""

import logging
import uuid
from types import SimpleNamespace

import pytest
from unittest.mock import Mock, patch

import plugin


@pytest.fixture
def plugin_logger(tmp_path, event_log):
    plugin_id = f"test-devicelifecycle-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=True, event_log_handler=event_log)


@pytest.fixture
def plugin_instance(plugin_logger):
    """A real Plugin instance without running __init__ -- deviceStopComm/
    deviceDeleted only touch self.plugin_logger, and deviceDeleted's
    super().deviceDeleted(dev) call needs an actual Plugin instance (not a
    bare stand-in) for zero-arg super() to resolve."""
    instance = plugin.Plugin.__new__(plugin.Plugin)
    instance.plugin_logger = plugin_logger
    return instance


@pytest.mark.integration
class TestDeviceStopCommClearsThrottleState:
    def test_failure_stop_comm_same_failure_reaches_event_log_again(
        self, plugin_instance, plugin_logger, event_log
    ):
        dev = SimpleNamespace(id=42)

        plugin_logger.log_failure(f"darwin_fetch:{dev.id}", "fetch failed")
        assert len(event_log.records) == 1

        plugin_instance.deviceStopComm(dev)

        plugin_logger.log_failure(f"darwin_fetch:{dev.id}", "fetch failed")
        assert len(event_log.records) == 2
        assert [r.levelno for r in event_log.records] == [logging.ERROR, logging.ERROR]

    def test_does_not_touch_other_devices(self, plugin_instance, plugin_logger, event_log):
        plugin_logger.log_failure("darwin_fetch:1", "fetch failed")
        plugin_logger.log_failure("darwin_fetch:2", "fetch failed")
        assert len(event_log.records) == 2

        plugin_instance.deviceStopComm(SimpleNamespace(id=1))

        plugin_logger.log_failure("darwin_fetch:2", "fetch failed")  # still throttled
        assert len(event_log.records) == 2


@pytest.mark.integration
class TestDeviceDeletedClearsThrottleState:
    def test_calls_super_and_clears_throttle_state(
        self, plugin_instance, plugin_logger, event_log
    ):
        dev = SimpleNamespace(id=7)

        plugin_logger.log_failure(f"image_gen:{dev.id}:classic", "PIL error")
        assert len(event_log.records) == 1

        # Must not raise (exercises super().deviceDeleted(dev) against the
        # mocked indigo.PluginBase, which now provides a no-op stub).
        plugin_instance.deviceDeleted(dev)

        plugin_logger.log_failure(f"image_gen:{dev.id}:classic", "PIL error")
        assert len(event_log.records) == 2


@pytest.mark.integration
class TestImageGenTotalFailureIsOneEventLogError:
    """routeUpdate's device-level rollup line must not duplicate the
    per-style ERROR image_generator.py already logs when every enabled
    style fails (#28 review item 4)."""

    def test_total_failure_is_exactly_one_event_log_error(
        self, mock_device, mock_darwin_normal, mock_plugin_paths, plugin_logger, event_log
    ):
        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)), \
             patch("image_generator.subprocess.run",
                   return_value=Mock(returncode=2, stdout="", stderr="font missing")):
            result = plugin.routeUpdate(
                mock_device, "test_api_key", mock_plugin_paths, plugin_logger,
            )

        assert result is True  # routeUpdate itself succeeds; only image gen failed
        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "PIL error" in event_log.records[0].getMessage()

    def test_recovery_from_total_failure_is_one_per_style_line_not_two(
        self, mock_device, mock_darwin_normal, mock_plugin_paths, plugin_logger, event_log
    ):
        """Both the per-style recovery (item 2) and the device-level
        rollup (item 4) could announce a recovery for the same event --
        the device-level rollup must stay silent (clear_failure, not
        log_recovery) so only the per-style line appears."""
        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)), \
             patch("image_generator.subprocess.run",
                   return_value=Mock(returncode=2, stdout="", stderr="font missing")):
            plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)
        assert len(event_log.records) == 1

        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)), \
             patch("image_generator.subprocess.run",
                   return_value=Mock(returncode=0, stdout="", stderr="")):
            plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "Classic image generation working again" in event_log.records[1].getMessage()

    def test_no_board_styles_enabled_is_exactly_one_event_log_error(
        self, mock_device, mock_darwin_normal, mock_plugin_paths, plugin_logger, event_log
    ):
        """A misconfigured device (both board styles disabled) already gets
        its own specific ERROR from image_generator.py's config-key
        log_failure() -- the device-level rollup must not add a second."""
        plugin_prefs = {'generateClassicBoard': False, 'generateModernBoard': False}

        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)):
            result = plugin.routeUpdate(
                mock_device, "test_api_key", mock_plugin_paths, plugin_logger, plugin_prefs,
            )

        assert result is True
        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "No board styles enabled" in event_log.records[0].getMessage()
