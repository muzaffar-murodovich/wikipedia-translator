#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/wiki_fetcher.py - Wikipedia'dan wikitext olish
URL yoki maqola nomi orqali inglizcha wikitext yuklab olish.
"""

import re
import urllib.parse
import urllib.request
import json
from typing import Optional, Tuple


def extract_article_name(url: str) -> Optional[str]:
    """
    Wikipedia URL'dan maqola nomini ajratib olish.

    Qo'llab-quvvatlanadigan formatlar:
      https://en.wikipedia.org/wiki/Albert_Einstein
      https://en.m.wikipedia.org/wiki/Albert_Einstein
      Albert Einstein   (to'g'ridan-to'g'ri nom)

    Returns:
        Maqola nomi yoki None
    """
    url = url.strip()

    # URL ekanligini tekshirish
    if "wikipedia.org" in url:
        match = re.search(r"wikipedia\.org/wiki/(.+?)(?:\?|#|$)", url)
        if match:
            return urllib.parse.unquote(match.group(1)).replace("_", " ")
        return None

    # To'g'ridan-to'g'ri maqola nomi
    return url


def fetch_wikitext(article_name: str, lang: str = "en") -> Tuple[Optional[str], Optional[str]]:
    """
    Wikipedia API orqali wikitext yuklab olish.

    Args:
        article_name: Maqola nomi (masalan: "Albert Einstein")
        lang: Til kodi (default: "en")

    Returns:
        (wikitext, normalized_title) yoki (None, None) agar xato bo'lsa
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

        # Maqola topilmadi
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
    Wikitext redirect ekanligini tekshirish.

    Returns:
        Redirect target sarlavhasi yoki None
    """
    match = re.match(r"#(?:REDIRECT|redirect)\s*\[\[(.+?)(?:\|.+?)?\]\]", wikitext.strip())
    if match:
        return match.group(1)
    return None
