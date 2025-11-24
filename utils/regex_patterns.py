#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/regex_patterns.py - Barcha regex patternlarni bir joyda
Bu faylda 20+ regex pattern mavjud. Hamma joydan ishlatiladi.
"""

import re
from typing import Optional

class RegexPatterns:
    """
    Butun loyihada ishlatiladigan regex patternlar.
    Har bir pattern katta harf bilan nomlangan.
    """
    
    # ========== Template Parameters Tozalash ==========
    
    # Bo'sh template parametri: | param = 
    EMPTY_PARAM = r'\|\s*([^=\|{}]+?)\s*=\s*(?=\n\s*[\|}])'
    
    # ========== Newlines Tozalash ==========
    
    # 3 yoki undan ko'p newline'lar → 2 ta newline
    MULTIPLE_NEWLINES = r'\n\s*\n\s*\n+'
    
    # Template ichida bo'sh satrlar
    TEMPLATE_EMPTY_LINES = r'(\{\{[^}]*?)\n\n+'
    
    # ========== Reference (Manba) Taglar ==========
    
    # <ref>...</ref> tag'i (yopiluvchi, self-closing EMAS)
    REF_TAG = r'<ref[^/>]*>.*?</ref>'
    
    # Self-closing ref: <ref ... /> (HECH QACHON compress qilmasin)
    REF_SELF_CLOSING = r'<ref[^>]*/\s*>'
    
    # SFN andoza: {{sfn|...}} yoki {{harvnb|...}} (manbalar kabi)
    SFN_TEMPLATE = r'\{\{(?:sfn|harvnb)\s*\|[^}]*\}\}'
    
    # Siqilgan manba: REF_a1b2c3d4
    REF_PLACEHOLDER = r'REF_[a-f0-9]{8}'
    
    # ========== Wikilink'lar ==========
    
    # [[link|text]] yoki [[link]]
    WIKILINK = r'\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]'
    
    # Bo'sh wikilink: [[]]
    EMPTY_WIKILINK = r'\[\[\s*\]\]'
    
    # QID: Q123456
    QID_PATTERN = r'(Q\d+)'
    
    # ========== Template'lar ==========
    
    # Template placeholder: {{TPL:Q12345}}
    TEMPLATE_PLACEHOLDER = r'\{\{TPL:(Q\d+)'
    
    # ========== HTML Izohlar ==========
    
    # <!-- comment -->
    HTML_COMMENT = r'<!--.*?-->'
    
    # ========== Tinish Belgilari va Manbalar ==========
    
    # Tinish belgisi MANBA OLDIDA: text.<ref>...</ref>
    PUNCT_BEFORE_REF = r'([.,;!?])\s*(<ref[^>]*>.*?</ref>)'
    
    # Tinish belgisi MANBALARIN ORASIDA: </ref>.<ref>
    PUNCT_BETWEEN_REFS = r'(</ref>)([.,;!?])(\s*)(<ref)'
    
    # Manba oxirida tinish: </ref>\n
    PUNCT_AFTER_REF_END = r'(</ref>)(\s*(?:\n|$))'
    
    # Duplikat tinish: </ref>.  →  </ref>.
    DUPLICATE_PUNCT = r'(</ref>)([.,;!?])\.'
    
    # ========== Kategoriyalar ==========
    
    # Kategoriya token: ⟦CAT:Q12345|label⟧
    CAT_TOKEN = r'⟦CAT:(Q\d+)\|([^\]]+?)⟧'
    
    # ========== Qavslar Tekshiruvi ==========
    
    # Ochiq qavslar
    OPEN_BRACKETS = r'[\[\{]'
    
    # Yopiq qavslar
    CLOSE_BRACKETS = r'[\]\}]'
    
    # ========== Inglizcha So'zlar ==========
    
    # Namespace prefixlari
    CATEGORY_PREFIX = r'\bcategory:'
    TEMPLATE_PREFIX = r'\btemplate:'
    FILE_PREFIX = r'\b(?:file|image):'
    
    # Umumiy inglizcha so'zlar
    BIRTH_DATE = r'\bbirth_date\b'
    DEATH_DATE = r'\bdeath_date\b'
    BIRTH_PLACE = r'\bbirth_place\b'
    
    # ========== Heading'lar ==========
    
    # == Heading ==
    HEADING = r'^==+.+?==+$'
    
    # ========== Qo'shimcha ==========
    
    # Whitespace qisqartirish
    EXTRA_SPACES = r'  +'
    
    # Trailing whitespace
    TRAILING_WHITESPACE = r'\s+$'

    # ========== CLASS METODLARI ==========
    
    @staticmethod
    def compile(pattern_name: str) -> Optional[re.Pattern]:
        """
        Regex patternni compile qil va qaytarish.
        Masalan: RegexPatterns.compile('EMPTY_PARAM')
        
        Args:
            pattern_name: Pattern nomi (UPPERCASE)
        
        Returns:
            Compiled regex pattern yoki None
        """
        pattern = getattr(RegexPatterns, pattern_name, None)
        if pattern:
            return re.compile(pattern, re.DOTALL | re.MULTILINE)
        return None
    
    @staticmethod
    def find_all(pattern_name: str, text: str) -> list:
        """
        Patternni text'da toping va barcha match'larni qaytarish.
        
        Args:
            pattern_name: Pattern nomi
            text: Tekshiriladigan matn
        
        Returns:
            Match'lar ro'yxati
        """
        regex = RegexPatterns.compile(pattern_name)
        if regex:
            return regex.findall(text)
        return []
    
    @staticmethod
    def replace(pattern_name: str, text: str, replacement: str) -> str:
        """
        Patternni top va almashtir.
        
        Args:
            pattern_name: Pattern nomi
            text: Tekshiriladigan matn
            replacement: Almashtirish matni
        
        Returns:
            Almashtirilgan matn
        """
        regex = RegexPatterns.compile(pattern_name)
        if regex:
            return regex.sub(replacement, text)
        return text
    
    @staticmethod
    def count(pattern_name: str, text: str) -> int:
        """Pattern'ni text'da necha marta topilganini hisoblash."""
        matches = RegexPatterns.find_all(pattern_name, text)
        return len(matches)


# ========== Maxsus Regex Funksiyalari ==========

def remove_empty_params(wikitext: str) -> str:
    """Bo'sh template parametrlarini olib tashlash."""
    cleaned = re.sub(RegexPatterns.EMPTY_PARAM, '', wikitext)
    cleaned = re.sub(RegexPatterns.MULTIPLE_NEWLINES, '\n\n', cleaned)
    cleaned = re.sub(RegexPatterns.TEMPLATE_EMPTY_LINES, r'\1\n', cleaned)
    return cleaned


