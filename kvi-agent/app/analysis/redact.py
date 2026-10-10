"""Privacy — redaction of unnecessary personal identifiers.

Applied to text shown in summaries/emails (text_redacted). The original text
remains in the database, access-controlled by role (see api/routes_archive.py).
Phone numbers and emails are always redacted in summaries; names are redacted
in report bodies unless needed for a specific follow-up (spec 11).
"""
from __future__ import annotations

import re

# Nepali mobile/landline patterns, with or without +977
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?977[-\s]?)?(?:9[678]\d[-\s]?\d{3}[-\s]?\d{4}|0\d{1,2}[-\s]?\d{6,7})(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Long digit sequences that look like ID/registration numbers (10+ digits)
LONG_ID_RE = re.compile(r"(?<!\d)\d{10,}(?!\d)")
# Simple address pattern: ward/tole references
ADDRESS_RE = re.compile(r"(?:ward|वडा|tole|टोल)\s*[-–]?\s*\d+", re.IGNORECASE)


def redact_text(text: str, *, redact_names: bool = False,
                known_names: list[str] | None = None) -> str:
    """Return a redaction-safe copy for summaries and email."""
    t = text or ""
    t = EMAIL_RE.sub("[email redacted]", t)
    t = PHONE_RE.sub("[phone redacted]", t)
    t = LONG_ID_RE.sub("[id redacted]", t)
    t = ADDRESS_RE.sub("[address redacted]", t)
    if redact_names and known_names:
        for name in sorted(known_names, key=len, reverse=True):
            if len(name) >= 3:
                t = re.sub(re.escape(name), "[name redacted]", t, flags=re.IGNORECASE)
    return t


def text_is_safe(text: str) -> bool:
    """True when no phone/email/long-id patterns are present."""
    t = text or ""
    return not (PHONE_RE.search(t) or EMAIL_RE.search(t) or LONG_ID_RE.search(t))
