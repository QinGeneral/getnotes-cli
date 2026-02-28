"""Tests for getnotes_cli.cache module"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from getnotes_cli.cache import CacheManager


def make_manager(tmp_path: Path) -> CacheManager:
    """Create a CacheManager using tmp_path for both output and config dirs."""
    manager = CacheManager(output_dir=tmp_path)
    # Point cache_path to a temp location so we don't touch ~/.getnotes-cli
    manager.cache_path = tmp_path / "cache_manifest.json"
    return manager


class TestCacheManagerIsCached:
    def test_not_cached_when_empty(self, tmp_path):
        mgr = make_manager(tmp_path)
        note = {"note_id": "n1", "version": 1, "updated_at": "2024-01-01"}
        assert not mgr.is_cached(note)

    def test_cached_when_version_and_updated_at_match(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr._manifest["n1"] = {"version": 2, "updated_at": "2024-01-02"}
        note = {"note_id": "n1", "version": 2, "updated_at": "2024-01-02"}
        assert mgr.is_cached(note)

    def test_not_cached_when_version_differs(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr._manifest["n1"] = {"version": 1, "updated_at": "2024-01-02"}
        note = {"note_id": "n1", "version": 2, "updated_at": "2024-01-02"}
        assert not mgr.is_cached(note)

    def test_not_cached_when_updated_at_differs(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr._manifest["n1"] = {"version": 1, "updated_at": "2024-01-01"}
        note = {"note_id": "n1", "version": 1, "updated_at": "2024-01-02"}
        assert not mgr.is_cached(note)

    def test_uses_id_field_as_fallback(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr._manifest["n2"] = {"version": 1, "updated_at": "2024-01-01"}
        note = {"id": "n2", "version": 1, "updated_at": "2024-01-01"}
        assert mgr.is_cached(note)


class TestCacheManagerUpdateAndGet:
    def test_update_stores_info(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("n1", {"title": "Hello", "version": 1})
        assert mgr.get("n1") == {"title": "Hello", "version": 1}

    def test_get_returns_none_for_missing(self, tmp_path):
        mgr = make_manager(tmp_path)
        assert mgr.get("nonexistent") is None

    def test_update_overwrites_existing(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("n1", {"version": 1})
        mgr.update("n1", {"version": 2})
        assert mgr.get("n1")["version"] == 2


class TestCacheManagerCountAndManifest:
    def test_count_empty(self, tmp_path):
        mgr = make_manager(tmp_path)
        assert mgr.count == 0

    def test_count_after_updates(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("a", {})
        mgr.update("b", {})
        assert mgr.count == 2

    def test_manifest_returns_internal_dict(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("x", {"v": 1})
        m = mgr.manifest
        assert m is mgr._manifest  # manifest returns the internal dict directly
        assert "x" in m


class TestCacheManagerLoadSave:
    def test_load_returns_empty_when_no_file(self, tmp_path):
        mgr = make_manager(tmp_path)
        result = mgr.load()
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("n1", {"title": "Test", "version": 3})
        mgr.save()

        mgr2 = make_manager(tmp_path)
        loaded = mgr2.load()
        assert loaded["n1"]["title"] == "Test"

    def test_load_returns_empty_on_corrupt_json(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.cache_path.write_text("!!!corrupt!!!", encoding="utf-8")
        result = mgr.load()
        assert result == {}


class TestCacheManagerCheck:
    def test_check_when_no_cache_file(self, tmp_path):
        mgr = make_manager(tmp_path)
        result = mgr.check()
        assert result["exists"] is False
        assert result["count"] == 0

    def test_check_when_cache_exists(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("n1", {"title": "Note", "created_at": "2024-01-01", "folder_name": "folder1"})
        mgr.save()

        mgr2 = make_manager(tmp_path)
        result = mgr2.check()
        assert result["exists"] is True
        assert result["count"] == 1
        assert "n1" in result["notes"]
        assert result["notes"]["n1"]["title"] == "Note"


class TestCacheManagerRebuildFromDisk:
    def test_rebuild_zero_when_notes_dir_missing(self, tmp_path):
        mgr = make_manager(tmp_path)
        count = mgr.rebuild_from_disk(tmp_path / "notes")
        assert count == 0

    def test_rebuild_from_valid_note_json(self, tmp_path):
        notes_dir = tmp_path / "notes"
        folder = notes_dir / "20240101_note1"
        folder.mkdir(parents=True)
        note_data = {
            "note_id": "n1",
            "version": 1,
            "updated_at": "2024-01-01",
            "title": "Rebuilt Note",
            "created_at": "2024-01-01",
        }
        (folder / "note.json").write_text(json.dumps(note_data), encoding="utf-8")

        mgr = make_manager(tmp_path)
        count = mgr.rebuild_from_disk(notes_dir)
        assert count == 1
        assert mgr.get("n1") is not None
        assert mgr.get("n1")["title"] == "Rebuilt Note"

    def test_rebuild_skips_existing_entries(self, tmp_path):
        notes_dir = tmp_path / "notes"
        folder = notes_dir / "20240101_note1"
        folder.mkdir(parents=True)
        note_data = {"note_id": "n1", "title": "New", "version": 2, "updated_at": "now"}
        (folder / "note.json").write_text(json.dumps(note_data), encoding="utf-8")

        mgr = make_manager(tmp_path)
        mgr.update("n1", {"title": "Old", "version": 1})
        count = mgr.rebuild_from_disk(notes_dir)
        # Should skip existing entry
        assert count == 0
        assert mgr.get("n1")["title"] == "Old"

    def test_rebuild_skips_folders_without_note_json(self, tmp_path):
        notes_dir = tmp_path / "notes"
        folder = notes_dir / "empty_folder"
        folder.mkdir(parents=True)

        mgr = make_manager(tmp_path)
        count = mgr.rebuild_from_disk(notes_dir)
        assert count == 0

    def test_rebuild_skips_missing_note_id(self, tmp_path):
        notes_dir = tmp_path / "notes"
        folder = notes_dir / "no_id"
        folder.mkdir(parents=True)
        (folder / "note.json").write_text(json.dumps({"title": "No ID"}), encoding="utf-8")

        mgr = make_manager(tmp_path)
        count = mgr.rebuild_from_disk(notes_dir)
        assert count == 0

    def test_rebuild_saves_manifest(self, tmp_path):
        notes_dir = tmp_path / "notes"
        folder = notes_dir / "n1_folder"
        folder.mkdir(parents=True)
        (folder / "note.json").write_text(
            json.dumps({"note_id": "n1", "title": "T", "version": 1, "updated_at": "x"}),
            encoding="utf-8",
        )
        mgr = make_manager(tmp_path)
        mgr.rebuild_from_disk(notes_dir)
        assert mgr.cache_path.exists()


class TestCacheManagerClear:
    def test_clear_returns_zero_when_no_file(self, tmp_path):
        mgr = make_manager(tmp_path)
        assert mgr.clear() == 0

    def test_clear_removes_file_and_returns_count(self, tmp_path):
        mgr = make_manager(tmp_path)
        mgr.update("n1", {})
        mgr.update("n2", {})
        mgr.save()

        count = mgr.clear()
        assert count == 2
        assert not mgr.cache_path.exists()
        assert mgr.count == 0
