#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
article_finder.py - Kategoriya bo'yicha maqolalarni topish
O'zbek Vikipediyada yo'q maqolalarni filtrlash va hajmi bo'yicha saralash.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Tuple

# Pywikibot sozlash
import os
os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "2")

import pywikibot


# ==================== WIKIPEDIA API ====================

def get_category_members(category: str, lang: str = "en", limit: int = 500) -> List[str]:
    """
    Kategoriya ichidagi barcha maqolalarni olish.
    Faqat maqolalar (namespace=0), subkategoriyalar emas.
    """
    members = []
    cmcontinue = ""

    while True:
        params = urllib.parse.urlencode({
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmtype": "page",
            "cmnamespace": "0",
            "cmlimit": str(limit),
            "format": "json",
            "formatversion": "2",
        })
        if cmcontinue:
            params += f"&cmcontinue={urllib.parse.quote(cmcontinue)}"
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        if cmcontinue:
            url += f"&cmcontinue={urllib.parse.quote(cmcontinue)}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "WikiTranslatorBot/1.0 (Uzbek Wikipedia)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for page in data.get("query", {}).get("categorymembers", []):
            members.append(page["title"])

        cont = data.get("continue", {})
        if "cmcontinue" in cont:
            cmcontinue = cont["cmcontinue"]
        else:
            break

    return members


def get_article_sizes(titles: List[str], lang: str = "en") -> Dict[str, int]:
    """
    Maqolalar hajmini (bayt) olish. Batch API bilan 50 talab.
    """
    sizes = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        joined = "|".join(urllib.parse.quote(t) for t in batch)
        url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&titles={joined}&prop=revisions"
            f"&rvprop=size&format=json&formatversion=2"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "WikiTranslatorBot/1.0 (Uzbek Wikipedia)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for page in data.get("query", {}).get("pages", []):
            if not page.get("missing"):
                title = page["title"]
                revs = page.get("revisions", [{}])
                sizes[title] = revs[0].get("size", 0) if revs else 0

    return sizes


def fetch_wikitext(title: str, lang: str = "en") -> Optional[str]:
    """Maqolaning wikitext'ini olish."""
    encoded = urllib.parse.quote(title)
    url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&titles={encoded}&prop=revisions"
        f"&rvprop=content&rvslots=main&format=json&formatversion=2"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WikiTranslatorBot/1.0 (Uzbek Wikipedia)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    slots = page.get("revisions", [{}])[0].get("slots", {})
    return slots.get("main", {}).get("content")


# ==================== WIKIDATA TEKSHIRISH ====================

def check_uz_exists_batch(titles: List[str]) -> Dict[str, bool]:
    """
    Maqolalarning o'zbekcha Vikipediyada mavjudligini tekshirish.
    Wikidata API (wbgetentities) orqali batch tekshirish.
    """
    results = {t: False for t in titles}
    site_en = pywikibot.Site("en", "wikipedia")

    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        for title in batch:
            try:
                page = pywikibot.Page(site_en, title)
                if not page.exists():
                    continue
                item = pywikibot.ItemPage.fromPage(page)
                item.get()
                if "uzwiki" in item.sitelinks:
                    results[title] = True
            except Exception:
                pass

    return results


# ==================== MAQOLA QISQARTIRISH ====================

def estimate_trimmed(wikitext: str) -> Tuple[Optional[str], int]:
    """
    Maqolani qisqartirish: intro + manbalar qismini ajratish.

    Qoida: birinchi == == dan == References == / == Sources == gacha olib tashlash.
    Kamida 1 ta <ref bo'lishi kerak.

    Returns:
        (qisqartirilgan_matn, hajm) yoki (None, 0) agar mos kelmasa
    """
    if not wikitext:
        return None, 0

    # Birinchi section headerini topish
    first_section = re.search(r'^(==[^=])', wikitext, re.MULTILINE)
    if not first_section:
        return None, 0

    intro = wikitext[:first_section.start()]

    # References/Sources/Bibliography section'ni topish
    ref_match = re.search(
        r'^(==\s*(?:References|Sources|Bibliography|Notes|Further reading|External links)\s*==)',
        wikitext, re.MULTILINE | re.IGNORECASE
    )
    if not ref_match:
        return None, 0

    tail = wikitext[ref_match.start():]

    trimmed = intro.rstrip() + "\n\n" + tail

    # Kamida 1 ta manba borligini tekshirish
    if "<ref" not in trimmed.lower():
        return None, 0

    return trimmed, len(trimmed)


# ==================== NATIJALARNI KO'RSATISH ====================

