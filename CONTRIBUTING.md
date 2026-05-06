# Contributing to phi-scrubber

Thanks for your interest. A few things to know before opening an issue or PR.

## Before you file an issue

> **Never paste real PHI (protected health information) into a bug report.** This includes real patient names, real MRNs, real addresses, real phone numbers from real notes. Use synthetic data from [Synthea](https://github.com/synthetichealth/synthea) or hand-crafted fake-looking inputs. If you accidentally paste something real, contact the maintainer and the issue will be deleted; don't comment on it again.

If the issue is a security concern (e.g., a bypass that leaks identifiers in real-world clinical text), please follow [SECURITY.md](SECURITY.md) instead of filing a public issue.

## Setting up a dev environment

```bash
git clone https://github.com/PaulAdejayan/phi-scrubber.git
cd phi-scrubber
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e ".[dev,ner]"
python -m spacy download en_core_web_lg
pytest
```

## Coding standards

- Python 3.10+. Type hints encouraged but not required for one-off detector tweaks.
- `ruff check phi_scrubber tests` should pass. Config is in `pyproject.toml`.
- New detector or pipeline component → new test file in `tests/`.
- Public-API changes → bump `phi_scrubber/__init__.py::__version__` and add a `CHANGELOG.md` entry.
- Comments should explain **why**, not what. The code shows what.

## Pull-request checklist

- [ ] Tests added or updated for the change
- [ ] `pytest` passes locally (regex-only mode minimum; full mode if you have spaCy installed)
- [ ] `ruff check` passes
- [ ] Docstrings on new public functions
- [ ] If touching the detection pipeline: added/updated an integration test in `tests/test_scrubber_integration.py` against fixture data
- [ ] If adding a new identifier category: added to the README "What gets detected" table

## Architecture

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing the pipeline. The hybrid regex+NER detection, span merge resolution, and per-patient date shifting are deliberate design choices with rationale documented there.

## Roadmap

See the README's roadmap section. v0.2 priorities are FHIR adapter and HTML diff viewer; v0.3 is precision/recall evaluation against i2b2/n2c2.

If you want to work on something on the roadmap, open a draft issue first to coordinate scope.

## License

By contributing, you agree your contribution is licensed under MIT (same as the project).
