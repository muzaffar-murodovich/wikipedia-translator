#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
additional-tools/category-checker.py
Check which articles in an English Wikipedia category
are missing from Uzbek Wikipedia.
"""

import os
import sys
import time
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

# Project root setup — must happen before any project imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

from finder.wiki import (
    fetch_category_uz_status,
    make_url,
    normalize_category_name,
)
from utils.file_handler import FileHandler
from utils.logger import logger

_SCRIPT_DIR = Path(__file__).resolve().parent


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


def open_in_browser(titles: List[str], start: int, end: int):
    """Open English Wikipedia articles in the default browser."""
    end = min(end, len(titles))
    start = min(start, end)
    subset = titles[start - 1 : end]

    for title in subset:
        webbrowser.open(make_url(title))
        time.sleep(0.5)  # Avoid overwhelming the browser

    print(f"\n🌐 {len(subset)} ta maqola brauzerda ochildi ({start}-{end}).")


def results_path(category: str) -> str:
    """Path of the saved results file for a category."""
    sanitized = category.replace("Category:", "").replace(" ", "_").replace("/", "_")
    return str(_SCRIPT_DIR / f"category_check_{sanitized}.json")


def load_saved_results(category: str) -> Optional[Tuple[List[str], int, str]]:
    """
    Load a previous check of this category from its results file.

    Returns:
        (missing_titles, total_in_category, checked_at) or None when the
        file is absent, unreadable or does not hold the expected fields.
    """
    path = results_path(category)
    if not FileHandler.file_exists(path):
        return None

    data = FileHandler.read_json(path)
    try:
        missing = [article["title"] for article in data["missing_articles"]]
        total = int(data["total_in_category"])
        checked_at = str(data["checked_at"])
    except (KeyError, TypeError, ValueError):
        logger.warning(f"Saqlangan fayl o'qib bo'lmadi, qaytadan tekshiriladi: {path}")
        return None

    return missing, total, checked_at


def describe_age(checked_at: str) -> str:
    """Human-readable age of a saved result, in Uzbek."""
    try:
        delta = datetime.now() - datetime.fromisoformat(checked_at)
    except ValueError:
        return checked_at

    days, hours = delta.days, delta.seconds // 3600
    if days > 0:
        return f"{days} kun oldin"
    if hours > 0:
        return f"{hours} soat oldin"
    return f"{max(delta.seconds // 60, 1)} daqiqa oldin"


def save_results_json(
    missing: List[str], category: str, total_in_category: int
) -> str:
    """
    Save missing articles to JSON file.

    Returns:
        Output file path
    """
    output_path = results_path(category)

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
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Saqlangan natijani e'tiborsiz qoldirib, Vikipediyadan qaytadan tekshirish",
    )

    args = parser.parse_args()

    category = normalize_category_name(args.category)

    open_range = None
    if args.open_range:
        open_range = parse_open_arg(args.open_range)

    logger.section(f"Kategoriya tekshirilmoqda: {category}")

    try:
        saved = None if args.refresh else load_saved_results(category)

        if saved:
            # Oldingi tekshiruv natijasi — Vikipediyaga so'rov yuborilmaydi.
            missing, total, checked_at = saved
            print_results(missing, total, category)
            print(f"\n📄 Saqlangan natija ({describe_age(checked_at)}): "
                  f"{results_path(category)}")
            print("   Yangilash uchun: --refresh")
        else:
            logger.info("Kategoriya a'zolari va o'zbekcha havolalar olinmoqda...")
            pages = fetch_category_uz_status(category)

            if not pages:
                print(f"\n⚠️  Kategoriyada maqola topilmadi: {category}")
                sys.exit(0)

            logger.info(f"{len(pages)} ta maqola topildi.")

            missing = sorted(title for title, uz in pages.items() if not uz)
            total = len(pages)

            print_results(missing, total, category)

            # Har doim saqlanadi — keyingi tekshiruv shu fayldan o'qiydi.
            output_path = save_results_json(missing, category, total)
            print(f"\n💾 Natijalar saqlandi: {output_path}")

        if open_range and missing:
            open_in_browser(missing, open_range[0], open_range[1])

    except Exception as e:
        logger.fail(f"Xatolik yuz berdi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
