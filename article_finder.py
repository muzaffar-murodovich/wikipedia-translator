#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
article_finder.py - Maqolalarni avtomatik topish
Seed kategoriyalardan BFS crawl, uz.wiki tekshiruv, progress tracking.
Argumentsiz: avtomatik rejim. Argument bilan: legacy rejim.
"""

import collections
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Pywikibot sozlash
import os
os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "2")

import pywikibot

import config


# ==================== WIKIPEDIA API ====================

USER_AGENT = "WikiTranslatorBot/1.0 (Uzbek Wikipedia)"


def _wiki_api(params: dict, lang: str = "en", domain: str = "wikipedia") -> dict:
    """Wikipedia/Wikidata API ga so'rov yuborish."""
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    encoded = urllib.parse.urlencode(params)
    if domain == "wikidata":
        url = f"https://www.wikidata.org/w/api.php?{encoded}"
    else:
        url = f"https://{lang}.wikipedia.org/w/api.php?{encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_category_members(category: str, lang: str = "en", limit: int = 500) -> List[str]:
    """
    Kategoriya ichidagi barcha maqolalarni olish.
    Faqat maqolalar (namespace=0), subkategoriyalar emas.
    """
    members = []
    cmcontinue = ""

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmtype": "page",
            "cmnamespace": "0",
            "cmlimit": str(limit),
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = _wiki_api(params, lang)

        for page in data.get("query", {}).get("categorymembers", []):
            members.append(page["title"])

        cont = data.get("continue", {})
        if "cmcontinue" in cont:
            cmcontinue = cont["cmcontinue"]
        else:
            break

    return members


def get_subcategories(category: str, lang: str = "en") -> List[str]:
    """
    Kategoriya ichidagi subkategoriyalarni olish.
    """
    subcats = []
    cmcontinue = ""

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmtype": "subcat",
            "cmlimit": "500",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = _wiki_api(params, lang)

        for page in data.get("query", {}).get("categorymembers", []):
            # "Category:Name" dan "Name" ni ajratish
            title = page["title"]
            if title.startswith("Category:"):
                title = title[len("Category:"):]
            subcats.append(title)

        cont = data.get("continue", {})
        if "cmcontinue" in cont:
            cmcontinue = cont["cmcontinue"]
        else:
            break

    return subcats


def get_article_sizes(titles: List[str], lang: str = "en") -> Dict[str, int]:
    """Maqolalar hajmini (bayt) olish. Batch API bilan 50 talab."""
    sizes = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        joined = "|".join(batch)
        data = _wiki_api({
            "action": "query",
            "titles": joined,
            "prop": "revisions",
            "rvprop": "size",
        }, lang)

        for page in data.get("query", {}).get("pages", []):
            if not page.get("missing"):
                title = page["title"]
                revs = page.get("revisions", [{}])
                sizes[title] = revs[0].get("size", 0) if revs else 0

    return sizes


