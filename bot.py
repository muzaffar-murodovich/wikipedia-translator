#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
agent_bot.py — Claude Agent SDK bilan ishlaydigan Wiki Translator Bot
"""

import os
import asyncio
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
from config import AGENT_SYSTEM_PROMPT, PROJECT_DIR
from database import init_db, save_message, get_history, clear_history

# ── Sozlamalar ────────────────────────────────────────────────────────────────

# .env faylidan muhit o'zgaruvchilarini yuklash
load_dotenv(Path(__file__).parent / ".env")

# Faqat shu foydalanuvchiga javob beradi
TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS: list[int] = [
    int(uid.strip())
    for uid in os.environ["ALLOWED_USER_IDS"].split(",")
    if uid.strip()
]


AGENT_TIMEOUT_SEC = 10 * 60

# Bot to'xtatish uchun sentinel fayl (restart buyrug'i yaratadi)
from config import PROJECT_DIR as _PROJECT_DIR
STOP_FILE = _PROJECT_DIR / "stop.flag"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

active_tasks: dict[tuple[int, int], asyncio.Task] = {}



# ── Agent ishga tushirish ─────────────────────────────────────────────────────

async def run_agent(user_message: str, history: list[dict] | None = None) -> tuple[str, list[Path]]:
    """Agent'ni ishga tushirish va SEND_FILE yo'llarini javobdan ajratib olish."""
    text_parts: list[str] = []

    if history:
        lines = []
        for m in history[-20:]:
            role = "Foydalanuvchi" if m["role"] == "user" else "Siz"
            lines.append(f"{role}: {m['content']}")
        prompt = "Oldingi suhbat:\n" + "\n".join(lines) + "\n\nJoriy xabar: " + user_message
    else:
        prompt = user_message

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            system_prompt=AGENT_SYSTEM_PROMPT,
            cwd=str(PROJECT_DIR),
            max_turns=10,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "LS"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    text_parts.append(block.text.strip())

    # Javobdan SEND_FILE qatorlarini ajratib, fayl yo'llarini to'plash
    full_text = "\n\n".join(text_parts)
    output_files: list[Path] = []
    clean_lines: list[str] = []

    for line in full_text.splitlines():
        if line.startswith("SEND_FILE:"):
            file_path = Path(line[len("SEND_FILE:"):].strip())
            if file_path.exists() and file_path.is_file():
                output_files.append(file_path)
        else:
            clean_lines.append(line)

    # SEND_FILE qatorlari olib tashlangan toza matn
    response_text = "\n".join(clean_lines).strip() or "✅ Vazifa bajarildi."
    return response_text, output_files


# ── Telegram handler'lar ──────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_allowed(user_id):
        return

    task_key = (user_id, chat_id)
    if task_key in active_tasks and not active_tasks[task_key].done():
        await update.message.reply_text("Avvalgi vazifa hali tugalamagan. Bekor qilish: /cancel")
        return

    msg = await update.message.reply_text("...")

    async def agent_task():
        try:
            history = get_history(user_id, bot_id=1, limit=20)
            response_text, output_files = await asyncio.wait_for(
                run_agent("Salom! Foydalanuvchi /start buyrug'ini bosdi. Qisqacha o'zingni tanishtir va nima qila olishingni ayt.", history=history),
                timeout=AGENT_TIMEOUT_SEC,
            )
            await msg.edit_text(response_text)
        except Exception as e:
            await msg.edit_text(
                "Salom! Men Wikipedia tarjima botiman.\n\n"
                "Quyidagilarni so'rashingiz mumkin:\n"
                "- Avicenna maqolasini tarjima qil\n"
                "- Fayl yuborgin\n"
                "- Kod o'zgartir\n\n"
                "Yangi suhbat: /upd\n"
                "Bekor qilish: /cancel"
            )
        finally:
            active_tasks.pop(task_key, None)

    task = asyncio.create_task(agent_task())
    active_tasks[task_key] = task


async def cmd_upd(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    await update.message.reply_text("Yangi suhbat boshlandi.")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_allowed(user_id):
        return
    task_key = (user_id, chat_id)
    task = active_tasks.get(task_key)
    if task and not task.done():
        task.cancel()
        active_tasks.pop(task_key, None)
        await update.message.reply_text("Agent to'xtatildi.")
    else:
        await update.message.reply_text("Hozirda faol agent yo'q.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_allowed(user_id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    task_key = (user_id, chat_id)
    if task_key in active_tasks and not active_tasks[task_key].done():
        await update.message.reply_text("Avvalgi vazifa hali tugalamagan. Bekor qilish: /cancel")
        return

    msg = await update.message.reply_text("...")
    log.info(f"So'rov [{user_id}]: {user_text[:100]}")

    async def agent_task():
        try:
            # SQLite dan tarix yuklash (bot qayta ishga tushsa ham saqlanadi)
            history = get_history(user_id, bot_id=1, limit=20)
            response_text, output_files = await asyncio.wait_for(
                run_agent(user_text, history=history),
                timeout=AGENT_TIMEOUT_SEC,
            )

            # Xabarlarni SQLite ga saqlash
            save_message(user_id, "user", user_text, bot_id=1)
            save_message(user_id, "assistant", response_text, bot_id=1)

            # Matnli javob
            if len(response_text) > 4000:
                await msg.edit_text(response_text[:4000] + "\n\n(davomi quyida)")
                for i in range(4000, len(response_text), 4000):
                    await update.message.reply_text(response_text[i:i+4000])
            else:
                await msg.edit_text(response_text)

            # Fayllarni yuborish
            for file_path in output_files:
                try:
                    with open(file_path, "rb") as f:
                        await update.message.reply_document(
                            document=f,
                            filename=file_path.name,
                            caption=f"📄 {file_path.name}",
                        )
                except Exception as e:
                    log.warning(f"Fayl yuborishda xato ({file_path.name}): {e}")

        except asyncio.TimeoutError:
            await msg.edit_text(
                f"Timeout! Agent {AGENT_TIMEOUT_SEC//60} daqiqada bajara olmadi.\n"
                "Kichikroq vazifa bilan qayta urining."
            )
        except asyncio.CancelledError:
            await msg.edit_text("Vazifa bekor qilindi.")
        except Exception as e:
            log.error(f"Agent xatosi [{user_id}]: {e}", exc_info=True)
            await msg.edit_text(f"Xato: {str(e)[:300]}")
        finally:
            active_tasks.pop(task_key, None)

    task = asyncio.create_task(agent_task())
    active_tasks[task_key] = task


# ── Global xato ushlagich ─────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """NetworkError va TimedOut xatolarini jimgina qayd etadi, botni to'xtatmaydi."""
    if isinstance(context.error, (NetworkError, TimedOut)):
        log.warning(f"Tarmoq xatosi (davom etiladi): {context.error}")
        return
    log.error(f"Kutilmagan xato: {context.error}", exc_info=context.error)


