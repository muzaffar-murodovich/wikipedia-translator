#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/cache_manager.py - In-memory memoization
Per-run memoization for QIDs, sitelinks, and redirects.
Data fetched from the API is kept in memory only (no disk persistence).
"""

from typing import Optional


class WikiCache:
    """
    Wikidata query in-memory memoization.
    3 cache types: QID, Sitelink, Redirect.
    """

    def __init__(self):
        self.qid_cache: dict = {}
        self.sitelink_cache: dict = {}
        self.redirect_cache: dict = {}

        self.stats = {
            "qid_hits": 0,
            "qid_misses": 0,
            "sitelink_hits": 0,
            "sitelink_misses": 0,
            "redirect_hits": 0,
            "redirect_misses": 0,
        }

    def get_qid(self, site_code: str, title: str) -> Optional[str]:
        """
        Get QID from cache.

        Args:
            site_code: Site code (en, uz, ru)
            title: Article title

        Returns:
            QID (Q12345) or None if not found
        """
        key = f"{site_code}:{title}"

        if key in self.qid_cache:
            cached_value = self.qid_cache[key]
            if cached_value == "NONE":
                self.stats["qid_hits"] += 1
                return None
            self.stats["qid_hits"] += 1
            return cached_value

        self.stats["qid_misses"] += 1
        return None

    def set_qid(self, site_code: str, title: str, qid: Optional[str]):
        """
        Save QID to cache.

        Args:
            site_code: Site code
            title: Article title
            qid: QID or None (None is stored as "NONE")
        """
        key = f"{site_code}:{title}"
        self.qid_cache[key] = qid if qid else "NONE"

    def get_sitelink(self, qid: str, target_site: str = "uzwiki") -> Optional[str]:
        """
        Get sitelink from cache.

        Args:
            qid: Wikidata QID (Q12345)
            target_site: Target site (uzwiki, enwiki, ruwiki)

        Returns:
            Sitelink (article title) or None
        """
        key = f"{qid}:{target_site}"

        if key in self.sitelink_cache:
            cached_value = self.sitelink_cache[key]
            if cached_value == "NONE":
                self.stats["sitelink_hits"] += 1
                return None
            self.stats["sitelink_hits"] += 1
            return cached_value

        self.stats["sitelink_misses"] += 1
        return None

    def set_sitelink(self, qid: str, target_site: str, title: Optional[str]):
        """
        Save sitelink to cache.

        Args:
            qid: Wikidata QID
            target_site: Target site
            title: Title or None
        """
        key = f"{qid}:{target_site}"
        self.sitelink_cache[key] = title if title else "NONE"

    def get_redirect(self, site_code: str, title: str) -> Optional[str]:
        """
        Get redirect from cache.

        Args:
            site_code: Site code
            title: Article title (may be a redirect)

        Returns:
            Actual title or None
        """
        key = f"{site_code}:{title}"

        if key in self.redirect_cache:
            cached_value = self.redirect_cache[key]
            if cached_value == "NONE":
                self.stats["redirect_hits"] += 1
                return None
            self.stats["redirect_hits"] += 1
            return cached_value

        self.stats["redirect_misses"] += 1
        return None

    def set_redirect(self, site_code: str, title: str, target: str):
        """
        Save redirect to cache.

        Args:
            site_code: Site code
            title: Original title
            target: Target title
        """
        key = f"{site_code}:{title}"
        self.redirect_cache[key] = target if target else "NONE"

    def get_cache_size(self) -> dict:
        """Get cache sizes."""
        return {
            "qid": len(self.qid_cache),
            "sitelink": len(self.sitelink_cache),
            "redirect": len(self.redirect_cache),
            "total": len(self.qid_cache) + len(self.sitelink_cache) + len(self.redirect_cache)
        }

    def print_stats(self):
        """Print cache statistics."""
        print("\n📊 Cache Statistikasi:")

        total_qid = self.stats["qid_hits"] + self.stats["qid_misses"]
        if total_qid > 0:
            hit_rate = 100 * self.stats["qid_hits"] / total_qid
            print(f"  QID Cache: {self.stats['qid_hits']}/{total_qid} hits ({hit_rate:.1f}%)")

        total_sitelink = self.stats["sitelink_hits"] + self.stats["sitelink_misses"]
        if total_sitelink > 0:
            hit_rate = 100 * self.stats["sitelink_hits"] / total_sitelink
            print(f"  Sitelink Cache: {self.stats['sitelink_hits']}/{total_sitelink} hits ({hit_rate:.1f}%)")

        total_redirect = self.stats["redirect_hits"] + self.stats["redirect_misses"]
        if total_redirect > 0:
            hit_rate = 100 * self.stats["redirect_hits"] / total_redirect
            print(f"  Redirect Cache: {self.stats['redirect_hits']}/{total_redirect} hits ({hit_rate:.1f}%)")

        cache_size = self.get_cache_size()
        print(f"\n💾 Cache Hajmi:")
        print(f"  QID: {cache_size['qid']}")
        print(f"  Sitelink: {cache_size['sitelink']}")
        print(f"  Redirect: {cache_size['redirect']}")
        print(f"  Jami: {cache_size['total']}")
