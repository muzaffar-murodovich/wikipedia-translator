#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/localization.py - Localization lug'atni boshqarish
130+ ta almashtirish bilan ishlash uchun optimal yechim.
Bir marta compile qilinadi, keyin tezda ishlaydi.
"""

import re
from typing import Dict, Optional
import config
from utils.file_handler import FileHandler


class LocalizationManager:
    """
    Localization map'ni load, cache, va apply qilish.
    Bir martalik regex compilation uchun optimal.
    """
    
    def __init__(self):
        """LocalizationManager'ni initialize qilish."""
        self.map = self._load_or_create_map()
        self.regex = self._compile_regex()
        self.stats = {
            "replacements": 0,
            "patterns_count": len(self.map)
        }
    
    def _load_or_create_map(self) -> Dict[str, str]:
        """
        Localization map'ni load qilish.
        Agar fayl yo'q bo'lsa, default map yaratish.
        """
        data = FileHandler.read_json(str(config.LOCALIZATION_FILE))
        
        if data:
            if config.VERBOSE:
                print(f"✓ Localization map yuklandi: {len(data)} ta almashtirish")
            return data
        
        # Default map yaratish
        default_map = self._get_default_map()
        FileHandler.write_json(str(config.LOCALIZATION_FILE), default_map)
        
        if config.VERBOSE:
            print(f"✓ Yaratildi: {config.LOCALIZATION_FILE} ({len(default_map)} ta almashtirish)")
        
        return default_map
    
    @staticmethod
    def _get_default_map() -> Dict[str, str]:
        """Default localization map."""
        return {
            # Andozalar
            "{{Langx|": "{{Lang-",
            "{{cite web": "{{veb havola",
            "{{cite book": "{{kitob havola",
            
            # Turkumlar
            "[[Category:": "[[Turkum:",
            "[[Turkum:Islom olimlari]]": "[[Turkum:Islom ulamolari]]",
            
            # Umumiy so'zlar
            "United States": "Amerika Qoʻshma Shtatlari",
            "New York": "Nyu-York",
            "University": "Universiteti",
            "College": "Kollej",
            "Department": "Kafedra",
        }
    
    def _compile_regex(self) -> Optional[re.Pattern]:
        """
        Regex pattern compile qilish.
        Eng uzun kalit so'zlar avvalgani (greedy matching oldini olish uchun).
        """
        if not self.map:
            return None
        
        # Uzunlik bo'yicha sortlash (eng uzun avvalgani)
        sorted_keys = sorted(self.map.keys(), key=len, reverse=True)
        
        # Regex special characters escape qilish
        escaped_keys = [re.escape(key) for key in sorted_keys]
        
        # Pattern yaratish: key1|key2|key3|...
        pattern_str = '|'.join(escaped_keys)
        
        try:
            return re.compile(pattern_str)
        except Exception as e:
            print(f"❌ Regex compile qilishda xato: {e}")
            return None
    
    def apply(self, text: str) -> str:
        """
        Localization almashtiruvlarini qoʻllash.
        Bir martalik regex pass'da barcha almashtirishlar bajariladi.
        
        Args:
            text: Almashtirilish kerak boʻlgan matn
        
        Returns:
            Almashtirilgan matn
        """
        if not self.regex or not self.map:
            return text
        
        def replacer(match):
            """Match'ni localization map'dan topish va almashtirish."""
            matched_text = match.group(0)
            replacement = self.map.get(matched_text, matched_text)
            return replacement
        
        # Bir marta regex sub - tezroq!
        result = self.regex.sub(replacer, text)
        
        # Statistika yangilash
        if result != text:
            self.stats["replacements"] += 1
        
        return result
    
    def add_replacement(self, english: str, uzbek: str) -> bool:
        """
        Yangi almashtirish qoʻshish.
        
        Args:
            english: Inglizcha matn
            uzbek: Oʻzbekcha tarjima
        
        Returns:
            Muvaffaqiyat bo'lsa True
        """
        try:
            self.map[english] = uzbek
            self.regex = self._compile_regex()  # Regex qayta compile qilish
            
            # Faylga saqlash
            FileHandler.write_json(str(config.LOCALIZATION_FILE), self.map)
            
            if config.VERBOSE:
                print(f"✓ Qoʻshildi: '{english}' → '{uzbek}'")
            
            return True
        except Exception as e:
            print(f"❌ Almashtirish qoʻshishda xato: {e}")
            return False
    
    def remove_replacement(self, english: str) -> bool:
        """
        Almashtiruvni oʻchirish.
        
        Args:
            english: Oʻchirilish kerak boʻlgan inglizcha matn
        
        Returns:
            Muvaffaqiyat bo'lsa True
        """
        if english in self.map:
            del self.map[english]
            self.regex = self._compile_regex()
            FileHandler.write_json(str(config.LOCALIZATION_FILE), self.map)
            
            if config.VERBOSE:
                print(f"✓ Oʻchirildi: '{english}'")
            
            return True
        return False
    
    def get_replacement(self, english: str) -> Optional[str]:
        """Almashtiruvni olish."""
        return self.map.get(english)
    
    def has_replacement(self, english: str) -> bool:
        """Almashtiruvni tekshirish."""
        return english in self.map
    
    def get_all_replacements(self) -> Dict[str, str]:
        """Barcha almashtiruvlarni olish (copy)."""
        return self.map.copy()
    
    def print_stats(self):
        """Statistika chiqarish."""
        print(f"\n📚 Localization Statistikasi:")
        print(f"  Jami almashtirishlar: {self.stats['patterns_count']}")
        print(f"  Qoʻllangan: {self.stats['replacements']}")
    
    def search_replacements(self, keyword: str) -> Dict[str, str]:
        """
        Qidiruv - keyword'ni oʻz ichiga olgan almashtiruvlarni topish.
        
        Args:
            keyword: Qidirilish kerak boʻlgan soʻz
        
        Returns:
            Mos kelgan almashtirishlar
        """
        results = {}
        keyword_lower = keyword.lower()
        
        for english, uzbek in self.map.items():
            if keyword_lower in english.lower() or keyword_lower in uzbek.lower():
                results[english] = uzbek
        
        return results