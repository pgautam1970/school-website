"""WhatsApp chat-export parser (authorized fallback path).

WhatsApp's official Business Platform API does NOT provide access to ordinary
existing class groups, and unauthorized scraping/session hijacking is forbidden.
The supported, compliant acquisition method is an administrator-authorized
chat export (WhatsApp: Group > More > Export chat > Without media), uploaded by
authorized staff or dropped into the watch folder.

This parser handles the common export line formats:
  Android:  [10/10/26, 7:45:12 PM] Sender Name: message
  Android2: 10/10/26, 7:45 AM - Sender Name: message
  iOS:      [10/10/26, 7:45:12 PM] Sender Name: message
  4-digit years, dot separators (dd.mm.yy) and 24-hour variants.
Continuation lines (multi-line messages) are appended to the previous message.
Media placeholders are captured as media_kind, not as text evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

NPT = ZoneInfo("Asia/Kathmandu")

_TS = (r"(?P<d>\d{1,4}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4}|\d{4}-\d{2}-\d{2})"
       r",?\s+(?P<t>\d{1,2}:\d{2}(?::\d{2})?)\s*(?P<ap>[APap]\.?[Mm]\.?)?")

LINE_BRACKET = re.compile(r"^\[" + _TS + r"\]\s*(?P<rest>.*)$")
LINE_PLAIN = re.compile(r"^" + _TS + r"\s*[-–]\s*(?P<rest>.*)$")
SENDER_MSG = re.compile(r"^(?P<sender>[^:]{1,80}):\s?(?P<msg>.*)$", re.DOTALL)

SYSTEM_MARKERS = (
    "messages and calls are end-to-end encrypted",
    "messages to this group are now secured",
    "created group", "added", "removed", "left", "changed the subject",
    "changed this group's settings", "missed voice call", "missed video call",
    "joined using this group's invite link",
)

MEDIA_PATTERNS = [
    (re.compile(r"^<?attached:\s*(.+)>?$", re.I), None),
    (re.compile(r"^(image|photo) omitted$", re.I), "image"),
    (re.compile(r"^video omitted$", re.I), "video"),
    (re.compile(r"^audio omitted$|^(voice message|ptt)\b", re.I), "audio"),
    (re.compile(r"^document omitted$", re.I), "document"),
    (re.compile(r"^sticker omitted$", re.I), "sticker"),
    (re.compile(r"^gif omitted$", re.I), "image"),
    (re.compile(r"^media omitted$", re.I), "media"),
]


@dataclass
class ParsedMessage:
    ts: datetime                 # timezone-aware, Asia/Kathmandu -> stored as UTC by caller
    sender: str
    text: str
    media_kind: str = ""


@dataclass
class ParseResult:
    messages: list[ParsedMessage] = field(default_factory=list)
    skipped_system: int = 0
    malformed_lines: int = 0
    first_ts: datetime | None = None
    last_ts: datetime | None = None


def _parse_date(d: str) -> tuple[int, int, int]:
    d = d.replace(".", "/").replace("-", "/")
    parts = d.split("/")
    if len(parts) != 3:
        raise ValueError(d)
    a, b, c = (int(p) for p in parts)
    if len(parts[0]) == 4:            # yyyy-mm-dd
        y, m, day = a, b, c
    else:                              # dd/mm/yy(y) — Nepal convention
        day, m, y = a, b, c
        if y < 100:
            y += 2000 if y < 70 else 1900
    return y, m, day


def _parse_ts(d: str, t: str, ap: str | None) -> datetime:
    y, m, day = _parse_date(d)
    hh, mm, *ss = (int(x) for x in t.split(":"))
    sec = ss[0] if ss else 0
    if ap:
        apn = ap.replace(".", "").upper()
        if apn == "PM" and hh < 12:
            hh += 12
        elif apn == "AM" and hh == 12:
            hh = 0
    return datetime(y, m, day, hh, mm, sec, tzinfo=NPT)


def _is_system(sender_or_msg: str) -> bool:
    low = sender_or_msg.lower()
    return any(marker in low for marker in SYSTEM_MARKERS)


def parse_export(content: str) -> ParseResult:
    result = ParseResult()
    content = content.replace("\r\n", "\n").replace("\u200e", "").replace("\u200f", "")
    pending: ParsedMessage | None = None

    for line in content.split("\n"):
        if not line.strip():
            continue
        m = LINE_BRACKET.match(line) or LINE_PLAIN.match(line)
        if m:
            if pending:
                result.messages.append(pending)
                pending = None
            try:
                ts = _parse_ts(m.group("d"), m.group("t"), m.group("ap"))
            except (ValueError, IndexError):
                result.malformed_lines += 1
                continue
            rest = m.group("rest")
            sm = SENDER_MSG.match(rest)
            if sm:
                sender, msg = sm.group("sender").strip(), sm.group("msg")
                if _is_system(msg) and (":" not in msg[:40]):
                    result.skipped_system += 1
                    continue
                media = ""
                bare = msg.strip().strip("<>\u200e\u200f").strip()
                for pat, kind in MEDIA_PATTERNS:
                    mm = pat.match(bare)
                    if mm:
                        media = kind or (mm.group(1).lower() if mm.groups() else "document")
                        msg = ""
                        break
                pending = ParsedMessage(ts=ts, sender=sender, text=msg.strip(), media_kind=media)
            else:
                # timestamped line without sender — system event
                if _is_system(rest):
                    result.skipped_system += 1
                else:
                    result.malformed_lines += 1
                continue
        else:
            # continuation of previous message OR unmatched line
            if pending is not None:
                pending.text = (pending.text + "\n" + line.strip()).strip()
            else:
                result.malformed_lines += 1

    if pending:
        result.messages.append(pending)

    for msg in result.messages:
        if result.first_ts is None or msg.ts < result.first_ts:
            result.first_ts = msg.ts
        if result.last_ts is None or msg.ts > result.last_ts:
            result.last_ts = msg.ts
    return result
