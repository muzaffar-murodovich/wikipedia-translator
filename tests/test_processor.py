"""Tests for core/processor.py — the parts that need no network."""

from unittest.mock import MagicMock

import pytest

import config

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


# ── _compress_references ──────────────────────────────────────────────────────

class TestCompressReferences:
    PLACEHOLDER_LEN = len("<ref>REF_a1b2c3d4</ref>")

    def test_threshold_exceeds_the_placeholder_length(self):
        # Below this, compressing a reference makes the text longer.
        assert config.REF_COMPRESS_THRESHOLD >= self.PLACEHOLDER_LEN

    def test_compression_never_lengthens_a_reference(self, processor):
        for body_len in range(1, 60):
            ref = "<ref>" + "x" * body_len + "</ref>"
            compressed, _ = processor._compress_references(ref)
            assert len(compressed) <= len(ref), f"grew for body of {body_len}"

    def test_long_reference_is_compressed(self, processor):
        ref = "<ref>" + "u" * 100 + "</ref>"
        compressed, ref_map = processor._compress_references(ref)
        assert len(ref_map) == 1
        assert len(compressed) < len(ref)

    def test_short_reference_is_left_alone(self, processor):
        ref = "<ref>ab</ref>"
        compressed, ref_map = processor._compress_references(ref)
        assert compressed == ref
        assert ref_map == {}

    def test_compress_then_restore_round_trips(self, processor):
        original = "Matn<ref>" + "manba " * 20 + "</ref> davomi"
        compressed, ref_map = processor._compress_references(original)
        assert processor._restore_references(compressed, ref_map) == original
