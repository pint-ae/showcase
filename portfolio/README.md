# PINT AE — Fabric showcase

A UAE e-invoicing compliance data product, built end-to-end in Microsoft Fabric. This public folder
demonstrates the **engineering**; the commercial value layer and its arithmetic are private.

**The problem:** the UAE mandates PINT AE e-invoicing for B2B invoices from 1 January 2027. Most
mid-market ERPs cannot emit a compliant invoice, and most rejections come from the accounting data, not
the e-invoice network.

**What this builds:** a pipeline that validates every invoice against 326 checks (302 official PINT AE
rules + 24 local interpretations), stores the results as Delta tables in a Fabric lakehouse, models them
in a Direct Lake semantic model with row-level security, and surfaces them in a report and a read-only
GraphQL API.

**The public demo:** [`index.html`](index.html) — a self-contained, synthetic-data view of the worklist,
the findings and the evidence trail.

## Try it in ten minutes

1. Open [`index.html`](index.html).
2. Read the three tiles (documents, clean, findings) and the worklist.
3. Read one finding — every one carries its rule id and citation.
4. Look at the evidence block: engine version, rule-set hash, regulation snapshot.
5. Read [`architecture.md`](architecture.md) for how it is built, and
   [`build-manual.md`](build-manual.md) for the exact steps.

## The parts

| Part | What it is |
|---|---|
| Engine (`pint-ae-toolkit`, PyPI) | parses and validates UBL 2.1 PINT AE invoices, 326 checks, EN/AR PDF reports |
| Lakehouse | 134 synthetic files + Gold Delta tables written by Spark notebooks |
| Semantic model | Direct Lake, additive schema, row-level security per entity |
| Report / API | the dashboard and a read-only GraphQL endpoint for downstream systems |
| Evidence | file hash, engine version, rule-set hash, regulation snapshot beside every finding |

## Decisions worth defending

1. **Direct Lake, not import** — a run shows up on the next page load with no refresh window (a live-demo
   killer otherwise).
2. **Additive model merge** — a script fetches the live model, backs it up, and adds only what is missing,
   never rewriting a relationship that exists.
3. **Evidence first** — every number traces to a file hash and a rule-set hash; coverage is labelled
   "coverage ≠ compliance".
4. **Row-level security** — three entity roles isolate what each business can see.
5. **Read-only API** — SQL analytics endpoints accept queries only; fixes stay in the customer's ERP.
6. **An honest boundary** — what was attempted and refused is recorded, including a report-import route
   that does not render on the trial tenant.

## What is deliberately not public

The reclaim arithmetic, the specific measures, pricing, the engagement tooling and any client material
are private. A CI leak scan fails the public export if they ever appear.

---

*Synthetic data. Advisory, not a tax ruling.*
