#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
additional-tools/category-checker.py
Check which articles in an English Wikipedia category
are missing from Uzbek Wikipedia.
"""

import os
import sys
import argparse
import webbrowser
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# Project root setup — must happen before any project imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)
os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "2")

import config
from core.cache_manager import WikiCache
from core.wikidata_fetcher import WikidataFetcher
from utils.file_handler import FileHandler
from utils.logger import logger

_SCRIPT_DIR = Path(__file__).resolve().parent


def normalize_category_name(name: str) -> str:
    """Ensure category name has 'Category:' prefix."""
    if name.lower().startswith("category:"):
        return "Category:" + name[len("Category:"):]
    return "Category:" + name


def fetch_category_uz_status(
    fetcher: WikidataFetcher, category: str
) -> Dict[str, Optional[str]]:
    """
    Fetch all article members of a category together with their Uzbek
    interwiki link — in a single API request per 500 members.

    Uses generator=categorymembers + prop=langlinks&lllang=uz, so category
    membership and Uzbek existence come back in one round trip. Interwiki
    links on Wikipedia are served from Wikidata sitelinks, so the result
    matches a per-article Wikidata lookup without the extra requests.

    Args:
        fetcher: WikidataFetcher instance (for its retrying _wiki_api)
        category: Full category name with "Category:" prefix

    Returns:
        {article_title: uz_title or None}
    """
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": category,
        "gcmlimit": "500",
        "gcmnamespace": "0",
        "gcmtype": "page",
        "prop": "langlinks",
        "lllang": config.TARGET_LANG,
        "lllimit": "max",
        "redirects": "1",
    }

    pages: Dict[str, Optional[str]] = {}
    cont: Dict[str, str] = {}
    requests_made = 0

    while True:
        data = fetcher._wiki_api({**params, **cont}, lang=config.SOURCE_LANG)
        requests_made += 1

        for page in data.get("query", {}).get("pages", []):
            langlinks = page.get("langlinks", [])
            uz_title = langlinks[0]["title"] if langlinks else None
            # Continuation can split a page's props across responses —
            # never overwrite a known title with None.
            pages[page["title"]] = pages.get(page["title"]) or uz_title

        if "continue" not in data:
            break
        cont = data["continue"]

    logger.debug(f"{requests_made} ta API so'rovi bajarildi.")
    return pages


def parse_open_arg(value: str) -> Tuple[int, int]:
    """
    Parse --open argument into (start, end) range (1-indexed).

    '10'    -> (1, 10)
    '10-20' -> (10, 20)
    """
    if "-" in value:
        parts = value.split("-", 1)
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Noto'g'ri format: '{value}'. N yoki N-M ko'rinishida bo'lishi kerak."
            )
        if start < 1 or end < start:
            raise argparse.ArgumentTypeError(
                f"Noto'g'ri oraliq: '{value}'. start >= 1 va end >= start bo'lishi kerak."
            )
        return start, end

    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Noto'g'ri format: '{value}'. N yoki N-M ko'rinishida bo'lishi kerak."
        )
    if n < 1:
        raise argparse.ArgumentTypeError("Qiymat 1 dan katta bo'lishi kerak.")
    return 1, n


def make_url(title: str) -> str:
    """Build English Wikipedia URL for an article title."""
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    return f"https://en.wikipedia.org/wiki/{encoded}"


def open_in_browser(titles: List[str], start: int, end: int):
    """Open English Wikipedia articles in the default browser."""
    end = min(end, len(titles))
    start = min(start, end)
    subset = titles[start - 1 : end]

    for title in subset:
        webbrowser.open(make_url(title))

    print(f"\n🌐 {len(subset)} ta maqola brauzerda ochildi ({start}-{end}).")


def save_results_json(
    missing: List[str], category: str, total_in_category: int
) -> str:
    """
    Save missing articles to JSON file.

    Returns:
        Output file path
    """
    sanitized = category.replace("Category:", "").replace(" ", "_").replace("/", "_")
    output_path = str(_SCRIPT_DIR / f"category_check_{sanitized}.json")

    data = {
        "category": category,
        "checked_at": datetime.now().isoformat(),
        "total_in_category": total_in_category,
        "total_missing": len(missing),
        "missing_articles": [
            {"title": title, "url": make_url(title)} for title in missing
        ],
    }

    FileHandler.write_json(output_path, data)
    return output_path


def print_results(missing: List[str], total_in_category: int, category: str):
    """Print results to console."""
    existing_count = total_in_category - len(missing)

    print(f"\n📂 Kategoriya: {category}")
    print(f"   Jami maqolalar: {total_in_category}")
    print(f"   ✅ O'zbekcha mavjud: {existing_count}")
    print(f"   ❌ O'zbekcha mavjud emas: {len(missing)}")

    if not missing:
        print("\n🎉 Barcha maqolalar o'zbekcha Vikipediyada mavjud!")
        return

    print(f"\n{'─' * 60}")
    print("O'zbekcha Vikipediyada mavjud bo'lmagan maqolalar:")
    print(f"{'─' * 60}")

    for i, title in enumerate(missing, 1):
        print(f"{i:>4}. {title}")
        print(f"      {make_url(title)}")


def main():
    parser = argparse.ArgumentParser(
        description="Inglizcha Vikipediya kategoriyasidagi maqolalarning "
        "o'zbekcha Vikipediyada mavjudligini tekshirish."
    )
    parser.add_argument("category", help="Kategoriya nomi (masalan: 'Uzbek writers')")
    parser.add_argument(
        "--open",
        dest="open_range",
        help="Brauzerda ochish: N (birinchi N ta) yoki N-M (oraliq)",
    )

    args = parser.parse_args()

    category = normalize_category_name(args.category)

    open_range = None
    if args.open_range:
        open_range = parse_open_arg(args.open_range)

    logger.section(f"Kategoriya tekshirilmoqda: {category}")

    try:
        # Cache is required by WikidataFetcher; the category query itself
        # needs no per-title lookups.
        fetcher = WikidataFetcher(WikiCache())

        logger.info("Kategoriya a'zolari va o'zbekcha havolalar olinmoqda...")
        pages = fetch_category_uz_status(fetcher, category)

        if not pages:
            print(f"\n⚠️  Kategoriyada maqola topilmadi: {category}")
            sys.exit(0)

        logger.info(f"{len(pages)} ta maqola topildi.")

        missing = sorted(title for title, uz in pages.items() if not uz)

        print_results(missing, len(pages), category)

        if missing:
            output_path = save_results_json(missing, category, len(pages))
            print(f"\n💾 Natijalar saqlandi: {output_path}")

        if open_range and missing:
            open_in_browser(missing, open_range[0], open_range[1])

    except Exception as e:
        logger.fail(f"Xatolik yuz berdi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
