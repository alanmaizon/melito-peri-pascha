"""Post-processing: clean OCR output to polytonic Greek text.

Minimal filtering — Latin lookalike replacement and Unicode normalization only.
Manual trimming of headers, footnotes, and line numbers is preferred.
"""

import re
import unicodedata


# Latin characters commonly confused with Greek by OCR engines.
LATIN_TO_GREEK: dict[str, str] = {
    "A": "Α", "B": "Β", "E": "Ε", "H": "Η", "I": "Ι", "K": "Κ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ",
    "Y": "Υ", "Z": "Ζ",
    "a": "α", "e": "ε", "i": "ι", "k": "κ", "n": "ν", "o": "ο",
    "p": "ρ", "u": "υ", "v": "ν", "w": "ω", "x": "χ", "y": "υ",
}


def replace_latin_lookalikes(text: str) -> str:
    """Swap Latin characters that OCR commonly substitutes for Greek glyphs."""
    return "".join(LATIN_TO_GREEK.get(ch, ch) for ch in text)


def normalize_unicode(text: str) -> str:
    """Normalize to NFC to merge combining diacritics into precomposed forms."""
    return unicodedata.normalize("NFC", text)


def collapse_whitespace(text: str) -> str:
    """Collapse runs of spaces and blank lines."""
    lines = text.split("\n")
    cleaned = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))


def postprocess(text: str) -> str:
    """Minimal post-processing: lookalike fix → NFC normalize → clean whitespace."""
    text = replace_latin_lookalikes(text)
    text = normalize_unicode(text)
    text = collapse_whitespace(text)
    return text.strip()
