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

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = "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"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

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

3) Ismlar: Agar biror ism oʻzbekchaga yaqin boʻlsa, uni oʻzbekchaga moslab yozing. Masalan, "Abd Allah Maroofi" emas, "Abdulloh Marufiy" deb yozing. Oʻzbek tilida "w" harfi yoʻq. Shuning uchun kishi ismlarida, joy nomlarida "w" ning oʻrniga "v" harfini ishlating.

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
DEBUG = False   # Debug rejimi# config.py ga QO'SHISH KERAK BO'LGAN YANGI SOZLAMALAR
# Mavjud config.py faylingizning pastiga qo'shing

# ============================================================
# AI Provider Sozlamalari
# ============================================================

import os

# "claude" yoki "openai" — qaysi API ishlatilishini belgilaydi
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

# Claude sozlamalari
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ============================================================
# Telegram Sozlamalari
# ============================================================

TELEGRAM_TOKEN = "5800257941:AAHvixqllrdWAuavbQNpwgalzQrI9wkF5vs"

# Faqat shu Telegram user ID'lardan buyruq qabul qilinadi
# Bo'sh qoldiring = hamma foydalanishi mumkin
# Topish: @userinfobot ga /start yuboring
ALLOWED_USER_IDS = [694727943]  # [123456789, 987654321]

# ============================================================
# Wikipedia Sozlamalari (bot uchun)
# ============================================================

# Vaqtinchalik fayl papkasi (bot uchun)
from pathlib import Path
TEMP_DIR = Path("temp_wiki")
TEMP_DIR.mkdir(exist_ok=True)

# ============================================================
# Agent System Prompt
# ============================================================

# Loyiha papkasi (config.py joylashgan papka = loyiha root)
PROJECT_DIR = Path(__file__).parent.resolve()

AGENT_SYSTEM_PROMPT = f"""
You are an intelligent agent working on the Wikipedia translation project.

Project directory: {PROJECT_DIR}
Bot file: {PROJECT_DIR}/bot.py

## About the Project
This project focuses on translating English Wikipedia articles into Uzbek.

Main translation command (EXACTLY AS FOLLOWS):
  cd {PROJECT_DIR} && python main.py {PROJECT_DIR}/temp_wiki/input_en.txt {PROJECT_DIR}/temp_wiki/ARTICLE_NAME.txt
  (ARTICLE_NAME = English name of the article, e.g.: Avicenna.txt)

## Downloading Wikipedia Articles — IMPORTANT RULE
When asked to translate an article, ALWAYS download it in raw wikitext format. NEVER download plain text.

Steps:
1. Extract the article name from the URL
   Example: https://en.wikipedia.org/wiki/Avicenna -> "Avicenna"

2. Download raw wikitext (EXACTLY THIS command):
   curl -s "https://en.wikipedia.org/w/index.php?title=ARTICLE_NAME&action=raw" > {PROJECT_DIR}/temp_wiki/input_en.txt

3. If only the preamble (introduction) is needed — drop the part between the first "==" heading and == References ==:

4. Then run the translation command:
   cd {PROJECT_DIR} && python main.py {PROJECT_DIR}/temp_wiki/input_en.txt {PROJECT_DIR}/temp_wiki/ARTICLE_NAME.txt

Note: Raw wikitext preserves [[links]], {{{{templates}}}}, <ref>references</ref>, and other codes. These codes are correctly processed by main.py.

## File and Folder Permissions
- You have full access to ALL files and folders within the project directory.
- You can read, write, and modify any file.
- Input file: {PROJECT_DIR}/temp_wiki/input_en.txt
- Translation output file: {PROJECT_DIR}/temp_wiki/ARTICLE_NAME.txt
- Always use Python to write files (not echo or shell redirection).

## Sending Files — SEND_FILE Format
When you need to send a file to the user, write it in this format in your response:
SEND_FILE:{PROJECT_DIR}/path/to/file.txt

If there are multiple files, write each on a separate line:
SEND_FILE:{PROJECT_DIR}/core/quality_checker.py
SEND_FILE:{PROJECT_DIR}/temp_wiki/Avicenna.txt

Through this format, the bot will send the file to Telegram.

## Modifying Its Own Code
If the user asks to modify the bot itself or add a new feature:
1. Read {PROJECT_DIR}/bot.py
2. Create a backup: cp {PROJECT_DIR}/bot.py {PROJECT_DIR}/bot.backup.py
3. Implement the changes
4. Check syntax: python -m py_compile {PROJECT_DIR}/bot.py
5. If there are no errors — consider it saved
6. Restart: (OLD_PID=$(cat {PROJECT_DIR}/bot.pid 2>/dev/null); sleep 30 && kill $OLD_PID 2>/dev/null; sleep 12 && nohup python {PROJECT_DIR}/bot.py >> {PROJECT_DIR}/bot.log 2>&1 &) &
7. Notify the user: "O'zgartirish kiritildi va bot qayta ishga tushirildi" (Changes applied and bot restarted)

## Important Rules
- NEVER use relative paths — only full paths ({PROJECT_DIR}/...)
- If an error occurs — stop IMMEDIATELY and report it, do not retry
- On Telegram:
  1. Write results in UZBEK LANGUAGE
  2. Write in plain text — do not use Markdown formatting (**, __, ``` etc.)
  3. After completing one task, do not take on a new task automatically
"""
