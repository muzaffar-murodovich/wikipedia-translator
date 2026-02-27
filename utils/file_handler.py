#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/file_handler.py - Barcha file operatsiyalari
Fayl o'qish, yozish, JSON bilan ishlash hammasini shu yerda.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class FileHandler:
    """File I/O bilan ishlash uchun universal class."""
    
    @staticmethod
    def read_file(filepath: str, encoding: str = 'utf-8') -> str:
        """
        Faylni o'qish.
        
        Args:
            filepath: Fayl yo'li
            encoding: Encoding (default: utf-8)
        
        Returns:
            Fayl mazmuni yoki "" agar xato bo'lsa
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
        Faylga yozish.
        
        Args:
            filepath: Fayl yo'li
            content: Yozish kerak bo'lgan matn
            encoding: Encoding (default: utf-8)
        
        Returns:
            Muvaffaqiyat bo'lsa True, aks holda False
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
        JSON faylni o'qish.
        
        Args:
            filepath: JSON fayl yo'li
        
        Returns:
            Parsed JSON dict yoki {} agar xato bo'lsa
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
        JSON faylga yozish.
        
        Args:
            filepath: JSON fayl yo'li
            data: Yozish kerak bo'lgan dict
            indent: JSON formatting (default: 2)
        
        Returns:
            Muvaffaqiyat bo'lsa True, aks holda False
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
        Faylga qo'shimcha yozish (append).
        
        Args:
            filepath: Fayl yo'li
            content: Qo'shimcha yozish kerak bo'lgan matn
            encoding: Encoding (default: utf-8)
        
        Returns:
            Muvaffaqiyat bo'lsa True, aks holda False
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
        """Fayl mavjud bo'lganini tekshirish."""
        return Path(filepath).exists()
    
    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Fayl hajmini olish (byte'da)."""
        try:
            return Path(filepath).stat().st_size
        except:
            return 0
    
    @staticmethod
    def read_lines(filepath: str, encoding: str = 'utf-8') -> list:
        """
        Faylni qator-qator o'qish.
        
        Returns:
            Qatorlar ro'yxati
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
        Faylning backup'ini yaratish.
        
        Returns:
            Backup fayl yo'li yoki None agar xato bo'lsa
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
        """Faylni o'chirish."""
        try:
            Path(filepath).unlink()
            return True
        except Exception as e:
            print(f"❌ File o'chirishda xato: {e}")
            return False
    
    @staticmethod
    def ensure_dir_exists(dirpath: str) -> bool:
        """Papka mavjud emasligini tekshirish va yaratish."""
        try:
            Path(dirpath).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"❌ Papka yaratishda xato: {e}")
            return False