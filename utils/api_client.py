#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/api_client.py - Shared Wikimedia API client
Single place for HTTP requests to Wikipedia/Wikidata, with rate-limit
(HTTP 429) handling. Every module must go through here — a request that
fails must never be silently treated as "not found".
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

import certifi

import config
from utils.logger import logger


def _resolve_ca_file() -> str:
    """
    Pick the CA bundle used to verify every API request.

    The certificate source must not depend on the platform. On Linux the
    ssl module reads a complete, package-managed CA directory, but on
    Windows it can only see the OS certificate store, which ships with a
    minimal root set and fills up on demand — a root Python needs may
    simply be absent, which surfaces as SSLCertVerificationError while
    browsers work fine. certifi provides the same bundle everywhere.

    SSL_CERT_FILE / REQUESTS_CA_BUNDLE still win when set, so a corporate
    proxy or antivirus that intercepts HTTPS can be supported by pointing
    them at a bundle containing its root certificate.
    """
    custom_ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if custom_ca:
        if os.path.isfile(custom_ca):
            return custom_ca
        logger.warning(
            f"CA fayli topilmadi ({custom_ca}) — certifi to'plamiga qaytilmoqda."
        )
    return certifi.where()


_SSL_CONTEXT_CA = _resolve_ca_file()

try:
    _SSL_CONTEXT = ssl.create_default_context(cafile=_SSL_CONTEXT_CA)
except (OSError, ssl.SSLError) as e:
    logger.warning(
        f"CA fayli o'qilmadi ({_SSL_CONTEXT_CA}): {e}. "
        "certifi to'plamiga qaytilmoqda."
    )
    _SSL_CONTEXT_CA = certifi.where()
    _SSL_CONTEXT = ssl.create_default_context(cafile=_SSL_CONTEXT_CA)


def _retry_delay(attempt: int, error: Exception) -> float:
    """
    Compute how long to wait before the next retry.
    Honours the server's Retry-After header when present,
    otherwise uses exponential backoff.
    """
    retry_after = None
    if isinstance(error, urllib.error.HTTPError):
        header = error.headers.get("Retry-After") if error.headers else None
        if header:
            try:
                retry_after = float(header)
            except (TypeError, ValueError):
                retry_after = None

    backoff = config.API_RETRY_BASE_DELAY * (2 ** attempt)
    return min(max(retry_after or 0.0, backoff), config.API_MAX_RETRY_DELAY)


def wiki_api(params: dict, lang: str = "en", domain: str = "wikipedia",
             timeout: int = 30) -> dict:
    """
    Send a request to the Wikipedia/Wikidata API and return the parsed JSON.

    Retries on rate limiting (429) and transient server/network errors,
    honouring the Retry-After header. Raises the last error if every
    attempt fails — callers must not treat a failed request as "not found".

    Args:
        params: API parameters (format/formatversion are filled in)
        lang: Wikipedia language code (ignored when domain="wikidata")
        domain: "wikipedia" or "wikidata"
        timeout: Per-request timeout in seconds

    Returns:
        Parsed JSON response
    """
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    encoded = urllib.parse.urlencode(params)

    if domain == "wikidata":
        url = f"https://www.wikidata.org/w/api.php?{encoded}"
    else:
        url = f"https://{lang}.wikipedia.org/w/api.php?{encoded}"

    last_error: Optional[Exception] = None

    for attempt in range(config.API_MAX_RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": config.API_USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            # 429 = rate limited, 5xx = transient server error
            if e.code != 429 and e.code < 500:
                raise
            last_error = e

        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError):
                # Sertifikat xatosi qayta urinishdan tuzalmaydi.
                logger.fail(
                    f"SSL sertifikati tekshiruvdan o'tmadi: {reason.verify_message or reason}\n"
                    f"    Ishlatilgan CA fayli: {_SSL_CONTEXT_CA}\n"
                    "    Sabablari: eskirgan certifi, tizim soati noto'g'ri, yoki "
                    "HTTPS trafikni ushlab turgan antivirus/proksi.\n"
                    "    Yechim: `pip install -U certifi`, yoki proksi ildiz "
                    "sertifikatini SSL_CERT_FILE orqali ko'rsating."
                )
                raise
            last_error = e

        if attempt < config.API_MAX_RETRIES - 1:
            delay = _retry_delay(attempt, last_error)
            logger.warning(
                f"API so'rovi muvaffaqiyatsiz ({last_error}). "
                f"{delay:.1f} soniyadan keyin qayta urinilmoqda "
                f"({attempt + 1}/{config.API_MAX_RETRIES - 1})..."
            )
            time.sleep(delay)

    raise last_error
