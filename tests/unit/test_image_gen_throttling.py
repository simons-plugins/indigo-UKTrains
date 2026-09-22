"""
Unit tests for per-cycle image generation failure throttling in
image_generator.py (GitHub issue #28).

Background: a persistently failing device retries image generation every
refresh cycle (default 60s), and each retry previously logged ~3 raw
ERROR lines straight to the Event Log via plain logger.error()/exception()
calls -- spamming the Event Log with a device that simply can't render.
_generate_single_image now routes those through PluginLogger's
log_failure()/clear_failure() so the Event Log gets one ERROR per distinct
failure category (not per raw stderr text, which varies), while the file
log still gets every occurrence.

Same RecordingHandler double-attachment pattern as
test_event_log_forwarding.py: PluginLogger's internal logger has
propagate=False, so caplog's root-attached handler can't see it.
"""

import logging
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import plugin
from image_generator import _generate_single_image


class RecordingHandler(logging.Handler):
    """Stands in for Indigo's self.indigo_log_handler."""

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
    # debug=False: keeps _generate_single_image's own logger.debug() chatter
    # (e.g. "Generating classic image: ...") out of file_log, so file_log
    # assertions below only see the failure/recovery records under test.
    plugin_id = f"test-imagegen-{uuid.uuid4().hex}"
    return plugin.PluginLogger(plugin_id, tmp_path, debug=False, event_log_handler=event_log)


@pytest.fixture
def file_log(plugin_logger):
    handler = RecordingHandler()
    plugin_logger.logger.addHandler(handler)
    return handler


@pytest.fixture
def paths(tmp_path):
    """Just needs to exist -- subprocess.run is mocked, so text2png.py is
    never actually invoked."""
    return SimpleNamespace(
        plugin_root=tmp_path,
        image_filename=tmp_path / "board.png",
        text_filename=tmp_path / "board.txt",
        parameters_filename=tmp_path / "params.txt",
    )


def make_device(dev_id=1, name="Test Device"):
    return SimpleNamespace(id=dev_id, name=name)


def _run_result(returncode, stderr=""):
    return Mock(returncode=returncode, stdout="", stderr=stderr)


@pytest.mark.unit
class TestPersistentFailureThrottling:
    def test_persistent_failure_varying_stderr_single_event_log_error(
        self, plugin_logger, event_log, file_log, paths
    ):
        """Same failure category (PIL error) recurring over 5 cycles with
        different stderr text each time (a real traceback rarely repeats
        verbatim) must still collapse to one Event Log ERROR -- the
        'changed?' comparison is keyed on category, not the raw message."""
        device = make_device()

        with patch("image_generator.subprocess.run") as run_mock:
            for cycle in range(5):
                run_mock.return_value = _run_result(2, stderr=f"Traceback (cycle {cycle})...")
                result = _generate_single_image(
                    paths.plugin_root, paths.image_filename, paths.text_filename,
                    paths.parameters_filename, True, "classic", device, plugin_logger,
                )
                assert result is False

        assert len(event_log.records) == 1
        assert event_log.records[0].levelno == logging.ERROR
        # The one Event Log line still carries the failure reason.
        assert "PIL error" in event_log.records[0].getMessage()

        # File log gets all 5 occurrences: first at ERROR, the rest at INFO.
        assert [r.levelno for r in file_log.records] == [
            logging.ERROR, logging.INFO, logging.INFO, logging.INFO, logging.INFO,
        ]
        # ...and each retains its own (varying) stderr detail.
        assert "cycle 0" in file_log.records[0].getMessage()
        assert "cycle 4" in file_log.records[4].getMessage()

    def test_different_failure_category_is_not_suppressed(
        self, plugin_logger, event_log, paths
    ):
        """A PIL error followed by a File I/O error (different exit code /
        category) must reach the Event Log as a new ERROR, even though
        both are 'the same key' (same device+style)."""
        device = make_device()

        with patch("image_generator.subprocess.run") as run_mock:
            run_mock.return_value = _run_result(2, stderr="font missing")
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, plugin_logger,
            )

            run_mock.return_value = _run_result(1, stderr="disk full")
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, plugin_logger,
            )

        assert len(event_log.records) == 2
        assert [r.levelno for r in event_log.records] == [logging.ERROR, logging.ERROR]
        assert "PIL error" in event_log.records[0].getMessage()
        assert "File I/O error" in event_log.records[1].getMessage()

    def test_success_clears_failure_silently_then_resurfaces_as_new(
        self, plugin_logger, event_log, paths
    ):
        """Success after failure must not itself emit a second Event Log
        line (the device-level recovery line in routeUpdate already covers
        that) -- but it must re-arm the throttle, so the same failure
        category recurring afterwards counts as new again."""
        device = make_device()

        with patch("image_generator.subprocess.run") as run_mock:
            run_mock.return_value = _run_result(2, stderr="font missing")
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, plugin_logger,
            )
            assert len(event_log.records) == 1

            run_mock.return_value = _run_result(0)
            result = _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, plugin_logger,
            )
            assert result is True
            # No recovery line from the per-style clear -- still just the 1.
            assert len(event_log.records) == 1

            run_mock.return_value = _run_result(2, stderr="font missing again")
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, plugin_logger,
            )

        assert len(event_log.records) == 2
        assert [r.levelno for r in event_log.records] == [logging.ERROR, logging.ERROR]

    def test_two_devices_do_not_throttle_each_other(self, plugin_logger, event_log, paths):
        device_a = make_device(dev_id=1, name="Device A")
        device_b = make_device(dev_id=2, name="Device B")

        with patch("image_generator.subprocess.run") as run_mock:
            run_mock.return_value = _run_result(2, stderr="font missing")
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device_a, plugin_logger,
            )
            _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device_b, plugin_logger,
            )

        assert len(event_log.records) == 2

    def test_timeout_and_missing_interpreter_are_throttled_too(
        self, plugin_logger, event_log, paths
    ):
        import subprocess as subprocess_module

        device = make_device()

        with patch("image_generator.subprocess.run") as run_mock:
            run_mock.side_effect = subprocess_module.TimeoutExpired(cmd="text2png.py", timeout=10)
            for _ in range(3):
                result = _generate_single_image(
                    paths.plugin_root, paths.image_filename, paths.text_filename,
                    paths.parameters_filename, True, "classic", device, plugin_logger,
                )
                assert result is False

        assert len(event_log.records) == 1
        assert "timed out" in event_log.records[0].getMessage()

    def test_unthrottled_logger_falls_back_to_plain_error(self, paths):
        """A plain logging.Logger (no log_failure/clear_failure) must fall
        back to the old unthrottled behaviour rather than raising."""
        device = make_device()
        # spec deliberately omits log_failure/clear_failure so hasattr()
        # guards in _generate_single_image fall back to plain .error().
        bare_logger = Mock(spec=["debug", "error"])

        with patch("image_generator.subprocess.run") as run_mock:
            run_mock.return_value = _run_result(2, stderr="font missing")
            result = _generate_single_image(
                paths.plugin_root, paths.image_filename, paths.text_filename,
                paths.parameters_filename, True, "classic", device, bare_logger,
            )

        assert result is False
        assert bare_logger.error.call_count == 1
