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

TELEGRAM_TOKEN = "5800257941:AAHvixqllrdWAuavbQNpwgalzQrI9wkF5vs" #revoked
PROJECT_DIR = Path(__file__).parent.resolve()

# Faqat shu foydalanuvchiga javob beradi
ALLOWED_USER_IDS: list[int] = [694727943]

AGENT_TIMEOUT_SEC = 5 * 60

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

active_tasks: dict[int, asyncio.Task] = {}
conversation_histories: dict[int, list[dict]] = {}


# ── Agent system prompt ───────────────────────────────────────────────────────

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

Note: Raw wikitext preserves [[links]], {{templates}}, <ref>references</ref>, and other codes. These codes are correctly processed by main.py.

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
6. Restart: pkill -f bot.py && nohup python {PROJECT_DIR}/bot.py >> {PROJECT_DIR}/bot.log 2>&1 &
7. Notify the user: "O'zgartirish kiritildi va bot qayta ishga tushirildi" (Changes applied and bot restarted)

## Important Rules
- NEVER use relative paths — only full paths ({PROJECT_DIR}/...)
- If an error occurs — stop IMMEDIATELY and report it, do not retry
- On Telegram:
  1. Write results in UZBEK LANGUAGE
  2. Write in plain text — do not use Markdown formatting (**, __, ``` etc.)
  3. After completing one task, do not take on a new task automatically
"""


# ── Agent ishga tushirish ─────────────────────────────────────────────────────

async def run_agent(user_message: str, history: list[dict] | None = None, on_turn=None) -> tuple[str, list[Path]]:
    """Agent'ni ishga tushirish va SEND_FILE yo'llarini javobdan ajratib olish."""
    start_time = time.time()
    text_parts: list[str] = []
    turn_count = 0

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
            turn_count += 1
            if on_turn:
                await on_turn(turn_count)
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
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "Wiki Agent Bot\n\n"
        "Vazifangizni oddiy til bilan yozing.\n\n"
        "Misollar:\n"
        "- Avicenna maqolasini tarjima qil\n"
        "- core/quality_checker.py faylini yuborgin\n"
        "- config.py faylini ko'rsat\n"
        "- Botga yangi /help buyrug'i qo'sh\n\n"
        "Maksimum vaqt: 5 daqiqa\n"
        "Yangi suhbat: /upd\n"
        "Bekor qilish: /cancel"
    )


async def cmd_upd(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    conversation_histories.pop(user_id, None)
    await update.message.reply_text("Yangi suhbat boshlandi.")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    task = active_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
        active_tasks.pop(user_id, None)
        await update.message.reply_text("Agent to'xtatildi.")
    else:
        await update.message.reply_text("Hozirda faol agent yo'q.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    if user_id in active_tasks and not active_tasks[user_id].done():
        await update.message.reply_text("Avvalgi vazifa hali tugalamagan. Bekor qilish: /cancel")
        return

    msg = await update.message.reply_text("Agent vazifani tahlil qilmoqda...")
    log.info(f"So'rov [{user_id}]: {user_text[:100]}")

    elapsed = 0

    async def on_turn(turn_num: int):
        nonlocal elapsed
        try:
            await msg.edit_text(
                f"Agent ishlayapti... (qadam {turn_num}/10)\n"
                f"Ketgan vaqt: {elapsed//60}:{elapsed%60:02d}\n"
                f"Bekor qilish: /cancel"
            )
        except Exception:
            pass

    async def progress_ticker():
        nonlocal elapsed
        while True:
            await asyncio.sleep(60)
            elapsed += 60
            try:
                await msg.edit_text(
                    f"Agent ishlayapti... ({elapsed//60} daqiqa)\n"
                    f"Bekor qilish: /cancel"
                )
            except Exception:
                pass

    async def agent_task():
        ticker = asyncio.create_task(progress_ticker())
        try:
            history = conversation_histories.get(user_id, [])
            response_text, output_files = await asyncio.wait_for(
                run_agent(user_text, history=history, on_turn=on_turn),
                timeout=AGENT_TIMEOUT_SEC,
            )

            # Tarixni yangilash
            hist = conversation_histories.setdefault(user_id, [])
            hist.append({"role": "user", "content": user_text})
            hist.append({"role": "assistant", "content": response_text})

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
            ticker.cancel()
            active_tasks.pop(user_id, None)

    task = asyncio.create_task(agent_task())
    active_tasks[user_id] = task


# ── Asosiy funksiya ───────────────────────────────────────────────────────────

def main():
    (PROJECT_DIR / "temp_wiki").mkdir(exist_ok=True)
    log.info(f"Bot ishga tushmoqda | Papka: {PROJECT_DIR} | Ruxsat: {ALLOWED_USER_IDS}")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("upd", cmd_upd))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()