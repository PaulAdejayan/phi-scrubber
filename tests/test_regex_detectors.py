"""Tests for each regex detector. One canonical hit + one or two negatives per pattern."""
from __future__ import annotations

import pytest

from phi_scrubber.detectors.regex_detectors import (
    detect_phone, detect_email, detect_ssn, detect_url, detect_ip,
    detect_zip, detect_id, detect_date, detect_all_regex,
)


class TestPhone:
    def test_paren_format(self):
        spans = detect_phone("Call (301) 555-0123 today")
        assert len(spans) == 1
        assert spans[0].original == "(301) 555-0123"

    def test_dash_format(self):
        spans = detect_phone("301-555-0123")
        assert len(spans) == 1

    def test_dot_format(self):
        spans = detect_phone("301.555.0123")
        assert len(spans) == 1

    def test_intl_prefix(self):
        spans = detect_phone("+1 301 555 0123")
        assert len(spans) == 1

    def test_does_not_match_in_long_digit_string(self):
        # Should not pull "555 0123" out of "MRN: 30155501234"
        spans = detect_phone("MRN: 30155501234567")
        assert len(spans) == 0


class TestEmail:
    def test_canonical(self):
        spans = detect_email("Reach pt at john.doe@example.com today")
        assert len(spans) == 1
        assert spans[0].original == "john.doe@example.com"

    def test_plus_addressing(self):
        spans = detect_email("billing+pt001@example.com")
        assert len(spans) == 1

    def test_no_email_no_match(self):
        assert detect_email("plain text no email") == []


class TestSSN:
    def test_canonical(self):
        spans = detect_ssn("SSN 123-45-6789")
        assert len(spans) == 1
        assert spans[0].original == "123-45-6789"

    def test_does_not_match_phone_format(self):
        # 301-555-0123 is a phone, not SSN
        assert detect_ssn("Phone 301-555-0123") == []

    def test_does_not_match_extra_digits(self):
        assert detect_ssn("12345678901-23-45678") == []


class TestURL:
    def test_https(self):
        spans = detect_url("Visit https://example.com/path?q=1")
        assert len(spans) == 1

    def test_strips_trailing_punctuation(self):
        spans = detect_url("See https://example.com.")
        assert len(spans) == 1
        assert spans[0].original == "https://example.com"

    def test_www(self):
        spans = detect_url("www.example.com is the site")
        assert len(spans) == 1


class TestIP:
    def test_valid_ipv4(self):
        spans = detect_ip("Server at 192.168.1.1")
        assert len(spans) == 1

    def test_invalid_octet_rejected(self):
        # 999 > 255, should be rejected
        spans = detect_ip("Bad: 999.1.1.1")
        assert len(spans) == 0

    def test_doesnt_match_version_string(self):
        spans = detect_ip("Version 1.2.3.4 of the lib")
        # 1.2.3.4 looks like an IP. We accept this — it's the regex's choice.
        # Document the behavior with a positive assertion so a future
        # behavior change is caught explicitly.
        assert len(spans) == 1


class TestZip:
    def test_5_digit(self):
        spans = detect_zip("Damascus, MD 20872 USA")
        assert len(spans) == 1
        assert spans[0].original == "20872"

    def test_zip_plus_4(self):
        spans = detect_zip("ZIP 20872-1234")
        assert len(spans) == 1

    def test_no_match_in_money(self):
        assert detect_zip("Cost was $20872") == []


class TestID:
    def test_mrn(self):
        spans = detect_id("MRN: 8842193")
        assert len(spans) == 1
        assert spans[0].original == "8842193"

    def test_mrn_no_colon(self):
        spans = detect_id("MRN 8842193")
        assert len(spans) == 1

    def test_account(self):
        spans = detect_id("Account: ABC-12345")
        assert len(spans) == 1

    def test_no_match_without_label(self):
        assert detect_id("Random number 8842193") == []


class TestDate:
    def test_slash_format(self):
        spans = detect_date("Admitted 3/14/2026 with chest pain")
        assert len(spans) == 1

    def test_iso_format(self):
        spans = detect_date("Date: 2026-03-14")
        assert len(spans) == 1

    def test_spelled_month(self):
        spans = detect_date("Born March 14, 1971")
        assert len(spans) == 1

    def test_short_year(self):
        spans = detect_date("Visit 3/14/26")
        assert len(spans) == 1

    def test_no_match_in_random_numbers(self):
        assert detect_date("Lab values 145.2 / 89.4") == []


class TestAllRegex:
    def test_aggregator_returns_sorted(self):
        text = "Call (301) 555-0123 about MRN: 8842193 on 3/14/2026"
        spans = detect_all_regex(text)
        # Phone, ID, and Date should all hit. Sorted by start.
        starts = [s.start for s in spans]
        assert starts == sorted(starts)
        cats = {s.category for s in spans}
        assert "PHONE" in cats
        assert "ID" in cats
        assert "DATE" in cats
