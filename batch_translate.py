#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
batch_translate.py - Translate the next N articles from the discovery queue.

The queue is filled by the article-finder agent; this drains it. Each article
goes through the same five phases main.py runs, via webui/pipeline.py's
run_pipeline(), which - unlike main.py - returns structured stats instead of
printing them.

The result is data/runs/<date>.json: every article's translated wikitext
together with the flags a human needs before publishing it. The web UI's
Kunlik page reads that file; nothing here publishes anything.

    python batch_translate.py -n 8
"""

import argparse
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Must happen before importing webui.pipeline: config.LOCALIZATION_FILE,
# WikiReviewer.RULES_FILE and the temp_wiki/ save are all relative paths.
# Without this, Phase 5 is silently skipped and the localization map is not
# found - the run still "succeeds" and ships an unreviewed article.
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

import config
from finder import runs, store
from finder.logcapture import capture_warnings
from utils.logger import logger
from utils.regex_patterns import RegexPatterns
from utils.trimmer import trim_article
from utils.wiki_fetcher import fetch_wikitext, is_redirect
from webui import pipeline

EXIT_OK = 0
EXIT_ERROR = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fetch(title: str):
    """fetch_wikitext(), following one redirect hop. Mirrors pipeline.py."""
    wikitext, resolved = fetch_wikitext(title)
    if wikitext is None:
        return None, None

    target = is_redirect(wikitext)
    if target:
        hopped_text, hopped_title = fetch_wikitext(target)
        if hopped_text is not None:
            return hopped_text, hopped_title

    return wikitext, resolved


def _blank_entry(row: dict) -> dict:
    return {
        "title": row["title"],
        "url": row.get("url"),
        "category": row.get("category"),
        "mode": row.get("mode", "full"),
        "status": "failed",
        "original_size": 0,
        "input_size": 0,
        "output_size": 0,
        "trim": None,
        "flags": {},
        "counts": {},
        "timings": {},
        "text": None,
        "error": None,
    }


def translate_one(row: dict, review: bool) -> dict:
    """
    Translate one queued article. Never raises: a failure is recorded in the
    returned entry so the batch can carry on to the next article.
    """
    entry = _blank_entry(row)
    title = row["title"]

    try:
        wikitext, resolved_title = _fetch(title)
        if wikitext is None:
            entry["error"] = f"Maqola topilmadi: {title}"
            return entry

        entry["original_size"] = len(wikitext)
        text = wikitext

        if entry["mode"] == "trim":
            trimmed, info = trim_article(wikitext)
            entry["trim"] = info
            if info["trimmed"]:
                text = trimmed
            else:
                # Nothing to cut (no sections, or lead straight into
                # References). Translating it whole is the right answer, not
                # an error.
                entry["mode"] = "full"

        entry["input_size"] = len(text)

        with capture_warnings() as warnings:
            result = pipeline.run_pipeline(
                text, lambda phase: None,
                article_title=resolved_title or title,
                review=review,
            )

        stats = result["stats"]
        entry.update({
            "status": "ok",
            "output_size": stats["output_size"],
            "counts": stats["counts"],
            "timings": stats["timings"],
            "text": result["text"],
        })
        entry["flags"] = {
            # stats["reviewer"] is None exactly when Phase 5 did not apply.
            "review_ran": stats["reviewer"] is not None,
            "failed_titles": stats["failed_titles"],
            "label_mismatches": stats["label_mismatches"],
            "leftover_refs": sorted(set(
                re.findall(RegexPatterns.REF_PLACEHOLDER, result["text"])
            )),
            "warnings": list(warnings),
        }
        return entry

    except pipeline.PipelineError as e:
        entry["error"] = str(e)
        return entry
    except Exception as e:
        entry["error"] = f"Kutilmagan xato: {e}"
        entry["traceback"] = traceback.format_exc()
        return entry


def run_batch(rows, run_id: str, review: bool) -> dict:
    report = {
        "run_id": run_id,
        "started_at": _now(),
        "finished_at": None,
        "review_enabled": review,
        "requested": len(rows),
        "ok": 0,
        "failed": 0,
        "articles": [],
    }

    if not review:
        logger.warning("Phase 5 (tahrir) oʻchirilgan — --review bilan yoqish mumkin")

    for i, row in enumerate(rows, start=1):
        logger.info(f"[{i}/{len(rows)}] {row['title']} ({row.get('mode')})")
        started = time.time()
        entry = translate_one(row, review)
        entry["seconds"] = round(time.time() - started, 1)

        data = store.load()
        if entry["status"] == "ok":
            report["ok"] += 1
            store.mark(data, row["title"], "translated", run_id=run_id)
            logger.success(f"{row['title']} — {entry['output_size']} belgi")
        else:
            report["failed"] += 1
            store.mark(data, row["title"], "failed", error=entry["error"], run_id=run_id)
            logger.fail(f"{row['title']} — {entry['error']}")
        store.save(data)

        report["articles"].append(entry)
        # Written after every article: a crash must not lose the work already
        # paid for in OpenAI tokens.
        runs.save_report(report)

    report["finished_at"] = _now()
    runs.save_report(report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Navbatdagi maqolalarni paketli tarjima qiladi."
    )
    parser.add_argument("-n", "--number", type=int, default=config.DAILY_BATCH_SIZE,
                        help="Nechta maqola tarjima qilinsin")
    parser.add_argument("--run-id", default=None,
                        help="Hisobot fayli nomi (standart: bugungi sana)")
    parser.add_argument("--only", action="append", metavar="TITLE",
                        help="Faqat shu maqola(lar)ni tarjima qilish")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nima tarjima qilinishini koʻrsatadi, tarjima qilmaydi")
    # Phase 5 follows config.ENABLE_REVIEW, not webui/settings.json: that
    # switch belongs to the browser, and a colleague turning it off there
    # must not silently disable review for an unattended batch.
    review_group = parser.add_mutually_exclusive_group()
    review_group.add_argument("--review", dest="review", action="store_true",
                              default=None, help="Phase 5 (tahrir) ni yoqish")
    review_group.add_argument("--no-review", dest="review", action="store_false",
                              help="Phase 5 (tahrir) ni oʻtkazib yuborish")
    args = parser.parse_args(argv)

    run_id = args.run_id or runs.today_run_id()
    if not runs.is_valid_run_id(run_id):
        logger.fail(f"Noto'g'ri run id: {run_id}")
        return EXIT_ERROR

    data = store.load()
    if args.only:
        rows = []
        for title in args.only:
            rec = data.get("articles", {}).get(title)
            if rec is None:
                logger.fail(f"Navbatda yoʻq: {title}")
                return EXIT_ERROR
            rows.append({"title": title, **rec})
    else:
        rows = store.next_queued(data, args.number)

    if not rows:
        logger.warning("Navbat boʻsh — avval article-finder agentini ishga tushiring")
        return EXIT_OK

    logger.section(f"PAKETLI TARJIMA — {run_id} ({len(rows)} ta maqola)")

    if args.dry_run:
        for row in rows:
            logger.info(f"  {row.get('size', 0):>6}  {row.get('mode')}  {row['title']}")
        logger.info("(--dry-run: hech narsa tarjima qilinmadi)")
        return EXIT_OK

    review = config.ENABLE_REVIEW if args.review is None else args.review
    report = run_batch(rows, run_id, review)

    logger.section("NATIJA")
    logger.stats(
        "Paket",
        run_id=run_id,
        soʻralgan=report["requested"],
        tayyor=report["ok"],
        xato=report["failed"],
        hisobot=str(runs.report_path(run_id)),
    )

    flagged = [
        a["title"] for a in report["articles"]
        if a["status"] == "ok" and (
            not a["flags"].get("review_ran")
            or a["flags"].get("leftover_refs")
            or a["flags"].get("failed_titles")
            or (a.get("trim") or {}).get("thin_lead")
        )
    ]
    if flagged:
        logger.warning(f"{len(flagged)} ta maqolada eʼtibor talab qiladigan belgi bor:")
        for title in flagged:
            logger.warning(f"    {title}")

    return EXIT_OK if report["failed"] == 0 else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
