# CLAUDE.md — Wikipedia Translator

## Project Overview

An **English-to-Uzbek Wikipedia article translator** that uses AI (Claude or OpenAI) to translate wikitext while preserving MediaWiki markup, wikilinks, templates, and categories. It resolves article links via Wikidata so that internal links point to the correct Uzbek Wikipedia equivalents.

---

## Repository Structure

```
wikipedia-translator/
├── main.py                   # Entry point; orchestrates the 4-phase pipeline
├── article_finder.py         # Auto-discovery: BFS category crawl + uz.wiki check
├── seed_categories.json      # Root categories for auto-discovery (Islam topics)
├── config.py                 # All configuration (comments/values in Uzbek)
├── localization_map.json     # 130+ term replacement rules (auto-loaded)
├── config.env                # Environment variable overrides (empty template)
├── Pipfile / Pipfile.lock    # Python 3.12 dependencies (pipenv)
├── input_en.txt              # English Wikipedia wikitext input (generated)
├── output_uz.txt             # Translated Uzbek output
├── core/
│   ├── translator.py         # AI translation engine (Claude & OpenAI)
│   ├── processor.py          # Wikitext prepare/finalize (QID placeholders)
│   ├── wikidata_fetcher.py   # Wikidata/Wikipedia API calls
│   ├── cache_manager.py      # 3-tier JSON cache (QID, sitelink, redirect)
│   └── quality_checker.py    # Post-translation QA checks
└── utils/
    ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
    ├── localization.py       # Loads and applies localization_map.json
    ├── logger.py             # Singleton logger (console + file)
    ├── regex_patterns.py     # Centralised regex patterns and fix functions
    └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
```

Cache lives in `.wiki_cache/` (gitignored) and grows automatically:
- `qid_cache.json` — title → QID mappings
- `sitelink_cache.json` — QID → Uzbek Wikipedia title mappings
- `redirect_cache.json` — redirect resolution results
- `finder_progress.json` — article finder progress (discovered articles, scanned categories, subcategory tree)

---

## Article Finder (`article_finder.py`)

Automatically discovers English Wikipedia articles that are missing from Uzbek Wikipedia, using BFS crawling of seed categories.

### Two modes

```bash
# Auto mode (no arguments) — crawls seed categories, shows pending articles
python article_finder.py

# Legacy mode — search a specific category
python article_finder.py "11th-century Arabic-language poets"
python article_finder.py "Islamic scholars" --max-size 50000
```

### How auto mode works

```
seed_categories.json (enabled, sorted by priority)
    │
    ├─ Load finder_progress.json
    ├─ If pending articles exist → display them
    └─ Otherwise → scan next categories:
        ├─ crawl_category_tree() — BFS with depth limit
        ├─ get_category_members() — articles per subcategory
        ├─ check_uz_exists_batch_fast() — Wikidata batch API (50/request)
        └─ Stop when 20+ pending articles found
            │
            ▼
        Interactive menu:
        [1-20] select article → download wikitext → save to input_en.txt
        [n] next page | [p] prev page | [s] scan more | [i] stats | [0] quit
```

### Key functions

| Function | Purpose |
|---|---|
| `_wiki_api()` | Centralized Wikipedia/Wikidata API helper |
| `get_category_members()` | Fetch articles in a category (namespace=0) |
| `get_subcategories()` | Fetch subcategories (`cmtype=subcat`) |
| `crawl_category_tree()` | BFS crawl with depth limit and cycle prevention |
| `check_uz_exists_batch_fast()` | Wikidata `wbgetentities` batch check (~50x faster than pywikibot) |
| `estimate_trimmed()` | Trim article: keep intro + references, remove body sections |
| `FinderProgress` class | Progress tracking via `.wiki_cache/finder_progress.json` |
| `scan_categories()` | Orchestrates BFS crawl + article discovery |
| `auto_discover()` | Main interactive loop |
| `select_and_save()` | Download wikitext, offer trimming, save to `input_en.txt` |

### `seed_categories.json`

Defines root categories for auto-crawling. Each entry:
```json
{"name": "Islamic scholars", "depth": 2, "priority": 2, "enabled": true}
```
- `depth` — subcategory crawl limit (0 = only root)
- `priority` — lower = scanned first
- `enabled` — set `false` to skip without deleting