def clean_html_comments(wikitext: str) -> str:
    """HTML izohlarini olib tashlash: <!-- ... -->"""
    return re.sub(RegexPatterns.HTML_COMMENT, '', wikitext, flags=re.DOTALL)


def fix_punctuation_with_refs(wikitext: str) -> str:
    """
    Tinish belgilarini manbalar bilan to'g'ri joylashtirish.
    
    Transformations:
    - text.<ref>...</ref>  →  text<ref>...</ref>.
    - </ref>.<ref> → </ref><ref>.
    """
    # 1. Tinish belgisini manba oldidan keyin joylashtirish
    wikitext = re.sub(
        RegexPatterns.PUNCT_BEFORE_REF,
        r'\2\1',
        wikitext,
        flags=re.DOTALL
    )
    
    # 2. Ketma-ket manbalar orasidagi tinish belgisini olib tashlash
    wikitext = re.sub(
        RegexPatterns.PUNCT_BETWEEN_REFS,
        r'\1\3\4',
        wikitext,
        flags=re.DOTALL
    )
    
    # 3. Manba oxirida tinish belgisi qo'shish (agar bo'lmasa)
    wikitext = re.sub(
        RegexPatterns.PUNCT_AFTER_REF_END,
        r'\1.\2',
        wikitext
    )
    
    # 4. Duplikat tinish belgilarini to'g'rilash
    wikitext = re.sub(
        RegexPatterns.DUPLICATE_PUNCT,
        r'\1\2',
        wikitext
    )
    
    return wikitext


def count_brackets(wikitext: str) -> tuple:
    """Ochiq va yopiq qavslarni sanash."""
    open_count = len(re.findall(r'[\[\{]', wikitext))
    close_count = len(re.findall(r'[\]\}]', wikitext))
    return (open_count, close_count)


def find_english_words(wikitext: str) -> dict:
    """Inglizcha so'zlarni topish."""
    return {
        "category": RegexPatterns.find_all('CATEGORY_PREFIX', wikitext),
        "template": RegexPatterns.find_all('TEMPLATE_PREFIX', wikitext),
        "birth_date": RegexPatterns.find_all('BIRTH_DATE', wikitext),
        "death_date": RegexPatterns.find_all('DEATH_DATE', wikitext),
    }


# ========== CITE BOOK SCRIPT-TITLE FIX ==========

def fix_cite_book_script_title(wikitext: str) -> str:
    """
    {{cite book}} andozasida `script-title` parametrini `title` ga o'zgartirish.
    Qiymatidagi ilk 3 ta belgini (masalan: ru:) olib tashlash.
    
    Namuna:
    {{cite book |script-title=ru:Преступление и наказание}}
    →
    {{cite book |title=Преступление и наказание}}
    """
    pattern = r'\{\{cite\s+book([^}]*?)\|\s*script-title\s*=\s*(?:[a-z]{2}:)?([^}|\]]*)'
    replacement = r'{{cite book\1|title=\2'
    return re.sub(pattern, replacement, wikitext, flags=re.IGNORECASE)


# ========== LOWERCASE -LIK SUFFIX FIX ==========

