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
from utils.logger import logger


class LocalizationManager:
    """
    Load, cache, and apply the localization map.
    Optimized with one-time regex compilation.
    """

    def __init__(self):
        self.map = self._load_map()
        self.regex = self._compile_regex()
        self.stats = {
            "replacements": 0,
            "patterns_count": len(self.map)
        }

    def _load_map(self) -> Dict[str, str]:
        """
        Load the localization map.

        A missing or unreadable file is reported loudly and leaves the map
        empty. It used to write a ten-entry stub over config.LOCALIZATION_FILE
        instead, which replaced the real 223-rule file and let the run finish
        looking healthy while producing an unlocalized article.
        """
        data = FileHandler.read_json(str(config.LOCALIZATION_FILE))

        if not data:
            logger.fail(
                f"Localization map yuklanmadi: {config.LOCALIZATION_FILE} — "
                "fayl yoʻq yoki boʻsh. Lokalizatsiya bosqichi hech narsa "
                "almashtirmaydi."
            )
            return {}

        if config.VERBOSE:
            print(f"✓ Localization map yuklandi: {len(data)} ta almashtirish")
        return data

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

        applied = 0

        def replacer(match):
            nonlocal applied
            matched_text = match.group(0)
            replacement = self.map.get(matched_text)
            if replacement is None:
                return matched_text
            applied += 1
            return replacement

        result = self.regex.sub(replacer, text)
        self.stats["replacements"] += applied

        return result

    def print_stats(self):
        """Print statistics."""
        print("\n📚 Localization Statistikasi:")
        print(f"  Qoidalar soni: {self.stats['patterns_count']}")
        print(f"  Qoʻllangan almashtirishlar: {self.stats['replacements']}")
