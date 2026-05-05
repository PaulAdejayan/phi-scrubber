"""Tests for per-patient deterministic date shifting."""
from __future__ import annotations

from datetime import datetime, timedelta

from phi_scrubber.date_shifter import (
    MAX_SHIFT_DAYS,
    offset_for_patient,
    shift_date_string,
    shift_datetime,
)


def test_offset_in_range():
    for pid in ["pt_001", "pt_002", "alice", "bob", "x" * 100]:
        off = offset_for_patient(pid)
        assert -MAX_SHIFT_DAYS <= off <= MAX_SHIFT_DAYS


def test_offset_deterministic_per_patient():
    assert offset_for_patient("pt_001") == offset_for_patient("pt_001")


def test_different_patients_likely_different_offsets():
    # Trivially possible to collide, but extremely unlikely for these
    offsets = {offset_for_patient(f"pt_{i:03d}") for i in range(20)}
    assert len(offsets) > 5  # at least some variety


def test_intervals_preserved_per_patient():
    """The whole point: same patient -> intervals survive."""
    pid = "pt_001"
    admission = datetime(2026, 3, 14)
    discharge = datetime(2026, 3, 19)
    shifted_admission = shift_datetime(admission, pid)
    shifted_discharge = shift_datetime(discharge, pid)
    assert shifted_discharge - shifted_admission == timedelta(days=5)


def test_shift_string_returns_iso():
    out = shift_date_string("3/14/2026", "pt_001")
    assert out is not None
    # Format YYYY-MM-DD
    assert len(out) == 10
    assert out[4] == "-" and out[7] == "-"


def test_shift_string_unparseable_returns_none():
    assert shift_date_string("not a date", "pt_001") is None
