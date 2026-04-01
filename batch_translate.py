"""Batch translation script — full or trimmed."""
import re
import subprocess
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.wiki_fetcher import fetch_wikitext


def estimate_trimmed(wikitext: str):
    if not wikitext:
        return None
    first_section = re.search(r'^(==[^=])', wikitext, re.MULTILINE)
    if not first_section:
        return None
    intro = wikitext[:first_section.start()]
    ref_match = re.search(
        r'^(==\s*(?:References|Sources|Bibliography|Notes|Further reading|External links)\s*==)',
        wikitext, re.MULTILINE | re.IGNORECASE
    )
    if not ref_match:
        return None
    tail = wikitext[ref_match.start():]
    trimmed = intro.rstrip() + "\n\n" + tail
    if "<ref" not in trimmed.lower():
        return None
    return trimmed


def translate_article(title: str, trim: bool = False):
    print(f"\n{'='*60}")
    print(f"Fetching: {title}  [trim={trim}]")
    wikitext, _ = fetch_wikitext(title)
    if not wikitext:
        print(f"  ERROR: could not fetch wikitext for '{title}'")
        return

    if trim:
        trimmed = estimate_trimmed(wikitext)
        if trimmed is None:
            print(f"  WARNING: trimming failed, using full text")
        else:
            wikitext = trimmed
            print(f"  Trimmed to {len(wikitext)} bytes")

    with open("input_en.txt", "w", encoding="utf-8") as f:
        f.write(wikitext)

    safe = title.replace(" ", "_").replace("/", "_")
    out_file = f"output_{safe}.txt"
    print(f"  Translating → {out_file}")
    result = subprocess.run(
        ["pipenv", "run", "python", "main.py", "input_en.txt", out_file],
        env={**os.environ, "PIPENV_IGNORE_VIRTUALENVS": "1"},
    )
    if result.returncode != 0:
        print(f"  ERROR: translation failed (exit {result.returncode})")
    else:
        os.makedirs("temp_wiki", exist_ok=True)
        dest = f"temp_wiki/{title}.txt"
        with open(out_file, "r", encoding="utf-8") as src, \
             open(dest, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        print(f"  Saved to temp_wiki/{title}.txt")


FULL = [
    "Ibn Khalawayh",
    "Al-Hatimi",
]

TRIMMED = [
    "Abu Bakr bin Yahya al-Suli",
    "Abu Hilal al-Askari",
    "Abu Abdallah al-Husayn ibn Ahmad al-Mughallis",
]

for t in FULL:
    translate_article(t, trim=False)

for t in TRIMMED:
    translate_article(t, trim=True)

print("\nDone.")
