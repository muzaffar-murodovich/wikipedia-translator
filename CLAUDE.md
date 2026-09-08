# CLAUDE.md — Wikipedia Translator

> **IMPORTANT: It is MANDATORY to read the `translation_rules.md` file BEFORE reviewing any translation results.**

## Project Overview

An **English-to-Uzbek Wikipedia article translator** that uses OpenAI to translate wikitext while preserving MediaWiki markup, wikilinks, templates, and categories. It resolves article links via Wikidata so that internal links point to the correct Uzbek Wikipedia equivalents.

---

## Repository Structure

```
wikipedia-translator/
├── main.py                   # Entry point; orchestrates the 5-phase pipeline
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
│   └── reviewer.py           # AI post-translation review (Phase 5)
├── utils/
│   ├── __init__.py
│   ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
│   ├── localization.py       # Loads and applies localization_map.json
│   ├── logger.py             # Singleton logger (console-only)
│   ├── regex_patterns.py     # Centralised regex patterns and fix functions
│   ├── api_client.py         # Shared Wikimedia HTTP client (TLS, retries)
│   └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
├── tests/                    # pytest suite (178 tests)
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
  - Prompt rules 5 and 6 restate the translation_rules.md rules that hold at
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
```

> **Note:** always work inside the project's own virtualenv. Without activating it, an interpreter from another project (or the system Python) is used and `mwparserfromhell` and the other dependencies are missing, causing `ModuleNotFoundError`.

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
| `WIKI_CONTACT` | (optional) Contact info for the Wikimedia API User-Agent (email or wiki user page) |

The `.env` file is gitignored — never commit API keys.

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
- **Reference compression**: `REF_COMPRESS_THRESHOLD = 20` characters.
- **Wikimedia API**: `API_BATCH_SIZE` (50), `API_MAX_RETRIES`, `API_RETRY_BASE_DELAY`, `API_MAX_RETRY_DELAY`, `API_BATCH_DELAY` — 429 rate-limit handling. `API_USER_AGENT` is built from `API_CONTACT` (env `WIKI_CONTACT`); Wikimedia's User-Agent policy requires real contact info, so set it to your email or wiki user page.

Do **not** hardcode API keys into `config.py`. Use environment variables.

---

## Key Modules — Developer Notes

### `core/processor.py`
- Uses `mwparserfromhell` to parse and manipulate wikitext AST.
- `prepare(raw_wikitext)` returns a **5-tuple**: `(prepared_text, link_qid_map, cat_qid_map, tpl_qid_map, ref_map)`.
- `self.unresolved_links` — wikilink targets with no uz.wiki article, left in English for the model. `main.py` feeds it to `translate()`, and `finalize()` checks the model actually translated them.
- `finalize(translated_text, ref_map)` takes **2 arguments** — the QID-to-title resolution is done internally via `self.fetcher.get_sitelink()` during finalize, not from the maps returned by prepare. The in-memory cache populated during `prepare()` (especially uz sitelinks pre-cached by `batch_page_info()`) makes this near-free.

### `core/translator.py`
- `translate(text, forced_links=None)` sends prepared wikitext to OpenAI for translation.
- `forced_links` names the targets with no uz.wiki article one by one (`config.FORCED_LINKS_TEMPLATE`). A general rule does not work: the prepared text is dominated by `[[Q12345|...]]` placeholders the model must not touch, and it generalises that to plain English wikilinks too.
- Tracks `translations` count, `tokens_used`, `cached_tokens`, and `prompt_tokens` statistics.
- The system prompt explicitly tells the model to pass all `[[Q...]]`, `CAT:...`, and `{{TPL:...}}` placeholders through unchanged.

### `core/wikidata_fetcher.py`
- Uses **direct HTTP** (`urllib`, via `utils/api_client.py`) for every lookup. There is no pywikibot dependency: the batch endpoint below answers redirects, QIDs and sitelinks in one request, so the per-item client bought nothing.
- `get_sitelink(qid, target_lang)` — returns the article title on the target Wikipedia (direct HTTP, called in Phase 3). Uses raw dict check on `cache.sitelink_cache` to correctly detect `"NONE"` sentinel entries and avoid redundant API calls.
- `batch_page_info(titles, site_code)` — **the batch workhorse** used in Phase 1 (direct HTTP, no pywikibot). One `action=query&redirects=1&prop=pageprops|langlinks` request per 50 titles returns the redirect target, the QID and the uz title in a single round trip, and pre-caches uz/en sitelinks (bonus for Phase 3). Returns `{title: {"resolved", "qid", "uz_title"}}`.
- `batch_resolve_redirects()` / `batch_get_qids_fast()` — thin wrappers over `batch_page_info()`, kept for compatibility. Calling both in sequence costs one request: the second is served from cache.
- **Rate limiting:** `_wiki_api()` is a thin wrapper over `utils.api_client.wiki_api()`, which retries on HTTP 429/5xx honouring the `Retry-After` header (`config.API_MAX_RETRIES`, `API_RETRY_BASE_DELAY`, `API_MAX_RETRY_DELAY`); `batch_page_info()` sleeps `API_BATCH_DELAY` between batches. On a failed lookup nothing is written to the cache — an API error must never be recorded as "not found", and the affected titles land in `fetcher.failed_titles`.
- All results pass through `cache_manager` automatically.

