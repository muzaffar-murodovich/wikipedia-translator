import pytest
from utils.regex_patterns import (
    RegexPatterns,
    remove_empty_params,
    clean_html_comments,
    fix_year_with_dash,
    fix_lik_suffix_capitalization,
    fix_cite_book_script_title,
    fix_punctuation_with_refs,
    fix_punctuation_with_sfn,
)


class TestRegexPatternsClass:
    def test_compile_known_pattern(self):
        assert RegexPatterns.compile("QID_PATTERN") is not None

    def test_compile_unknown_returns_none(self):
        assert RegexPatterns.compile("NONEXISTENT_PATTERN") is None

    def test_find_all_qids(self):
        text = "[[Q123|link]] and [[Q456]]"
        matches = RegexPatterns.find_all("QID_PATTERN", text)
        assert "Q123" in matches
        assert "Q456" in matches

    def test_count_matches(self):
        text = "Q1 and Q2 and Q3"
        assert RegexPatterns.count("QID_PATTERN", text) == 3

    def test_replace_applies_substitution(self):
        text = "== References =="
        result = RegexPatterns.replace("HEADING", text, "== Manbalar ==")
        assert result == "== Manbalar =="

    def test_find_all_unknown_pattern_returns_empty(self):
        assert RegexPatterns.find_all("NONEXISTENT", "some text") == []


class TestRemoveEmptyParams:
    def test_removes_empty_param(self):
        text = "{{Infobox\n| name = Einstein\n| alias =\n}}"
        result = remove_empty_params(text)
        assert "| alias =" not in result
        assert "| name = Einstein" in result

    def test_preserves_non_empty_params(self):
        text = "{{Infobox\n| name = Einstein\n}}"
        result = remove_empty_params(text)
        assert "| name = Einstein" in result

    def test_no_empty_params_unchanged(self):
        text = "{{Infobox\n| a = x\n| b = y\n}}"
        result = remove_empty_params(text)
        assert "| a = x" in result
        assert "| b = y" in result


class TestCleanHtmlComments:
    def test_removes_inline_comment(self):
        assert clean_html_comments("Before<!-- comment -->After") == "BeforeAfter"

    def test_removes_multiline_comment(self):
        text = "Before<!--\nLine 1\nLine 2\n-->After"
        assert clean_html_comments(text) == "BeforeAfter"

    def test_no_comments_unchanged(self):
        text = "Just plain text"
        assert clean_html_comments(text) == text

    def test_multiple_comments_all_removed(self):
        text = "A<!-- x -->B<!-- y -->C"
        assert clean_html_comments(text) == "ABC"


class TestFixYearWithDash:
    def test_year_yil(self):
        assert fix_year_with_dash("2025 yil") == "2025-yil"

    def test_year_yilda(self):
        assert fix_year_with_dash("1990 yilda") == "1990-yilda"

    def test_year_yillar(self):
        assert fix_year_with_dash("1990 yillar") == "1990-yillar"

    def test_already_dashed_unchanged(self):
        assert fix_year_with_dash("2025-yil") == "2025-yil"

    def test_circa_template_with_yilda(self):
        result = fix_year_with_dash("{{Circa|910}} yilda")
        assert "{{Circa|910}}-yilda" in result

    def test_number_without_yil_unchanged(self):
        assert fix_year_with_dash("2025 noyabr") == "2025 noyabr"


class TestFixLikSuffixCapitalization:
    def test_lowercases_mid_sentence(self):
        result = fix_lik_suffix_capitalization("u Bangladeshlik olim edi")
        assert "bangladeshlik" in result

    def test_preserves_after_equals_sign_no_space(self):
        # Lookbehind checks exactly one char: '=' immediately before the word
        text = "| nationality =Bangladeshlik"
        assert "Bangladeshlik" in fix_lik_suffix_capitalization(text)

    def test_preserves_inside_wikilink(self):
        text = "[[Bangladeshlik]]"
        assert "[[Bangladeshlik]]" in fix_lik_suffix_capitalization(text)

    def test_no_lik_word_unchanged(self):
        text = "oddiy gap bu yerda"
        assert fix_lik_suffix_capitalization(text) == text


class TestFixCiteBookScriptTitle:
    def test_replaces_script_title_with_title(self):
        text = "{{cite book |script-title=ru:Nazvanie}}"
        result = fix_cite_book_script_title(text)
        assert "script-title" not in result
        assert "|title=Nazvanie" in result

    def test_strips_language_prefix(self):
        text = "{{cite book |script-title=ar:Arabic text}}"
        result = fix_cite_book_script_title(text)
        assert "ar:" not in result
        assert "Arabic text" in result

    def test_no_script_title_unchanged(self):
        text = "{{cite book |title=Normal title}}"
        assert fix_cite_book_script_title(text) == text

    def test_case_insensitive_match(self):
        text = "{{Cite Book |script-title=ru:Text}}"
        result = fix_cite_book_script_title(text)
        assert "script-title" not in result


class TestFixPunctuationWithRefs:
    def test_moves_period_before_ref_to_after(self):
        text = "Text.<ref>Source</ref> Next"
        result = fix_punctuation_with_refs(text)
        assert "Text<ref>Source</ref>." in result

    def test_moves_comma_before_ref_to_after(self):
        text = "Word,<ref>Source</ref> next"
        result = fix_punctuation_with_refs(text)
        assert "Word<ref>Source</ref>," in result

    def test_no_refs_unchanged(self):
        text = "Simple text. No refs here."
        assert fix_punctuation_with_refs(text) == text

    def test_removes_punct_between_consecutive_refs(self):
        text = "Text<ref>A</ref>.<ref>B</ref>"
        result = fix_punctuation_with_refs(text)
        assert "</ref>.<ref>" not in result

    def test_no_duplicate_punct_after_ref(self):
        text = "Text<ref>Source</ref>.."
        result = fix_punctuation_with_refs(text)
        assert "</ref>.." not in result


class TestFixPunctuationWithSfn:
    def test_moves_period_before_sfn_to_after(self):
        text = "Text.{{sfn|Author|2020|p=5}} Next"
        result = fix_punctuation_with_sfn(text)
        assert "Text{{sfn|Author|2020|p=5}}" in result

    def test_removes_punct_between_consecutive_sfns(self):
        text = "Text{{sfn|A|2020}}.{{sfn|B|2021}}"
        result = fix_punctuation_with_sfn(text)
        assert "}}.{{sfn" not in result

    def test_no_sfn_unchanged(self):
        text = "Simple text with no templates."
        assert fix_punctuation_with_sfn(text) == text
