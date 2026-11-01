"""Pydantic models for PINT AE invoices (UBL 2.1 subset).

Field names follow the PINT AE BIS 1.0.4 business terms in snake_case.
All monetary and quantity values use Decimal for tax-grade precision.

See: docs/learning/03_pydantic_for_tax_data.md
Spec: PINT AE Billing 1.0.4 - https://docs.peppol.eu/poac/ae/pint-ae/bis/
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Party(BaseModel):
    """A supplier or customer in a PINT AE invoice."""

    name: str = Field(..., min_length=1, max_length=200)
    trn: str | None = Field(
        default=None,
        min_length=15,
        max_length=15,
        pattern=r"^\d{15}$",
        description=(
            "VAT registration number (15 digits). Optional: exports and zero-rated "
            "supplies may have no buyer VAT identifier; absence is reported by R-022."
        ),
    )
    peppol_id: str | None = Field(default=None)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    country_subentity: str | None = Field(
        default=None,
        description="UAE emirate code (AUH/DXB/SHJ/AJM/UAQ/FUJ/RAK)",
    )
    legal_registration: str | None = Field(
        default=None,
        description="cac:PartyLegalEntity/cbc:CompanyID (IBT-030/IBT-047), if present",
    )
    is_person: bool = Field(
        default=False,
        description="True when the party is a natural person (cac:Person) - advisory B2C signal",
    )


class TaxCategory(BaseModel):
    """A VAT tax category (aligned UAE list: S, Z, E, O, AE, N)."""

    code: str = Field(..., min_length=1, max_length=2, pattern=r"^(S|Z|E|O|AE|N)$")
    percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Absent for Exempt and Not-subject categories per IBR-119-AE",
    )
    taxable_amount: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)


class LineItem(BaseModel):
    """A single invoice line item."""

    line_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_code: str = Field(default="EA", min_length=1, max_length=3)
    unit_price: Decimal = Field(..., ge=0)
    base_quantity: Decimal | None = Field(
        default=None, gt=0, description="cac:Price/cbc:BaseQuantity (IBT-149)"
    )
    allowance_total: Decimal = Field(default=Decimal("0"), ge=0)
    charge_total: Decimal = Field(default=Decimal("0"), ge=0)
    line_total: Decimal = Field(..., ge=0)
    tax_category: TaxCategory


class PintAeInvoice(BaseModel):
    """A PINT AE document (subset of the mandatory fields)."""

    customization_id: str = Field(..., pattern=r"^urn:peppol:pint:(billing|selfbilling)-1@ae-1$")
    profile_id: str = Field(default="urn:peppol:bis:billing")
    document_type: str = Field(
        default="invoice",
        pattern=r"^(invoice|credit-note|self-billed-invoice|self-billed-credit-note)$",
        description="Invoice or CreditNote, standard or self-billed",
    )
    invoice_id: str = Field(..., min_length=1, max_length=50)
    issue_date: date
    invoice_type_code: str = Field(..., pattern=r"^\d{3}$")
    document_currency_code: str = Field(..., min_length=3, max_length=3)
    transaction_type_code: str | None = Field(
        default=None,
        description=(
            "Invoice transaction-type code (BTAE-02), carried in cbc:ProfileExecutionID. "
            "Mandatory and 8 binary digits per IBR-154-AE; validated by the official "
            "Schematron layer, not by a local rule."
        ),
    )
    supplier: Party
    customer: Party
    tax_categories: list[TaxCategory] = Field(..., min_length=1)
    line_items: list[LineItem] = Field(..., min_length=1)
    line_extension_amount: Decimal = Field(..., ge=0)
    tax_exclusive_amount: Decimal = Field(..., ge=0)
    tax_inclusive_amount: Decimal = Field(..., ge=0)
    prepaid_amount: Decimal | None = Field(default=None, ge=0)
    payable_rounding_amount: Decimal | None = Field(default=None)
    payable_amount: Decimal = Field(..., ge=0)
