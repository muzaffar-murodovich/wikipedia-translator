#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config.py - Butun loyiha uchun markaziy konfiguratsiya
Barcha sozlamalar shu yerda. Bosh fayllarni tahrirlash shart emas!
"""

import os
from pathlib import Path

# ============================================================
# OpenAI Sozlamalari
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# ============================================================
# Wikipedia Sozlamalari
# ============================================================

WIKIPEDIA_FAMILY = "wikipedia"
SOURCE_LANG = "en"  # Inglizcha'dan
TARGET_LANG = "uz"  # O'zbek tiliga

# ============================================================
# Parallel Processing Sozlamalari
# ============================================================

MAX_WORKERS = 3                    # Parallel thread'lar soni
REQUEST_DELAY = 0.5                # So'rovlar orasida 0.5 soniya

# ============================================================
# Pywikibot Konfiguratsiyasi
# ============================================================

PYWIKIBOT_CONFIG = {
    "maxlag": 5,                   # Server lag 5s dan oshsa kutish
    "put_throttle": 1,             # Edits orasida 1s kutish
    "noisysleep": False,           # "Sleeping..." xabarlarini yashirish
    "max_retries": 3,              # 3 marta urinish
    "retry_wait": 10,              # Xato bo'lsa 10s kutish
}

# ============================================================
# Cache Sozlamalari
# ============================================================

CACHE_DIR = Path(".wiki_cache")
CACHE_DIR.mkdir(exist_ok=True)

QID_CACHE_FILE = CACHE_DIR / "qid_cache.json"
SITELINK_CACHE_FILE = CACHE_DIR / "sitelink_cache.json"
REDIRECT_CACHE_FILE = CACHE_DIR / "redirect_cache.json"

# ============================================================
# Localization Sozlamalari
# ============================================================

LOCALIZATION_FILE = Path("localization_map.json")

# ============================================================
# Reference Compression
# ============================================================

REF_COMPRESS_THRESHOLD = 20  # 20 belgidan uzun ref'larni siqish

# ============================================================
# Fallback Mappinglar
# ============================================================

FALLBACK_TEMPLATE_MAP_EN2UZ = {
    "infobox person": "Shaxs bilgiqutisi",
    "infobox place": "Joyni bilgiqutisi",
    "infobox country": "Davlatni bilgiqutisi",
    # Qo'shimcha andozalar qo'shish mumkin
}

FALLBACK_CATEGORY_PREFIX = "Turkum"

# ============================================================
# Logging Sozlamalari
# ============================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = Path("translation.log")

# ============================================================
# Tarjima Prompt Sozlamalari
# ============================================================

TRANSLATION_SYSTEM_PROMPT = "Siz oʻzbekcha Vikipediya muharririsiz."

TRANSLATION_USER_PROMPT = """
Quyidagi wikitext'ni oʻzbek tiliga tarjima qiling. MUHIM QOIDALAR:

1) Quyidagi placeholder'larni aynan oʻz holicha qoldiring:
   - [[Q12345|...]] koʻrinishidagi havolalarda: QID (masalan, Q12345) oʻzgarmasin; faqat '|' dan keyingi label'ni oʻzbekchaga tarjima qiling.
   - ⟦CAT:Q12345|...⟧ koʻrinishidagi tokenlarda: QID oʻzgarmasin; faqat '|' dan keyingi label'ni oʻzbekchaga tarjima qiling.
   - Template nomlari 'TPL:Q12345' koʻrinishida boʻladi — ularni aynan shunday qoldiring. Template parametrlarining qiymatlari tarjima qiling, lekin parametr kalitlari (key) oʻzgartirmang.
   - REF_ bilan boshlanadigan qisqa manbalarni oʻzgartirmang.

2) Strukturani saqlang: sarlavhalar, roʻyxatlar, {{...}} va boshqa wikitext sintaksisi buzilmasin.

3) Ismlar: Agar biror ism oʻzbekchaga yaqin boʻlsa, uni oʻzbekchaga moslab yozing. Masalan, "Abdullah Maroofi" emas, "Abdulloh Marufiy" deb yozing. Oʻzbek tilida "w" harfi yoʻq. Shuning uchun ismlarda, joy nomlarida "w" ning oʻrniga "v" harfini ishlating.

4) Izoh yozmang. Faqat wikitext chiqaring.

Matn:
```{text}```
"""

# ============================================================
# Xatolik Xabarlari
# ============================================================

ERROR_MESSAGES = {
    "maxlag_timeout": "⚠️  Wikipedia serverlari band. Keyinroq urinib ko'ring.",
    "api_error": "❌ API xatosi. Internet ulanishini tekshiring.",
    "invalid_qid": "⚠️  Noto'g'ri QID formatı.",
    "file_not_found": "❌ Fayl topilmadi.",
    "json_error": "❌ JSON formatida xato.",
}

# ============================================================
# Qo'shimcha Sozlamalar
# ============================================================

VERBOSE = True  # Batafsil xabarlar chiqarish
DEBUG = False   # Debug rejimi