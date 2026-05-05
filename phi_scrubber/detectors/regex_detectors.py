"""Regex-based PHI detectors.

Each detector returns a list of (start, end, category, confidence, original)
spans against a single text input. Categories are HIPAA Safe Harbor identifier
groups; tags emitted by the replacer downstream.

Confidence is a heuristic in [0, 1]. Caller may use it to break ties when
multiple detectors hit overlapping spans (longest-match wins by default).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RawSpan:
    start: int
    end: int
    category: str
    confidence: float
    original: str


# ---------------------------------------------------------------------------
# Patterns. Compiled once at import time.
# ---------------------------------------------------------------------------

# Phone — handles:
#   (301) 555-0123, 301-555-0123, 301.555.0123, +1 301 555 0123,
#   3015550123 (10 digit run, but only when not part of a longer ID)
_PHONE_RE = re.compile(
    r"""
    (?<![\d-])              # not part of a longer digit string
    (?:\+?1[\s.-]?)?        # optional +1 or 1
    (?:\(\d{3}\)|\d{3})     # area code
    [\s.-]?\d{3}            # exchange
    [\s.-]?\d{4}            # subscriber
    (?!\d)                  # not followed by another digit
    """,
    re.VERBOSE,
)

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# SSN — XXX-XX-XXXX. Avoid matching when surrounded by other digits.
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

# URL — http(s):// or www.
_URL_RE = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"']+",
    re.IGNORECASE,
)

# IP v4 (with sanity check on octet ranges done later)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# ZIP code — 5 digit or ZIP+4. Require word boundary on left, optional state/punct on right.
# Also avoid matching when preceded by '$' or surrounded by other identifier-y digits.
_ZIP_RE = re.compile(
    r"""
    (?<![\d$])              # not part of a money amount or longer digit run
    \b\d{5}(?:-\d{4})?\b    # 5-digit or ZIP+4
    (?!\d)
    """,
    re.VERBOSE,
)

# MRN / account / generic medical record numbers.
# Triggers when preceded by an identifier label.
_ID_LABEL_RE = re.compile(
    r"""
    \b(?:MRN|MR\#|MR\sNumber|Medical\sRecord(?:\sNumber)?|Account|Acct|
       Account\sNumber|Member\sID|Health\sPlan|HPID|Encounter|License|
       License\sNumber|License\s\#|DL\#|DL\sNumber|Patient\sID|
       Pt\sID|Member\sNumber|Visit\sID)
    \s*[:#\-]?\s*([A-Z0-9-]{4,20})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Dates. Captures common US formats:
#   3/14/2026, 03-14-2026, 3/14/26, March 14 2026, 14 March 2026,
#   2026-03-14 (ISO), Mar 14 2026
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
)
_DATE_RE = re.compile(
    rf"""
    \b(?:
        # Numeric MM/DD/YYYY or M/D/YY (slash, dash, dot separators)
        (?:0?[1-9]|1[0-2])[/.\-](?:0?[1-9]|[12]\d|3[01])[/.\-](?:\d{{2}}|\d{{4}})
      | # ISO YYYY-MM-DD
        (?:19|20)\d{{2}}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])
      | # Month DD, YYYY  /  Month DD YYYY
        (?:{_MONTHS})\s+(?:0?[1-9]|[12]\d|3[01])(?:,)?\s+(?:19|20)\d{{2}}
      | # DD Month YYYY
        (?:0?[1-9]|[12]\d|3[01])\s+(?:{_MONTHS})\s+(?:19|20)\d{{2}}
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _valid_ip(text: str) -> bool:
    """Validate that all octets are 0-255."""
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Public detector functions
# ---------------------------------------------------------------------------


def detect_phone(text: str) -> list[RawSpan]:
    return [
        RawSpan(m.start(), m.end(), "PHONE", 0.95, m.group(0))
        for m in _PHONE_RE.finditer(text)
    ]


def detect_email(text: str) -> list[RawSpan]:
    return [
        RawSpan(m.start(), m.end(), "EMAIL", 0.99, m.group(0))
        for m in _EMAIL_RE.finditer(text)
    ]


def detect_ssn(text: str) -> list[RawSpan]:
    return [
        RawSpan(m.start(), m.end(), "SSN", 0.99, m.group(0))
        for m in _SSN_RE.finditer(text)
    ]


def detect_url(text: str) -> list[RawSpan]:
    out = []
    for m in _URL_RE.finditer(text):
        # strip trailing punctuation common in prose: ., , ; : )
        end = m.end()
        s = m.group(0)
        while s and s[-1] in ".,;:)":
            s = s[:-1]
            end -= 1
        if s:
            out.append(RawSpan(m.start(), end, "URL", 0.95, s))
    return out


def detect_ip(text: str) -> list[RawSpan]:
    out = []
    for m in _IP_RE.finditer(text):
        if _valid_ip(m.group(0)):
            out.append(RawSpan(m.start(), m.end(), "IP", 0.90, m.group(0)))
    return out


def detect_zip(text: str) -> list[RawSpan]:
    return [
        RawSpan(m.start(), m.end(), "ZIP", 0.70, m.group(0))
        for m in _ZIP_RE.finditer(text)
    ]


def detect_id(text: str) -> list[RawSpan]:
    """Capture only the ID payload (group 1), not the label."""
    out = []
    for m in _ID_LABEL_RE.finditer(text):
        if m.group(1):
            out.append(
                RawSpan(m.start(1), m.end(1), "ID", 0.92, m.group(1))
            )
    return out


def detect_date(text: str) -> list[RawSpan]:
    return [
        RawSpan(m.start(), m.end(), "DATE", 0.93, m.group(0))
        for m in _DATE_RE.finditer(text)
    ]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

ALL_DETECTORS = [
    detect_phone,
    detect_email,
    detect_ssn,
    detect_url,
    detect_ip,
    detect_zip,
    detect_id,
    detect_date,
]


def detect_all_regex(text: str) -> list[RawSpan]:
    """Run every regex detector, return all spans sorted by start offset."""
    spans: list[RawSpan] = []
    for fn in ALL_DETECTORS:
        spans.extend(fn(text))
    spans.sort(key=lambda s: (s.start, -s.end))
    return spans
