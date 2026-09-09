#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/run_webui.pyw - Windows autostart entry point (launched via pythonw.exe).

Two things only python.exe gets right by default and pythonw.exe does not:

1. Working directory - config.py, translation_rules.md and
   localization_map.json are all read via paths relative to the process's
   CWD, so this chdir's to the repo root before anything else is imported.
2. stdout/stderr - under pythonw.exe there is no console, so sys.stdout and
   sys.stderr are None. utils/logger.py's logging.StreamHandler() defaults
   to sys.stderr and would raise AttributeError on the very first log call,
   killing the process before Flask starts. Both are redirected to a log
   file before importing anything that logs.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)

LOG_DIR = REPO_ROOT / "webui" / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = open(LOG_DIR / "webui.log", "a", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

sys.path.insert(0, str(REPO_ROOT))

from webui.app import app, PORT  # noqa: E402  (must follow the redirects above)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False, use_reloader=False)
