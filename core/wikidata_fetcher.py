#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/wikidata_fetcher.py - Wikidata bilan ishlash
QID'larni topish, sitelink'larni olish, redirect'larni hal qilish.
Parallel processing bilan optimallashtirilgan.
"""

import time as time_module
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import pywikibot

import config
from core.cache_manager import WikiCache
from utils.logger import logger


class WikidataFetcher:
    """
    Wikidata va Wikipedia bilan ishlash.
    QID, sitelink, redirect'larni API'dan olish yoki cache'dan.
    """
    
    def __init__(self, cache: WikiCache):
        """
        Initialize.
        
        Args:
            cache: WikiCache instance
        """
        self.cache = cache
        self.site_en = pywikibot.Site("en", "wikipedia")
        self.site_uz = pywikibot.Site("uz", "wikipedia")
        self.site_wd = pywikibot.Site("wikidata", "wikidata")
    
    # ==================== REDIRECT RESOLUTION ====================
    
    def resolve_redirect(self, title: str, site_code: str = "en") -> str:
        """
        Redirect'ni hal qilish. Agar CR7 → Cristiano Ronaldo bo'lsa,
        Cristiano Ronaldo'ni qaytarish.
        
        Args:
            title: Maqola sarlavhasi
            site_code: Sayt kodi (en, uz)
        
        Returns:
            Haqiqiy sarlavha
        """
        # Cache'dan tekshirish
        cached = self.cache.get_redirect(site_code, title)
        if cached is not None:
            return cached
        
        try:
            site = self.site_en if site_code == "en" else self.site_uz
            page = pywikibot.Page(site, title)
            
            if page.isRedirectPage():
                target = page.getRedirectTarget()
                result = target.title()
            else:
                result = title
            
            self.cache.set_redirect(site_code, title, result)
            return result
        
        except Exception as e:
            logger.debug(f"Redirect hal qilishda xato: {title} - {e}")
            self.cache.set_redirect(site_code, title, title)
            return title
    
    # ==================== QID FETCHING ====================
    
    def get_qid(self, title: str, site_code: str = "en") -> Optional[str]:
        """
        Wikipedia maqolasining QID'sini olish.
        
        Args:
            title: Maqola sarlavhasi
            site_code: Sayt kodi (en, uz)
        
        Returns:
            QID (Q12345) yoki None
        """
        # Cache'dan tekshirish
        cached = self.cache.get_qid(site_code, title)
        if cached is not None:
            return cached
        
        try:
            # Redirect'ni hal qilish
            actual_title = self.resolve_redirect(title, site_code)
            
            # Maqolani olish
            site = self.site_en if site_code == "en" else self.site_uz
            page = pywikibot.Page(site, actual_title)
            
            if not page.exists():
                self.cache.set_qid(site_code, title, None)
                return None
            
            # ItemPage'dan QID olish
            item = pywikibot.ItemPage.fromPage(page)
            item.get()
            qid = item.id
            
            self.cache.set_qid(site_code, title, qid)
            return qid
        
        except Exception as e:
            logger.debug(f"QID olishda xato: {title} - {e}")
            self.cache.set_qid(site_code, title, None)
            return None
    
    # ==================== SITELINK FETCHING ====================
    
    def get_sitelink(self, qid: str, target_lang: str = "uz") -> Optional[str]:
        """
        QID'dan sitelink'ni olish.
        Masalan: Q12345 → "Abdulloh Marufiy" (o'zbek'da)
        
        Args:
            qid: Wikidata QID (Q12345)
            target_lang: Maqsad til (uz, en, ru)
        
        Returns:
            Maqola sarlavhasi yoki None
        """
        target_site = f"{target_lang}wiki"
        
        # Cache'dan tekshirish
        cached = self.cache.get_sitelink(qid, target_site)
        if cached is not None:
            return cached
        
        try:
            item = pywikibot.ItemPage(self.site_wd, qid)
            item.get()
            
            sitelinks = item.sitelinks
            if target_site in sitelinks:
                title = sitelinks[target_site].title
                self.cache.set_sitelink(qid, target_site, title)
                return title
            
            self.cache.set_sitelink(qid, target_site, None)
            return None
        
        except Exception as e:
            logger.debug(f"Sitelink olishda xato: {qid} - {e}")
            self.cache.set_sitelink(qid, target_site, None)
            return None
    
    # ==================== BATCH OPERATIONS ====================
    
    def batch_get_qids(self, titles: List[str], site_code: str = "en") -> Dict[str, Optional[str]]:
        """
        Ko'plab maqolalarning QID'larini parallel olish.
        
        Args:
            titles: Maqola sarlavhalari ro'yxati
            site_code: Sayt kodi
        
        Returns:
            {title: QID} dict
        """
        if not titles:
            return {}
        
        results = {}
        
        def get_with_delay(title):
            """Delay bilan QID olish (rate limiting)."""
            time_module.sleep(config.REQUEST_DELAY)
            return self.get_qid(title, site_code)
        
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            future_to_title = {
                executor.submit(get_with_delay, title): title
                for title in titles
            }
            
            for future in as_completed(future_to_title):
                title = future_to_title[future]
                try:
                    qid = future.result()
                    results[title] = qid
                except Exception as e:
                    logger.debug(f"Batch QID xatosi: {title} - {e}")
                    results[title] = None
        
        return results
    
    def batch_get_sitelinks(self, qids: List[str], target_lang: str = "uz") -> Dict[str, Optional[str]]:
        """
        Ko'plab QID'larning sitelink'larini parallel olish.
        
        Args:
            qids: QID ro'yxati
            target_lang: Maqsad til
        
        Returns:
            {QID: sitelink} dict
        """
        if not qids:
            return {}
        
        results = {}
        
        def get_with_delay(qid):
            """Delay bilan sitelink olish."""
            time_module.sleep(config.REQUEST_DELAY)
            return self.get_sitelink(qid, target_lang)
        
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            future_to_qid = {
                executor.submit(get_with_delay, qid): qid
                for qid in qids
            }
            
            for future in as_completed(future_to_qid):
                qid = future_to_qid[future]
                try:
                    sitelink = future.result()
                    results[qid] = sitelink
                except Exception as e:
                    logger.debug(f"Batch sitelink xatosi: {qid} - {e}")
                    results[qid] = None
        
        return results
    
    # ==================== UTILITY METHODS ====================
    
    def get_en_sitelink(self, qid: str) -> Optional[str]:
        """QID'dan inglizcha sitelink olish."""
        return self.get_sitelink(qid, "en")
    
    def is_valid_qid(self, qid: str) -> bool:
        """QID formatining to'g'ri bo'lganini tekshirish."""
        import re
        return bool(re.match(r'^Q\d+$', qid))
    
    def test_connection(self) -> bool:
        """Wikidata'ga ulanish tekshirish."""
        try:
            item = pywikibot.ItemPage(self.site_wd, "Q1")
            item.get()
            logger.success("Wikidata'ga ulanish muvaffaqiyatli")
            return True
        except Exception as e:
            logger.fail(f"Wikidata'ga ulanishda xato: {e}")
            return False