### Article trimming

For large articles (>`FINDER_TRIM_THRESHOLD` bytes), the finder offers to trim:
1. Keep everything before the first `== ==` section header (intro)
2. Remove body content
3. Keep from `== References ==` (or Sources/Bibliography/Notes) onward
4. Only if the trimmed result contains at least one `<ref`

### Progress tracking (`FinderProgress`)

Article statuses: `pending` → `translated` | `skipped` | `has_uz`

Progress persists across runs in `.wiki_cache/finder_progress.json`. Previously scanned categories and known articles are not re-checked.

---

## Translation Pipeline (4 phases)

```
input_en.txt
    │
    ▼
Phase 1 — PREPARE (core/processor.py)
  • Replaces [[wikilinks]] with [[Q12345|label]] placeholders
  • Replaces [[Category:…]] with ⟦CAT:Q12345|label⟧ placeholders
  • Replaces {{templates}} with {{TPL:Q12345}} placeholders
  • Compresses long <ref>…</ref> blocks to short hashes
    │
    ▼
Phase 2 — TRANSLATE (core/translator.py)
  • Sends prepared wikitext to Claude or OpenAI
  • Placeholders pass through untouched (model instructed to preserve them)
    │
    ▼
Phase 3 — FINALIZE (core/processor.py)
  • Resolves QID placeholders → Uzbek Wikipedia titles via Wikidata
  • Falls back to English title when no Uzbek sitelink exists
  • Restores compressed <ref> blocks
    │
    ▼
Phase 4 — LOCALIZE (utils/localization.py)
  • Applies 130+ regex replacements from localization_map.json
  • Examples: [[Category: → [[Turkum:, == References == → == Manbalar ==
    │
    ▼
output_uz.txt  +  quality report
```

---

## Running

```bash
# Install dependencies
pipenv install

# 1. Find an article to translate (auto mode)
python article_finder.py
# → discovers articles, saves selected one to input_en.txt

# 2. Translate
python main.py input_en.txt output_uz.txt

# Or pass a Wikipedia article URL / title directly (wiki_fetcher downloads it)
python main.py "https://en.wikipedia.org/wiki/Example" output_uz.txt
```

### Required Environment Variables

Set these in `config.env` or export before running:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `PYWIKIBOT_NO_USER_CONFIG=2` | Prevent pywikibot from loading local config |

`config.env` is gitignored — never commit API keys.

---

## Configuration (`config.py`)

All configuration is in a single file. Comments and string values are written in **Uzbek**. Key settings:

- **AI provider / model**: switch between `claude-sonnet-4-6`, `gpt-4o`, etc.
- **Source / target languages**: English → Uzbek (`uz`)
- **Cache paths**: `.wiki_cache/` directory
- **Pywikibot tuning**: `maxlag=5`, `put_throttle=1`, `max_retries=3`
- **Translation system prompt**: instructs the model to preserve QID placeholders and transliterate names (w→v rule for Uzbek)
- **Fallback template mappings**: when Wikidata has no sitelink
- **Article Finder**: `SEED_CATEGORIES_FILE`, `FINDER_PROGRESS_FILE`, `FINDER_MAX_DEPTH=3`, `FINDER_PAGE_SIZE=20`, `FINDER_TRIM_THRESHOLD=6000` (bytes)

Do **not** hardcode API keys into `config.py`. Use environment variables.

---

## Key Modules — Developer Notes

### `core/translator.py`
- `translate(text)` dispatches to `_translate_claude()` or `_translate_openai()` based on config.
- Tracks `translation_count` and `total_tokens` statistics.
- The system prompt explicitly tells the model to pass all `[[Q…]]`, `⟦CAT:…⟧`, and `{{TPL:…}}` placeholders through unchanged.

### `core/processor.py`
- `prepare(wikitext)` returns `(processed_text, qid_map, ref_map)`.
- `finalize(text, qid_map, ref_map)` resolves placeholders back to titles.
- Reference compression threshold: 20 characters (configurable in the class).

### `core/wikidata_fetcher.py`
- Uses **pywikibot** for Wikidata queries.
- `get_qid(title, site)` — resolves a Wikipedia title to its QID.
- `get_sitelink(qid, target_site)` — returns the article title on the target Wikipedia.
- Batch methods available for parallel lookups.
- All results pass through `cache_manager` automatically.

