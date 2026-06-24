#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
main.py - Wiki Translator MAIN
Orchestrator for the modular translation pipeline.
"""

import re
import sys
import time
from pathlib import Path

import os
os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "2")

from dotenv import load_dotenv
load_dotenv(override=True)

import pywikibot
pywikibot.config.maxlag = 5
pywikibot.config.put_throttle = 1
pywikibot.config.noisysleep = False
pywikibot.config.max_retries = 3
pywikibot.config.retry_wait = 10

import config
from utils.file_handler import FileHandler
from utils.localization import LocalizationManager
from utils.regex_patterns import fix_arabic_transliteration
from utils.logger import logger
from core.cache_manager import WikiCache
from core.wikidata_fetcher import WikidataFetcher
from core.translator import WikiTranslator
from core.processor import WikiTextProcessor
from core.reviewer import WikiReviewer


def main(input_file: str, output_file: str):
    """
    Main translation pipeline.

    Phase 1: PREPARE - Prepare wikitext with QID placeholders
    Phase 2: TRANSLATE - Translate via AI
    Phase 3: FINALIZE - Resolve placeholders
    Phase 4: LOCALIZE - Adapt to Uzbek Wikipedia style

    Args:
        input_file: English Wikipedia article file
        output_file: Uzbek Wikipedia article output file
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
    processor = WikiTextProcessor(fetcher, cache)
    translator = WikiTranslator()
    localization = LocalizationManager()
    reviewer = WikiReviewer()

    logger.success(f"Tizimlar initialize qilindi")
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
        translated_text = translator.translate(prepared_text)
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
        result = fix_arabic_transliteration(result)
        loc_time = time.time() - loc_start
        logger.info(f"  ⏱️  Vaqt: {loc_time:.2f}s")
    except Exception as e:
        logger.critical(f"Localize phase'da xato: {e}")
        return False
    
    logger.section("🔍 PHASE 5: REVIEW")
    review_start = time.time()
 
    if not config.ENABLE_REVIEW:
        logger.warning("Phase 5 o'tkazib yuborildi (ENABLE_REVIEW=false)")
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

    logger.section("💾 SAVE")
    logger.info(f"Yozilmoqda: {output_file}")

    if FileHandler.write_file(output_file, result):
        logger.success(f"Saqlab qo'yildi ({len(result)} belgi)")
    else:
        logger.fail("Fayl yozishda xato!")
        return False

    # Save to temp_wiki directory using article name
    article_match = re.search(r"'''(.+?)'''", raw_text)
    if article_match:
        article_name = article_match.group(1).strip()
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

    logger.success("Tarjima muvaffaqiyatli tugadi!")
    logger.info(f"Natija: {output_file}\n")

    return True


def validate_inputs(input_file: str, output_file: str) -> bool:
    """Validate input parameters."""
    if not Path(input_file).exists():
        print(f"❌ Fayl topilmadi: {input_file}")
        return False

    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Foydalanish: python main.py input_en.txt output_uz.txt")
        sys.exit(1)

    input_file, output_file = sys.argv[1], sys.argv[2]

    if not validate_inputs(input_file, output_file):
        sys.exit(1)

    # Start the process
    try:
        success = main(input_file, output_file)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Foydalanuvchi tomonidan to'xtatildi")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Kutilmagan xato: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
