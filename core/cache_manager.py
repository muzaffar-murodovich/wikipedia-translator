#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/cache_manager.py - Cache tizimi
QID, sitelink, va redirect'larni cache qilish.
Bir marta API'dan so'rangan ma'lumot JSON'da saqlanadi.
"""

import json
from pathlib import Path
from typing import Optional, Dict
import config
from utils.file_handler import FileHandler


class WikiCache:
    """
    Wikidata so'rovlarining kesh tizimi.
    3 turli cache: QID, Sitelink, Redirect
    """
    
    def __init__(self):
        """Cache manager'ni initialize qilish."""
        self.qid_cache = FileHandler.read_json(str(config.QID_CACHE_FILE))
        self.sitelink_cache = FileHandler.read_json(str(config.SITELINK_CACHE_FILE))
        self.redirect_cache = FileHandler.read_json(str(config.REDIRECT_CACHE_FILE))
        
        # Statistika
        self.stats = {
            "qid_hits": 0,
            "qid_misses": 0,
            "sitelink_hits": 0,
            "sitelink_misses": 0,
            "redirect_hits": 0,
            "redirect_misses": 0,
        }
    
    # ==================== QID CACHE ====================
    
    def get_qid(self, site_code: str, title: str) -> Optional[str]:
        """
        QID'ni cache'dan olish.
        
        Args:
            site_code: Sayt kodi (en, uz, ru)
            title: Maqola sarlavhasi
        
        Returns:
            QID (Q12345) yoki None agar topilmasa
        """
        key = f"{site_code}:{title}"
        
        if key in self.qid_cache:
            cached_value = self.qid_cache[key]
            # "NONE" string'i - mavjud emas
            if cached_value == "NONE":
                self.stats["qid_hits"] += 1
                return None
            self.stats["qid_hits"] += 1
            return cached_value
        
        self.stats["qid_misses"] += 1
        return None
    
    def set_qid(self, site_code: str, title: str, qid: Optional[str]):
        """
        QID'ni cache'ga saqlash.
        
        Args:
            site_code: Sayt kodi
            title: Maqola sarlavhasi
            qid: QID yoki None (None bo'lsa "NONE" saqlanadi)
        """
        key = f"{site_code}:{title}"
        self.qid_cache[key] = qid if qid else "NONE"
        self._save_cache(self.qid_cache, config.QID_CACHE_FILE)
    
    # ==================== SITELINK CACHE ====================
    
    def get_sitelink(self, qid: str, target_site: str = "uzwiki") -> Optional[str]:
        """
        Sitelink'ni cache'dan olish.
        
        Args:
            qid: Wikidata QID (Q12345)
            target_site: Maqsad sayt (uzwiki, enwiki, ru wiki)
        
        Returns:
            Sitelink (maqola sarlavhasi) yoki None
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
        Sitelink'ni cache'ga saqlash.
        
        Args:
            qid: Wikidata QID
            target_site: Maqsad sayt
            title: Sarlavha yoki None
        """
        key = f"{qid}:{target_site}"
        self.sitelink_cache[key] = title if title else "NONE"
        self._save_cache(self.sitelink_cache, config.SITELINK_CACHE_FILE)
    
    # ==================== REDIRECT CACHE ====================
    
    def get_redirect(self, site_code: str, title: str) -> Optional[str]:
        """
        Redirect'ni cache'dan olish.
        
        Args:
            site_code: Sayt kodi
            title: Maqola sarlavhasi (redirect bo'lishi mumkin)
        
        Returns:
            Haqiqiy sarlavha yoki None
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
        Redirect'ni cache'ga saqlash.
        
        Args:
            site_code: Sayt kodi
            title: Asl sarlavha
            target: Maqsad sarlavha
        """
        key = f"{site_code}:{title}"
        self.redirect_cache[key] = target if target else "NONE"
        self._save_cache(self.redirect_cache, config.REDIRECT_CACHE_FILE)
    
    # ==================== UTILITY METODLARI ====================
    
    def _save_cache(self, data: dict, filepath: Path):
        """Cache'ni JSON'ga saqlash."""
        FileHandler.write_json(str(filepath), data)
    
    def clear_cache(self, cache_type: str = "all"):
        """
        Cache'ni tozalash.
        
        Args:
            cache_type: "qid", "sitelink", "redirect" yoki "all"
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
        """Cache hajmini olish."""
        return {
            "qid": len(self.qid_cache),
            "sitelink": len(self.sitelink_cache),
            "redirect": len(self.redirect_cache),
            "total": len(self.qid_cache) + len(self.sitelink_cache) + len(self.redirect_cache)
        }
    
    def print_stats(self):
        """Cache statistikasini chiqarish."""
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
        Cache'ni eksport qilish (backup uchun).
        
        Args:
            filepath: Eksport fayl yo'li
        
        Returns:
            Muvaffaqiyat bo'lsa True
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
        Cache'ni import qilish (backup'dan).
        
        Args:
            filepath: Import fayl yo'li
        
        Returns:
            Muvaffaqiyat bo'lsa True
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