"""Detectors emit (start, end, category, confidence, original) spans.

Two strategies, run in parallel by the scrubber:
  1. Pattern-based (regex_detectors) — deterministic shapes
  2. Statistical (ner_detector) — spaCy NER with graceful fallback if not installed
"""
