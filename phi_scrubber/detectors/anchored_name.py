"""Context-anchored name detection.

Complementary to the spaCy NER detector. Catches names that NER misses:
  - Lowercase first names ("Pt paul adejayan Maria Delgado")
  - Multi-person lists with mixed casing ("Pt Paul Adejayan and Maria dogmligng")
  - Non-English or heavily accented names the PERSON classifier doesn't recognize

Triggers ONLY after a strong contextual prefix (Pt / PT / Patient / PATIENT / Dr /
DR, with optional trailing period). The prefix provides the anchor; without one,
this detector does not fire — which keeps precision high.

Confidence is set below NER's 0.85 so NER wins on overlap when both detectors
fire. But span length wins before confidence in scrubber.merge_spans, so a longer
anchored span beats a shorter NER span (desired for the "paul adejayan Maria
Delgado" case where NER catches only the capitalized half).
"""
from __future__ import annotations

import re

from phi_scrubber.detectors.regex_detectors import RawSpan

# Case-sensitive prefix patterns. Avoids false positives on common words that
# share these letters in lowercase prose (e.g. "pt" appearing in "experienced").
_PATIENT_PREFIX_RE = re.compile(r"\b(?:Pt|PT|Patient|PATIENT)\.?[ \t]+")
_DOCTOR_PREFIX_RE = re.compile(r"\b(?:Dr|DR)\.?[ \t]+")

# A single name-like word: unicode letters, apostrophes, hyphens, combining marks.
# Length cap guards against pathological inputs.
_WORD_RE = re.compile(r"[^\W\d_][\w'’\-]{0,30}", re.UNICODE)

# Prose words that cannot be part of a name — act as hard stops. If encountered,
# the name sequence ends immediately (and the stop word is NOT included).
# Not exhaustive — only words common enough in clinical narrative to matter.
_HARD_STOP = frozenset({
    # verbs clinicians use next to patient / doctor names
    "complains", "complained", "reports", "reported", "presents", "presented",
    "returns", "returned", "arrived", "arrives", "seen", "visited", "visits",
    "called", "receives", "received", "requires", "needs", "needed",
    "stated", "states", "denies", "denied", "admits", "admitted",
    "noted", "notes", "describes", "described", "came",
    "reviewed", "reviews", "examined", "examines", "discharged", "discharges",
    "treated", "treats", "prescribed", "prescribes", "consulted", "consults",
    "ordered", "orders", "assessed", "assesses", "evaluated", "evaluates",
    # auxiliary verbs
    "was", "were", "is", "are", "has", "had", "have",
    # pronouns / determiners that signal clause break
    "who", "that", "which", "whose", "these", "those", "this",
    # prepositions that typically appear after a name sequence
    "on", "at", "for", "with", "from", "by", "in", "to", "of", "about",
    "after", "before", "during", "since", "while", "until",
    # time words
    "today", "yesterday", "tomorrow",
    # articles
    "a", "an", "the",
})

# Connector words that CAN appear between names in a multi-person list.
_CONNECTORS = frozenset({"and", "or"})

_MAX_WORDS = 7


def _collect_name_span(text: str, start_idx: int) -> int | None:
    """Scan forward from start_idx, collecting a sequence of name-like words.

    Returns the end offset (exclusive) of the collected name, or None if no
    valid name was found (no words, or the sequence contained no capitalized
    word — which prevents pure-prose over-match like "Pt complains of pain").
    """
    i = start_idx
    end_offset: int | None = None
    saw_cap = False
    words_matched = 0

    while words_matched < _MAX_WORDS and i < len(text):
        # Allow a comma + optional whitespace between name groups ("Paul, Maria").
        if i < len(text) and text[i] == ",":
            i += 1
        while i < len(text) and text[i] in " \t":
            i += 1

        m = _WORD_RE.match(text, i)
        if not m:
            break

        word = m.group(0)
        word_lower = word.lower()

        # Hard stop: this word cannot be part of a name. End here, exclude it.
        if word_lower in _HARD_STOP:
            break

        # Connectors ("and", "or") only count if followed by another name word.
        if word_lower in _CONNECTORS:
            peek = m.end()
            while peek < len(text) and text[peek] in " \t":
                peek += 1
            peek_m = _WORD_RE.match(text, peek)
            if peek_m is None or peek_m.group(0).lower() in _HARD_STOP:
                break
            i = m.end()
            words_matched += 1
            continue

        # A real name word. Track whether we've seen a capital anywhere.
        if word[:1].isupper():
            saw_cap = True

        end_offset = m.end()
        i = m.end()
        words_matched += 1

    if end_offset is None or not saw_cap:
        return None
    return end_offset


def _scan_prefix(
    text: str,
    prefix_re: re.Pattern[str],
    category: str,
    confidence: float,
) -> list[RawSpan]:
    out: list[RawSpan] = []
    for pm in prefix_re.finditer(text):
        name_end = _collect_name_span(text, pm.end())
        if name_end is None:
            continue
        # Span covers only the NAME, not the prefix. The scrubber replaces this
        # range with [PATIENT_N] / [DOCTOR_N]; the "Pt " / "Dr. " stays visible.
        out.append(RawSpan(
            start=pm.end(),
            end=name_end,
            category=category,
            confidence=confidence,
            original=text[pm.end():name_end],
        ))
    return out


def detect_anchored_names(text: str) -> list[RawSpan]:
    """Public entry point. Returns spans tagged PATIENT or DOCTOR."""
    spans: list[RawSpan] = []
    spans.extend(_scan_prefix(text, _PATIENT_PREFIX_RE, "PATIENT", 0.75))
    spans.extend(_scan_prefix(text, _DOCTOR_PREFIX_RE, "DOCTOR", 0.75))
    return spans
