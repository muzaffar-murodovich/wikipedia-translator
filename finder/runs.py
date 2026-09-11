#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finder/runs.py - Daily batch reports (data/runs/<run_id>.json).

One file per batch run, holding each article's translated text alongside the
quality flags the human needs before publishing it. batch_translate.py writes
them; the web UI's Kunlik page reads them.

Kept separate from store.py because the two have different lifetimes: the
queue is the project's running memory, a run report is a dated snapshot.
"""

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Anchored to the repo root for the same reason as the queue: the batch
# runner, the CLI and the web UI all reach these files from different
# working directories.
_dir: Path = Path(os.environ.get("FINDER_RUNS") or (_REPO_ROOT / config.RUNS_DIR))

# A run id becomes a filename, so it may not carry a path separator.
RUN_ID_RE = re.compile(r'^[\w.-]+$')


def set_dir(path) -> None:
    """Point the reports at another directory (tests, alternate workspace)."""
    global _dir
    _dir = Path(path)


def get_dir() -> Path:
    return _dir


def today_run_id() -> str:
    return date.today().isoformat()


def is_valid_run_id(run_id: str) -> bool:
    return bool(run_id) and bool(RUN_ID_RE.match(run_id)) and ".." not in run_id


def report_path(run_id: str) -> Path:
    if not is_valid_run_id(run_id):
        raise ValueError(f"Noto'g'ri run id: {run_id}")
    return _dir / f"{run_id}.json"


def save_report(report: Dict[str, Any]) -> None:
    """Write a report atomically; safe to call after every article."""
    path = report_path(report["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_report(run_id: str) -> Optional[Dict[str, Any]]:
    path = report_path(run_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_runs(limit: int = 30) -> List[Dict[str, Any]]:
    """Run summaries, newest first. Never loads the translated text."""
    if not _dir.exists():
        return []

    rows: List[Dict[str, Any]] = []
    for path in sorted(_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # One unreadable report must not hide the rest of the history.
            continue
        rows.append({
            "run_id": data.get("run_id", path.stem),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "ok": data.get("ok", 0),
            "failed": data.get("failed", 0),
        })
    return rows


def latest_run_id() -> Optional[str]:
    runs = list_runs(limit=1)
    return runs[0]["run_id"] if runs else None
