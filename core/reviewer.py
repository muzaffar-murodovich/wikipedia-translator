#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/reviewer.py - Post-translation review via AI
Phase 5: Applies translation_rules.md rules to the localized wikitext.
"""

from pathlib import Path
from typing import Optional
from openai import OpenAI
import config
from utils.logger import logger


class WikiReviewer:
    """Review and fix translated wikitext according to translation_rules.md."""

    RULES_FILE = Path("translation_rules.md")

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.rules = self._load_rules()
        self.stats = {"reviews": 0, "tokens_used": 0}

        if self.rules:
            logger.success(f"Tahrir qoidalari yuklandi ({len(self.rules)} belgi)")
        else:
            logger.warning("translation_rules.md topilmadi — Phase 5 o'tkazib yuboriladi")

    def _load_rules(self) -> Optional[str]:
        """Load translation_rules.md content."""
        if not self.RULES_FILE.exists():
            return None
        try:
            return self.RULES_FILE.read_text(encoding="utf-8")
        except Exception as e:
            logger.fail(f"Qoidalar faylini o'qishda xato: {e}")
            return None

    def is_available(self) -> bool:
        """Return True if rules were loaded successfully."""
        return self.rules is not None

    def review(self, text: str) -> Optional[str]:
        """
        Review and fix translated wikitext using translation_rules.md.

        Args:
            text: Localized wikitext (output of Phase 4)

        Returns:
            Corrected wikitext, or None on failure
        """
        if not self.is_available():
            return text

        user_prompt = config.REVIEW_USER_PROMPT.format(
            rules=self.rules,
            text=text,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": config.REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

            reviewed = response.choices[0].message.content

            reviewed = response.choices[0].message.content.strip()
            if reviewed.startswith("```"):
                reviewed = reviewed.split("\n", 1)[-1]
            if reviewed.endswith("```"):
                reviewed = reviewed.rsplit("\n", 1)[0]
            reviewed = reviewed.strip()
            self.stats["reviews"] += 1
            if hasattr(response, "usage"):
                self.stats["tokens_used"] += response.usage.total_tokens
            logger.success(f"Tahrir tugadi ({len(reviewed)} belgi)")
            return reviewed

        except Exception as e:
            logger.fail(f"Tahrir xatosi: {e}")
            return None

    def print_stats(self):
        logger.stats(
            "Tahrir Statistikasi",
            model=self.model,
            reviews=self.stats["reviews"],
            tokens_used=self.stats["tokens_used"],
        )