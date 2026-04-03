"""
Transliterate polytonic Ancient Greek to phonetic Latin script.

Uses reconstructed mid-2nd century CE Koine pronunciation
as spoken in western Asia Minor (Sardis), suitable for feeding
to TTS engines that cannot read Greek Unicode.

Based on epigraphic evidence and Buth's "Living Koine" reconstruction.
"""

import re
import unicodedata


# Strip all Greek diacritics (accents, breathing, iota subscript)
# and return the base letter + whether it had iota subscript
def _strip_diacritics(char: str) -> tuple[str, bool]:
    """Return (base_char, had_iota_subscript) after removing diacritics."""
    has_ypogegrammeni = False
    decomposed = unicodedata.normalize("NFD", char)
    cleaned = []
    for c in decomposed:
        cat = unicodedata.category(c)
        name = unicodedata.name(c, "")
        if "YPOGEGRAMMENI" in name or "PROSGEGRAMMENI" in name:
            has_ypogegrammeni = True
        elif cat == "Mn":
            # Skip combining marks (accents, breathing)
            continue
        else:
            cleaned.append(c)
    base = unicodedata.normalize("NFC", "".join(cleaned))
    return base, has_ypogegrammeni


# Voiceless consonants (for αυ/ευ → af/ef rule)
VOICELESS = set("πτκφθχσξψ")

# Single-letter mappings (after diacritics stripped, lowercase)
SINGLE = {
    "α": "a",
    "β": "v",       # bilabial fricative /β/ — "v" is closest Latin approx
    "γ": "gh",      # velar fricative /ɣ/
    "δ": "d",       # still a stop in 2nd c.
    "ε": "e",
    "ζ": "z",
    "η": "e",       # open /ɛː/ — not yet /i/
    "θ": "th",
    "ι": "i",
    "κ": "k",
    "λ": "l",
    "μ": "m",
    "ν": "n",
    "ξ": "ks",
    "ο": "o",
    "π": "p",
    "ρ": "r",
    "σ": "s",
    "ς": "s",
    "τ": "t",
    "υ": "y",       # fronted /y/ as in French "lune"
    "φ": "f",
    "χ": "kh",
    "ψ": "ps",
    "ω": "o",       # merged with ο by this period
}

# Digraph / diphthong mappings (checked before single letters)
# αυ and ευ are handled specially (voiced/voiceless context)
DIGRAPHS = {
    "αι": "e",      # merged with ε
    "ει": "i",      # merged with ι
    "οι": "y",      # fronted /y/, same as υ
    "ου": "u",
    "υι": "yi",     # rare diphthong
    "γγ": "ng",     # /ŋg/
    "γκ": "nk",     # /ŋk/
    "γχ": "nkh",    # /ŋx/
    "γξ": "nks",    # /ŋks/
    "μπ": "mb",
    "ντ": "nd",
}


