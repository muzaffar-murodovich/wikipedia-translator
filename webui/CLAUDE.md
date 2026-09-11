# CLAUDE.md — `webui/`

Developer notes for the local browser UI. For the colleague-facing setup and
usage guide (in Uzbek), see `webui/README.md`. For the pipeline itself, see
the repository root `CLAUDE.md`.

---

## Why it exists

Colleagues who translate articles are not terminal users: without this they
have to open VS Code, find the project, and run
`python main.py input_en.txt output_uz.txt --title "..."` by hand. The web UI
gives them a page instead.

Deployment shape, decided with the maintainer:

- **Per machine, not a shared server.** Each colleague clones the repo, sets
  up their own `.env` / `OPENAI_API_KEY`, and runs their own copy.
- **Colleagues are on Windows**, so autostart is Windows Task Scheduler; the
  maintainer's own machine is Linux, where only the Flask part is ever run.
- **Bound to `127.0.0.1` only**, no auth — one local user per machine. Never
  change this to `0.0.0.0`; nothing here is written for exposure.
- `debug=False`, `use_reloader=False`: the Werkzeug debugger is remote code
  execution for anything that can reach the port, and the reloader spawns a
  subprocess that complicates the `pythonw` launch.

---

## The hard rule: the pipeline is imported, never modified

`main.py`, `config.py`, `core/` and `utils/` are read-only from here. The one
deliberate exception is **`localization_map.json`**, which the UI edits — it
is data, and the root `CLAUDE.md` already documents editing it by hand as the
supported way to add a rule.

---

## Files

