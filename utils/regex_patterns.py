#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
utils/regex_patterns.py - All regex patterns in one place
This file contains 20+ regex patterns used across the project.
"""

import re
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

    # Category token: ⟦CAT:Q12345|cat_name|sort_key⟧ (sort_key may be empty)
    CAT_TOKEN = r'⟦CAT:(Q\d+)\|([^|⟧]+)\|([^⟧]*)⟧'

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

    # 3. Remove punctuation between consecutive refs, of either kind
    # </ref>.<ref> -> </ref><ref>,  <ref />.<ref /> -> <ref /><ref />
    wikitext = re.sub(
        r'(</ref>|/\s*>)([.,;!?])(\s*)(<ref)',
        r'\1\3\4',
        wikitext
    )

    # 4. Add period after normal ref if missing (when followed by space/newline, not punctuation/markup)
    # Skip if next word starts with a lowercase letter (sentence continues, e.g. "<ref /> va ...")
    wikitext = re.sub(
        r'(</ref>)(\s+)(?![.,;!?<{\[a-zʼ‘’\'])',
        r'\1.\2',
        wikitext
    )

    # 5. Add period after self-closing ref if missing
    # Skip if next word starts with a lowercase letter (sentence continues)
    wikitext = re.sub(
        r'(/\s*>)(\s+)(?![.,;!?<{\[a-zʼ‘’\'])',
        r'\1.\2',
        wikitext
    )

    # 6. Fix duplicate punctuation
    # </ref>.. -> </ref>.
    wikitext = re.sub(
        r'(</ref>|/\s*>)([.,;!?])\2+',
        r'\1\2',
        wikitext
    )

    # 7. Add a period when a capitalised [[link]] starts the next sentence.
    # Steps 4 and 5 deliberately skip '[', because a lowercase link continues
    # the sentence; a capitalised one does not.
    wikitext = re.sub(
        r'(</ref>|/\s*>)(\s+)(\[\[)(?=[A-ZА-ЯЁʿʾ])',
        r'\1.\2\3',
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

_LIK_WORD = re.compile(r'\b([A-Z][a-z]*lik)\b(?![}\]])')

# Positions where the capital is correct and the word must be left alone:
# the start of a line (a paragraph starts a sentence, and the article name
# opens with '''), the start of a new sentence, a template parameter value
# and the inside of a [[wikilink]].
_LIK_KEEP_CAPITAL = re.compile(
    r"(?:\A|\n)[ \t*#:;]*(?:'{2,})?[ \t]*$"   # line start / '''article name'''
    r"|[.!?][ \t]*$"                           # new sentence
    r"|[=:][ \t]*$"                             # template parameter value
    r"|\[[ \t]*$"                               # [[wikilink]] target
)


# Everything a _LIK_KEEP_CAPITAL match may consist of after its first
# character. Walking back over this run bounds how far the scan has to look.
_LIK_LOOKBACK_CHARS = " \t*#:;'"


def _keep_capital_scan_start(wikitext: str, word_start: int) -> int:
    """
    Earliest position a _LIK_KEEP_CAPITAL match ending at `word_start` can begin.

    Every alternative is a single leading character (\n, '.', '=', '[' ...)
    followed by a run drawn from _LIK_LOOKBACK_CHARS, and none of them can span
    a newline. Bounding the scan this way keeps the whole fix linear; searching
    from position 0 for every -lik word made it quadratic — a 180 KB article
    spent about twelve seconds here.
    """
    i = word_start
    while i > 0 and wikitext[i - 1] in _LIK_LOOKBACK_CHARS:
        i -= 1
    # One more character for the alternative's own leading token, and never
    # past the newline that opens this line.
    return max(i - 1, wikitext.rfind('\n', 0, word_start), 0)


def fix_lik_suffix_capitalization(wikitext: str) -> str:
    """
    Lowercase words ending with -lik suffix mid-sentence.

    The suffix builds a common adjective, so it is lowercase inside a sentence
    but keeps its capital wherever any other word would keep it.

    Example:
    '''Ubaydul Haq''' — Bangladeshlik teacher
    -> '''Ubaydul Haq''' — bangladeshlik teacher

    But keeps:
    '''Mogadishulik Saʼid''' — ...   (article name)
    | nationality = Bangladeshlik      (parameter value)
    [[Bangladeshlik]]                  (link target)
    """
    def replacer(match):
        word = match.group(1)
        if _LIK_KEEP_CAPITAL.search(wikitext, _keep_capital_scan_start(wikitext,
                                                                       match.start()),
                                    match.start()):
            return word
        return word[0].lower() + word[1:]

    return _LIK_WORD.sub(replacer, wikitext)


# ========== Year With Dash Fix ==========

# A calendar year is 3-4 digits, optionally the two-digit tail of a range
# (1975/76). A duration ("28 yil davomida") is not a year and keeps its space.
_YEAR_BEFORE_YIL = re.compile(
    r'(?<!\d)(\d{3,4}(?:/\d{2})?)\s+(yil(?:da|lar(?:i|da)?)?)'
)

# Words that mark the number as a length of time rather than a point in time.
_DURATION_AFTER_YIL = re.compile(
    r'\w*\s+(?:davom\w*|mobaynida|ichida|oldin|avval|keyin|burun'
    r'|muqaddam|oʻtgach|ortiq|kam|koʻp)\b'
)


def fix_year_with_dash(wikitext: str) -> str:
    """
    Add dash between year numbers and -yil suffix.

    Examples:
    2025 yil -> 2025-yil
    1975/76 yillarda -> 1975/76-yillarda

    A duration keeps its space, because -yil marks a point in time only:
    28 yil davomida -> 28 yil davomida
    100 yil oldin   -> 100 yil oldin
    """
    def replacer(match):
        if _DURATION_AFTER_YIL.match(wikitext, match.end()):
            return match.group(0)
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern 1: YYYY yil -> YYYY-yil
    wikitext = _YEAR_BEFORE_YIL.sub(replacer, wikitext)

    # Pattern 2: {{Circa|910}} yilda -> {{Circa|910}}-yilda
    wikitext = re.sub(r'(\{\{\s*Circa[^}]*\}\})\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)

    return wikitext


# ========== Fix Punctuation With SFN Templates ==========

# One citation: an {{sfn}}/{{efn}} template, or a <ref> tag of either kind.
_SFN_EFN_TPL = r'\{\{(?:sfn|efn)\s*\|[^}]*\}\}'
_REF_TAG_ANY = r'<ref[^/>]*>.*?</ref>|<ref[^>]*/\s*>'
_CITATION = r'(?:' + _SFN_EFN_TPL + r'|' + _REF_TAG_ANY + r')'

# A citation chain plus the punctuation mark in front of it. Citations may be
# separated by stray punctuation and spaces, but never by a newline: joining
# across one would swallow a paragraph break.
_CITATION_CHAIN = re.compile(
    r'(?P<lead>[.,;!?])?[ \t]*'
    r'(?P<chain>' + _CITATION + r'(?:[ \t]*[.,;!?]*[ \t]*' + _CITATION + r')*)'
    r'(?P<trail>[.,;!?]*)',
    re.IGNORECASE | re.DOTALL,
)

_ONE_CITATION = re.compile(_CITATION, re.IGNORECASE | re.DOTALL)
_HAS_SFN_EFN = re.compile(_SFN_EFN_TPL, re.IGNORECASE)


def _chain_closes_sentence(rest: str) -> bool:
    """
    True when a period should be invented after a citation chain.

    `rest` is the text following the chain. A period is only invented when
    the chain really ends a sentence: a lowercase word means the sentence is
    still running, and markup that opens something new is left alone. A
    capitalised [[link]] does start a new sentence, so it counts.
    """
    space = re.match(r'\s+', rest)
    if not space:
        return False

    after = rest[space.end():]
    if not after:
        # End of the paragraph or of the document.
        return True
    if after[0] in '.,;!?<{':
        return False
    if after.startswith('[['):
        nxt = after[2:3]
        return bool(nxt) and (nxt.isupper() or nxt.isdigit())
    if after[0] in "[ʼʻ‘’'":
        return False
    return not after[0].islower()


def fix_punctuation_with_sfn(wikitext: str) -> str:
    """
    Put the sentence punctuation after a chain of {{sfn}}/{{efn}} citations.

    A run of citations is treated as one unit rather than one hop at a time.
    The first punctuation mark found — in front of the chain, or stranded
    between two of its templates — becomes the chain's trailing mark, and any
    further marks inside the chain are dropped.

    Moving the marks one template at a time is what used to pile them up:

        Matn.{{sfn|A}}.{{sfn|B}} Yana.  ->  Matn{{sfn|A}}{{sfn|B}}.. Yana.

    An existing mark is never destroyed and a period is never invented in
    front of a word that continues the sentence.

    A chain of plain <ref> tags with no {{sfn}}/{{efn}} in it belongs to
    fix_punctuation_with_refs and is left untouched here.
    """
    def rebuild(match: re.Match) -> str:
        chain = match.group('chain')
        if not _HAS_SFN_EFN.search(chain):
            return match.group(0)

        citations = _ONE_CITATION.findall(chain)
        # findall() with a non-capturing group returns whole matches.
        joined = ''.join(citations)

        # The first mark anywhere in the chain region is the sentence's own;
        # the rest are artefacts of an earlier pass moving it template by
        # template, and go.
        marks = [match.group('lead')] if match.group('lead') else []
        marks += re.findall(r'[.,;!?]', chain)
        marks += list(match.group('trail'))

        if marks:
            return joined + marks[0]
        if _chain_closes_sentence(match.string[match.end():]):
            return joined + '.'
        return joined

    return _CITATION_CHAIN.sub(rebuild, wikitext)


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