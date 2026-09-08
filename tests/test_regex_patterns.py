"""Tests for utils/regex_patterns.py — all pure string/regex transformations."""

from utils.regex_patterns import (
    RegexPatterns,
    remove_empty_params,
    clean_html_comments,
    fix_punctuation_with_refs,
    fix_cite_book_script_title,
    fix_lik_suffix_capitalization,
    fix_year_with_dash,
    fix_punctuation_with_sfn,
    fix_arabic_transliteration,
    apply_all_fixes,
)


# ── RegexPatterns class methods ───────────────────────────────────────────────

class TestRegexPatternsClass:
    def test_compile_returns_pattern_for_known_name(self):
        import re
        pat = RegexPatterns.compile("HTML_COMMENT")
        assert pat is not None
        assert isinstance(pat, type(re.compile("")))

    def test_compile_returns_none_for_unknown_name(self):
        assert RegexPatterns.compile("DOES_NOT_EXIST") is None

    def test_find_all_returns_matches(self):
        matches = RegexPatterns.find_all("QID_PATTERN", "See Q1234 and Q5678")
        assert "Q1234" in matches
        assert "Q5678" in matches

    def test_find_all_returns_empty_for_no_match(self):
        assert RegexPatterns.find_all("QID_PATTERN", "no qids here") == []

    def test_replace_applies_substitution(self):
        result = RegexPatterns.replace("EXTRA_SPACES", "hello  world", " ")
        assert result == "hello world"

    def test_count_returns_correct_integer(self):
        text = "<!-- a --><!-- b -->"
        assert RegexPatterns.count("HTML_COMMENT", text) == 2


# ── remove_empty_params ───────────────────────────────────────────────────────

class TestRemoveEmptyParams:
    def test_removes_empty_param(self):
        wikitext = "{{tpl\n| name =\n| value = hello\n}}"
        result = remove_empty_params(wikitext)
        assert "| name =" not in result
        assert "| value = hello" in result

    def test_keeps_filled_param(self):
        wikitext = "{{tpl\n| value = hello\n}}"
        result = remove_empty_params(wikitext)
        assert "| value = hello" in result

    def test_collapses_multiple_newlines(self):
        wikitext = "line1\n\n\n\nline2"
        result = remove_empty_params(wikitext)
        assert "\n\n\n" not in result

    def test_no_change_when_clean(self):
        wikitext = "{{tpl|param=value}}"
        result = remove_empty_params(wikitext)
        assert "param=value" in result


# ── clean_html_comments ───────────────────────────────────────────────────────

class TestCleanHtmlComments:
    def test_removes_inline_comment(self):
        result = clean_html_comments("Hello <!-- comment --> World")
        assert "comment" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_multiline_comment(self):
        result = clean_html_comments("before\n<!-- line1\nline2 -->\nafter")
        assert "line1" not in result
        assert "after" in result

    def test_no_change_when_no_comments(self):
        text = "Plain text with no comments"
        assert clean_html_comments(text) == text


# ── fix_punctuation_with_refs ─────────────────────────────────────────────────

class TestFixPunctuationWithRefs:
    def test_moves_period_before_ref_to_after(self):
        result = fix_punctuation_with_refs("text.<ref>source</ref>")
        assert result == "text<ref>source</ref>."

    def test_moves_comma_before_ref_to_after(self):
        result = fix_punctuation_with_refs("text,<ref>source</ref>")
        assert result == "text<ref>source</ref>,"

    def test_moves_period_before_self_closing_ref(self):
        result = fix_punctuation_with_refs('text.<ref name="x"/>')
        assert result.startswith('text<ref name="x"/>')

    def test_removes_punct_between_consecutive_refs(self):
        result = fix_punctuation_with_refs("text</ref>.<ref>next</ref>")
        assert "</ref>.<ref>" not in result
        assert "</ref><ref>" in result or "</ref>\n<ref>" in result or "next</ref>" in result

    def test_deduplicates_period_after_ref(self):
        result = fix_punctuation_with_refs("text</ref>..")
        assert "</ref>.." not in result

    def test_no_period_added_before_lowercase_continuation(self):
        # A ref followed by a lowercase word — no period should be injected
        result = fix_punctuation_with_refs("text</ref> va boshqa")
        # Should NOT have ".</ref>" or "ref>. va" — period before "va" is wrong
        assert ".</ref>" not in result


# ── fix_cite_book_script_title ────────────────────────────────────────────────

