#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
core/quality_checker.py - Translation quality checking
Detects unresolved placeholders, empty wikilinks, and other issues.
"""

import re
from typing import List
from utils.regex_patterns import RegexPatterns
from utils.logger import logger


class QualityIssue:
    """Issue representation."""

    def __init__(self, severity: str, message: str, location: str = ""):
        """
        Args:
            severity: "error", "warning", "info"
            message: Error/warning text
            location: Location of the issue (optional)
        """
        self.severity = severity
        self.message = message
        self.location = location

    def __str__(self):
        icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        icon = icons.get(self.severity, "•")
        loc = f" [{self.location}]" if self.location else ""
        return f"{icon} {self.message}{loc}"


class QualityChecker:
    """Translation quality checker."""

    def __init__(self):
        self.issues = []

    def check(self, wikitext: str) -> List[QualityIssue]:
        """
        Check wikitext and find issues.

        Args:
            wikitext: Text to check

        Returns:
            List of QualityIssues
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
        """Check for unresolved QIDs."""
        qid_pattern = r'\[\[(Q\d+)\|'
        matches = RegexPatterns.find_all('QID_PATTERN', wikitext)

        wikilink_matches = re.findall(qid_pattern, wikitext)

        if wikilink_matches:
            unique_qids = set(wikilink_matches)
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan {len(wikilink_matches)} ta QID havola: {', '.join(list(unique_qids)[:5])}"
            ))

    def _check_unresolved_templates(self, wikitext: str):
        """Check for unresolved templates."""
        matches = RegexPatterns.find_all('TEMPLATE_PLACEHOLDER', wikitext)

        if matches:
            unique = set(matches)
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan {len(matches)} ta andoza: {', '.join(list(unique)[:5])}"
            ))

    def _check_empty_wikilinks(self, wikitext: str):
        """Check for empty wikilinks."""
        matches = RegexPatterns.find_all('EMPTY_WIKILINK', wikitext)

        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Bo'sh havolalar topildi: {len(matches)} ta"
            ))

    def _check_brackets(self, wikitext: str):
        """Check bracket balance."""
        open_count = len(re.findall(r'[\[\{]', wikitext))
        close_count = len(re.findall(r'[\]\}]', wikitext))

        if open_count != close_count:
            self.issues.append(QualityIssue(
                "error",
                f"Qavslar soni mos kelmaydi: {open_count} ochiq, {close_count} yopiq"
            ))

    def _check_ref_placeholders(self, wikitext: str):
        """Check for unrestored reference placeholders."""
        matches = RegexPatterns.find_all('REF_PLACEHOLDER', wikitext)

        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Tiklanmagan manbalar: {len(matches)} ta"
            ))

    def _check_cat_tokens(self, wikitext: str):
        """Check for unresolved category tokens."""
        matches = re.findall(RegexPatterns.CAT_TOKEN, wikitext)

        if matches:
            self.issues.append(QualityIssue(
                "error",
                f"Hal qilinmagan kategoriyalar: {len(matches)} ta"
            ))

    def print_report(self):
        """Print quality check results."""
        pass

    def has_errors(self) -> bool:
        """Check if there are errors."""
        return any(i.severity == "error" for i in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return any(i.severity == "warning" for i in self.issues)

    def get_error_count(self) -> int:
        """Get error count."""
        return len([i for i in self.issues if i.severity == "error"])

    def get_warning_count(self) -> int:
        """Get warning count."""
        return len([i for i in self.issues if i.severity == "warning"])
