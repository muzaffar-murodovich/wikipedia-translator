#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/cache_manager.py - Cache system
Caches QIDs, sitelinks, and redirects.
Data fetched from the API once is stored as JSON.
"""

import json
from pathlib import Path
from typing import Optional, Dict
import config
from utils.file_handler import FileHandler


class WikiCache:
    """
    Wikidata query cache system.
    3 cache types: QID, Sitelink, Redirect.
    """

    def __init__(self):
        self.qid_cache = FileHandler.read_json(str(config.QID_CACHE_FILE))
        self.sitelink_cache = FileHandler.read_json(str(config.SITELINK_CACHE_FILE))
        self.redirect_cache = FileHandler.read_json(str(config.REDIRECT_CACHE_FILE))

        # Deferred write mode
        self._deferred = False
        self._dirty = {"qid": False, "sitelink": False, "redirect": False}

        # Statistics
        self.stats = {
            "qid_hits": 0,
            "qid_misses": 0,
            "sitelink_hits": 0,
            "sitelink_misses": 0,
            "redirect_hits": 0,
            "redirect_misses": 0,
        }

    def begin_batch(self):
        """Start deferred write mode."""
        self._deferred = True
        self._dirty = {"qid": False, "sitelink": False, "redirect": False}

    def end_batch(self):
        """Flush deferred cache changes to disk."""
        self._deferred = False
        if self._dirty["qid"]:
            self._save_cache(self.qid_cache, config.QID_CACHE_FILE)
        if self._dirty["sitelink"]:
            self._save_cache(self.sitelink_cache, config.SITELINK_CACHE_FILE)
        if self._dirty["redirect"]:
            self._save_cache(self.redirect_cache, config.REDIRECT_CACHE_FILE)
        self._dirty = {"qid": False, "sitelink": False, "redirect": False}

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
        if self._deferred:
            self._dirty["qid"] = True
        else:
            self._save_cache(self.qid_cache, config.QID_CACHE_FILE)

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
        if self._deferred:
            self._dirty["sitelink"] = True
        else:
            self._save_cache(self.sitelink_cache, config.SITELINK_CACHE_FILE)

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
        if self._deferred:
            self._dirty["redirect"] = True
        else:
            self._save_cache(self.redirect_cache, config.REDIRECT_CACHE_FILE)

    def _save_cache(self, data: dict, filepath: Path):
        """Save cache to JSON."""
        FileHandler.write_json(str(filepath), data)

    def clear_cache(self, cache_type: str = "all"):
        """
        Clear cache.

        Args:
            cache_type: "qid", "sitelink", "redirect" or "all"
        """
        if cache_type in ("qid", "all"):
            self.qid_cache = {}
            self._save_cache(self.qid_cache, config.QID_CACHE_FILE)
            print("✓ QID cache tozalandi")

        if cache_type in ("sitelink", "all"):
            self.sitelink_cache = {}
            self._save_cache(self.sitelink_cache, config.SITELINK_CACHE_FILE)
            print("✓ Sitelink cache tozalandi")

        if cache_type in ("redirect", "all"):
            self.redirect_cache = {}
            self._save_cache(self.redirect_cache, config.REDIRECT_CACHE_FILE)
            print("✓ Redirect cache tozalandi")

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

    def export_cache(self, filepath: str) -> bool:
        """
        Export cache (for backup).

        Args:
            filepath: Export file path

        Returns:
            True on success
        """
        try:
            all_cache = {
                "qid": self.qid_cache,
                "sitelink": self.sitelink_cache,
                "redirect": self.redirect_cache,
            }
            FileHandler.write_json(filepath, all_cache)
            print(f"✓ Cache eksport qilindi: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Cache eksport qilishda xato: {e}")
            return False

    def import_cache(self, filepath: str) -> bool:
        """
        Import cache (from backup).

        Args:
            filepath: Import file path

        Returns:
            True on success
        """
        try:
            data = FileHandler.read_json(filepath)
            if "qid" in data:
                self.qid_cache = data["qid"]
                self._save_cache(self.qid_cache, config.QID_CACHE_FILE)
            if "sitelink" in data:
                self.sitelink_cache = data["sitelink"]
                self._save_cache(self.sitelink_cache, config.SITELINK_CACHE_FILE)
            if "redirect" in data:
                self.redirect_cache = data["redirect"]
                self._save_cache(self.redirect_cache, config.REDIRECT_CACHE_FILE)
            print(f"✓ Cache import qilindi: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Cache import qilishda xato: {e}")
            return False
