#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/translator.py - Translation via OpenAI
"""

from typing import Optional, Sequence
from openai import OpenAI
import config
from core.usage_stats import new_usage_stats, record_usage, cache_hit_summary
from utils.logger import logger


class WikiTranslator:
    """Translate Wikipedia articles to Uzbek via OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.stats = new_usage_stats("translations")
        logger.info(f"🤖 Provider: OpenAI ({self.model})")

    @staticmethod
    def _forced_links_block(titles: Optional[Sequence[str]]) -> str:
        """
        Build the "translate these targets by name" prompt block.

        A general rule is not enough: the prepared text is dominated by
        [[Q12345|...]] placeholders that the model must not touch, and it
        generalises that to plain English wikilinks too. Naming the
        offending targets one by one is what actually gets through.

        Returns:
            Formatted block, or "" when every link resolved to uz.wiki
        """
        if not titles:
            return ""
        listing = "\n".join(f"   - [[{t}]]" for t in titles)
        return config.FORCED_LINKS_TEMPLATE.format(titles=listing)

    def translate(
        self, prepared_text: str, forced_links: Optional[Sequence[str]] = None
    ) -> Optional[str]:
        """
        Translate text to Uzbek.

        Args:
            prepared_text: Prepared text (with placeholders)
            forced_links: Wikilink targets with no uz.wiki article — the model
                is told by name to translate these, not just by a general rule

        Returns:
            Translated text or None
        """
        user_prompt = config.TRANSLATION_USER_PROMPT.format(
            text=prepared_text,
            forced_links=self._forced_links_block(forced_links),
        )

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
            record_usage(self.stats, response)
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
            cached_tokens=cache_hit_summary(self.stats),
        )
