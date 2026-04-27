"""Shared fixtures for the wikipedia-translator test suite."""

import json
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_openai_response():
    """Reusable mock OpenAI chat completion response."""
    resp = MagicMock()
    resp.choices[0].message.content = "mocked translated text"
    resp.usage.total_tokens = 100
    resp.usage.prompt_tokens = 80
    resp.usage.prompt_tokens_details.cached_tokens = 20
    return resp


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Mock OpenAI client whose create() returns mock_openai_response."""
    client = MagicMock()
    client.chat.completions.create.return_value = mock_openai_response
    return client


@pytest.fixture
def rules_file(tmp_path):
    """Temporary translation_rules.md file with minimal content."""
    f = tmp_path / "translation_rules.md"
    f.write_text("# Rules\n1. Rule one\n2. Rule two\n", encoding="utf-8")
    return f


@pytest.fixture
def sample_localization_json(tmp_path):
    """Temporary localization_map.json with a handful of entries."""
    data = {
        "== References ==": "== Manbalar ==",
        "== See also ==": "== Yana qarang ==",
        "[[Category:": "[[Turkum:",
    }
    f = tmp_path / "localization_map.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return f
