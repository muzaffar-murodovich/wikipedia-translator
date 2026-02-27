#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/translator.py - OpenAI orqali tarjima
Placeholder'larni saqlab, matnni AI'ga yuborish.
"""

from typing import Optional

from openai import OpenAI

import config
from utils.logger import logger


class WikiTranslator:
    """
    Wikipedia maqolalarini o'zbek tiliga tarjima qilish.
    """
    
    def __init__(self):
        """Initialize."""
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.stats = {
            "translations": 0,
            "tokens_used": 0,
            "cost": 0.0
        }
    
    def translate(self, prepared_text: str) -> Optional[str]:
        """
        Matnni o'zbek tiliga tarjima qilish.
        
        Args:
            prepared_text: Tayyorlangan matn (placeholder'lar bilan)
        
        Returns:
            Tarjima qilingan matn yoki None agar xato bo'lsa
        """
        try:
            logger.info(f"Tarjima qilinmoqda ({self.model})...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": config.TRANSLATION_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": self._format_user_prompt(prepared_text)
                    }
                ],
            )
            
            translated_text = response.choices[0].message.content
            
            # Statistika yangilash
            self.stats["translations"] += 1
            if hasattr(response, 'usage'):
                self.stats["tokens_used"] += response.usage.total_tokens
            
            logger.success(f"Tarjima tugadi ({len(translated_text)} belgi)")
            return translated_text
        
        except Exception as e:
            logger.fail(f"Tarjima xatosi: {e}")
            return None
    
    def _format_user_prompt(self, text: str) -> str:
        """
        Foydalanuvchi prompt'ni formatlash.
        Config'dan olingan prompt'ni matnni qo'shish.
        """
        return config.TRANSLATION_USER_PROMPT.format(text=text)
    
    def print_stats(self):
        """Statistika chiqarish."""
        logger.stats(
            "Tarjima Statistikasi",
            translations=self.stats["translations"],
            tokens_used=self.stats["tokens_used"],
        )