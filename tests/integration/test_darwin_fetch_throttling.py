"""
Integration tests for throttling repeated Darwin REST fetch failures in
routeUpdate() (GitHub issue #28).

A persistently unreachable/erroring Darwin endpoint previously logged a
raw ERROR (or exception) to the Event Log every refresh cycle via the
module-level errorHandler(). routeUpdate() now routes that through
PluginLogger's log_failure()/log_recovery(), keyed per device, so the
Event Log gets one line per distinct failure and one recovery line when
the device starts working again.

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
    plugin_id = f"test-darwinfetch-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=True, event_log_handler=event_log)


@pytest.mark.integration
class TestDarwinFetchFailureThrottling:
    def test_repeated_fetch_failure_is_one_event_log_line(
        self, mock_device, mock_plugin_paths, plugin_logger, event_log
    ):
        mock_session = Mock()

        with patch("plugin.nationalRailLogin", return_value=(True, mock_session)):
            for cycle in range(5):
                mock_session.get_station_board.side_effect = Exception(
                    f"REST request failed (attempt {cycle})"
                )
                result = plugin.routeUpdate(
                    mock_device, "test_api_key", mock_plugin_paths, plugin_logger,
                )
                assert result is False

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

    def test_recovery_after_fetch_failure_emits_one_info_line(
        self, mock_device, mock_darwin_normal, mock_plugin_paths, plugin_logger, event_log
    ):
        mock_session = Mock()
        mock_session.get_station_board.side_effect = Exception("REST request failed")

        with patch("plugin.nationalRailLogin", return_value=(True, mock_session)):
            plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

        # Recovery call: Darwin fetch now succeeds. Image generation is a
        # separate concern (covered by test_image_gen_throttling.py) --
        # stub the subprocess call so it succeeds quietly and doesn't add
        # unrelated Event Log noise to this Darwin-fetch-specific test.
        with patch("plugin.nationalRailLogin", return_value=(True, mock_darwin_normal)), \
             patch("image_generator.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")):
            result = plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)

        assert result is True
        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "Darwin REST request working again" in event_log.records[1].getMessage()

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

        mock_session = Mock()
        mock_session.get_station_board.side_effect = Exception("REST request failed")

        with patch("plugin.nationalRailLogin", return_value=(True, mock_session)):
            plugin.routeUpdate(device_a, "test_api_key", mock_plugin_paths, plugin_logger)
            plugin.routeUpdate(device_b, "test_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 2
