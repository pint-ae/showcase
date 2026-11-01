# packages/core

The PINT AE conformance engine: typed model, UBL 2.1 parser, XSD validation,
Schematron pipeline, UAE business rules, a deterministic synthetic portfolio
generator, bilingual PDF reports and the `pint-ae` CLI.

**Licence:** Business Source License 1.1 (see `LICENSE`; attribution in `NOTICE`).
Evaluation and other non-production use are free; **production use requires a
commercial licence**. Four years after each release that version becomes
Apache-2.0. This directory is the engine we publish; the private client-pack tooling,
the module tuning and client-specific mappings are not part of it.

## What it checks

Eight modules own 326 checks: the official PINT AE Billing 1.0.4 Schematron set
(302 assertions, vendored and pinned by SHA-256, XSLT precompiled) plus 24 local
UAE rules (arithmetic, identifiers, emirate codes, the MD 197/2026 transmission
window and the tax-group exclusion), with UBL 2.1 XSD validation on top.

## What a free installation reports

A fresh installation is the **free tier**: `core-conformance`, `arithmetic` and
`emirate` run; `currency`, `parties`, `payments`, `transaction-type` and
`vat-categories` are withheld and reported as "not licensed" - never as clean.
`pint-ae modules` shows the state per module. A signed `pint-ae.lic` unlocks the
rest; production use is licensed under BUSL-1.1 (see `LICENSE`).

## Try it

    pint-ae corpus --out demo/                # 100 generated documents, 40 with a defect
    pint-ae diagnose demo/documents/          # 70 clean, 30 with errors (free tier)
    pint-ae diagnose demo/documents/ --json results.json
    pint-ae modules                           # what this installation may report
    pint-ae rules                             # every check, counted from the artefacts
    pint-ae selftest                          # is this installation intact?

The same corpus reports 60 clean / 40 with errors once a licence unlocks all
eight modules. Exit codes: `0` clean, `1` errors, `2` some input could not be
validated, `3` usage error (including asking for a module you are not licensed
for, or an unknown module id).

## Layout

- `types.py` - pydantic models (Decimal money, UAE identifiers)
- `parser.py` - UBL 2.1 XML to `PintAeInvoice` (billing and self-billing)
- `intake.py` - files, folders, globs and `.zip` archives; nothing silently skipped
- `xsd_validator.py` - UBL 2.1 schema validation
- `schematron/` - the vendored, hash-pinned official XSLT artefacts
- `rules.py` - 24 custom UAE rules and the `_RULES` registry
- `modules.py` - the eight modules that own the checks (stable public ids)
- `licensing.py` - signed entitlements and the free tier
- `config.py` - `pint-ae.toml` (modules, thresholds, severity overrides)
- `regulatory.py` - pinned spec version, rule-set hash, regulation snapshot
- `corpus.py` - deterministic synthetic client portfolio generator
- `pdf.py` - bilingual (EN/AR) diagnostic report
- `compare.py` - two-round comparison: fixed / still failing / newly broken
- `results.py` - the `pint-ae/results-v1` JSON contract
- `cli.py` - `diagnose`, `report`, `corpus`, `compare`, `modules`, `rules`,
  `selftest`, `config` (plus `--jobs` for process-parallel batches)

## Verify

    pint-ae selftest                          # artefact hashes and packaged data
    pint-ae modules                           # entitlement state per module
    pint-ae rules                             # counts derived from the artefacts

The repository's own test suite, benchmark scripts and packaging checks are not
part of the published subset; they stay in the private repository.

## Known limits

- The CII (Cross Industry Invoice) syntax and the older opt-in Schematron pair are
  not validated, by design: PINT AE is UBL.
- Arabic PDF text needs a bundled font; when none is available the report says so
  instead of rendering a substitute.
