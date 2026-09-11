# CLAUDE.md — Wikipedia Translator

> **IMPORTANT: It is MANDATORY to read the `translation_rules.md` file BEFORE reviewing any translation results.**

## Project Overview

An **English-to-Uzbek Wikipedia article translator** that uses OpenAI to translate wikitext while preserving MediaWiki markup, wikilinks, templates, and categories. It resolves article links via Wikidata so that internal links point to the correct Uzbek Wikipedia equivalents.

---

## Repository Structure

```
wikipedia-translator/
├── main.py                   # Entry point; orchestrates the 5-phase pipeline
├── batch_translate.py        # Drains the discovery queue; writes a daily run report
├── config.py                 # All configuration (comments/values in Uzbek)
├── localization_map.json     # 223 term replacement rules (auto-loaded)
├── translation_rules.md      # Post-translation review checklist (used by Phase 5)
├── pytest.ini                # Test configuration
├── .env                      # Environment variables (API keys — gitignored)
├── requirements.txt          # Runtime dependencies (pip)
├── requirements-dev.txt      # Runtime + pytest
├── core/
│   ├── __init__.py
│   ├── translator.py         # AI translation engine (OpenAI)
│   ├── processor.py          # Wikitext prepare/finalize (QID placeholders)
│   ├── wikidata_fetcher.py   # Wikidata/Wikipedia API calls
│   ├── cache_manager.py      # In-memory 3-tier memoization (QID, sitelink, redirect)
│   ├── usage_stats.py        # Shared OpenAI token accounting (translator + reviewer)
│   └── reviewer.py           # AI post-translation review (Phase 5)
├── utils/
│   ├── __init__.py
│   ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
│   ├── localization.py       # Loads and applies localization_map.json
│   ├── logger.py             # Singleton logger (console-only)
│   ├── regex_patterns.py     # Centralised regex patterns and fix functions
│   ├── link_labels.py        # Wikilink label cleanup (rule 2), runs after Phase 5
│   ├── api_client.py         # Shared Wikimedia HTTP client (TLS, retries)
│   ├── trimmer.py            # Cuts a long article to lead + references + categories
│   └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
├── finder/                   # Article discovery — feeds the translation queue
│   ├── store.py              # data/queue.json: categories seen, articles queued/done
│   ├── wiki.py               # Category listing, sizes, uz existence, risk screening
│   ├── runs.py               # data/runs/<date>.json: daily batch reports
│   ├── logcapture.py         # Collects the pipeline's console-only warnings
│   └── cli.py                # `python -m finder.cli` — the discovery agent's tool
├── .claude/agents/
│   └── article-finder.md     # Haiku subagent that fills the queue (tracked in git)
├── data/                     # Queue and run reports (gitignored, per-machine)
├── tests/                    # pytest suite (445 tests)
├── webui/                    # Local browser UI (Flask) — see webui/CLAUDE.md
│   ├── app.py                # Flask routes; pins the CWD to the repo root
│   ├── pipeline.py           # Replays main.py's phases with progress reporting
│   ├── state.py              # The single in-flight translation job
│   ├── settings.py           # Per-machine overrides (webui/settings.json)
│   ├── templates/, static/   # Three pages, vanilla JS, no build step
│   └── *.ps1                 # Windows autostart (Task Scheduler) scripts
└── additional-tools/
    └── category-checker.py   # Check which category articles are missing from uz.wiki
```

`WikiCache` is an in-memory per-run memoization layer (not persisted to disk). It covers three lookup types:
- title -> QID
- QID -> Uzbek Wikipedia title (sitelink)
- title -> redirect target

Translated outputs are saved to `temp_wiki/` (gitignored) with the article name as filename.

---

## Translation Pipeline (5 phases)

