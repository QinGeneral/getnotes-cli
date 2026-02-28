"""Tests for getnotes_cli.settings module"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

import getnotes_cli.settings as settings_module
from getnotes_cli.settings import UserSettings, resolve_output, resolve_delay, resolve_page_size


def make_settings(tmp_path: Path) -> UserSettings:
    """Create a UserSettings instance backed by tmp_path."""
    config_file = tmp_path / "config.json"
    with (
        patch.object(settings_module, "CONFIG_FILE", config_file),
        patch.object(settings_module, "CONFIG_DIR", tmp_path),
    ):
        instance = UserSettings()
    # Keep references so monkeypatching persists during tests
    instance._config_file = config_file
    instance._config_dir = tmp_path
    return instance


class TestUserSettingsGet:
    def test_get_returns_none_when_not_set(self, tmp_path):
        s = make_settings(tmp_path)
        assert s.get("output") is None

    def test_get_returns_value_when_set(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["output"] = "/some/path"
        assert s.get("output") == "/some/path"


class TestUserSettingsAll:
    def test_all_returns_empty_when_no_settings(self, tmp_path):
        s = make_settings(tmp_path)
        assert s.all() == {}

    def test_all_returns_copy_of_data(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["delay"] = 1.0
        d = s.all()
        d["extra"] = "x"
        assert "extra" not in s._data


class TestUserSettingsSet:
    def _set(self, s: UserSettings, tmp_path: Path, key: str, value: str):
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            return s.set(key, value)

    def test_set_output(self, tmp_path):
        s = make_settings(tmp_path)
        result = self._set(s, tmp_path, "output", "/my/output")
        assert result == "/my/output"
        assert s._data["output"] == "/my/output"

    def test_set_delay_converts_to_float(self, tmp_path):
        s = make_settings(tmp_path)
        result = self._set(s, tmp_path, "delay", "1.5")
        assert result == 1.5
        assert isinstance(s._data["delay"], float)

    def test_set_page_size_converts_to_int(self, tmp_path):
        s = make_settings(tmp_path)
        result = self._set(s, tmp_path, "page_size", "50")
        assert result == 50
        assert isinstance(s._data["page_size"], int)

    def test_set_page_size_via_hyphen_key(self, tmp_path):
        s = make_settings(tmp_path)
        result = self._set(s, tmp_path, "page-size", "25")
        assert result == 25
        assert s._data.get("page_size") == 25

    def test_set_invalid_key_raises(self, tmp_path):
        s = make_settings(tmp_path)
        with pytest.raises(KeyError):
            self._set(s, tmp_path, "nonexistent_key", "value")

    def test_set_persists_to_file(self, tmp_path):
        s = make_settings(tmp_path)
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            s.set("output", "/saved")
        assert config_file.exists()
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["output"] == "/saved"


class TestUserSettingsRemove:
    def _remove(self, s: UserSettings, tmp_path: Path, key: str) -> bool:
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            return s.remove(key)

    def test_remove_existing_key_returns_true(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["output"] = "/x"
        assert self._remove(s, tmp_path, "output") is True
        assert "output" not in s._data

    def test_remove_missing_key_returns_false(self, tmp_path):
        s = make_settings(tmp_path)
        assert self._remove(s, tmp_path, "output") is False

    def test_remove_via_hyphen_key(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["page_size"] = 20
        assert self._remove(s, tmp_path, "page-size") is True
        assert "page_size" not in s._data


class TestUserSettingsClear:
    def test_clear_returns_count(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["output"] = "/x"
        s._data["delay"] = 1.0
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            count = s.clear()
        assert count == 2

    def test_clear_empties_data(self, tmp_path):
        s = make_settings(tmp_path)
        s._data["output"] = "/x"
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            s.clear()
        assert s._data == {}

    def test_clear_on_empty_returns_zero(self, tmp_path):
        s = make_settings(tmp_path)
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            assert s.clear() == 0


class TestLoadFromFile:
    def test_loads_existing_config_on_init(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"output": "/loaded", "delay": 2.0}), encoding="utf-8")
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            s = UserSettings()
        assert s.get("output") == "/loaded"
        assert s.get("delay") == 2.0

    def test_loads_empty_when_file_missing(self, tmp_path):
        config_file = tmp_path / "config.json"
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            s = UserSettings()
        assert s.all() == {}

    def test_loads_empty_on_corrupt_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("INVALID", encoding="utf-8")
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            s = UserSettings()
        assert s.all() == {}


class TestResolveFunctions:
    def _mock_settings(self, tmp_path: Path, data: dict):
        """Patch the module-level _settings singleton."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(data), encoding="utf-8")
        with (
            patch.object(settings_module, "CONFIG_FILE", config_file),
            patch.object(settings_module, "CONFIG_DIR", tmp_path),
        ):
            mock_settings = UserSettings()
        return mock_settings

    def test_resolve_output_cli_value_wins(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"output": "/saved"})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_output("/cli", "/default") == "/cli"

    def test_resolve_output_saved_value_over_default(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"output": "/saved"})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_output(None, "/default") == "/saved"

    def test_resolve_output_falls_back_to_default(self, tmp_path):
        mock = self._mock_settings(tmp_path, {})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_output(None, "/default") == "/default"

    def test_resolve_delay_cli_value_wins(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"delay": 2.0})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_delay(0.1, 0.5) == 0.1

    def test_resolve_delay_saved_value(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"delay": 3.0})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_delay(None, 0.5) == 3.0

    def test_resolve_delay_default(self, tmp_path):
        mock = self._mock_settings(tmp_path, {})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_delay(None, 0.5) == 0.5

    def test_resolve_page_size_cli_value_wins(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"page_size": 50})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_page_size(10, 20) == 10

    def test_resolve_page_size_saved_value(self, tmp_path):
        mock = self._mock_settings(tmp_path, {"page_size": 50})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_page_size(None, 20) == 50

    def test_resolve_page_size_default(self, tmp_path):
        mock = self._mock_settings(tmp_path, {})
        with patch.object(settings_module, "_get_settings", return_value=mock):
            assert resolve_page_size(None, 20) == 20
