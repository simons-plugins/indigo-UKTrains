"""
Unit tests for the bundled trains.html status page install/update logic
(Plugin._sync_web_page), mirroring the pattern used by indigo-lamplighter.

These build a `Plugin` instance without running `Plugin.__init__` (which does
a lot of unrelated setup: station dictionary, image paths, etc. that these
tests have no need to depend on), then call `_sync_web_page` on it directly.
"""

import logging

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


class TestSyncWebPageIdentical:
    def test_no_write_when_identical(self, install, caplog):
        dest = _dest_path(install)
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"<html>trains v1</html>")
        before_mtime = dest.stat().st_mtime_ns

        fake = FakeSelf({"managePage": True})
        with caplog.at_level(logging.DEBUG, logger=fake.logger.name):
            fake._sync_web_page()

        assert dest.stat().st_mtime_ns == before_mtime
        assert not any("Installed/updated" in r.message for r in caplog.records)


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