```
input_en.txt
    |
    v
Phase 1 — PREPARE (core/processor.py)
  - Removes empty template params, HTML comments
  - Compresses long <ref>...</ref> blocks to short hashes
  - Parses wikitext with mwparserfromhell
  - Replaces [[wikilinks]] with [[Q12345|label]] placeholders
  - Replaces [[Category:...]] with  CAT:Q12345|label  placeholders
  - Replaces {{templates}} with {{TPL:Q12345}} placeholders
  - Uses `batch_page_info()` — one en.wikipedia request per 50 titles resolves
    redirects + QIDs + uz sitelinks together
    |
    v
Phase 2 — TRANSLATE (core/translator.py)
  - Sends prepared wikitext to OpenAI
  - Placeholders pass through untouched (model instructed to preserve them)
  - Links with no uz.wiki article are listed by name in the prompt so the
    model translates their targets instead of copying the placeholder habit
  - Prompt rules 5-7 restate the translation_rules.md rules that hold at
    translation time (lead sentence, date format) — rules 2/2a cannot, they
    need the Uzbek page name Phase 3 produces
    |
    v
Phase 3 — FINALIZE (core/processor.py)
  - Resolves [[Q12345|label]] -> Uzbek Wikipedia titles via Wikidata sitelinks
  - Resolves CAT:Q12345 -> [[Turkum:...]] categories
  - Resolves {{TPL:Q12345}} -> Uzbek template names (with fallback map)
  - Falls back to English title when no Uzbek sitelink exists
  - Guards the links Phase 1 handed to the model: a target still equal to the
    English original takes the translated label as its page name
  - Restores compressed <ref> blocks
  - Applies regex fixes (punctuation, year formatting, -lik suffix, Arabic transliteration, etc.)
  - Warns if a compressed <ref> failed to come back
    |
    v
Phase 4 — LOCALIZE (utils/localization.py)
  - Applies 223 regex replacements from localization_map.json
  - Examples: [[Category: -> [[Turkum:, == References == -> == Manbalar ==
    |
    v
Phase 5 — REVIEW (core/reviewer.py)
  - Sends localized wikitext to OpenAI with translation_rules.md as rules
  - Model fixes only rule violations; wikitext structure preserved
  - Enabled by `ENABLE_REVIEW` in `config.py`; also skipped if `translation_rules.md` is missing
    |
    v
LINK CLEANUP (utils/link_labels.py)
  - Drops the pipe of a label that only re-spells its target
    ([[Lohur|Lahor]] -> [[Lohur]]), keeps one that carries grammar
    ([[Somalilar|somalilik]])
  - Runs last, after Phase 5, because the reviewer edits links of its own
  - Mismatches it cannot decide mechanically are logged for manual review
    |
    v
output_uz.txt  +  quality report
```

---

## Running

```bash
# Create and activate a virtualenv (Python 3.12)
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt    # or requirements-dev.txt to get pytest too

# Translate
python main.py input_en.txt output_uz.txt

# Name the temp_wiki copy after the real page title (recommended)
python main.py input_en.txt output_uz.txt --title "Mian Wada"
```

> **Note:** always work inside the project's own virtualenv. Without activating it, an interpreter from another project (or the system Python) is used and `mwparserfromhell` and the other dependencies are missing, causing `ModuleNotFoundError`.

### Workflow

1. Place English Wikipedia wikitext in `input_en.txt` (download via `utils/wiki_fetcher.py` or manually)
2. Run `main.py input_en.txt output_uz.txt --title "<page title>"`
3. Review `output_uz.txt` using the rules in `translation_rules.md`
4. The output is also auto-saved to `temp_wiki/<title>.txt`

> **`--title`**: `main.py` only ever receives file paths, so without this flag
> it falls back to the first `'''bold'''` run in the source — which is the lead
> name, not the page title, and the two often differ ("Mian Wada" is bolded as
> "Mian Muhammad Ismail Suharwardy"). Pass `--title` whenever you know it.

### Batch translation (multiple articles)

`main.py` only accepts file paths — not URLs or article names directly.
For multiple articles:

```python
from utils.wiki_fetcher import fetch_wikitext
import subprocess

articles = ["Article One", "Article Two", "Article Three"]
for title in articles:
    wikitext, _ = fetch_wikitext(title)
    with open("input_en.txt", "w", encoding="utf-8") as f:
        f.write(wikitext)
    safe = title.replace(" ", "_")
    subprocess.run(["python", "main.py", "input_en.txt", f"output_{safe}.txt",
                    "--title", title])
```

### Required Environment Variables

Set these in `.env` or export before running:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | (optional) Translation model — defaults to `gpt-5.2` |
| `REVIEW_MODEL` | (optional) Phase 5 review model — defaults to `gpt-5.4-mini` |
| `WIKI_CONTACT` | (optional) Contact info for the Wikimedia API User-Agent (email or wiki user page) |

The `.env` file is gitignored — never commit API keys.

---

## Web UI (`webui/`)

An alternative to the CLI for colleagues who do not use a terminal: a local
Flask page at `http://127.0.0.1:5057` where one textbox takes an article
link, an article name, or raw wikitext, and the translation appears beside it
with copy/download buttons, per-phase progress, a Phase 5 on/off switch, and
an editor for `localization_map.json`.

```bash
pip install -r webui/requirements.txt   # into the project's existing .venv
python -m webui.app
```

It **imports** `core/`, `utils/` and `config.py` and changes none of them; it
replays the same five phases as `main.py` in `webui/pipeline.py`, which means
**a change to `main.py`'s phases must be mirrored there**. Each colleague runs
their own copy on their own Windows machine, started at logon by a Task
Scheduler task.

