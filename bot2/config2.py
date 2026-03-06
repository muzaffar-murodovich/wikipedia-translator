#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config2.py - 2-bot (sifat tekshiruvchi) uchun konfiguratsiya.

To'ldirish kerak bo'lgan joylar:
  TELEGRAM_TOKEN_BOT2 - @BotFather orqali yangi bot yaratib oling
  GROUP_CHAT_ID       - Guruh yaratilgach to'ldiring
  BOT2_SYSTEM_PROMPT  - Custom instruction keyinroq to'ldiriladi
"""

import os
from pathlib import Path

# ============================================================
# Telegram Sozlamalari
# ============================================================

# @BotFather -> /newbot -> tokenni shu yerga yoki .env ga yozing
TELEGRAM_TOKEN_BOT2 = os.getenv("TELEGRAM_TOKEN_BOT2", "")

# Ruxsat berilgan foydalanuvchilar (1-bot bilan bir xil)
ALLOWED_USER_IDS = [694727943]

# Telegram guruh chat ID (guruh yaratilgach to'ldiring)
# Topish: guruhga @userinfobot qo'shing, /start yuboring
# Masalan: GROUP_CHAT_ID = "-1001234567890"
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", None)

# ============================================================
# AI Sozlamalari (1-bot bilan bir xil .env dan o'qiladi)
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-3-5")

# ============================================================
# Papkalar
# ============================================================

# Loyiha root papkasi (bot2/ ning parent)
PROJECT_DIR = Path(__file__).parent.parent.resolve()

# bot2/ papkasi
BOT2_DIR = Path(__file__).parent.resolve()

# Tekshirilgan tarjimalar saqlanadigan papka
CHECKED_DIR = PROJECT_DIR / "temp_wiki" / "checked"
CHECKED_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Vaqt Sozlamalari
# ============================================================

# Har necha sekundda pending tarjimalarni tekshirish
POLLING_INTERVAL = 30   # soniya

# Agent maksimal ishlash vaqti
AGENT_TIMEOUT_SEC = 600  # 10 daqiqa

# ============================================================
# Bot2 System Prompt (Custom Instruction)
# ============================================================
# Bu yerga sifat tekshiruv bo'yicha ko'rsatmalar yoziladi.
# Hozircha asosiy qoidalar mavjud. Keyinroq to'ldiriladi.

BOT2_SYSTEM_PROMPT = f"""Siz o'zbek tili va Vikipediya mutaxassisisiz.

Sizning yagona vazifangiz: ingliz tilidan o'zbek tiliga tarjima qilingan
Vikipediya maqolalarining sifatini tekshirish va yaxshilash.

Loyiha papkasi: {PROJECT_DIR}
Tekshirilgan fayllar papkasi: {CHECKED_DIR}

[CUSTOM INSTRUCTION — Keyinroq to'ldiriladi]

Umumiy qoidalar:
1. Berilgan tarjima faylini to'liq o'qing
2. Quyidagi jihatlarni tekshiring:
   - Grammatika va imlo xatolari
   - Terminologiya (ilmiy va texnik atamalar)
   - O'zbek Vikipediya uslubi
   - Wikitext formati ([[havolalar]], andozalar, <ref>izohlar</ref>)
3. Zarur o'zgartirishlarni kiriting
4. Yaxshilangan tarjimani yangi faylga saqlang
5. Kiritilgan o'zgartirishlar haqida QISQA bayonot yozing

Bayonot formati (faqat shu matnni qaytaring):
Kiritilgan o'zgartirishlar: [nima o'zgardi — qisqacha]

Muhim qoidalar:
- Faqat to'liq yo'llar ishlating ({PROJECT_DIR}/...)
- Wikitext tuzilmasini (havolalar, andozalar) buzmang
- Bayonot o'ZBEK tilida bo'lsin
- Qisqa va aniq yozing
"""
