"""Command-line interface for phi-scrubber.

Usage:
  phi-scrubber input.txt -o output.txt
  phi-scrubber input.txt --audit audit.json
  phi-scrubber input.txt --no-shift-dates
  phi-scrubber input.txt --patient-id pt_001
  phi-scrubber input.txt --no-ner   (skip spaCy even if installed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from phi_scrubber import Scrubber, __version__
from phi_scrubber.detectors.ner_detector import is_spacy_available


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="phi-scrubber",
        description="De-identify clinical free-text per HIPAA Safe Harbor (45 CFR 164.514(b)(2)).",
        epilog="Honest disclaimer: this tool is NOT sufficient as the sole "
               "de-identification control on real PHI. Human review required. "
               "See README for full limits.",
    )
    p.add_argument("input", type=Path, help="Path to input text file (or '-' for stdin)")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output path. Default: stdout.",
    )
    p.add_argument(
        "--audit", type=Path, default=None,
        help="Write audit JSON to this path (per-span details). DO NOT publish "
             "this file with the scrubbed text — it lets you reverse the scrub.",
    )
    p.add_argument(
        "--patient-id", type=str, default="default-patient",
        help="Patient ID seed for deterministic date-shift offsets. Same ID -> "
             "same offset. Default: 'default-patient'.",
    )
    p.add_argument(
        "--no-shift-dates", action="store_true",
        help="Redact dates (emit [DATE]) instead of shifting (emit [DATE_SHIFTED]).",
    )
    p.add_argument(
        "--no-ner", action="store_true",
        help="Skip spaCy NER even if installed. Regex-only mode.",
    )
    p.add_argument(
        "--ner-model", type=str, default="en_core_web_lg",
        help="spaCy model name. Default: en_core_web_lg.",
    )
    p.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress diagnostic stderr output.",
    )
    p.add_argument(
        "--version", action="version", version=f"phi-scrubber {__version__}",
    )
    return p


def read_input(path: Path) -> str:
    if str(path) == "-":
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.quiet:
        if args.no_ner:
            print("[phi-scrubber] mode: regex-only (NER skipped per --no-ner)", file=sys.stderr)
        elif is_spacy_available():
            print(f"[phi-scrubber] mode: regex + NER ({args.ner_model})", file=sys.stderr)
        else:
            print(
                "[phi-scrubber] mode: regex-only (spaCy not installed — install "
                "with: pip install 'phi-scrubber[ner]' && python -m spacy download "
                "en_core_web_lg)",
                file=sys.stderr,
            )

    try:
        text = read_input(args.input)
    except FileNotFoundError:
        print(f"[phi-scrubber] error: input file not found: {args.input}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"[phi-scrubber] error reading input: {e}", file=sys.stderr)
        return 2

    scrubber = Scrubber(
        shift_dates=not args.no_shift_dates,
        use_ner=not args.no_ner,
        ner_model=args.ner_model,
    )
    result = scrubber.scrub(text, patient_id=args.patient_id)

    # Write scrubbed text
    if args.output is None:
        sys.stdout.write(result.text)
    else:
        args.output.write_text(result.text, encoding="utf-8")
        if not args.quiet:
            print(
                f"[phi-scrubber] wrote {len(result.text)} chars -> {args.output}, "
                f"{len(result.spans)} spans replaced",
                file=sys.stderr,
            )

    # Write audit if requested
    if args.audit is not None:
        args.audit.write_text(
            json.dumps(result.to_audit_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"[phi-scrubber] wrote audit -> {args.audit}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
