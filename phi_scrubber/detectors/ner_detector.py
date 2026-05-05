"""Named-entity detection via spaCy. Graceful fallback if spaCy isn't installed.

Detects:
  - PERSON  -> patient/doctor (heuristic disambiguation via context)
  - ORG     -> hospital/clinic
  - GPE     -> city / state / country (geo-political entity)

Model: en_core_web_lg recommended. en_core_web_sm works but worse recall.
The caller can pass a custom nlp via load_model() to override.
"""
from __future__ import annotations

import re
from typing import Optional

from phi_scrubber.detectors.regex_detectors import RawSpan


# Cached loaded model; only loaded once per process.
_NLP: Optional[object] = None
_LOAD_ATTEMPTED = False


def _try_load_spacy(model: str = "en_core_web_lg") -> Optional[object]:
    """Attempt to load a spaCy model. Returns None if spaCy isn't installed
    or the model isn't downloaded. Never raises — graceful degradation is
    a feature here.
    """
    global _NLP, _LOAD_ATTEMPTED
    if _NLP is not None or _LOAD_ATTEMPTED:
        return _NLP
    _LOAD_ATTEMPTED = True
    try:
        import spacy  # type: ignore
    except ImportError:
        return None
    for candidate in (model, "en_core_web_lg", "en_core_web_md", "en_core_web_sm"):
        try:
            _NLP = spacy.load(candidate)
            return _NLP
        except OSError:
            continue
    return None


def _classify_person(span_text: str, doc_text: str, span_start: int) -> str:
    """Heuristic: 'Dr.', 'Doctor', 'PCP', 'attending' nearby -> DOCTOR.
    Otherwise default to PATIENT.
    """
    # Look at the 30 chars preceding the span for a doctor cue.
    window = doc_text[max(0, span_start - 30): span_start].lower()
    if re.search(r"\b(?:dr\.?|doctor|pcp|attending|md\b|physician|provider|consultant)\b", window):
        return "DOCTOR"
    return "PATIENT"


def _classify_org(span_text: str) -> str:
    """Heuristic: hospital/medical/clinic/health -> HOSPITAL. Otherwise ORG (generic)."""
    hospital_cues = ("hospital", "medical", "clinic", "health", "cancer center", "memorial")
    s = span_text.lower()
    if any(cue in s for cue in hospital_cues):
        return "HOSPITAL"
    return "ORG"


def detect_ner(text: str, model: str = "en_core_web_lg") -> list[RawSpan]:
    """Run spaCy NER. Returns empty list if spaCy unavailable.

    Person entities are sub-classified PATIENT vs DOCTOR via context cue.
    Org entities are sub-classified HOSPITAL vs ORG.
    """
    nlp = _try_load_spacy(model)
    if nlp is None:
        return []
    try:
        doc = nlp(text)
    except Exception:
        return []
    spans: list[RawSpan] = []
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            cat = _classify_person(ent.text, text, ent.start_char)
            spans.append(RawSpan(ent.start_char, ent.end_char, cat, 0.85, ent.text))
        elif ent.label_ == "ORG":
            cat = _classify_org(ent.text)
            spans.append(RawSpan(ent.start_char, ent.end_char, cat, 0.80, ent.text))
        elif ent.label_ == "GPE":
            spans.append(RawSpan(ent.start_char, ent.end_char, "CITY", 0.85, ent.text))
    return spans


def is_spacy_available() -> bool:
    """Quick capability check for callers / CLI status messages."""
    return _try_load_spacy() is not None
