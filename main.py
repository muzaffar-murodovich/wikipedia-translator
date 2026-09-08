#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
main.py - Wiki Translator MAIN
Orchestrator for the modular translation pipeline.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

import config
from utils.file_handler import FileHandler
from utils.link_labels import collapse_redundant_labels
from utils.localization import LocalizationManager
from utils.logger import logger
from core.cache_manager import WikiCache
from core.wikidata_fetcher import WikidataFetcher
from core.translator import WikiTranslator
from core.processor import WikiTextProcessor
from core.reviewer import WikiReviewer


def main(input_file: str, output_file: str, article_title: Optional[str] = None):
    """
    Main translation pipeline.

    Phase 1: PREPARE - Prepare wikitext with QID placeholders
    Phase 2: TRANSLATE - Translate via AI
    Phase 3: FINALIZE - Resolve placeholders
    Phase 4: LOCALIZE - Adapt to Uzbek Wikipedia style

    Args:
        input_file: English Wikipedia article file
        output_file: Uzbek Wikipedia article output file
        article_title: English Wikipedia page title, used to name the
            temp_wiki copy. Falls back to the bolded lead name.
    """
    start_time = time.time()

    logger.info(f"📖 Fayl o'qilmoqda: {input_file}")
    raw_text = FileHandler.read_file(input_file)

    if not raw_text:
        logger.fail(f"Fayl bo'sh yoki topilmadi: {input_file}")
        return False

    logger.success(f"Yuklandi ({len(raw_text)} belgi)")

    # Initialize managers
    cache = WikiCache()
    fetcher = WikidataFetcher(cache)
    processor = WikiTextProcessor(fetcher)
    translator = WikiTranslator()
    localization = LocalizationManager()
    reviewer = WikiReviewer()

    logger.success("Tizimlar initialize qilindi")
    logger.info(f"  Localization: {len(localization.map)} ta almashtirish")

    logger.section("📝 PHASE 1: PREPARE")
    prep_start = time.time()

    try:
        prepared_text, link_map, cat_map, tpl_map, ref_map = processor.prepare(raw_text)
        prep_time = time.time() - prep_start
        logger.info(f"  ⏱️  Vaqt: {prep_time:.2f}s")
    except Exception as e:
        logger.critical(f"Prepare phase'da xato: {e}")
        return False

    logger.section("🤖 PHASE 2: TRANSLATE")
    trans_start = time.time()

    try:
        translated_text = translator.translate(prepared_text, processor.unresolved_links)
        if not translated_text:
            logger.fail("Tarjima muvaffaq bo'lmadi")
            return False
        trans_time = time.time() - trans_start
        logger.info(f"  ⏱️  Vaqt: {trans_time:.2f}s")
    except Exception as e:
        logger.critical(f"Translate phase'da xato: {e}")
        return False

    logger.section("🔧 PHASE 3: FINALIZE")
    final_start = time.time()

    try:
        finalized_text = processor.finalize(translated_text, ref_map)
        final_time = time.time() - final_start
        logger.info(f"  ⏱️  Vaqt: {final_time:.2f}s")
    except Exception as e:
        logger.critical(f"Finalize phase'da xato: {e}")
        return False

    logger.section("🌐 PHASE 4: LOCALIZE")
    loc_start = time.time()

    try:
        result = localization.apply(finalized_text)
        loc_time = time.time() - loc_start
        logger.info(f"  ⏱️  Vaqt: {loc_time:.2f}s")
    except Exception as e:
        logger.critical(f"Localize phase'da xato: {e}")
        return False
    
    logger.section("🔍 PHASE 5: REVIEW")
    review_start = time.time()
 
    if not config.ENABLE_REVIEW:
        logger.warning("Phase 5 o'tkazib yuborildi (ENABLE_REVIEW=False)")
        review_time = 0.0
    elif reviewer.is_available():
        try:
            reviewed = reviewer.review(result)
            if reviewed:
                result = reviewed
            else:
                logger.warning("Tahrir muvaffaq bo'lmadi — Phase 4 natijasi saqlanadi")
            review_time = time.time() - review_start
            logger.info(f"  ⏱️  Vaqt: {review_time:.2f}s")
        except Exception as e:
            logger.critical(f"Review phase'da xato: {e}")
            review_time = time.time() - review_start
    else:
        logger.warning("Phase 5 o'tkazib yuborildi (qoidalar fayli topilmadi)")
        review_time = 0.0

    # Rule 2 cleanup — last, because Phase 5 edits links of its own.
    result, label_mismatches = collapse_redundant_labels(result)
    if label_mismatches:
        logger.warning(
            f"{len(label_mismatches)} havolada nom va koʻrinadigan matn farq qiladi "
            "(2-qoida) — qoʻlda tekshiring:"
        )
        for target, label in label_mismatches:
            logger.warning(f"    [[{target}|{label}]]")

    logger.section("💾 SAVE")
    logger.info(f"Yozilmoqda: {output_file}")

    if FileHandler.write_file(output_file, result):
        logger.success(f"Saqlab qo'yildi ({len(result)} belgi)")
    else:
        logger.fail("Fayl yozishda xato!")
        return False

    # Save to temp_wiki. The page title is the article's real identity; the
    # bolded lead name is only a fallback and regularly disagrees with it —
    # "Mian Wada" is bolded as "Mian Muhammad Ismail Suharwardy".
    article_name = article_title
    if not article_name:
        article_match = re.search(r"'''(.+?)'''", raw_text)
        if article_match:
            article_name = article_match.group(1).strip()

    if article_name:
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', article_name)
        temp_dir = Path("temp_wiki")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"{safe_name}.txt"
        if FileHandler.write_file(str(temp_path), result):
            logger.success(f"temp_wiki ga saqlandi: {temp_path}")
        else:
            logger.warning(f"temp_wiki ga yozishda xato: {temp_path}")

    logger.section("📊 STATISTIKA")
    elapsed = time.time() - start_time

    logger.stats(
        "Tarjima Natijalari",
        input_size=f"{len(raw_text)} belgi",
        output_size=f"{len(result)} belgi",
        size_change=f"{len(result) - len(raw_text):+d} ({100*(len(result)-len(raw_text))/len(raw_text):+.1f}%)",
        links=len(link_map),
        categories=len(cat_map),
        templates=len(tpl_map),
    )

    logger.stats(
        "Vaqt Analizi",
        prepare=f"{prep_time:.2f}s",
        translate=f"{trans_time:.2f}s",
        finalize=f"{final_time:.2f}s",
        localize=f"{loc_time:.2f}s",
        total=f"{elapsed:.2f}s",
        review=f"{review_time:.2f}s",
    )

    cache.print_stats()
    translator.print_stats()
    localization.print_stats()

    # print_stats qatorlari oxiriga:
    reviewer.print_stats()

    # API xatosi tufayli aniqlanmagan sarlavhalar — ular QID olmagani uchun
    # havola/turkum/andoza sifatida ingliz tilida qolib ketgan bo'ladi.
    failed = sorted(fetcher.failed_titles)
    if failed:
        logger.warning(
            f"⚠️  {len(failed)} ta sarlavha aniqlanmadi (API xatosi) — "
            "ular ingliz tilida qolgan bo'lishi mumkin:"
        )
        for title in failed[:20]:
            logger.warning(f"    • {title}")
        if len(failed) > 20:
            logger.warning(f"    … va yana {len(failed) - 20} ta")
        logger.warning(
            "Natijadagi havolalar, turkumlar va andozalarni tekshiring "
            "yoki tarjimani qaytadan yuriting."
        )

    logger.success("Tarjima muvaffaqiyatli tugadi!")
    logger.info(f"Natija: {output_file}\n")

    return True


def validate_inputs(input_file: str) -> bool:
    """Validate input parameters."""
    if not Path(input_file).exists():
        print(f"❌ Fayl topilmadi: {input_file}")
        return False

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inglizcha Vikipediya maqolasini oʻzbekchaga tarjima qilish."
    )
    parser.add_argument("input_file", help="Inglizcha wikitext fayli")
    parser.add_argument("output_file", help="Natija yoziladigan fayl")
    parser.add_argument(
        "--title",
        dest="article_title",
        help="Inglizcha sahifa nomi — temp_wiki nusxasi shu nom bilan saqlanadi",
    )
    args = parser.parse_args()
    input_file, output_file = args.input_file, args.output_file

    if not validate_inputs(input_file):
        sys.exit(1)

    # Start the process
    try:
        success = main(input_file, output_file, args.article_title)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Foydalanuvchi tomonidan to'xtatildi")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Kutilmagan xato: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