> **See `webui/CLAUDE.md`** for the architecture, the invariants of the
> localization editor, and the Windows/CWD traps. `webui/README.md` is the
> colleague-facing setup guide (in Uzbek).

---

## Daily Workflow (discovery → batch → review)

The five-phase pipeline translates **one** article. On top of it sits a daily
loop that decides *which* articles to translate and hands the results to a
human. Publishing is never automated — there is no login or edit code in the
project and none is wanted.

```
article-finder agent (Haiku)  ──►  finder/cli.py  ──►  data/queue.json
                                                            │
                                   batch_translate.py  ◄─────┘
                                            │
                                   data/runs/<date>.json
                                            │
                                   webui /kunlik  ──►  human reads, copies, publishes
```

The governing principle: **all mechanical work is in the CLI, only judgment is
in the model.** Deduplication, the size-to-mode decision, maintenance-category
filtering and risk screening are Python. The agent decides only "is this
category on topic" and "is this article about a radical subject".

### 1. Fill the queue

```bash
# In Claude Code — the agent is defined in .claude/agents/article-finder.md
"use the article-finder agent, start from Category:Hadith scholars"
```

It lists a category's articles that are missing from uz.wiki, screens them
against their own en.wiki categories (`finder.cli screen`), queues the
acceptable ones and records a reason for every rejection. When a category is
exhausted it navigates to a related one. All state is in `data/queue.json`, so
losing context costs nothing.

The CLI is usable directly too — `python -m finder.cli status`,
`cat-list`, `screen`, `queue-add`, `reject`, `next`.

### 2. Translate the batch

```bash
python batch_translate.py -n 8
```

Takes the smallest queued articles first, trims the ones over
`TRIM_SIZE_THRESHOLD`, runs each through `webui/pipeline.py`'s `run_pipeline()`
and writes `data/runs/<date>.json`. One article failing never stops the batch,
and the report is rewritten after **every** article so a crash cannot lose work
already paid for in tokens.

### 3. Review and publish

```bash
python -m webui.app     # http://127.0.0.1:5057/kunlik
```

The Kunlik page lists the day's articles with their quality flags — Phase 5
skipped, references left raw, links that stayed English, label/target
mismatches, a lead too thin to publish — plus a copy button and a "Nashr
qilindi" checkbox that writes back to the queue.

> **`batch_translate.py` does not use the web UI's Phase 5 switch.** It follows
> `config.ENABLE_REVIEW`, overridable with `--review` / `--no-review`. The
> browser checkbox is per-machine UI state; a colleague turning it off must not
> silently disable review for an unattended batch.

---

## Configuration (`config.py`)

All configuration is in a single file. Comments and string values are written in **Uzbek**. Key settings:

- **AI model (translation)**: `OPENAI_MODEL` (default `gpt-5.2`).
- **AI model (review)**: `REVIEW_MODEL` (default `gpt-5.4-mini`) — arzonroq model Phase 5 uchun, qoidalarga asoslangan tuzatish uchun yetarli.
- **Source / target languages**: English (`en`) -> Uzbek (`uz`)
- **Phase 5 switch**: `ENABLE_REVIEW` (default `True`) — set to `False` to skip the review phase and its OpenAI call entirely.
- **Translation prompts**: `TRANSLATION_SYSTEM_PROMPT` and `TRANSLATION_USER_PROMPT` — instruct the model to preserve QID/CAT/TPL/REF placeholders and transliterate names (w->v rule for Uzbek).
- **Review prompts**: `REVIEW_SYSTEM_PROMPT` and `REVIEW_USER_PROMPT` — used by Phase 5 to apply `translation_rules.md` corrections without altering wikitext structure. Rules are embedded in the **system prompt** (static prefix) to maximize OpenAI prompt-cache hits; only the wikitext varies per call.
- **Fallback template mappings**: `FALLBACK_TEMPLATE_MAP_EN2UZ` — when Wikidata has no sitelink for a template.
- **Reference compression**: `REF_COMPRESS_THRESHOLD = 30` characters — must stay
  above the 23-character `<ref>REF_a1b2c3d4</ref>` placeholder, or a short
  reference gets *longer* when compressed.
- **Article discovery / batch**: `TRIM_SIZE_THRESHOLD` (10000 bytes — above this an
  article is translated trimmed, not whole), `TRIM_MIN_LEAD_BYTES` (400 — below this the
  trimmed result is flagged as too thin to publish), `DAILY_BATCH_SIZE` (8),
  `QUEUE_FILE` (`data/queue.json`), `RUNS_DIR` (`data/runs`). The last two are relative,
  and both `finder/store.py` and `finder/runs.py` anchor them to the repo root — the CLI,
  the batch runner and the web UI reach them from different working directories.
