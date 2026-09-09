#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/state.py - The single in-progress translation job.

One colleague per machine, so one job at a time is enough - a lock-protected
global dict, not a multi-job store. A second /api/translate call while one
is running is refused (409) rather than queued.
"""

import copy
import threading
import time
from typing import Any, Dict, Optional

_lock = threading.Lock()
_job: Optional[Dict[str, Any]] = None


def start_job(raw_input: str) -> bool:
    """Claim the single job slot. False if a job is already running."""
    global _job
    with _lock:
        if _job is not None and _job["status"] == "running":
            return False
        _job = {
            "status": "running",
            "phase": "prepare",
            "raw_input": raw_input,
            "title": None,
            "error": None,
            "text": None,
            "stats": None,
            "started_at": time.time(),
            "finished_at": None,
        }
        return True


def update_job(**kwargs) -> None:
    with _lock:
        if _job is not None:
            _job.update(kwargs)


def snapshot() -> Optional[Dict[str, Any]]:
    with _lock:
        return copy.deepcopy(_job)
