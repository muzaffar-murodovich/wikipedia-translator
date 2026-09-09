#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/settings.py - Per-colleague local overrides (webui/settings.json)

config.py is the project's shared source and is never written to here.
Overrides live only in this gitignored file, one per machine, the same way
.env does — so review_enabled defaults to config.ENABLE_REVIEW until a
colleague flips the switch in the UI.
"""

import threading
from pathlib import Path
from typing import Any, Dict

import config
from utils.file_handler import FileHandler

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"
_lock = threading.Lock()


def _read() -> Dict[str, Any]:
    return FileHandler.read_json(str(SETTINGS_FILE))


def _write(data: Dict[str, Any]) -> None:
    FileHandler.write_json(str(SETTINGS_FILE), data)


def get_review_enabled() -> bool:
    with _lock:
        data = _read()
    return bool(data.get("review_enabled", config.ENABLE_REVIEW))


def set_review_enabled(value: bool) -> None:
    with _lock:
        data = _read()
        data["review_enabled"] = bool(value)
        _write(data)
