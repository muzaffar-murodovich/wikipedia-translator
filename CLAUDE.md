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
│   ├── cache_manager.py      # In-memory 3-tier memoization (QID, sitelink, redirect)
│   └── reviewer.py           # AI post-translation review (Phase 5)
├── utils/
│   ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
│   ├── localization.py       # Loads and applies localization_map.json
│   ├── logger.py             # Singleton logger (console + file)
│   ├── regex_patterns.py     # Centralised regex patterns and fix functions
│   └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
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
Phase 5 — REVIEW (core/reviewer.py)
  - Sends localized wikitext to OpenAI with translation_rules.md as rules
  - Model fixes only rule violations; wikitext structure preserved
  - Skipped if translation_rules.md is missing
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
| `OPENAI_MODEL` | (optional) Translation model — defaults to `gpt-5.2` |
| `REVIEW_MODEL` | (optional) Phase 5 review model — defaults to `gpt-5.4-mini` |

The `.env` file is gitignored — never commit API keys.

`PYWIKIBOT_NO_USER_CONFIG=2` is set automatically by `main.py` at startup.

---

## Configuration (`config.py`)

All configuration is in a single file. Comments and string values are written in **Uzbek**. Key settings:

- **AI model (translation)**: `OPENAI_MODEL` (default `gpt-5.2`).
- **AI model (review)**: `REVIEW_MODEL` (default `gpt-5.4-mini`) — arzonroq model Phase 5 uchun, qoidalarga asoslangan tuzatish uchun yetarli.
- **Source / target languages**: English (`en`) -> Uzbek (`uz`)
- **Pywikibot tuning**: `PYWIKIBOT_CONFIG` dict — `maxlag=10`, `put_throttle=1`, `max_retries=8`, `retry_wait=20`. Also configured directly in `main.py` before pywikibot import.
- **Translation prompts**: `TRANSLATION_SYSTEM_PROMPT` and `TRANSLATION_USER_PROMPT` — instruct the model to preserve QID/CAT/TPL/REF placeholders and transliterate names (w->v rule for Uzbek).
- **Review prompts**: `REVIEW_SYSTEM_PROMPT` and `REVIEW_USER_PROMPT` — used by Phase 5 to apply `translation_rules.md` corrections without altering wikitext structure. Rules are embedded in the **system prompt** (static prefix) to maximize OpenAI prompt-cache hits; only the wikitext varies per call.
- **Fallback template mappings**: `FALLBACK_TEMPLATE_MAP_EN2UZ` — when Wikidata has no sitelink for a template.
- **Reference compression**: `REF_COMPRESS_THRESHOLD = 20` characters.

Do **not** hardcode API keys into `config.py`. Use environment variables.

---

## Key Modules — Developer Notes

### `core/processor.py`
- Uses `mwparserfromhell` to parse and manipulate wikitext AST.
- `prepare(raw_wikitext)` returns a **5-tuple**: `(prepared_text, link_qid_map, cat_qid_map, tpl_qid_map, ref_map)`.
- `finalize(translated_text, ref_map)` takes **2 arguments** — the QID-to-title resolution is done internally via `self.fetcher.get_sitelink()` during finalize, not from the maps returned by prepare. The in-memory cache populated during `prepare()` (especially uz sitelinks pre-cached by `batch_get_qids_fast()`) makes this near-free.

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

### `core/reviewer.py`
- Phase 5 post-translation review via OpenAI.
- Uses `config.REVIEW_MODEL` (default `gpt-5.4-mini`) — separate from translation model to reduce cost.
- Loads `translation_rules.md` at init; if missing, `is_available()` returns `False` and the phase is skipped in `main.py`.
- `review(text)` formats the rules into `REVIEW_SYSTEM_PROMPT` (static — benefits from prompt caching) and the wikitext into `REVIEW_USER_PROMPT` (dynamic), strips markdown code fences from the response, and returns the corrected text (or `None` on failure).
- Tracks `reviews` count and `tokens_used`; `print_stats()` emits a stats block at end of run.

### `core/cache_manager.py`
- In-memory 3-tier memoization: QID, sitelink, redirect. No disk persistence — each run starts empty.
- Cache values of `"NONE"` mean "looked up and not found" — do not re-query within the same run.
- Cache keys: `"site_code:title"` for QID/redirect, `"QID:target_site"` for sitelink.
- Within a single run, Phase 1 populates most entries (via `batch_get_qids_fast()` which pre-caches uz/en sitelinks), so Phase 3 mostly hits the cache.

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
- Writes to console.
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
```

- Accepts category name with or without `"Category:"` prefix.
- Uses `WikidataFetcher` and `WikiCache` from the main project (batch API, 50 titles/request).
- JSON output saved to `additional-tools/category_check_<name>.json` (gitignored).
- **Note:** The tool checks article **existence** on uz.wiki (Wikidata sitelink), not category membership. An article may exist on uz.wiki but be in a different category.

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
