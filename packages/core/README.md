# packages/core

The PINT AE conformance engine: typed model, UBL 2.1 parser, XSD validation,
Schematron pipeline, UAE business rules, a synthetic portfolio generator,
bilingual PDF report and the `pint-ae` CLI.

**Licence:** Apache-2.0 (see `LICENSE` in this directory, attribution in
`NOTICE`) - this is the subset published as the public showcase.

## Verify

    pwsh -File ../../scripts/verify.ps1

Prints the derived counts (custom rules, Schematron assertions, total checks,
tests) and runs format, lint, types and tests. From a published checkout without
the repository tooling, use the commands in "Try it" below instead.

## Try it

    pint-ae corpus --out demo/                # 100 generated documents, 40 with a defect
    pint-ae diagnose demo/documents/          # 60 clean, 40 with errors
    pint-ae modules                           # 8 modules that own the 326 checks
    pint-ae diagnose demo/documents/ --modules parties
    pint-ae rules                             # every check, counted from the artefacts
    pint-ae selftest                          # is this installation intact?

## Layout

- `types.py` - pydantic models (Decimal money, UAE identifiers)
- `parser.py` - UBL 2.1 XML to `PintAeInvoice` (billing and self-billing)
- `xsd_validator.py` - UBL 2.1 schema validation
- `schema/` - see `schematron/` for the official rule artefacts (vendored,
  hash-pinned) and the legacy opt-in pair
- `rules.py` - 24 custom UAE rules and the `_RULES` registry
- `modules.py` - the eight modules that own the checks (stable public ids)
- `regulatory.py` - pinned spec version, rule-set hash, regulation snapshot
- `corpus.py` - deterministic synthetic client portfolio generator
- `pdf.py` - bilingual (EN/AR) diagnostic report
- `cli.py` - `diagnose`, `report`, `corpus`, `rules`, `selftest`

## Tests

Run from this directory with the project installed (`pip install -e ".[dev]"`):

    pytest

The suite covers the official samples, a differential oracle against the
publisher's own XSLT, per-rule mutation checks, and the generated corpus whose
expectations are declared in `tests/fixtures/corpus/manifest.json`.
