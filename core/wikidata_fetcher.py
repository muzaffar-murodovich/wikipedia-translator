#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/wikidata_fetcher.py - Wikidata integration
Fetch QIDs, get sitelinks, resolve redirects.
Optimized with batch processing.
"""

import re
import time
from typing import Optional, Dict, List

import pywikibot

import config
from core.cache_manager import WikiCache
from utils.api_client import wiki_api
from utils.logger import logger


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

        # Titles whose last batch lookup failed because of an API error.
        # These are NOT "not found" — callers must not report them as missing.
        self.failed_titles: set = set()

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
            # API xatosi — cache'ga NONE yozmaymiz (bu "mavjud emas" degani emas).
            logger.error(f"Sitelink olishda xato: {qid} - {e}")
            return None

    def _wiki_api(self, params: dict, lang: str = "en", domain: str = "wikipedia") -> dict:
        """
        Send a request to the Wikipedia/Wikidata API.

        Delegates to utils.api_client, which handles HTTP 429 rate limiting
        and transient errors. Raises on failure — callers must not record a
        failed request as "not found".
        """
        return wiki_api(params, lang=lang, domain=domain)

    def batch_page_info(
        self, titles: List[str], site_code: str = "en"
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Resolve redirects, QIDs and target-language titles in ONE request per batch.

        Uses the source Wikipedia API (not wikidata.org):
            action=query&redirects=1&prop=pageprops|langlinks

        This replaces the old two-step flow (batch_resolve_redirects +
        batch_get_qids_fast), halving the number of HTTP requests and
        keeping all traffic on one host — which is what caused the
        HTTP 429 rate limiting.

        Args:
            titles: Article titles (redirects allowed)
            site_code: Source site code (en, uz)

        Returns:
            {original_title: {"resolved": str, "qid": Optional[str],
                              "uz_title": Optional[str]}}
        """
        target_site = f"{config.TARGET_LANG}wiki"
        results: Dict[str, Dict[str, Optional[str]]] = {}
        uncached: List[str] = []

        # Fully cached only if we know the redirect AND the QID of its target.
        for title in titles:
            resolved = self.cache.get_redirect(site_code, title)
            if resolved is None:
                uncached.append(title)
                continue
            qid_key = f"{site_code}:{resolved}"
            if qid_key not in self.cache.qid_cache:
                uncached.append(title)
                continue
            qid = self.cache.get_qid(site_code, resolved)
            results[title] = {
                "resolved": resolved,
                "qid": qid,
                "uz_title": self.cache.get_sitelink(qid, target_site) if qid else None,
            }

        for i in range(0, len(uncached), config.API_BATCH_SIZE):
            batch = uncached[i:i + config.API_BATCH_SIZE]
            if i:
                time.sleep(config.API_BATCH_DELAY)
            try:
                data = self._wiki_api({
                    "action": "query",
                    "titles": "|".join(batch),
                    "redirects": "1",
                    "prop": "pageprops|langlinks",
                    "ppprop": "wikibase_item",
                    "lllang": config.TARGET_LANG,
                    "lllimit": "max",
                }, lang=site_code)

                query = data.get("query", {})
                normalized_map = {n["from"]: n["to"] for n in query.get("normalized", [])}
                redirect_map = {r["from"]: r["to"] for r in query.get("redirects", [])}

                page_info = {}
                for pg in query.get("pages", []):
                    qid = pg.get("pageprops", {}).get("wikibase_item")
                    langlinks = pg.get("langlinks", [])
                    page_info[pg["title"]] = (
                        qid,
                        langlinks[0]["title"] if langlinks else None,
                    )

                for title in batch:
                    lookup = normalized_map.get(title, title)
                    resolved = redirect_map.get(lookup, lookup)
                    qid, uz_title = page_info.get(resolved, (None, None))

                    results[title] = {
                        "resolved": resolved,
                        "qid": qid,
                        "uz_title": uz_title,
                    }

                    self.cache.set_redirect(site_code, title, resolved)
                    self.cache.set_qid(site_code, resolved, qid)
                    if qid:
                        # Bonus for Phase 3: target and source sitelinks.
                        self.cache.set_sitelink(qid, target_site, uz_title)
                        self.cache.set_sitelink(qid, f"{site_code}wiki", resolved)
                    self.failed_titles.discard(title)

            except Exception as e:
                # API xatosi — "topilmadi" degani emas. Cache'ga yozmaymiz,
                # aks holda xato javob butun run davomida saqlanib qoladi.
                logger.error(f"Batch sahifa ma'lumoti xatosi ({len(batch)} ta sarlavha): {e}")
                for title in batch:
                    results[title] = {"resolved": title, "qid": None, "uz_title": None}
                    self.failed_titles.add(title)

        return results

    def batch_resolve_redirects(self, titles: List[str], site_code: str = "en") -> Dict[str, str]:
        """
        Batch resolve redirects. Thin wrapper over batch_page_info().

        Args:
            titles: List of article titles
            site_code: Site code (en, uz)

        Returns:
            {original_title: resolved_title} dict
        """
        info = self.batch_page_info(titles, site_code)
        return {title: data["resolved"] for title, data in info.items()}

    def batch_get_qids_fast(self, titles: List[str], site_code: str = "en") -> Dict[str, Optional[str]]:
        """
        Batch fetch QIDs. Thin wrapper over batch_page_info().

        Target-language sitelinks are cached as a side effect (for Phase 3),
        so a following batch_resolve_redirects()/get_sitelink() call is free.

        Args:
            titles: Article titles
            site_code: Site code

        Returns:
            {title: QID} dict (QID or None)
        """
        info = self.batch_page_info(titles, site_code)
        return {title: data["qid"] for title, data in info.items()}

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
