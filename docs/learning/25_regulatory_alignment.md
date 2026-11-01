# Learning Note 25 — Regulatory alignment, and a near-miss worth remembering

**Block:** 1.4j
**Date:** 2026-11-01
**Files:** `docs/sources/regulatory-register.md`, `pint_ae/regulatory.py`,
`rules.py` (R-024, R-025), `tests/test_regulatory.py`

---

## What the regulation actually says

The UAE e-invoicing framework is six instruments, not one:

- **MD 243/2025** — the system: scope, obligations, agent, self-billing.
- **MD 244/2025 + MR 66/2026** — the phases and dates.
- **Cabinet Decision 106/2025** — the six penalties.
- **MD 197/2026** — in force 1 October 2026: new exclusions (tax groups for 24
  months, financial services), the **14-business-day transmission rule**, the
  storage wording, and the repeal of the system-failure notice.
- **FTA Decision 4/2026** — records must be complete, legible and accessible.
- **PINT AE 1.0.4 / PINT General 1.1.3** — the technical standard.

Every one is now downloaded, hashed (`docs/sources/regulatory-register.md`) and
quoted with its article number.

## The near-miss

Reading three law-firm summaries and the MoF guidelines, I found no 14-day
transmission window and drafted a plan that would have **retired R-024 as
unsupported**. Then I downloaded MD 197/2026 itself: **Article 6(5)** requires
issue and transmission within fourteen business days of the business transaction.
The summaries were incomplete; the guidelines described onboarding, not the
obligation.

The rule stayed, the citation was corrected to the article, and the proxy was
written down (the invoice shows the issue date, not the transmission date; public
holidays are not yet modelled).

**Lesson:** secondary sources are pointers, never evidence. A professional
product cites the instrument, the article and a hash — and a rule is only retired
after the primary source is read, not after three summaries fail to mention it.

## What changed in the product

- **Provenance in every report**: spec version, rule-set SHA-256 and regulation
  snapshot date. A client can tie a finding to the exact rules that produced it.
- **Exclusions are scope, not defects**: tax-group intercompany (to 31 Dec 2028),
  B2C, sovereign/airline, financial services. Flagging those as non-compliant
  would be a false positive in front of a client — so scope classification is now
  a product requirement, not a nice-to-have.
- **Penalties are quoted exactly**: six items, two now obsolete, and no
  “AED 50,000 cap” because the instrument does not contain one.
- **No system-failure feature**: the obligation was repealed; an internal incident
  log stays as evidence, not as a compliance product.
- **No storage-location sales pitch**: the residency requirement was removed;
  client tenancy is still the right default, for confidentiality and PDPL.

## Why this matters commercially

A diagnostic is bought on trust. One wrong citation — a penalty figure from a
news article, a rule that does not exist, a storage requirement that was repealed
— and the whole report becomes negotiable. A dated register, hashed artefacts and
article-level citations are what turn “I ran a script” into “this is defensible”.

## Numbers

- 24 local rules + 302 official assertions = 326 checks.
- 139 tests; rule-set hash printed in every PDF.
- Regulation snapshot: 2026-11-01.

## Interview angle

Q: How do you keep a compliance product correct when the regulation changes?
A: A dated register of primary instruments with hashes, a monthly review, outputs
that record the exact rule-set and regulation snapshot, and a rule-set hash gate
in CI. When three rules changed weeks before go-live, the diff was a changelog
entry and a scenario, not a rewrite.
