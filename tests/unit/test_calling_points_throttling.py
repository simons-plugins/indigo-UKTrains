"""
Unit tests for calling-points failure throttling in device_manager.py
(GitHub issue #30, follow-up to #23).

Background: _build_calling_points_string() used to report failures through
a module-level, stderr-only placeholder errorHandler() that reached no log
at all when called from device_manager's own module context (only
plugin.py's errorHandler, which it never called, could reach the Event
Log). It's now threaded the real PluginLogger through, and routes SOAP
calling-points failures through log_failure() -- throttled the same way as
darwin_fetch/darwin_login/image_gen (#28), since a persistent
calling-points problem retries every refresh cycle. The "NULL estimated
time" case is explicitly non-critical and stays file-only at DEBUG, never
a throttled failure.

Follow-up (#31): _build_calling_points_string() no longer decides
recovery itself -- it's called twice per train per cycle (once for the
device-state pass, once for the image pass) and once per train across up
to MAX_TRAINS_TRACKED trains, so a single clean call recovering the
device's failure state would let one good train's pass wipe out the
failure a broken train elsewhere in the SAME cycle just set, and the next
cycle would log a fresh ERROR for the same underlying problem: an
ERROR/INFO flap every cycle, forever. Recovery is now decided once per
device per cycle by _process_train_services(), after it has seen every
train and both passes -- see TestRecoveryScopedToWholeCycle below.

Follow-up (#35, #36): a calling point cancelled at that location carries
Darwin's per-point `isCancelled` flag and is now rendered as Name(Cancelled)
rather than as a normal stop with its scheduled/estimated time. The per-point
loop also now reads one list of per-point tuples, so the old
(AttributeError, IndexError) branch -- unreachable with list-backed data,
and wrongly documented as the "no estimated time" handler -- was removed;
the catch-all is the only per-point handler.

Same RecordingHandler double-attachment pattern as
test_event_log_forwarding.py / test_image_gen_throttling.py: PluginLogger's
internal logger has propagate=False, so caplog's root-attached handler
can't see it.
"""

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import plugin
from device_manager import _build_calling_points_string, _process_train_services
from mocks.mock_darwin import calling_point_dict
from mocks.mock_indigo import RecordingHandler, create_mock_device
from nredarwin.webservice import CallingPoint


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


def make_calling_point(location_name, st="10:00", et="On time", at=None, is_cancelled=False):
    return SimpleNamespace(
        location_name=location_name, st=st, et=et, at=at, is_cancelled=is_cancelled
    )