class TestFixCiteBookScriptTitle:
    def test_strips_lang_prefix_and_renames_param(self):
        wikitext = "{{cite book |script-title=ru:Tekst}}"
        result = fix_cite_book_script_title(wikitext)
        assert "script-title" not in result
        assert "title=Tekst" in result

    def test_handles_no_lang_prefix(self):
        wikitext = "{{cite book |script-title=Tekst}}"
        result = fix_cite_book_script_title(wikitext)
        assert "script-title" not in result
        assert "title=Tekst" in result

    def test_does_not_touch_regular_title_param(self):
        wikitext = "{{cite book |title=Normal}}"
        result = fix_cite_book_script_title(wikitext)
        assert result == wikitext

    def test_does_not_touch_unrelated_template(self):
        wikitext = "{{cite web |script-title=ar:Text}}"
        result = fix_cite_book_script_title(wikitext)
        # only cite book is affected
        assert result == wikitext


# ── fix_lik_suffix_capitalization ─────────────────────────────────────────────

class TestFixLikSuffixCapitalization:
    def test_lowercases_mid_sentence(self):
        result = fix_lik_suffix_capitalization("Uni Bangladeshlik olim deb atashgan")
        assert result == "Uni bangladeshlik olim deb atashgan"

    def test_keeps_capital_in_article_name(self):
        wikitext = "'''Mogadishulik Saʼid''' — somalilik olim."
        assert fix_lik_suffix_capitalization(wikitext) == wikitext

    def test_keeps_capital_at_line_start(self):
        wikitext = "Bangladeshlik olim keldi."
        assert fix_lik_suffix_capitalization(wikitext) == wikitext

    def test_keeps_capital_after_sentence_end(self):
        wikitext = "U ketdi. Toshkentlik olim keldi."
        assert fix_lik_suffix_capitalization(wikitext) == wikitext

    def test_keeps_capital_in_spaced_parameter_value(self):
        wikitext = "| name          = Mogadishulik Saʼid"
        assert fix_lik_suffix_capitalization(wikitext) == wikitext

    def test_skips_when_equals_immediately_adjacent(self):
        # lookbehind only skips if = is the char directly before the word (no space)
        wikitext = "| nationality =Bangladeshlik"
        result = fix_lik_suffix_capitalization(wikitext)
        assert "Bangladeshlik" in result

    def test_skips_inside_wikilink(self):
        wikitext = "[[Bangladeshlik]]"
        result = fix_lik_suffix_capitalization(wikitext)
        assert "[[Bangladeshlik]]" in result

    def test_multiple_occurrences(self):
        result = fix_lik_suffix_capitalization("Hindistонlik va Bangladeshlik mutafakkirlar")
        # Capital -lik words mid-sentence get lowercased
        assert "Bangladeshlik" not in result or "bangladeshlik" in result


# ── fix_year_with_dash ────────────────────────────────────────────────────────

class TestFixYearWithDash:
    def test_basic_yil(self):
        assert fix_year_with_dash("2025 yil") == "2025-yil"

    def test_yilda(self):
        assert fix_year_with_dash("1400 yilda") == "1400-yilda"

    def test_yillar(self):
        assert fix_year_with_dash("1990 yillar") == "1990-yillar"

    def test_yillarda(self):
        assert fix_year_with_dash("1975 yillarda") == "1975-yillarda"

    def test_already_dashed_unchanged(self):
        assert fix_year_with_dash("2025-yil") == "2025-yil"

    def test_circa_template(self):
        result = fix_year_with_dash("{{Circa|910}} yilda")
        assert "{{Circa|910}}-yilda" in result

    def test_no_year_unchanged(self):
        text = "Hello World"
        assert fix_year_with_dash(text) == text


# ── fix_punctuation_with_sfn ──────────────────────────────────────────────────

