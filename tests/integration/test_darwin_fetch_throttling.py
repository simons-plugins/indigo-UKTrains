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
            # Repeat for device_a first -- proves per-device suppression is
            # actually active, so the assertion below (device_b also
            # reaching the Event Log) can't pass just because throttling is
            # broken entirely (#28 review: degradation-path coverage).
            plugin.routeUpdate(device_a, "test_api_key", mock_plugin_paths, plugin_logger)
            assert len(event_log.records) == 1

            plugin.routeUpdate(device_b, "test_api_key", mock_plugin_paths, plugin_logger)

        assert len(event_log.records) == 2

    def test_outage_then_401_is_two_errors_second_names_401(
        self, mock_device, mock_plugin_paths, plugin_logger, event_log
    ):
        """The exact reproduction from the review: a network outage
        transitioning into a 401 both raise WebServiceError (nredarwin uses
        that type for nearly everything), so they must not throttle each
        other -- classify_exception() keys on the embedded HTTP status, not
        the bare exception type.

        Patches plugin._fetch_station_board directly (rather than
        mock_session.get_station_board) -- WebServiceError is one of the
        types darwin_api_retry actually retries, and letting that run for
        real here would mean real tenacity sleep delays for no test value;
        routeUpdate's own handling of the raised exception is what's under
        test, not the retry mechanism."""
        from nredarwin.webservice import WebServiceError

        with patch("plugin.nationalRailLogin", return_value=(True, Mock())):
            with patch("plugin._fetch_station_board", side_effect=WebServiceError(
                "Darwin REST network error: [Errno 8] nodename nor servname "
                "provided, or not known"
            )):
                result = plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)
                assert result is False

            with patch("plugin._fetch_station_board", side_effect=WebServiceError(
                "Darwin REST 401 Unauthorized: invalid key"
            )):
                result = plugin.routeUpdate(mock_device, "test_api_key", mock_plugin_paths, plugin_logger)
                assert result is False

        assert len(event_log.records) == 2
        assert [r.levelno for r in event_log.records] == [logging.ERROR, logging.ERROR]
        assert "401" in event_log.records[1].getMessage()

    def test_broken_event_log_handler_does_not_break_route_update(
        self, mock_device, mock_plugin_paths, tmp_path
    ):
        """A broken indigo_log_handler (its handle() raising) must not stop
        routeUpdate from completing or from writing to the file log --
        _EventLogForwarder.emit() catches the exception and reports it via
        Handler.handleError() rather than letting it propagate up through
        PluginLogger.log_failure() (#28 review)."""
        from mocks.mock_indigo import RecordingHandler

        class RaisingHandler(logging.Handler):
            def handle(self, record):
                raise RuntimeError("Event Log is down")

        plugin_id = f"test-brokeneventlog-{uuid.uuid4().hex}"
        broken_plugin_logger = plugin.PluginLogger(
            plugin_id, tmp_path, debug=True, event_log_handler=RaisingHandler()
        )
        file_log = RecordingHandler()
        broken_plugin_logger.logger.addHandler(file_log)

        mock_session = Mock()
        mock_session.get_station_board.side_effect = Exception("REST request failed")

        with patch("plugin.nationalRailLogin", return_value=(True, mock_session)):
            result = plugin.routeUpdate(
                mock_device, "test_api_key", mock_plugin_paths, broken_plugin_logger,
            )

        assert result is False
        assert any("REST request failed" in r.getMessage() for r in file_log.records)
