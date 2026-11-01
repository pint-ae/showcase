# Learning Note 04 — lxml and XPath

**Block:** 6.3b
**Date:** 2026-10-31
**Code:** packages/core/src/pint_ae/parser.py
**Spec:** PINT AE Billing 1.0.4 - https://docs.peppol.eu/poac/ae/upcoming/pint-ae/bis/

---

## The concept

lxml is a Python binding to libxml2 (C library). It parses XML into an
element tree that Python can navigate. XPath is the query language used
to reach any node in the tree.

Three XPath patterns we use:
- find("cac:Party") - first matching child
- findall("cac:InvoiceLine") - all matching children (list)
- findtext("cbc:ID") - first matching child's text content

The three parts of every XPath: node path (cac:), prefix, and local name.
The prefix is defined in NSMAP and maps to the namespace URI. NEVER use the
prefix from the document itself - it may differ.

---

## How we implement it here

The parser exposes one public function:

  parse(xml: str | bytes) -> PintAeInvoice

Internally:
1. etree.fromstring() builds the tree.
2. _parse_party() extracts supplier and customer.
3. _parse_tax_category() extracts each TaxCategory.
4. _parse_line() extracts each LineItem.
5. The top-level parse() assembles PintAeInvoice.

Errors are explicit: if a required element is missing, ValueError is raised
with the XPath that failed. No silent defaults for mandatory fields.

Optional fields use _opt_text() which returns None when missing.

---

## Why the parser is deliberately boring

The parser is a TRANSFORM, not a product. Its only job is XML -> PintAeInvoice.
Every product (N1, N2, N3) is a different view over the typed object. If the
parser tried to validate, reconcile, or score, it would conflate concerns and
be harder to test.

Keep it simple. Rules live in rules/. Reconciliation lives in reconciler/.
The parser is just the front door.

---

## Interview Q&A

Q: Why bind namespaces by URI not prefix?
A: The document author chooses prefixes. A document could use ns1: instead
of cbc: for the same URI. NSMAP binds URI-to-prefix in our code, so XPath
is robust regardless of the document's prefix choice.

Q: find vs findtext?
A: find returns the element (need attributes, e.g., schemeID). findtext
returns just the text (shorthand for text extraction). We use findtext
when we only need the value, find when we need attributes.

Q: fromstring vs parse?
A: fromstring parses from a bytes/str already in memory. parse() reads from
a file path or file object. Our API accepts bytes, so fromstring.

Q: How do you handle a missing required element?
A: _text() raises ValueError with the failing XPath. This is deliberate - in
tax processing, a missing mandatory field is a hard error. Optional fields
use _opt_text() which returns None.

Q: What about performance?
A: lxml is C-backed, parses ~10,000 small invoices per second on a laptop.
At invoice scale (thousands per day), the parser is not the bottleneck.
If it ever is, batch and parallelise with multiprocessing.

---

## Spec reference

- lxml documentation: https://lxml.de/
- XPath tutorial: https://www.w3schools.com/xml/xpath_intro.asp
- PINT AE Billing 1.0.4 BIS: https://docs.peppol.eu/poac/ae/upcoming/pint-ae/bis/
