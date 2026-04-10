#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/localization.py - Localization dictionary management
Optimal solution for handling 130+ replacements.
Compiled once, then runs fast.
"""

import re
from typing import Dict, Optional
import config
from utils.file_handler import FileHandler


class LocalizationManager:
    """
    Load, cache, and apply the localization map.
    Optimized with one-time regex compilation.
    """

    def __init__(self):
        self.map = self._load_or_create_map()
        self.regex = self._compile_regex()
        self.stats = {
            "replacements": 0,
            "patterns_count": len(self.map)
        }

    def _load_or_create_map(self) -> Dict[str, str]:
        """Load localization map, or create default if missing."""
        data = FileHandler.read_json(str(config.LOCALIZATION_FILE))

        if data:
            if config.VERBOSE:
                print(f"✓ Localization map yuklandi: {len(data)} ta almashtirish")
            return data

        # Create default map
        default_map = self._get_default_map()
        FileHandler.write_json(str(config.LOCALIZATION_FILE), default_map)

        if config.VERBOSE:
            print(f"✓ Yaratildi: {config.LOCALIZATION_FILE} ({len(default_map)} ta almashtirish)")

        return default_map

    @staticmethod
    def _get_default_map() -> Dict[str, str]:
        """Default localization map."""
        return {
            # Templates
            "{{Langx|": "{{Lang-",
            "{{cite web": "{{veb havola",
            "{{cite book": "{{kitob havola",

            # Categories
            "[[Category:": "[[Turkum:",
            "[[Turkum:Islom olimlari]]": "[[Turkum:Islom ulamolari]]",

            # Common words
            "United States": "Amerika Qoʻshma Shtatlari",
            "New York": "Nyu-York",
            "University": "Universiteti",
            "College": "Kollej",
            "Department": "Kafedra",
        }

    def _compile_regex(self) -> Optional[re.Pattern]:
        """
        Compile regex pattern.
        Longest keys first (to prevent greedy matching issues).
        """
        if not self.map:
            return None

        # Sort by length (longest first)
        sorted_keys = sorted(self.map.keys(), key=len, reverse=True)

        # Escape regex special characters
        escaped_keys = [re.escape(key) for key in sorted_keys]

        # Build pattern: key1|key2|key3|...
        pattern_str = '|'.join(escaped_keys)

        try:
            return re.compile(pattern_str)
        except Exception as e:
            print(f"❌ Regex compile qilishda xato: {e}")
            return None

    def apply(self, text: str) -> str:
        """
        Apply localization replacements.
        All replacements done in a single regex pass.

        Args:
            text: Text to process

        Returns:
            Processed text
        """
        if not self.regex or not self.map:
            return text

        def replacer(match):
            matched_text = match.group(0)
            return self.map.get(matched_text, matched_text)

        result = self.regex.sub(replacer, text)

        if result != text:
            self.stats["replacements"] += 1

        return result

    def add_replacement(self, english: str, uzbek: str) -> bool:
        """
        Add a new replacement.

        Args:
            english: English text
            uzbek: Uzbek translation

        Returns:
            True on success
        """
        try:
            self.map[english] = uzbek
            self.regex = self._compile_regex()

            FileHandler.write_json(str(config.LOCALIZATION_FILE), self.map)

            if config.VERBOSE:
                print(f"✓ Qoʻshildi: '{english}' → '{uzbek}'")

            return True
        except Exception as e:
            print(f"❌ Almashtirish qoʻshishda xato: {e}")
            return False

    def remove_replacement(self, english: str) -> bool:
        """
        Remove a replacement.

        Args:
            english: English text to remove

        Returns:
            True on success
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
        """Get a replacement value."""
        return self.map.get(english)

    def has_replacement(self, english: str) -> bool:
        """Check if a replacement exists."""
        return english in self.map

    def get_all_replacements(self) -> Dict[str, str]:
        """Get all replacements (copy)."""
        return self.map.copy()

    def print_stats(self):
        """Print statistics."""
        print(f"\n📚 Localization Statistikasi:")
        print(f"  Jami almashtirishlar: {self.stats['patterns_count']}")
        print(f"  Qoʻllangan: {self.stats['replacements']}")

    def search_replacements(self, keyword: str) -> Dict[str, str]:
        """
        Search for replacements containing a keyword.

        Args:
            keyword: Keyword to search for

        Returns:
            Matching replacements
        """
        results = {}
        keyword_lower = keyword.lower()

        for english, uzbek in self.map.items():
            if keyword_lower in english.lower() or keyword_lower in uzbek.lower():
                results[english] = uzbek

        return results