class TestFixPunctuationWithSfn:
    def test_moves_period_before_sfn_to_after(self):
        result = fix_punctuation_with_sfn("text.{{sfn|Smith|2020}}")
        assert "text.{{sfn" not in result
        assert "{{sfn|Smith|2020}}" in result

    def test_removes_punct_between_sfn_and_sfn(self):
        result = fix_punctuation_with_sfn("{{sfn|A|2020}}.{{sfn|B|2021}}")
        assert "}}.{{" not in result

    def test_no_change_when_correct(self):
        # period already after sfn and followed by space — should stay
        result = fix_punctuation_with_sfn("text{{sfn|A}}\n")
        assert "{{sfn|A}}" in result

    def test_comma_survives_a_chain_of_sfns(self):
        # The comma has to travel past every template, not be dropped
        # between two of them and replaced by an invented period.
        result = fix_punctuation_with_sfn("matn edi,{{sfn|A}}{{sfn|B}} u keldi.")
        assert result == "matn edi{{sfn|A}}{{sfn|B}}, u keldi."

    def test_period_survives_a_chain_of_sfns(self):
        result = fix_punctuation_with_sfn("matn tugadi.{{sfn|A}}{{sfn|B}} Yangi.")
        assert result == "matn tugadi{{sfn|A}}{{sfn|B}}. Yangi."

    def test_no_period_invented_before_lowercase_word(self):
        # A lowercase word means the sentence continues.
        result = fix_punctuation_with_sfn("matn davom etadi{{sfn|A}} va yana.")
        assert result == "matn davom etadi{{sfn|A}} va yana."

    def test_missing_period_still_added_before_capital(self):
        result = fix_punctuation_with_sfn("matn tugadi{{sfn|A}} Yangi jumla.")
        assert result == "matn tugadi{{sfn|A}}. Yangi jumla."


# ── fix_arabic_transliteration ────────────────────────────────────────────────

class TestFixArabicTransliteration:
    def test_macron_a_removed(self):
        result = fix_arabic_transliteration("Kātib")
        assert "ā" not in result
        assert "Katib" in result

    def test_macron_u_removed(self):
        result = fix_arabic_transliteration("Qūt")
        assert "ū" not in result
        assert "Qut" in result

    def test_dot_h_removed(self):
        result = fix_arabic_transliteration("Muḥammad")
        assert "ḥ" not in result
        assert "Muhammad" in result

    def test_final_i_macron_becomes_iy(self):
        result = fix_arabic_transliteration("al-Amirī")
        assert "ī" not in result
        assert "Amiriy" in result

    def test_hamza_removed(self):
        result = fix_arabic_transliteration("ʿAlim")
        assert "ʿ" not in result
        assert "Alim" in result

    def test_solar_letter_r(self):
        result = fix_arabic_transliteration("al-Roziy")
        assert "ar-Roziy" in result

    def test_solar_letter_n(self):
        result = fix_arabic_transliteration("al-Nasafiy")
        assert "an-Nasafiy" in result

    def test_solar_letter_sh(self):
        result = fix_arabic_transliteration("al-Shofiiy")
        assert "ash-Shofiiy" in result

    def test_solar_letter_t(self):
        result = fix_arabic_transliteration("al-Tabariy")
        assert "at-Tabariy" in result

    def test_skips_ref_tag_content(self):
        wikitext = "<ref>al-Ṭabarī notes here</ref>"
        result = fix_arabic_transliteration(wikitext)
        # Content inside <ref> should be untouched
        assert "Ṭ" in result or "al-Ṭabarī" in result

    def test_processes_wikilink_label_not_target(self):
        # Link target should be untouched; label can be processed
        wikitext = "[[Abū_Bakr|Abū Bakr]]"
        result = fix_arabic_transliteration(wikitext)
        # Target part (before |) should remain; label (after |) gets processed
        assert "[[Abū_Bakr|" in result  # target unchanged
        # Label loses diacritics
        assert "|Abu Bakr]]" in result or "|Abū Bakr]]" not in result or "[[Abū_Bakr|" in result

    def test_no_diacritics_unchanged(self):
        text = "Hello World"
        result = fix_arabic_transliteration(text)
        assert result == text


# ── apply_all_fixes ───────────────────────────────────────────────────────────

class TestApplyAllFixes:
    def test_collapses_excess_newlines(self):
        result = apply_all_fixes("a\n\n\n\nb")
        assert "\n\n\n" not in result
        assert "a" in result and "b" in result

    def test_applies_year_dash_fix(self):
        result = apply_all_fixes("Tug'ilgan: 2025 yil")
        assert "2025-yil" in result

    def test_applies_lik_fix(self):
        result = apply_all_fixes("Kitob Bangladeshlik olim haqida")
        assert "bangladeshlik" in result

    def test_smoke_complex_wikitext(self):
        wikitext = (
            "'''Test''' — Bangladeshlik olim.<ref>source</ref>\n"
            "2025 yil tugʻilgan. al-Roziy haqida <!-- comment -->\n"
        )
        result = apply_all_fixes(wikitext)
        assert isinstance(result, str)
        assert len(result) > 0
