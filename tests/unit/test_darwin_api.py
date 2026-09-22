"""
Unit tests for darwin_api.py (GitHub issue #28 review):

  - nationalRailLogin() returns the failure reason as its second element
    (not None) on failure, and no longer prints to stderr.
  - _log_retry_attempt() (the tenacity before_sleep callback) logs at INFO,
    not WARNING -- during a persistent outage this fires on every retry,
    every refresh cycle, and routeUpdate's own throttled log_failure()
    call already surfaces the outage to the Event Log once. Logging it at
    WARNING here would bypass that throttle entirely via PluginLogger's
    WARNING+ -> Event Log forwarder.
"""

import logging
import sys
import uuid
from types import SimpleNamespace

import pytest

import plugin
from darwin_api import nationalRailLogin, MISSING_API_KEY_REASON, _log_retry_attempt
from nredarwin.webservice import WebServiceError


@pytest.mark.unit
class TestNationalRailLoginReason:
    def test_missing_key_reason_is_the_shared_constant(self):
        ok, reason = nationalRailLogin('NO KEY')
        assert ok is False
        assert reason == MISSING_API_KEY_REASON

    def test_blank_key_reason_is_the_shared_constant(self):
        ok, reason = nationalRailLogin('')
        assert ok is False
        assert reason == MISSING_API_KEY_REASON

    def test_web_service_error_reason_carries_original_message(self, monkeypatch):
        def raise_web_service_error(*args, **kwargs):
            raise WebServiceError("Darwin REST 403 Forbidden: bad key")

        monkeypatch.setattr("darwin_api.DarwinLdbSession", raise_web_service_error)

        ok, reason = nationalRailLogin('a_real_looking_key')

        assert ok is False
        assert "403 Forbidden" in reason

    def test_unexpected_error_reason_carries_original_message(self, monkeypatch):
        def raise_runtime_error(*args, **kwargs):
            raise RuntimeError("connection refused")

        monkeypatch.setattr("darwin_api.DarwinLdbSession", raise_runtime_error)

        ok, reason = nationalRailLogin('a_real_looking_key')

        assert ok is False
        assert "connection refused" in reason

    def test_success_returns_the_session(self, monkeypatch):
        sentinel_session = object()
        monkeypatch.setattr("darwin_api.DarwinLdbSession", lambda **kwargs: sentinel_session)

        ok, session = nationalRailLogin('a_real_looking_key')

        assert ok is True
        assert session is sentinel_session


@pytest.mark.unit
class TestRetryAttemptLogging:
    def test_retry_attempt_is_info_not_warning(self, tmp_path, event_log, monkeypatch):
        from mocks.mock_indigo import RecordingHandler

        plugin_id = f"test-retrylog-{uuid.uuid4().hex}"
        plugin_logger = plugin.PluginLogger(
            plugin_id, tmp_path, debug=True, event_log_handler=event_log
        )
        file_log = RecordingHandler()
        plugin_logger.logger.addHandler(file_log)
        fake_plugin = SimpleNamespace(plugin_logger=plugin_logger)
        monkeypatch.setitem(sys.modules, '__main__', SimpleNamespace(plugin=fake_plugin))

        retry_state = SimpleNamespace(
            attempt_number=2, next_action=SimpleNamespace(sleep=1.5)
        )
        _log_retry_attempt(retry_state)

        # INFO stays file-only via PluginLogger's WARNING+ Event Log
        # forwarder -- a retry callback must never itself reach the Event
        # Log, however many times it fires in a cycle.
        assert event_log.records == []
        assert len(file_log.records) == 1
        assert file_log.records[0].levelno == logging.INFO

    def test_first_attempt_does_not_log(self, tmp_path, event_log, monkeypatch):
        from mocks.mock_indigo import RecordingHandler

        plugin_id = f"test-retrylog-first-{uuid.uuid4().hex}"
        plugin_logger = plugin.PluginLogger(
            plugin_id, tmp_path, debug=True, event_log_handler=event_log
        )
        file_log = RecordingHandler()
        plugin_logger.logger.addHandler(file_log)
        fake_plugin = SimpleNamespace(plugin_logger=plugin_logger)
        monkeypatch.setitem(sys.modules, '__main__', SimpleNamespace(plugin=fake_plugin))

        retry_state = SimpleNamespace(
            attempt_number=1, next_action=SimpleNamespace(sleep=1.0)
        )
        _log_retry_attempt(retry_state)

        assert event_log.records == []
        assert file_log.records == []
