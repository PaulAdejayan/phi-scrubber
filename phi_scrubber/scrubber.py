"""Main scrubber pipeline.

  text -> [regex detectors]    -> spans
       -> [NER detector]       -> spans
       -> [gazetteer]          -> spans
       -> merge_spans          (overlap resolution: longest-match wins)
       -> assign tags          (consistent within document)
       -> apply right-to-left  (so earlier offsets don't shift)
       -> emit scrubbed text + audit log

Returns a ScrubResult dataclass with:
  - .text     scrubbed text
  - .spans    final merged spans used
  - .audit    [(start_in_orig, end_in_orig, category, original, tag), ...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from phi_scrubber.detectors.gazetteer import detect_gazetteer
from phi_scrubber.detectors.ner_detector import detect_ner, is_spacy_available
from phi_scrubber.detectors.regex_detectors import RawSpan, detect_all_regex
from phi_scrubber.replacers import TagAssigner


@dataclass(frozen=True)
class Span:
    """A finalized PHI span, post-merge, ready for replacement."""
    start: int
    end: int
    category: str
    confidence: float
    original: str
    tag: str = ""  # filled after tag assignment


@dataclass
class ScrubResult:
    text: str
    spans: list[Span] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    spacy_available: bool = False

    def to_audit_dict(self) -> dict:
        return {
            "scrubbed_text": self.text,
            "spans": [
                {
                    "start": s.start,
                    "end": s.end,
                    "category": s.category,
                    "confidence": s.confidence,
                    "original": s.original,
                    "tag": s.tag,
                }
                for s in self.spans
            ],
            "spacy_available": self.spacy_available,
        }


# ---------------------------------------------------------------------------
# Span merging
# ---------------------------------------------------------------------------


# Priority for tie-breaking when categories collide on the same span.
# Higher priority = wins on equal coverage. SSN > ID > PHONE etc.
_CATEGORY_PRIORITY: dict[str, int] = {
    "SSN": 100,
    "EMAIL": 95,
    "URL": 90,
    "IP": 85,
    "PHONE": 80,
    "ID": 75,
    "DATE": 70,
    "ZIP": 60,
    "DOCTOR": 55,
    "PATIENT": 55,
    "HOSPITAL": 50,
    "ORG": 45,
    "CITY": 40,
}


def _spans_overlap(a: RawSpan, b: RawSpan) -> bool:
    return not (a.end <= b.start or b.end <= a.start)


def _prefer(a: RawSpan, b: RawSpan) -> RawSpan:
    """Choose between two overlapping spans:
      1. Longest match wins
      2. Tie -> higher category priority
      3. Tie -> higher confidence
    """
    a_len = a.end - a.start
    b_len = b.end - b.start
    if a_len != b_len:
        return a if a_len > b_len else b
    a_pri = _CATEGORY_PRIORITY.get(a.category, 0)
    b_pri = _CATEGORY_PRIORITY.get(b.category, 0)
    if a_pri != b_pri:
        return a if a_pri > b_pri else b
    return a if a.confidence >= b.confidence else b


def merge_spans(raw: list[RawSpan]) -> list[RawSpan]:
    """Resolve overlapping detections so each character is covered at most once.

    Sort by start, then sweep — when two spans overlap, keep the preferred one
    and drop the other.
    """
    if not raw:
        return []
    sorted_spans = sorted(raw, key=lambda s: (s.start, -(s.end - s.start)))
    out: list[RawSpan] = []
    for span in sorted_spans:
        if out and _spans_overlap(out[-1], span):
            kept = _prefer(out[-1], span)
            out[-1] = kept
        else:
            out.append(span)
    return out


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class Scrubber:
    """High-level scrubber. Configure once, scrub many documents.

    Args:
      shift_dates: emit [DATE_SHIFTED] when True (default, preserves intervals
                   via offset stored in audit log), [DATE] when False.
      use_ner: try to use spaCy NER. Auto-disabled if spaCy not installed.
      ner_model: spaCy model name to load.
    """

    def __init__(
        self,
        *,
        shift_dates: bool = True,
        use_ner: bool = True,
        ner_model: str = "en_core_web_lg",
    ) -> None:
        self.shift_dates = shift_dates
        self.use_ner = use_ner
        self.ner_model = ner_model

    def scrub(self, text: str, patient_id: Optional[str] = None) -> ScrubResult:
        """Scrub a single document. Pass patient_id for date-shift seeding
        (irrelevant if shift_dates=False).
        """
        # 1. Run all detectors
        spans: list[RawSpan] = []
        spans.extend(detect_all_regex(text))
        spacy_ok = False
        if self.use_ner:
            spacy_ok = is_spacy_available()
            if spacy_ok:
                spans.extend(detect_ner(text, model=self.ner_model))
        spans.extend(detect_gazetteer(text))

        # 2. Resolve overlaps
        merged = merge_spans(spans)

        # 3. Assign consistent tags
        assigner = TagAssigner(shift_dates=self.shift_dates)
        finalized: list[Span] = []
        for sp in merged:
            tag = assigner.tag_for(sp.category, sp.original)
            finalized.append(Span(
                start=sp.start, end=sp.end,
                category=sp.category, confidence=sp.confidence,
                original=sp.original, tag=tag,
            ))

        # 4. Apply replacements right-to-left so offsets don't shift
        out = text
        for sp in sorted(finalized, key=lambda s: -s.start):
            out = out[: sp.start] + sp.tag + out[sp.end:]

        # 5. Build audit log
        audit = [
            {
                "start": sp.start,
                "end": sp.end,
                "category": sp.category,
                "confidence": sp.confidence,
                "original": sp.original,
                "tag": sp.tag,
            }
            for sp in finalized
        ]

        return ScrubResult(
            text=out,
            spans=finalized,
            audit=audit,
            spacy_available=spacy_ok,
        )