### `core/cache_manager.py`
- Cache values of `"NONE"` mean "looked up and not found" — do not re-query.
- Cache files are loaded at startup and saved at shutdown (and after major operations).
- `import_cache()` / `export_cache()` helpers for backup/restore.

### `utils/regex_patterns.py`
- Central registry of all regex patterns used across the codebase.
- `apply_all_fixes(text)` applies every fix in the correct order.
- Contains Uzbek-specific fixes: `fix_lik_suffix_capitalization()`, `fix_year_with_dash()`.
- Modify patterns here, not inline in other files.

### `utils/localization.py`
- Reads `localization_map.json` at startup.
- Patterns compiled once (longest-key-first for greedy matching).
- `add_replacement()` / `remove_replacement()` for runtime edits.
- To add a new term replacement, edit `localization_map.json` directly.

### `utils/logger.py`
- Singleton — obtain via `Logger.get_instance()`.
- Writes to both console and `translation.log`.
- Use `logger.section()`, `logger.success()`, `logger.fail()`, `logger.stats()` for structured output.

---

## Code Conventions

| Convention | Detail |
|---|---|
| **Language** | File/class/function names in English; comments, docstrings, error messages in Uzbek |
| **Encoding** | UTF-8 everywhere; always open files with `encoding="utf-8"` |
| **Type hints** | Use `Optional`, `Dict`, `List`, `Tuple` from `typing` |
| **Null sentinel** | Use the string `"NONE"` (not Python `None`) for cache "not found" entries |
| **Error handling** | Catch exceptions, log with the logger, return a safe fallback — avoid bare `raise` in pipeline code |
| **Logging** | Always use the singleton `Logger`; never use `print()` in library code |
| **Patterns** | New regex patterns go into `utils/regex_patterns.py`, not inline |
| **Config** | New settings go into `config.py` only; no magic strings scattered in code |
| **Design patterns** | Singleton (Logger), Manager (Cache, Localization), Pipeline (main.py phases) |

---

## Adding Features

### New AI provider
1. Add credentials and model name to `config.py`.
2. Add a `_translate_<provider>()` method in `core/translator.py`.
3. Update the dispatch logic in `translate()`.

### New localization rule
Add an entry to `localization_map.json`:
```json
"English term": "Oʻzbekcha atama"
```
No code changes needed — it is loaded automatically.

### New regex fix
Add a static method to `utils/regex_patterns.py` and call it from `apply_all_fixes()`.

### New seed category
Add an entry to `seed_categories.json`:
```json
{"name": "Category name", "depth": 2, "priority": 5, "enabled": true}
```
No code changes needed. Delete `.wiki_cache/finder_progress.json` to force a fresh scan, or let it scan incrementally.

### New cache tier
Extend `core/cache_manager.py` following the same `get/set/save/load` pattern as existing tiers.

---

## Testing & Quality

There is no automated test suite. Validation is done by:

1. **`core/quality_checker.py`** — run automatically after Phase 4; reports:
   - Unresolved QID/template/category placeholders
   - Empty wikilinks
   - Bracket mismatches
   - Unrestore reference hashes
2. **Manual inspection** of `output_uz.txt` using rules in **`translation_rules.md`** (name transliteration, solar letters, wikilink consistency).
3. **Logger statistics** printed at the end of each run (cache hit rates, token counts, translation counts).

When adding new placeholder types or fixes, add corresponding checks to `quality_checker.py`.

---

## Git Workflow

- Development branch naming: `claude/<description>-<sessionId>`
- Commit messages are short and descriptive in English.
- **Never commit** `config.env`, API keys, `output*.txt`, `*.log`, or `temp_wiki/` — all excluded by `.gitignore`.
- `seed_categories.json` **is** committed — it defines which categories to crawl.
- Push with: `git push -u origin <branch-name>`

---

## Dependencies (Pipfile)

| Package | Purpose |
|---|---|
| `anthropic` | Claude API client |
| `openai` | OpenAI API client |
| `aiohttp` | Async HTTP for API calls |
| `pywikibot` | Wikidata / Wikipedia API |
| `python-telegram-bot` | Optional Telegram bot interface |
| `claude-agent-sdk` | Claude Agent SDK integration |

Python version: **3.12**

Install: `pipenv install`
