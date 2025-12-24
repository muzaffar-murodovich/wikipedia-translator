#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/quality_checker.py - Tarjima sifatini tekshirish
Hal qilinmagan placeholder'lar, bo'sh havolalar va boshqa muammolarni aniqlash.
"""

from typing import List
from utils.regex_patterns import RegexPatterns
from utils.logger import logger


class QualityIssue:
    """Muammo representation."""
    
    def __init__(self, severity: str, message: str, location: str = ""):
        """
        Args:
            severity: "error", "warning", "info"
            message: Xato/ogohlantirish matni
            location: Xatoning joylashuvi (ixtiyoriy)
        """
        self.severity = severity
        self.message = message
        self.location = location
    
    def __str__(self):
        """String representation."""
        icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        icon = icons.get(self.severity, "•")
        loc = f" [{self.location}]" if self.location else ""
        return f"{icon} {self.message}{loc}"


class QualityChecker:
    """Tarjima sifatini tekshirish."""
    
    def __init__(self):
        """QualityChecker'ni initialize qilish."""
        self.issues = []
    
    def check(self, wikitext: str) -> List[QualityIssue]:
        """
        Wikitext'ni tekshirish va muammolarni topish.
        
        Args:
            wikitext: Tekshiriladigan matn
        
        Returns:
            QualityIssue'lar ro'yxati
        """
        self.issues = []
        
        self._check_unresolved_qids(wikitext)
        self._check_unresolved_templates(wikitext)
        self._check_empty_wikilinks(wikitext)
        self._check_brackets(wikitext)
        self._check_ref_placeholders(wikitext)
        self._check_cat_tokens(wikitext)
        
        return self.issues
    
    def _check_unresolved_qids(self, wikitext: str):
        """Hal qilinmagan QID'larni tekshirish."""
        qid_pattern = r'\[\[(Q\d+)\|'
        matches = RegexPatterns.find_all('QID_PATTERN', wikitext)
        
        # Wikilink'larni tekshirish
        import re
        wikilink_matches = re.findall(qid_pattern, wikitext)
        
        if wikilink_matches:
            unique_qids = set(wikilink_matches)
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan {len(wikilink_matches)} ta QID havola: {', '.join(list(unique_qids)[:5])}"
            ))
    
    def _check_unresolved_templates(self, wikitext: str):
        """Hal qilinmagan andozalarni tekshirish."""
        matches = RegexPatterns.find_all('TEMPLATE_PLACEHOLDER', wikitext)
        
        if matches:
            unique = set(matches)
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan {len(matches)} ta andoza: {', '.join(list(unique)[:5])}"
            ))
    
    def _check_empty_wikilinks(self, wikitext: str):
        """Bo'sh wikilink'larni tekshirish."""
        matches = RegexPatterns.find_all('EMPTY_WIKILINK', wikitext)
        
        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Bo'sh havolalar topildi: {len(matches)} ta"
            ))
    
    def _check_brackets(self, wikitext: str):
        """Qavslar mos kelishini tekshirish."""
        open_count, close_count = RegexPatterns.count('OPEN_BRACKETS', wikitext), \
                                   RegexPatterns.count('CLOSE_BRACKETS', wikitext)
        
        # To'g'ri hisob
        import re
        open_count = len(re.findall(r'[\[\{]', wikitext))
        close_count = len(re.findall(r'[\]\}]', wikitext))
        
        if open_count != close_count:
            self.issues.append(QualityIssue(
                "error",
                f"Qavslar soni mos kelmaydi: {open_count} ochiq, {close_count} yopiq"
            ))
    
    def _check_ref_placeholders(self, wikitext: str):
        """Tiklanmagan manba placeholder'larini tekshirish."""
        matches = RegexPatterns.find_all('REF_PLACEHOLDER', wikitext)
        
        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Tiklanmagan manbalar: {len(matches)} ta"
            ))
    
    def _check_cat_tokens(self, wikitext: str):
        """Hal qilinmagan kategoriyalarni tekshirish."""
        import re
        matches = re.findall(RegexPatterns.CAT_TOKEN, wikitext)
        
        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan kategoriyalar: {len(matches)} ta"
            ))
    
    def print_report(self):
        """Tekshiruv natijalari ko'rsatish."""
        # if not self.issues:
        #     logger.success("Sifat tekshiruvi: Xatolar topilmadi!")
        #     return
        
        # logger.section("SIFAT TEKSHIRUVI NATIJALARI")
        
        # errors = [i for i in self.issues if i.severity == "error"]
        # warnings = [i for i in self.issues if i.severity == "warning"]
        
        # if errors:
        #     logger.info("🔴 XATOLAR:")
        #     for issue in errors:
        #         logger.error(f"  {issue}")
        
        # if warnings:
        #     logger.info("🟡 OGOHLANTIRISHLAR:")
        #     for issue in warnings:
        #         logger.warning(f"  {issue}")
        
        # # Xulosa
        # logger.info(f"\nJami muammo: {len(self.issues)}")
        
        # if errors:
        #     logger.warning("⚠️  Xatolar tuzatilmaguncha maqola to'liq bo'lmaydi!")
        pass
    
    def has_errors(self) -> bool:
        """Xato borligini tekshirish."""
        return any(i.severity == "error" for i in self.issues)
    
    def has_warnings(self) -> bool:
        """Ogohlantirish borligini tekshirish."""
        return any(i.severity == "warning" for i in self.issues)
    
    def get_error_count(self) -> int:
        """Xato sonini olish."""
        return len([i for i in self.issues if i.severity == "error"])
    
    def get_warning_count(self) -> int:
        """Ogohlantirish sonini olish."""
        return len([i for i in self.issues if i.severity == "warning"])