- **Wikimedia API**: `API_BATCH_SIZE` (50), `API_MAX_RETRIES`, `API_RETRY_BASE_DELAY`, `API_MAX_RETRY_DELAY`, `API_BATCH_DELAY` — 429 rate-limit handling. `API_USER_AGENT` is built from `API_CONTACT` (env `WIKI_CONTACT`); Wikimedia's User-Agent policy requires real contact info, so set it to your email or wiki user page.

Do **not** hardcode API keys into `config.py`. Use environment variables.

---

## Key Modules — Developer Notes

### `core/processor.py`
- Uses `mwparserfromhell` to parse and manipulate wikitext AST.
- `prepare(raw_wikitext)` returns a **3-tuple**: `(prepared_text, counts, ref_map)`, where
  `counts` is `{"links", "categories", "templates"}` — the number of *distinct* QIDs
  resolved per kind. It used to return three QID-keyed maps whose values nothing read.
- `self.unresolved_links` — wikilink targets with no uz.wiki article, left in English for the model. `main.py` feeds it to `translate()`, and `finalize()` checks the model actually translated them.
- `finalize(translated_text, ref_map)` takes **2 arguments** — the QID-to-title resolution is done internally via `self.fetcher.get_sitelink()` during finalize. The in-memory cache populated during `prepare()` (especially uz sitelinks pre-cached by `batch_page_info()`) makes this near-free.
- `_restore_references()` falls back to matching the bare `REF_<id>` when the model has
  reformatted a placeholder, and **warns about any that never came back** rather than
  shipping a raw `REF_a1b2c3d4` in the article.

### `core/translator.py`
- `translate(text, forced_links=None)` sends prepared wikitext to OpenAI for translation.
- `forced_links` names the targets with no uz.wiki article one by one (`config.FORCED_LINKS_TEMPLATE`). A general rule does not work: the prepared text is dominated by `[[Q12345|...]]` placeholders the model must not touch, and it generalises that to plain English wikilinks too.
- Token accounting lives in `core/usage_stats.py`, shared with the reviewer.
- The system prompt explicitly tells the model to pass all `[[Q...]]`, `CAT:...`, and `{{TPL:...}}` placeholders through unchanged.

### `core/wikidata_fetcher.py`
- Uses **direct HTTP** (`urllib`, via `utils/api_client.py`) for every lookup. There is no pywikibot dependency: the batch endpoint below answers redirects, QIDs and sitelinks in one request, so the per-item client bought nothing.
- `get_sitelink(qid, target_lang)` — returns the article title on the target Wikipedia (direct HTTP, called in Phase 3). Calls `cache.has_sitelink()` first, because a cached `"NONE"` reads back as `None` exactly like a cache miss.
- `batch_page_info(titles, site_code)` — **the batch workhorse** used in Phase 1 (direct HTTP, no pywikibot). One `action=query&redirects=1&prop=pageprops|langlinks` request per 50 titles returns the redirect target, the QID and the uz title in a single round trip, and pre-caches uz/en sitelinks (bonus for Phase 3). Returns `{title: {"resolved", "qid", "uz_title"}}`.
- **Rate limiting:** `_wiki_api()` is a thin wrapper over `utils.api_client.wiki_api()`, which retries on HTTP 429/5xx honouring the `Retry-After` header (`config.API_MAX_RETRIES`, `API_RETRY_BASE_DELAY`, `API_MAX_RETRY_DELAY`); `batch_page_info()` sleeps `API_BATCH_DELAY` between batches. On a failed lookup nothing is written to the cache — an API error must never be recorded as "not found", and the affected titles land in `fetcher.failed_titles`.
- All results pass through `cache_manager` automatically.

### `core/reviewer.py`
- Phase 5 post-translation review via OpenAI.
- Uses `config.REVIEW_MODEL` (default `gpt-5.4-mini`) — separate from translation model to reduce cost.
- Loads `translation_rules.md` at init; if missing, `is_available()` returns `False` and the phase is skipped in `main.py`.
- `review(text)` formats the rules into `REVIEW_SYSTEM_PROMPT` (static — benefits from prompt caching) and the wikitext into `REVIEW_USER_PROMPT` (dynamic), strips markdown code fences from the response, and returns the corrected text (or `None` on failure).
- Token accounting lives in `core/usage_stats.py`, shared with the translator; `print_stats()` emits a stats block at end of run.

