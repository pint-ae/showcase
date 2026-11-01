# Learning Note 01 — UBL, Peppol, and PINT AE

**Block:** 6.1
**Date:** 2026-10-31
**Spec version:** PINT AE Billing 1.0.4
**Spec URL:** https://docs.peppol.eu/poac/ae/upcoming/pint-ae/bis/

---

## The concept

**UBL 2.1** is an XML schema standard published by OASIS for business
documents (invoice, credit note, order, despatch advice). It exists because
EU public procurement needed a machine-readable invoice format, and every ERP
had its own XML dialect.

**Peppol** is not a format — it is the network and governance structure that
carries UBL documents between access points. Run by OpenPeppol (a Belgian
non-profit), Peppol defines:

- The transport protocol (AS4) that moves the document from sender's access
  point to receiver's access point
- The BIS (Business Interoperability Specifications) — UBL profiles that
  declare which fields are mandatory, at what cardinality, for what document type
- The directory that maps Peppol IDs to access points

**PINT AE** (Peppol International Invoice for the UAE) is a CIUS —
a Contextualized Implementation Specification — of Peppol BIS Billing 3.0.
It constrains the EU base standard to UAE requirements:

- Adds the 15-digit TRN as the mandatory tax identifier
- Restricts VAT categories to S, Z, E, O, AE
- Fixes currency fields to AED where applicable
- Adds UAE-specific Schematron rules, verified against
  `urn:peppol:pint:billing-1@ae-1` in `cbc:CustomizationID`

Current version is 1.0.4. Prior version was 1.0.3. 1.0.4 was a minor
correction release — reverse-charge VAT category handling and Schematron
rule fixes. No field additions or removals.

---

## How we implement it here

- Fixtures use `urn:peppol:pint:billing-1@ae-1` as the `cbc:CustomizationID`
- The parser assumes UBL 2.1 structure: root `Invoice`, `cac:` and `cbc:`
  namespaces
- We extract the PINT AE mandatory subset, not the full UBL element set

---

## Interview Q&A

**Q: What is PINT AE?**
A: Peppol International Invoice for the UAE — a Peppol BIS that customizes the
EU Peppol Billing 3.0 standard for UAE e-invoicing. Current version 1.0.4.

**Q: Why UBL and not JSON?**
A: OASIS standard, used in EU public procurement since 2017, and Peppol requires
it for interoperability. No JSON equivalent exists in the Peppol BIS family.

**Q: What is a CIUS?**
A: Contextualized Implementation Specification — a constrained subset of a base
standard. PINT AE is a CIUS of Peppol BIS Billing 3.0.

**Q: What is the relationship between Peppol and UBL?**
A: UBL is the document format; Peppol is the transport network and governance
layer. Peppol uses UBL, but UBL exists independently.

**Q: What changed in PINT AE 1.0.4?**
A: Minor fixes to reverse-charge VAT category handling and Schematron rule
corrections. The `CustomizationID` prefix remains
`urn:peppol:pint:billing@ae-1` — the version suffix is not in the ID.

---

## Spec reference

- PINT AE Billing 1.0.4 BIS: https://docs.peppol.eu/poac/ae/upcoming/pint-ae/bis/
- PINT AE 1.0.4 release notes: https://docs.peppol.eu/poac/ae/upcoming/pint-ae/specialized-release-notes/
- Peppol BIS Billing 3.0: https://docs.peppol.eu/poacc/billing/3.0/
- OASIS UBL 2.1: http://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.pdf
