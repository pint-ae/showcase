# Architecture

How the showcase is built, and why each choice was made. The money layer is omitted here; this is the
engineering.

```
 UBL XML (100 invoices)  ──►  notebook: validate  ──►  Delta tables  ──►  semantic model ──►  report
   Files/corpus                 (engine 0.6.1)          gold_*           (Direct Lake)     └──► GraphQL API
        │                              │                    │
        └── Files/value ◄──────────────┴── notebook: value layer (worklist, evidence)
```

## Layers

1. **Engine** — `pint-ae-toolkit` (PyPI): parses UBL 2.1, runs 326 checks, returns findings with the rule
   id and citation. Vendored, hash-pinned rules; 24 local interpretations on top of the official set.
2. **Lakehouse** — `Files/` holds the source XML and the value CSVs; `Tables/` holds the Gold Delta tables
   written by the notebooks (`gold_documents`, `gold_findings`, `gold_intake`, `gold_runs`, plus the value
   tables).
3. **Notebooks** — PySpark: `nb_n1_validate` runs the engine and writes the Gold tables;
   `nb_n1_value` adds the drill key and the worklist. The schema is aligned to the model, not the reverse,
   so a re-run cannot silently break a relationship or a role.
4. **Semantic model** — Direct Lake over the Delta tables: no import, no refresh window. Built additively:
   a script fetches the live TMDL, backs it up, and adds only what is missing.
5. **Report** — five pages (snapshot, analyse, fix, invoice detail, prove) with drill-through, a tooltip
   page, bookmarks for the demo states, sync slicers and a phone layout.
6. **GraphQL API** — read-only queries over a keyed surface (a warehouse, because lakehouse Delta tables
   have no primary key and GraphQL refuses keyless objects).

## Decisions and trade-offs

| Decision | Trade-off accepted |
|---|---|
| Direct Lake | no refresh window, but the model schema must match the Delta schema exactly |
| Additive model merge | never delete a hand-built object, at the cost of a script that must be idempotent |
| Evidence beside every finding | more columns, but an auditor gets the hash and the rule set, not a claim |
| Row-level security per entity | three roles to maintain, but the demo can show isolation honestly |
| Read-only API | no write path, but no write risk and a clean contract for the customer's systems |
| Notebooks pin the engine version | a manual bump, but never a silent behaviour change |

## Honest limitations

- The report cannot be produced-and-rendered by the REST API on the trial tenant (it imports but does not
  materialise); the working route is the UI build or a publish from Power BI Desktop.
- Trial capacity throttles Spark; a paid F64+ capacity removes the queue.
- Direct Lake models cannot be opened as local projects in Desktop; they are connected to the published
  model.
