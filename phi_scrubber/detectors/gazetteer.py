"""Tiny seed gazetteer for common US hospitals + cities that NER often misses.

Intentionally small — this is starter data, not a comprehensive list. Real
deployment should plug a domain-specific dictionary in.

Use case: catches edge cases like "MGH" or "Hopkins" that spaCy may tag as
ORG with low confidence, or city names like "Damascus, MD" that spaCy may
miss when not preceded by a state.
"""
from __future__ import annotations

import re

from phi_scrubber.detectors.regex_detectors import RawSpan


# Hand-picked sample. Keep alphabetized for diff sanity.
HOSPITAL_TERMS: tuple[str, ...] = (
    "Cleveland Clinic",
    "Hopkins",
    "Johns Hopkins",
    "Kaiser Permanente",
    "Mass General",
    "Massachusetts General",
    "Mayo Clinic",
    "MGH",
    "NYU Langone",
    "Shady Grove Medical",
    "Sloan Kettering",
)

# US state names + abbreviations. Used as fallback to catch "City, ST" patterns
# the NER model might miss if the model is unfamiliar with the city name.
STATE_ABBR: tuple[str, ...] = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)


def _hospital_pattern() -> re.Pattern:
    # Word-boundary match, case-insensitive
    pattern = r"\b(?:" + "|".join(re.escape(t) for t in HOSPITAL_TERMS) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def _city_state_pattern() -> re.Pattern:
    # "Word [Word] [Word], ST"  — matches up to 3 capitalized words then comma + state
    abbrs = "|".join(STATE_ABBR)
    return re.compile(
        rf"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){{0,2}}),\s({abbrs})\b"
    )


_HOSP_RE = _hospital_pattern()
_CITY_RE = _city_state_pattern()


def detect_gazetteer(text: str) -> list[RawSpan]:
    """Run gazetteer lookups. Cheap belt-and-suspenders for NER misses."""
    spans: list[RawSpan] = []
    for m in _HOSP_RE.finditer(text):
        spans.append(RawSpan(m.start(), m.end(), "HOSPITAL", 0.97, m.group(0)))
    for m in _CITY_RE.finditer(text):
        # Tag the full "City, ST" span as CITY
        spans.append(RawSpan(m.start(), m.end(), "CITY", 0.85, m.group(0)))
    return spans
