"""Detectors emit (start, end, category, confidence, original) spans.

Three strategies, run in parallel by the scrubber:
  1. Pattern-based (regex_detectors)  — deterministic shapes for structured IDs
  2. Context-anchored (anchored_name) — regex for names after Pt/Dr prefixes
                                        (catches lowercase/non-English names NER misses)
  3. Statistical (ner_detector)       — spaCy NER with graceful fallback if not installed
  4. Dictionary (gazetteer)           — hand-curated hospital + city/state lists
"""
