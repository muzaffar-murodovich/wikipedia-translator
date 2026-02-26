#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/logger.py - Logging tizimi
Barcha xabarlarni console va faylga yozish.
"""

import logging
from datetime import datetime
from pathlib import Path
import config


class Logger:
    """
    Markaziy logging tizimi.
    Console va fayl'ga yozish.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - faqat bitta Logger instance."""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Logger'ni initialize qilish."""
        if self._initialized:
            return
        
        self.logger = logging.getLogger("WikiTranslator")
        self.logger.setLevel(self._get_log_level(config.LOG_LEVEL))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._get_log_level(config.LOG_LEVEL))
        
        # File handler
        file_handler = logging.FileHandler(
            config.LOG_FILE,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        self._initialized = True
        self.debug(f"Logger initialize qilindi. Level: {config.LOG_LEVEL}")
    
    @staticmethod
    def _get_log_level(level_str: str) -> int:
        """String'dan log level'ni olish."""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(level_str.upper(), logging.INFO)
    
    def debug(self, message: str):
        """Debug level'da yozish."""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Info level'da yozish."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Warning level'da yozish."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Error level'da yozish."""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Critical level'da yozish."""
        self.logger.critical(message)
    
    def section(self, title: str):
        """Bo'limni yozish."""
        separator = "=" * 60
        self.info(f"\n{separator}")
        self.info(f"  {title}")
        self.info(f"{separator}\n")
    
    def success(self, message: str):
        """Muvaffaqiyat xabari."""
        self.info(f"✅ {message}")
    
    def fail(self, message: str):
        """Xato xabari."""
        self.error(f"❌ {message}")
    
    def progress(self, current: int, total: int, title: str = ""):
        """Jarayon chiqarish."""
        percent = 100 * current / total
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        message = f"[{bar}] {percent:.1f}% ({current}/{total})"
        if title:
            message = f"{title}: {message}"
        
        self.info(message)
    
    def table(self, data: dict, title: str = ""):
        """Jadval ko'rinishida yozish."""
        if title:
            self.info(f"\n{title}")
        
        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0
        
        for key, value in data.items():
            self.info(f"  {str(key):<{max_key_len}} : {value}")
    
    def stats(self, title: str, **kwargs):
        """Statistika yozish."""
        self.info(f"\n📊 {title}:")
        for key, value in kwargs.items():
            self.info(f"  {key}: {value}")
    
    def get_log_path(self) -> Path:
        """Log fayl yo'li."""
        return config.LOG_FILE
    
    def clear_log(self) -> bool:
        """Log faylni tozalash."""
        try:
            Path(config.LOG_FILE).unlink()
            self.info("Log fayl tozalandi")
            return True
        except Exception as e:
            self.error(f"Log faylni tozalashda xato: {e}")
            return False
    
    def get_log_size(self) -> int:
        """Log fayl hajmi (byte'da)."""
        try:
            return Path(config.LOG_FILE).stat().st_size
        except:
            return 0


# Global logger instance
logger = Logger()