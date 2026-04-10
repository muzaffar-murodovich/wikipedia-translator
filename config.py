#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config.py - Central configuration for the entire project
All settings are here. No need to edit main files!
"""

import os
from pathlib import Path

# --- OpenAI Settings ---

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

# --- Wikipedia Settings ---

WIKIPEDIA_FAMILY = "wikipedia"
SOURCE_LANG = "en"  # Source language
TARGET_LANG = "uz"  # Target language

# --- Parallel Processing Settings ---

MAX_WORKERS = 1                    # Number of parallel threads
REQUEST_DELAY = 1                  # Delay between requests (seconds)

# --- Pywikibot Configuration ---

PYWIKIBOT_CONFIG = {
    "maxlag": 10,                   # Wait if server lag exceeds 5s
    "put_throttle": 1,             # Wait 1s between edits
    "noisysleep": False,           # Suppress "Sleeping..." messages
    "max_retries": 8,              # Retry attempts
    "retry_wait": 20,              # Wait time after error (seconds)
}

# --- Cache Settings ---

CACHE_DIR = Path(".wiki_cache")
CACHE_DIR.mkdir(exist_ok=True)

QID_CACHE_FILE = CACHE_DIR / "qid_cache.json"
SITELINK_CACHE_FILE = CACHE_DIR / "sitelink_cache.json"
REDIRECT_CACHE_FILE = CACHE_DIR / "redirect_cache.json"

# --- Localization Settings ---

LOCALIZATION_FILE = Path("localization_map.json")

# --- Reference Compression ---

REF_COMPRESS_THRESHOLD = 20  # Compress refs longer than 20 characters

# --- Fallback Mappings ---

FALLBACK_TEMPLATE_MAP_EN2UZ = {
    "infobox person": "Shaxs bilgiqutisi",
    "infobox place": "Joyni bilgiqutisi",
    "infobox country": "Davlatni bilgiqutisi",
}

FALLBACK_CATEGORY_PREFIX = "Turkum"

# --- Logging Settings ---

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# --- Translation Prompt Settings ---

TRANSLATION_SYSTEM_PROMPT = "Siz oʻzbekcha Vikipediya muharririsiz."

TRANSLATION_USER_PROMPT = """
Quyidagi wikitext'ni oʻzbek tiliga tarjima qiling. MUHIM QOIDALAR:

1) Quyidagi placeholder'larni aynan oʻz holicha qoldiring:
   - [[Q12345|...]] koʻrinishidagi havolalarda: QID (masalan, Q12345) oʻzgarmasin; faqat '|' dan keyingi label'ni oʻzbekchaga tarjima qiling.
   - ⟦CAT:Q12345|...⟧ koʻrinishidagi tokenlarda: QID oʻzgarmasin; faqat '|' dan keyingi label'ni oʻzbekchaga tarjima qiling.
   - Template nomlari 'TPL:Q12345' koʻrinishida boʻladi — ularni aynan shunday qoldiring. Template parametrlarining qiymatlari tarjima qiling, lekin parametr kalitlari (key) oʻzgartirmang.
   - REF_ bilan boshlanadigan qisqa manbalarni oʻzgartirmang.

2) Strukturani saqlang: sarlavhalar, roʻyxatlar, {{...}} va boshqa wikitext sintaksisi buzilmasin.

3) Ismlar: Agar biror ism oʻzbekchaga yaqin boʻlsa, uni oʻzbekchaga moslab yozing. Masalan, "Abd Allah Maroofi" emas, "Abdulloh Marufiy" deb yozing. Oʻzbek tilida "w" harfi yoʻq. Shuning uchun kishi ismlarida, joy nomlarida "w" ning oʻrniga "v" harfini ishlating.

4) Izoh yozmang. Faqat wikitext chiqaring.

Matn:
```{text}```
"""

# --- Error Messages ---

ERROR_MESSAGES = {
    "maxlag_timeout": "⚠️  Wikipedia serverlari band. Keyinroq urinib ko'ring.",
    "api_error": "❌ API xatosi. Internet ulanishini tekshiring.",
    "invalid_qid": "⚠️  Noto'g'ri QID formatı.",
    "file_not_found": "❌ Fayl topilmadi.",
    "json_error": "❌ JSON formatida xato.",
}

# --- Additional Settings ---

VERBOSE = True  # Enable verbose output
DEBUG = False   # Debug mode
