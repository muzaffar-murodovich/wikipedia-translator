"""Tests for core/translator.py — WikiTranslator with mocked OpenAI."""

import pytest
from unittest.mock import patch, MagicMock
import config


def _make_response(content="translated text", total=100, prompt=80, cached=20):
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
def translator(mock_client):
    with patch("core.translator.OpenAI", return_value=mock_client):
        from core.translator import WikiTranslator
        t = WikiTranslator()
    return t


# ── Initialisation ────────────────────────────────────────────────────────────

class TestWikiTranslatorInit:
    def test_model_set_from_config(self, translator):
        assert translator.model == config.OPENAI_MODEL

    def test_stats_start_at_zero(self, translator):
        assert translator.stats == {
            "translations": 0,
            "tokens_used": 0,
            "cached_tokens": 0,
            "prompt_tokens": 0,
        }


# ── translate() ───────────────────────────────────────────────────────────────

class TestTranslate:
    def test_returns_response_content(self, translator, mock_client):
        mock_client.chat.completions.create.return_value = _make_response("tarjima")
        result = translator.translate("hello")
        assert result == "tarjima"

    def test_increments_translations_stat(self, translator):
        translator.translate("hello")
        translator.translate("world")
        assert translator.stats["translations"] == 2

    def test_accumulates_token_stats(self, translator, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            total=100, prompt=80, cached=20
        )
        translator.translate("hello")
        assert translator.stats["tokens_used"] == 100
        assert translator.stats["prompt_tokens"] == 80
        assert translator.stats["cached_tokens"] == 20

    def test_accumulates_tokens_across_calls(self, translator, mock_client):
        mock_client.chat.completions.create.return_value = _make_response(
            total=50, prompt=40, cached=10
        )
        translator.translate("a")
        translator.translate("b")
        assert translator.stats["tokens_used"] == 100
        assert translator.stats["cached_tokens"] == 20

    def test_returns_none_on_api_exception(self, translator, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("API down")
        result = translator.translate("hello")
        assert result is None

    def test_no_exception_propagates_on_api_error(self, translator, mock_client):
        mock_client.chat.completions.create.side_effect = RuntimeError("timeout")
        try:
            translator.translate("hello")
        except Exception:
            pytest.fail("translate() should not propagate exceptions")

    def test_stats_not_incremented_on_failure(self, translator, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("fail")
        translator.translate("hello")
        assert translator.stats["translations"] == 0

    def test_text_appears_in_user_message(self, translator, mock_client):
        translator.translate("my prepared text")
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        # find the user message
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 1
        assert "my prepared text" in user_msgs[0]["content"]

    def test_forced_links_listed_in_user_message(self, translator, mock_client):
        translator.translate("text", ["safe conduct", "Hawazin"])
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        content = [m for m in messages if m["role"] == "user"][0]["content"]
        assert "[[safe conduct]]" in content
        assert "[[Hawazin]]" in content

    def test_no_forced_links_block_when_all_resolved(self, translator, mock_client):
        translator.translate("text")
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        content = [m for m in messages if m["role"] == "user"][0]["content"]
        assert "MAJBURIY" not in content

    def test_forced_links_block_deduplicates_nothing_when_empty(self, translator):
        from core.translator import WikiTranslator
        assert WikiTranslator._forced_links_block([]) == ""
        assert WikiTranslator._forced_links_block(None) == ""

    def test_system_message_is_set(self, translator, mock_client):
        translator.translate("text")
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0]
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == config.TRANSLATION_SYSTEM_PROMPT

    def test_correct_model_used(self, translator, mock_client):
        translator.translate("text")
        create_call = mock_client.chat.completions.create.call_args
        model_used = create_call.kwargs.get("model") or create_call.args[0]
        assert model_used == config.OPENAI_MODEL

    def test_handles_response_without_usage_gracefully(self, translator, mock_client):
        resp = MagicMock()
        resp.choices[0].message.content = "ok"
        del resp.usage  # simulate missing usage attribute
        mock_client.chat.completions.create.return_value = resp
        result = translator.translate("text")
        # Should still return the content, not raise
        assert result == "ok"
