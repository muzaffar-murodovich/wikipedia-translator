#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/file_handler.py - All file operations
File reading, writing, and JSON handling in one place.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


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
            print(f"❌ Fayl topilmadi: {filepath}")
            return ""
        except Exception as e:
            print(f"❌ File o'qishda xato: {e}")
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
            print(f"❌ File yozishda xato: {e}")
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
            print(f"❌ JSON o'qishda xato: {e}")
            return {}
        except Exception as e:
            print(f"❌ JSON faylida xato: {e}")
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
            print(f"❌ JSON yozishda xato: {e}")
            return False

    @staticmethod
    def append_file(filepath: str, content: str, encoding: str = 'utf-8') -> bool:
        """
        Append to a file.

        Args:
            filepath: File path
            content: Text to append
            encoding: Encoding (default: utf-8)

        Returns:
            True on success, False otherwise
        """
        try:
            with open(filepath, 'a', encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"❌ File append'da xato: {e}")
            return False

    @staticmethod
    def file_exists(filepath: str) -> bool:
        """Check if file exists."""
        return Path(filepath).exists()

    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Get file size in bytes."""
        try:
            return Path(filepath).stat().st_size
        except:
            return 0

    @staticmethod
    def read_lines(filepath: str, encoding: str = 'utf-8') -> list:
        """
        Read file line by line.

        Returns:
            List of lines
        """
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.readlines()
        except Exception as e:
            print(f"❌ File o'qishda xato: {e}")
            return []

    @staticmethod
    def create_backup(filepath: str) -> Optional[str]:
        """
        Create a backup of a file.

        Returns:
            Backup file path or None on error
        """
        try:
            path = Path(filepath)
            if not path.exists():
                return None

            backup_path = f"{filepath}.backup"
            content = path.read_text(encoding='utf-8')
            Path(backup_path).write_text(content, encoding='utf-8')
            return backup_path
        except Exception as e:
            print(f"❌ Backup yaratishda xato: {e}")
            return None

    @staticmethod
    def delete_file(filepath: str) -> bool:
        """Delete a file."""
        try:
            Path(filepath).unlink()
            return True
        except Exception as e:
            print(f"❌ File o'chirishda xato: {e}")
            return False

    @staticmethod
    def ensure_dir_exists(dirpath: str) -> bool:
        """Ensure directory exists, create if needed."""
        try:
            Path(dirpath).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"❌ Papka yaratishda xato: {e}")
            return False
