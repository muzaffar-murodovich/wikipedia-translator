"""Tests for core/reviewer.py — WikiReviewer with mocked OpenAI and rules file."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import config


def _make_response(content="reviewed text", total=200, prompt=150, cached=30):
    resp = MagicMock()
    resp.choices[0].message.content = content
    resp.usage.total_tokens = total
    resp.usage.prompt_tokens = prompt
    resp.usage.prompt_tokens_details.cached_tokens = cached
    return resp


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_response()
    return client


@pytest.fixture
def reviewer(mock_client, rules_file):
    """WikiReviewer with a real rules file in tmp_path and mocked OpenAI."""
    from core.reviewer import WikiReviewer
    with patch.object(WikiReviewer, "RULES_FILE", rules_file):
        with patch("core.reviewer.OpenAI", return_value=mock_client):
            r = WikiReviewer()
    return r


@pytest.fixture
def reviewer_no_rules(mock_client, tmp_path):
    """WikiReviewer pointing at a nonexistent rules file."""
    from core.reviewer import WikiReviewer
    missing = tmp_path / "no_rules.md"
    with patch.object(WikiReviewer, "RULES_FILE", missing):
        with patch("core.reviewer.OpenAI", return_value=mock_client):
            r = WikiReviewer()
    return r


# ── Initialisation ────────────────────────────────────────────────────────────

class TestWikiReviewerInit:
    def test_is_available_true_when_rules_loaded(self, reviewer):
        assert reviewer.is_available() is True

    def test_is_available_false_when_no_rules_file(self, reviewer_no_rules):
        assert reviewer_no_rules.is_available() is False

    def test_stats_start_at_zero(self, reviewer):
        assert reviewer.stats == {
            "reviews": 0,
            "tokens_used": 0,
            "cached_tokens": 0,
            "prompt_tokens": 0,
        }

    def test_model_set_from_config(self, reviewer):
        assert reviewer.model == config.REVIEW_MODEL


# ── review() — happy path ─────────────────────────────────────────────────────

class TestReview:
    def test_returns_response_content(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response("fixed text")
        result = reviewer.review("original text")
        assert result == "fixed text"

    def test_increments_reviews_stat(self, reviewer):
        reviewer.review("text")
        assert reviewer.stats["reviews"] == 1

    def test_accumulates_token_stats(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            total=200, prompt=150, cached=30
        )
        reviewer.review("text")
        assert reviewer.stats["tokens_used"] == 200
        assert reviewer.stats["prompt_tokens"] == 150
        assert reviewer.stats["cached_tokens"] == 30

    def test_rules_appear_in_system_message(self, reviewer, mock_client, rules_file):
        reviewer.review("some wikitext")
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        system_msgs = [m for m in messages if m["role"] == "system"]
        rules_content = rules_file.read_text(encoding="utf-8")
        assert rules_content in system_msgs[0]["content"]

    def test_wikitext_appears_in_user_message(self, reviewer, mock_client):
        reviewer.review("my wikitext content")
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert "my wikitext content" in user_msgs[0]["content"]


# ── review() — unavailable path ───────────────────────────────────────────────

class TestReviewUnavailable:
    def test_returns_input_unchanged_when_no_rules(self, reviewer_no_rules):
        result = reviewer_no_rules.review("original wikitext")
        assert result == "original wikitext"

    def test_does_not_call_api_when_unavailable(self, reviewer_no_rules, mock_client):
        reviewer_no_rules.review("text")
        mock_client.chat.completions.create.assert_not_called()


# ── review() — error handling ─────────────────────────────────────────────────

class TestReviewErrorHandling:
    def test_returns_none_on_api_exception(self, reviewer, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("API down")
        result = reviewer.review("text")
        assert result is None

    def test_no_exception_propagates(self, reviewer, mock_client):
        mock_client.chat.completions.create.side_effect = RuntimeError("timeout")
        try:
            reviewer.review("text")
        except Exception:
            pytest.fail("review() should not propagate exceptions")

    def test_stats_not_incremented_on_failure(self, reviewer, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("fail")
        reviewer.review("text")
        assert reviewer.stats["reviews"] == 0


# ── Code fence stripping ──────────────────────────────────────────────────────

class TestCodeFenceStripping:
    def test_strips_opening_backtick_fence(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            "```\nfixed content"
        )
        result = reviewer.review("text")
        assert result == "fixed content"

    def test_strips_closing_backtick_fence(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            "fixed content\n```"
        )
        result = reviewer.review("text")
        assert result == "fixed content"

    def test_strips_both_fences(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            "```\nfixed content\n```"
        )
        result = reviewer.review("text")
        assert result == "fixed content"

    def test_strips_fence_with_language_tag(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            "```wikitext\nfixed content\n```"
        )
        result = reviewer.review("text")
        assert result == "fixed content"

    def test_no_fence_content_unchanged(self, reviewer, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            "plain corrected text"
        )
        result = reviewer.review("text")
        assert result == "plain corrected text"
