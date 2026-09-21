"""
Unit tests for the bundled trains.html status page install/update logic
(Plugin._sync_web_page, Plugin._warn_if_managed_page_is_stale,
Plugin.closedPrefsConfigUi, and the _truthy helper), mirroring the pattern
used by indigo-lamplighter.

These build a `Plugin` instance without running `Plugin.__init__` (which does
a lot of unrelated setup: station dictionary, image paths, etc. that these
tests have no need to depend on), then call the methods under test directly.
"""

import builtins
import logging
from unittest.mock import Mock

import pytest

import indigo
import plugin


def FakeSelf(prefs=None):
    """A real `Plugin` instance built without running `Plugin.__init__`
    (which does a lot of unrelated setup: station dictionary, image paths,
    etc.), carrying just the attributes `_sync_web_page` and the methods it
    calls actually need."""
    instance = plugin.Plugin.__new__(plugin.Plugin)
    instance.pluginPrefs = prefs or {}
    instance.logger = logging.getLogger("test.uktrains.web_page_sync")
    instance.pluginVersion = "2026.2.0"
    return instance


def _make_install(tmp_path, source_bytes=b"<html>trains v1</html>"):
    """Build an install-folder layout with the bundled page in place."""
    pages_dir = (
        tmp_path / "Plugins" / plugin.WEB_PAGE_BUNDLE_DIR / "Contents"
        / "Resources" / "pages"
    )
    pages_dir.mkdir(parents=True)
    source = pages_dir / plugin.WEB_PAGE_FILENAME
    source.write_bytes(source_bytes)
    return tmp_path


def _source_path(install):
    return (
        install / "Plugins" / plugin.WEB_PAGE_BUNDLE_DIR / "Contents"
        / "Resources" / "pages" / plugin.WEB_PAGE_FILENAME
    )


@pytest.fixture
def install(tmp_path):
    return _make_install(tmp_path)


@pytest.fixture(autouse=True)
def _install_folder(install):
    """Point indigo.server.getInstallFolderPath() at the per-test install dir."""
    indigo.server.getInstallFolderPath.return_value = str(install)
    yield


def _dest_path(install):
    return install / "Web Assets" / "static" / "pages" / plugin.WEB_PAGE_FILENAME


def _no_unexpected_errors(caplog):
    """True if nothing was logged at ERROR+ (i.e. no broad `except Exception`
    handler fired) - used to prove a "fatal" patched call was never reached."""
    return not any(r.levelno >= logging.ERROR for r in caplog.records)


class TestSyncWebPageMissing:
    def test_installs_when_missing(self, install, caplog):
        fake = FakeSelf({"managePage": True})
        dest = _dest_path(install)
        assert not dest.exists()

        with caplog.at_level(logging.INFO, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.exists()
        assert dest.read_bytes() == b"<html>trains v1</html>"
        assert any("Installed/updated" in r.message for r in caplog.records)

    def test_managepage_absent_from_prefs_defaults_to_installed(self, install):
        """No `managePage` key at all (e.g. pre-feature install) must default
        to True, same as _truthy's documented default."""
        dest = _dest_path(install)
        assert not dest.exists()

        fake = FakeSelf({})
        fake._sync_web_page()

        assert dest.exists()
        assert dest.read_bytes() == b"<html>trains v1</html>"


class TestSyncWebPageDiffers:
    def test_overwrites_differing_installed_page(self, install, caplog):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>old installed copy</html>")

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.INFO, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.read_bytes() == b"<html>trains v1</html>"
        assert any(
            "Installed/updated" in r.message and r.levelno == logging.INFO
            for r in caplog.records
        )
        # No leftover temp files in the destination directory.
        leftover = [p for p in dest.parent.iterdir() if p != dest]
        assert leftover == []


class TestSyncWebPageIdentical:
    def test_no_write_when_identical(self, install, caplog, monkeypatch):
        """Identical bundled/installed bytes must short-circuit before any
        write attempt - proven by making the write path itself fatal rather
        than trusting an mtime comparison."""
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>trains v1</html>")

        monkeypatch.setattr(
            plugin.tempfile, "mkstemp",
            Mock(side_effect=AssertionError("must not write: mkstemp called")),
        )
        monkeypatch.setattr(
            plugin.os, "replace",
            Mock(side_effect=AssertionError("must not write: os.replace called")),
        )

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.DEBUG, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.read_bytes() == b"<html>trains v1</html>"
        assert not any("Installed/updated" in r.message for r in caplog.records)
        assert _no_unexpected_errors(caplog)


class TestSyncWebPageEmptyBundled:
    def test_empty_bundled_page_leaves_installed_untouched(self, install, caplog):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>installed good copy</html>")

        _source_path(install).write_bytes(b"")

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.WARNING, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.read_bytes() == b"<html>installed good copy</html>"
        assert any(
            "empty" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )


class TestSyncWebPageBundledMissing:
    def test_pref_on_warns_without_writing(self, install, caplog, monkeypatch):
        _source_path(install).unlink()
        dest = _dest_path(install)

        monkeypatch.setattr(
            plugin.os, "makedirs",
            Mock(side_effect=AssertionError("must not write: os.makedirs called")),
        )
        monkeypatch.setattr(
            plugin.os, "replace",
            Mock(side_effect=AssertionError("must not write: os.replace called")),
        )

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.DEBUG, logger=fake.logger.name):
            fake._sync_web_page()

        assert not dest.exists()
        assert any(
            "not found in the plugin bundle" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )
        assert _no_unexpected_errors(caplog)

    def test_pref_off_logs_info(self, install, caplog):
        _source_path(install).unlink()

        fake = FakeSelf({"managePage": False})
        with caplog.at_level(logging.INFO, logger=fake.logger.name):
            fake._sync_web_page()

        assert any(
            "missing" in r.message and r.levelno == logging.INFO
            for r in caplog.records
        )


