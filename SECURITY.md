# Security Policy

## Scope

phi-scrubber is a pattern + NER de-identification tool aligned with HIPAA Safe Harbor (§164.514(b)(2)). Security issues for this project fall into two classes:

1. **Detection-bypass vulnerabilities** — input patterns where the tool fails to redact a real Safe Harbor identifier, leaving PHI in the "scrubbed" output. These are the most important class.
2. **Implementation vulnerabilities** — standard software-security issues (dependency CVEs, path traversal, injection in the CLI, etc.).

## Reporting

**Do NOT open a public GitHub issue for either class.**

Instead, email **padejay1 [at] umbc [dot] edu** with:

- A clear description of the issue
- A minimal reproducer (use **synthetic data only** — never real PHI)
- Suggested severity if you have an opinion
- Whether you'd like attribution in the fix's release notes

You should expect an acknowledgement within 5 business days. Time-to-fix depends on severity and on how the maintainer's day-job schedule (yes, this is a portfolio project — be patient).

## What counts as PHI in a bug report

If your reproducer contains anything that **could possibly identify a real person** — even fictional-looking names that happen to match a real one, even the surname of a real doctor at a real hospital, even a partial real-looking address — it's PHI for our purposes. Use Synthea or hand-craft inputs that are obviously fake (e.g., "Mr. Test Patient at General Hospital City, ST"). When in doubt, scrub the reproducer before sending.

## What this tool is NOT

- **NOT a HIPAA compliance certification.** It's a tool that helps with de-identification. Compliance is your covered entity's responsibility, requires human review, and may require Expert Determination (which is out of scope here).
- **NOT a substitute for a Privacy Officer.** Don't deploy as the sole control on a clinical-data pipeline.
- **NOT audited.** Use synthetic data for evaluation. Test against your own gold-standard before any production-adjacent use.

See the README's "Honest limitations" section for the full picture.

## Disclosure timeline

For confirmed detection-bypass or implementation vulnerabilities:

- **Critical** (PHI leakage from default config on common inputs): aim for fix within 14 days; coordinated disclosure 14 days after fix.
- **High** (PHI leakage from non-default config or edge inputs): aim for fix within 30 days; coordinated disclosure 30 days after fix.
- **Medium / Low**: rolled into normal release cadence.

If a fix isn't possible (e.g., a fundamental limitation of the regex+NER hybrid approach), the limitation will be added to the "Honest limitations" section of the README and the issue closed with rationale.
