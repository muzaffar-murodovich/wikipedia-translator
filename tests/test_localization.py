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
