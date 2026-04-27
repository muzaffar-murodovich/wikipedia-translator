import pytest
from unittest.mock import MagicMock
from core.processor import WikiTextProcessor
from core.cache_manager import WikiCache


def make_processor(uz_sitelinks=None, en_sitelinks=None):
    """Create a processor with a mocked fetcher.

    uz_sitelinks: dict of QID -> uz title (or None if missing)
    en_sitelinks: dict of QID -> en title (or None if missing)
    """
    uz_sitelinks = uz_sitelinks or {}
    en_sitelinks = en_sitelinks or {}

    fetcher = MagicMock()
    fetcher.get_sitelink.side_effect = lambda qid, lang: (
        uz_sitelinks.get(qid) if lang == "uz" else en_sitelinks.get(qid)
    )
    fetcher.get_en_sitelink.side_effect = lambda qid: en_sitelinks.get(qid)

    cache = WikiCache()
    return WikiTextProcessor(fetcher, cache)


class TestFinalizeWikilinkResolution:
    def test_uz_sitelink_exists_uses_uz_title(self):
        """[[Q1|Label]] with uz sitelink → [[UzTitle|Label]]"""
        proc = make_processor(uz_sitelinks={"Q1": "Albert Eynshteyn"})
        result = proc.finalize("[[Q1|Eynshteyn]]", ref_map={})
        assert "[[Albert Eynshteyn|Eynshteyn]]" in result

    def test_uz_sitelink_matches_label_drops_label(self):
        """[[Q1|UzTitle]] with matching uz sitelink → [[UzTitle]]"""
        proc = make_processor(uz_sitelinks={"Q1": "Muhammad"})
        result = proc.finalize("[[Q1|Muhammad]]", ref_map={})
        assert "[[Muhammad]]" in result
        assert "|" not in result.split("[[")[1].split("]]")[0]

    def test_no_uz_sitelink_falls_back_to_en_title(self):
        """Main fix: uz missing → use en title as red link, keep label."""
        proc = make_processor(
            uz_sitelinks={"Q1": None},
            en_sitelinks={"Q1": "Abu Muhammad ibn al-Husaini"},
        )
        result = proc.finalize("[[Q1|Muhammad]]", ref_map={})
        assert "[[Abu Muhammad ibn al-Husaini|Muhammad]]" in result

    def test_no_uz_sitelink_en_matches_label_drops_label(self):
        """[[Q1|EnTitle]], no uz, en title matches label → [[EnTitle]]"""
        proc = make_processor(
            uz_sitelinks={"Q1": None},
            en_sitelinks={"Q1": "Muhammad"},
        )
        result = proc.finalize("[[Q1|Muhammad]]", ref_map={})
        assert "[[Muhammad]]" in result

    def test_no_sitelinks_with_label_keeps_label_as_text(self):
        """No uz, no en, has label → bare label text (no broken link)."""
        proc = make_processor(uz_sitelinks={"Q1": None}, en_sitelinks={"Q1": None})
        result = proc.finalize("Bu [[Q1|Muhammad]] edi.", ref_map={})
        assert "Muhammad" in result
        assert "[[" not in result
        assert "Q1" not in result

    def test_no_sitelinks_no_label_removes_link(self):
        """No uz, no en, no label → wikilink removed entirely."""
        proc = make_processor(uz_sitelinks={"Q1": None}, en_sitelinks={"Q1": None})
        result = proc.finalize("Boshlanish [[Q1]] oxiri.", ref_map={})
        assert "Q1" not in result
        assert "[[" not in result

    def test_non_qid_wikilink_untouched(self):
        """Plain wikilinks (not QID placeholders) pass through."""
        proc = make_processor()
        result = proc.finalize("[[Toshkent]] poytaxt.", ref_map={})
        assert "[[Toshkent]]" in result

    def test_multiple_wikilinks_mixed_outcomes(self):
        """Multiple links, each resolved independently."""
        proc = make_processor(
            uz_sitelinks={"Q1": "Toshkent", "Q2": None, "Q3": None},
            en_sitelinks={"Q2": "Abu Muhammad", "Q3": None},
        )
        result = proc.finalize(
            "[[Q1|poytaxt]] va [[Q2|Muhammad]] hamda [[Q3|nomaʼlum]].",
            ref_map={},
        )
        assert "[[Toshkent|poytaxt]]" in result
        assert "[[Abu Muhammad|Muhammad]]" in result
        assert "nomaʼlum" in result
        assert "Q3" not in result