class TestSyncWebPageInstallFolderRaises:
    def test_pref_on_warns_without_raising(self, install, caplog, monkeypatch):
        monkeypatch.setattr(
            indigo.server.getInstallFolderPath, "side_effect", RuntimeError("boom")
        )

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.DEBUG, logger=fake.logger.name):
            fake._sync_web_page()  # must not raise

        assert any(
            "Could not determine the Indigo install folder" in r.message
            and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_pref_off_logs_debug_only(self, install, caplog, monkeypatch):
        monkeypatch.setattr(
            indigo.server.getInstallFolderPath, "side_effect", RuntimeError("boom")
        )

        fake = FakeSelf({"managePage": False})
        with caplog.at_level(logging.DEBUG, logger=fake.logger.name):
            fake._sync_web_page()  # must not raise

        assert caplog.records
        assert not any(r.levelno > logging.DEBUG for r in caplog.records)


class TestSyncWebPageInstalledUnreadable:
    def test_unreadable_installed_copy_warns_about_permissions(
        self, install, caplog, monkeypatch
    ):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>old installed copy</html>")

        real_open = builtins.open

        def _raise_on_dest(path, mode="r", *args, **kwargs):
            if str(path) == str(dest) and "b" in mode:
                raise OSError(13, "Permission denied")
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(plugin, "open", _raise_on_dest, raising=False)

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.WARNING, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.read_bytes() == b"<html>old installed copy</html>"
        assert any(
            "could not" in r.message.lower()
            and "read" in r.message.lower()
            and r.levelno == logging.WARNING
            for r in caplog.records
        )
        # Must name the actual reason (permissions), not the generic
        # "could not install" message.
        assert not any(
            "Could not install/update" in r.message for r in caplog.records
        )


class TestSyncWebPageReplaceFails:
    def test_replace_failure_leaves_original_intact_and_cleans_tmp(
        self, install, caplog, monkeypatch
    ):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>original</html>")

        monkeypatch.setattr(
            plugin.os, "replace", Mock(side_effect=OSError("disk full"))
        )

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.WARNING, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.read_bytes() == b"<html>original</html>"
        leftover = [p for p in dest.parent.iterdir() if p != dest]
        assert leftover == []
        assert any(
            "Could not install/update" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )


class TestSyncWebPageUnticked:
    def test_no_write_when_unticked(self, install, caplog):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>an old, hand-edited copy</html>")

        fake = FakeSelf({"managePage": False})
        with caplog.at_level(logging.INFO, logger=fake.logger.name):
            fake._sync_web_page()

        # Installed copy must be left exactly alone.
        assert dest.read_bytes() == b"<html>an old, hand-edited copy</html>"
        assert any(
            "management is off" in r.message for r in caplog.records
        )

    def test_no_write_when_unticked_string_false(self, install):
        """Indigo can hand back the checkbox as the string 'false'."""
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>an old, hand-edited copy</html>")

        fake = FakeSelf({"managePage": "false"})
        fake._sync_web_page()

        assert dest.read_bytes() == b"<html>an old, hand-edited copy</html>"


class TestSyncWebPageUnwritableDestination:
    def test_error_logged_not_raised_when_dest_unwritable(self, install, caplog):
        # Block "Web Assets/static" from ever becoming a directory by
        # putting a plain file there -- os.makedirs then fails reliably,
        # regardless of OS permission bits or which user runs the test.
        web_assets = install / "Web Assets"
        web_assets.mkdir()
        (web_assets / "static").write_bytes(b"not a directory")

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.WARNING, logger=fake.logger.name):
            # Must not raise.
            fake._sync_web_page()

        assert any(
            "Could not install/update" in r.message for r in caplog.records
        )


class TestClosedPrefsConfigUi:
    def test_cancelled_does_not_sync(self):
        fake = FakeSelf({"managePage": True})
        fake._sync_web_page = Mock(
            side_effect=AssertionError("_sync_web_page must not be called on cancel")
        )

        fake.closedPrefsConfigUi({"managePage": True}, True)

        fake._sync_web_page.assert_not_called()

    def test_uses_valuesdict_not_stored_prefs(self, install):
        """Stored pluginPrefs still says managePage=False (not yet updated by
        Indigo); the freshly-saved valuesDict says True. The sync must go by
        valuesDict."""
        dest = _dest_path(install)
        assert not dest.exists()

        fake = FakeSelf({"managePage": False})
        fake.closedPrefsConfigUi({"managePage": True}, False)

        assert dest.exists()
        assert dest.read_bytes() == b"<html>trains v1</html>"

    def test_managepage_absent_from_valuesdict_defaults_to_installed(self, install):
        dest = _dest_path(install)
        assert not dest.exists()

        fake = FakeSelf({"managePage": False})
        fake.closedPrefsConfigUi({}, False)

        assert dest.exists()


class TestTruthy:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("False", False),
            (" no ", False),
            ("0", False),
            ("TRUE", True),
        ],
    )
    def test_string_values(self, value, expected):
        assert plugin._truthy(value) is expected

    def test_none_uses_default(self):
        assert plugin._truthy(None, default=True) is True
        assert plugin._truthy(None, default=False) is False

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, False),
            (1, True),
        ],
    )
    def test_int_values(self, value, expected):
        assert plugin._truthy(value) is expected
