"""
Unit tests for issue #26: an unexpanded '~' in the imageFilename pref was
never passed through Path.expanduser(), so PluginPaths.initialize() and
validatePrefsConfigUi() treated it as a *relative* path. mkdir(parents=True)
then silently created a literal '~' directory under the process's cwd, and
all departure-board .txt/.png output went there instead of the user's home
directory - config validation still passed because its write test hit the
same wrong folder.

These tests build a `Plugin` instance without running `Plugin.__init__`
(same pattern as test_web_page_sync.py), then call validatePrefsConfigUi()
directly, plus test config.PluginPaths.initialize() directly.
"""

from pathlib import Path

import pytest

import config
import indigo
import plugin


def FakeSelf():
    """A real `Plugin` instance built without running `Plugin.__init__`
    (which does a lot of unrelated setup this test has no need for).
    validatePrefsConfigUi() only touches `self.config` via hasattr(), so an
    instance with no attributes set at all is sufficient."""
    return plugin.Plugin.__new__(plugin.Plugin)


def valid_prefs(**overrides):
    prefs = {
        'darwinAPI': 'a_valid_api_key_123',
        'createMaps': True,
        'imageFilename': '/tmp/should-be-overridden',
        'updateFreq': '60',
    }
    prefs.update(overrides)
    return prefs


# ========== config.PluginPaths.initialize ==========

class TestPluginPathsExpandsTilde:
    def test_tilde_expands_to_home_based_absolute_path(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        paths = config.PluginPaths.initialize(
            str(tmp_path / "plugin"), user_image_path="~/Documents/IndigoImages"
        )

        assert paths.image_output_dir == fake_home / "Documents" / "IndigoImages"
        assert paths.image_output_dir.is_absolute()
        assert paths.image_output_dir.exists()

    def test_no_literal_tilde_directory_created_under_cwd(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        fake_cwd = tmp_path / "cwd"
        fake_cwd.mkdir()
        monkeypatch.chdir(fake_cwd)

        config.PluginPaths.initialize(
            str(tmp_path / "plugin"), user_image_path="~/Documents/IndigoImages"
        )

        assert not (fake_cwd / "~").exists()


# ========== plugin.Plugin.validatePrefsConfigUi ==========

@pytest.mark.usefixtures("tmp_path")
class TestValidatePrefsConfigUiImagePath:
    def test_tilde_path_is_expanded_and_saved_as_absolute(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        devProps = indigo.Dict(valid_prefs(imageFilename="~/IndigoImages"))
        ok, result = FakeSelf().validatePrefsConfigUi(devProps)[:2]

        assert ok is True
        assert result['imageFilename'] == str(fake_home / "IndigoImages")
        assert Path(result['imageFilename']).is_absolute()

    def test_no_literal_tilde_directory_created_under_cwd(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        fake_cwd = tmp_path / "cwd"
        fake_cwd.mkdir()
        monkeypatch.chdir(fake_cwd)

        devProps = indigo.Dict(valid_prefs(imageFilename="~/IndigoImages"))
        ok = FakeSelf().validatePrefsConfigUi(devProps)[0]

        assert ok is True
        assert not (fake_cwd / "~").exists()

    def test_relative_path_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        devProps = indigo.Dict(valid_prefs(imageFilename="Images"))
        result = FakeSelf().validatePrefsConfigUi(devProps)

        ok, returned_props, errorDict = result
        assert ok is False
        assert "imageFilename" in errorDict


# ========== plugin.Plugin.validatePrefsConfigUi - update frequency ==========

class TestValidatePrefsConfigUiUpdateFrequency:
    def test_frequency_below_30_seconds_is_rejected(self):
        devProps = indigo.Dict(valid_prefs(updateFreq="10", createMaps=False))
        result = FakeSelf().validatePrefsConfigUi(devProps)

        ok, returned_props, errorDict = result
        assert ok is False
        assert "updateFreq" in errorDict

    def test_frequency_of_30_seconds_is_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        devProps = indigo.Dict(valid_prefs(updateFreq="30", createMaps=False))

        ok = FakeSelf().validatePrefsConfigUi(devProps)[0]

        assert ok is True
