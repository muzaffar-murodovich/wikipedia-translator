#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
agent_bot.py — Claude Agent SDK bilan ishlaydigan Wiki Translator Bot

Xavfsizlik mexanizmlari:
  • 5 daqiqa timeout — agent loop'ga tushib qolsa majburan to'xtatiladi
  • /cancel buyrug'i — istalgan vaqtda bekor qilish
  • max_turns=10 — cheksiz aylanib qolmasligi uchun
  • Progress xabarlari — har 60 sekundda nima qilayotganini ko'rsatadi
"""

import os
import asyncio
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

# ── Sozlamalar ────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = "5800257941:AAHvixqllrdWAuavbQNpwgalzQrI9wkF5vs"
PROJECT_DIR = Path(__file__).parent.resolve()
ALLOWED_USER_IDS: list[int] = [694727943]

AGENT_TIMEOUT_SEC = 5 * 60   # 5 daqiqa
PROGRESS_INTERVAL = 60        # Har 60 sekundda progress xabari

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# Faol agentlarni kuzatish: {user_id: asyncio.Task}
active_tasks: dict[int, asyncio.Task] = {}



# ── Agent system prompt ───────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = f"""Sen Wikipedia tarjima loyihasida ishlaydigan aqlli agentsan.
Loyiha papkasi: {PROJECT_DIR}

## Loyiha haqida
Bu loyiha inglizcha Vikipediya maqolalarini o'zbekchaga tarjima qiladi.

Asosiy fayl: `main.py`
Chaqirish usuli (AYNAN SHUNDAY, boshqacha emas):
  cd {PROJECT_DIR} && python main.py {PROJECT_DIR}/temp_wiki/input_en.txt {PROJECT_DIR}/temp_wiki/MAQOLA_NOMI.txt
  (MAQOLA_NOMI = maqolaning inglizcha nomi, masalan Avicenna.txt)

## Fayl yo'llari — DOIM TO'LIQ YO'L ISHLAT
- Kirish fayli:  {PROJECT_DIR}/temp_wiki/input_en.txt
- Chiqish fayli: {PROJECT_DIR}/temp_wiki/MAQOLA_NOMI.txt
  (MAQOLA_NOMI = Wikipedia maqolasining inglizcha nomi, masalan: Avicenna.txt, Rumi.txt)
- Faylni yozish uchun Python ishlat, echo yoki shell redirect EMAS:
    python3 -c "open('{PROJECT_DIR}/temp_wiki/input_en.txt','w').write(wikitext)"

## Sen nima qila olasan
1. Wikipedia API orqali maqola wikitext'ini olish (requests)
2. Wikitext'ni kerak bo'lsa o'zgartirish (bo'lim olib tashlash va h.k.)
3. input_en.txt ga yozish, keyin main.py chaqirish
4. output_uz.txt ni foydalanuvchiga yuborish
5. Kategoriya statistikasi hisoblash

## Muhim qoidalar — ALBATTA RIOYA QILING
- HECH QACHON nisbiy yo'l ishlatma — faqat to'liq yo'l ({PROJECT_DIR}/...)
- Xato bo'lsa — DARHOL to'xtab, xabar ber, qayta urinma
- Natijalarni O'ZBEK TILIDA yoz
- Bir vazifani bajargach, yangi vazifa olma

