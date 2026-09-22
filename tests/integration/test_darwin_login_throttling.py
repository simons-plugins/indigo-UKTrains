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


class RecordingHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def event_log():
    return RecordingHandler()


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
            plugin.routeUpdate(device_b, "bad_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 2

    def test_login_failure_with_bare_logger_falls_back_to_error_handler(
        self, mock_device, mock_plugin_paths
    ):
        """A logger without the throttling API (log_failure) must not
        crash routeUpdate -- mirrors the same guard already covered for
        the Darwin-fetch path."""
        bare_logger = Mock(spec=["debug", "error", "info"])

        with patch("plugin.nationalRailLogin", return_value=(False, None)):
            result = plugin.routeUpdate(
                mock_device, "bad_api_key", mock_plugin_paths, bare_logger,
            )

        assert result is False
