"""Scope classification (MD 243/2025 as amended by MD 197/2026).

The diagnostic must not call an excluded transaction non-compliant. Exclusions
fall into three groups:

1. **Configuration-known** — intra-tax-group transactions (Art. 4(1)(f)): both
   TRNs are in the configured tax-group set. These are excluded, and their
   compliance findings are suppressed (recorded, not hidden).
2. **Document-inferable (advisory)** — a consumer supply: the buyer is a natural
   person, or has no VAT identifier, electronic address or legal registration.
   This is a *label*, never a suppression: a B2B invoice can also lack a TRN, and
   hiding the resulting errors would be dangerous.
3. **Not determinable from the document** — sovereign government acts, airline
   transport and VAT-exempt/zero-rated financial services. The tool says
   ``unknown`` rather than guessing.
"""

from __future__ import annotations

from pint_ae.types import PintAeInvoice

IN_SCOPE = "in-scope"
EXCLUDED_TAX_GROUP = "excluded-tax-group"
LIKELY_CONSUMER = "likely-consumer"
UNKNOWN = "unknown"

_SCOPE_VALUES = (IN_SCOPE, EXCLUDED_TAX_GROUP, LIKELY_CONSUMER, UNKNOWN)


def document_type(inv: PintAeInvoice) -> str:
    """Return the parsed type: invoice, credit-note, or their self-billed variants."""
    return inv.document_type


def classify(inv: PintAeInvoice, tax_group_trns: set[str] | None = None) -> tuple[str, str]:
    """Return ``(scope, reason)`` for a parsed document.

    ``excluded-tax-group`` is the only value that justifies suppressing findings;
    the caller decides what to do with it.
    """
    trns = tax_group_trns or set()
    if trns and inv.supplier.trn in trns and inv.customer.trn in trns:
        return (
            EXCLUDED_TAX_GROUP,
            "both parties are in the configured tax group - excluded from the system "
            "until 31 Dec 2028 (MD 197/2026, Art. 4(1)(f))",
        )

    buyer = inv.customer
    if buyer.is_person:
        return (
            LIKELY_CONSUMER,
            "buyer is a natural person; B2C supplies are outside the system until a "
            "Minister decision (advisory label, findings are still reported)",
        )
    if buyer.trn is None and buyer.peppol_id is None and buyer.legal_registration is None:
        return (
            LIKELY_CONSUMER,
            "buyer has no VAT identifier, electronic address or legal registration; "
            "this looks like a consumer supply (advisory label, findings are still "
            "reported)",
        )

    return (
        IN_SCOPE,
        "business transaction with an identifiable counterparty; sovereign, airline "
        "and financial-service exclusions are not determinable from the document",
    )
