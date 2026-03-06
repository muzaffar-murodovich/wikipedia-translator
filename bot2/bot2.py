#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
bot2.py — Sifat tekshiruvchi bot (Sohibjamol).

Vazifa:
  1-bot tarjimani tugatgach, database.py orqali xabar beradi.
  Bot2 avtomatik ravishda pending tarjimalarni tekshiradi,
  yaxshilangan versiyani saqlaydi va guruhga bayonot yuboradi.
"""

import os
import sys
import asyncio
import logging
import time
from pathlib import Path

# Loyiha root papkasini sys.path ga qo'shish
BOT2_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = BOT2_DIR.parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
from bot2.config2 import (
    TELEGRAM_TOKEN_BOT2,
    ALLOWED_USER_IDS,
    GROUP_CHAT_ID,
    BOT2_DIR as CFG_BOT2_DIR,
    PROJECT_DIR as CFG_PROJECT_DIR,
    POLLING_INTERVAL,
    AGENT_TIMEOUT_SEC,
    BOT2_SYSTEM_PROMPT,
    CHECKED_DIR,
)
from database import (
    init_db,
    save_message,
    get_history,
    clear_history,
    get_pending_translations,
    update_translation_status,
    save_quality_check,
    get_translation_stats,
)

# ── Muhit o'zgaruvchilari ─────────────────────────────────────────────────────

load_dotenv(PROJECT_DIR / ".env")

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot2")

# ── Global holat ─────────────────────────────────────────────────────────────

# Hozirda tekshirilayotgan tarjima IDlari (takrorlanmasligi uchun)
checking_ids: set[int] = set()

# Guruh suhbatlari uchun
active_tasks: dict[int, asyncio.Task] = {}
conversation_histories: dict[int, list[dict]] = {}


# ── Agent ishga tushirish ─────────────────────────────────────────────────────

async def run_quality_check_agent(
    translation_id: int,
    article_name: str,
    input_file: str,
    output_file: str,
) -> tuple[str, str | None]:
    """
    Tarjima sifatini tekshiruvchi agentni ishga tushiradi.

    Returns:
        (changes_summary, improved_file_path | None)
    """
    # Tekshirilgan fayllar uchun nom
    base_name = Path(output_file).stem
    checked_file = str(CHECKED_DIR / f"{base_name}_checked.txt")

    prompt = (
        f"Tarjima ID: {translation_id}\n"
        f"Maqola nomi: {article_name}\n"
        f"Asl inglizcha fayl: {input_file}\n"
        f"Tarjima fayli: {output_file}\n"
        f"Tekshirilgan fayl saqlash yo'li: {checked_file}\n\n"
        "Iltimos, tarjima faylini o'qing, sifatini tekshiring va yaxshilang. "
        "Yaxshilangan versiyani ko'rsatilgan yo'lga saqlang. "
        "Kiritilgan o'zgartirishlar haqida QISQA bayonot yozing."
    )

    text_parts: list[str] = []

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            system_prompt=BOT2_SYSTEM_PROMPT,
            cwd=str(PROJECT_DIR),
            max_turns=8,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    text_parts.append(block.text.strip())

    summary = "\n\n".join(text_parts).strip() or "O'zgartirishlar kiritildi."

    # Tekshirilgan fayl mavjudligini tekshirish
    improved_path = checked_file if Path(checked_file).exists() else None

    return summary, improved_path


# ── Tarjimalarni polling qilish ───────────────────────────────────────────────

async def check_pending_loop(application: Application):
    """
    Har POLLING_INTERVAL sekundda pending tarjimalarni tekshiradi.
    """
    bot: Bot = application.bot
    await asyncio.sleep(5)  # Ishga tushishdan 5 soniya kutish

    log.info(f"Polling loop boshlandi (har {POLLING_INTERVAL}s)")

    while True:
        try:
            pending = get_pending_translations()
            for tr in pending:
                tr_id = tr["id"]
                if tr_id in checking_ids:
                    continue  # Allaqachon tekshirilmoqda

                checking_ids.add(tr_id)
                asyncio.create_task(
                    process_translation(bot, tr)
                )

        except Exception as e:
            log.error(f"Polling xatosi: {e}", exc_info=True)

        await asyncio.sleep(POLLING_INTERVAL)


async def process_translation(bot: Bot, tr: dict):
    """Bitta tarjimani tekshirish va natijani guruhga yuborish."""
    tr_id = tr["id"]
    article_name = tr["article_name"]
    output_file = tr["output_file"]
    input_file = tr["input_file"]

    log.info(f"Tekshirilmoqda: {article_name} (ID={tr_id})")

    # Statusni yangilash
    update_translation_status(tr_id, "checking")

    # Guruhga xabar: boshladi
    try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"Sohibjamol: {article_name} maqolasini tekshirmoqda..."
        )
    except Exception as e:
        log.warning(f"Guruhga xabar yuborishda xato: {e}")

    try:
        summary, improved_file = await asyncio.wait_for(
            run_quality_check_agent(tr_id, article_name, input_file, output_file),
            timeout=AGENT_TIMEOUT_SEC,
        )

        # Natijani DBga saqlash
        save_quality_check(
            translation_id=tr_id,
            changes_summary=summary,
            improved_file=improved_file or "",
        )
        update_translation_status(tr_id, "checked")

        # Guruhga bayonot
        report = (
            f"Maqola: {article_name}\n"
            f"Holat: Tekshirildi\n\n"
            f"Kiritilgan o'zgartirishlar:\n{summary[:800]}"
        )
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=report)

        # Yaxshilangan faylni guruhga yuborish
        if improved_file and Path(improved_file).exists():
            with open(improved_file, "rb") as f:
                await bot.send_document(
                    chat_id=GROUP_CHAT_ID,
                    document=f,
                    filename=Path(improved_file).name,
                    caption=f"{article_name} — yaxshilangan tarjima",
                )

    except asyncio.TimeoutError:
        update_translation_status(tr_id, "timeout")
        try:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"{article_name} tekshiruvi vaqt tugashi bilan to'xtatildi."
            )
        except Exception:
            pass

    except Exception as e:
        log.error(f"process_translation xatosi [{article_name}]: {e}", exc_info=True)
        update_translation_status(tr_id, "error")
        try:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"{article_name} tekshirishda xato: {str(e)[:200]}"
            )
        except Exception:
            pass

    finally:
        checking_ids.discard(tr_id)


# ── Telegram buyruqlar ────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "Sohibjamol — Sifat tekshiruvchi bot\n\n"
        "Vazifam: tarjima qilingan maqolalarni avtomatik tekshirish.\n\n"
        "Buyruqlar:\n"
        "/stats — so'nggi tarjimalar holati\n"
        "/check_now — pending tarjimalarni hoziroq tekshirish"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    stats = get_translation_stats(limit=10)
    if not stats:
        await update.message.reply_text("Hozircha tarjima yozuvlari yo'q.")
        return

    lines = ["So'nggi 10 ta tarjima:\n"]
    for s in stats:
        status_emoji = {
            "pending_check": "⏳",
            "checking": "🔄",
            "checked": "✅",
            "error": "❌",
            "timeout": "⏱",
        }.get(s.get("status", ""), "❓")
        lines.append(
            f"{status_emoji} {s['article_name']} — {s['status']}\n"
            f"   {s['translated_at'][:16] if s['translated_at'] else ''}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    pending = get_pending_translations()
    if not pending:
        await update.message.reply_text("Tekshirish kerak bo'lgan tarjima yo'q.")
        return

    await update.message.reply_text(f"{len(pending)} ta tarjima tekshirilmoqda...")

    bot = context.bot
    for tr in pending:
        if tr["id"] not in checking_ids:
            checking_ids.add(tr["id"])
            asyncio.create_task(process_translation(bot, tr))


# ── Guruh xabarlarini qayta ishlash ──────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guruh va shaxsiy chatdagi barcha matn xabarlarini qayta ishlash."""
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    if user_id in active_tasks and not active_tasks[user_id].done():
        await update.message.reply_text("Avvalgi vazifa hali tugalamagan.")
        return

    msg = await update.message.reply_text("Sohibjamol fikr yuritmoqda...")
    log.info(f"Guruh xabari [{user_id}]: {user_text[:100]}")

    async def agent_task():
        try:
            # SQLite dan tarix yuklash (bot qayta ishga tushsa ham saqlanadi)
            history = get_history(user_id, bot_id=2, limit=10)

            if history:
                lines = []
                for m in history:
                    role = "Foydalanuvchi" if m["role"] == "user" else "Siz"
                    lines.append(f"{role}: {m['content']}")
                prompt = "Oldingi suhbat:\n" + "\n".join(lines) + "\n\nJoriy xabar: " + user_text
            else:
                prompt = user_text

            text_parts: list[str] = []

            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    system_prompt=BOT2_SYSTEM_PROMPT,
                    cwd=str(PROJECT_DIR),
                    max_turns=5,
                    allowed_tools=["Read", "Bash", "Glob"],
                    permission_mode="acceptEdits",
                ),
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock) and block.text.strip():
                            text_parts.append(block.text.strip())

            response = "\n\n".join(text_parts).strip() or "Tayyor."

            # Xabarlarni SQLite ga saqlash (internet/elektr uzilsa ham yo'qolmaydi)
            save_message(user_id, "user", user_text, bot_id=2)
            save_message(user_id, "assistant", response, bot_id=2)

            if len(response) > 4000:
                await msg.edit_text(response[:4000] + "\n\n(davomi quyida)")
                for i in range(4000, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000])
            else:
                await msg.edit_text(response)

        except Exception as e:
            log.error(f"handle_message xatosi: {e}", exc_info=True)
            try:
                await msg.edit_text(f"Xato: {str(e)[:200]}")
            except Exception:
                pass
        finally:
            active_tasks.pop(user_id, None)

    task = asyncio.create_task(agent_task())
    active_tasks[user_id] = task


# ── Ishga tushirish ───────────────────────────────────────────────────────────

async def post_init(application: Application):
    """Bot ishga tushgandan so'ng polling loopni boshlash."""
    asyncio.create_task(check_pending_loop(application))


def main():
    # DB jadvallarini yaratish
    init_db()

    # PID saqlash
    pid_file = PROJECT_DIR / "bot2.pid"
    pid_file.write_text(str(os.getpid()))

    token = os.environ.get("TELEGRAM_TOKEN_BOT2", TELEGRAM_TOKEN_BOT2)
    if not token:
        log.error("TELEGRAM_TOKEN_BOT2 topilmadi. .env faylini tekshiring.")
        sys.exit(1)

    log.info(f"Bot2 (Sohibjamol) ishga tushmoqda | PID: {os.getpid()}")
    log.info(f"Guruh: {GROUP_CHAT_ID} | Polling: {POLLING_INTERVAL}s")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("check_now", cmd_check_now))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
