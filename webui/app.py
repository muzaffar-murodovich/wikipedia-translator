#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
webui/app.py - Local Flask UI for the translation pipeline.

Binds to 127.0.0.1 only: single colleague, single machine, no auth needed.
main.py, config.py, core/ and utils/ are only ever imported here, never
modified - see CLAUDE.md and the webui implementation plan.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import os
from pathlib import Path

# config.LOCALIZATION_FILE, WikiReviewer.RULES_FILE and the temp_wiki/ save
# in pipeline.py are all relative paths, resolved against the process's
# working directory - exactly like main.py assumes it's run from the repo
# root. app.py has no such guarantee (a colleague could launch it from
# inside webui/, or a shortcut could start it anywhere), so this pins the
# CWD to the repo root before anything reads or writes one of those paths.
# Without it, a save from the browser would silently create/edit a second
# webui/localization_map.json instead of the shared project one.
REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)

import threading
import time
from typing import List, Tuple

from flask import Flask, jsonify, render_template, request, Response

from utils.file_handler import FileHandler
import config as project_config

from finder import runs, store

from . import pipeline, settings, state

# Anchored to REPO_ROOT rather than left as the bare relative
# project_config.LOCALIZATION_FILE: the one shared localization_map.json
# lives at the repo root, and this endpoint must never depend on whatever
# the process's CWD happens to be at request time.
LOCALIZATION_PATH = REPO_ROOT / project_config.LOCALIZATION_FILE

PORT = int(os.environ.get("WEBUI_PORT", 5057))

app = Flask(__name__)


def _worker(raw_input: str) -> None:
    try:
        def on_progress(phase: str) -> None:
            state.update_job(phase=phase)

        result = pipeline.run_pipeline(raw_input, on_progress)
        state.update_job(
            status="done",
            phase="done",
            title=result["title"],
            text=result["text"],
            stats=result["stats"],
            finished_at=time.time(),
        )
    except pipeline.PipelineError as e:
        state.update_job(status="error", error=str(e), finished_at=time.time())
    except Exception as e:
        state.update_job(status="error", error=f"Kutilmagan xato: {e}", finished_at=time.time())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/localization")
def localization_page():
    return render_template("localization.html")


@app.route("/kunlik")
def kunlik_page():
    return render_template("kunlik.html")


@app.route("/api/translate", methods=["POST"])
def api_translate():
    data = request.get_json(silent=True) or {}
    raw_input = (data.get("input") or "").strip()
    if not raw_input:
        return jsonify({"error": "Matn kiritilmagan"}), 400

    if not state.start_job(raw_input):
        return jsonify({"error": "Hozir boshqa tarjima ishlamoqda"}), 409

    threading.Thread(target=_worker, args=(raw_input,), daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def api_status():
    job = state.snapshot()
    if job is None:
        return jsonify({"status": "idle"})
    return jsonify({
        "status": job["status"],
        "phase": job["phase"],
        "phase_label": pipeline.PHASE_LABELS.get(job["phase"], job["phase"]),
        "error": job["error"],
    })


@app.route("/api/result")
def api_result():
    job = state.snapshot()
    if job is None or job["status"] != "done":
        return jsonify({"error": "Natija hali tayyor emas"}), 409
    return jsonify({"text": job["text"], "title": job["title"], "stats": job["stats"]})


@app.route("/download")
def download():
    job = state.snapshot()
    if job is None or job["status"] != "done":
        return jsonify({"error": "Natija hali tayyor emas"}), 409

    filename = f"{job['title']}.txt" if job["title"] else f"tarjima_{int(time.time())}.txt"
    return Response(
        job["text"],
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if "review_enabled" in data:
            settings.set_review_enabled(bool(data["review_enabled"]))
    return jsonify({"review_enabled": settings.get_review_enabled()})


def _load_localization_pairs() -> List[Tuple[str, str]]:
    data = FileHandler.read_json(str(LOCALIZATION_PATH))
    return list(data.items())


@app.route("/api/localization", methods=["GET", "POST"])
def api_localization():
    if request.method == "GET":
        pairs = _load_localization_pairs()
        return jsonify([{"en": en, "uz": uz} for en, uz in pairs])

    data = request.get_json(silent=True) or {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return jsonify({"error": "Noto'g'ri so'rov"}), 400

    seen = set()
    result_map = {}
    for entry in entries:
        # Leading/trailing whitespace in "en" is often load-bearing (it is
        # matched literally against the wikitext, e.g. " buyidlar" with a
        # leading space), and "uz" may legitimately be "" (a delete rule,
        # e.g. stripping a stray ``` or an empty <references> tag) - so
        # values are kept exactly as submitted; .strip() below is only used
        # to detect a blank row, never to alter what gets stored.
        en = entry.get("en") or ""
        uz = entry.get("uz") or ""
        if not en.strip():
            return jsonify({"error": "Bo'sh atama qatori mavjud"}), 400
        if en in seen:
            return jsonify({"error": f"Takrorlangan atama: {en}"}), 400
        seen.add(en)
        result_map[en] = uz

    if not FileHandler.write_json(str(LOCALIZATION_PATH), result_map):
        return jsonify({"error": "Faylga yozishda xato"}), 500

    return jsonify({"status": "saved", "count": len(result_map)})


# ── Kunlik: the day's batch, ready to read and publish ────────────────────────

@app.route("/api/runs")
def api_runs():
    return jsonify(runs.list_runs())


@app.route("/api/run/<run_id>")
def api_run(run_id: str):
    if run_id == "latest":
        latest = runs.latest_run_id()
        if latest is None:
            return jsonify({"error": "Hali birorta paket ishga tushmagan"}), 404
        run_id = latest

    if not runs.is_valid_run_id(run_id):
        return jsonify({"error": "Noto'g'ri paket nomi"}), 400

    report = runs.load_report(run_id)
    if report is None:
        return jsonify({"error": f"Paket topilmadi: {run_id}"}), 404

    # "Published" lives only in the queue. Keeping a second copy in the run
    # report would be two sources of truth for the one thing the human
    # actually changes.
    articles = store.load().get("articles", {})
    for entry in report.get("articles", []):
        rec = articles.get(entry["title"], {})
        entry["published"] = rec.get("status") == "published"

    return jsonify(report)


@app.route("/api/publish", methods=["POST"])
def api_publish():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    published = bool(data.get("published"))
    if not title:
        return jsonify({"error": "Maqola nomi yo'q"}), 400

    queue = store.load()
    if not store.mark(queue, title, "published" if published else "translated"):
        return jsonify({"error": f"Navbatda yo'q: {title}"}), 404
    store.save(queue)

    return jsonify({"status": "ok", "published": published})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False, use_reloader=False)
