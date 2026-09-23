"""
Unit tests for calling-points failure throttling in device_manager.py
(GitHub issue #30, follow-up to #23).

Background: _build_calling_points_string() used to report failures through
a module-level, stderr-only placeholder errorHandler() that reached no log
at all when called from device_manager's own module context (only
plugin.py's errorHandler, which it never called, could reach the Event
Log). It's now threaded the real PluginLogger through, and routes SOAP
calling-points failures through log_failure()/log_recovery() -- throttled
the same way as darwin_fetch/darwin_login/image_gen (#28), since a
persistent calling-points problem retries every refresh cycle. The "NULL
estimated time" case is explicitly non-critical and stays file-only at
DEBUG, never a throttled failure.

Same RecordingHandler double-attachment pattern as
test_event_log_forwarding.py / test_image_gen_throttling.py: PluginLogger's
internal logger has propagate=False, so caplog's root-attached handler
can't see it.
"""

import logging
import uuid
from types import SimpleNamespace

import pytest

import plugin
from device_manager import _build_calling_points_string
from mocks.mock_indigo import RecordingHandler


@pytest.fixture
def plugin_logger(tmp_path, event_log):
    plugin_id = f"test-callingpoints-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=True, event_log_handler=event_log)


@pytest.fixture
def file_log(plugin_logger):
    handler = RecordingHandler()
    plugin_logger.logger.addHandler(handler)
    return handler


def make_device(dev_id=1, name="Test Device"):
    return SimpleNamespace(id=dev_id, name=name)


def make_calling_point(location_name, st="10:00", et="On time"):
    return SimpleNamespace(location_name=location_name, st=st, et=et)


@pytest.mark.unit
class TestSoapAccessFailureThrottling:
    """Line ~118 (was): an AttributeError while reading
    subsequent_calling_points/st/et -- retried every refresh cycle, so it's
    throttled per device like darwin_fetch/darwin_login (#28-style)."""

    def test_first_failure_reaches_event_log_as_error(self, plugin_logger, event_log, file_log):
        device = make_device()
        # object() has neither .location_name nor .st/.et -- the list
        # comprehensions inside the outer try raise AttributeError.
        service = SimpleNamespace(subsequent_calling_points=[object()])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == ''
        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "Calling Points" in event_log.records[0].getMessage()

    def test_repeated_failure_is_suppressed_on_event_log_but_not_file_log(
        self, plugin_logger, event_log, file_log
    ):
        device = make_device()
        service = SimpleNamespace(subsequent_calling_points=[object()])

        for _ in range(3):
            _build_calling_points_string(service, device, plugin_logger)

        assert len(event_log.records) == 1
        assert [r.levelno for r in file_log.records] == [
            logging.ERROR, logging.INFO, logging.INFO,
        ]

    def test_two_devices_do_not_throttle_each_other(self, plugin_logger, event_log):
        service = SimpleNamespace(subsequent_calling_points=[object()])

        _build_calling_points_string(service, make_device(dev_id=1), plugin_logger)
        _build_calling_points_string(service, make_device(dev_id=2), plugin_logger)

        assert len(event_log.records) == 2


@pytest.mark.unit
class TestNullEstimatedTimeIsNonCritical:
    """Line ~129 (was): a calling point missing its estimated/arrival time
    is expected Darwin behaviour, not a failure -- DEBUG/file-only, never
    reaches the Event Log (#30)."""

    def test_debug_only_nothing_at_warning_or_above(self, plugin_logger, event_log, file_log):
        device = make_device()

        # A generator (rather than a list) for subsequent_calling_points:
        # _build_calling_points_string iterates it three times to build
        # calling_points/arrival_times/estimated_times, so the 2nd and 3rd
        # passes come back empty once the generator is exhausted --
        # reproducing Darwin handing back a calling point whose arrival/
        # estimated time can't be read for that index (IndexError).
        def points():
            yield make_calling_point("Slough")
            yield make_calling_point("Reading")

        service = SimpleNamespace(subsequent_calling_points=points())

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == ''
        assert event_log.records == []
        assert all(r.levelno < logging.WARNING for r in file_log.records)
        debug_records = [r for r in file_log.records if "not critical" in r.getMessage()]
        assert len(debug_records) == 2
        assert all(r.levelno == logging.DEBUG for r in debug_records)

    def test_success_with_no_prior_failure_emits_no_recovery_line(
        self, plugin_logger, event_log
    ):
        """log_recovery() is a no-op unless something was actually
        outstanding for this device's key -- nothing to recover here."""
        device = make_device()

        def points():
            yield make_calling_point("Slough")

        service = SimpleNamespace(subsequent_calling_points=points())
        _build_calling_points_string(service, device, plugin_logger)

        assert event_log.records == []


@pytest.mark.unit
class TestUnknownErrorPerCallingPoint:
    """Line ~131 (was): an unexpected exception building one calling
    point's text (e.g. a None arrival time on a service reporting 'On
    time') is a real failure -- throttled like the SOAP-access case, not
    silently swallowed."""

    def test_unknown_error_reaches_event_log_and_other_points_still_render(
        self, plugin_logger, event_log
    ):
        device = make_device()
        broken = make_calling_point("Slough", st=None, et="On time")
        ok = make_calling_point("Reading", st="10:15", et="On time")
        service = SimpleNamespace(subsequent_calling_points=[broken, ok])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        assert "unknown error" in event_log.records[0].getMessage()
        # The broken calling point contributed nothing, but the good one
        # still made it into the string.
        assert "Slough" not in result
        assert "Reading(10:15)" in result


@pytest.mark.unit
class TestRecovery:
    def test_recovery_after_failure_emits_one_info_line(self, plugin_logger, event_log):
        device = make_device()
        failing_service = SimpleNamespace(subsequent_calling_points=[object()])
        _build_calling_points_string(failing_service, device, plugin_logger)
        assert len(event_log.records) == 1

        ok_service = SimpleNamespace(subsequent_calling_points=[make_calling_point("Reading", st="10:15")])
        _build_calling_points_string(ok_service, device, plugin_logger)

        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "working again" in event_log.records[1].getMessage()

        # Re-arms the throttle: the same failure recurring afterwards
        # reaches the Event Log as new again.
        _build_calling_points_string(failing_service, device, plugin_logger)
        assert len(event_log.records) == 3
        assert event_log.records[2].levelno == logging.ERROR
