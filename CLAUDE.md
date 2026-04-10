# CLAUDE.md — Wikipedia Translator

> **IMPORTANT: It is MANDATORY to read the `translation_rules.md` file BEFORE reviewing any translation results.**

## Project Overview

An **English-to-Uzbek Wikipedia article translator** that uses OpenAI to translate wikitext while preserving MediaWiki markup, wikilinks, templates, and categories. It resolves article links via Wikidata so that internal links point to the correct Uzbek Wikipedia equivalents.

---

## Repository Structure

```
wikipedia-translator/
├── main.py                   # Entry point; orchestrates the 4-phase pipeline
├── config.py                 # All configuration (comments/values in Uzbek)
├── localization_map.json     # 150+ term replacement rules (auto-loaded)
├── translation_rules.md      # Manual post-translation review checklist
├── .env                      # Environment variables (API keys — gitignored)
├── Pipfile / Pipfile.lock    # Python 3.12 dependencies (pipenv)
├── core/
│   ├── translator.py         # AI translation engine (OpenAI)
│   ├── processor.py          # Wikitext prepare/finalize (QID placeholders)
│   ├── wikidata_fetcher.py   # Wikidata/Wikipedia API calls
│   └── cache_manager.py      # 3-tier JSON cache (QID, sitelink, redirect)
└── utils/
    ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
    ├── localization.py       # Loads and applies localization_map.json
    ├── logger.py             # Singleton logger (console + file)
    ├── regex_patterns.py     # Centralised regex patterns and fix functions
    └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
```

Cache lives in `.wiki_cache/` (gitignored) and grows automatically:
- `qid_cache.json` — title -> QID mappings
- `sitelink_cache.json` — QID -> Uzbek Wikipedia title mappings
- `redirect_cache.json` — redirect resolution results

Translated outputs are saved to `temp_wiki/` (gitignored) with the article name as filename.

---

## Translation Pipeline (4 phases)

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
  - Uses batch Wikidata API (50 titles/request) for redirects + QIDs
    |
    v
Phase 2 — TRANSLATE (core/translator.py)
  - Sends prepared wikitext to OpenAI
  - Placeholders pass through untouched (model instructed to preserve them)
    |
    v
Phase 3 — FINALIZE (core/processor.py)
  - Resolves [[Q12345|label]] -> Uzbek Wikipedia titles via Wikidata sitelinks
  - Resolves CAT:Q12345 -> [[Turkum:...]] categories
  - Resolves {{TPL:Q12345}} -> Uzbek template names (with fallback map)
  - Falls back to English title when no Uzbek sitelink exists
  - Restores compressed <ref> blocks
  - Applies regex fixes (punctuation, year formatting, -lik suffix, etc.)
    |
    v
