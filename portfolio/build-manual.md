# Build manual — the Fabric pattern (public edition)

This is the **pattern** to rebuild the showcase in Fabric, with the money-specific measures renamed to
illustrative placeholders so the commercial logic stays private. The steps, the items and the order are
real.

## 1. Workspace and capacity

1. https://app.fabric.microsoft.com → **Workspaces → New workspace** → `acme-n1` → assign a capacity.
2. Confirm the workspace is Active.

## 2. Lakehouse and data

1. **+ New item → Lakehouse** → `pint_ae_lakehouse`.
2. Folders `corpus`, `purchase`, `value`, `value/golden`, `licences`, `diagnostics`.
3. Upload the 100 XML invoices into `corpus`, the 20 into `purchase`, and the value files into `value/`.
4. Upload the signed licence into `licences/` — without it the engine runs free tier (3 modules) and the
   numbers are wrong for a demo.

## 3. Notebooks

1. **+ New item → Notebook** → `nb_n1_validate`; attach the lakehouse; paste the validation notebook;
   **Run all**. Check the licence print and `findings=72`.
2. Repeat for `nb_n1_value` (the worklist/drill layer). Its final table is the reconciliation.
3. On a paid tenant, replace `%pip` with an **Environment** item carrying the pinned wheel.

## 4. Semantic model

1. Lakehouse → **SQL analytics endpoint → New semantic model** → tick the Gold tables.
2. **Manage relationships** — one path per table pair (a second path is refused as "ambiguous").
3. **New measure** — the reporting measures (a public example: `[Documents] = COUNTROWS(gold_documents)`;
   the money measures are private and omitted here).
4. **New parameter → Numeric range** for a what-if scenario; **New parameter → Fields** to switch a chart's
   dimension.
5. **Manage roles** — one role per entity filtering the entity column; **View as role** to test isolation.

## 5. Report

1. **New report** from the model; import the theme.
2. Five pages — snapshot (sentence + tiles + worklist), analyse (decomposition, control band, histogram,
   recurrence), fix (the table), invoice detail (the drill target with evidence), prove (the scenario).
3. Tooltip page, drill-through on the drill key, bookmarks for the demo states, sync slicers, phone layout.
4. Publish, or build in the UI — REST-imported reports do not render on the trial tenant.

## 6. Pipeline

1. **+ New item → Data pipeline** → two notebook activities in order (validate, then value), with a
   `Succeeded` dependency.
2. Schedule it; add a failure alert. A pipeline that runs only the first notebook leaves the value tables
   stale.

## 7. GraphQL API

1. A **Warehouse** (paid F64+) with keyed tables — the lakehouse Delta tables have no primary key and
   GraphQL refuses keyless objects.
2. **+ New item → API for GraphQL** → connect the warehouse → expose the tables → run a query.
3. Permissions: the demo account gets **Run queries only**; an app registration needs `GraphQLApi.Execute.All`.

## Verification checklist

- [ ] The reconciliation matches the pinned numbers (documents, clean, with-errors, findings, worklist).
- [ ] The notebook prints `licence: licensed · 8 modules`.
- [ ] The model shows the tables, relationships, measures and roles.
- [ ] An invoice drills through to its findings and evidence.
- [ ] `View as role` changes the numbers.
- [ ] The pipeline runs both notebooks and the timestamps move.
- [ ] If the API is in the meeting: one query returns the same counts.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `corpus=0` | re-upload; check the lakehouse attached to the notebook |
| `findings=48`, licence free | upload the licence into `Files/licences` |
| job fails instantly | capacity throttled — wait, or use paid |
| "ambiguous paths between X and Y" | delete one relationship |
| GraphQL schema fails | object has no primary key — use keyed warehouse tables |
| first API query times out | warm the endpoint first |
