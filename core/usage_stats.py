#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/usage_stats.py - Token accounting shared by the two OpenAI callers.

WikiTranslator and WikiReviewer both fold the same four numbers out of a
chat completion and report them the same way; this is that code, once.
"""

from typing import Dict

from utils.logger import logger


def new_usage_stats(counter_name: str) -> Dict[str, int]:
    """
    A fresh stats dict.

    Args:
        counter_name: name of the call counter ("translations", "reviews")
    """
    return {counter_name: 0, "tokens_used": 0, "cached_tokens": 0, "prompt_tokens": 0}


def record_usage(stats: Dict[str, int], response) -> None:
    """
    Fold one response's token usage into `stats` and log the cache hit rate.

    `usage` is present as an attribute on the response but may be None, and
    the individual counts may be None too. Reading through them unguarded
    used to raise inside the caller's try block, where the except discarded
    an already finished translation.
    """
    usage = getattr(response, "usage", None)
    if not usage:
        return

    prompt_tokens = usage.prompt_tokens or 0
    stats["tokens_used"] += usage.total_tokens or 0
    stats["prompt_tokens"] += prompt_tokens

    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    stats["cached_tokens"] += cached

    hit_rate = (cached / prompt_tokens * 100) if prompt_tokens else 0
    logger.info(f"Cache: {cached}/{prompt_tokens} token ({hit_rate:.1f}%)")


def cache_hit_summary(stats: Dict[str, int]) -> str:
    """"cached/prompt (rate%)", as printed in the end-of-run stats block."""
    prompt_tokens = stats["prompt_tokens"]
    hit_rate = (stats["cached_tokens"] / prompt_tokens * 100) if prompt_tokens else 0
    return f"{stats['cached_tokens']}/{prompt_tokens} ({hit_rate:.1f}%)"
