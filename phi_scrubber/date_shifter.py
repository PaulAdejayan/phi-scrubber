"""Per-patient consistent date shifting.

Safe Harbor §164.514(b)(2)(C) requires removing all dates more granular than
year. But research utility often requires preserved INTERVALS (admission ->
discharge). The accepted compromise:

    Shift every date for one patient by the SAME random offset in [-180, 180].

Different patients get different offsets. Same patient -> same offset, every
time, for the duration of the dataset. Intervals survive; absolute dates
become meaningless.

We seed the offset by patient_id so the offset is deterministic per patient
across runs without storing a side-table. If you need cryptographic
unlinkability, swap the hash for HMAC with a secret key.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser as date_parser


# Maximum shift in days, in either direction.
MAX_SHIFT_DAYS = 180


def offset_for_patient(patient_id: str) -> int:
    """Deterministic offset in [-MAX_SHIFT_DAYS, +MAX_SHIFT_DAYS].

    Uses SHA-256 of the patient_id, takes the first 4 bytes as an int, and
    maps to range [-180, 180].
    """
    h = hashlib.sha256(patient_id.encode("utf-8")).digest()
    raw = int.from_bytes(h[:4], "big")
    span = MAX_SHIFT_DAYS * 2 + 1
    return (raw % span) - MAX_SHIFT_DAYS


def shift_date_string(text: str, patient_id: str) -> Optional[str]:
    """Shift a date string by this patient's deterministic offset.

    Preserves the INPUT'S surface format wherever possible (numeric vs spelled
    month, year width, etc.) — though the simplified MVP just emits ISO
    YYYY-MM-DD output. Document scrubbers using this should typically REPLACE
    the date with [DATE_SHIFTED] tag, not the shifted text — the actual
    shifted dates live only in the audit log.

    Returns None if the input couldn't be parsed.
    """
    try:
        dt = date_parser.parse(text, fuzzy=False)
    except (ValueError, OverflowError):
        return None
    shifted = dt + timedelta(days=offset_for_patient(patient_id))
    return shifted.strftime("%Y-%m-%d")


def shift_datetime(dt: datetime, patient_id: str) -> datetime:
    """Pure datetime shift — for callers that already have a datetime."""
    return dt + timedelta(days=offset_for_patient(patient_id))