# ── Asosiy funksiya ───────────────────────────────────────────────────────────

def build_app():
    """Yangi Application obyekti yaratish (retry tsiklida qayta ishlatish uchun)."""
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("upd", cmd_upd))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    return app


def main():
    (PROJECT_DIR / "temp_wiki").mkdir(exist_ok=True)

    my_pid = os.getpid()

    # Ishga tushishda eski stop.flag ni o'chirish (avvalgi restart qoldig'i)
    if STOP_FILE.exists():
        try:
            old_content = STOP_FILE.read_text().strip()
            STOP_FILE.unlink()
            log.warning(f"Ishga tushishda eski stop.flag o'chirildi (mazmun: '{old_content}')")
        except Exception:
            pass

    # SQLite jadvallarini yaratish
    init_db()

    # Joriy PID ni faylga saqlash (restart uchun kerak)
    pid_file = PROJECT_DIR / "bot.pid"
    pid_file.write_text(str(my_pid))

    log.info(f"Bot ishga tushmoqda | Papka: {PROJECT_DIR} | Ruxsat: {ALLOWED_USER_IDS} | PID: {my_pid}")

    retry_delay = 5
    while True:
        try:
            # Har urinishda yangi event loop yaratish (eski yopilgan loop muammosini hal qilish)
            # run_polling() ichki event loopni yopadi, keyingi urinishda yopilgan loop ishlatilmasin
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Har urinishda yangi Application yaratiladi (eski holat muammosini oldini olish)
            app = build_app()
            app.run_polling(drop_pending_updates=True)

            # run_polling normalda qaytdi — bu SIGTERM/SIGINT yoki Application.stop() demak.
            # Har qanday holatda to'xtatiladi. Faqat XATOLAR qayta uriniladi.
            log.info("run_polling to'xtadi (SIGTERM/SIGINT) — bot yakunlandi.")
            break

        except (KeyboardInterrupt, SystemExit):
            log.info("Bot to'xtatildi (KeyboardInterrupt/SystemExit).")
            break
        except RuntimeError as e:
            # "Event loop is closed" — run_polling SIGTERM sababi bilan to'xtadi
            # Bu xato retry ga emas, chiqishga ishora qiladi
            if "event loop" in str(e).lower():
                log.info(f"Event loop yopildi (to'xtash signali qabul qilindi) — bot yakunlandi: {e}")
                break
            log.warning(f"RuntimeError, {retry_delay}s keyin qayta uriniladi: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        except (NetworkError, TimedOut) as e:
            log.warning(f"Tarmoq xatosi, {retry_delay}s keyin qayta uriniladi: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        except Exception as e:
            log.warning(f"Xato ({type(e).__name__}), {retry_delay}s keyin qayta uriniladi: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)


if __name__ == "__main__":
    main()