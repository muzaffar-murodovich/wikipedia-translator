#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/run_webui.pyw - Windows autostart entry point (launched via pythonw.exe).

The one thing only python.exe gets right by default and pythonw.exe does
not: under pythonw.exe there is no console, so sys.stdout and sys.stderr
are None. utils/logger.py's logging.StreamHandler() defaults to sys.stderr
and would raise AttributeError on the very first log call, killing the
process before Flask starts. Both are redirected to a log file before
importing anything that logs.

(webui/app.py itself pins the working directory to the repo root, since
translation_rules.md, localization_map.json and temp_wiki/ are all read or
written via paths relative to the process's CWD - that fix lives there so
it also covers `python -m webui.app`, not just this entry point.)
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LOG_DIR = REPO_ROOT / "webui" / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = open(LOG_DIR / "webui.log", "a", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

sys.path.insert(0, str(REPO_ROOT))

from webui.app import app, PORT  # noqa: E402  (must follow the redirects above)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False, use_reloader=False)
