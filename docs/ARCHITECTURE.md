# Architecture

This document explains the design decisions behind phi-scrubber. The README covers what it does and how to use it; this covers **why** it's built the way it is.

## Pipeline

![pipeline](img/architecture.svg)

```
clinical note ──► [regex detectors]    ──┐
                                          │
                  [spaCy NER]         ──┼──► span merger ──► tag assigner ──► apply right-to-left ──► scrubbed text
                                          │                                                              │
                  [gazetteer]        ──┘                                                              └──► audit log
                                                          ▲
                                                          │
                                              [date shifter]  (per-patient offset)
```

## Why a hybrid detection stack

HIPAA Safe Harbor names 18 categories of identifiers. They split into two engineering problems with different right answers.

**Identifiers with shapes** — phone numbers, SSNs, dates, ZIPs, MRNs, URLs, IPs — are deterministic patterns. Regex is the right tool: high precision, fast, no model dependency, no surprises in production.

**Identifiers without shapes** — names of people, hospitals, cities — are semantic. There's no regex for "is this a person's name." That's where statistical NER (named entity recognition) earns its keep. spaCy's `en_core_web_lg` model handles PERSON, ORG, GPE entities at acceptable accuracy for portfolio-grade work.

Mixing the two strategies is non-trivial because they emit overlapping spans on the same input. Resolution rules:

1. **Longest match wins.** "Dr. Sarah Chen" (NER PERSON) beats "Sarah" (regex first-name match) because it covers more characters.
2. **Category priority** breaks length ties. SSN > ID > PHONE > DATE > ZIP > person > org > city. Reflects "more specific identifier wins."
3. **Confidence** breaks priority ties. Each detector emits a confidence in `[0, 1]`.

Code: `phi_scrubber/scrubber.py::merge_spans` and the `_CATEGORY_PRIORITY` table.

## Why per-document consistent tagging

The naive replacement is "find PHI, replace with `[REDACTED]`." That destroys clinical readability. A discharge summary that says

> [REDACTED] was admitted on [REDACTED]. [REDACTED] ordered labs. [REDACTED] reviewed the case and discharged [REDACTED].

is unusable for research because you can't tell who's the patient, who's the attending, who ordered which test.

Better: numbered tags within a document. "Dr. Chen" → `[DOCTOR_1]` every time it appears. "John Adeyemi" → `[PATIENT_1]`. Researchers can still trace co-references.

Implementation: `phi_scrubber/replacers.py::TagAssigner`. Normalization (whitespace + casefold) ensures "Dr. Chen", "Dr.  Chen", and "dr. chen" map to the same tag.

Categories that are typically singular per document (PHONE, EMAIL, SSN) get bare tags like `[PHONE]` rather than `[PHONE_1]`. Saves visual noise.

## Why per-patient deterministic date shifting

Safe Harbor §164.514(b)(2)(C) requires removing all dates more granular than year. The naive implementation strips dates outright.

But research utility is destroyed. A liver-disease cohort study needs to know intervals: time from admission to symptom onset, time from start-of-medication to lab response, dialysis intervals. Throwing out dates throws out the temporal structure that makes clinical research possible.

The compromise (well-established in the de-identification literature):

**Shift every date for one patient by the same random offset in `[-180, +180]` days.** Different patients get different offsets. Same patient → same offset, every time, for the duration of the dataset.

Result: intervals survive (admission-to-discharge of 5 days stays 5 days), but absolute dates become meaningless (a March 14 admission shifted -127 days lands on November 7 of the prior year — clinically nonsensical as a real admission date).

Implementation seeds the offset with `SHA-256(patient_id)`:

```python
def offset_for_patient(patient_id: str) -> int:
    h = hashlib.sha256(patient_id.encode("utf-8")).digest()
    raw = int.from_bytes(h[:4], "big")
    span = MAX_SHIFT_DAYS * 2 + 1
    return (raw % span) - MAX_SHIFT_DAYS
```

This is deterministic across runs without storing a side-table. If you need cryptographic unlinkability — i.e., an attacker who knows the algorithm and one (patient_id, shift) pair can't predict another patient's shift — swap the hash for HMAC with a secret key. Code is in `phi_scrubber/date_shifter.py` and the change is one-line.

