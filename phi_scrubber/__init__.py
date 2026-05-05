"""phi-scrubber — pattern + NER de-identification of clinical free-text.

Aligned with HIPAA Safe Harbor Method (45 CFR 164.514(b)(2)).
NOT sufficient as the sole compliance control — a qualified human reviewer
is required. See README for honest limits.
"""

from phi_scrubber.scrubber import Scrubber, ScrubResult, Span

__version__ = "0.1.0"
__all__ = ["Scrubber", "ScrubResult", "Span"]
