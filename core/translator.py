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
        self.stats = {"translations": 0, "tokens_used": 0, "cached_tokens": 0, "prompt_tokens": 0}
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
                self.stats["prompt_tokens"] += response.usage.prompt_tokens
                details = getattr(response.usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                self.stats["cached_tokens"] += cached
                hit_rate = (cached / response.usage.prompt_tokens * 100) if response.usage.prompt_tokens else 0
                logger.info(f"Cache: {cached}/{response.usage.prompt_tokens} token ({hit_rate:.1f}%)")
            logger.success(f"Tarjima tugadi ({len(translated)} belgi)")
            return translated
        except Exception as e:
            logger.fail(f"Tarjima xatosi: {e}")
            return None

    def print_stats(self):
        hit_rate = (
            self.stats["cached_tokens"] / self.stats["prompt_tokens"] * 100
            if self.stats["prompt_tokens"] else 0
        )
        logger.stats(
            "Tarjima Statistikasi",
            model=self.model,
            translations=self.stats["translations"],
            tokens_used=self.stats["tokens_used"],
            cached_tokens=f"{self.stats['cached_tokens']}/{self.stats['prompt_tokens']} ({hit_rate:.1f}%)",
        )
