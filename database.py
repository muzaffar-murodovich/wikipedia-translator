#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
database.py - Ikkala bot uchun umumiy SQLite boshqaruvchi.

Jadvallar:
  messages       - Suhbat tarixi (internet/elektr uzilsa ham saqlanadi)
  translations   - Tarjima yozuvlari
  quality_checks - 2-bot sifat tekshiruv natijalari
"""

import sqlite3
import logging
from pathlib import Path

DB_PATH = Path(__file__).parent / "shared.db"
log = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    """SQLite ulanish qaytaradi."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Barcha jadvallarni yaratish (agar mavjud bo'lmasa)."""
    with get_conn() as conn:
        conn.executescript("""
            -- Suhbat tarixi (bot_id=1 asosiy bot, bot_id=2 sifat tekshiruvchi)
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER  PRIMARY KEY AUTOINCREMENT,
                bot_id    INTEGER  NOT NULL DEFAULT 1,
                user_id   INTEGER  NOT NULL,
                role      TEXT     NOT NULL,
                content   TEXT     NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Tarjima yozuvlari
            CREATE TABLE IF NOT EXISTS translations (
                id            INTEGER  PRIMARY KEY AUTOINCREMENT,
                article_name  TEXT     NOT NULL,
                input_file    TEXT     NOT NULL,
                output_file   TEXT     NOT NULL,
                user_id       INTEGER  NOT NULL,
                status        TEXT     DEFAULT 'pending_check',
                translated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Sifat tekshiruv natijalari
            CREATE TABLE IF NOT EXISTS quality_checks (
                id             INTEGER  PRIMARY KEY AUTOINCREMENT,
                translation_id INTEGER  NOT NULL,
                changes_summary TEXT,
                improved_file  TEXT,
                checked_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (translation_id) REFERENCES translations(id)
            );
        """)
    log.info(f"SQLite DB tayyor: {DB_PATH}")


# ── Suhbat tarixi ─────────────────────────────────────────────────────────────

def save_message(user_id: int, role: str, content: str, bot_id: int = 1):
    """Bitta xabarni saqla."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (bot_id, user_id, role, content) VALUES (?, ?, ?, ?)",
                (bot_id, user_id, role, content),
            )
    except Exception as e:
        log.error(f"save_message xatosi: {e}")


def get_history(user_id: int, bot_id: int = 1, limit: int = 20) -> list[dict]:
    """So'nggi `limit` ta xabarni ro'yxat sifatida qaytaradi (eski → yangi)."""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE user_id=? AND bot_id=? "
                "ORDER BY timestamp DESC LIMIT ?",
                (user_id, bot_id, limit),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        log.error(f"get_history xatosi: {e}")
        return []


def clear_history(user_id: int, bot_id: int = 1):
    """Foydalanuvchi suhbat tarixini o'chirish (/upd)."""
    try:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM messages WHERE user_id=? AND bot_id=?",
                (user_id, bot_id),
            )
    except Exception as e:
        log.error(f"clear_history xatosi: {e}")


# ── Tarjima yozuvlari ─────────────────────────────────────────────────────────

def save_translation(
    article_name: str, input_file: str, output_file: str, user_id: int
) -> int:
    """Yangi tarjima yozuvini saqla. Yaratilgan ID ni qaytaradi."""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO translations (article_name, input_file, output_file, user_id) "
                "VALUES (?, ?, ?, ?)",
                (article_name, input_file, output_file, user_id),
            )
            return cur.lastrowid
    except Exception as e:
        log.error(f"save_translation xatosi: {e}")
        return -1


def get_pending_translations() -> list[dict]:
    """status='pending_check' bo'lgan tarjimalarni qaytaradi."""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM translations WHERE status='pending_check' "
                "ORDER BY translated_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"get_pending_translations xatosi: {e}")
        return []


def update_translation_status(translation_id: int, status: str):
    """Tarjima statusini yangilashtirish."""
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE translations SET status=? WHERE id=?",
                (status, translation_id),
            )
    except Exception as e:
        log.error(f"update_translation_status xatosi: {e}")


# ── Sifat tekshiruv ───────────────────────────────────────────────────────────

def save_quality_check(translation_id: int, changes_summary: str, improved_file: str):
    """Sifat tekshiruv natijasini saqlash."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO quality_checks (translation_id, changes_summary, improved_file) "
                "VALUES (?, ?, ?)",
                (translation_id, changes_summary, improved_file),
            )
    except Exception as e:
        log.error(f"save_quality_check xatosi: {e}")


def get_translation_stats(user_id: int | None = None, limit: int = 10) -> list[dict]:
    """Tarjima statistikasini qaytaradi (JOIN quality_checks)."""
    try:
        with get_conn() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT t.article_name, t.status, t.translated_at, "
                    "       qc.changes_summary, qc.improved_file "
                    "FROM translations t "
                    "LEFT JOIN quality_checks qc ON t.id = qc.translation_id "
                    "WHERE t.user_id=? "
                    "ORDER BY t.translated_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT t.article_name, t.status, t.translated_at, "
                    "       qc.changes_summary, qc.improved_file "
                    "FROM translations t "
                    "LEFT JOIN quality_checks qc ON t.id = qc.translation_id "
                    "ORDER BY t.translated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"get_translation_stats xatosi: {e}")
        return []
