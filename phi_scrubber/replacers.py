"""Replacement-tag generation with per-document consistency.

Goals:
  - Same entity (same surface form, same category) -> same tag throughout doc
  - PATIENT_1 / DOCTOR_1 / DOCTOR_2 etc. — numbered for distinguishable people
  - Single-instance categories (PHONE, EMAIL, etc.) -> bare tags like [PHONE]
  - Tags are bracketed and uppercased so downstream tooling can parse them
"""
from __future__ import annotations

from dataclasses import dataclass


# Categories that get numbered when more than one distinct instance appears.
# Categories NOT in this set just get the bare tag every time.
NUMBERED_CATEGORIES: frozenset[str] = frozenset({"PATIENT", "DOCTOR", "ORG", "HOSPITAL"})


@dataclass
class TagAssignment:
    tag: str
    original: str
    category: str


class TagAssigner:
    """Assigns consistent tags across a single document.

    Same (category, normalized-original) -> same tag.
    """

    def __init__(self, *, shift_dates: bool = True) -> None:
        self._counter: dict[str, int] = {}
        # key: (category, normalized_original) -> tag
        self._mapping: dict[tuple[str, str], str] = {}
        self._shift_dates = shift_dates

    @staticmethod
    def _normalize(s: str) -> str:
        # Casefold + collapse whitespace; we treat "Dr. Chen" / "Dr.  Chen" as same.
        return " ".join(s.split()).casefold()

    def tag_for(self, category: str, original: str) -> str:
        """Return the tag for a given (category, original) pair, assigning
        a fresh tag the first time we see it.
        """
        # Special case: DATE — shifted vs redacted is a CALLER concern; we
        # just emit DATE_SHIFTED or DATE depending on assigner config.
        if category == "DATE":
            return "[DATE_SHIFTED]" if self._shift_dates else "[DATE]"

        norm = self._normalize(original)
        key = (category, norm)
        if key in self._mapping:
            return self._mapping[key]

        if category in NUMBERED_CATEGORIES:
            self._counter[category] = self._counter.get(category, 0) + 1
            tag = f"[{category}_{self._counter[category]}]"
        else:
            tag = f"[{category}]"
        self._mapping[key] = tag
        return tag

    def all_assignments(self) -> list[TagAssignment]:
        return [
            TagAssignment(tag=tag, original=orig, category=cat)
            for (cat, orig), tag in self._mapping.items()
        ]