### `core/cache_manager.py`
- In-memory 3-tier memoization: QID, sitelink, redirect. No disk persistence — each run starts empty.
- Cache values of `"NONE"` mean "looked up and not found" — do not re-query within the same run.
- Cache keys: `"site_code:title"` for QID/redirect, `"QID:target_site"` for sitelink.
- All three tiers share `_get()` / `_set()` / `_has()` over a tier table.
- **`get_*()` returns `None` for both "cached as absent" and "never looked up"** — use
  `has_qid()` / `has_sitelink()` / `has_redirect()` when the difference matters, and never
  reach into `qid_cache` / `sitelink_cache` / `redirect_cache` from outside the class.
- Within a single run, Phase 1 populates most entries (via `batch_page_info()` which pre-caches uz/en sitelinks), so Phase 3 mostly hits the cache.
- **Never cache a lookup that failed with an API error** — only genuine "not found" answers get the `"NONE"` sentinel.

### `utils/regex_patterns.py`
- Central registry of all regex patterns used across the codebase (`RegexPatterns` class).
- **The registry must hold the patterns that actually run.** An earlier set of
  `PUNCT_*` constants sat here unread while `fix_punctuation_with_refs()` ran its own
  inline copies, and the two silently drifted apart until the class version was a
  different matcher, not a different spelling.
- `apply_all_fixes(text)` applies every fix in the correct order:
  1. `fix_arabic_transliteration()` — diacritic removal (ā→a, ī→i, ū→u, etc.), final `-ī` → `-iy` suffix, and solar letter assimilation (`al-Roziy` → `ar-Roziy`). Implements Rules 1 & 2 from `translation_rules.md`. Skips `<ref>`, URLs, template params, and link targets.
  2. `fix_cite_book_script_title()` — `script-title` -> `title` in cite book templates
  3. `fix_year_with_dash()` — `2025 yil` -> `2025-yil`
  4. `fix_lik_suffix_capitalization()` — lowercase `-lik` suffix words mid-sentence
  5. `_fix_all_punctuation()` — `fix_punctuation_with_refs()` then
     `fix_punctuation_with_sfn()`, both inside **one** `_apply_fix_outside_infoboxes()`
     masking pass (each pass costs a full parse, and the second re-derived the first's
     infobox set).
     - `fix_punctuation_with_refs()` — punctuation around `<ref>` tags, both kinds.
     - `fix_punctuation_with_sfn()` — a run of `{{sfn}}`/`{{efn}}`/`<ref>` citations is
       treated as **one chain**: the first mark found (before the chain, or stranded
       between two of its templates) becomes the chain's trailing mark and the rest are
       dropped. Moving marks one template at a time is what used to produce `..` and
       `...`. A period is never invented in front of a lowercase word, and a chain with
       no `{{sfn}}`/`{{efn}}` in it is left to `fix_punctuation_with_refs()`.
  6. `fix_template_blank_lines()` — remove blank lines inside multiline templates
  7. Collapse 3+ consecutive newlines to 2
- `_apply_fix_outside_infoboxes(wikitext, fix_func)` — wraps a fix function to skip infobox templates.
- Modify patterns here, not inline in other files.