def fetch_wikitext(title: str, lang: str = "en") -> Optional[str]:
    """Maqolaning wikitext'ini olish."""
    data = _wiki_api({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
    }, lang)

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
    Pywikibot orqali (sekin, legacy rejim uchun).
    """
    results = {t: False for t in titles}
    site_en = pywikibot.Site("en", "wikipedia")

    for title in titles:
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


def check_uz_exists_batch_fast(titles: List[str]) -> Dict[str, bool]:
    """
    Tezlashtirilgan uz.wiki mavjudlik tekshiruvi.
    Wikidata wbgetentities API bilan 50 talab batch tekshirish.
    Pywikibot yondashuvdan ~50x tez.
    """
    results = {t: False for t in titles}

    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        joined = "|".join(batch)
        try:
            data = _wiki_api({
                "action": "wbgetentities",
                "sites": "enwiki",
                "titles": joined,
                "props": "sitelinks",
                "sitefilter": "uzwiki",
            }, domain="wikidata")

            for entity_id, entity in data.get("entities", {}).items():
                if entity_id.startswith("-"):
                    continue
                sitelinks = entity.get("sitelinks", {})
                if "uzwiki" in sitelinks:
                    # enwiki sitelink'dan asl nomni olish
                    # entity'dagi title normallashgan bo'lishi mumkin
                    en_title = sitelinks.get("enwiki", {}).get("title", "")
                    if en_title in results:
                        results[en_title] = True
                    else:
                        # Normallashmagan nomni tekshirish
                        for t in batch:
                            if t.replace(" ", "_") == en_title.replace(" ", "_"):
                                results[t] = True
                                break
        except Exception as e:
            print(f"  ⚠️  Wikidata batch xatosi: {e}")
            # Fallback: bu batch'ni pywikibot bilan tekshirish
            fallback = check_uz_exists_batch(batch)
            results.update(fallback)

    return results


# ==================== BFS CRAWL ====================

def crawl_category_tree(root_category: str, max_depth: int = 3,
                        cached_tree: Optional[Dict] = None) -> List[str]:
    """
    BFS orqali kategoriya daraxtini kezish.

    Args:
        root_category: Boshlang'ich kategoriya
        max_depth: Maksimal chuqurlik (0 = faqat root)
        cached_tree: Oldindan cache'langan subcategory tree

    Returns:
        Barcha topilgan kategoriyalar ro'yxati (root dahil)
    """
    if cached_tree is None:
        cached_tree = {}

    visited = set()
    queue = collections.deque([(root_category, 0)])
    all_categories = []

    while queue:
        category, depth = queue.popleft()

        if category in visited:
            continue
        visited.add(category)
        all_categories.append(category)

        if depth >= max_depth:
            continue

        # Cache'dan yoki API'dan subcategory olish
        if category in cached_tree:
            subcats = cached_tree[category]
        else:
            try:
                subcats = get_subcategories(category)
                cached_tree[category] = subcats
            except Exception as e:
                print(f"  ⚠️  Subkategoriya olishda xato: {category} - {e}")
                subcats = []

        for subcat in subcats:
            if subcat not in visited:
                queue.append((subcat, depth + 1))

    return all_categories


# ==================== MAQOLA QISQARTIRISH ====================

def estimate_trimmed(wikitext: str) -> Tuple[Optional[str], int]:
    """
    Maqolani qisqartirish: intro + manbalar qismini ajratish.
    Qoida: birinchi == == dan == References == gacha olib tashlash.
    Kamida 1 ta <ref bo'lishi kerak.
    """
    if not wikitext:
        return None, 0

    first_section = re.search(r'^(==[^=])', wikitext, re.MULTILINE)
    if not first_section:
        return None, 0

    intro = wikitext[:first_section.start()]

    ref_match = re.search(
        r'^(==\s*(?:References|Sources|Bibliography|Notes|Further reading|External links)\s*==)',
        wikitext, re.MULTILINE | re.IGNORECASE
    )
    if not ref_match:
        return None, 0

    tail = wikitext[ref_match.start():]
    trimmed = intro.rstrip() + "\n\n" + tail

    if "<ref" not in trimmed.lower():
        return None, 0

    return trimmed, len(trimmed)


# ==================== PROGRESS TRACKING ====================

class FinderProgress:
    """
    Maqola topish jarayonini kuzatish.
    .wiki_cache/finder_progress.json bilan ishlash.
    """

    def __init__(self):
        self.filepath = str(config.FINDER_PROGRESS_FILE)
        self.data = self.load()

    def load(self) -> dict:
        """Progress faylni yuklash yoki yangi yaratish."""
        try:
            if Path(self.filepath).exists():
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"  ⚠️  Progress fayl xatosi, yangi yaratilmoqda: {e}")
        return {
            "categories_scanned": {},
            "articles": {},
            "subcategory_tree": {},
        }

    def save(self):
        """Progress'ni saqlash."""
        self.data["last_run"] = datetime.now().isoformat()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ❌ Progress saqlashda xato: {e}")

    def mark_category_scanned(self, category: str, total: int, missing: int,
                              parent: Optional[str] = None, depth: int = 0):
        """Kategoriyani skanerlangan deb belgilash."""
        self.data["categories_scanned"][category] = {
            "status": "complete",
            "scanned_at": datetime.now().isoformat(),
            "total": total,
            "missing": missing,
            "parent": parent,
            "depth": depth,
        }

    def mark_article_discovered(self, title: str, size: int, trimmed_size: int = 0,
                                categories: Optional[List[str]] = None):
        """Yangi maqolani pending statusda saqlash."""
        if title not in self.data["articles"]:
            self.data["articles"][title] = {
                "status": "pending",
                "size": size,
                "trimmed_size": trimmed_size,
                "categories": categories or [],
                "discovered_at": datetime.now().isoformat(),
            }
        else:
            # Mavjud maqolaga kategoriya qo'shish
            art = self.data["articles"][title]
            if categories:
                existing_cats = art.get("categories", [])
                for cat in categories:
                    if cat not in existing_cats:
                        existing_cats.append(cat)
                art["categories"] = existing_cats
            # Hajmni yangilash (eng oxirgi qiymat)
            art["size"] = size

    def mark_article_translated(self, title: str):
        """Maqolani translated deb belgilash."""
        if title in self.data["articles"]:
            self.data["articles"][title]["status"] = "translated"
            self.data["articles"][title]["translated_at"] = datetime.now().isoformat()

    def mark_article_skipped(self, title: str, reason: str = ""):
        """Maqolani skipped deb belgilash."""
        if title in self.data["articles"]:
            self.data["articles"][title]["status"] = "skipped"
            self.data["articles"][title]["reason"] = reason

    def mark_article_has_uz(self, title: str):
        """Maqolani has_uz deb belgilash (o'zbekchada mavjud)."""
        self.data["articles"][title] = {
            "status": "has_uz",
            "discovered_at": datetime.now().isoformat(),
        }

    def get_pending_articles(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Tarjima kutayotgan maqolalarni olish.
        Hajm bo'yicha saralangan (kichikdan kattaga).
        """
        pending = []
        for title, info in self.data["articles"].items():
            if info.get("status") == "pending":
                pending.append({
                    "title": title,
                    "size": info.get("size", 0),
                    "trimmed_size": info.get("trimmed_size", 0),
                    "categories": info.get("categories", []),
                })

        pending.sort(key=lambda x: x["size"])
        return pending[offset:offset + limit]

    def get_pending_count(self) -> int:
        """Pending maqolalar sonini olish."""
        return sum(1 for a in self.data["articles"].values() if a.get("status") == "pending")

    def is_category_scanned(self, category: str) -> bool:
        """Kategoriya allaqachon skanerlanganmi?"""
        return category in self.data["categories_scanned"]

    def get_stats(self) -> Dict:
        """Umumiy statistika."""
        articles = self.data["articles"]
        cats = self.data["categories_scanned"]
        return {
            "total_articles": len(articles),
            "pending": sum(1 for a in articles.values() if a.get("status") == "pending"),
            "translated": sum(1 for a in articles.values() if a.get("status") == "translated"),
            "skipped": sum(1 for a in articles.values() if a.get("status") == "skipped"),
            "has_uz": sum(1 for a in articles.values() if a.get("status") == "has_uz"),
            "categories_scanned": len(cats),
        }


# ==================== SEED KATEGORIYALAR ====================

def load_seed_categories() -> List[Dict]:
    """
    seed_categories.json ni yuklash.
    Faqat enabled=True, priority bo'yicha saralangan.
    """
    filepath = str(config.SEED_CATEGORIES_FILE)
    if not Path(filepath).exists():
        print(f"  ❌ {filepath} topilmadi!")
        print(f"  seed_categories.json yarating yoki kategoriya nomi bilan ishga tushiring:")
        print(f"  python article_finder.py 'Kategoriya nomi'")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ❌ seed_categories.json o'qishda xato: {e}")
        return []

    categories = data.get("categories", [])
    # Faqat enabled=True, priority bo'yicha saralash
    enabled = [c for c in categories if c.get("enabled", True)]
    enabled.sort(key=lambda x: x.get("priority", 99))
    return enabled


# ==================== NATIJALARNI KO'RSATISH ====================

def format_size(size_bytes: int) -> str:
    """Hajmni o'qiladigan formatda ko'rsatish."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    return f"{size_bytes / 1024:.1f} KB"


def display_results(articles: List[Dict], category: str):
    """Topilgan maqolalarni jadval ko'rinishida chiqarish (legacy rejim)."""
    print(f"\n{'=' * 70}")
    print(f"  Kategoriya: {category}")
    print(f"  O'zbek Vikipediyada yo'q maqolalar: {len(articles)} ta")
    print(f"{'=' * 70}")

    if not articles:
        print("  Barcha maqolalar allaqachon o'zbekchada mavjud!")
        return

    _print_article_table(articles)


def display_auto_results(articles: List[Dict], stats: Dict, page: int = 1):
    """Avtomatik rejim natijalari + statistika."""
    page_size = config.FINDER_PAGE_SIZE
    total_pages = max(1, (stats["pending"] + page_size - 1) // page_size)

    print(f"\n{'=' * 70}")
    print(f"  MAQOLA TOPISH — Avtomatik rejim")
    print(f"  Topilgan: {stats['total_articles']} | Kutayotgan: {stats['pending']}"
          f" | Tarjima: {stats['translated']} | Uz mavjud: {stats['has_uz']}")
    print(f"  Skanerlangan kategoriyalar: {stats['categories_scanned']}")
    print(f"{'=' * 70}")

    if not articles:
        print("\n  Tarjima kutayotgan maqolalar yo'q. [s] bosib skanerlang.")
        return

    print(f"\n  Sahifa {page}/{total_pages} (hajm bo'yicha saralangan)")
    _print_article_table(articles)


def _print_article_table(articles: List[Dict]):
    """Maqolalar jadvalini chiqarish."""
    print(f"\n  {'#':>3}  {'Maqola':40s}  {'Hajm':>8s}  {'Qisqa':>8s}")
    print(f"  {'─' * 3}  {'─' * 40}  {'─' * 8}  {'─' * 8}")

    for i, art in enumerate(articles, 1):
        name = art["title"]
        if len(name) > 38:
            name = name[:35] + "..."
        size_str = format_size(art["size"])
        trim_str = format_size(art["trimmed_size"]) if art.get("trimmed_size", 0) > 0 else "—"
        print(f"  {i:3d}  {name:40s}  {size_str:>8s}  {trim_str:>8s}")

    print(f"\n  Jami: {len(articles)} ta maqola")


# ==================== LEGACY REJIM ====================

def find_articles(category: str, max_size: int = 0, check_trim: bool = True) -> List[Dict]:
    """
    Kategoriyadan o'zbekchada yo'q maqolalarni topish (legacy rejim).
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

    missing = [t for t in members if not uz_exists.get(t, False)]
    print(f"  O'zbekchada yo'q: {len(missing)} ta")

    articles = []
    for title in missing:
        size = sizes.get(title, 0)
        if max_size > 0 and size > max_size:
            continue
        articles.append({"title": title, "size": size, "trimmed_size": 0})

    articles.sort(key=lambda x: x["size"])

    if check_trim:
        big_threshold = config.FINDER_TRIM_THRESHOLD
        big_articles = [a for a in articles if a["size"] > big_threshold]
        if big_articles:
            print(f"⏳ Katta maqolalar uchun qisqartirilgan hajm ({len(big_articles)} ta)...")
            for art in big_articles:
                wikitext = fetch_wikitext(art["title"])
                if wikitext:
                    _, trim_size = estimate_trimmed(wikitext)
                    art["trimmed_size"] = trim_size

    return articles


# ==================== INTERAKTIV TANLASH ====================

def select_and_save(articles: List[Dict], progress: Optional[FinderProgress] = None):
    """Foydalanuvchi maqola tanlashi va input_en.txt ga saqlashi."""
    while True:
        choice = input("\n  Tanlang: ").strip()

        if choice in ("0", "q", ""):
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
                if art["size"] > config.FINDER_TRIM_THRESHOLD:
                    trimmed, trim_size = estimate_trimmed(wikitext)
                    if trimmed and trim_size > 0:
                        trim_choice = input(
                            f"  Maqola katta ({format_size(art['size'])}). "
                            f"Qisqartirilsin ({format_size(trim_size)})? [H/y]: "
                        ).strip().lower()
                        if trim_choice in ("h", "ha", "y", "yes", ""):
                            wikitext = trimmed
                            print(f"  ✂️  Qisqartirildi: {format_size(len(wikitext))}")

                with open("input_en.txt", "w", encoding="utf-8") as f:
                    f.write(wikitext)
                print(f"  ✅ input_en.txt ga saqlandi ({format_size(len(wikitext))})")
                print(f"  ▶ Tarjima: python main.py input_en.txt output_uz.txt")

                # Progress'da belgilash
                if progress:
                    progress.mark_article_translated(title)
                    progress.save()

                break
            else:
                print("  ❌ Noto'g'ri raqam")
        except ValueError:
            print("  ❌ Raqam kiriting")


# ==================== AVTOMATIK REJIM ====================

def scan_categories(progress: FinderProgress, seeds: List[Dict], target_pending: int = 20):
    """
    Seed kategoriyalarni BFS crawl + skanerlash.
    target_pending ta pending to'plangach to'xtatish.
    """
    cached_tree = progress.data.get("subcategory_tree", {})

    for seed in seeds:
        name = seed["name"]
        depth = seed.get("depth", config.FINDER_MAX_DEPTH)

        print(f"\n⏳ Kategoriya daraxti: {name} (chuqurlik: {depth})")
        categories = crawl_category_tree(name, max_depth=depth, cached_tree=cached_tree)
        progress.data["subcategory_tree"] = cached_tree
        print(f"  Topildi: {len(categories)} ta kategoriya")

        for category in categories:
            if progress.is_category_scanned(category):
                continue

            print(f"  📂 Skanerlanmoqda: {category}", end="", flush=True)

            try:
                members = get_category_members(category)
            except Exception as e:
                print(f" — xato: {e}")
                continue

            if not members:
                progress.mark_category_scanned(category, 0, 0, parent=name)
                print(f" — bo'sh")
                continue

            # Allaqachon ma'lum maqolalarni filtrlash
            new_members = [m for m in members if m not in progress.data["articles"]]

            if not new_members:
                progress.mark_category_scanned(category, len(members), 0, parent=name)
                print(f" — {len(members)} ta (barchasi ma'lum)")
                continue

            # Hajmlarni olish
            sizes = get_article_sizes(new_members)

            # Uz.wiki mavjudligini tez tekshirish
            uz_exists = check_uz_exists_batch_fast(new_members)

            missing_count = 0
            for title in new_members:
                if uz_exists.get(title, False):
                    progress.mark_article_has_uz(title)
                else:
                    size = sizes.get(title, 0)
                    progress.mark_article_discovered(title, size, categories=[category])
                    missing_count += 1

            progress.mark_category_scanned(category, len(members), missing_count, parent=name)
            progress.save()

            print(f" — {len(members)} ta, {missing_count} ta yo'q")

            # Yetarli pending to'plandimi?
            if progress.get_pending_count() >= target_pending:
                print(f"\n  ✅ {progress.get_pending_count()} ta pending maqola to'plandi")
                return

    progress.save()


def auto_discover():
    """
    Avtomatik maqola topish rejimi (argumentsiz).
    """
    seeds = load_seed_categories()
    if not seeds:
        return

    progress = FinderProgress()
    stats = progress.get_stats()
    page = 1
    page_size = config.FINDER_PAGE_SIZE

    # Agar pending maqolalar yo'q bo'lsa — skanerlash
    if stats["pending"] == 0:
        print("⏳ Yangi maqolalar izlanmoqda...")
        scan_categories(progress, seeds, target_pending=page_size)
        stats = progress.get_stats()

    # Asosiy menyu loop
    while True:
        offset = (page - 1) * page_size
        articles = progress.get_pending_articles(limit=page_size, offset=offset)
        stats = progress.get_stats()

        display_auto_results(articles, stats, page)

        if not sys.stdin.isatty():
            break

        total_pages = max(1, (stats["pending"] + page_size - 1) // page_size)
        print(f"  [1-{len(articles)}] tanlash | [n] keyingi | [p] oldingi | [s] skanerlash | [0] chiqish")

        choice = input("\n  Tanlang: ").strip().lower()

        if choice in ("0", "q", ""):
            break
        elif choice == "n":
            if page < total_pages:
                page += 1
            else:
                print("  Oxirgi sahifa.")
        elif choice == "p":
            if page > 1:
                page -= 1
            else:
                print("  Birinchi sahifa.")
        elif choice == "s":
            print()
            scan_categories(progress, seeds, target_pending=stats["pending"] + page_size)
            page = 1
        elif choice == "i":
            s = progress.get_stats()
            print(f"\n  📊 Statistika:")
            print(f"     Jami topilgan:  {s['total_articles']}")
            print(f"     Kutayotgan:     {s['pending']}")
            print(f"     Tarjima:        {s['translated']}")
            print(f"     O'zbekchada:    {s['has_uz']}")
            print(f"     O'tkazilgan:    {s['skipped']}")
            print(f"     Kategoriyalar:  {s['categories_scanned']}")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(articles):
                    select_and_save([articles[idx]], progress)
                    page = 1  # Sahifani yangilash
                else:
                    print("  ❌ Noto'g'ri raqam")
            except ValueError:
                print("  ❌ Noto'g'ri buyruq")


# ==================== CLI ====================

def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        # AVTOMATIK REJIM
        auto_discover()
        return

    # LEGACY REJIM: kategoriya nomi bilan
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
