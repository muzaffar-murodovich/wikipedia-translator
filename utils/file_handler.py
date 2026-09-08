#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/file_handler.py - All file operations
File reading, writing, and JSON handling in one place.
"""

import json
from pathlib import Path
from typing import Dict, Any

from utils.logger import logger


class FileHandler:
    """Universal class for file I/O operations."""

    @staticmethod
    def read_file(filepath: str, encoding: str = 'utf-8') -> str:
        """
        Read a file.

        Args:
            filepath: File path
            encoding: Encoding (default: utf-8)

        Returns:
            File contents or "" on error
        """
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            logger.fail(f"Fayl topilmadi: {filepath}")
            return ""
        except Exception as e:
            logger.fail(f"File o'qishda xato: {e}")
            return ""

    @staticmethod
    def write_file(filepath: str, content: str, encoding: str = 'utf-8') -> bool:
        """
        Write to a file.

        Args:
            filepath: File path
            content: Text to write
            encoding: Encoding (default: utf-8)

        Returns:
            True on success, False otherwise
        """
        try:
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.fail(f"File yozishda xato: {e}")
            return False

    @staticmethod
    def read_json(filepath: str) -> Dict[str, Any]:
        """
        Read a JSON file.

        Args:
            filepath: JSON file path

        Returns:
            Parsed JSON dict or {} on error
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            logger.fail(f"JSON o'qishda xato: {e}")
            return {}
        except Exception as e:
            logger.fail(f"JSON faylida xato: {e}")
            return {}

    @staticmethod
    def write_json(filepath: str, data: Dict[str, Any], indent: int = 2) -> bool:
        """
        Write to a JSON file.

        Args:
            filepath: JSON file path
            data: Dict to write
            indent: JSON formatting (default: 2)

        Returns:
            True on success, False otherwise
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except Exception as e:
            logger.fail(f"JSON yozishda xato: {e}")
            return False

    @staticmethod
    def file_exists(filepath: str) -> bool:
        """Check if file exists."""
        return Path(filepath).exists()