### `utils/link_labels.py`
- Implements `translation_rules.md` rule 2: a wikilink label must not disagree with its page name.
- The target comes from Wikidata, the label from the translation model, so the two regularly spell one name differently — `[[Lohur|Lahor]]`.
- `is_same_name(target, label)` decides whether the label only re-spells the target. Deliberately strict: a wrong collapse silently corrupts a sentence, a missed one is only reported. It rejects a namespace/interwiki prefix, a parenthetical disambiguator (rule 2's own exception), a lowercase label (a common-noun gloss such as `[[Tasavvuf|soʻfiy]]` carries the sentence grammar), a differing length, and finally compares the consonant skeleton with vowels folded and the Arabic article stripped.
- `collapse_redundant_labels(text)` returns the cleaned text plus the deduplicated list of mismatches left for a human.
- Uzbek case suffixes sit outside the brackets, so a collapse leaves the sentence intact: `[[Lohur|Lahor]]ga` -> `[[Lohur]]ga`.
- Called from `main.py` **after** Phase 5 — the reviewer does not fix these violations and sometimes re-introduces a redundant pipe.

### `utils/trimmer.py`
- `trim_article(wikitext)` returns `(text, info)`. It keeps the lead and the citation
  apparatus and drops the body sections, for articles over `TRIM_SIZE_THRESHOLD`.
- The section split uses **mwparserfromhell, not regex** — `==` also appears inside
  `<ref>` bodies and template parameters, where it is not a heading. The parser already
  knows the difference; only the heading *title* is matched, against
  `RegexPatterns.APPARATUS_HEADING`.
- **A named `<ref>` defined in a cut section is inlined into its first surviving
  invocation.** Without this, `<ref name="x"/>` in the lead renders on uz.wiki as a red
  "Cite error: The named reference x was invoked but never defined" — and a reviewer
  reading Uzbek prose would never catch it. This step is not optional.
- `info["trimmed"] is False` is **not an error**: it means there was nothing to cut (no
  sections, or the lead runs straight into References). The caller falls back to a full
  translation. `info["thin_lead"]` flags a result too short to be worth publishing.

### `finder/store.py`
- Owns `data/queue.json` and is the only module that touches it.
- `upsert_article()` **never downgrades a status.** An article that has been published
  cannot fall back to "queued" because the agent met it again in a second category; a
  re-add returns `("dup", existing_status)`.
- `reject` is the one exception, in `finder/cli.py`: a *queued* article can still be
  pulled back out, because a second look overrules the first. Anything translated or
  published has left the queue and is the human's to undo.
- Articles that already exist on uz.wiki are deliberately **not** stored — that is ~70%
  of every category. `categories[c].status == "exhausted"` plus the counts is enough
  memory to avoid re-listing.
- Writes are atomic (`os.replace`): the CLI and the web UI both write this file.
- `FINDER_QUEUE` in the environment points the whole toolchain at another file.

### `finder/wiki.py`
- `fetch_category_members(category)` — one request per 500 members returns membership,
  Uzbek existence **and** byte size together (`prop=langlinks|info`; the size field is
  `length`, not `size`).
- `risky_categories(categories)` — the decisive evidence for the radical-topic screen.
  Matched as substrings, so the nationality-scoped variants (`Moroccan Salafis`,
  `Albanian Salafis`) are covered without enumerating them.
- **Screening on the article title alone is not enough.** A trial run of the agent
  correctly rejected al-Albani but queued six figures categorised as Salafis, Wahhabis or
  Islamists, one imprisoned on terrorism charges. The screen is a hard step in the
  agent's loop, not a fallback for when the model feels unsure.
- `is_maintenance_category()` filters the housekeeping and date buckets so the agent
  never spends context on them.

### `finder/logcapture.py`
- `capture_warnings()` collects what `core/processor.py` reports only to the console —
  links whose target stayed English, references whose placeholder never came back.
  `utils/logger.py` wraps the stdlib logger, so a temporary handler picks them up
  **without modifying processor.py**.

### `batch_translate.py`
- `os.chdir(REPO_ROOT)` runs **before** `webui.pipeline` is imported.
  `config.LOCALIZATION_FILE`, `WikiReviewer.RULES_FILE` and the `temp_wiki/` save are all
  relative; without it Phase 5 is silently skipped and the run still reports success.
- One article's failure is recorded and the batch continues. The report is saved after
  every article.
- Phase 5 follows `config.ENABLE_REVIEW`, **not** `webui/settings.json` — see the Daily
  Workflow note above.

### `utils/localization.py`
- Reads `localization_map.json` at startup (223 entries).
- Patterns compiled once (longest-key-first for greedy matching).
- **A missing or unreadable map is reported and leaves the map empty.** It used to write a
  ten-entry default over `config.LOCALIZATION_FILE`, which replaced the real file and let
  the run finish looking healthy while emitting an unlocalized article.
- `stats["replacements"]` counts the replacements that fired, not the `apply()` calls.
- To add a new term replacement, edit `localization_map.json` directly — no code changes needed.

### `utils/logger.py`
- Singleton — instantiated at module level as `logger = Logger()`.
- Import with: `from utils.logger import logger`
- Console-only output (no file logging).
- Use `logger.section()`, `logger.success()`, `logger.fail()`, `logger.stats()` for structured output.

### `utils/api_client.py`
- `wiki_api(params, lang, domain)` — the single place where HTTP requests to Wikipedia/Wikidata are made. Every module goes through it; a failed request is raised, never silently treated as "not found".
- Retries on 429 and 5xx/network errors with exponential backoff, honouring `Retry-After`. A 4xx other than 429 is raised at once.
- **TLS:** certificates are verified against the `certifi` bundle, not the platform default. Python's default CA source differs per OS — on Linux it is a complete package-managed directory, on Windows only the system certificate store, which ships with a minimal root set and fills up on demand, so a needed root can be missing and requests fail with `SSLCertVerificationError` while browsers work. `certifi` behaves identically everywhere.
- `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` override the bundle when set (for an intercepting corporate proxy or antivirus); a missing or unreadable file logs a warning and falls back to `certifi`.
- A certificate error is **not** retried — `urlopen` wraps it in `URLError`, so `e.reason` is inspected and the error re-raised immediately with a message naming the CA bundle in use.

### `utils/wiki_fetcher.py`
- `fetch_wikitext(article_name, lang)` — downloads wikitext via Wikipedia API. Returns `(wikitext, title)` tuple.
- `extract_article_name(url)` — extracts article name from Wikipedia URL or returns input as-is.
- `is_redirect(wikitext)` — checks if wikitext is a redirect page; returns target title or `None`.

### `utils/file_handler.py`
- Static methods for file I/O: `read_file()`, `write_file()`, `read_json()`, `write_json()`, `file_exists()`.
- All operations use UTF-8 encoding by default.
- JSON operations use `ensure_ascii=False` to preserve Uzbek script.

---

## Code Conventions

| Convention | Detail |
|---|---|
| **Language** | File/class/function names in English; comments and docstrings in English; user-facing error messages and log output in Uzbek |
| **Encoding** | UTF-8 everywhere; always open files with `encoding="utf-8"` |
| **Type hints** | Use `Optional`, `Dict`, `List`, `Tuple` from `typing` |
| **Null sentinel** | Use the string `"NONE"` (not Python `None`) for cache "not found" entries |
| **Error handling** | Catch exceptions, log with the logger, return a safe fallback — avoid bare `raise` in pipeline code |
| **Logging** | Always use the singleton `logger` from `utils.logger`; never use `print()` in library code |
| **Patterns** | New regex patterns go into `utils/regex_patterns.py`, not inline |
| **Config** | New settings go into `config.py` only; no magic strings scattered in code |
| **Design patterns** | Singleton (Logger), Manager (Cache, Localization), Pipeline (main.py phases) |
| **Apostrophes** | Bold markup is three straight ASCII apostrophes (`'''`, U+0027 x3) — a curly variant produces no bold at all. Inside Uzbek words the curly characters are letters, not markup: `ʻ` (U+02BB) in `oʻ`/`gʻ`, `ʼ` (U+02BC) for tutuq belgisi (`Saʼd`). Write these in code and in `localization_map.json` values. **Nothing in the pipeline normalises apostrophes**, and that is deliberate — see below |

### Apostrophes in the output

The translation model writes `oʻ`/`gʻ` inconsistently: sometimes the correct letter
U+02BB, sometimes the typographic quote U+2018 (`bo‘lib`, `qishlog‘ida`), sometimes a
straight `'`. The same goes for tutuq belgisi (U+02BC vs U+2019).

**The pipeline does not fix this, on purpose.** Uzbek Wikipedia's **Vikifikator**
script normalises exactly these characters when a page is saved, so doing it here
would duplicate work that the wiki already does reliably.

`localization_map.json` does **not** convert apostrophes. Around thirty of its
entries contain one, but every single one is a whole-term replacement that happens
to spell a particular term correctly (`Turkum:Ash'ariylar` → `Turkum:Ashʼariylar`).
There is no general `'` → `ʻ` rule, and none is wanted.

So: do not add apostrophe-normalising rules to the map or a regex fix for them, and
do not treat U+2018/U+2019 in `output_uz.txt` as a bug to chase.

---

## Adding Features

### New localization rule
Add an entry to `localization_map.json`:
```json
"English term": "Ozbekcha atama"
```
No code changes needed — it is loaded automatically.

### New regex fix
Add a function to `utils/regex_patterns.py` and call it from `apply_all_fixes()`.

### New cache tier
Extend `core/cache_manager.py` following the same `get/set` pattern as existing tiers (in-memory only, "NONE" sentinel for negative lookups).

---

## Additional Tools

### `additional-tools/category-checker.py`

Standalone CLI tool that checks which articles in an English Wikipedia category are **missing** from Uzbek Wikipedia (via Wikidata sitelinks). Outputs only missing articles to console and JSON.

```bash
# Basic usage
python additional-tools/category-checker.py "11th-century Arabic-language poets"

# Open first 5 missing articles in browser
python additional-tools/category-checker.py "Uzbek writers" --open 5

# Open articles 10-20 in browser
python additional-tools/category-checker.py "Uzbek writers" --open 10-20

# Ignore the saved file and query Wikipedia again
python additional-tools/category-checker.py "Uzbek writers" --refresh
```

- Accepts category name with or without `"Category:"` prefix.
- Uses one `generator=categorymembers` + `prop=langlinks&lllang=uz` request per 500 members: category membership and Uzbek existence arrive together, so a 494-article category costs a single request (~1 s).
- JSON output saved to `additional-tools/category_check_<name>.json` (gitignored), and **read back on the next check of the same category** — a repeat check makes no HTTP request at all and prints the saved result's age. `--refresh` forces a new query and overwrites the file. A file that is absent, corrupt or missing its expected fields falls back to a fresh query with a warning.
- The results file is always written, including when nothing is missing, so the next check can reuse it.
- **A refresh overwrites the file without asking** — copy it first if you have annotated the list.
- **Note:** The tool checks article **existence** on uz.wiki (Wikidata sitelink), not category membership. An article may exist on uz.wiki but be in a different category.

---

## Testing & Quality

**Automated tests** — 445 tests under `tests/`, run with:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

`pytest.ini` sets `testpaths = tests` and `pythonpath = .`, so plain `pytest` works from the repo root. Coverage by module:

| Test file | Tests | Covers |
|---|---|---|
| `test_regex_patterns.py` | 69 | `utils/regex_patterns.py` |
| `test_finder_wiki.py` | 50 | `finder/wiki.py` |
| `test_cache_manager.py` | 34 | `core/cache_manager.py` |
| `test_link_labels.py` | 30 | `utils/link_labels.py` |
| `test_trimmer.py` | 29 | `utils/trimmer.py` |
| `test_finder_cli.py` | 28 | `finder/cli.py` |
| `test_wiki_fetcher.py` | 24 | `utils/wiki_fetcher.py` |
| `test_batch_translate.py` | 24 | `batch_translate.py` |
| `test_finder_store.py` | 23 | `finder/store.py` |
| `test_reviewer.py` | 21 | `core/reviewer.py` |
| `test_translator.py` | 21 | `core/translator.py` |
| `test_runs.py` | 20 | `finder/runs.py` |
| `test_processor.py` | 18 | `core/processor.py` |
| `test_file_handler.py` | 16 | `utils/file_handler.py` |
| `test_webui_kunlik.py` | 14 | `webui/` Kunlik routes |
| `test_localization.py` | 10 | `utils/localization.py` |
| `test_logcapture.py` | 7 | `finder/logcapture.py` |
| `test_api_client.py` | 7 | `utils/api_client.py` |

No network or OpenAI calls are made — `urlopen` and the OpenAI client are monkeypatched (`tests/conftest.py` holds the shared fixtures). `core/wikidata_fetcher.py` and `main.py` are **not** covered yet. Of `webui/`, only the Kunlik routes are tested (skipped when Flask is absent, since it lives in `webui/requirements.txt`); the translate and localization pages are still verified by hand in a browser (see `webui/CLAUDE.md`).

`tests/test_finder_cli.py` asserts **exact stdout lines** on purpose: that format is the contract the `article-finder` agent is written against, and changing it silently would break the agent without failing any other test.

Beyond the suite, translation quality is validated by:

1. **Automatic Phase 5 review** — `core/reviewer.py` applies `translation_rules.md` rules via OpenAI before the final output is written. This catches the most common rule violations automatically.
2. **Manual inspection** of `output_uz.txt` — **always read `translation_rules.md` first** and verify:
   - Name transliteration (remove diacritics, -i -> -iy suffix)
   - Solar letter assimilation (al-Roziy -> ar-Roziy)
   - Lead sentence structure (em-dash after parenthetical)
   - Wikilink label/target consistency
   - Date formatting (hijriy/milodiy prefix, YYYY-yil)
3. **Logger statistics** printed at the end of each run (cache hit rates, token counts, timing).
4. **Failed-title warning** — if any lookup failed with an API error, `main.py` lists the affected titles after the statistics. Those links, categories and templates never got a QID, so they stay in English in the output: check them, or re-run the translation.

---

## Git Workflow

Single-maintainer project — there is no team and no PR review step.

- **Commit straight to `main`.** Do not open a branch unless there is a real
  reason: work that may be abandoned half-finished, or several independent
  changes in flight at once. A branch that is fast-forward merged into `main`
  right away produces exactly the same history as committing to `main`, and
  only leaves a stale local branch behind.
- Keep unrelated changes in separate commits, even on `main`.
- Commit messages are short and descriptive in English.
- **Never commit** `.env`, API keys, `output*.txt`, `*.log`, or `temp_wiki/` — all excluded by `.gitignore`.
- The `origin` remote is HTTPS but no credentials are stored; pushes go over SSH:
  `git push git@github.com:muzaffar-murodovich/wikipedia-translator.git main`

---

## Dependencies (`requirements.txt`)

| Package | Purpose |
|---|---|
| `openai` | OpenAI API client (primary provider) |
| `mwparserfromhell` | Wikitext parser (used in processor.py) |
| `python-dotenv` | Loads `.env` file into environment |
| `certifi` | CA bundle for TLS verification (see `utils/api_client.py`) |
| `pytest` | Test runner (`requirements-dev.txt`) |

Runtime versions are pinned with `==` so every machine gets the same set.
`certifi` is the deliberate exception (`>=`): an outdated CA bundle is what
breaks TLS on Windows in the first place, so it must stay upgradable.

Python version: **3.12**

Install: `pip install -r requirements.txt`
