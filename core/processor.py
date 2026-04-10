#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/processor.py - Wikitext tayyorlash, finalizatsiya va o'zbekcha stilga aylantitrish
"""

import re
import hashlib
from typing import Dict, Tuple

import mwparserfromhell as mwp

import config
from core.wikidata_fetcher import WikidataFetcher
from core.cache_manager import WikiCache
from utils.regex_patterns import RegexPatterns, remove_empty_params, clean_html_comments, fix_punctuation_with_refs, apply_all_fixes
from utils.logger import logger


class WikiTextProcessor:
    """Wikitext'ni tayyorlash, tarjima qilish va finalizatsiya qilish."""
    
    def __init__(self, fetcher: WikidataFetcher, cache: WikiCache):
        """
        Initialize.
        
        Args:
            fetcher: WikidataFetcher instance
            cache: WikiCache instance
        """
        self.fetcher = fetcher
        self.cache = cache
    
    # ==================== PHASE 1: PREPARE ====================
    
    def prepare(self, raw_wikitext: str) -> Tuple[str, Dict, Dict, Dict, Dict]:
        """
        Wikitext'ni tarjimaga tayyorlash (batch API bilan optimallashtirilgan).
        - Bo'sh template parametrlarni olib tashlash
        - Uzun manbalarni siqish
        - Wikilink'larni QID placeholder'lari bilan almashtirish
        - Kategoriyalarni special token'lari bilan almashtirish
        - Andozalarni placeholder'lari bilan almashtirish

        Returns:
            (prepared_text, link_map, cat_map, tpl_map, ref_map)
        """
        logger.info("📝 Wikitext tayyorlanmoqda...")

        # Kesh yozishni kechiktirish (oxirida bir marta yoziladi)
        self.cache.begin_batch()

        try:
            # 1. Bo'sh parametrlarni tozalash
            wikitext = remove_empty_params(raw_wikitext)

            # 2. Manbalarni siqish
            wikitext, ref_map = self._compress_references(wikitext)

            # 3. HTML izohlarni olib tashlash
            wikitext = clean_html_comments(wikitext)

            # Parse wikitext
            code = mwp.parse(wikitext)

            # ===== A-BOSQICH: Barcha sarlavhalarni yig'ish =====

            category_items = []   # (target, wikilink_obj, label)
            wikilink_items = []   # (target, wikilink_obj, label)
            template_items = []   # (en_tpl_title, template_obj, original_name)

            # 4. Kategoriyalarni yig'ish
            for wl in list(code.filter_wikilinks()):
                target = str(wl.title).strip()
                if target.startswith("Category:"):
                    label = str(wl.text).strip() if wl.text else target.split("Category:", 1)[-1]
                    category_items.append((target, wl, label))

            # 5. Wikilink'larni yig'ish
            for wl in code.filter_wikilinks():
                target = str(wl.title).strip()

                # Namespace'larni skip qilish
                if ":" in target and not target.startswith(":"):
                    ns = target.split(":", 1)[0].lower()
                    if ns in ("file", "image", "template", "help", "portal", "special", "module", "wikipedia", "category"):
                        continue

                # Agar QID bo'lsa, skip
                if target.startswith("Q") and target[1:].isdigit():
                    continue

                label = str(wl.text).strip() if wl.text else target
                wikilink_items.append((target, wl, label))

            # 6. Andozalarni yig'ish
            for tpl in code.filter_templates():
                original_name = str(tpl.name).strip()
                if original_name.startswith("TPL:"):
                    continue
                en_tpl_title = f"Template:{original_name}"
                template_items.append((en_tpl_title, tpl, original_name))

            # ===== B-BOSQICH: Batch hal qilish =====

            # Barcha unique sarlavhalarni yig'ish
            all_titles = set()
            for target, _, _ in category_items:
                all_titles.add(target)
            for target, _, _ in wikilink_items:
                all_titles.add(target)
            for target, _, _ in template_items:
                all_titles.add(target)

            all_titles_list = list(all_titles)

            # B1: Batch redirect hal qilish (1-2 HTTP so'rov)
            redirect_map = self.fetcher.batch_resolve_redirects(all_titles_list)

            # B2: Resolved sarlavhalar uchun QID'larni batch olish (1-2 HTTP so'rov)
            resolved_titles = list(set(redirect_map.values()))
            qid_map = self.fetcher.batch_get_qids_fast(resolved_titles)

            # ===== C-BOSQICH: Natijalarni qo'llash =====

            link_qid_map = {}
            cat_qid_map = {}
            tpl_qid_map = {}

            # Kategoriyalar
            for target, wl, label in category_items:
                resolved = redirect_map.get(target, target)
                qid = qid_map.get(resolved)
                if qid:
                    cat_qid_map[qid] = target
                    token = f"⟦CAT:{qid}|{label}⟧"
                    code.replace(wl, token)

            # Wikilink'lar
            for target, wl, label in wikilink_items:
                resolved = redirect_map.get(target, target)
                qid = qid_map.get(resolved)
                if qid:
                    link_qid_map[qid] = resolved
                    wl.title = qid
                    wl.text = label

            # Andozalar
            for en_tpl_title, tpl, original_name in template_items:
                resolved = redirect_map.get(en_tpl_title, en_tpl_title)
                qid = qid_map.get(resolved)
                if qid:
                    tpl_qid_map[qid] = original_name
                    tpl.name = f"TPL:{qid}"

            prepared_text = str(code)

            logger.success(f"Tayyorlandi: {len(link_qid_map)} havola, {len(cat_qid_map)} kategoriya, {len(tpl_qid_map)} andoza")

            return prepared_text, link_qid_map, cat_qid_map, tpl_qid_map, ref_map

        finally:
            # Kesh o'zgarishlarini diskka yozish (har doim)
            self.cache.end_batch()
    
    def _compress_references(self, wikitext: str) -> Tuple[str, Dict[str, str]]:
        """Uzun manbalarni siqish."""
        ref_pattern = re.compile(RegexPatterns.REF_TAG, re.DOTALL | re.IGNORECASE)
        ref_map = {}
        
        def replace_ref(match):
            ref_content = match.group(0)
            if len(ref_content) > config.REF_COMPRESS_THRESHOLD:
                ref_id = hashlib.md5(ref_content.encode()).hexdigest()[:8]
                placeholder = f"<ref>REF_{ref_id}</ref>"
                ref_map[ref_id] = ref_content
                return placeholder
            return ref_content
        
        compressed = ref_pattern.sub(replace_ref, wikitext)
        
        if ref_map:
            logger.info(f"✓ Manbalar siqildi: {len(ref_map)} ta")
        
        return compressed, ref_map
    
    # ==================== PHASE 3: FINALIZE ====================
    
    def finalize(self, translated_text: str, ref_map: Dict[str, str]) -> str:
        """
        Tarjima qilingan matnni finalizatsiya qilish.
        - QID placeholder'larini sitelink'lari bilan almashtirish
        - Kategoriya token'larini real kategoriyalar bilan almashtirish
        - Andoza placeholder'larini real andoza nomlari bilan almashtirish
        - Manbalarni tikish
        - O'zbek uslubiga moslashtirish
        
        Args:
            translated_text: Tarjima qilingan matn
            ref_map: Siqilgan manbalar mapping
        
        Returns:
            Finallashtirilgan matn
        """
        logger.info("🔧 Finalizatsiya qilinmoqda...")
        
        code = mwp.parse(translated_text)
        
        # 1. Wikilink'larni hal qilish
        for wl in code.filter_wikilinks():
            target = str(wl.title).strip()
            label = str(wl.text).strip() if wl.text else ""
            
            if target.startswith("Q") and target[1:].isdigit():
                uz_title = self.fetcher.get_sitelink(target, "uz")
                if uz_title:
                    wl.title = uz_title
                    if not label or label == uz_title:
                        wl.text = None
                else:
                    if label:
                        wl.title = label
                        wl.text = None
                    else:
                        wl.title = ""
                        wl.text = ""
        
        # 2. Kategoriyalarni hal qilish
        text_after_links = str(code)
        
        def cat_repl(m):
            qid = m.group(1)
            label = m.group(2).strip()
            uz_title = self.fetcher.get_sitelink(qid, "uz")
            if uz_title:
                if not uz_title.startswith(("Turkum:", "Kategoriya:")):
                    return f"[[{config.FALLBACK_CATEGORY_PREFIX}:{uz_title}]]"
                return f"[[{uz_title}]]"
            else:
                return f"[[{config.FALLBACK_CATEGORY_PREFIX}:{label}]]"
        
        text_after_cats = re.sub(RegexPatterns.CAT_TOKEN, cat_repl, text_after_links)
        
        # 3. Andozalarni hal qilish
        code2 = mwp.parse(text_after_cats)
        templates_to_remove = []
        
        for tpl in code2.filter_templates():
            name = str(tpl.name).strip()
            if name.startswith("TPL:") and name[4:].startswith("Q"):
                qid = name[4:]
                uz_title = self.fetcher.get_sitelink(qid, "uz")
                
                if uz_title:
                    if ":" in uz_title:
                        uz_tpl_name = uz_title.split(":", 1)[1].strip()
                    else:
                        uz_tpl_name = uz_title.strip()
                    tpl.name = uz_tpl_name
                else:
                    # Fallback mapping
                    en_title = self.fetcher.get_en_sitelink(qid)
                    if en_title and en_title.lower().startswith("template:"):
                        base = en_title.split(":", 1)[1].strip()
                        mapped = config.FALLBACK_TEMPLATE_MAP_EN2UZ.get(base.lower())
                        if mapped:
                            tpl.name = mapped
                        else:
                            tpl.name = base
                    else:
                        templates_to_remove.append(tpl)
        
        # Hal qilinmagan andozalarni olib tashlash
        for tpl in templates_to_remove:
            code2.remove(tpl)
        
        final_text = str(code2)
        
        # 4. Manbalarni tikish
        final_text = self._restore_references(final_text, ref_map)
        
        # 5. O'zbek stiliga moslashtirish
        final_text = fix_punctuation_with_refs(final_text)
        
        # 6. Localization qoʻllash (main.py'da qilinadi)
        
        # 7. O'zbek tili qoidalarini qoʻllash
        final_text = apply_all_fixes(final_text)
        
        logger.success("Finalizatsiya tugadi")
        
        return final_text
    
    def _restore_references(self, wikitext: str, ref_map: Dict[str, str]) -> str:
        """Siqilgan manbalarni tikish."""
        for ref_id, original_ref in ref_map.items():
            placeholder = f"<ref>REF_{ref_id}</ref>"
            wikitext = wikitext.replace(placeholder, original_ref)
        
        if ref_map:
            logger.info(f"✓ Manbalar tikaldi: {len(ref_map)} ta")
        
        return wikitext