"""Tests for core/processor.py — the parts that need no network."""

from unittest.mock import MagicMock

import pytest

from core.processor import WikiTextProcessor


@pytest.fixture
def processor():
    return WikiTextProcessor(MagicMock(), MagicMock())


REF_MAP = {
    "a1b2c3d4": "<ref>Birinchi manba</ref>",
    "deadbeef": "<ref>Ikkinchi manba</ref>",
}


# ── _restore_references ───────────────────────────────────────────────────────

class TestRestoreReferences:
    def test_restores_an_exact_placeholder(self, processor):
        text = "Matn<ref>REF_a1b2c3d4</ref> davomi"
        assert processor._restore_references(text, REF_MAP) == (
            "Matn<ref>Birinchi manba</ref> davomi"
        )

    def test_restores_despite_a_stray_space(self, processor):
        text = "Matn<ref>REF_a1b2c3d4 </ref> davomi"
        assert "Birinchi manba" in processor._restore_references(text, REF_MAP)

    def test_restores_when_the_model_dropped_the_tags(self, processor):
        text = "Matn REF_a1b2c3d4 davomi"
        assert "<ref>Birinchi manba</ref>" in processor._restore_references(text, REF_MAP)

    def test_restores_through_a_named_ref_wrapper(self, processor):
        text = 'Matn<ref name="x">REF_a1b2c3d4</ref> davomi'
        assert "Birinchi manba" in processor._restore_references(text, REF_MAP)

    def test_reference_text_with_backslashes_is_not_reinterpreted(self, processor):
        ref_map = {"a1b2c3d4": r"<ref>C:\path\1 va \g<0></ref>"}
        text = "Matn REF_a1b2c3d4"
        assert processor._restore_references(text, ref_map).endswith(ref_map["a1b2c3d4"])

    def test_warns_about_a_reference_that_never_came_back(self, processor, caplog):
        text = "Matn<ref>REF_ffffffff</ref> davomi"
        result = processor._restore_references(text, REF_MAP)
        assert "REF_ffffffff" in result           # left in place, not silently dropped
        assert "REF_ffffffff" in caplog.text      # and reported

    def test_silent_when_everything_resolved(self, processor, caplog):
        text = "Matn<ref>REF_a1b2c3d4</ref> va <ref>REF_deadbeef</ref>"
        processor._restore_references(text, REF_MAP)
        assert "tiklanmadi" not in caplog.text

    def test_empty_ref_map_is_a_no_op(self, processor):
        assert processor._restore_references("Matn", {}) == "Matn"
