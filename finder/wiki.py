#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finder/wiki.py - The Wikipedia reads the discovery agent needs.

All of it goes through utils.api_client.wiki_api, the project's single HTTP
entry point, so retries, the User-Agent and the certifi CA bundle are shared
with the rest of the pipeline.

These are reads only. Nothing here can edit a wiki, and nothing should:
publishing is the human's step.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional

import config
from utils.api_client import wiki_api
from utils.logger import logger

# Categories that say nothing about a subject: cleanup trackers, stub
# markers and the date buckets every biography carries. The agent would
# otherwise spend its context reading them.
_MAINTENANCE_PATTERNS = [
    r'^(?:All |Articles |Pages |Wikipedia |CS1 |Webarchive|Use \w+ dates'
    r'|Commons category|Short description|Harv and Sfn|Interlanguage link)',
    r'\bstubs?$',
    r'^\d+s? (?:births|deaths)$',
    r'^\d+(?:st|nd|rd|th)-century (?:births|deaths)$',
    r'^(?:Year of|Date of|Place of) (?:birth|death)',
]

_MAINTENANCE_RE = re.compile("|".join(_MAINTENANCE_PATTERNS), re.IGNORECASE)


def normalize_category_name(name: str) -> str:
    """Ensure category name has 'Category:' prefix."""
    if name.lower().startswith("category:"):
        return "Category:" + name[len("Category:"):]
    return "Category:" + name


def strip_category_prefix(name: str) -> str:
    """'Category:Hadith scholars' -> 'Hadith scholars'."""
    if name.lower().startswith("category:"):
        return name[len("Category:"):]
    return name


def make_url(title: str) -> str:
    """Build English Wikipedia URL for an article title."""
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    return f"https://en.wikipedia.org/wiki/{encoded}"


def is_maintenance_category(name: str) -> bool:
    """Is this a housekeeping/date category rather than a topical one?"""
    return bool(_MAINTENANCE_RE.search(strip_category_prefix(name)))


def fetch_category_members(category: str) -> Dict[str, Dict[str, Any]]:
    """
    Every article in a category, with its Uzbek interwiki and byte size.

    One request per 500 members: generator=categorymembers carries
    prop=langlinks|info, so membership, Uzbek existence and article size all
    arrive together. Interwiki links are served from Wikidata sitelinks, so
    the uz answer matches a per-article Wikidata lookup.

    Returns {en_title: {"uz": uz_title or None, "size": int}}
    """
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": normalize_category_name(category),
        "gcmlimit": "500",
        "gcmnamespace": "0",
        "gcmtype": "page",
        "prop": "langlinks|info",
        "lllang": config.TARGET_LANG,
        "lllimit": "max",
        "redirects": "1",
    }

    pages: Dict[str, Dict[str, Any]] = {}
    cont: Dict[str, str] = {}
    requests_made = 0

    while True:
        data = wiki_api({**params, **cont}, lang=config.SOURCE_LANG)
        requests_made += 1

        for page in data.get("query", {}).get("pages", []):
            title = page["title"]
            langlinks = page.get("langlinks", [])
            uz_title = langlinks[0]["title"] if langlinks else None

            rec = pages.setdefault(title, {"uz": None, "size": 0})
            # Continuation can split a page's props across responses —
            # never overwrite a known value with an empty one.
            rec["uz"] = rec["uz"] or uz_title
            rec["size"] = rec["size"] or page.get("length", 0)

        if "continue" not in data:
            break
        cont = data["continue"]

    logger.debug(f"{requests_made} ta API so'rovi bajarildi.")
    return pages


def fetch_category_uz_status(category: str) -> Dict[str, Optional[str]]:
    """{article_title: uz_title or None} — the shape category-checker.py wants."""
    return {t: rec["uz"] for t, rec in fetch_category_members(category).items()}


def fetch_article_categories(title: str) -> List[str]:
    """
    The visible categories of one article.

    This is how the agent moves on: when a category is finished it opens an
    article from it and picks one of that article's other categories.
    """
    data = wiki_api({
        "action": "query",
        "titles": title,
        "prop": "categories",
        "clshow": "!hidden",
        "cllimit": "max",
        "redirects": "1",
    }, lang=config.SOURCE_LANG)

    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        return []
    return [c["title"] for c in pages[0].get("categories", [])]


def fetch_category_parents(category: str) -> List[str]:
    """The categories a category itself belongs to."""
    data = wiki_api({
        "action": "query",
        "titles": normalize_category_name(category),
        "prop": "categories",
        "clshow": "!hidden",
        "cllimit": "max",
    }, lang=config.SOURCE_LANG)

    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        return []
    return [c["title"] for c in pages[0].get("categories", [])]


