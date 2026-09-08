#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/cache_manager.py - In-memory memoization
Per-run memoization for QIDs, sitelinks, and redirects.
Data fetched from the API is kept in memory only (no disk persistence).
"""

from typing import Optional

from utils.logger import logger


class WikiCache:
    """
    Wikidata query in-memory memoization.
    3 cache types: QID, Sitelink, Redirect.

    A looked-up-and-absent answer is stored as the string "NONE" so a second
    lookup in the same run is served from memory rather than re-queried. That
    makes get_*() ambiguous on its own — it returns None both for "known to
    be absent" and for "never looked up" — so every tier also has a has_*()
    that answers the difference. Callers used to reach into the dicts
    themselves for it.
    """

    NOT_FOUND = "NONE"

    def __init__(self):
        self.qid_cache: dict = {}
        self.sitelink_cache: dict = {}
        self.redirect_cache: dict = {}

        self._tiers = {
            "qid": self.qid_cache,
            "sitelink": self.sitelink_cache,
            "redirect": self.redirect_cache,
        }

        self.stats = {
            "qid_hits": 0,
            "qid_misses": 0,
            "sitelink_hits": 0,
            "sitelink_misses": 0,
            "redirect_hits": 0,
            "redirect_misses": 0,
        }

    # ── shared tier access ───────────────────────────────────────────────────

    def _get(self, tier: str, key: str) -> Optional[str]:
        """Read one tier, counting the hit or miss. "NONE" reads back as None."""
        store = self._tiers[tier]
        if key in store:
            self.stats[f"{tier}_hits"] += 1
            value = store[key]
            return None if value == self.NOT_FOUND else value

        self.stats[f"{tier}_misses"] += 1
        return None

    def _set(self, tier: str, key: str, value: Optional[str]) -> None:
        """Write one tier, storing a falsy value as the NOT_FOUND sentinel."""
        self._tiers[tier][key] = value if value else self.NOT_FOUND

    def _has(self, tier: str, key: str) -> bool:
        """Whether this key was looked up at all, absent answers included."""
        return key in self._tiers[tier]

    # ── QID: title -> Q12345 ─────────────────────────────────────────────────

    def get_qid(self, site_code: str, title: str) -> Optional[str]:
        """QID for a title, or None if absent or not cached."""
        return self._get("qid", f"{site_code}:{title}")

    def set_qid(self, site_code: str, title: str, qid: Optional[str]) -> None:
        """Cache a QID; None is stored as the NOT_FOUND sentinel."""
        self._set("qid", f"{site_code}:{title}", qid)

    def has_qid(self, site_code: str, title: str) -> bool:
        """Whether this title's QID was looked up, "not found" included."""
        return self._has("qid", f"{site_code}:{title}")

    # ── Sitelink: QID -> title on the target wiki ────────────────────────────

    def get_sitelink(self, qid: str, target_site: str = "uzwiki") -> Optional[str]:
        """Target-wiki title for a QID, or None if absent or not cached."""
        return self._get("sitelink", f"{qid}:{target_site}")

    def set_sitelink(self, qid: str, target_site: str, title: Optional[str]) -> None:
        """Cache a sitelink; None is stored as the NOT_FOUND sentinel."""
        self._set("sitelink", f"{qid}:{target_site}", title)

    def has_sitelink(self, qid: str, target_site: str = "uzwiki") -> bool:
        """Whether this sitelink was looked up, "not found" included."""
        return self._has("sitelink", f"{qid}:{target_site}")

    # ── Redirect: title -> its target ────────────────────────────────────────

    def get_redirect(self, site_code: str, title: str) -> Optional[str]:
        """Redirect target for a title, or None if absent or not cached."""
        return self._get("redirect", f"{site_code}:{title}")

    def set_redirect(self, site_code: str, title: str, target: Optional[str]) -> None:
        """Cache a redirect target; a falsy target is stored as NOT_FOUND."""
        self._set("redirect", f"{site_code}:{title}", target)

    def has_redirect(self, site_code: str, title: str) -> bool:
        """Whether this title's redirect was looked up, "not found" included."""
        return self._has("redirect", f"{site_code}:{title}")

    # ── reporting ────────────────────────────────────────────────────────────

    def get_cache_size(self) -> dict:
        """Get cache sizes."""
        sizes = {tier: len(store) for tier, store in self._tiers.items()}
        sizes["total"] = sum(sizes.values())
        return sizes

    def print_stats(self):
        """Print cache statistics."""
        labels = {"qid": "QID", "sitelink": "Sitelink", "redirect": "Redirect"}

        rates = {}
        for tier, label in labels.items():
            hits = self.stats[f"{tier}_hits"]
            total = hits + self.stats[f"{tier}_misses"]
            if total:
                rates[label] = f"{hits}/{total} ({100 * hits / total:.1f}%)"
        if rates:
            logger.stats("Cache Statistikasi", **rates)

        cache_size = self.get_cache_size()
        logger.stats(
            "Cache Hajmi",
            **{label: cache_size[tier] for tier, label in labels.items()},
            Jami=cache_size["total"],
        )
