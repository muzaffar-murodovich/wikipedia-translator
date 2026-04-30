#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/regex_patterns.py - All regex patterns in one place
This file contains 20+ regex patterns used across the project.
"""

import re
from typing import Optional
import mwparserfromhell as mwp

class RegexPatterns:
    """
    Regex patterns used throughout the project.
    Each pattern is named in UPPERCASE.
    """

    # ========== Template Parameter Cleanup ==========

    # Empty template parameter: | param =
    EMPTY_PARAM = r'\|\s*([^=\|{}]+?)\s*=\s*(?=\n\s*[\|}])'

    # ========== Newline Cleanup ==========

    # 3+ newlines -> 2 newlines
    MULTIPLE_NEWLINES = r'\n\s*\n\s*\n+'

    # Empty lines inside templates
    TEMPLATE_EMPTY_LINES = r'(\{\{[^}]*?)\n\n+'

    # ========== Reference Tags ==========

    # <ref>...</ref> tag (closing, NOT self-closing)
    REF_TAG = r'<ref[^/>]*>.*?</ref>'

    # Self-closing ref: <ref ... /> (NEVER compress)
    REF_SELF_CLOSING = r'<ref[^>]*/\s*>'

    # SFN template: {{sfn|...}} or {{harvnb|...}}
    SFN_TEMPLATE = r'\{\{sfn\s*\|[^}]*\}\}'

    # Compressed reference placeholder: REF_a1b2c3d4
    REF_PLACEHOLDER = r'REF_[a-f0-9]{8}'

    # ========== Wikilinks ==========

    # [[link|text]] or [[link]]
    WIKILINK = r'\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]'

    # Empty wikilink: [[]]
    EMPTY_WIKILINK = r'\[\[\s*\]\]'

    # QID: Q123456
    QID_PATTERN = r'(Q\d+)'

    # ========== Templates ==========

    # Template placeholder: {{TPL:Q12345}}
    TEMPLATE_PLACEHOLDER = r'\{\{TPL:(Q\d+)'

    # ========== HTML Comments ==========

    # <!-- comment -->
    HTML_COMMENT = r'<!--.*?-->'

    # ========== Punctuation and References ==========

    # Punctuation BEFORE ref: text.<ref>...</ref>
    PUNCT_BEFORE_REF = r'([.,;!?])\s*(<ref[^>]*>.*?</ref>)'

    # Punctuation BETWEEN refs: </ref>.<ref>
    PUNCT_BETWEEN_REFS = r'(</ref>)([.,;!?])(\s*)(<ref)'

    # Punctuation after ref end: </ref>\n
    PUNCT_AFTER_REF_END = r'(</ref>)(\s*(?:\n|$))'

    # Duplicate punctuation: </ref>.. -> </ref>.
    DUPLICATE_PUNCT = r'(</ref>)([.,;!?])\.'

    # ========== Categories ==========

    # Category token: ⟦CAT:Q12345|label⟧
    CAT_TOKEN = r'⟦CAT:(Q\d+)\|([^\]]+?)⟧'

    # ========== Bracket Check ==========

    # Open brackets
    OPEN_BRACKETS = r'[\[\{]'

    # Close brackets
    CLOSE_BRACKETS = r'[\]\}]'

    # ========== English Words ==========

    # Namespace prefixes
    CATEGORY_PREFIX = r'\bcategory:'
    TEMPLATE_PREFIX = r'\btemplate:'
    FILE_PREFIX = r'\b(?:file|image):'

    # Common English words
    BIRTH_DATE = r'\bbirth_date\b'
    DEATH_DATE = r'\bdeath_date\b'
    BIRTH_PLACE = r'\bbirth_place\b'

    # ========== Headings ==========

    # == Heading ==
    HEADING = r'^==+.+?==+$'

    # ========== Miscellaneous ==========

    # Extra spaces
    EXTRA_SPACES = r'  +'

    # Trailing whitespace
    TRAILING_WHITESPACE = r'\s+$'

    # ========== Class Methods ==========

    @staticmethod
    def compile(pattern_name: str) -> Optional[re.Pattern]:
        """
        Compile a regex pattern by name.
        E.g. RegexPatterns.compile('EMPTY_PARAM')

        Args:
            pattern_name: Pattern name (UPPERCASE)

        Returns:
            Compiled regex pattern or None
        """
        pattern = getattr(RegexPatterns, pattern_name, None)
        if pattern:
            return re.compile(pattern, re.DOTALL | re.MULTILINE)
        return None

    @staticmethod
    def find_all(pattern_name: str, text: str) -> list:
        """
        Find all matches of a pattern in text.

        Args:
            pattern_name: Pattern name
            text: Text to search

        Returns:
            List of matches
        """
        regex = RegexPatterns.compile(pattern_name)
        if regex:
            return regex.findall(text)
        return []

    @staticmethod
    def replace(pattern_name: str, text: str, replacement: str) -> str:
        """
        Find and replace a pattern.

        Args:
            pattern_name: Pattern name
            text: Text to search
            replacement: Replacement text

        Returns:
            Replaced text
        """
        regex = RegexPatterns.compile(pattern_name)
        if regex:
            return regex.sub(replacement, text)
        return text

    @staticmethod
    def count(pattern_name: str, text: str) -> int:
        """Count how many times a pattern appears in text."""
        matches = RegexPatterns.find_all(pattern_name, text)
        return len(matches)


# ========== Special Regex Functions ==========

def remove_empty_params(wikitext: str) -> str:
    """Remove empty template parameters."""
    cleaned = re.sub(RegexPatterns.EMPTY_PARAM, '', wikitext)
    cleaned = re.sub(RegexPatterns.MULTIPLE_NEWLINES, '\n\n', cleaned)
    cleaned = re.sub(RegexPatterns.TEMPLATE_EMPTY_LINES, r'\1\n', cleaned)
    return cleaned


def clean_html_comments(wikitext: str) -> str:
    """Remove HTML comments: <!-- ... -->"""
    return re.sub(RegexPatterns.HTML_COMMENT, '', wikitext, flags=re.DOTALL)


def fix_punctuation_with_refs(wikitext: str) -> str:
    """
    Fix punctuation placement around references.

    Transformations:
    - text.<ref>...</ref>  ->  text<ref>...</ref>.
    - text.<ref name="x"/>  ->  text<ref name="x"/>.
    - </ref>.<ref> -> </ref><ref>.
    - </ref>. -> </ref>. (keep as is)
    - <ref/> (at end) -> <ref/>. (add period)
    """

    # 1. Move punctuation from before ref to after ref (normal ref)
    wikitext = re.sub(
        r'([.,;!?])\s*(<ref[^/>]*>.*?</ref>)',
        r'\2\1',
        wikitext,
        flags=re.DOTALL
    )

    # 2. Move punctuation from before self-closing ref to after
    wikitext = re.sub(
        r'([.,;!?])\s*(<ref[^>]*/\s*>)',
        r'\2\1',
        wikitext
    )

    # 3. Remove punctuation between consecutive refs
    # </ref>.<ref> -> </ref><ref>
    wikitext = re.sub(
        r'(</ref>)([.,;!?])(\s*)(<ref)',
        r'\1\3\4',
        wikitext,
        flags=re.DOTALL
    )

    # 4. Remove punctuation between self-closing refs
    # <ref />.<ref /> -> <ref /><ref />
    wikitext = re.sub(
        r'(/\s*>)([.,;!?])(\s*)(<ref)',
        r'\1\3\4',
        wikitext
    )

    # 5. Mixed normal ref and self-closing ref sequences
    # </ref>.<ref /> -> </ref><ref />
    wikitext = re.sub(
        r'(</ref>|/\s*>)([.,;!?])(\s*)(<ref)',
        r'\1\3\4',
        wikitext
    )

    # 6. Add period after normal ref if missing (when followed by space/newline, not punctuation/markup)
    # Skip if next word starts with a lowercase letter (sentence continues, e.g. "<ref /> va ...")
    wikitext = re.sub(
        r'(</ref>)(\s+)(?![.,;!?<{\[a-zʼ‘’\'])',
        r'\1.\2',
        wikitext
    )

    # 7. Add period after self-closing ref if missing
    # Skip if next word starts with a lowercase letter (sentence continues)
    wikitext = re.sub(
        r'(/\s*>)(\s+)(?![.,;!?<{\[a-zʼ‘’\'])',
        r'\1.\2',
        wikitext
    )

    # 8. Fix duplicate punctuation
    # </ref>.. -> </ref>.
    wikitext = re.sub(
        r'(</ref>|/\s*>)([.,;!?])\2+',
        r'\1\2',
        wikitext
    )

    return wikitext


# ========== Cite Book Script-Title Fix ==========

def fix_cite_book_script_title(wikitext: str) -> str:
    """
    Replace `script-title` with `title` in {{cite book}} templates.
    Strips the language prefix (e.g. "ru:") from the value.

    Example:
    {{cite book |script-title=ru:Text}} -> {{cite book |title=Text}}
    """
    pattern = r'\{\{cite\s+book([^}]*?)\|\s*script-title\s*=\s*(?:[a-z]{2}:)?([^}|\]]*)'
    replacement = r'{{cite book\1|title=\2'
    return re.sub(pattern, replacement, wikitext, flags=re.IGNORECASE)


# ========== Lowercase -lik Suffix Fix ==========

def fix_lik_suffix_capitalization(wikitext: str) -> str:
    """
    Lowercase words ending with -lik suffix mid-sentence.
    Skips words inside templates, after =/:/.  or inside [[...]].

    Example:
    '''Ubaydul Haq''' — Bangladeshlik teacher
    -> '''Ubaydul Haq''' — bangladeshlik teacher

    But keeps:
    | nationality = [[Bangladeshlik]]  (unchanged)
    """
    pattern = r'(?<![=:.\[])\b([A-Z][a-z]*lik)\b(?![}\]])'

    def replacer(match):
        word = match.group(1)
        return word[0].lower() + word[1:]

    return re.sub(pattern, replacer, wikitext)


# ========== Year With Dash Fix ==========

def fix_year_with_dash(wikitext: str) -> str:
    """
    Add dash between year numbers and -yil suffix.

    Examples:
    2025 yil -> 2025-yil
    1975/76 yillarda -> 1975/76-yillarda
    """
    # Pattern 1: YYYY yil -> YYYY-yil
    wikitext = re.sub(r'(\d+)\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)

    # Pattern 2: {{Circa|910}} yilda -> {{Circa|910}}-yilda
    wikitext = re.sub(r'(\{\{\s*Circa[^}]*\}\})\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)

    return wikitext


# ========== Fix Punctuation With SFN Templates ==========

def fix_punctuation_with_sfn(wikitext: str) -> str:
    """Move punctuation to correct position around SFN/EFN templates."""
    _sfn_efn = r'\{\{(?:sfn|efn)\s*\|[^}]*\}\}'

    # Step 1: Move punctuation from before SFN/EFN to after SFN/EFN
    wikitext = re.sub(
        r'([.,;!?])\s*(' + _sfn_efn + r')',
        r'\2\1',
        wikitext, flags=re.IGNORECASE
    )

    # Step 2: </ref>.{{sfn/efn}} -> </ref>{{sfn/efn}}.
    wikitext = re.sub(
        r'(</ref>)([.,;!?])(\s*)(' + _sfn_efn + r')',
        r'\1\3\4\2',
        wikitext, flags=re.IGNORECASE
    )

    # Step 3: {{sfn/efn}}.{{sfn/efn}} -> {{sfn/efn}}{{sfn/efn}}
    wikitext = re.sub(
        r'(\}\})([.,;!?])(\s*)(\{\{(?:sfn|efn))',
        r'\1\3\4',
        wikitext, flags=re.IGNORECASE
    )

    # Step 4: Clean excess punctuation in sfn/efn/ref chains
    for _ in range(5):
        wikitext = re.sub(
            r'(\}\}|</ref>)([.,;!?])(\s*)(\{\{(?:sfn|efn)|<ref)',
            r'\1\3\4',
            wikitext, flags=re.IGNORECASE
        )

    # Step 5: Add period after last sfn/efn if missing
    wikitext = re.sub(
        r'(' + _sfn_efn + r')(\s+)(?![.,;!?<{\[])',
        r'\1.\2',
        wikitext,
        flags=re.IGNORECASE
    )

    # Step 6: Remove punctuation before sfn/efn
    wikitext = re.sub(
        r'([.,;!?])\s*(' + _sfn_efn + r')',
        r'\2',
        wikitext, flags=re.IGNORECASE
    )

    # 7a. Add period after </ref> when followed by [[Capitalized link]] (new sentence)
    wikitext = re.sub(
        r'(</ref>)(\s+)(\[\[)(?=[A-ZА-ЯЁʿʾ])',
        r'\1.\2\3',
        wikitext
    )

    # 7b. Same for self-closing refs
    wikitext = re.sub(
        r'(/\s*>)(\s+)(\[\[)(?=[A-ZА-ЯЁʿʾ])',
        r'\1.\2\3',
        wikitext
    )

    return wikitext

# ========== Combine All Fixes ==========

def apply_all_fixes(wikitext: str) -> str:
    """Apply all text fixes in sequence. Order matters!"""

    # 0. Arabic transliteration + date fixes (already infobox-aware via mwparserfromhell)
    wikitext = fix_arabic_transliteration(wikitext)

    # 1. Cite book script-title fix
    wikitext = fix_cite_book_script_title(wikitext)

    # 2. Year dash fix
    wikitext = fix_year_with_dash(wikitext)

    # 3. -lik suffix capitalization fix
    wikitext = fix_lik_suffix_capitalization(wikitext)

    # 4. Punctuation with refs fix — skip infoboxes
    wikitext = _apply_fix_outside_infoboxes(wikitext, fix_punctuation_with_refs)

    # 5. SFN punctuation fix — skip infoboxes
    wikitext = _apply_fix_outside_infoboxes(wikitext, fix_punctuation_with_sfn)

    # 6. fix template blank lines 
    wikitext = fix_template_blank_lines(wikitext)
    
    # Collapse 3+ consecutive newlines to 2 (single blank line max)
    wikitext = re.sub(r'\n{3,}', '\n\n', wikitext)

    return wikitext

_DIACRITIC_TRANS = str.maketrans({
    'ā': 'a', 'Ā': 'A',
    'ī': 'i', 'Ī': 'I',
    'ū': 'u', 'Ū': 'U',
    'ḥ': 'h', 'Ḥ': 'H',
    'ṣ': 's', 'Ṣ': 'S',
    'ḍ': 'd', 'Ḍ': 'D',
    'ṭ': 't', 'Ṭ': 'T',
    'ẓ': 'z', 'Ẓ': 'Z',
    'ġ': 'gʻ', 'Ġ': 'Gʻ',
    'ʿ': '',
    'ʾ': '',
})

# Tags whose contents must NEVER be modified
_PROTECTED_TAGS = frozenset({
    'ref', 'nowiki', 'pre', 'source', 'syntaxhighlight', 'code', 'math'
})


def _apply_arabic_text_fixes(text: str) -> str:
    """Apply Rule 1 (diacritics) and Rule 2 (solar letters) to plain text."""

    # Rule 1a: Final -ī → -iy (must run BEFORE general diacritic removal,
    # otherwise the information is lost)
    text = re.sub(r'ī\b', 'iy', text)
    text = re.sub(r'Ī\b', 'Iy', text)

    # Rule 1b: Remove all other diacritics
    text = text.translate(_DIACRITIC_TRANS)

    # Rule 2: Solar letter assimilation (al-X → aX-X)
    # 'Sh' must come first in the alternation to avoid 'S' matching first
    def _solar_replace(m: re.Match) -> str:
        prefix = m.group(1)  # 'a' or 'A'
        letter = m.group(2)  # 'Sh', 'R', 'D', 'N', 'S', 'T', or 'Z'
        if letter == 'Sh':
            return f'{prefix}sh-{letter}'
        return f'{prefix}{letter.lower()}-{letter}'

    text = re.sub(r'\b([Aa])l-(Sh|R|D|N|S|T|Z)', _solar_replace, text)
    return text


def _process_wikicode_safe(code) -> None:
    """
    Recursively walk the parse tree, applying text fixes ONLY to safe contexts.
    Skips <ref>, URLs, and non-infobox templates.
    """
    for node in code.nodes:
        node_type = type(node).__name__

        if node_type == 'Text':
            node.value = _apply_arabic_text_fixes(node.value)
            node.value = _apply_date_fixes(node.value)

        elif node_type == 'Heading':
            _process_wikicode_safe(node.title)

        elif node_type == 'Wikilink':
            # Process visible label only — link target is intentionally untouched
            if node.text is not None:
                _process_wikicode_safe(node.text)

        elif node_type == 'Tag':
            tag_name = str(node.tag).lower() if node.tag else ''
            if tag_name in _PROTECTED_TAGS:
                continue
            if node.contents is not None:
                _process_wikicode_safe(node.contents)

        elif node_type == 'ExternalLink':
            # Skip URL; process display title only
            if node.title is not None:
                _process_wikicode_safe(node.title)

        elif node_type == 'Template':
            # Process param values ONLY for infobox templates (containing 'bilgiquti').
            # Skip all other templates (cite book, sfn, lang-*, etc.).
            template_name = str(node.name).strip().lower()
            if 'bilgiquti' not in template_name:
                continue
            for param in node.params:
                _process_wikicode_safe(param.value)

        # Comment, HTMLEntity, Argument → skip

def fix_arabic_transliteration(wikitext: str) -> str:
    """
    Apply translation_rules.md Rules 1 and 2 deterministically.

    Rule 1: diacritic removal (ā→a, ī→i, ū→u, ḥ→h, ʿ→∅, ʾ→∅, etc.)
            with final -ī → -iy preservation.
    Rule 2: solar letter assimilation (al-Roziy → ar-Roziy, al-Shofiʼiy → ash-Shofiʼiy).

    Skips: <ref>...</ref>, URLs, template parameter values, link targets.

    Examples:
        Labīd            → Labid
        al-ʿĀmirī        → al-Amiriy
        al-Shofiʼiy      → ash-Shofiʼiy
        al-Tabariy       → at-Tabariy
        Muḥammad         → Muhammad
    """
    code = mwp.parse(wikitext, skip_style_tags=True)
    _process_wikicode_safe(code)
    return str(code)

def _apply_fix_outside_infoboxes(wikitext: str, fix_func) -> str:
    """
    Apply a regex-based fix function to wikitext, but skip infobox templates
    (templates containing 'bilgiquti' in their name).
    """
    code = mwp.parse(wikitext, skip_style_tags=True)

    # Collect infobox templates as strings (no AST manipulation)
    infoboxes = []
    for tpl in code.filter_templates():
        if 'bilgiquti' in str(tpl.name).strip().lower():
            infoboxes.append(str(tpl))

    # Replace each infobox with a placeholder via plain string replace
    text = wikitext
    placeholders = {}
    for i, infobox in enumerate(infoboxes):
        placeholder = f"@@INFOBOX_{i}@@"
        placeholders[placeholder] = infobox
        text = text.replace(infobox, placeholder, 1)

    # Apply fix to text without infoboxes
    text = fix_func(text)

    # Restore infoboxes
    for placeholder, original in placeholders.items():
        text = text.replace(placeholder, original)

    return text
def _apply_date_fixes(text: str) -> str:
    """Apply Rule 5a: hijri/milodi date formatting."""
    text = re.sub(
        r'\b(\d+)\s+(hijriy|milodiy)(?:\s+(yil(?:da|gacha|dan|ga|i|lar(?:i|da|dan|ga)?)?))?\b',
        lambda m: f"{m.group(2)} {m.group(1)}-{m.group(3) or 'yil'}",
        text
    )
    text = re.sub(r'\b(hijriy|milodiy)\s+(\d+)\b(?!\s*-)', r'\1 \2-yil', text)
    return text

def fix_template_blank_lines(wikitext: str) -> str:
    """Clean up multi-line template formatting."""
    code = mwp.parse(wikitext, skip_style_tags=True)
    
    for tpl in code.filter_templates():
        if not tpl.params:
            continue
        
        is_multiline = any('\n' in str(p) for p in tpl.params)
        if not is_multiline:
            continue
        
        # Clean blank lines inside param values
        for param in tpl.params:
            value_str = str(param.value)
            cleaned = re.sub(r'\n\s*\n+', '\n', value_str)
            if cleaned != value_str:
                param.value = cleaned
        
        # Ensure name ends with newline so first param starts on new line
        name_str = str(tpl.name)
        if not name_str.endswith('\n'):
            tpl.name = name_str.rstrip() + '\n'
    
    return str(code)