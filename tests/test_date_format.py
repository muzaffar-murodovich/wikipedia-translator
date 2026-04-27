import pytest
from utils.regex_patterns import _apply_date_fixes


class TestApplyDateFixes:
    def test_number_before_hijriy(self):
        assert _apply_date_fixes("132 hijriy") == "hijriy 132-yil"

    def test_number_before_milodiy(self):
        assert _apply_date_fixes("750 milodiy") == "milodiy 750-yil"

    def test_combined_hijriy_milodiy(self):
        assert _apply_date_fixes("132 hijriy/750 milodiy") == "hijriy 132-yil/milodiy 750-yil"

    def test_hijriy_before_number(self):
        assert _apply_date_fixes("hijriy 132") == "hijriy 132-yil"

    def test_idempotent_hijriy(self):
        assert _apply_date_fixes("hijriy 132-yil") == "hijriy 132-yil"

    def test_idempotent_milodiy(self):
        assert _apply_date_fixes("milodiy 750-yil") == "milodiy 750-yil"

    def test_number_hijriy_yilda(self):
        # _apply_date_fixes is a plain-text function — no ref/template protection
        text = "al-Tabariy 132 hijriy yilda tugʻilgan"
        result = _apply_date_fixes(text)
        assert "hijriy 132-yilda" in result

    def test_infobox_param_fixed(self):
        text = "{{Shaxs bilgiqutisi|birth_year=132 hijriy}}"
        result = _apply_date_fixes(text)
        assert "birth_year=hijriy 132-yil" in result

    def test_no_date_string_unchanged(self):
        text = "Oddiy matn bu yerda."
        assert _apply_date_fixes(text) == text
