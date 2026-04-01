#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/wikidata_fetcher.py - Wikidata bilan ishlash
QID'larni topish, sitelink'larni olish, redirect'larni hal qilish.
Parallel processing bilan optimallashtirilgan.
"""

import json
import time as time_module
import urllib.parse
import urllib.request
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import pywikibot

import config
from core.cache_manager import WikiCache
from utils.logger import logger

_USER_AGENT = "WikiTranslatorBot/1.0 (Uzbek Wikipedia; uz.wikipedia.org)"


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
        self._site_en = None
        self._site_uz = None
        self._site_wd = None

    @property
    def site_en(self):
        """Lazy: en.wikipedia pywikibot Site."""
        if self._site_en is None:
            self._site_en = pywikibot.Site("en", "wikipedia")
        return self._site_en

    @property
    def site_uz(self):
        """Lazy: uz.wikipedia pywikibot Site."""
        if self._site_uz is None:
            self._site_uz = pywikibot.Site("uz", "wikipedia")
        return self._site_uz

    @property
    def site_wd(self):
        """Lazy: Wikidata pywikibot Site."""
        if self._site_wd is None:
            self._site_wd = pywikibot.Site("wikidata", "wikidata")
        return self._site_wd
    
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

        # Cache'dan tekshirish: raw dict orqali — "NONE" sentinel'ni ham topadi.
        # cache.get_sitelink() "NONE" va "yo'q" uchun ikkalasi ham None qaytaradi,
        # shuning uchun dict'ni to'g'ridan-to'g'ri tekshiramiz.
        cache_key = f"{qid}:{target_site}"
        if cache_key in self.cache.sitelink_cache:
            return self.cache.get_sitelink(qid, target_site)

        # Direct HTTP API (pywikibot ishlatilmaydi)
        try:
            data = self._wiki_api({
                "action": "wbgetentities",
                "ids": qid,
                "props": "sitelinks",
                "sitefilter": target_site,
            }, domain="wikidata")

            entity = data.get("entities", {}).get(qid, {})
            sitelinks = entity.get("sitelinks", {})

            if target_site in sitelinks:
                title = sitelinks[target_site]["title"]
                self.cache.set_sitelink(qid, target_site, title)
                return title

            self.cache.set_sitelink(qid, target_site, None)
            return None

        except Exception as e:
            logger.debug(f"Sitelink olishda xato: {qid} - {e}")
            self.cache.set_sitelink(qid, target_site, None)
            return None
    
    # ==================== FAST BATCH OPERATIONS ====================

    def _wiki_api(self, params: dict, lang: str = "en", domain: str = "wikipedia") -> dict:
        """Wikipedia/Wikidata API ga to'g'ridan-to'g'ri HTTP so'rov."""
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        encoded = urllib.parse.urlencode(params)
        if domain == "wikidata":
            url = f"https://www.wikidata.org/w/api.php?{encoded}"
        else:
            url = f"https://{lang}.wikipedia.org/w/api.php?{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def batch_resolve_redirects(self, titles: List[str], site_code: str = "en") -> Dict[str, str]:
        """
        Ko'plab sarlavhalarning redirect'larini batch API bilan hal qilish.
        Wikipedia action=query&redirects bilan 50 ta/so'rov.

        Args:
            titles: Sarlavhalar ro'yxati
            site_code: Sayt kodi (en, uz)
        Returns:
            {original_title: resolved_title} dict
        """
        results = {}
        uncached = []

        # Cache'dan tekshirish
        for title in titles:
            cached = self.cache.get_redirect(site_code, title)
            if cached is not None:
                results[title] = cached
            else:
                uncached.append(title)

        # Uncached sarlavhalarni batch API bilan hal qilish
        for i in range(0, len(uncached), 50):
            batch = uncached[i:i + 50]
            joined = "|".join(batch)
            try:
                data = self._wiki_api({
                    "action": "query",
                    "titles": joined,
                    "redirects": "1",
                }, lang=site_code)

                # Redirect mapping
                redirect_map = {}
                for r in data.get("query", {}).get("redirects", []):
                    redirect_map[r["from"]] = r["to"]

                # Normalized mapping (masalan, "abu_bakr" → "Abu Bakr")
                normalized_map = {}
                for n in data.get("query", {}).get("normalized", []):
                    normalized_map[n["from"]] = n["to"]

                for title in batch:
                    lookup = normalized_map.get(title, title)
                    resolved = redirect_map.get(lookup, lookup)
                    results[title] = resolved
                    self.cache.set_redirect(site_code, title, resolved)

            except Exception as e:
                logger.debug(f"Batch redirect xatosi: {e}")
                for title in batch:
                    results[title] = title
                    self.cache.set_redirect(site_code, title, title)

        return results

    def batch_get_qids_fast(self, titles: List[str], site_code: str = "en") -> Dict[str, Optional[str]]:
        """
        Ko'plab maqolalarning QID va sitelink'larini batch API bilan olish.
        Wikidata wbgetentities API bilan 50 ta/so'rov.
        Bonus: uz/en sitelink'lar ham cache'ga tushadi (Phase 3 uchun).

        Args:
            titles: Maqola sarlavhalari (redirect hal qilingan)
            site_code: Sayt kodi
        Returns:
            {title: QID} dict (QID yoki None)
        """
        results = {}
        uncached = []

        # Cache'dan tekshirish
        for title in titles:
            cached = self.cache.get_qid(site_code, title)
            if cached is not None:
                results[title] = cached
            else:
                uncached.append(title)

        if not uncached:
            return results

        # Batch API bilan QID olish
        site_db = f"{site_code}wiki"
        for i in range(0, len(uncached), 50):
            batch = uncached[i:i + 50]
            joined = "|".join(batch)
            try:
                data = self._wiki_api({
                    "action": "wbgetentities",
                    "sites": site_db,
                    "titles": joined,
                    "props": "sitelinks",
                }, domain="wikidata")

                # Title → QID mapping yaratish
                title_to_qid = {}
                for entity_id, entity in data.get("entities", {}).items():
                    if entity_id.startswith("-"):
                        continue
                    sitelinks = entity.get("sitelinks", {})

                    # Source wiki title'dan mapping
                    src_link = sitelinks.get(site_db, {})
                    src_title = src_link.get("title", "")
                    title_to_qid[src_title] = entity_id

                    # Uz sitelink'ni cache'ga saqlash (Phase 3 uchun)
                    uz_link = sitelinks.get("uzwiki", {})
                    uz_title = uz_link.get("title") if uz_link else None
                    self.cache.set_sitelink(entity_id, "uzwiki", uz_title)

                    # En sitelink'ni ham saqlash (fallback uchun)
                    if src_title:
                        self.cache.set_sitelink(entity_id, f"{site_code}wiki", src_title)

                for title in batch:
                    qid = title_to_qid.get(title)
                    if not qid:
                        # Normalization bilan tekshirish
                        for src_t, q in title_to_qid.items():
                            if src_t.replace(" ", "_") == title.replace(" ", "_"):
                                qid = q
                                break
                    results[title] = qid
                    self.cache.set_qid(site_code, title, qid)

            except Exception as e:
                logger.debug(f"Batch QID xatosi: {e}")
                for title in batch:
                    results[title] = None
                    self.cache.set_qid(site_code, title, None)

        return results

    # ==================== LEGACY BATCH OPERATIONS ====================
    
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