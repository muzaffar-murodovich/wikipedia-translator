#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/translator.py - Translation via OpenAI
"""

from typing import Optional
from openai import OpenAI
import config
from utils.logger import logger


class WikiTranslator:
    """Translate Wikipedia articles to Uzbek via OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.stats = {"translations": 0, "tokens_used": 0}
        logger.info(f"🤖 Provider: OpenAI ({self.model})")

    def translate(self, prepared_text: str) -> Optional[str]:
        """
        Translate text to Uzbek.

        Args:
            prepared_text: Prepared text (with placeholders)

        Returns:
            Translated text or None
        """
        user_prompt = config.TRANSLATION_USER_PROMPT.format(text=prepared_text)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": config.TRANSLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

            translated = response.choices[0].message.content
            self.stats["translations"] += 1
            if hasattr(response, "usage"):
                self.stats["tokens_used"] += response.usage.total_tokens
            logger.success(f"Tarjima tugadi ({len(translated)} belgi)")
            return translated
        except Exception as e:
            logger.fail(f"Tarjima xatosi: {e}")
            return None

    def print_stats(self):
        logger.stats(
            "Tarjima Statistikasi",
            model=self.model,
            translations=self.stats["translations"],
            tokens_used=self.stats["tokens_used"],
        )
