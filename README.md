# pint-ae toolkit — showcase

Demonstration of a PINT AE validation toolkit built for the UAE e-invoicing mandate (Phase 1 Jan 2027, Phase 2 Jul 2027).

## What the toolkit does

Parses PINT AE invoices (UBL 2.1 XML), validates against Peppol BIS Billing 3.0 business rules, and emits structured violations with citations to the standard.

## What's in this repo

- [`docs/01_5_corner_model.md`](docs/01_5_corner_model.md) — how the UAE 5-corner e-invoicing model works
- [`notebooks-html/`](notebooks-html/) — walkthrough of parsing and validation (rendered HTML)

## Commercial edition

The full toolkit is available through commercial engagement. It includes:
- Extended rule library (40+ rules vs 5 shown here)
- Reverse-charge and Designated Zone flow handling
- Per-ERP field mappings (SAP, Oracle, Dynamics, NetSuite, Tally)
- Tuned thresholds per sector and per client

## Author

Solo practitioner, Microsoft Fabric and Python specialist. Built for the UAE e-invoicing mandate.
