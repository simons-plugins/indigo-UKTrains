"""
Unit tests for PluginLogger's WARNING+ -> Indigo Event Log forwarding and
per-device failure throttling (GitHub issue #26).

Background: PluginLogger's own Python logger ("Plugin.<id>") is created
with propagate=False by design, so records never reach the root logger and
caplog's default (root-attached) handler can't see them -- attaching a
recording handler directly to the logger is required. We do that twice:
once standing in for Indigo's real `indigo_log_handler` (the "Event Log
side"), and once attached straight to PluginLogger's internal logger to
observe everything that would land in the file log, independent of the
Event Log forwarding threshold.
"""

import logging
import uuid

import pytest

import plugin


class RecordingHandler(logging.Handler):
    """Stands in for Indigo's self.indigo_log_handler: records everything
    handled instead of writing to a real Event Log."""

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def event_log():
    """Recording handler standing in for indigo_log_handler (the Event Log
    side) -- what PluginLogger forwards WARNING+ records to."""
    return RecordingHandler()


@pytest.fixture
def plugin_logger(tmp_path, event_log):
    # Unique logger name per test: logging.getLogger() caches by name, and
    # while PluginLogger.__init__ clears old handlers each time, a fresh
    # name keeps tests fully independent.
    plugin_id = f"test-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=True, event_log_handler=event_log)


@pytest.fixture
def file_log(plugin_logger):
    """Recording handler attached directly to PluginLogger's internal
    logger -- captures everything that would land in the file log,
    regardless of the Event Log WARNING+ threshold."""
    handler = RecordingHandler()
    plugin_logger.logger.addHandler(handler)
    return handler


class TestLevelForwarding:
    """WARNING/ERROR/exception reach the Event Log; DEBUG/INFO stay
    file-only (the propagate=False intent from issue #26 is preserved)."""

    def test_warning_reaches_event_log(self, plugin_logger, event_log):
        plugin_logger.warning("a warning")

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.WARNING
        assert event_log.records[0].getMessage() == "a warning"

    def test_error_reaches_event_log(self, plugin_logger, event_log):
        plugin_logger.error("an error")

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

    def test_exception_reaches_event_log(self, plugin_logger, event_log):
        try:
            raise ValueError("boom")
        except ValueError:
            plugin_logger.exception("caught it")

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

    def test_debug_does_not_reach_event_log(self, plugin_logger, event_log, file_log):
        plugin_logger.debug("just debug")

        assert event_log.records == []
        # But it's still in the file log (propagate=False never affected that).
        assert len(file_log.records) == 1
        assert file_log.records[0].levelno == logging.DEBUG

    def test_info_does_not_reach_event_log(self, plugin_logger, event_log, file_log):
        plugin_logger.info("just info")

        assert event_log.records == []
        assert len(file_log.records) == 1
        assert file_log.records[0].levelno == logging.INFO

    def test_no_event_log_handler_is_backward_compatible(self, tmp_path):
        # PluginLogger(..., event_log_handler=None) (the old call signature)
        # must not raise, and stays file-only exactly like before #26.
        pl = plugin.PluginLogger("test-no-handler", tmp_path, debug=True)
        pl.warning("still file-only")  # no event log handler configured


class TestFailureThrottling:
    """routeUpdate retries every cycle; log_failure()/log_recovery() keep
    the file log complete while throttling the Event Log to: once per
    distinct failure, and one line on recovery."""

    def test_first_failure_reaches_event_log_as_error(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "image generation failed")

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert event_log.records[0].getMessage() == "image generation failed"

    def test_repeated_identical_failure_suppressed_on_event_log_only(
        self, plugin_logger, event_log, file_log
    ):
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_failure("dev-1", "image generation failed")

        # Event Log: only the first occurrence.
        assert len(event_log.records) == 1

        # File log: every occurrence still lands -- first at ERROR, the
        # throttled repeats downgraded to INFO so they don't re-trip the
        # WARNING+ forwarder.
        assert [r.levelno for r in file_log.records] == [
            logging.ERROR, logging.INFO, logging.INFO,
        ]
        assert all(r.getMessage() == "image generation failed" for r in file_log.records)

    def test_changed_failure_message_is_not_suppressed(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "PIL error in classic image generation")
        plugin_logger.log_failure("dev-1", "File I/O error in classic image generation")

        assert len(event_log.records) == 2
        assert [r.levelno for r in event_log.records] == [logging.ERROR, logging.ERROR]

    def test_different_devices_do_not_throttle_each_other(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_failure("dev-2", "image generation failed")

        assert len(event_log.records) == 2

    def test_recovery_without_prior_failure_is_a_noop(self, plugin_logger, event_log):
        plugin_logger.log_recovery("dev-1", "image generation working again")

        assert event_log.records == []

    def test_recovery_after_failure_emits_one_info_line(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_recovery("dev-1", "image generation working again for 'dev-1'")

        assert len(event_log.records) == 2
        assert event_log.records[0].levelno == logging.ERROR
        assert event_log.records[1].levelno == logging.INFO
        assert event_log.records[1].getMessage() == "image generation working again for 'dev-1'"

    def test_recovery_is_emitted_only_once(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_recovery("dev-1", "image generation working again")
        plugin_logger.log_recovery("dev-1", "image generation working again")

        # Second call has nothing outstanding to clear -- no-op.
        assert len(event_log.records) == 2

    def test_same_failure_resurfaces_after_recovery(self, plugin_logger, event_log):
        plugin_logger.log_failure("dev-1", "image generation failed")
        plugin_logger.log_recovery("dev-1", "image generation working again")
        plugin_logger.log_failure("dev-1", "image generation failed")

        # failure, recovery, then the SAME message recurring: all three
        # reach the Event Log, because recovery cleared the throttle state.
        assert len(event_log.records) == 3
        assert [r.levelno for r in event_log.records] == [
            logging.ERROR, logging.INFO, logging.ERROR,
        ]
