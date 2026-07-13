# Wikipedia Translator

An English → Uzbek Wikipedia article translator. It uses OpenAI to translate wikitext while preserving MediaWiki markup, wikilinks, templates, and categories, and resolves internal links via Wikidata so they point to the correct Uzbek Wikipedia articles.

## How it works

Translation runs through a 5-phase pipeline:

1. **Prepare** (`core/processor.py`) — parses the wikitext with `mwparserfromhell`, replaces wikilinks/categories/templates with Wikidata QID placeholders, and compresses long `<ref>` blocks.
2. **Translate** (`core/translator.py`) — sends the prepared wikitext to OpenAI. Placeholders pass through untouched.
3. **Finalize** (`core/processor.py`) — resolves QID placeholders back to Uzbek Wikipedia titles/categories/templates via Wikidata sitelinks, falling back to the English title when no Uzbek article exists, and restores compressed references.
4. **Localize** (`utils/localization.py`) — applies ~215 term/style replacements from `localization_map.json`.
5. **Review** (`core/reviewer.py`) — a second OpenAI pass checks the result against `translation_rules.md` and fixes rule violations, without altering the wikitext structure.

## Requirements

- Python 3.12
- [pipenv](https://pipenv.pypa.io/)
- An OpenAI API key

## Installation

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv install
```

> `PIPENV_IGNORE_VIRTUALENVS=1` is required because pipenv otherwise detects any already-active virtualenv and uses it instead of this project's own `.venv`, causing `ModuleNotFoundError` for dependencies like `pywikibot`.

Create a `.env` file (gitignored) with:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (required) |
| `OPENAI_MODEL` | Translation model (optional, defaults to `gpt-5.2`) |
| `REVIEW_MODEL` | Phase 5 review model (optional, defaults to `gpt-5.4-mini`) |

## Usage

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run python main.py input_en.txt output_uz.txt
```

1. Place English Wikipedia wikitext in `input_en.txt` (download it with `utils/wiki_fetcher.py` or paste it manually).
2. Run `main.py` with the input and output file paths.
3. Review `output_uz.txt` against the checklist in `translation_rules.md`.
4. The output is also auto-saved to `temp_wiki/<Article Name>.txt` (gitignored).

### Translating multiple articles

`main.py` only accepts file paths, not URLs or article names. To batch-translate:

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

## Additional tools

`additional-tools/category-checker.py` checks which articles in an English Wikipedia category are missing from Uzbek Wikipedia (via Wikidata sitelinks):

```bash
python additional-tools/category-checker.py "11th-century Arabic-language poets"

# Open the first 5 missing articles in a browser
python additional-tools/category-checker.py "Uzbek writers" --open 5
```

## Project structure

```
wikipedia-translator/
├── main.py                   # Entry point; orchestrates the 5-phase pipeline
├── config.py                 # All configuration (models, prompts, tuning)
├── localization_map.json     # Term replacement rules (auto-loaded)
├── translation_rules.md      # Post-translation review checklist (used by Phase 5)
├── core/
│   ├── translator.py         # AI translation engine (OpenAI)
│   ├── processor.py          # Wikitext prepare/finalize (QID placeholders)
│   ├── wikidata_fetcher.py   # Wikidata/Wikipedia API calls
│   ├── cache_manager.py      # In-memory 3-tier memoization (QID, sitelink, redirect)
│   └── reviewer.py           # AI post-translation review (Phase 5)
├── utils/
│   ├── file_handler.py       # File I/O (UTF-8, JSON, backup)
│   ├── localization.py       # Loads and applies localization_map.json
│   ├── logger.py             # Singleton logger (console-only)
│   ├── regex_patterns.py     # Centralized regex patterns and fix functions
│   └── wiki_fetcher.py       # Downloads English Wikipedia wikitext via API
├── additional-tools/
│   └── category-checker.py   # Checks which category articles are missing from uz.wiki
└── tests/                    # pytest test suite
```

## Testing

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run pytest
```

## License

No license has been specified for this project.
