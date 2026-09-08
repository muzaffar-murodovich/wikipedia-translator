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
REVIEW_MODEL = os.getenv("REVIEW_MODEL", "gpt-5.4-mini")
# Phase 5 (REVIEW)
ENABLE_REVIEW = True

# --- Wikipedia Settings ---

WIKIPEDIA_FAMILY = "wikipedia"
SOURCE_LANG = "en"  # Source language
TARGET_LANG = "uz"  # Target language

# --- Parallel Processing Settings ---

MAX_WORKERS = 1                    # Number of parallel threads
REQUEST_DELAY = 1                  # Delay between requests (seconds)

# --- Wikimedia API Settings ---

API_BATCH_SIZE = 50          # Bitta so'rovdagi sarlavhalar soni (API limiti)
API_MAX_RETRIES = 5          # 429/503 xatolarida qayta urinishlar soni
API_RETRY_BASE_DELAY = 1.0   # Qayta urinishlar orasidagi boshlang'ich kutish (soniya)
API_MAX_RETRY_DELAY = 30.0   # Qayta urinishda maksimal kutish (soniya)
API_BATCH_DELAY = 1.0        # Ketma-ket batch so'rovlar orasidagi pauza (soniya)

# Wikimedia User-Agent siyosati kontakt ma'lumotini talab qiladi:
# https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
# .env da WIKI_CONTACT ni o'z email yoki foydalanuvchi sahifangizga o'zgartiring.
API_CONTACT = os.getenv("WIKI_CONTACT", "https://uz.wikipedia.org/wiki/Vikipediya:Bot")
API_USER_AGENT = f"WikiTranslatorBot/1.0 ({API_CONTACT}) python-urllib/3.12"

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

2) Oddiy ingliz wikilinklarini (QID emas) toʻliq tarjima qiling — HAM target, HAM label.
   Target hech qachon inglizcha qolmasin: oʻzbek Vikipediyasida bunday maqola boʻlmasa
   ham, havola oʻzbekcha nom bilan yoziladi (qizil havola boʻlishi normal holat).
   Masalan:
   - [[Treaty of Safar]] → [[Safar shartnomasi]]
   - [[Tarsus, Mersin|Tarsus]] → [[Tars, Mersin|Tars]]
   - [[Dilawar Khan (politician)]] → [[Dilovar Xon (siyosatchi)]]
   - [[Sa'd al-Dawla al-Qawwasi|Sa'd al-Dawla]] → [[Saʼd ad-Davla al-Qavvasiy|Saʼd ad-Davla]]
   - Agar oʻzbek tilidagi nomi nomaʼlum boʻlsa — fonetik transliteratsiya qiling.
   - [[Rashiq al-Nasimi]] → [[Roshiq an-Nasimiy]] (arab ismlarini oʻzbek imlosiga moslashtiring)
   - [[Traditionalist theology (Islam)|Athari]] → [[Anʼanaviy ilohiyot (Islom)|asariy]] (qavs ichidagi disambiguation'ni ham tarjima qiling)

3) Strukturani saqlang: sarlavhalar, roʻyxatlar, {{...}} va boshqa wikitext sintaksisi buzilmasin.

4) Izoh yozmang. Faqat wikitext chiqaring.

5) Kirish jumlasi oʻzbekcha tuzilishda boʻlsin: '''Ism''' (maʼlumotlar; muqobil nomlar) — taʼrif.
   Qavsdan keyin em-dash (—) qoʻyiladi; inglizcha vergul uslubi emas.
   - Notoʻgʻri: '''Ismoil ibn Abdurahmon''' (1043-yilda vafot etgan), '''Ismoil az-Zafir''' nomi bilan ham tanilgan, Toledo taifasining birinchi hukmdori
   - Toʻgʻri: '''Ismoil ibn Abdurahmon''' (1043-yilda vafot etgan; '''Ismoil az-Zafir''' nomi bilan ham tanilgan) — Toledo taifasining birinchi hukmdori

6) Yil raqami "hijriy"/"milodiy" soʻzidan keyin va -yil qoʻshimchasi bilan yoziladi.
   - Notoʻgʻri: 132 hijriy/750 milodiy
   - Toʻgʻri: hijriy 132-yil/milodiy 750-yil
   Manbada boʻlmagan sanani oʻzingiz qoʻshmang: faqat "1301" yozilgan boʻlsa,
   hijriy muqobilini hisoblab qoʻshmang — "1301-yil" deb qoldiring.

7) Jumla ichidagi geografik nomlarda inglizcha "Shahar, Mamlakat" tartibi
   oʻzbekcha egalik qurilishiga aylanadi.
   - Notoʻgʻri: U Damashq, Suriyada yashagan
   - Toʻgʻri: U Suriyaning Damashq shahrida yashagan
   - Notoʻgʻri: Masjid al-Hindiyda, Najaf, Iroqda
   - Toʻgʻri: Iroqning Najaf shahridagi Masjid al-Hindiyda
   Bu qoida faqat matn ichidagi jumlalarga tegishli. Bilgiquti (infobox)
   parametrlari qiymatida "Shahar, Mamlakat" tartibi oʻz holicha qoladi.
{forced_links}
Matn:
```{text}```
"""

# Phase 2 uchun dinamik blok: uz.wiki'da maqolasi yoʻq havolalar roʻyxati.
# Matndagi [[Q12345|...]] placeholder'lari koʻp boʻlgani uchun model
# "target'ga tegilmaydi" degan naqshni oddiy havolalarga ham umumlashtiradi.
# Umumiy qoida buni yenga olmadi, shuning uchun ular nomma-nom sanab oʻtiladi.
FORCED_LINKS_TEMPLATE = """
8) MAJBURIY — quyidagi wikilink target'lari oʻzbek Vikipediyasida mavjud emas:
{titles}
   Ularning HAR BIRINI oʻzbekchaga tarjima yoki transliteratsiya qiling.
   Bu havolalarda target inglizcha qolishi MUMKIN EMAS — 1-qoidadagi
   "oʻzgartirmang" koʻrsatmasi faqat Q/CAT/TPL placeholder'lariga tegishli.
   Masalan: [[safe conduct]] → [[xavfsiz yoʻl]], [[Hawazin|Hawazinite]] → [[Havozin|havoziniy]]
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

# --- Review Prompt Settings (Phase 5) ---
# config.py ga "Translation Prompt Settings" blokidan KEYIN qo'shing

REVIEW_SYSTEM_PROMPT = """Siz oʻzbekcha Vikipediya muharririsiz.

Sizning vazifangiz — berilgan oʻzbekcha wikitext'ni quyidagi qoidalar asosida tekshirish va tuzatish.

QOIDALAR:
{rules}

---

MUHIM CHEKLOVLAR:
1) Faqat qoidalarda koʻrsatilgan xatolarni tuzating. Boshqa hech narsani oʻzgartirmang.
2) Wikitext tuzilishini ({{...}}, [[...]], <ref>...</ref> va boshqalar) buzmang.
3) Izoh yozmang. Faqat tuzatilgan wikitext chiqaring."""

REVIEW_USER_PROMPT = """MATN:
```
{text}
```
"""