**Known attack surface:** correlating shifted dates with other temporal anchors (medication start, lab result patterns, billing cycles) can re-identify. There's published literature on this. Per-patient shifting raises the bar; it doesn't eliminate the attack.

## Why right-to-left replacement

Naive replacement (left-to-right) breaks because every replacement changes character offsets for all subsequent spans. By the time you get to span 5, span 5's stored offsets refer to character positions that no longer exist.

The standard fix: sort spans by start position descending, walk right-to-left. Earlier spans' offsets are unaffected by later replacements because the later replacement happens at a higher offset that's already past.

Code: `phi_scrubber/scrubber.py::Scrubber.scrub` applies replacements via `sorted(finalized, key=lambda s: -s.start)`.

## Why graceful spaCy fallback

spaCy + `en_core_web_lg` is ~500 MB. Many users don't want that on first install — especially folks evaluating the tool or running it in a constrained environment.

The detector module attempts a lazy import + lazy model load. If either fails, it returns an empty span list. The scrubber pipeline still runs — just with regex + gazetteer detection only. The CLI prints a status message at startup so users know which mode they're in.

This avoids the "I tried to install your package and got an opaque ImportError" first-impression problem.

Code: `phi_scrubber/detectors/ner_detector.py::_try_load_spacy`.

## Test strategy

Three layers:

1. **Unit tests per detector** — each regex pattern against canonical inputs and pathological inputs (e.g., SSN-vs-phone disambiguation, ZIP-vs-money disambiguation, IP octet validation).
2. **Unit tests per pipeline component** — span merge, tag assigner, date shifter.
3. **Integration tests** on a fixture clinical note — full scrub end-to-end, asserting both that PHI is removed AND that scrubbed text remains clinically readable.

NER tests are gated with `pytest.mark.skipif(not is_spacy_available())` so the suite passes whether or not spaCy is installed. CI runs both: regex-only matrix on Python 3.10/3.11/3.12, plus a separate job with `en_core_web_sm` to exercise the NER path.

## What's intentionally NOT in scope

- **Expert Determination Method.** That requires a qualified statistician certifying re-identification risk is "very small." Not something software can do.
- **The "no actual knowledge" clause.** Safe Harbor requires the covered entity to have no actual knowledge that residual info could re-identify. A human reviewer is the only way to satisfy that — software can't.
- **Structured EHR field scrubbing.** This tool is for narrative notes (history-of-present-illness, discharge summaries, consult notes). Structured fields (MRN columns, DOB columns) need a different approach — typically column-level redaction at the database layer.
- **Real-PHI testing.** All test fixtures are synthetic. CI never sees real patient data. Production users are responsible for their own validation against gold-standard datasets like i2b2/n2c2.

## Future work (v0.2+)

- **FHIR `DocumentReference` adapter** — read `content[0].attachment.data` (base64), scrub, re-encode. v0.2.
- **HTML before/after diff viewer** — for human review workflows. v0.2.
- **Precision/recall evaluation harness** — against i2b2/n2c2 de-identification challenge dataset. Lets us put real numbers on detection quality. v0.3.
- **LLM-assisted catch-all** — Safe Harbor §164.514(b)(2)(R) requires removing "other unique identifiers" beyond the listed 18. Local LLM (e.g., Llama-3 8B Instruct) for context-aware detection of long-tail identifiers. v0.4.

## References

- HHS HIPAA Privacy Rule de-identification methods overview — https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html
- HIPAA Safe Harbor specification (45 CFR §164.514(b)(2)) — https://www.ecfr.gov/current/title-45/section-164.514#p-164.514(b)(2)
- spaCy linguistic features (NER) — https://spacy.io/usage/linguistic-features#named-entities
- i2b2 / n2c2 de-identification challenge — https://n2c2.dbmi.hms.harvard.edu/
- Sweeney, L. (2002). "k-anonymity: A model for protecting privacy." International Journal of Uncertainty, Fuzziness and Knowledge-based Systems. (Background reading on re-identification attacks.)
