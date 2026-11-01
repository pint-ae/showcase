# Learning Note 05 — Field Maps and Spec Traceability

**Block:** 6.4
**Date:** 2026-10-31
**File:** docs/sources/pint-ae-bis-1.0.4/field-map.md
**Spec:** PINT AE Billing 1.0.4 (extends Peppol BIS Billing 3.0)

---

## The concept

A field map is a table that connects a spec reference to a code location
and a test. Each row is one atomic requirement.

Two identifier systems are in play:

1. UBL element names (cbc:ID, cac:Party) - the XML shape
2. Peppol Business Terms (BT-1, BT-31) - the international semantic identifier

PINT AE extends Peppol BIS Billing 3.0, so BT numbers come from the base
standard. The PINT AE layer adds UAE-specific constraints on top of some
of those BTs (e.g., BT-31 must be a 15-digit TRN, not any VAT number).

This is why we use BT numbers in the field map: they are stable across
Peppol profiles and let the same field be referenced in EU and UAE
contexts.

---

## How we implement it here

The public field map covers 15 of the 51 mandatory fields - the structural
subset every invoice shares (identifiers, parties, totals). The remaining
36 (TaxSubtotal, InvoiceLine children, AE extensions) are in the private
repo's extended map.

The PINT AE section column is marked [W1] for rows that will be verified
against the PINT AE BIS HTML in Week 1 as each rule is implemented. This
is deliberate - transcribing 15 paragraph numbers in a single sitting is
busywork, but verifying one BT at a time as you write the corresponding
test is real learning.

---

## Why this is the moat

When a client gets a rejection, they will ask "according to what?". The
answer must be citable. Without field-map.md, the answer is "my code says
so" - a script. With it, the answer is "BT-31, PINT AE Billing 1.0.4
constrains the seller VAT identifier to a 15-digit TRN". That is a product.

The private map grows to 200+ rows as the client base grows. Each row that
comes from real client data - a specific UAE edge case, a specific ASP
behaviour, a specific FTA interpretation - is a row no competitor has.

---

## Interview Q&A

Q: How do you ensure your validator is correct?
A: Every rule is traceable to a BT number and, in Week 1, to a PINT AE
paragraph. CI runs tests. If a client disputes a rejection, I open the
field-map row and read them the citation.

Q: Why BT numbers and not paragraph numbers?
A: BT numbers are stable across Peppol profiles and standard versions.
PINT AE inherits them from Peppol BIS Billing 3.0. A paragraph number
changes when the document is republished; a BT number is permanent.

Q: What is [W1]?
A: A marker meaning "verify in Week 1". It is not a placeholder for missing
work - it is a scheduled verification. Every [W1] becomes a concrete
paragraph reference before the corresponding rule ships.

Q: What if a field has no BT number?
A: It is a UAE-specific extension and does not belong in the public field
map. It goes in the private extended map.

Q: Why so few rows in the public version?
A: The public version demonstrates the method. The full 51-field map plus
AE extensions (reverse charge, DZ flows, zero-rating evidence) is the
accumulated client-specific moat, and lives in the private repo.

---

## Spec reference

- Peppol BIS Billing 3.0 Business Terms: https://docs.peppol.eu/poacc/billing/3.0/
- PINT AE Billing 1.0.4 BIS: https://docs.peppol.eu/poac/ae/upcoming/pint-ae/bis/