## Javob formati
- Qisqa va aniq, oddiy matn (Markdown belgisi ishlatma: **, __, ``` va h.k.)
- Statistikani oddiy jadval yoki ro'yxat sifatida yoz

## Fayl yuborish qoidasi — MUHIM
- Faqat tarjima vazifasi bajarilganda output faylni yarating
- Savol, statistika, ma'lumot so'rovlarida HECH QANDAY FAYL yaratma
- Agar foydalanuvchi shunchaki savol bersa — faqat matnli javob ber
"""


# ── Agent ishga tushirish ─────────────────────────────────────────────────────

async def run_agent(user_message: str, on_turn=None, send_files: bool = True) -> tuple[str, list[Path]]:
    """Timeout va turn callback bilan agent'ni ishga tushirish."""
    import time
    start_time = time.time()   # agent boshlanish vaqti
    text_parts: list[str] = []
    turn_count = 0

    async for message in query(
        prompt=user_message,
        options=ClaudeAgentOptions(
            system_prompt=AGENT_SYSTEM_PROMPT,
            cwd=str(PROJECT_DIR),
            max_turns=10,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "LS"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, AssistantMessage):
            turn_count += 1
            if on_turn:
                await on_turn(turn_count)
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    text_parts.append(block.text.strip())

    # Faqat agent ishga tushgandan KEYIN yaratilgan fayllarni qaytarish
    output_files: list[Path] = []
    if send_files:
        temp_dir = PROJECT_DIR / "temp_wiki"
        if temp_dir.exists():
            for f in temp_dir.iterdir():
                if (f.suffix in (".txt", ".wiki")
                        and f.stat().st_size > 0
                        and f.name != "input_en.txt"
                        and not f.name.startswith("fetch_")
                        and f.stat().st_mtime >= start_time):   # faqat yangi fayllar
                    output_files.append(f)

    response_text = "\n\n".join(text_parts) if text_parts else "✅ Vazifa bajarildi."
    return response_text, output_files


# ── Telegram handler'lar ──────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "👋 *Wiki Agent Bot*\n\n"
        "Vazifangizni oddiy til bilan yozing. Agent o'zi kod yozib bajaradi.\n\n"
        "📌 *Misollar:*\n"
        "• `Avicenna maqolasini tarjima qil`\n"
        "• `https://en.wikipedia.org/wiki/Category:X turkumida nechta o'zbekcha maqola bor?`\n"
        "• `Rumi maqolasini tarjima qil, == Notes == bo'limisiz`\n\n"
        "⏱ Maksimum vaqt: *5 daqiqa*\n"
        "🛑 To'xtatish: /cancel",
        parse_mode="Markdown",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faol agentni bekor qilish."""
    user_id = update.effective_user.id
    task = active_tasks.get(user_id)

    if task and not task.done():
        task.cancel()
        active_tasks.pop(user_id, None)
        await update.message.reply_text("🛑 Agent to'xtatildi.")
        log.info(f"User {user_id} agentni bekor qildi.")
    else:
        await update.message.reply_text("Hozirda faol agent yo'q.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarni agent orqali qayta ishlash — timeout va cancel bilan."""
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    # Agar avvalgi agent hali ishlayotgan bo'lsa
    if user_id in active_tasks and not active_tasks[user_id].done():
        await update.message.reply_text(
            "⚠️ Avvalgi vazifa hali tugalamagan.\n"
            "To'xtatish uchun: /cancel"
        )
        return

    msg = await update.message.reply_text("🤔 Agent vazifani tahlil qilmoqda...")
    log.info(f"Agent so'rovi [{user_id}]: {user_text[:100]}")

    elapsed = 0

    async def on_turn(turn_num: int):
        nonlocal elapsed
        elapsed_min = elapsed // 60
        elapsed_sec = elapsed % 60
        try:
            await msg.edit_text(
                f"⚙️ Agent ishlayapti... (qadam {turn_num}/10)\n"
                f"⏱ Ketgan vaqt: {elapsed_min}:{elapsed_sec:02d}\n\n"
                f"_To'xtatish: /cancel_",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    async def progress_ticker():
        nonlocal elapsed
        while True:
            await asyncio.sleep(60)
            elapsed += 60
            try:
                elapsed_min = elapsed // 60
                await msg.edit_text(
                    f"⚙️ Agent ishlayapti... ({elapsed_min} daqiqa o'tdi)\n"
                    f"_To'xtatish: /cancel_",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    async def agent_task():
        ticker = asyncio.create_task(progress_ticker())
        try:
            response_text, output_files = await asyncio.wait_for(
                run_agent(user_text, on_turn=on_turn, send_files=True),
                timeout=AGENT_TIMEOUT_SEC,
            )

            # Javobni yuborish — parse_mode yo'q (Markdown belgilari xom matn sifatida)
            if len(response_text) > 4000:
                await msg.edit_text(response_text[:4000] + "\n\n(davomi quyida)")
                for i in range(4000, len(response_text), 4000):
                    await update.message.reply_text(response_text[i:i+4000])
            else:
                await msg.edit_text(response_text)

            # Faqat tarjima so'rovida fayllarni yuborish
            for file_path in output_files:
                try:
                    with open(file_path, "rb") as f:
                        await update.message.reply_document(
                            document=f,
                            filename=file_path.name,
                            caption=f"📄 {file_path.name}",
                        )
                except Exception as e:
                    log.warning(f"Fayl yuborishda xato: {e}")

        except asyncio.TimeoutError:
            log.warning(f"Agent timeout [{user_id}]")
            await msg.edit_text(
                f"⏰ *Timeout!* Agent {AGENT_TIMEOUT_SEC//60} daqiqada bajara olmadi.\n\n"
                "Sabab bo'lishi mumkin:\n"
                "• Maqola juda katta\n"
                "• `main.py` uzoq ishlayapti\n"
                "• Wikipedia sekin javob bermoqda\n\n"
                "Bo'limlarni cheklash yoki kichikroq maqola bilan qayta urining.",
                parse_mode="Markdown",
            )
        except asyncio.CancelledError:
            await msg.edit_text("🛑 Vazifa bekor qilindi.")
        except Exception as e:
            log.error(f"Agent xatosi [{user_id}]: {e}", exc_info=True)
            await msg.edit_text(
                f"❌ Xato:\n`{str(e)[:300]}`",
                parse_mode="Markdown",
            )
        finally:
            ticker.cancel()
            active_tasks.pop(user_id, None)

    task = asyncio.create_task(agent_task())
    active_tasks[user_id] = task


# ── Asosiy funksiya ───────────────────────────────────────────────────────────

def main():
    (PROJECT_DIR / "temp_wiki").mkdir(exist_ok=True)

    print("🚀 Wiki Agent Bot ishga tushmoqda...")
    print(f"   Loyiha papkasi: {PROJECT_DIR}")
    print(f"   Timeout: {AGENT_TIMEOUT_SEC//60} daqiqa | Max turns: 10")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot tayyor! /cancel bilan istalgan vaqt to'xtatish mumkin.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()