def format_size(size_bytes: int) -> str:
    """Hajmni o'qiladigan formatda ko'rsatish."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    return f"{size_bytes / 1024:.1f} KB"


def display_results(articles: List[Dict], category: str):
    """Topilgan maqolalarni jadval ko'rinishida chiqarish."""
    print(f"\n{'=' * 70}")
    print(f"  Kategoriya: {category}")
    print(f"  O'zbek Vikipediyada yo'q maqolalar: {len(articles)} ta")
    print(f"{'=' * 70}")

    if not articles:
        print("  Barcha maqolalar allaqachon o'zbekchada mavjud!")
        return

    print(f"\n  {'#':>3}  {'Maqola':40s}  {'Hajm':>8s}  {'Qisqa':>8s}")
    print(f"  {'─' * 3}  {'─' * 40}  {'─' * 8}  {'─' * 8}")

    for i, art in enumerate(articles, 1):
        name = art["title"]
        if len(name) > 38:
            name = name[:35] + "..."
        size_str = format_size(art["size"])
        trim_str = format_size(art["trimmed_size"]) if art["trimmed_size"] > 0 else "—"
        print(f"  {i:3d}  {name:40s}  {size_str:>8s}  {trim_str:>8s}")

    print(f"\n  Jami: {len(articles)} ta maqola")
    print(f"  'Qisqa' = intro + manbalar qismi hajmi\n")


# ==================== ASOSIY FUNKSIYA ====================

def find_articles(category: str, max_size: int = 0, check_trim: bool = True) -> List[Dict]:
    """
    Kategoriyadan o'zbekchada yo'q maqolalarni topish.

    Args:
        category: Wikipedia kategoriya nomi (Category: prefikssiz)
        max_size: Maksimal hajm (0 = cheklovsiz)
        check_trim: Katta maqolalar uchun qisqartirilgan hajmni hisoblash

    Returns:
        Saralangan maqolalar ro'yxati
    """
    print(f"\n⏳ Kategoriya a'zolarini olish: {category}")
    members = get_category_members(category)
    print(f"  Topildi: {len(members)} ta maqola")

    if not members:
        return []

    print(f"⏳ Maqola hajmlarini olish...")
    sizes = get_article_sizes(members)

    print(f"⏳ O'zbek Vikipediyada mavjudligini tekshirish...")
    uz_exists = check_uz_exists_batch(members)

    # Faqat o'zbekchada yo'qlarini filtrlash
    missing = [t for t in members if not uz_exists.get(t, False)]
    print(f"  O'zbekchada yo'q: {len(missing)} ta")

    articles = []
    for title in missing:
        size = sizes.get(title, 0)
        if max_size > 0 and size > max_size:
            continue
        articles.append({
            "title": title,
            "size": size,
            "trimmed_size": 0,
        })

    # Hajm bo'yicha saralash (kichikdan kattaga)
    articles.sort(key=lambda x: x["size"])

    # Qisqartirilgan hajmni hisoblash (faqat katta maqolalar uchun)
    if check_trim:
        big_threshold = 15000  # 15KB dan katta maqolalar uchun
        big_articles = [a for a in articles if a["size"] > big_threshold]
        if big_articles:
            print(f"⏳ Katta maqolalar uchun qisqartirilgan hajm hisoblanmoqda ({len(big_articles)} ta)...")
            for art in big_articles:
                wikitext = fetch_wikitext(art["title"])
                if wikitext:
                    _, trim_size = estimate_trimmed(wikitext)
                    art["trimmed_size"] = trim_size

    return articles


def select_and_save(articles: List[Dict]):
    """
    Foydalanuvchi maqola tanlashi va input_en.txt ga saqlashi.
    """
    while True:
        choice = input("\n  Maqola raqamini kiriting (0 = chiqish): ").strip()
        if choice == "0" or not choice:
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(articles):
                art = articles[idx]
                title = art["title"]
                print(f"\n⏳ '{title}' yuklanmoqda...")

                wikitext = fetch_wikitext(title)
                if not wikitext:
                    print("  ❌ Wikitext yuklab bo'lmadi")
                    continue

                # Hajm katta bo'lsa, qisqartirishni taklif qilish
                if art["size"] > 15000 and art["trimmed_size"] > 0:
                    trim_choice = input(
                        f"  Maqola katta ({format_size(art['size'])}). "
                        f"Qisqartirilsin ({format_size(art['trimmed_size'])})? [H/y]: "
                    ).strip().lower()
                    if trim_choice in ("h", "ha", "y", "yes", ""):
                        trimmed, _ = estimate_trimmed(wikitext)
                        if trimmed:
                            wikitext = trimmed
                            print(f"  ✂️  Qisqartirildi: {format_size(len(wikitext))}")

                with open("input_en.txt", "w", encoding="utf-8") as f:
                    f.write(wikitext)
                print(f"  ✅ input_en.txt ga saqlandi ({format_size(len(wikitext))})")
                print(f"  ▶ Tarjima: python main.py input_en.txt output_uz.txt")
                break
            else:
                print("  ❌ Noto'g'ri raqam")
        except ValueError:
            print("  ❌ Raqam kiriting")


# ==================== CLI ====================

def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Foydalanish:")
        print("  python article_finder.py 'Kategoriya nomi'")
        print("  python article_finder.py '11th-century Arabic-language poets'")
        print("  python article_finder.py '11th-century Arabic-language poets' --max-size 50000")
        sys.exit(1)

    category = sys.argv[1]

    max_size = 0
    if "--max-size" in sys.argv:
        idx = sys.argv.index("--max-size")
        if idx + 1 < len(sys.argv):
            max_size = int(sys.argv[idx + 1])

    articles = find_articles(category, max_size=max_size)
    display_results(articles, category)

    if articles and sys.stdin.isatty():
        select_and_save(articles)


if __name__ == "__main__":
    main()
