#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finder/store.py - The one file that owns data/queue.json.

Everything the discovery agent decides lands here: which categories were
opened and how they were reached, which articles were queued, rejected,
translated or published. Nothing else in the project touches the file.

The agent runs on a small model and loses context between sessions, so the
file is the memory: every decision is written the moment it is made, and a
title that is already known is never offered a second time.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import config

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Anchored to the repo root rather than left relative: the CLI, the batch
# runner and the web UI all reach this file from different working
# directories, and a second queue.json would silently split the state.
# FINDER_QUEUE points the whole toolchain at another file (a trial run, a
# second topic area) without touching the real queue.
_path: Path = Path(os.environ.get("FINDER_QUEUE") or (_REPO_ROOT / config.QUEUE_FILE))

CATEGORY_STATUSES = ("pending", "in_progress", "exhausted", "skipped")
ARTICLE_STATUSES = ("queued", "translated", "published", "rejected", "failed")


def set_path(path) -> None:
    """Point the store at another file (tests, alternate workspace)."""
    global _path
    _path = Path(path)


def get_path() -> Path:
    return _path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _skeleton() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now(),
        "categories": {},
        "articles": {},
        "stats": {s: 0 for s in ARTICLE_STATUSES},
    }


def load() -> Dict[str, Any]:
    """Read the queue, returning a fresh skeleton when there is no file yet."""
    if not _path.exists():
        return _skeleton()
    try:
        with open(_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # A corrupt queue must not be silently replaced - the caller would
        # re-queue hundreds of already-published articles. English, because
        # the finder CLI prints this straight to the discovery agent.
        raise RuntimeError(f"Queue file is corrupt: {_path}")

    for key in ("categories", "articles"):
        data.setdefault(key, {})
    data.setdefault("stats", {})
    return data


def save(data: Dict[str, Any]) -> None:
    """Write the queue atomically (two processes can hold it open)."""
    recount(data)
    data["updated_at"] = _now()
    _path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=str(_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def recount(data: Dict[str, Any]) -> None:
    """Rebuild the stats block from the articles themselves."""
    stats = {s: 0 for s in ARTICLE_STATUSES}
    for rec in data.get("articles", {}).values():
        status = rec.get("status")
        if status in stats:
            stats[status] += 1
    data["stats"] = stats


# ── Categories ────────────────────────────────────────────────────────────────

def upsert_category(data: Dict[str, Any], name: str, **fields) -> Dict[str, Any]:
    """
    Create or update a category record.

    `source` records how the category was reached ("seed", a parent/sub
    category, or the article whose category list suggested it) - that trail
    is the only record of how the agent navigated.
    """
    cats = data.setdefault("categories", {})
    rec = cats.get(name)
    if rec is None:
        rec = {
            "status": "pending",
            "source": "seed",
            "first_seen": _now(),
            "checked_at": None,
            "members": 0,
            "missing": 0,
            "queued": 0,
            "rejected": 0,
            "note": "",
        }
        cats[name] = rec
    rec.update({k: v for k, v in fields.items() if v is not None})
    return rec


def known_categories(data: Dict[str, Any]) -> Set[str]:
    return set(data.get("categories", {}))


def current_category(data: Dict[str, Any]) -> Optional[str]:
    """The category being worked on, if any."""
    for name, rec in data.get("categories", {}).items():
        if rec.get("status") == "in_progress":
            return name
    return None


def pending_categories(data: Dict[str, Any]) -> List[str]:
    return [
        name for name, rec in data.get("categories", {}).items()
        if rec.get("status") == "pending"
    ]


# ── Articles ──────────────────────────────────────────────────────────────────

def _blank_article() -> Dict[str, Any]:
    return {
        "status": "queued",
        "mode": "full",
        "size": 0,
        "category": None,
        "url": None,
        "reject_reason": None,
        "discovered_at": _now(),
        "translated_at": None,
        "published_at": None,
        "run_id": None,
        "error": None,
    }


def upsert_article(data: Dict[str, Any], title: str, **fields) -> Tuple[str, str]:
    """
    Add an article, or report that it is already known.

    Never overwrites an existing record: a title that has been published or
    rejected must not silently drop back to "queued" because the agent met
    it again in a second category.

    Returns ("added", status) or ("dup", existing_status).
    """
    articles = data.setdefault("articles", {})
    existing = articles.get(title)
    if existing is not None:
        return "dup", existing.get("status", "queued")

    rec = _blank_article()
    rec.update({k: v for k, v in fields.items() if v is not None})
    articles[title] = rec
    return "added", rec["status"]


def mark(data: Dict[str, Any], title: str, status: str, **fields) -> bool:
    """Set an article's status explicitly. Returns False if it is unknown."""
    rec = data.get("articles", {}).get(title)
    if rec is None:
        return False

    rec["status"] = status
    if status == "translated":
        rec["translated_at"] = _now()
    elif status == "published":
        rec["published_at"] = _now()

    rec.update({k: v for k, v in fields.items() if v is not None})
    return True


def known_titles(data: Dict[str, Any]) -> Set[str]:
    return set(data.get("articles", {}))


def next_queued(data: Dict[str, Any], n: int) -> List[Dict[str, Any]]:
    """
    The next n queued articles, smallest first.

    Small articles translate fully and review quickly, so a short batch is
    worth more finished articles than a long one.
    """
    rows = [
        {"title": title, **rec}
        for title, rec in data.get("articles", {}).items()
        if rec.get("status") == "queued"
    ]
    rows.sort(key=lambda r: (r.get("size") or 0, r.get("discovered_at") or ""))
    return rows[:n]
