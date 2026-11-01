# Learning Note 26 — What makes it a tool rather than a script

**Block:** 1.4f / 1.4g / 1.4k
**Date:** 2026-11-01
**Files:** `intake.py`, `results.py`, `scope.py`, `cli.py`

---

## The three gaps that mattered

Before this block the engine was correct and unusable in the field:

1. **A client sends a folder, not a file list.** Passing a directory produced a
   permission error counted as a parse error. Now files, folders, globs and zips
   are expanded into a deterministic stream of items, each with a classification
   and a reason: accepted, not-XML, unsupported document, syntax error, unreadable,
   duplicate, empty, too large.
2. **The output was console text.** Nothing downstream — CI, the packager, a
   client's integration — can consume that. There is now one JSON contract
   (`pint-ae/results-v1`) that carries its own provenance: tool version, spec
   version, rule-set SHA-256, regulation snapshot, per-file classification, scope
   and findings.
3. **One defect could appear three times.** A wrong VAT rate fired R-005, R-018
   and `ibr-190-ae`. The overlap map now keeps the official finding and records
   the local duplicate as suppressed, with the reason — visible in JSON, counted
   in the summary, never silently dropped.

## Decisions worth remembering

- **Classification is not validation.** "I could not read this" and "this invoice
  has errors" are different outcomes with different exit codes. Conflating them
  makes a batch report lie about the failure mode.
- **A duplicate is not a failure.** Clients send the same invoice twice; the run
  should not fail because of it, but the file must still be listed.
- **Exclusion is not a defect.** Tax-group intercompany transactions are excluded
  by law (MD 197/2026, to 31 Dec 2028). Reporting them as non-compliant would be
  the false positive that ends a client relationship. The scope label suppresses
  findings only where the exclusion is configuration-confirmed, and the suppressed
  findings stay in the JSON.
- **Heuristics must be labelled.** "Likely consumer" is advisory; it never hides
  an error, because a B2B invoice can also lack a TRN.
- **Determinism is part of the contract.** Sorted input, sorted findings, sorted
  JSON keys. Only the timestamps and environment line differ between runs, and
  that is stated rather than pretended.
- **Human locations beat XPaths.** "AccountingSupplierParty › Party › EndpointID"
  is actionable; `/*:Invoice[namespace-uri()='urn:oasis:...'][1]/...` is not.

## The lesson CI taught us

The sandbox this project is developed in cannot create pytest `tmp_path`
directories, so the 21 filesystem tests are CI-only. The first CI run of this
block failed on Linux because directory items used a path relative to the parent
(`batch/a.xml`) while single files used the full path - an inconsistency the
tests caught only on a real filesystem. The display contract is now explicit:
**full path for files and zip archives, plus `#member` for archive entries**.

Rule: any code that touches the filesystem is proven by CI, not by local
"it looked fine". When a block adds filesystem behaviour, read the CI log before
believing the block is done.

## What is still missing
- The scenario suite and its oracles (1.4h).
- Coverage floor and mutation checks (still open from the accuracy programme).
- Full exclusion classification for sovereign/airline/financial services, which a
  document cannot reliably tell us.
- Performance at 10k documents (baseline 0.145 s/invoice).

## Interview angle

Q: What is the difference between a validator and a tool?
A: A tool has an input contract, a classification for everything it is given, a
machine-readable output with provenance, deterministic ordering, meaningful exit
codes, and it never silently skips a file. The validator is the easy half.
