import pytest
from utils.wiki_fetcher import extract_article_name, is_redirect


class TestExtractArticleName:
    def test_desktop_url(self):
        url = "https://en.wikipedia.org/wiki/Albert_Einstein"
        assert extract_article_name(url) == "Albert Einstein"

    def test_mobile_url(self):
        url = "https://en.m.wikipedia.org/wiki/Albert_Einstein"
        assert extract_article_name(url) == "Albert Einstein"

    def test_url_with_query_params(self):
        url = "https://en.wikipedia.org/wiki/Albert_Einstein?action=edit"
        assert extract_article_name(url) == "Albert Einstein"

    def test_url_with_anchor(self):
        url = "https://en.wikipedia.org/wiki/Albert_Einstein#Early_life"
        assert extract_article_name(url) == "Albert Einstein"

    def test_url_encoded_characters(self):
        url = "https://en.wikipedia.org/wiki/Muhammad_ibn_M%C5%ABs%C4%81"
        assert extract_article_name(url) == "Muhammad ibn Mūsā"

    def test_plain_article_name_returned_as_is(self):
        assert extract_article_name("Albert Einstein") == "Albert Einstein"

    def test_strips_leading_trailing_whitespace(self):
        assert extract_article_name("  Albert Einstein  ") == "Albert Einstein"

    def test_url_without_wiki_path_returns_none(self):
        assert extract_article_name("https://en.wikipedia.org/") is None

    def test_other_language_wikipedia_url(self):
        url = "https://uz.wikipedia.org/wiki/Albert_Eynshteyn"
        assert extract_article_name(url) == "Albert Eynshteyn"


class TestIsRedirect:
    def test_uppercase_redirect(self):
        assert is_redirect("#REDIRECT [[Albert Einstein]]") == "Albert Einstein"

    def test_lowercase_redirect(self):
        assert is_redirect("#redirect [[Albert Einstein]]") == "Albert Einstein"

    def test_redirect_returns_target_not_alias(self):
        assert is_redirect("#REDIRECT [[Albert Einstein|Einstein]]") == "Albert Einstein"

    def test_redirect_with_extra_whitespace(self):
        assert is_redirect("#REDIRECT  [[Target Article]]") == "Target Article"

    def test_non_redirect_returns_none(self):
        wikitext = "{{Infobox person|name=Einstein}}\n== Biography =="
        assert is_redirect(wikitext) is None

    def test_empty_string_returns_none(self):
        assert is_redirect("") is None

    def test_normal_article_with_redirect_word_returns_none(self):
        assert is_redirect("This article discusses redirect pages.") is None
