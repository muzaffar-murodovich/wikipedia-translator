#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/wiki_fetcher.py - Fetch wikitext from Wikipedia
Download English wikitext by URL or article name.
"""

import re
import urllib.parse
from typing import Optional, Tuple

from utils.api_client import wiki_api
from utils.logger import logger


def extract_article_name(url: str) -> Optional[str]:
    """
    Extract article name from a Wikipedia URL.

    Supported formats:
      https://en.wikipedia.org/wiki/Albert_Einstein
      https://en.m.wikipedia.org/wiki/Albert_Einstein
      Albert Einstein   (plain article name)

    Returns:
        Article name or None
    """
    url = url.strip()

    if "wikipedia.org" in url:
        match = re.search(r"wikipedia\.org/wiki/(.+?)(?:\?|#|$)", url)
        if match:
            return urllib.parse.unquote(match.group(1)).replace("_", " ")
        return None

    # Plain article name
    return url


def fetch_wikitext(article_name: str, lang: str = "en") -> Tuple[Optional[str], Optional[str]]:
    """
    Download wikitext via Wikipedia API.

    Args:
        article_name: Article name (e.g. "Albert Einstein")
        lang: Language code (default: "en")

    Returns:
        (wikitext, normalized_title) or (None, None) on error
    """
    try:
        data = wiki_api({
            "action": "query",
            "titles": article_name,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
        }, lang=lang)

        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None, None

        page = pages[0]

        if page.get("missing"):
            return None, None

        title = page.get("title")
        slots = page.get("revisions", [{}])[0].get("slots", {})
        wikitext = slots.get("main", {}).get("content")

        return wikitext, title

    except Exception as e:
        # Yuklab bo'lmadi — bu "maqola yo'q" degani EMAS.
        logger.error(f"Maqolani yuklab bo'lmadi: {article_name} - {e}")
        return None, str(e)


def is_redirect(wikitext: str) -> Optional[str]:
    """
    Check if wikitext is a redirect page.

    Returns:
        Redirect target title or None
    """
    match = re.match(r"#(?:REDIRECT|redirect)\s*\[\[(.+?)(?:\|.+?)?\]\]", wikitext.strip())
    if match:
        return match.group(1)
    return None
