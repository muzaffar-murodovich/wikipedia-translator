"""Tests for utils/localization.py."""

import json

import pytest

from utils.localization import LocalizationManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """A LocalizationManager over a small, known map."""
    data = {
        "[[Category:": "[[Turkum:",
        "== References ==": "== Manbalar ==",
        "== See also ==": "== Yana qarang ==",
    }
    path = tmp_path / "localization_map.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("config.LOCALIZATION_FILE", path)
    return LocalizationManager()


class TestApply:
    def test_replaces_every_occurrence(self, manager):
        result = manager.apply("[[Category:A]] [[Category:B]]")
        assert result == "[[Turkum:A]] [[Turkum:B]]"

    def test_counts_each_replacement_not_each_call(self, manager):
        manager.apply("[[Category:A]] == References == [[Category:B]]")
        assert manager.stats["replacements"] == 3

    def test_counts_accumulate_across_calls(self, manager):
        manager.apply("[[Category:A]]")
        manager.apply("[[Category:B]] == See also ==")
        assert manager.stats["replacements"] == 3

    def test_no_match_leaves_the_count_at_zero(self, manager):
        manager.apply("hech qanday moslik yoʻq")
        assert manager.stats["replacements"] == 0

    def test_text_without_matches_is_unchanged(self, manager):
        assert manager.apply("oddiy matn") == "oddiy matn"

    def test_patterns_count_reports_the_map_size(self, manager):
        assert manager.stats["patterns_count"] == 3


class TestMissingMap:
    def test_missing_file_leaves_the_map_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.LOCALIZATION_FILE", tmp_path / "absent.json")
        assert LocalizationManager().map == {}

    def test_missing_file_is_reported(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr("config.LOCALIZATION_FILE", tmp_path / "absent.json")
        LocalizationManager()
        assert "Localization map yuklanmadi" in caplog.text

    def test_missing_file_does_not_get_a_stub_written_over_it(self, tmp_path, monkeypatch):
        """It used to write a ten-entry default map, which would clobber the
        real 223-rule file whenever it could not be read."""
        target = tmp_path / "absent.json"
        monkeypatch.setattr("config.LOCALIZATION_FILE", target)
        LocalizationManager()
        assert not target.exists()

    def test_apply_is_a_no_op_without_a_map(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.LOCALIZATION_FILE", tmp_path / "absent.json")
        manager = LocalizationManager()
        assert manager.apply("[[Category:X]]") == "[[Category:X]]"