def fetch_subcategories(category: str) -> List[str]:
    """The categories directly beneath a category."""
    data = wiki_api({
        "action": "query",
        "list": "categorymembers",
        "cmtitle": normalize_category_name(category),
        "cmtype": "subcat",
        "cmlimit": "max",
    }, lang=config.SOURCE_LANG)

    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


def fetch_titles_info(titles: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Byte size and Uzbek interwiki for a list of article titles.

    Used when queueing titles the agent names directly: it confirms the
    article exists and is still missing from uz.wiki before it takes a slot
    in the day's batch.

    Returns {en_title: {"uz": uz_title or None, "size": int, "missing": bool}}
    keyed by the RESOLVED title, plus an entry for every redirect source that
    pointed at one.
    """
    out: Dict[str, Dict[str, Any]] = {}

    for i in range(0, len(titles), config.API_BATCH_SIZE):
        chunk = titles[i:i + config.API_BATCH_SIZE]
        data = wiki_api({
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "langlinks|info",
            "lllang": config.TARGET_LANG,
            "lllimit": "max",
            "redirects": "1",
        }, lang=config.SOURCE_LANG)

        query = data.get("query", {})

        resolved: Dict[str, str] = {}
        for kind in ("normalized", "redirects"):
            for item in query.get(kind, []):
                resolved[item["from"]] = item["to"]

        for page in query.get("pages", []):
            langlinks = page.get("langlinks", [])
            out[page["title"]] = {
                "uz": langlinks[0]["title"] if langlinks else None,
                "size": page.get("length", 0),
                "missing": "missing" in page,
            }

        # A title the caller typed may have been normalised or redirected;
        # let them look it up under the name they used.
        for src, dst in resolved.items():
            if dst in out:
                out[src] = out[dst]

    return out


# Categories that settle the question of whether an article is on a radical
# topic. They are matched as substrings of the category name, so the
# nationality-scoped variants ("Moroccan Salafis", "Albanian Salafis") are
# covered without enumerating them.
#
# "Living people" is in the list not because it is disqualifying but because
# a living religious figure needs a human-grade look, which is exactly what
# the screening agent is for.
_RISK_PATTERNS = [
    r'salafi', r'wahhab', r'jihad', r'terroris[tm]', r'militant',
    r'al-qaeda', r'taliban', r'islamic state', r'isil\b', r'boko haram',
    r'al-shabaab', r'lashkar', r'muslim brotherhood', r'hizb ut-tahrir',
    r'ahl-i hadith', r'ahl al-hadith', r'islamis[tm]', r'extremis',
    r'insurgen', r'suicide bomb', r'takfir', r'assassin',
    r'people convicted', r'prisoners', r'living people',
    # Armed movements that name themselves after a cause rather than a creed.
    # "Moro Islamic Liberation Front members" was read as CLEAR until this
    # line existed - the words Salafi, jihad and militant never appear in it.
    r'liberation front', r'liberation movement', r'liberation organisation',
    r'mujahid', r'separatis', r'paramilitary', r'guerrilla', r'warlord',
    r'hamas', r'hezbollah|hizbullah|hizballah', r'armed group', r'rebel',
]

_RISK_RE = re.compile("|".join(_RISK_PATTERNS), re.IGNORECASE)


def risky_categories(categories: List[str]) -> List[str]:
    """The subset of an article's categories that call for a human judgment."""
    return [c for c in categories if _RISK_RE.search(strip_category_prefix(c))]


def fetch_titles_categories(titles: List[str]) -> Dict[str, List[str]]:
    """
    The visible categories of many articles, batched.

    One request per API_BATCH_SIZE titles, so screening a whole category
    listing costs about one round trip per 50 candidates.
    """
    out: Dict[str, List[str]] = {}

    for i in range(0, len(titles), config.API_BATCH_SIZE):
        chunk = titles[i:i + config.API_BATCH_SIZE]
        cont: Dict[str, str] = {}

        while True:
            data = wiki_api({
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "categories",
                "clshow": "!hidden",
                "cllimit": "max",
                "redirects": "1",
                **cont,
            }, lang=config.SOURCE_LANG)

            query = data.get("query", {})
            for page in query.get("pages", []):
                names = [c["title"] for c in page.get("categories", [])]
                out.setdefault(page["title"], []).extend(names)

            # A batch of 50 articles easily exceeds one response's category
            # allowance, and the rest arrive under "continue".
            if "continue" not in data:
                break
            cont = data["continue"]

        for kind in ("normalized", "redirects"):
            for item in query.get(kind, []):
                if item["to"] in out:
                    out[item["from"]] = out[item["to"]]

    return out
