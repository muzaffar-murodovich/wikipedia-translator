#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/pipeline.py - Orchestration for the web UI.

Mirrors main.py's five-phase pipeline (see CLAUDE.md) so the browser gets
the same translation main.py would produce, but as structured progress/JSON
instead of console log lines - main.py itself is never imported or changed.

The .env load must happen before `import config`, exactly like main.py,
because config.py reads os.getenv(...) at import time.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import re
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import config
from utils.file_handler import FileHandler
from utils.link_labels import collapse_redundant_labels
from utils.localization import LocalizationManager
from utils.wiki_fetcher import extract_article_name, fetch_wikitext, is_redirect
from core.cache_manager import WikiCache
from core.wikidata_fetcher import WikidataFetcher
from core.translator import WikiTranslator
from core.processor import WikiTextProcessor
from core.reviewer import WikiReviewer
from core.usage_stats import cache_hit_summary

from . import settings

PHASE_LABELS = {
    "resolve": "Manba aniqlanmoqda",
    "prepare": "Tayyorlash",
    "translate": "Tarjima",
    "finalize": "Finalizatsiya",
    "localize": "Lokalizatsiya",
    "review": "Tahrir",
    "cleanup": "Havolalarni tozalash",
    "save": "Saqlash",
    "done": "Tayyor",
}

# A pasted title/URL is short and has none of these; real wikitext almost
# always has at least one, even a small hand-written snippet.
_WIKITEXT_MARKERS = ("[[", "{{", "==", "<ref")
_TITLE_MAX_LEN = 200


class PipelineError(Exception):
    """A user-facing translation failure (bad input, API failure, ...)."""


def _looks_like_wikipedia_url(text: str) -> bool:
    return text.startswith(("http://", "https://")) and "wikipedia.org" in text


def _looks_like_title(text: str) -> bool:
    return (
        "\n" not in text
        and len(text) <= _TITLE_MAX_LEN
        and not any(marker in text for marker in _WIKITEXT_MARKERS)
    )


def _fetch_full_article(name: str) -> Tuple[Optional[str], Optional[str]]:
    """fetch_wikitext(), following one redirect hop automatically."""
    wikitext, title = fetch_wikitext(name)
    if wikitext is None:
        return None, None

    target = is_redirect(wikitext)
    if target:
        redirected_text, redirected_title = fetch_wikitext(target)
        if redirected_text is not None:
            return redirected_text, redirected_title

    return wikitext, title


def resolve_input(raw_input: str) -> Tuple[str, Optional[str]]:
    """
    Turn the single textbox input into (wikitext, article_title).

    A Wikipedia URL or a short, markup-free line is treated as an article
    to fetch in full; anything else is treated as wikitext to translate as
    given (article_title is None, so it won't be saved into temp_wiki/).
    """
    trimmed = raw_input.strip()
    if not trimmed:
        raise PipelineError("Matn kiritilmagan")

    if _looks_like_wikipedia_url(trimmed):
        name = extract_article_name(trimmed)
        if not name:
            raise PipelineError(f"Havoladan maqola nomini aniqlab bo'lmadi: {trimmed}")
        wikitext, title = _fetch_full_article(name)
        if wikitext is None:
            raise PipelineError(f"Maqola topilmadi: {name}")
        return wikitext, title

    if _looks_like_title(trimmed):
        wikitext, title = _fetch_full_article(trimmed)
        if wikitext is not None:
            return wikitext, title
        # Not an actual article title - fall through and translate the
        # short line itself rather than failing on an ambiguous guess.

    return trimmed, None


def run_pipeline(raw_input: str, on_progress: Callable[[str], None]) -> dict:
    """
    Run the full translation pipeline for one submission.

    Returns {"text", "title", "stats"} on success; raises PipelineError (or
    lets an unexpected exception propagate) on failure.
    """
    on_progress("resolve")
    wikitext, article_title = resolve_input(raw_input)

    cache = WikiCache()
    fetcher = WikidataFetcher(cache)
    processor = WikiTextProcessor(fetcher)
    translator = WikiTranslator()
    localization = LocalizationManager()
    reviewer = WikiReviewer()

    timings = {}
    start = time.time()

    on_progress("prepare")
    t = time.time()
    prepared_text, counts, ref_map = processor.prepare(wikitext)
    timings["prepare"] = time.time() - t

    on_progress("translate")
    t = time.time()
    translated_text = translator.translate(prepared_text, processor.unresolved_links)
    if not translated_text:
        raise PipelineError("Tarjima muvaffaqiyatsiz tugadi")
    timings["translate"] = time.time() - t

    on_progress("finalize")
    t = time.time()
    finalized_text = processor.finalize(translated_text, ref_map)
    timings["finalize"] = time.time() - t

    on_progress("localize")
    t = time.time()
    result = localization.apply(finalized_text)
    timings["localize"] = time.time() - t

    on_progress("review")
    t = time.time()
    review_ran = False
    if settings.get_review_enabled() and reviewer.is_available():
        reviewed = reviewer.review(result)
        if reviewed:
            result = reviewed
            review_ran = True
    timings["review"] = time.time() - t

    on_progress("cleanup")
    result, label_mismatches = collapse_redundant_labels(result)

    on_progress("save")
    if article_title:
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', article_title)
        temp_dir = Path("temp_wiki")
        temp_dir.mkdir(exist_ok=True)
        FileHandler.write_file(str(temp_dir / f"{safe_name}.txt"), result)

    timings["total"] = time.time() - start

    stats = {
        "counts": counts,
        "timings": {k: round(v, 2) for k, v in timings.items()},
        "input_size": len(wikitext),
        "output_size": len(result),
        "cache": cache.get_cache_size(),
        "translator": {
            "model": translator.model,
            "translations": translator.stats["translations"],
            "tokens_used": translator.stats["tokens_used"],
            "cache_hits": cache_hit_summary(translator.stats),
        },
        "reviewer": {
            "model": reviewer.model,
            "reviews": reviewer.stats["reviews"],
            "tokens_used": reviewer.stats["tokens_used"],
            "cache_hits": cache_hit_summary(reviewer.stats),
        } if review_ran else None,
        "localization": dict(localization.stats),
        "failed_titles": sorted(fetcher.failed_titles),
        "label_mismatches": [[t, l] for t, l in label_mismatches],
    }

    on_progress("done")
    return {"text": result, "title": article_title, "stats": stats}
