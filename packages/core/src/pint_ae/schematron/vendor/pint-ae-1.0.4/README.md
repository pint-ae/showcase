# Vendored PINT AE 1.0.4 Schematron artefacts

**Source:** https://docs.peppol.eu/poac/ae/pint-ae/resources.zip
**Package SHA-256:** `1e8b0bd595c672ac9d6fc886ddd0eb8027cb39a1d26bebdcb1ada37b7eee491f`
**Fetched:** 2026-11-01
**Spec:** PINT AE Billing 1.0.4 (released 2026-06-02; PINT General 1.1.3)
**Publisher:** OpenPeppol AISBL / UAE Peppol Authority. See the package's own
terms; these files are redistributed here unmodified.

## Files

| file | bytes | sha256 | what |
|---|---|---|---|
| `jurisdiction.sch` | 70998 | `d0e767f246fa8e90749060a51fea5a22e03659ae83ec66aff9cfd3b932168a3e` | UAE jurisdiction rules (source) |
| `jurisdiction.xslt` | 200074 | `da931f161362fe26bb9f5a1e519cd44758e5cba977584800b806c09bcf1b807b` | Publisher-precompiled XSLT for the AE rules |
| `shared.sch` | 79671 | `c073dd645db0401a3276cfa31f381750d35f7fde8381b19b92b8bceee236f534` | Shared PINT rules (source) |
| `shared.xslt` | 243710 | `b6557c207f1cccaebf32b67ae0d50b309192751b58ddd22fa5af90c6d45f7d16` | Publisher-precompiled XSLT for the shared rules |

## Measured assertion counts

- `shared.sch`: **170** asserts, all `flag="fatal"`
- `jurisdiction.sch`: **132** asserts, all `flag="fatal"`
- Official conformance set: **302** assertions, all fatal

## Verified

Both precompiled XSLTs run against all 30 official examples with **0 failed
assertions** (measured 2026-11-01). That is the golden baseline: the
publisher's own samples pass the publisher's own rules.

## Status: wired and pinned

`pint_ae/schematron/validator.py` runs this official pair by default; the older
vendored pair (`shared_pint.sch` 171 asserts, `peppol_bis3.sch` 160) is opt-in via
`--peppol-bis3` and reported as warnings. All 302 official assertions carry
`flag="fatal"`, so a failure is an `error`. The combined SHA-256 of the two rule
files is pinned in `pint_ae/regulatory.py` and re-verified by `pint-ae selftest`.

## Refresh procedure

1. Re-download the package from the URL above.
2. Replace the four files and recompute the hashes in this README and in the
   source manifest used for provenance.
3. Update `EXPECTED_RULE_SET_SHA256` in `pint_ae/regulatory.py`; `pint-ae selftest`
   fails until the pin and the files agree again.
4. If the assertion counts changed, treat it as a rule-set change: re-run the
   differential and corpus tests before accepting it.
