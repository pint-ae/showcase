# Learning Note 24 — Adopting the official rulebook (and what it exposed)

**Block:** M1 Paste 1
**Date:** 2026-11-01
**Files:** `schematron/validator.py`, `schematron/vendor/pint-ae-1.0.4/`,
`parser.py`, `types.py`, `rules.py`, `tests/test_official_samples.py`

---

## What changed

The checker now runs the **publisher's own rule set** by default:

- 170 shared PINT assertions + 132 UAE jurisdiction assertions = **302**, all
  `flag="fatal"`, run from the vendored `.sch`/`.xslt` files (SHA-256 pinned).
- Failures are reported as **errors**, not warnings. Exit code 1 means "this
  invoice will be rejected", which is what the client is paying to know.
- Peppol BIS 3.0 (160 assertions) moved behind `--peppol-bis3`; it is not part
  of the PINT AE conformance set and it misfires when the profile is not a BIS
  ProfileID.
- The 30 official samples are the golden corpus: `tests/test_official_samples.py`
  fails if any of them stops being clean.

## What it exposed about our own code

Running someone else's valid data is the cheapest audit there is. It found, in
one afternoon:

1. **R‑023 was wrong.** It said the transaction-type code was optional and
   merely "8 binary characters". The official `ibr-154-ae` makes
   `cbc:ProfileExecutionID` mandatory, 8 digits, from a fixed list. A rule that
   contradicts the spec is worse than no rule: it produces both false alarms and
   false comfort. It was deleted rather than "fixed", because the official layer
   already validates it.
2. **Our R‑007 allow-list was invented.** The official invoice code list
   contains `480` ("Invoice out of scope of tax"); our hard-coded set did not.
   The rule now reads the official genericode list, so the code list is the
   source of truth.
3. **Our Peppol-ID rule assumed a 10-digit TIN.** The official samples use
   `0235:<15-digit TRN>` and foreign schemes such as `0151`. The local rule now
   checks what is genuinely a defect (no scheme, all-same characters,
   placeholders) and leaves scheme validity to the official layer.
4. **Our arithmetic rules ignored real UBL structure**: `PayableRoundingAmount`,
   `PrepaidAmount`, line-level allowances/charges and `BaseQuantity`. BR‑CO‑15,
   BR‑CO‑16 and IBR‑147 define those formulas; ours were approximations. They
   were rewritten against the rules and now pass on all samples.
5. **Our parser could not read a credit note.** PINT AE credit notes use
   `cac:CreditNoteLine` and `cbc:CreditNoteTypeCode`; we only handled invoices.
   It also required `PartyName`, while real documents often use
   `PartyLegalEntity/RegistrationName`, and it demanded a buyer TRN that exports
   legitimately omit.
6. **One official sample is itself XSD-invalid** — `volume-discount-credit-note.xml`
   puts `DiscrepancyResponse` before `OrderLineReference`, violating the UBL
   sequence. Recorded, excluded from the XSD assertion only, not silenced.

## The lesson

Two lessons, both about evidence:

- **Test against the publisher's data before claiming coverage.** Our fixtures
  were synthetic and incomplete, so every rule "passed". The official samples
  passed 30/30 for the official layers and failed half our own — that asymmetry
  is the real measurement.
- **A duplicate rule is a liability, not redundancy.** Every local rule that
  re-implemented an official one had drifted: wrong formula, wrong allow-list,
  wrong assumption. Where the official rule exists, delete ours; where it does
  not, our rule must cite the paragraph it implements.

## Numbers

- Official: 302 assertions (170 + 132), all fatal.
- Local: 24 rules (R‑023 retired).
- Total: **326 checks per invoice**, generated from code (PDF scope line shows it).
- Tests: 133.
- Golden baseline: 30/30 official samples clean through the tool.

## Interview angle

A candidate who says "I validate invoices against 326 checks" is describing
coverage. A candidate who says "I run the publisher's 302 assertions with their
own samples as a regression gate, and I deleted my duplicate rules because they
had drifted from the spec" is describing engineering judgment — and that is the
thing being hired.
