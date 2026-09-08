#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/processor.py - Wikitext preparation, finalization, and Uzbek-style conversion
"""

import re
import hashlib
from typing import Dict, List, Tuple

import mwparserfromhell as mwp

import config
from core.wikidata_fetcher import WikidataFetcher
from utils.regex_patterns import RegexPatterns, remove_empty_params, clean_html_comments, apply_all_fixes
from utils.logger import logger


class WikiTextProcessor:
    """Wikitext preparation, translation support, and finalization."""

    def __init__(self, fetcher: WikidataFetcher):
        """
        Args:
            fetcher: WikidataFetcher instance
        """
        self.fetcher = fetcher
        # Wikilink targets with no uz.wiki article: prepare() leaves them in
        # English for the model to translate, finalize() checks it actually did.
        self.unresolved_links: List[str] = []

    @staticmethod
    def _remove_templates(code, templates: List) -> int:
        """
        Remove templates from a parsed wikitext node list.

        A template nested inside another template that was already removed
        is no longer part of the tree, and mwparserfromhell raises
        ValueError for it. That is the desired end state — it is already
        gone — so it is skipped rather than crashing the pipeline.

        Returns:
            Number of templates actually removed
        """
        removed = 0
        for tpl in templates:
            try:
                code.remove(tpl)
                removed += 1
            except ValueError:
                # Already removed together with its parent template.
                continue
        return removed

    def prepare(self, raw_wikitext: str) -> Tuple[str, Dict, Dict, Dict, Dict]:
        """
        Prepare wikitext for translation (optimized with batch API).
        - Remove empty template parameters
        - Compress long references
        - Replace wikilinks with QID placeholders
        - Replace categories with special tokens
        - Replace templates with placeholders

        Returns:
            (prepared_text, link_map, cat_map, tpl_map, ref_map)
        """
        logger.info("📝 Wikitext tayyorlanmoqda...")

        # 1. Remove empty parameters
        wikitext = remove_empty_params(raw_wikitext)

        # 2. Compress references
        wikitext, ref_map = self._compress_references(wikitext)

        # 3. Remove HTML comments
        wikitext = clean_html_comments(wikitext)

        # Parse wikitext
        code = mwp.parse(wikitext)

        # ===== Phase A: Collect all titles =====

        category_items = []   # (target, wikilink_obj, label)
        wikilink_items = []   # (target, wikilink_obj, label)
        template_items = []   # (en_tpl_title, template_obj, original_name)

        # 4. Collect categories
        for wl in list(code.filter_wikilinks()):
            target = str(wl.title).strip()
            if target.startswith("Category:"):
                sort_key = str(wl.text).strip() if wl.text else ""
                category_items.append((target, wl, sort_key))

        # 5. Collect wikilinks
        for wl in code.filter_wikilinks():
            target = str(wl.title).strip()

            # Skip namespaces
            if ":" in target and not target.startswith(":"):
                ns = target.split(":", 1)[0].lower()
                if ns in ("file", "image", "template", "help", "portal", "special", "module", "wikipedia", "category"):
                    continue

            # Skip if already a QID
            if target.startswith("Q") and target[1:].isdigit():
                continue

            label = str(wl.text).strip() if wl.text else target
            wikilink_items.append((target, wl, label))

        # 6. Collect templates
        for tpl in code.filter_templates():
            original_name = str(tpl.name).strip()
            if original_name.startswith("TPL:"):
                continue
            en_tpl_title = f"Template:{original_name}"
            template_items.append((en_tpl_title, tpl, original_name))

        # ===== Phase B: Batch resolution =====

        # Collect all unique titles
        all_titles = set()
        for target, _, _ in category_items:
            all_titles.add(target)
        for target, _, _ in wikilink_items:
            all_titles.add(target)
        for target, _, _ in template_items:
            all_titles.add(target)

        all_titles_list = list(all_titles)

        # B1: Redirects + QIDs + uz sitelinks in one pass (1 request per 50 titles)
        page_info = self.fetcher.batch_page_info(all_titles_list)
        redirect_map = {t: d["resolved"] for t, d in page_info.items()}
        qid_map = {d["resolved"]: d["qid"] for d in page_info.values()}

        # ===== Phase C: Apply results =====

        link_qid_map = {}
        cat_qid_map = {}
        tpl_qid_map = {}

        # Categories
        for target, wl, sort_key in category_items:
            resolved = redirect_map.get(target, target)
            qid = qid_map.get(resolved)
            cat_name = target.split("Category:", 1)[-1]
            if qid:
                cat_qid_map[qid] = target
                token = f"⟦CAT:{qid}|{cat_name}|{sort_key}⟧"
                code.replace(wl, token)

        # Wikilinks
        unresolved_links = []
        for target, wl, label in wikilink_items:
            resolved = redirect_map.get(target, target)
            qid = qid_map.get(resolved)
            
            # Check uz sitelink BEFORE replacing with QID
            if qid:
                uz_title = self.fetcher.get_sitelink(qid, "uz")
                if uz_title:
                    # uz.wiki'da maqola bor — QID bilan almashtiramiz
                    link_qid_map[qid] = resolved
                    wl.title = qid
                    wl.text = label
                else:
                    # uz.wiki'da yoʻq — wikilinkga tegmaymiz, AI tarjima qilsin
                    unresolved_links.append(target)
            else:
                # QID umuman topilmadi
                unresolved_links.append(target)

        # Deduplicate, keep document order — the list goes into the prompt.
        self.unresolved_links = list(dict.fromkeys(unresolved_links))

        if unresolved_links:
            logger.info(f"  ℹ️  {len(self.unresolved_links)} havola uz.wiki'da yoʻq — AI tarjima qiladi")

        # Templates
        unresolved_templates = []
        for en_tpl_title, tpl, original_name in template_items:
            resolved = redirect_map.get(en_tpl_title, en_tpl_title)
            qid = qid_map.get(resolved)
            if qid:
                tpl_qid_map[qid] = original_name
                tpl.name = f"TPL:{qid}"
            else:
                # No QID — try fallback map, else mark for removal
                mapped = config.FALLBACK_TEMPLATE_MAP_EN2UZ.get(original_name.lower())
                if mapped:
                    tpl.name = mapped
                else:
                    unresolved_templates.append(tpl)

        # Remove unresolved templates (no QID, no fallback mapping)
        removed = self._remove_templates(code, unresolved_templates)

        if removed:
            logger.info(f"✓ Hal qilinmagan andozalar oʻchirildi: {removed} ta")

        prepared_text = str(code)

        logger.success(f"Tayyorlandi: {len(link_qid_map)} havola, {len(cat_qid_map)} kategoriya, {len(tpl_qid_map)} andoza")

        return prepared_text, link_qid_map, cat_qid_map, tpl_qid_map, ref_map

    def _compress_references(self, wikitext: str) -> Tuple[str, Dict[str, str]]:
        """Compress long references."""
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

    def finalize(self, translated_text: str, ref_map: Dict[str, str]) -> str:
        """
        Finalize translated text.
        - Resolve QID placeholders to sitelinks
        - Resolve category tokens to real categories
        - Resolve template placeholders to real template names
        - Restore compressed references
        - Apply Uzbek style fixes

        Args:
            translated_text: Translated text
            ref_map: Compressed references mapping

        Returns:
            Finalized text
        """
        logger.info("🔧 Finalizatsiya qilinmoqda...")

        code = mwp.parse(translated_text)
        unresolved = set(self.unresolved_links)
        recovered = []     # (english target, uzbek label) — target taken from label
        still_english = [] # targets the model left untouched and unlabelled

        # 1. Resolve wikilinks
        for wl in code.filter_wikilinks():
            target = str(wl.title).strip()
            label = str(wl.text).strip() if wl.text else ""

            if target.startswith("Q") and target[1:].isdigit():
                uz_title = self.fetcher.get_sitelink(target, "uz")
                if uz_title:
                    wl.title = uz_title
                    if not label or label == uz_title:
                        wl.text = None
                # No `else` needed — Phase 1 garantees uz_title exists for QID-prefixed links
            elif target in unresolved:
                # The model was told by name to translate this target and did
                # not: it matches the English string prepare() handed over.
                # A translated label is the one Uzbek name available, and
                # translation_rules.md rule 2 wants label and page name to
                # agree anyway, so the label becomes the page name.
                if label and label != target:
                    wl.title = label
                    wl.text = None
                    recovered.append((target, label))
                else:
                    still_english.append(target)

        if recovered:
            logger.warning(f"{len(recovered)} havola target'i inglizcha qolgan — label'dan olindi:")
            for en_target, uz_label in recovered:
                logger.warning(f"    [[{en_target}]] → [[{uz_label}]]")

        if still_english:
            logger.warning(
                f"{len(still_english)} havola inglizcha qoldi (label yoʻq, qoʻlda tekshiring): "
                + ", ".join(f"[[{t}]]" for t in still_english)
            )

        # 2. Resolve categories
        text_after_links = str(code)

        def cat_repl(m):
            qid = m.group(1)
            cat_name = m.group(2).strip()
            sort_key = m.group(3).strip()
            suffix = f"|{sort_key}" if sort_key else ""
            uz_title = self.fetcher.get_sitelink(qid, "uz")
            if uz_title:
                if not uz_title.startswith(("Turkum:", "Kategoriya:")):
                    return f"[[{config.FALLBACK_CATEGORY_PREFIX}:{uz_title}{suffix}]]"
                return f"[[{uz_title}{suffix}]]"
            else:
                return f"[[{config.FALLBACK_CATEGORY_PREFIX}:{cat_name}{suffix}]]"

        text_after_cats = re.sub(RegexPatterns.CAT_TOKEN, cat_repl, text_after_links)

        # 3. Resolve templates
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
                            templates_to_remove.append(tpl)
                    else:
                        templates_to_remove.append(tpl)

        # Remove unresolved templates
        self._remove_templates(code2, templates_to_remove)

        final_text = str(code2)

        # 4. Restore references
        final_text = self._restore_references(final_text, ref_map)

        # 5. Apply Uzbek language rules (includes punctuation fixes)
        final_text = apply_all_fixes(final_text)

        logger.success("Finalizatsiya tugadi")

        return final_text

    def _restore_references(self, wikitext: str, ref_map: Dict[str, str]) -> str:
        """
        Restore compressed references.

        The model occasionally reformats a placeholder — a stray space, a
        dropped tag — and an exact string replace then silently misses it,
        leaving a raw REF_a1b2c3d4 in the finished article. So fall back to
        matching the id itself, and report whatever is still unresolved.
        """
        restored = 0
        for ref_id, original_ref in ref_map.items():
            placeholder = f"<ref>REF_{ref_id}</ref>"
            if placeholder in wikitext:
                wikitext = wikitext.replace(placeholder, original_ref)
                restored += 1
                continue

            loosened = re.compile(
                r"(?:<ref[^>]*>\s*)?REF_" + re.escape(ref_id) + r"(?:\s*</ref>)?"
            )
            # A lambda, not a template string: the reference text is arbitrary
            # wikitext and may contain backslashes.
            wikitext, hits = loosened.subn(lambda _m: original_ref, wikitext)
            if hits:
                restored += 1

        if ref_map:
            logger.info(f"✓ Manbalar tiklandi: {restored}/{len(ref_map)} ta")

        leftover = sorted(set(re.findall(RegexPatterns.REF_PLACEHOLDER, wikitext)))
        if leftover:
            logger.warning(
                f"{len(leftover)} ta manba tiklanmadi — matnda xom qoldi "
                "(model placeholder'ni oʻzgartirgan boʻlishi mumkin): "
                + ", ".join(leftover)
            )

        return wikitext
