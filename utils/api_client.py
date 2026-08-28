#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/api_client.py - Shared Wikimedia API client
Single place for HTTP requests to Wikipedia/Wikidata, with rate-limit
(HTTP 429) handling. Every module must go through here — a request that
fails must never be silently treated as "not found".
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

import config
from utils.logger import logger


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
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            # 429 = rate limited, 5xx = transient server error
            if e.code != 429 and e.code < 500:
                raise
            last_error = e

        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
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
