"""Tests for the context-anchored name detector.

Covers the gaps that spaCy NER misses in isolation:
  - Lowercase first names
  - Multi-person lists via "and" / "or" / comma
  - Pure prose does NOT trigger (false-positive guard)
  - Doctor prefix maps to DOCTOR category
"""
from __future__ import annotations

from phi_scrubber.detectors.anchored_name import detect_anchored_names


def _spans(text: str):
    return detect_anchored_names(text)


def _by_cat(text: str, cat: str):
    return [s for s in _spans(text) if s.category == cat]


# ---------------------------------------------------------------------------
# PATIENT prefix
# ---------------------------------------------------------------------------


def test_catches_simple_patient_name():
    [s] = _by_cat("Pt Maria Delgado seen today", "PATIENT")
    assert s.original == "Maria Delgado"


def test_catches_lowercase_first_name():
    # Regression: NER's en_core_web_lg misses lowercase "paul adejayan" because
    # OntoNotes is title-cased. The anchored detector rescues it.
    [s] = _by_cat("Pt paul adejayan Maria Delgado (MRN 00482913)", "PATIENT")
    assert s.original == "paul adejayan Maria Delgado"


def test_catches_multi_person_with_and():
    # Regression: trailing lowercase surname in a multi-person list leaked.
    [s] = _by_cat("Pt Paul Adejayan and Maria dogmligng (MRN 00482913)", "PATIENT")
    assert s.original == "Paul Adejayan and Maria dogmligng"


def test_catches_comma_separated_list():
    [s] = _by_cat("Pt Paul Adejayan, Maria Delgado, John Smith seen", "PATIENT")
    assert "Paul Adejayan" in s.original
    assert "Maria Delgado" in s.original
    assert "John Smith" in s.original


def test_catches_all_caps_prefix_and_name():
    [s] = _by_cat("PT MARIA DELGADO (MRN 00482913)", "PATIENT")
    assert s.original == "MARIA DELGADO"


def test_catches_accented_name():
    [s] = _by_cat("Pt Aisha Wiśniewska returned yesterday", "PATIENT")
    assert s.original == "Aisha Wiśniewska"


def test_catches_hyphenated_name():
    [s] = _by_cat("Pt Mary-Jane Watson-Smith arrived", "PATIENT")
    assert s.original == "Mary-Jane Watson-Smith"


def test_catches_patient_word_prefix():
    [s] = _by_cat("Patient Alice Brown was discharged", "PATIENT")
    assert s.original == "Alice Brown"


# ---------------------------------------------------------------------------
# False-positive guards
# ---------------------------------------------------------------------------


def test_prose_without_capital_does_not_match():
    # "complains" is a hard-stop word AND no capital follows — nothing to match.
    assert _by_cat("Pt complains of chest pain and shortness of breath", "PATIENT") == []


def test_all_lowercase_prose_does_not_match():
    assert _by_cat("Pt was not seen today due to no-show", "PATIENT") == []


def test_lowercase_pt_in_prose_does_not_match():
    # Case-sensitive prefix — lowercase "pt" shouldn't trigger.
    assert _by_cat("The experienced pt alice brown came by", "PATIENT") == []


def test_pts_does_not_match_as_pt():
    # "Pts" has no space before "seen" — regex requires [ \t]+ after Pt.
    assert _by_cat("Pts seen today in triage", "PATIENT") == []


def test_pt_without_following_name_returns_nothing():
    # Nothing after the prefix at all.
    assert _by_cat("Pt ", "PATIENT") == []


def test_stop_word_terminates_span():
    # "Smith returned" — "returned" is a hard stop, so only "Smith" is captured.
    [s] = _by_cat("Pt Smith returned to the clinic", "PATIENT")
    assert s.original == "Smith"


# ---------------------------------------------------------------------------
# DOCTOR prefix
# ---------------------------------------------------------------------------


def test_catches_doctor_with_period():
    [s] = _by_cat("seen by Dr. Alan Brooks on 03/14", "DOCTOR")
    assert s.original == "Alan Brooks"


def test_catches_doctor_without_period():
    [s] = _by_cat("Dr Alan Brooks reviewed the case", "DOCTOR")
    assert s.original == "Alan Brooks"


def test_catches_all_caps_doctor():
    [s] = _by_cat("DR BROOKS was consulted", "DOCTOR")
    assert s.original == "BROOKS"


def test_doctor_span_stops_at_preposition():
    # "on" is a hard stop — "Alan Brooks" is captured, "on 03/14" is not.
    [s] = _by_cat("seen by Dr. Alan Brooks on 03/14/2026 at the clinic", "DOCTOR")
    assert s.original == "Alan Brooks"


# ---------------------------------------------------------------------------
# Span offsets
# ---------------------------------------------------------------------------


def test_span_offsets_cover_only_the_name_not_prefix():
    text = "Pt Maria Delgado came in"
    [s] = _by_cat(text, "PATIENT")
    assert text[s.start:s.end] == "Maria Delgado"
    assert text[s.start - 1] == " "  # the space after "Pt"


def test_multiple_prefixes_in_one_document():
    text = "Pt Maria Delgado seen by Dr. Alan Brooks."
    results = _spans(text)
    patients = [s for s in results if s.category == "PATIENT"]
    doctors = [s for s in results if s.category == "DOCTOR"]
    assert len(patients) == 1
    assert len(doctors) == 1
    assert patients[0].original == "Maria Delgado"
    assert doctors[0].original == "Alan Brooks"


def test_confidence_is_below_ner_threshold():
    # Important: NER wins on identical spans. Length wins before confidence,
    # but when spans tie exactly, NER's 0.85 beats this detector's 0.75.
    text = "Pt Maria Delgado"
    [s] = _by_cat(text, "PATIENT")
    assert s.confidence < 0.85
