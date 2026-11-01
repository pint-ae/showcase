# pint-ae toolkit

Parsing, validation and diagnostics for **PINT AE** e-invoices (UBL 2.1) - the UAE
Peppol Authority's e-invoicing standard, PINT AE Billing 1.0.4.

This repository is the published, source-available subset of a larger commercial
product (Business Source License 1.1: evaluation use is free, production use is
licensed):
the conformance engine, the official PINT AE rule set (302 assertions, vendored and
pinned by SHA-256) and 24 local UAE rules. The commercial engagement tooling, the
module tuning and the client-specific mappings are **not** part of it.

## What it does

- Parses UBL 2.1 `Invoice` and `CreditNote` documents into a typed model.
- Validates against the official PINT AE 1.0.4 artefacts: 302 Schematron
  assertions, all `flag="fatal"`, plus UBL 2.1 XSD.
- Adds 24 local UAE rules (arithmetic, identifiers, emirate codes, MD 197/2026
  transmission window and tax-group exclusion): **326 checks per document**.
- Accepts files, folders, globs and `.zip` archives; every input is classified and
  never silently skipped.
- Emits a machine-readable contract (`pint-ae/results-v1`) and bilingual EN/AR PDF
  reports that carry the spec version, the rule-set SHA-256 and the regulation
  snapshot.

## Install

    git clone https://github.com/pint-ae/showcase
    cd showcase/packages/core
    python -m venv .venv && . .venv/bin/activate      # or .venv\Scripts\activate
    pip install -e .

## Usage

    pint-ae diagnose invoices/                       # files, folders, globs or zips
    pint-ae diagnose invoices/ --json results.json
    pint-ae corpus --out demo/                       # generate a portfolio to try it on
    pint-ae diagnose demo/documents/                 # 70 clean, 30 with errors (free tier)
    pint-ae modules                                  # what this installation may report
    pint-ae rules                                    # every check, counted from the artefacts
    pint-ae selftest                                 # is this installation intact?

**Entitlements.** A public installation is the free tier: `core-conformance`,
`arithmetic` and `emirate` run; `currency`, `parties`, `payments`, `transaction-type`
and `vat-categories` are withheld and reported as "not licensed" - never as clean. A
signed `pint-ae.lic` unlocks them (production use is licensed; see `LICENSE`). On the
generated demo portfolio that is the difference between 70 and 60 clean documents.

**Exit codes:** `0` clean, `1` errors, `2` some input could not be validated,
`3` usage error (including asking for a module you are not licensed for).

## Provenance

The vendored artefacts come from `docs.peppol.eu` and are redistributed unmodified;
their SHA-256s are in `NOTICE` and are re-verified by `pint-ae selftest`.

## Licence

Business Source License 1.1 - evaluation and other non-production use are permitted;
production use requires a commercial licence. See `LICENSE` (parameters and reference)
and `NOTICE` (third-party attribution). Module entitlements are enforced by a signed
`pint-ae.lic`.
