# Schematron rules — what runs and where it comes from

The validator runs the **official PINT AE 1.0.4 artefacts** by default. Two source
files, 302 assertions, all `flag="fatal"` in the publisher's source, so a failed
assertion is reported as an `error`:

| Layer | File | Assertions | Source |
|---|---|---|---|
| shared 1.0.4 | `../vendor/pint-ae-1.0.4/shared.sch` | 170 | `resources.zip` from docs.peppol.eu |
| jurisdiction 1.0.4 | `../vendor/pint-ae-1.0.4/jurisdiction.sch` | 132 | same package |

Self-billing documents (`urn:peppol:pint:selfbilling-1@ae-1`) are routed to the
matching pair under `../vendor/pint-ae-sb-1.0.4/`; the rules are the same, the
document-type code lists differ.

The publisher ships precompiled `.xslt` files next to the `.sch` files. Those are
used directly — no Saxon compilation at run time, no writable cache needed. A
`.sch` file is only compiled with the ISO skeleton in `../xsl/` when no `.xslt`
exists. The vendored bytes are pinned by SHA-256 and re-verified by
`pint-ae selftest`.

## The legacy pair in this folder

| File | Assertions | Status |
|---|---|---|
| `shared_pint.sch` | 171 | opt-in via `--peppol-bis3`, findings are warnings |
| `peppol_bis3.sch` | 160 | opt-in via `--peppol-bis3`, findings are warnings |

Provenance: `shared_pint.sch` from the Saxonica PINT attachment,
`peppol_bis3.sch` from `docs.peppol.eu/poacc/billing/3.0`. Both are opt-in because
Peppol BIS 3.0 derives its profile from a Business Profile identifier that PINT AE
does not use, so a subset of its rules can misfire; they are kept for comparison,
not for the conformance verdict.

## What the local rules add

The official artefact is the source of truth. 24 local rules in
`src/pint_ae/rules.py` cover what the artefact cannot see or does not say, for
example: arithmetic that must hold with UAE rounding, TIN/TRN coherence, emirate
codes, and two obligations from Ministerial Decision 197/2026 (the
14-business-day transmission window and the intra-tax-group exclusion). When a
local rule duplicates an official assertion, the official finding wins and the
local one is recorded as suppressed, never hidden.

## Why the partial fixtures report errors

`tests/fixtures/basic_invoice.xml` predates the official artefacts and carries only
part of the mandatory field set. The official layers correctly report the missing
fields. That is the point: "clean" is demonstrated on the 30 official samples and
on the generated client corpus, not on those partial fixtures.

## Updating the rules

1. Replace the vendored files and update the SHA-256s in
   `../vendor/pint-ae-1.0.4/README.md` and `../../regulatory.py`
   (`EXPECTED_RULE_SET_SHA256`).
2. Run `pint-ae selftest` — it fails loudly while the pinned hash is stale.
3. Re-run the test suite; the official samples and the generated corpus are the
   regression gate.