@pytest.mark.unit
class TestSoapAccessFailureThrottling:
    """Line ~118 (was): an AttributeError while reading
    subsequent_calling_points/st/et -- retried every refresh cycle, so it's
    throttled per device like darwin_fetch/darwin_login (#28-style)."""

    def test_first_failure_reaches_event_log_as_error(self, plugin_logger, event_log, file_log):
        device = make_device()
        # object() has neither .location_name nor .st/.et -- the per-point
        # comprehension inside the outer try raises AttributeError.
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
class TestSinglePassIteration:
    """The function reads each calling point once, so a one-shot iterable
    (generator) is fine. The old (AttributeError, IndexError) per-point
    branch was unreachable with list-backed data and has been removed
    (#36); a missing estimated time is handled by falling back to `at`
    then the scheduled time, see TestNullEstimatedTimeRendersScheduledTime."""

    def test_generator_source_renders_every_point(self, plugin_logger, event_log, file_log):
        device = make_device()

        def points():
            yield make_calling_point("Slough", st="10:00")
            yield make_calling_point("Reading", st="10:15")

        service = SimpleNamespace(subsequent_calling_points=points())

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Slough(10:00) Reading(10:15) "
        assert event_log.records == []
        assert all(r.levelno < logging.WARNING for r in file_log.records)

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
class TestNullEstimatedTimeRendersScheduledTime:
    """Once a service has called at a point, Darwin drops `et` and sends
    `at` instead (same shape: 'On time' or an HH:MM actual), so the
    JSON-backed CallingPoint.et reads None for the first stops of a train
    that has just left the board station. Captured live 2026-11-02 20:49
    on Walton-Waterloo: Hersham st='20:49', no `et`, at='On time',
    isCancelled=False. `'On' in None` raised TypeError, which only the
    catch-all saw -- so every departing train produced "Estimated Time
    for calling point - unknown error ... argument of type 'NoneType' is
    not iterable - advise developer" in the Event Log. It is expected
    data, not a failure: use `at` as the estimate, log nothing."""

    def test_none_et_with_on_time_at_renders_scheduled_time_and_logs_nothing(
        self, plugin_logger, event_log, file_log
    ):
        device = make_device()
        passed = make_calling_point("Hersham", st="20:49", et=None, at="On time")
        ok = make_calling_point("Esher", st="20:52", et="On time")
        service = SimpleNamespace(subsequent_calling_points=[passed, ok])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Hersham(20:49) Esher(20:52) "
        assert event_log.records == []
        assert all(r.levelno < logging.WARNING for r in file_log.records)

    def test_none_et_with_late_at_renders_the_actual_time(self, plugin_logger, event_log):
        """A late actual is the better answer than the scheduled time."""
        device = make_device()
        passed = make_calling_point("Hersham", st="20:49", et=None, at="20:53")
        service = SimpleNamespace(subsequent_calling_points=[passed])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Hersham(20:53) "
        assert event_log.records == []

    def test_none_et_and_none_at_falls_back_to_scheduled_time(self, plugin_logger, event_log):
        device = make_device()
        service = SimpleNamespace(
            subsequent_calling_points=[make_calling_point("Surbiton", st="10:05", et=None)]
        )

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Surbiton(10:05) "
        assert event_log.records == []

    def test_none_et_and_none_st_is_still_reported_as_a_failure(
        self, plugin_logger, event_log
    ):
        """Adversarial guard: making `et` None benign must not swallow a
        calling point with no time at all -- that is still a real failure."""
        device = make_device()
        service = SimpleNamespace(
            subsequent_calling_points=[make_calling_point("Surbiton", st=None, et=None)]
        )
        sink = []

        result = _build_calling_points_string(service, device, plugin_logger, failure_sink=sink)

        assert result == ''
        assert sink == [True]
        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR

    def test_none_et_is_not_reported_as_a_failure_to_the_caller(
        self, plugin_logger, event_log
    ):
        """A None `et` must not feed the per-cycle failure aggregation
        either, or _process_train_services would never log recovery."""
        device = make_device()
        service = SimpleNamespace(
            subsequent_calling_points=[make_calling_point("Surbiton", st="10:05", et=None)]
        )
        sink = []

        _build_calling_points_string(service, device, plugin_logger, failure_sink=sink)

        assert sink == []


