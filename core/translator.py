#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/translator.py - Translation via Claude and OpenAI
Set AI_PROVIDER = "claude" or "openai" in config.
"""

from typing import Optional
import config
from utils.logger import logger


class WikiTranslator:
    """
    Translate Wikipedia articles to Uzbek.
    Uses Claude or OpenAI based on config.AI_PROVIDER.
    """

    def __init__(self):
        self.provider = getattr(config, "AI_PROVIDER", "openai").lower()
        self.stats = {"translations": 0, "tokens_used": 0}

        if self.provider == "claude":
            import anthropic
            self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            self.model = getattr(config, "CLAUDE_MODEL", "claude-sonnet-4-6")
            logger.info(f"🤖 Provider: Claude ({self.model})")
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.model = getattr(config, "OPENAI_MODEL", "gpt-4o")
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
            if self.provider == "openai":
                return self._translate_openai(user_prompt)
            else:
                return self._translate_claude(user_prompt)
        except Exception as e:
            logger.fail(f"Tarjima xatosi ({self.provider}): {e}")
            return None

    def _translate_claude(self, user_prompt: str) -> Optional[str]:
        """Translate via Claude API."""
        logger.info(f"Tarjima qilinmoqda (Claude: {self.model})...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8096,
            system=config.TRANSLATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        translated = response.content[0].text
        self.stats["translations"] += 1
        self.stats["tokens_used"] += (
            response.usage.input_tokens + response.usage.output_tokens
        )
        logger.success(f"Tarjima tugadi ({len(translated)} belgi)")
        return translated

    def _translate_openai(self, user_prompt: str) -> Optional[str]:
        """Translate via OpenAI API."""
        logger.info(f"Tarjima qilinmoqda (OpenAI: {self.model})...")

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

    def print_stats(self):
        logger.stats(
            "Tarjima Statistikasi",
            provider=self.provider,
            model=self.model,
            translations=self.stats["translations"],
            tokens_used=self.stats["tokens_used"],
        )
