#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/logger.py - Logging system
Writes all messages to console.
"""

import logging
import config


class Logger:
    """Central logging system (console-only)."""

    _instance = None

    def __new__(cls):
        """Singleton pattern - only one Logger instance."""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the Logger."""
        if self._initialized:
            return

        self.logger = logging.getLogger("WikiTranslator")
        self.logger.setLevel(self._get_log_level(config.LOG_LEVEL))

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._get_log_level(config.LOG_LEVEL))

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self._initialized = True
        self.debug(f"Logger initialize qilindi. Level: {config.LOG_LEVEL}")

    @staticmethod
    def _get_log_level(level_str: str) -> int:
        """Convert string to log level."""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(level_str.upper(), logging.INFO)

    def debug(self, message: str):
        """Log at debug level."""
        self.logger.debug(message)

    def info(self, message: str):
        """Log at info level."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log at warning level."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log at error level."""
        self.logger.error(message)

    def critical(self, message: str):
        """Log at critical level."""
        self.logger.critical(message)

    def section(self, title: str):
        """Log a section header."""
        separator = "=" * 60
        self.info(f"\n{separator}")
        self.info(f"  {title}")
        self.info(f"{separator}\n")

    def success(self, message: str):
        """Log a success message."""
        self.info(f"✅ {message}")

    def fail(self, message: str):
        """Log a failure message."""
        self.error(f"❌ {message}")

    def progress(self, current: int, total: int, title: str = ""):
        """Log progress."""
        percent = 100 * current / total
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)

        message = f"[{bar}] {percent:.1f}% ({current}/{total})"
        if title:
            message = f"{title}: {message}"

        self.info(message)

    def table(self, data: dict, title: str = ""):
        """Log data in table format."""
        if title:
            self.info(f"\n{title}")

        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0

        for key, value in data.items():
            self.info(f"  {str(key):<{max_key_len}} : {value}")

    def stats(self, title: str, **kwargs):
        """Log statistics."""
        self.info(f"\n📊 {title}:")
        for key, value in kwargs.items():
            self.info(f"  {key}: {value}")


# Global logger instance
logger = Logger()