@pytest.mark.unit
class TestCancelledCallingPointRendersCancelled:
    """GitHub issue #35: Darwin flags a stop the train will skip with a
    per-point `isCancelled`. CallingPoint never exposed it, so the stop
    rendered with its scheduled/estimated time as if it were a normal
    call. It must render as Name(Cancelled), ahead of et/at/st."""

    def test_cancelled_point_with_no_et_renders_cancelled_not_scheduled_time(
        self, plugin_logger, event_log, file_log
    ):
        device = make_device()
        cancelled = make_calling_point("Surbiton", st="10:05", et=None, at=None, is_cancelled=True)
        ok = make_calling_point("Reading", st="10:15", et="On time")
        service = SimpleNamespace(subsequent_calling_points=[cancelled, ok])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Surbiton(Cancelled) Reading(10:15) "
        assert event_log.records == []
        assert all(r.levelno < logging.WARNING for r in file_log.records)

    def test_cancelled_point_wins_over_et_and_at(self, plugin_logger):
        device = make_device()
        with_et = make_calling_point("Surbiton", st="10:05", et="10:09", at=None, is_cancelled=True)
        with_at = make_calling_point("Surbiton", st="10:05", et=None, at="10:09", is_cancelled=True)

        assert _build_calling_points_string(
            SimpleNamespace(subsequent_calling_points=[with_et]), device, plugin_logger
        ) == "Surbiton(Cancelled) "
        assert _build_calling_points_string(
            SimpleNamespace(subsequent_calling_points=[with_at]), device, plugin_logger
        ) == "Surbiton(Cancelled) "

    def test_cancelled_point_is_not_reported_as_a_failure(self, plugin_logger, event_log):
        device = make_device()
        service = SimpleNamespace(subsequent_calling_points=[
            make_calling_point("Surbiton", st="10:05", et=None, is_cancelled=True)
        ])
        sink = []

        _build_calling_points_string(service, device, plugin_logger, failure_sink=sink)

        assert sink == []
        assert event_log.records == []

    def test_real_calling_point_from_darwin_json(self, plugin_logger, event_log):
        """Pins the real JSON wrapper, with the `et` key absent."""
        device = make_device()
        service = SimpleNamespace(subsequent_calling_points=[
            CallingPoint(calling_point_dict("Surbiton", "10:05", et=None, is_cancelled=True)),
            CallingPoint(calling_point_dict("Reading", "10:15")),
        ])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Surbiton(Cancelled) Reading(10:15) "
        assert event_log.records == []

    def test_real_calling_point_with_et_absent_and_at_present(self, plugin_logger, event_log):
        """The payload captured live 2026-11-02: no `et`, at='On time'."""
        device = make_device()
        raw = calling_point_dict("Hersham", "20:49", et=None)
        raw["at"] = "On time"
        service = SimpleNamespace(subsequent_calling_points=[CallingPoint(raw)])

        result = _build_calling_points_string(service, device, plugin_logger)

        assert result == "Hersham(20:49) "
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
        message = event_log.records[0].getMessage()
        assert "unknown error" in message
        # The message must say which stop failed and what it carried, or the
        # next "argument of type 'NoneType'" report is undiagnosable (#34).
        assert "'Slough'" in message
        assert "st=None" in message
        # The broken calling point contributed nothing, but the good one
        # still made it into the string.
        assert "Slough" not in result
        assert "Reading(10:15)" in result


@pytest.mark.unit
class TestRecovery:
    def test_success_after_failure_does_not_auto_recover(self, plugin_logger, event_log):
        """Recovery moved out of this function (#31): _build_calling_points_
        string() is called twice per train per cycle and once per train
        across a whole board, so a single clean call must not clear the
        device's failure state by itself -- only the whole-cycle caller
        (_process_train_services) decides that now. See
        TestRecoveryScopedToWholeCycle for the aggregate behaviour."""
        device = make_device()
        failing_service = SimpleNamespace(subsequent_calling_points=[object()])
        _build_calling_points_string(failing_service, device, plugin_logger)
        assert len(event_log.records) == 1

        ok_service = SimpleNamespace(subsequent_calling_points=[make_calling_point("Reading", st="10:15")])
        _build_calling_points_string(ok_service, device, plugin_logger)

        # No "working again" line -- this function never calls
        # log_recovery() any more, so the failure state is untouched.
        assert len(event_log.records) == 1

        # The failure is still outstanding, so an explicit log_recovery()
        # call (what _process_train_services now does once per cycle)
        # still clears it and emits the one INFO line.
        plugin_logger.log_recovery(
            f"calling_points:{device.id}", f"Calling points working again for '{device.name}'"
        )
        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "working again" in event_log.records[1].getMessage()

        # Re-arms the throttle: the same failure recurring afterwards
        # reaches the Event Log as new again.
        _build_calling_points_string(failing_service, device, plugin_logger)
        assert len(event_log.records) == 3
        assert event_log.records[2].levelno == logging.ERROR


