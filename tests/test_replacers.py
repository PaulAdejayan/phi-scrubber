"""Tests for tag-assignment consistency."""
from __future__ import annotations

from phi_scrubber.replacers import TagAssigner


def test_same_input_same_tag():
    a = TagAssigner()
    t1 = a.tag_for("PATIENT", "John Smith")
    t2 = a.tag_for("PATIENT", "John Smith")
    assert t1 == t2 == "[PATIENT_1]"


def test_different_patients_get_different_tags():
    a = TagAssigner()
    t1 = a.tag_for("PATIENT", "John Smith")
    t2 = a.tag_for("PATIENT", "Jane Doe")
    assert t1 == "[PATIENT_1]"
    assert t2 == "[PATIENT_2]"


def test_doctor_and_patient_independent_counters():
    a = TagAssigner()
    p = a.tag_for("PATIENT", "John")
    d = a.tag_for("DOCTOR", "Chen")
    assert p == "[PATIENT_1]"
    assert d == "[DOCTOR_1]"


def test_normalization_handles_whitespace_and_case():
    a = TagAssigner()
    t1 = a.tag_for("DOCTOR", "Dr. Sarah Chen")
    t2 = a.tag_for("DOCTOR", "dr.   sarah  chen")
    assert t1 == t2


def test_non_numbered_categories_share_one_tag():
    a = TagAssigner()
    t1 = a.tag_for("PHONE", "(301) 555-0123")
    t2 = a.tag_for("PHONE", "(301) 555-9999")
    # Both PHONE; bare tag, not numbered
    assert t1 == "[PHONE]"
    assert t2 == "[PHONE]"


def test_date_shifted_by_default():
    a = TagAssigner()
    assert a.tag_for("DATE", "3/14/2026") == "[DATE_SHIFTED]"


def test_date_redacted_when_shift_disabled():
    a = TagAssigner(shift_dates=False)
    assert a.tag_for("DATE", "3/14/2026") == "[DATE]"


def test_audit_trail_captured():
    a = TagAssigner()
    a.tag_for("PATIENT", "John")
    a.tag_for("DOCTOR", "Chen")
    a.tag_for("PATIENT", "John")  # same — no new entry
    audit = a.all_assignments()
    assert len(audit) == 2  # one PATIENT, one DOCTOR
