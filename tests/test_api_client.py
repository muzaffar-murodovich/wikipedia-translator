"""Tests for utils/api_client.py — CA bundle selection and retry behaviour."""

import json
import ssl
import urllib.error
import pytest
from unittest.mock import MagicMock

import config
from utils import api_client
from utils.api_client import _resolve_ca_file, wiki_api


def _make_urlopen_ctx(payload: dict):
    """Create a context-manager mock whose read() returns JSON-encoded payload."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _cert_error() -> urllib.error.URLError:
    """A certificate failure shaped the way urlopen reports it."""
    reason = ssl.SSLCertVerificationError(1, "certificate verify failed")
    reason.verify_message = "unable to get local issuer certificate"
    return urllib.error.URLError(reason)


# ── _resolve_ca_file ──────────────────────────────────────────────────────────

class TestResolveCaFile:

    def test_defaults_to_certifi(self, monkeypatch):
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        assert _resolve_ca_file().endswith("cacert.pem")

    def test_ssl_cert_file_wins_when_present(self, monkeypatch, tmp_path):
        ca = tmp_path / "corporate-ca.pem"
        ca.write_text("", encoding="utf-8")
        monkeypatch.setenv("SSL_CERT_FILE", str(ca))
        assert _resolve_ca_file() == str(ca)

    def test_falls_back_when_ssl_cert_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "yoq.pem"))
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        assert _resolve_ca_file().endswith("cacert.pem")


# ── wiki_api retry behaviour ──────────────────────────────────────────────────

class TestWikiApiRetries:

    def test_certificate_error_is_not_retried(self, monkeypatch):
        calls = []

        def fail(req, timeout=None, **kwargs):
            calls.append(req.full_url)
            raise _cert_error()

        monkeypatch.setattr(api_client.urllib.request, "urlopen", fail)
        monkeypatch.setattr(api_client.time, "sleep", lambda s: None)

        with pytest.raises(urllib.error.URLError):
            wiki_api({"action": "query", "titles": "X"})

        # A bad CA never becomes a good one — one attempt, no backoff.
        assert len(calls) == 1

    def test_transient_error_is_retried(self, monkeypatch):
        calls = []

        def fail(req, timeout=None, **kwargs):
            calls.append(req.full_url)
            raise urllib.error.URLError("connection reset")

        monkeypatch.setattr(api_client.urllib.request, "urlopen", fail)
        monkeypatch.setattr(api_client.time, "sleep", lambda s: None)

        with pytest.raises(urllib.error.URLError):
            wiki_api({"action": "query", "titles": "X"})

        assert len(calls) == config.API_MAX_RETRIES

    def test_succeeds_after_transient_error(self, monkeypatch):
        payload = {"query": {"pages": [{"title": "X"}]}}
        calls = []

        def flaky(req, timeout=None, **kwargs):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise urllib.error.URLError("connection reset")
            return _make_urlopen_ctx(payload)

        monkeypatch.setattr(api_client.urllib.request, "urlopen", flaky)
        monkeypatch.setattr(api_client.time, "sleep", lambda s: None)

        assert wiki_api({"action": "query", "titles": "X"}) == payload
        assert len(calls) == 2

    def test_ssl_context_is_passed_to_urlopen(self, monkeypatch):
        seen = {}

        def capture(req, timeout=None, **kwargs):
            seen.update(kwargs)
            return _make_urlopen_ctx({"query": {}})

        monkeypatch.setattr(api_client.urllib.request, "urlopen", capture)
        wiki_api({"action": "query", "titles": "X"})

        assert seen["context"] is api_client._SSL_CONTEXT