def make_train(destination_text, std, subsequent_calling_points, etd="On time",
                operator_name="Great Western Railway", operator_code="GW", platform="1"):
    """A minimal object serving as both the `destination` (ServiceItem)
    and the `service` passed into _process_train_services -- matches the
    production flow, where GetDepBoardWithDetails returns calling points
    inline on the same object (no second API call, see device_manager.py
    _process_train_services docstring)."""
    return SimpleNamespace(
        destination_text=destination_text,
        std=std,
        etd=etd,
        operator_name=operator_name,
        operator_code=operator_code,
        platform=platform,
        subsequent_calling_points=subsequent_calling_points,
    )


def make_board(services):
    return SimpleNamespace(train_services=services)


@pytest.mark.unit
class TestRecoveryScopedToWholeCycle:
    """GitHub issue #31: recovery must be decided once per device per cycle
    in _process_train_services(), not per _build_calling_points_string()
    call. Before the fix, a clean train's pass (device-state or image)
    called log_recovery() and cleared the device's failure state even
    while another train on the SAME cycle was persistently broken -- so
    the next cycle's broken train logged a fresh ERROR, forever:
    ERROR/INFO flap every cycle, the exact spam #30 set out to stop.
    """

    def test_persistent_failure_alongside_a_good_train_flaps_only_once(
        self, plugin_logger, event_log, file_log
    ):
        device = create_mock_device(device_id=1, name="Test Device")
        # object() has no .location_name -- raises AttributeError inside
        # _build_calling_points_string, same as the throttling tests above.
        broken = make_train("Oxford", "10:00", subsequent_calling_points=[object()])
        good = make_train(
            "Reading", "10:05",
            subsequent_calling_points=[make_calling_point("Slough", st="10:10")],
        )
        board = make_board([broken, good])

        for _ in range(2):  # two refresh cycles
            _process_train_services(
                device, None, board, [], include_calling_points=True, logger=plugin_logger
            )

        # One ERROR total across both cycles -- not one per cycle.
        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        # The failure never actually cleared, so no "working again" line
        # ever reaches the Event Log.
        assert not any("working again" in r.getMessage() for r in event_log.records)

        # The file log still records every occurrence: 2 calls
        # (device-state pass + image pass) from the broken train per
        # cycle, across 2 cycles.
        assert [r.levelno for r in file_log.records] == [
            logging.ERROR, logging.INFO, logging.INFO, logging.INFO,
        ]

    def test_all_good_after_a_failing_cycle_recovers_exactly_once(
        self, plugin_logger, event_log
    ):
        device = create_mock_device(device_id=1, name="Test Device")
        broken = make_train("Oxford", "10:00", subsequent_calling_points=[object()])
        board_failing = make_board([broken])

        _process_train_services(
            device, None, board_failing, [], include_calling_points=True, logger=plugin_logger
        )
        assert len(event_log.records) == 1  # precondition: outstanding failure

        # Spy on log_recovery() itself so a would-be per-train call (masked
        # externally by log_recovery's own no-op-after-first-clear
        # behaviour) still shows up as a bug here.
        recovery_spy = MagicMock(side_effect=plugin_logger.log_recovery)
        plugin_logger.log_recovery = recovery_spy

        good_trains = [
            make_train("Reading", "10:05", subsequent_calling_points=[make_calling_point("Slough", st="10:10")]),
            make_train("Didcot", "10:15", subsequent_calling_points=[make_calling_point("Slough", st="10:20")]),
            make_train("Swindon", "10:25", subsequent_calling_points=[make_calling_point("Slough", st="10:30")]),
        ]
        board_ok = make_board(good_trains)

        _process_train_services(
            device, None, board_ok, [], include_calling_points=True, logger=plugin_logger
        )

        assert recovery_spy.call_count == 1
        assert len(event_log.records) == 2
        assert event_log.records[1].levelno == logging.INFO
        assert "working again" in event_log.records[1].getMessage()