Phase 4 — LOCALIZE (utils/localization.py)
  - Applies 150+ regex replacements from localization_map.json
  - Examples: [[Category: -> [[Turkum:, == References == -> == Manbalar ==
    |
    v
output_uz.txt  +  quality report
```

---

## Running

```bash
# Install dependencies
PIPENV_IGNORE_VIRTUALENVS=1 pipenv install

# Translate
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run python main.py input_en.txt output_uz.txt
```

> **Note:** `PIPENV_IGNORE_VIRTUALENVS=1` is required because pipenv detects any active virtualenv (e.g. from another project) and uses it instead of the project's own `.venv`. Without this flag, `pywikibot` and other project dependencies won't be found, causing `ModuleNotFoundError`.

### Workflow

1. Place English Wikipedia wikitext in `input_en.txt` (download via `utils/wiki_fetcher.py` or manually)
2. Run `main.py input_en.txt output_uz.txt`
3. Review `output_uz.txt` using the rules in `translation_rules.md`
4. The output is also auto-saved to `temp_wiki/<Article Name>.txt`

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
    subprocess.run(["python", "main.py", "input_en.txt", f"output_{safe}.txt"])
```

### Required Environment Variables

Set these in `.env` or export before running:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |

The `.env` file is gitignored — never commit API keys.

`PYWIKIBOT_NO_USER_CONFIG=2` is set automatically by `main.py` at startup.

---

## Configuration (`config.py`)

All configuration is in a single file. Comments and string values are written in **Uzbek**. Key settings:

- **AI model**: `OPENAI_MODEL` (default `gpt-5.2`).
- **Source / target languages**: English (`en`) -> Uzbek (`uz`)
- **Cache paths**: `.wiki_cache/` directory
- **Pywikibot tuning**: `PYWIKIBOT_CONFIG` dict — `maxlag=10`, `put_throttle=1`, `max_retries=8`, `retry_wait=20`. Also configured directly in `main.py` before pywikibot import.
- **Translation prompts**: `TRANSLATION_SYSTEM_PROMPT` and `TRANSLATION_USER_PROMPT` — instruct the model to preserve QID/CAT/TPL/REF placeholders and transliterate names (w->v rule for Uzbek).
- **Fallback template mappings**: `FALLBACK_TEMPLATE_MAP_EN2UZ` — when Wikidata has no sitelink for a template.
- **Reference compression**: `REF_COMPRESS_THRESHOLD = 20` characters.

Do **not** hardcode API keys into `config.py`. Use environment variables.

---

## Key Modules — Developer Notes

### `core/processor.py`
- Uses `mwparserfromhell` to parse and manipulate wikitext AST.
- `prepare(raw_wikitext)` returns a **5-tuple**: `(prepared_text, link_qid_map, cat_qid_map, tpl_qid_map, ref_map)`.
- `finalize(translated_text, ref_map)` takes **2 arguments** — the QID-to-title resolution is done internally via `self.fetcher.get_sitelink()` during finalize, not from the maps returned by prepare.
- Batch processing: `begin_batch()` / `end_batch()` on the cache defers disk writes until the entire prepare phase completes.

### `core/translator.py`
- `translate(text)` sends prepared wikitext to OpenAI for translation.
- Tracks `translations` count and `tokens_used` statistics.
- The system prompt explicitly tells the model to pass all `[[Q...]]`, `CAT:...`, and `{{TPL:...}}` placeholders through unchanged.

### `core/wikidata_fetcher.py`
- Uses **pywikibot** for legacy single-item queries and **direct HTTP** (`urllib`) for batch operations.
- `site_en`, `site_uz`, `site_wd` are **lazy properties** — pywikibot `Site()` objects are created only on first access, not at init time. This prevents `MaxlagTimeoutError` on startup.
- `get_qid(title, site)` — resolves a Wikipedia title to its QID (pywikibot, legacy).
- `get_sitelink(qid, target_lang)` — returns the article title on the target Wikipedia (direct HTTP, called in Phase 3). Uses raw dict check on `cache.sitelink_cache` to correctly detect `"NONE"` sentinel entries and avoid redundant API calls.
- `batch_resolve_redirects()` / `batch_get_qids_fast()` — direct HTTP API, used in Phase 1 (no pywikibot). Process 50 titles per request.
- `batch_get_qids_fast()` also pre-caches uz and en sitelinks (bonus for Phase 3).
- All results pass through `cache_manager` automatically.

### `core/cache_manager.py`
- 3-tier cache: QID, sitelink, redirect.
- Cache values of `"NONE"` mean "looked up and not found" — do not re-query.
- Cache keys: `"site_code:title"` for QID/redirect, `"QID:target_site"` for sitelink.
- Supports deferred batch mode: `begin_batch()` / `end_batch()` to minimize disk writes.
- `import_cache()` / `export_cache()` helpers for backup/restore.

### `utils/regex_patterns.py`
- Central registry of all regex patterns used across the codebase (`RegexPatterns` class).
- `apply_all_fixes(text)` applies every fix in the correct order:
  1. `fix_cite_book_script_title()` — `script-title` -> `title` in cite book templates
  2. `fix_year_with_dash()` — `2025 yil` -> `2025-yil`
  3. `fix_lik_suffix_capitalization()` — lowercase `-lik` suffix words mid-sentence
  4. `fix_punctuation_with_refs()` — move punctuation after `<ref>` tags
  5. `fix_punctuation_with_sfn()` — handle `{{sfn}}` template punctuation
- Modify patterns here, not inline in other files.

### `utils/localization.py`
- Reads `localization_map.json` at startup.
- Patterns compiled once (longest-key-first for greedy matching).
- `add_replacement()` / `remove_replacement()` for runtime edits.
- To add a new term replacement, edit `localization_map.json` directly — no code changes needed.

### `utils/logger.py`
- Singleton — instantiated at module level as `logger = Logger()`.
- Import with: `from utils.logger import logger`
- Writes to both console and `translation.log`.
- Use `logger.section()`, `logger.success()`, `logger.fail()`, `logger.stats()` for structured output.

### `utils/wiki_fetcher.py`
- `fetch_wikitext(article_name, lang)` — downloads wikitext via Wikipedia API. Returns `(wikitext, title)` tuple.
- `extract_article_name(url)` — extracts article name from Wikipedia URL or returns input as-is.
- `is_redirect(wikitext)` — checks if wikitext is a redirect page.

### `utils/file_handler.py`
- Static methods for all file I/O: `read_file()`, `write_file()`, `read_json()`, `write_json()`, `append_file()`, `create_backup()`.
- All operations use UTF-8 encoding by default.

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
| **Bold markup** | Use `'''` (curly/typographic apostrophe U+2019) for bold article names, not `'''` (straight U+0027) |

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
Extend `core/cache_manager.py` following the same `get/set/save/load` pattern as existing tiers.

---

## Testing & Quality

There is no automated test suite. Validation is done by:

1. **Manual inspection** of `output_uz.txt` — **always read `translation_rules.md` first** and apply all rules:
   - Name transliteration (remove diacritics, -i -> -iy suffix)
   - Solar letter assimilation (al-Roziy -> ar-Roziy)
   - Lead sentence structure (em-dash after parenthetical)
   - Wikilink label/target consistency
   - Date formatting (hijriy/milodiy prefix, YYYY-yil)
2. **Logger statistics** printed at the end of each run (cache hit rates, token counts, timing).

---

## Git Workflow

- Development branch naming: `claude/<description>-<sessionId>`
- Commit messages are short and descriptive in English.
- **Never commit** `.env`, API keys, `output*.txt`, `*.log`, or `temp_wiki/` — all excluded by `.gitignore`.
- Push with: `git push -u origin <branch-name>`

---

## Dependencies (Pipfile)

| Package | Purpose |
|---|---|
| `openai` | OpenAI API client (primary provider) |
| `aiohttp` | Async HTTP for API calls |
| `pywikibot` | Wikidata / Wikipedia API |
| `mwparserfromhell` | Wikitext parser (used in processor.py) |
| `python-telegram-bot` | Optional Telegram bot interface |

Python version: **3.12**

Install: `PIPENV_IGNORE_VIRTUALENVS=1 pipenv install`
