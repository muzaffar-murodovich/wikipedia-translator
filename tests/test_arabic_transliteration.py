import pytest
from utils.regex_patterns import fix_arabic_transliteration


class TestFixArabicTransliteration:
    def test_infobox_name_param_diacritics_removed(self):
        text = "{{Shaxs bilgiqutisi|name=Muḥammad|birth_place=al-Madīna}}"
        result = fix_arabic_transliteration(text)
        assert "name=Muhammad" in result
        assert "birth_place=al-Madina" in result

    def test_infobox_solar_letter_assimilation(self):
        text = "{{Joyni Bilgiqutisi|name=al-Ṭabariyyah}}"
        result = fix_arabic_transliteration(text)
        assert "name=at-Tabariyyah" in result

    def test_cite_book_unchanged(self):
        text = "{{cite book|author=Muḥammad ibn Isḥāq|title=Sirah}}"
        assert fix_arabic_transliteration(text) == text

    def test_sfn_unchanged(self):
        text = "{{sfn|al-Ṭabarī|2010|p=42}}"
        assert fix_arabic_transliteration(text) == text

    def test_lang_template_unchanged(self):
        text = "{{lang-ar|Muḥammad}}"
        assert fix_arabic_transliteration(text) == text

    def test_ref_content_unchanged(self):
        text = "<ref>{{Shaxs bilgiqutisi|name=Muḥammad}}</ref>"
        assert fix_arabic_transliteration(text) == text

    def test_mixed_content_infobox_fixed_ref_skipped(self):
        text = (
            "{{Shaxs bilgiqutisi|name=Muḥammad|birth_year=570}}\n"
            "'''Muḥammad''' — payg'ambar.<ref>{{cite book|author=Ibn Isḥāq}}</ref>"
        )
        result = fix_arabic_transliteration(text)
        assert "name=Muhammad" in result
        assert "'''Muhammad''' — pay" in result
        assert "Ibn Isḥāq" in result