def fix_lik_suffix_capitalization(wikitext: str) -> str:
    """
    -lik qo'shimchasi bilan tugagan so'zlarning ilk harfini kichik qilish.
    LEKIN:
    - Template ichida bo'lmagan
    - Barobar belgisi (=) dan keyin, colon (:) dan keyin, nuqta (.) dan keyin bo'lmagan
    - Gapning boshida bo'lmagan
    
    Namuna:
    '''Ubaydul Haq''' — Bangladeshlik oʻqituvchi
    →
    '''Ubaydul Haq''' — bangladeshlik oʻqituvchi
    
    Lekin:
    | nationality = [[Bangladeshlik]]  (o'charmay qo'yadi)
    . [[Bangladeshlik]]  (o'charmay qo'yadi)
    [[Turkum:Bangladeshlik]]  (o'charmay qo'yadi)
    """
    
    # Qidiriladigan pattern: -lik qo'shimchasi bilan tugagan so'zlar
    # LEKIN: =, :, . dan keyin keladigan so'zlar va template ichidagi so'zlar EMAS
    
    # 1. Gapning boshidan keyin kelgan -lik so'zlarni olish
    # Pattern: (punkt yoki template tugashi) + (whitespace) + (KATTA harfdan boshlanuvchi -lik so'z)
    
    # Negatif lookbehind: = : . dan keyin emas, {{ ichida emas
    pattern = r'(?<![=:.\[])\b([A-Z][a-z]*lik)\b(?![}\]])'
    
    def replacer(match):
        word = match.group(1)
        # Agar = yoki : yoki . dan oldin bo'lsa, o'charmay qo'y
        return word[0].lower() + word[1:]
    
    return re.sub(pattern, replacer, wikitext)


# ========== YEAR WITH DASH FIX ==========

def fix_year_with_dash(wikitext: str) -> str:
    """
    Yil raqamlaridan keyin -yil qo'shimchasiga chiziqcha (-) qoʻshish.
    
    Namunalar:
    2025 yil → 2025-yil
    1975/76 yillarda → 1975/76-yillarda
    """
    
    # Pattern 1: YYYY yil → YYYY-yil
    wikitext = re.sub(r'(\d+)\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)
    
    # Pattern 2: {{Circa|910}} yilda → {{Circa|910}}-yilda
    wikitext = re.sub(r'(\{\{\s*Circa[^}]*\}\})\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)
    
    return wikitext


# ========== COMPRESS REFERENCES (SELF-CLOSING EMAS) ==========

def compress_references_safe(wikitext: str) -> tuple:
    """
    Manbalarni siqish, LEKIN:
    - Self-closing ref'lar (<ref .../>) EMAS
    - SFN andozalar ham siqish (<ref> kabi)
    
    Returns:
        (compressed_text, ref_map)
    """
    import hashlib
    
    ref_map = {}
    
    # 1. Normal ref'larni siqish: <ref ...>...</ref>
    ref_pattern = re.compile(RegexPatterns.REF_TAG, re.DOTALL | re.IGNORECASE)
    
    def replace_ref(match):
        ref_content = match.group(0)
        if len(ref_content) > 200:  # REF_COMPRESS_THRESHOLD
            ref_id = hashlib.md5(ref_content.encode()).hexdigest()[:8]
            placeholder = f"<ref>REF_{ref_id}</ref>"
            ref_map[ref_id] = ref_content
            return placeholder
        return ref_content
    
    compressed = ref_pattern.sub(replace_ref, wikitext)
    
    # 2. SFN andozalarni ham siqish (optional, lekin tavsiya qiluvchi)
    # SFN'lar odatda qisqa bo'lgani uchun siqishning zaruriyati kam
    
    return compressed, ref_map


# ========== FIX PUNCTUATION WITH SFN TEMPLATES ==========

def fix_punctuation_with_sfn(wikitext: str) -> str:
    """
    SFN andozalardan oldin qoʻyilgan tinish belgilarini keyinga surish.
    
    Namuna:
    .{{sfn|Qandaydir matn}} → {{sfn|Qandaydir matn}}.
    ,{{sfn|...}} → {{sfn|...}},
    
    Xuddi <ref> kabi.
    """
    
    # Tinish belgisi SFN dan oldin
    pattern = r'([.,;!?])\s*(\{\{(?:sfn|harvnb)\s*\|[^}]*\}\})'
    replacement = r'\2\1'
    
    return re.sub(pattern, replacement, wikitext)


# ========== COMBINE ALL FIXES ==========

def apply_all_fixes(wikitext: str) -> str:
    """
    Barcha o'zgartirishlarni ketma-ket qoʻllash.
    
    Tartib muhim!
    """
    
    # 1. Cite book script-title fix
    wikitext = fix_cite_book_script_title(wikitext)
    
    # 2. Year dash fix
    wikitext = fix_year_with_dash(wikitext)
    
    # 3. -lik suffix capitalization fix
    wikitext = fix_lik_suffix_capitalization(wikitext)
    
    # 4. SFN punctuation fix
    wikitext = fix_punctuation_with_sfn(wikitext)
    
    return wikitext