| File | Responsibility |
|---|---|
| `app.py` | Flask routes, the background worker, CWD pinning |
| `pipeline.py` | Input resolution + a replay of `main.py`'s phases with progress |
| `state.py` | The single in-flight job (lock-protected global) |
| `settings.py` | Per-machine overrides in `webui/settings.json` (gitignored) |
| `run_webui.pyw` | Windows autostart entry point (`pythonw.exe`) |
| `setup_autostart.ps1` | One-time: `pip install` + register the logon task |
| `start_webui.ps1` | Start it once, hidden, without waiting for a logon |
| `uninstall_autostart.ps1` | Remove the scheduled task |
| `templates/`, `static/` | Three pages, vanilla JS, no build step |
| `requirements.txt` | `-r ../requirements.txt` + `Flask` (installed into the project's existing `.venv`, not a second one) |

---

## `pipeline.py` — a replay of `main.py`

`main.py`'s `main()` is fully synchronous and reports only through the console
logger, so it cannot drive a progress display, and it always reads from a file.
`run_pipeline()` therefore instantiates the same objects in the same order and
calls the same phases, updating a progress callback between them and returning
structured stats instead of printing them.

**This means the two can drift.** When a phase is added, reordered or changed
in `main.py`, `pipeline.py` must be changed to match — nothing enforces it.

`resolve_input()` turns the single textbox into `(wikitext, article_title)`:

- A `wikipedia.org` URL → `extract_article_name()` → `fetch_wikitext()`.
- A short (≤200 chars), single-line string with none of `[[`, `{{`, `==`,
  `<ref` → treated as an article title and fetched the same way. If the fetch
  finds nothing it **falls through** and translates the line as literal
  wikitext, rather than failing on an ambiguous guess.
- Anything else → literal wikitext, `article_title` is `None`.
- One redirect hop is followed automatically: a redirect page has no content,
  and "translate this article" means the target.

`article_title` is `None` for pasted wikitext, and that is what suppresses the
`temp_wiki/<title>.txt` copy — a snippet has no article identity to file it
under. The browser download is the output in that case.

`run_pipeline()` takes two keyword-only overrides, both for callers outside
the browser. `review=` decides Phase 5, defaulting to the browser's own
switch only when left as `None` — `batch_translate.py` passes
`config.ENABLE_REVIEW` instead, so a checkbox ticked in the UI cannot
silently disable review for an unattended nightly run. `article_title=`
overrides the resolved title. `batch_translate.py` needs it: a trimmed article is literal
wikitext as far as `resolve_input()` can tell, so without the override the
batch would lose both the title and the `temp_wiki/` copy. The browser never
passes it. This is the same "caller's title wins" rule `main.py`'s `main()`
already follows, so it narrows the drift rather than widening it.

Unlike `main.py`, nothing is written to a fixed `output_uz.txt`: it would
clobber the file of a maintainer who also uses the CLI.

---

## Job state

One colleague per machine, so `state.py` holds **one** job, not a dict of
them. A second `POST /api/translate` while one is running returns 409; the
client shows a notice rather than queueing. The worker thread wraps everything
in `except Exception` so an unexpected failure can never leave the job stuck
at `"running"` forever, which would lock the UI until a restart.

The browser polls `GET /api/status` (cheap — no text) and fetches
`GET /api/result` once when it turns `done`. Reloading the page mid-run
resumes the poll, and a finished result is re-rendered, because the state
lives on the server.

---

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | Translate page |
| `GET /localization` | Localization dictionary editor |
| `POST /api/translate` | Body `{input}`; starts the worker, 409 if busy |
| `GET /api/status` | `status`, `phase`, `phase_label`, `error` |
| `GET /api/result` | `text`, `title`, `stats` — only once `done` |
| `GET /download` | The result as a `.txt` attachment |
| `GET/POST /api/settings` | `{review_enabled}` |
| `GET/POST /api/localization` | The map as `[{en, uz}, ...]` |
| `GET /kunlik` | The day's batch, ready to read and publish |
| `GET /api/runs` | Run summaries, newest first — never the translated text |
| `GET /api/run/<id>` | One report; `latest` is an alias. `published` is joined in |
| `POST /api/publish` | Body `{title, published}` → writes to `data/queue.json` |

There is deliberately **no `/shutdown`**: it is an unauthenticated way to kill
the process, for a convenience the Task Manager already provides.

---

## The Kunlik page

`batch_translate.py` translates the day's queue overnight and writes
`data/runs/<date>.json`. This page is where the human reads the result: each
article with its quality flags, a copy button, and a "Nashr qilindi" checkbox.

Two things worth keeping:

- **"Published" lives only in `data/queue.json`**, never in the run report.
  The report is a dated snapshot of what the batch produced; publication is
  running state the human changes later. `GET /api/run/<id>` joins the two at
  read time. Two copies of "did I publish this" would go out of sync on the
  first re-run.
- **`run_id` becomes a filename**, so it is validated (`finder.runs`
  `RUN_ID_RE`) before being joined to a path, and `RUNS_DIR` is anchored to
  `REPO_ROOT` — the same reasoning as `LOCALIZATION_PATH`.

Deliberately **not** here: in-browser editing, diffing, a quality score, and a
"run the batch now" button. The batch takes 10-20 minutes, which is the wrong
shape for an HTTP request, and `state.py` would refuse a second job anyway.

---

## Settings override layer

`settings.py` reads and writes `webui/settings.json` (gitignored, like `.env`
— it is per-machine state, not project config). Today it holds only
`review_enabled`, which `pipeline.py` consults **instead of**
`config.ENABLE_REVIEW` when deciding whether to run Phase 5. `config.py`
itself is never written to.

---

## Localization editor — three invariants worth keeping

All three were real bugs during development; each one silently corrupts the
map if reintroduced.

1. **Never `.strip()` the stored values.** Two dozen entries carry
   load-bearing leading or trailing whitespace (`" buyidlar"` →
   `" Buvayhiylar"`); the map is matched literally against wikitext.
   `.strip()` is used only to decide whether a row is blank.
2. **An empty replacement is legal.** A few entries map to `""` — they delete
   a fragment (a stray ` ``` `, an empty `<references>` tag). Only the *key*
   may not be blank.
3. **The filter hides rows, it does not re-render them.** Save reads every
   `<tr>` in the table, so if filtering removed the non-matching rows from the
   DOM, saving while filtered would drop the other ~222 entries.

The file path is `LOCALIZATION_PATH` — `REPO_ROOT / config.LOCALIZATION_FILE`,
absolute. `config.LOCALIZATION_FILE` on its own is relative and would follow
the process's CWD into a second, private `webui/localization_map.json`.

---

## Two platform traps

- **CWD.** `config.LOCALIZATION_FILE`, `WikiReviewer.RULES_FILE` and the
  `temp_wiki/` save are all relative paths, resolved against the process's
  working directory — `main.py` gets away with it because it is documented as
  run from the repo root. A scheduled task starts in `System32`. So `app.py`
  does `os.chdir(REPO_ROOT)` at import, covering every entry point including
  `python -m webui.app`.
- **`pythonw.exe` has no console**, so `sys.stdout` and `sys.stderr` are
  `None`. `utils/logger.py`'s `StreamHandler()` defaults to `sys.stderr` and
  raises `AttributeError` on the first log line, killing the process before
  Flask starts. `run_webui.pyw` redirects both to `webui/logs/webui.log`
  **before** importing anything that logs.

---

## Styling

`static/style.css` is deliberately **light-only** — no `prefers-color-scheme`
block, and `color-scheme: light` so the browser's own widgets stay light on a
dark desktop. It uses Wikipedia's Vector 2022 / Codex palette (`#fff`,
`#f8f9fa`, `#202122`, `#3366cc`, `#a2a9b1`, `#eaecf0`) and serif headings, so
the tool matches the wiki page it sits beside.

---

## Running and testing

```bash
# From the repo root, with the project venv active
pip install -r webui/requirements.txt
python -m webui.app          # http://127.0.0.1:5057
```

Port: `WEBUI_PORT`, read from the environment or a `webui/.env` (separate from
the project `.env`).

`tests/test_webui_kunlik.py` covers the Kunlik routes through Flask's
`test_client` (skipped when Flask is absent — it is in `webui/requirements.txt`,
not the project's own). The translate and localization pages have **no
automated coverage**: they are verified by running the server and using them in
a browser. The Windows-specific parts (the `.ps1` scripts,
`schtasks`, `pythonw`) cannot be exercised on the maintainer's Linux machine
and need a real Windows box.
