# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned (v0.2)

- FHIR `DocumentReference` adapter (read base64 content, scrub, re-encode)
- HTML before/after diff viewer for human review workflows

### Planned (v0.3)

- Precision/recall evaluation harness against i2b2/n2c2 de-identification challenge dataset

### Planned (v0.4)

- LLM-assisted catch-all detection for §164.514(b)(2)(R) "other unique identifiers"

---

## [0.1.0] — 2026-05-05

Initial release. MVP per the project specification at `~/life/areas/career/phi-scrubber-project.md`.

### Added

- Hybrid detection pipeline: regex + spaCy NER + seed gazetteer
- 8 regex detector categories: phone, email, SSN, MRN/account/license, URL, IP, ZIP, dates
- spaCy NER for PERSON / ORG / GPE with PATIENT-vs-DOCTOR and HOSPITAL-vs-ORG sub-classification via local context cues
- Seed gazetteer for common US hospitals + city-state patterns (catches NER misses)
- Span merge with longest-match-wins + category priority + confidence tiebreak
- Per-document consistent tag assigner (`PATIENT_1`, `DOCTOR_1`, `HOSPITAL_1`, etc.) with case + whitespace normalization
- Per-patient deterministic date shifter via `SHA-256(patient_id)` → offset in `[-180, +180]` days
- Right-to-left replacement application so offsets stay valid across multi-span scrubs
- CLI: `phi-scrubber input.txt -o output.txt --patient-id pt_001 --audit audit.json --no-shift-dates --no-ner`
- Library API: `Scrubber().scrub(text, patient_id="...")`
- Audit-log emission with per-span `(start, end, category, confidence, original, tag)` records
- Graceful fallback when spaCy isn't installed (regex-only mode + status message)
- 56-test pytest suite covering regex detectors, replacers, date shifter, integration
- GitHub Actions CI matrix on Python 3.10 / 3.11 / 3.12
- Separate CI job exercising spaCy NER path with `en_core_web_sm`
- README with HIPAA Safe Harbor citation + the honest disclaimer paragraph
- MIT license
- Architecture documentation at `docs/ARCHITECTURE.md`
- Contributing guidelines at `CONTRIBUTING.md`
- Security policy at `SECURITY.md`

### Notes

- This release is a portfolio MVP. It is **NOT sufficient as the sole de-identification control** on real PHI — see README and `SECURITY.md` for honest limits.
- All test fixtures are synthetic. Use [Synthea](https://github.com/synthetichealth/synthea) or i2b2/n2c2 challenge data for any further evaluation.
