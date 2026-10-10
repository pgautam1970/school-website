"""Stage 2 — Normalization.

Unicode normalization, language identification (English / Nepali Devanagari /
Romanized Nepali / code-switched mixed) and text hygiene. The ORIGINAL text is
always preserved by callers; normalization produces a parallel analysis copy.
"""
from __future__ import annotations

import re
import unicodedata

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# Common Romanized-Nepali tokens seen in school groups (not English words).
ROMANIZED_NEPALI_TOKENS = {
    "aaja", "ajha", "bhola", "bholi", "ke", "kina", "kasari", "kahile", "ko",
    "ho", "hola", "garna", "garyo", "garne", "garibakhnu", "bakhnu", "bhayo",
    "cha", "chha", "chaina", "huncha", "hola", "tapai", "tapain", "hami",
    "timi", "malai", "timilai", "ghar", "khaana", "khana", "paani", "skul",
    "sikne", "padhaune", "padhai", "pariksha", "grihakarya", "karyakram",
    "baithak", "sirsir", "didi", "bhai", "namaste", "dhanyabad", "maaf",
    "mitho", "ramro", "naramro", "thik", "thikai", "baje", "bihana", "belka",
    "beluki", "raati", "din", "hijo", "parkhi", "padhaunu", "lekhnu", "lyauxu",
    "pathauxu", "pathaunu", "sanga", "sangai", "bujhne", "bujhaune", "sochne",
    "aunu", "aaunu", "jaanu", "jane", "basne", "sit", "buseko", "heri",
    "herne", "heridinu", "milera", "sahayog", "sujanu", "chito", "dhilo",
}

# Normalize common educational abbreviations / local terminology (analysis copy only).
ABBREV_MAP = {
    r"\bh\/w\b": "homework", r"\bhw\b": "homework", r"\basgn\b": "assignment",
    r"\bptm\b": "parent teacher meeting", r"\btlm\b": "teaching learning material",
    r"\bcls\b": "class", r"\btchr\b": "teacher", r"\bstud\b": "student",
    r"\bexam\b": "examination", r"\bassgn\b": "assessment", r"\bsec\b": "section",
    r"\bkvi\b": "kashyap vidyapeeth", r"\bvs\b": "versus",
}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def strip_control(text: str) -> str:
    """Remove control characters except newline/tab. Treat input as untrusted."""
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")


def normalize_text(text: str) -> str:
    """Produce an analysis-friendly copy (original must be stored separately)."""
    t = strip_control(nfc(text or ""))
    t = t.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")  # ZWJ/ZWNJ noise
    low = t.lower()
    for pat, repl in ABBREV_MAP.items():
        low = re.sub(pat, repl, low)
    low = re.sub(r"[ \t]+", " ", low).strip()
    return low


def detect_language(text: str) -> str:
    """Return 'ne' (Devanagari), 'ne-roman', 'mixed', or 'en'."""
    t = nfc(text or "")
    dev_chars = len(DEVANAGARI_RE.findall(t))
    letters = sum(1 for c in t if c.isalpha())
    if letters == 0:
        return "en"
    dev_ratio = dev_chars / max(letters, 1)
    ascii_tokens = re.findall(r"[a-zA-Z]+", t.lower())
    nep_tokens = sum(1 for w in ascii_tokens if w in ROMANIZED_NEPALI_TOKENS)
    nep_ratio = nep_tokens / max(len(ascii_tokens), 1)
    if dev_ratio > 0.6:
        return "ne"
    if dev_ratio > 0.15 or (nep_ratio > 0.25 and dev_ratio > 0):
        return "mixed"
    if nep_ratio >= 0.2 and len(ascii_tokens) >= 3:
        return "ne-roman"
    return "en"
