# 27 — Oracles, the synthetic client portfolio, and the operations commands

**Block:** 1.4h (scenario suite), 1.4i (operations), 1.4l (self-billing)
**Version:** 0.2.6
**Written after the fact**, like the others: what was built, what surprised us, and
what a reviewer should re-run.

---

## 1. The problem with "we tested it on 30 samples"

Thirty official samples prove the tool can read the publisher's documents. They do
**not** prove it finds a client's mistakes, because none of them contains a
mistake, and they do not prove it stays quiet on a clean invoice in a portfolio of
a hundred. Both directions matter commercially: a missed error is the product
failing, and a false positive on a compliant invoice destroys trust in the first
meeting.

So the accuracy claim needed four independent mechanisms, not one bigger fixture
set:

| Mechanism | Answers |
|---|---|
| Differential oracle | Does our wrapper report what the official artefact reports? |
| Mutation oracle | Does each local rule actually fire on its own defect? |
| Variance oracle | Do cosmetic changes change findings? (they must not) |
| Client portfolio | Does a realistic quarter come out exactly as declared? |

The first three are covered in note 26's block; this note is mostly about the
fourth, because that is the one a client can look at.

## 2. Why a generated corpus rather than a captured one

A captured corpus is real but unusable in the repository: it is client data, it
contains PII, and it cannot be published. A generated corpus is publishable, but
only if it is *internally consistent* — otherwise the tool reports dozens of
artefacts of the generator and the exercise proves nothing.

Consistency turned out to be the whole job. The generated documents had to satisfy
the official rules before they could carry an injected defect, which meant
learning the publisher's actual expectations the hard way:

- **TRN = 10-digit TIN + `01` + `003`.** Generate the endpoint id and the TRN from
  the same TIN and `R-022` / `IBR-149-AE` stay quiet; mismatch them and the
  coherence rules fire on every document.
- **Unit codes are a closed list** (UN/ECE Rec 20/21). `BG` (bag), `BX` (box) and
  `DR` (drum) are real Rec 20 codes that PINT AE 1.0.4 does **not** accept; the
  whole document fails `ibr-cl-23`. Cement bags became `NAR`, water cartons `CTN`,
  paint drums `LTR`.
- **Exempt supplies are not type 380.** `ibr-151-ae` requires at least one
  non-`E`/`O` line on a commercial invoice, and `ibr-167-ae` requires a VAT
  exemption reason code on the line; the official samples use type `480` with
  `VATEX-AE-EDU` and no VAT line amount (`ibr-163-ae`).
- **Reverse charge needs more than a code.** `ibr-166-ae` wants the type of goods
  (`BTAE-09`, `cac:CommodityClassification/cbc:NatureCode`) and `ibr-174-ae` wants
  the item standard identifier with scheme `0160`.
- **Credit notes need a reason and a reference.** `ibr-158-ae` wants
  `cac:DiscrepancyResponse/cbc:ResponseCode`; `ibr-055-ae` wants
  `cac:BillingReference` and a response code that is not `VD`.
- **A document-level allowance needs both base amount and percentage or neither**
  (`aligned-ibrp-057`); providing only the base amount is a fatal error.

Each of those was discovered because the "clean" document produced a finding, and
the finding was right. That is the corpus doing its job before it even reports a
defect.

## 3. One defect, several findings — and that is correct

The instinct is to map one injected defect to one expected assertion. The
publisher's rule set is layered, so it is not true: if the declared line total no
longer adds up, both `ibr-co-10` (sum of lines) and `ibr-co-13` (amount without
tax) are genuinely violated. If the line amount payable is missing, both
`ibr-104-ae` and `ibr-194-ae` fire. Declaring only the "primary" id would have
made the suite lie by omission.

So the manifest declares the **complete** reviewed set, and a separate test
asserts the same 100 documents against the publisher's XSLT directly. If our
expectation were wrong, the oracle would disagree; if our wrapper dropped a
finding, the oracle would disagree. Two independent statements must agree, which
is why the manifest can be trusted as documentation rather than a snapshot.

## 4. Determinism is a product feature, not a test convenience

The corpus dates every document in Oct–Nov 2026, before the 1 January 2027
mandate start. Two date-dependent rules exist (`R-024` transmission window,
`R-009` issue date not in the future) and both are silent for a past-dated
portfolio, so the reviewed expectations do not rot when the calendar moves. The
generator's pseudo-random choices come from SHA-256 of the seed and the document
index, not from `random`, so a Python upgrade cannot silently change the corpus.

That matters beyond tests: `pint-ae corpus --out demo/` is the demo path for a
prospect who will not send invoices. A demo that changes shape every release is
not a demo.

## 5. The two bugs the corpus found immediately

1. **Non-UTF-8 consoles killed the run.** Official messages contain `Σ`
   (`ibr-co-10` reads "Σ Invoice line net amount"). On a cp1252 console — the
   default on many Windows installs — printing that finding raised
   `UnicodeEncodeError` and the whole batch died after the first error. Fixed by
   reconfiguring the streams: interactive consoles replace unencodable characters,
   redirected output becomes UTF-8. The customer-facing lesson is that the report
   must never be the thing that fails.
2. **A folder holding a manifest was "not validated".** Writing
   `manifest.json` next to the invoices made `diagnose` classify it as `not-xml`
   and return exit code 2. Fixed by writing documents to `<out>/documents/`:
   a folder you point the tool at contains documents only.

## 6. Operations: `rules` and `selftest`

Two commands exist because a consultant on a client site needs them:

- `pint-ae rules` prints what this installation actually checks. The local count
  comes from `len(_RULES)`, the assertion counts from the vendored `.sch` files —
  no number in a proposal is typed by hand.
- `pint-ae selftest` fails if the vendored artefact hash no longer matches
  `EXPECTED_RULE_SET_SHA256`, if a stylesheet cannot load, or if the engine no
  longer reproduces a known finding on a generated sample. Before this block the
  hash was only *computed*; now it is *pinned*, so swapping a rule file is a
  deliberate act.

## 7. What is still not proven

- **Real exports.** The corpus is consistent by construction; real ERP output is
  not. This is the honest gap (G0) and only a client sample closes it.
- **ASP submission.** The invoice XML is not the ASP payload. Interoperability is
  unproven until a first ASP conversation produces a sample.
- **Scale.** ~0.15 s/invoice here; the 10k benchmark and `--jobs` are M5. The
  Saxon processor is not thread-safe, which is why a thread pool is not a
  shortcut and why the flag was deliberately not shipped in this block.
- **Two upstream artefacts limitations** (`ibr-128-ae` shadowing, `BR-CL-23`
  crashing on an empty numeric) are carried as classified failures, documented in
  `VERIFICATION.md` §8.3 — not silently worked around.

## 8. Re-run it

    pint-ae selftest
    pint-ae corpus --out demo/ && pint-ae diagnose demo/documents/
    pytest tests/test_corpus.py tests/test_differential.py tests/test_mutation.py -q
    pytest --collect-only -q | tail -1     # 785 tests
