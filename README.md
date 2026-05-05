# phi-scrubber

Pattern-based + NER-based de-identification of clinical free-text, aligned with **HIPAA Safe Harbor Method (45 CFR §164.514(b)(2))**.

> **This tool implements pattern-based + NER-based detection aligned with HIPAA Safe Harbor Method (§164.514(b)(2)). It does NOT satisfy the "no actual knowledge" clause on its own — a qualified human reviewer is still required for formal Safe Harbor compliance. It also does NOT implement the Expert Determination Method. Do not use as the sole de-identification control on real PHI without institutional review.**

That paragraph is the most important sentence in this README. Read it twice.

---

## What it does

Takes clinical free-text and replaces 18 categories of HIPAA Safe Harbor identifiers with consistent, human-readable tags. Preserves clinical readability and (optionally) date intervals for research utility.

### Example

**Input**

```
Mr. John Adeyemi, a 54-year-old male from Damascus, MD, was admitted on
3/14/2026 with chest pain. Contact: (301) 555-0123. MRN: 8842193.
PCP Dr. Sarah Chen at Shady Grove Medical.
```

**Output**

```
[PATIENT_1], a 54-year-old male from [CITY], was admitted on
[DATE_SHIFTED] with chest pain. Contact: [PHONE]. MRN: [ID].
PCP [DOCTOR_1] at [HOSPITAL].
```

---

## Install

```bash
# Clone, then from the repo root:
pip install -e .

# For NER (recommended — adds PERSON / ORG / GPE detection)
pip install -e ".[ner]"
python -m spacy download en_core_web_lg

# For development (tests + linter)
pip install -e ".[dev]"
```

Without spaCy installed, the tool runs in **regex-only mode**: it still catches phone, email, SSN, MRN, dates, ZIP, URL, IP — but NOT person/organization/city names. The `[ner]` extra is strongly recommended for real use.

---

## CLI

```bash
phi-scrubber input.txt -o output.txt
phi-scrubber input.txt --audit audit.json
phi-scrubber input.txt --no-shift-dates    # redact dates instead of shifting
phi-scrubber input.txt --patient-id pt_001 # seed the date offset by patient
```

`--audit audit.json` writes the per-document replacement map (offsets, original spans, tags) for traceability — never publish this file alongside the scrubbed text.

---

## Library use

```python
from phi_scrubber import Scrubber

s = Scrubber()
result = s.scrub(text, patient_id="pt_001")
print(result.text)        # scrubbed text
print(result.audit)       # list of (start, end, category, original, tag)
```

---

## What gets detected

### Pattern-based (deterministic regex)

| Category | Example | Tag |
|---|---|---|
| Phone | `(301) 555-0123` | `[PHONE]` |
| Email | `pt@example.com` | `[EMAIL]` |
| SSN | `123-45-6789` | `[SSN]` |
| MRN / account / license | `MRN: 8842193` | `[ID]` |
| URL | `https://example.com` | `[URL]` |
| IP | `192.168.1.1` | `[IP]` |
| ZIP | `20902` | `[ZIP]` |
| Date | `3/14/2026` | `[DATE_SHIFTED]` (or `[DATE]`) |

### NER-based (spaCy, optional)

| Category | Example | Tag |
|---|---|---|
| Person | `Dr. Sarah Chen` | `[DOCTOR_1]` / `[PATIENT_1]` |
| Organization | `Shady Grove Medical` | `[HOSPITAL]` |
| City / state | `Damascus, MD` | `[CITY]` |

### Date shifting

By default dates are **shifted** by a per-patient consistent offset (±180 days). Same patient, same offset → admission/discharge intervals survive but absolute dates become meaningless. Pass `--no-shift-dates` to redact instead.

---

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The pytest suite covers:
- Each regex category against canonical and pathological inputs
- Span merging (overlapping detections, longest-match wins)
- Per-document consistent tagging (same name → same tag throughout)
- Date-shift consistency (same patient → same offset across calls)
- Integration: full scrub of fixture clinical notes

---

## Honest limitations

- **No "actual knowledge" filter.** Safe Harbor requires the covered entity to have no actual knowledge that residual info could re-identify. Software can't satisfy that — a human reviewer must.
- **NER recall is imperfect.** spaCy misses unusual names, foreign names, rare hospital names. Build a domain gazetteer if you have one.
- **Date shifting is per-patient.** Across a dataset, statistical attacks correlating shifted dates with other temporal info (medications, lab values) may re-identify. The literature on this is real.
- **No Expert Determination support.** That method requires a statistical expert to certify de-identification — out of scope here.
- **Free-text only.** Structured EHR fields (MRN columns, DOB columns) need a different tool. This is for narrative notes.

---

## Roadmap

| Version | Adds |
|---|---|
| **v0.1 (MVP)** | CLI + 8 regex categories + spaCy NER + per-doc tagging + date shifting + tests |
| v0.2 | FHIR `DocumentReference` adapter, HTML diff viewer |
| v0.3 | Precision/recall eval against i2b2/n2c2 challenge data |
| v0.4 | LLM-assisted catch-all detection for §164.514(b)(2)(R) "other unique identifiers" |

---

## References

- HIPAA Privacy Rule — 45 CFR §164.514(b)(2) Safe Harbor Method
- HHS HIPAA Privacy Rule Summary — https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html
- spaCy NER documentation — https://spacy.io/usage/linguistic-features#named-entities
- Synthea synthetic patient generator — https://github.com/synthetichealth/synthea
- i2b2 / n2c2 de-identification challenge

---

## License

MIT — see `LICENSE`.