def transliterate(text: str) -> str:
    """Convert polytonic Greek text to phonetic Latin-alphabet spelling."""
    # Remove editorial brackets but keep content
    text = re.sub(r"[\[\]]", "", text)

    # Normalize to NFC first
    text = unicodedata.normalize("NFC", text)

    result = []
    i = 0
    chars = list(text)
    n = len(chars)

    while i < n:
        ch = chars[i]

        # Pass through non-Greek characters (punctuation, spaces, numbers)
        if not _is_greek(ch):
            # Convert Greek punctuation
            if ch == "·":
                result.append(";")
            elif ch == ";":  # Greek question mark
                result.append("?")
            elif ch == "\u0374" or ch == "ʹ":  # numeral sign
                pass
            elif ch in "\u1fbd\u1fbf\u1ffe\u1fce\u1fde\u1fcd\u1fdd\u2019\u02bc\u0313\u0314\u0343\u1fbf\u2018\u0027\u2032":
                # koronis / breathing marks / apostrophe (elision) — skip
                pass
            elif ch == "\u1fbe":  # iota subscript as separate char — silent
                pass
            else:
                result.append(ch)
            i += 1
            continue

        # Skip Greek modifier/breathing characters that are standalone
        if ch in "\u1fbd\u1fbf\u1ffe\u1fce\u1fde\u1fcd\u1fdd\u0343\u1fbe":
            i += 1
            continue

        # Strip diacritics from current char
        base, has_sub = _strip_diacritics(ch)
        base_lower = base.lower()
        is_upper = base != base.lower()

        # Look ahead for digraphs (need to strip next char too)
        if i + 1 < n and _is_greek(chars[i + 1]):
            next_base, next_sub = _strip_diacritics(chars[i + 1])
            next_lower = next_base.lower()
            pair = base_lower + next_lower

            # Handle αυ / ευ (context-dependent)
            if pair in ("αυ", "ευ"):
                vowel_part = "a" if base_lower == "α" else "e"
                # Check what follows the diphthong
                following = _peek_base(chars, i + 2)
                if following in VOICELESS or following is None:
                    cons = "f"
                else:
                    cons = "v"
                out = vowel_part + cons
                if is_upper:
                    out = out.capitalize()
                result.append(out)
                i += 2
                continue

            # Handle other digraphs
            if pair in DIGRAPHS:
                out = DIGRAPHS[pair]
                if is_upper:
                    out = out.capitalize()
                result.append(out)
                if has_sub:
                    pass  # iota subscript silent by 2nd c.
                i += 2
                continue

            # Handle γ before front vowels → /j/ (palatalized)
            if base_lower == "γ" and next_lower in ("ε", "η", "ι"):
                out = "y"
                if is_upper:
                    out = out.capitalize()
                result.append(out)
                i += 1
                continue

        # Handle ρρ → rr, λλ → ll, etc. (gemination)
        if i + 1 < n:
            next_base2, _ = _strip_diacritics(chars[i + 1])
            if base_lower == next_base2.lower() and base_lower in SINGLE:
                out = SINGLE[base_lower] * 2
                if is_upper:
                    out = out[0].upper() + out[1:]
                result.append(out)
                i += 2
                continue

        # Single letter
        if base_lower in SINGLE:
            out = SINGLE[base_lower]
            if is_upper:
                out = out.capitalize()
            result.append(out)
            if has_sub:
                pass  # iota subscript silent
        else:
            # Unknown character — pass through
            result.append(ch)

        i += 1

    return "".join(result)


def _is_greek(ch: str) -> bool:
    """Check if character is a Greek letter."""
    try:
        name = unicodedata.name(ch, "")
        return "GREEK" in name
    except ValueError:
        return False


def _peek_base(chars: list, idx: int) -> str | None:
    """Peek at the base (diacritics-stripped) lowercase letter at idx."""
    if idx >= len(chars):
        return None
    base, _ = _strip_diacritics(chars[idx])
    low = base.lower()
    if low in SINGLE or low in ("α", "ε", "η", "ι", "ο", "υ", "ω"):
        return low
    return None


def simplify_greek(text: str) -> str:
    """Strip polytonic diacritics but keep Greek alphabet.

    Removes accents, breathing marks, iota subscripts, editorial brackets,
    and standalone modifier characters that TTS engines misread as symbol
    names. Keeps the base Greek letters so the TTS Greek model can
    pronounce them natively.
    """
    # Remove editorial brackets but keep content
    text = re.sub(r"[\[\]]", "", text)
    text = unicodedata.normalize("NFC", text)

    result = []
    for ch in text:
        # Remove standalone Greek modifier characters
        if ch in "\u1fbd\u1fbf\u1ffe\u1fce\u1fde\u1fcd\u1fdd\u0343\u1fbe":
            continue

        if _is_greek(ch):
            base, _ = _strip_diacritics(ch)
            result.append(base)
        else:
            # Convert Greek punctuation to standard
            if ch == "·":
                result.append(",")
            elif ch == ";":  # Greek question mark
                result.append("?")
            else:
                result.append(ch)

    return "".join(result)


def transliterate_file(input_path: str, output_path: str, mode: str = "latin") -> None:
    """Convert a Greek text file for TTS consumption.

    mode="latin"  — full Latin-alphabet phonetic transliteration
    mode="greek"  — simplified Greek (strip diacritics, keep alphabet)
    """
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    if mode == "greek":
        result = simplify_greek(text)
    else:
        result = transliterate(text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
