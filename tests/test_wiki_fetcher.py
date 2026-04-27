"""Tests for utils/wiki_fetcher.py — URL parsing, redirect detection, API fetching."""

import json
import pytest
from unittest.mock import MagicMock
from utils.wiki_fetcher import extract_article_name, fetch_wikitext, is_redirect


def _make_urlopen_ctx(payload: dict):
    """Create a context-manager mock whose read() returns JSON-encoded payload."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── extract_article_name ──────────────────────────────────────────────────────

class TestExtractArticleName:
    def test_plain_name_returned_as_is(self):
        assert extract_article_name("Albert Einstein") == "Albert Einstein"

    def test_en_wikipedia_url(self):
        url = "https://en.wikipedia.org/wiki/Albert_Einstein"
        assert extract_article_name(url) == "Albert Einstein"

    def test_mobile_url(self):
        url = "https://en.m.wikipedia.org/wiki/Nikola_Tesla"
        assert extract_article_name(url) == "Nikola Tesla"

    def test_underscores_converted_to_spaces(self):
        url = "https://en.wikipedia.org/wiki/Python_programming_language"
        assert extract_article_name(url) == "Python programming language"

    def test_url_encoded_chars_decoded(self):
        url = "https://en.wikipedia.org/wiki/%C3%96sterreich"
        result = extract_article_name(url)
        assert "Österreich" in result

    def test_query_string_stripped(self):
        url = "https://en.wikipedia.org/wiki/Python?action=edit"
        assert extract_article_name(url) == "Python"

    def test_fragment_stripped(self):
        url = "https://en.wikipedia.org/wiki/Python#History"
        assert extract_article_name(url) == "Python"

    def test_invalid_wikipedia_url_returns_none(self):
        url = "https://en.wikipedia.org/Special:Search"
        assert extract_article_name(url) is None

    def test_empty_string_returned_as_is(self):
        assert extract_article_name("") == ""

    def test_non_wikipedia_url_returned_as_is(self):
        url = "https://example.com/page"
        assert extract_article_name(url) == url


# ── is_redirect ───────────────────────────────────────────────────────────────

class TestIsRedirect:
    def test_detects_uppercase_redirect(self):
        assert is_redirect("#REDIRECT [[Target]]") == "Target"

    def test_detects_lowercase_redirect(self):
        assert is_redirect("#redirect [[Target]]") == "Target"

    def test_returns_none_for_non_redirect(self):
        assert is_redirect("== Lead ==\nSome article content") is None

    def test_returns_none_for_empty_string(self):
        assert is_redirect("") is None

    def test_redirect_with_pipe_returns_target_not_alias(self):
        assert is_redirect("#REDIRECT [[Target Page|display text]]") == "Target Page"

    def test_redirect_with_leading_whitespace(self):
        result = is_redirect("  #REDIRECT [[Page]]")
        assert result == "Page"

    def test_redirect_with_spaces_in_target(self):
        result = is_redirect("#REDIRECT [[Albert Einstein]]")
        assert result == "Albert Einstein"


# ── fetch_wikitext ────────────────────────────────────────────────────────────

class TestFetchWikitext:
    def _success_payload(self, title="Albert Einstein", content="== Bio ==\n..."):
        return {
            "query": {
                "pages": [{
                    "title": title,
                    "revisions": [{"slots": {"main": {"content": content}}}]
                }]
            }
        }

    def test_returns_wikitext_and_title_on_success(self, monkeypatch):
        monkeypatch.setattr(
            "utils.wiki_fetcher.urllib.request.urlopen",
            lambda req, timeout=None: _make_urlopen_ctx(self._success_payload())
        )
        wikitext, title = fetch_wikitext("Albert Einstein")
        assert title == "Albert Einstein"
        assert "== Bio ==" in wikitext

    def test_returns_none_none_for_missing_page(self, monkeypatch):
        payload = {"query": {"pages": [{"title": "X", "missing": True}]}}
        monkeypatch.setattr(
            "utils.wiki_fetcher.urllib.request.urlopen",
            lambda req, timeout=None: _make_urlopen_ctx(payload)
        )
        wikitext, title = fetch_wikitext("X")
        assert wikitext is None
        assert title is None

    def test_returns_none_none_for_empty_pages(self, monkeypatch):
        payload = {"query": {"pages": []}}
        monkeypatch.setattr(
            "utils.wiki_fetcher.urllib.request.urlopen",
            lambda req, timeout=None: _make_urlopen_ctx(payload)
        )
        result = fetch_wikitext("X")
        assert result == (None, None)

    def test_returns_none_and_error_string_on_network_error(self, monkeypatch):
        def raise_error(req, timeout=None):
            raise Exception("connection refused")

        monkeypatch.setattr("utils.wiki_fetcher.urllib.request.urlopen", raise_error)
        wikitext, error = fetch_wikitext("Albert Einstein")
        assert wikitext is None
        assert "connection refused" in error

    def test_url_contains_article_name(self, monkeypatch):
        captured = []

        def capture(req, timeout=None):
            captured.append(req.full_url)
            return _make_urlopen_ctx(self._success_payload())

        monkeypatch.setattr("utils.wiki_fetcher.urllib.request.urlopen", capture)
        fetch_wikitext("Albert Einstein")
        assert len(captured) == 1
        assert "Albert" in captured[0]
        assert "wikipedia.org" in captured[0]

    def test_lang_parameter_used_in_url(self, monkeypatch):
        captured = []

        def capture(req, timeout=None):
            captured.append(req.full_url)
            return _make_urlopen_ctx(self._success_payload())

        monkeypatch.setattr("utils.wiki_fetcher.urllib.request.urlopen", capture)
        fetch_wikitext("Page", lang="ru")
        assert "ru.wikipedia.org" in captured[0]
