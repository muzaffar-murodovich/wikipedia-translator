#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/wiki_fetcher.py - Fetch wikitext from Wikipedia
Download English wikitext by URL or article name.
"""

import re
import urllib.parse
import urllib.request
import json
from typing import Optional, Tuple


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
    encoded = urllib.parse.quote(article_name)
    api_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&titles={encoded}&prop=revisions"
        f"&rvprop=content&rvslots=main&format=json&formatversion=2"
    )

    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "WikiTranslatorBot/1.0 (Uzbek Wikipedia translation)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

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