### `core/reviewer.py`
- Phase 5 post-translation review via OpenAI.
- Uses `config.REVIEW_MODEL` (default `gpt-5.4-mini`) — separate from translation model to reduce cost.
- Loads `translation_rules.md` at init; if missing, `is_available()` returns `False` and the phase is skipped in `main.py`.
- `review(text)` formats the rules into `REVIEW_SYSTEM_PROMPT` (static — benefits from prompt caching) and the wikitext into `REVIEW_USER_PROMPT` (dynamic), strips markdown code fences from the response, and returns the corrected text (or `None` on failure).
- Tracks `reviews` count, `tokens_used`, `cached_tokens`; `print_stats()` emits a stats block at end of run.

### `core/cache_manager.py`
- In-memory 3-tier memoization: QID, sitelink, redirect. No disk persistence — each run starts empty.
- Cache values of `"NONE"` mean "looked up and not found" — do not re-query within the same run.
- Cache keys: `"site_code:title"` for QID/redirect, `"QID:target_site"` for sitelink.
- Within a single run, Phase 1 populates most entries (via `batch_page_info()` which pre-caches uz/en sitelinks), so Phase 3 mostly hits the cache.
- **Never cache a lookup that failed with an API error** — only genuine "not found" answers get the `"NONE"` sentinel.

### `utils/regex_patterns.py`
- Central registry of all regex patterns used across the codebase (`RegexPatterns` class).
- `apply_all_fixes(text)` applies every fix in the correct order:
  1. `fix_arabic_transliteration()` — diacritic removal (ā→a, ī→i, ū→u, etc.), final `-ī` → `-iy` suffix, and solar letter assimilation (`al-Roziy` → `ar-Roziy`). Implements Rules 1 & 2 from `translation_rules.md`. Skips `<ref>`, URLs, template params, and link targets.
  2. `fix_cite_book_script_title()` — `script-title` -> `title` in cite book templates
  3. `fix_year_with_dash()` — `2025 yil` -> `2025-yil`
  4. `fix_lik_suffix_capitalization()` — lowercase `-lik` suffix words mid-sentence
  5. `fix_punctuation_with_refs()` — move punctuation after `<ref>` tags (applied outside infoboxes via `_apply_fix_outside_infoboxes()`)
  6. `fix_punctuation_with_sfn()` — handle `{{sfn}}` template punctuation (applied outside infoboxes). Punctuation moves past a whole chain of templates, and a period is never invented in front of a lowercase word — the sentence is still running there.
  7. `fix_template_blank_lines()` — remove blank lines inside multiline templates
  8. Collapse 3+ consecutive newlines to 2
- `_apply_fix_outside_infoboxes(wikitext, fix_func)` — wraps a fix function to skip infobox templates.
- Modify patterns here, not inline in other files.

### `utils/localization.py`
- Reads `localization_map.json` at startup (223 entries).
- Patterns compiled once (longest-key-first for greedy matching).
- `add_replacement()` / `remove_replacement()` for runtime edits.
- To add a new term replacement, edit `localization_map.json` directly — no code changes needed.

### `utils/logger.py`
- Singleton — instantiated at module level as `logger = Logger()`.
- Import with: `from utils.logger import logger`
- Console-only output (no file logging).
- Use `logger.section()`, `logger.success()`, `logger.fail()`, `logger.stats()`, `logger.progress()`, `logger.table()` for structured output.

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
- Static methods for all file I/O: `read_file()`, `write_file()`, `read_json()`, `write_json()`, `append_file()`, `read_lines()`, `create_backup()`, `delete_file()`, `file_exists()`, `get_file_size()`, `ensure_dir_exists()`.
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
| **Apostrophes** | Bold markup is three straight ASCII apostrophes (`'''`, U+0027 x3) — a curly variant produces no bold at all. Inside Uzbek words the curly characters are letters, not markup: `ʻ` (U+02BB) in `oʻ`/`gʻ`, `ʼ` (U+02BC) for tutuq belgisi (`Saʼd`). `localization_map.json` converts straight apostrophes to those letters — never to the typographic quotes U+2018/U+2019 |

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

**Automated tests** — 178 tests under `tests/`, run with:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

`pytest.ini` sets `testpaths = tests` and `pythonpath = .`, so plain `pytest` works from the repo root. Coverage by module:

| Test file | Tests | Covers |
|---|---|---|
| `test_regex_patterns.py` | 57 | `utils/regex_patterns.py` |
| `test_file_handler.py` | 29 | `utils/file_handler.py` |
| `test_cache_manager.py` | 27 | `core/cache_manager.py` |
| `test_wiki_fetcher.py` | 23 | `utils/wiki_fetcher.py` |
| `test_reviewer.py` | 19 | `core/reviewer.py` |
| `test_translator.py` | 16 | `core/translator.py` |
| `test_api_client.py` | 7 | `utils/api_client.py` |

No network or OpenAI calls are made — `urlopen` and the OpenAI client are monkeypatched (`tests/conftest.py` holds the shared fixtures). `core/processor.py`, `core/wikidata_fetcher.py`, `utils/localization.py` and `main.py` are **not** covered yet.

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
