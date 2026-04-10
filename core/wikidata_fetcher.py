#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/wikidata_fetcher.py - Wikidata integration
Fetch QIDs, get sitelinks, resolve redirects.
Optimized with batch processing.
"""

import re
import json
import urllib.parse
import urllib.request
from typing import Optional, Dict, List

import pywikibot

import config
from core.cache_manager import WikiCache
from utils.logger import logger

_USER_AGENT = "WikiTranslatorBot/1.0 (Uzbek Wikipedia; uz.wikipedia.org)"


class WikidataFetcher:
    """
    Wikidata and Wikipedia API integration.
    Fetches QIDs, sitelinks, and redirects from API or cache.
    """

    def __init__(self, cache: WikiCache):
        """
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

    def resolve_redirect(self, title: str, site_code: str = "en") -> str:
        """
        Resolve a redirect to its target article.
        E.g. CR7 -> Cristiano Ronaldo.

        Args:
            title: Article title
            site_code: Site code (en, uz)

        Returns:
            Actual (resolved) title
        """
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

    def get_qid(self, title: str, site_code: str = "en") -> Optional[str]:
        """
        Get the QID for a Wikipedia article.

        Args:
            title: Article title
            site_code: Site code (en, uz)

        Returns:
            QID (Q12345) or None
        """
        cached = self.cache.get_qid(site_code, title)
        if cached is not None:
            return cached

        try:
            actual_title = self.resolve_redirect(title, site_code)

            site = self.site_en if site_code == "en" else self.site_uz
            page = pywikibot.Page(site, actual_title)

            if not page.exists():
                self.cache.set_qid(site_code, title, None)
                return None

            item = pywikibot.ItemPage.fromPage(page)
            item.get()
            qid = item.id

            self.cache.set_qid(site_code, title, qid)
            return qid

        except Exception as e:
            logger.debug(f"QID olishda xato: {title} - {e}")
            self.cache.set_qid(site_code, title, None)
            return None

    def get_sitelink(self, qid: str, target_lang: str = "uz") -> Optional[str]:
        """
        Get sitelink from a QID.
        E.g. Q12345 -> "Abdulloh Marufiy" (in Uzbek).

        Args:
            qid: Wikidata QID (Q12345)
            target_lang: Target language (uz, en, ru)

        Returns:
            Article title or None
        """
        target_site = f"{target_lang}wiki"

        # Check cache via raw dict to correctly detect "NONE" sentinel entries.
        cache_key = f"{qid}:{target_site}"
        if cache_key in self.cache.sitelink_cache:
            return self.cache.get_sitelink(qid, target_site)

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

    def _wiki_api(self, params: dict, lang: str = "en", domain: str = "wikipedia") -> dict:
        """Direct HTTP request to Wikipedia/Wikidata API."""
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
        Batch resolve redirects using Wikipedia API.
        Uses action=query&redirects with 50 titles/request.

        Args:
            titles: List of article titles
            site_code: Site code (en, uz)

        Returns:
            {original_title: resolved_title} dict
        """
        results = {}
        uncached = []

        for title in titles:
            cached = self.cache.get_redirect(site_code, title)
            if cached is not None:
                results[title] = cached
            else:
                uncached.append(title)

        for i in range(0, len(uncached), 50):
            batch = uncached[i:i + 50]
            joined = "|".join(batch)
            try:
                data = self._wiki_api({
                    "action": "query",
                    "titles": joined,
                    "redirects": "1",
                }, lang=site_code)

                redirect_map = {}
                for r in data.get("query", {}).get("redirects", []):
                    redirect_map[r["from"]] = r["to"]

                # Normalized mapping (e.g. "abu_bakr" -> "Abu Bakr")
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
        Batch fetch QIDs and sitelinks using Wikidata API.
        Uses wbgetentities with 50 titles/request.
        Bonus: uz/en sitelinks are also cached (for Phase 3).

        Args:
            titles: Article titles (redirects already resolved)
            site_code: Site code

        Returns:
            {title: QID} dict (QID or None)
        """
        results = {}
        uncached = []

        for title in titles:
            cached = self.cache.get_qid(site_code, title)
            if cached is not None:
                results[title] = cached
            else:
                uncached.append(title)

        if not uncached:
            return results

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

                title_to_qid = {}
                for entity_id, entity in data.get("entities", {}).items():
                    if entity_id.startswith("-"):
                        continue
                    sitelinks = entity.get("sitelinks", {})

                    # Map from source wiki title
                    src_link = sitelinks.get(site_db, {})
                    src_title = src_link.get("title", "")
                    title_to_qid[src_title] = entity_id

                    # Cache uz sitelink (for Phase 3)
                    uz_link = sitelinks.get("uzwiki", {})
                    uz_title = uz_link.get("title") if uz_link else None
                    self.cache.set_sitelink(entity_id, "uzwiki", uz_title)

                    # Cache en sitelink (for fallback)
                    if src_title:
                        self.cache.set_sitelink(entity_id, f"{site_code}wiki", src_title)

                for title in batch:
                    qid = title_to_qid.get(title)
                    if not qid:
                        # Try normalization match
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

    def get_en_sitelink(self, qid: str) -> Optional[str]:
        """Get English sitelink from QID."""
        return self.get_sitelink(qid, "en")

    def is_valid_qid(self, qid: str) -> bool:
        """Check if QID format is valid."""
        return bool(re.match(r'^Q\d+$', qid))

    def test_connection(self) -> bool:
        """Test connection to Wikidata."""
        try:
            item = pywikibot.ItemPage(self.site_wd, "Q1")
            item.get()
            logger.success("Wikidata'ga ulanish muvaffaqiyatli")
            return True
        except Exception as e:
            logger.fail(f"Wikidata'ga ulanishda xato: {e}")
            return False
