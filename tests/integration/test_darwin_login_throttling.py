"""
Integration tests for throttling repeated Darwin login failures in
routeUpdate() (GitHub issue #28 review).

Before this, nationalRailLogin() returning (False, None) -- missing/bad API
key, or the session itself failing to construct -- was silently ignored by
routeUpdate(): nothing reached the plugin logger at all, only a print() to
stderr inside darwin_api.py. A persistently bad API key retried every cycle
produced zero visibility in the Event Log. routeUpdate() now routes that
through PluginLogger's log_failure()/log_recovery(), keyed per device, the
same as the Darwin-fetch and image-gen failure paths.

Reuses the RecordingHandler double-attachment pattern from
test_event_log_forwarding.py -- PluginLogger's internal logger has
propagate=False, so caplog can't see it directly.
"""

import logging
import uuid

import pytest
from unittest.mock import Mock, patch

import plugin


@pytest.fixture
def plugin_logger(tmp_path, event_log):
    plugin_id = f"test-darwinlogin-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=True, event_log_handler=event_log)


@pytest.mark.integration
class TestDarwinLoginFailureThrottling:
    def test_repeated_login_failure_is_one_event_log_line(
        self, mock_device, mock_plugin_paths, plugin_logger, event_log
    ):
        with patch("plugin.nationalRailLogin", return_value=(False, None)):
            for _ in range(5):
                result = plugin.routeUpdate(
                    mock_device, "bad_api_key", mock_plugin_paths, plugin_logger,
                )
                assert result is False

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "login" in event_log.records[0].getMessage().lower()

    def test_recovery_after_login_failure_emits_one_info_line(
        self, mock_device, mock_darwin_normal, mock_plugin_paths, plugin_logger, event_log
    ):
        with patch("plugin.nationalRailLogin", return_value=(False, None)):
            plugin.routeUpdate(mock_device, "bad_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)), \
             patch("image_generator.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")):
            result = plugin.routeUpdate(mock_device, "good_api_key", mock_plugin_paths, plugin_logger)

        assert result is True
        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "login" in event_log.records[1].getMessage().lower()
        assert "working again" in event_log.records[1].getMessage().lower()

    def test_two_devices_do_not_throttle_each_other(
        self, mock_plugin_paths, plugin_logger, event_log
    ):
        from mocks.mock_indigo import create_mock_device

        device_a = create_mock_device(device_id=1, name="Device A", states={
            'stationCRS': 'PAD', 'destinationCRS': 'BRI', 'stationLong': '', 'timeGenerated': '',
        })
        device_b = create_mock_device(device_id=2, name="Device B", states={
            'stationCRS': 'PAD', 'destinationCRS': 'BRI', 'stationLong': '', 'timeGenerated': '',
        })

        with patch("plugin.nationalRailLogin", return_value=(False, None)):
            plugin.routeUpdate(device_a, "bad_api_key", mock_plugin_paths, plugin_logger)
            # Repeat for device_a first -- proves per-device suppression is
            # actually active, so the assertion below (device_b also
            # reaching the Event Log) can't pass just because throttling is
            # broken entirely (#28 review: degradation-path coverage).
            plugin.routeUpdate(device_a, "bad_api_key", mock_plugin_paths, plugin_logger)
            assert len(event_log.records) == 1

            plugin.routeUpdate(device_b, "bad_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 2

    def test_login_message_names_the_real_reason(
        self, mock_device, mock_plugin_paths, plugin_logger, event_log
    ):
        """nationalRailLogin() returns the actual failure reason as its
        second element on failure (not None) -- routeUpdate must put it in
        the Event Log line instead of the old generic 'check the API key'
        (#28 review)."""
        with patch("plugin.nationalRailLogin", return_value=(False, "Failed to create Darwin REST session: Darwin REST 403 Forbidden: bad key")):
            result = plugin.routeUpdate(
                mock_device, "bad_api_key", mock_plugin_paths, plugin_logger,
            )

        assert result is False
        assert len(event_log.records) == 1
        assert "403 Forbidden" in event_log.records[0].getMessage()

    def test_missing_api_key_end_to_end_repeats_are_suppressed(
        self, mock_device, mock_plugin_paths, plugin_logger, event_log
    ):
        """Exercises the real nationalRailLogin() (not patched) with a
        missing API key, end-to-end through routeUpdate -- must reach the
        Event Log once as ERROR naming the real reason, then stay
        suppressed on repeats (category='missing_key' is a stable
        classifier, not a per-call message comparison)."""
        for _ in range(3):
            result = plugin.routeUpdate(
                mock_device, "NO KEY", mock_plugin_paths, plugin_logger,
            )
            assert result is False

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "API key is missing" in event_log.records[0].getMessage()
