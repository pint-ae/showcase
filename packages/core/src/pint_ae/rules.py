"""PINT AE business rules validator.

The rule count is deliberately not written here: it derives from the `_RULES`
registry at the bottom of the module, so the PDF scope line and the methodology
cannot drift away from what actually runs.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path

from lxml import etree

from pint_ae.types import PintAeInvoice

#: Fallback only. The authoritative list is the official PINT AE 1.0.4 code
#: list, loaded by `document_type_codes()` (IBR-CL-01).
ALLOWED_TYPE_CODES = {"380", "381", "383", "384", "386", "388", "389", "393", "395"}
ALLOWED_CURRENCIES = {"AED", "USD", "EUR", "GBP", "SAR", "OMR", "KWD", "BHD", "QAR"}
ALLOWED_VAT_CODES = {"S", "Z", "E", "O", "AE", "N"}

_VENDOR_DIR = Path(__file__).parent / "schematron" / "vendor" / "pint-ae-1.0.4"
_SB_VENDOR_DIR = Path(__file__).parent / "schematron" / "vendor" / "pint-ae-sb-1.0.4"
_GENERICODE_NS = "{http://docs.oasis-open.org/codelist/ns/genericode/1.0/}"
_DOCUMENT_CODE_LISTS = (
    _VENDOR_DIR / "UNCL1001-invoice.gc",
    _VENDOR_DIR / "UNCL1001-creditnote.gc",
    _SB_VENDOR_DIR / "UNCL1001-invoice.gc",
    _SB_VENDOR_DIR / "UNCL1001-creditnote.gc",
)

_VAT_GROUP_TRNS: set[str] = set()
_reference_date: date | None = None

#: The e-invoicing mandate start. Time-dependent rules only apply from here on.
MANDATE_START = date(2027, 1, 1)


def set_vat_group(trns: set[str]) -> None:
    """Set the VAT group member TRNs for R-025 exclusion checks."""
    global _VAT_GROUP_TRNS
    _VAT_GROUP_TRNS = set(trns)


def set_reference_date(value: date | None) -> None:
    """Pin the "today" used by time-dependent rules (tests, historical replays)."""
    global _reference_date
    _reference_date = value


def _reference_today() -> date:
    return _reference_date or date.today()


EMIRATE_CODES = {"AUH", "DXB", "SHJ", "AJM", "UAQ", "FUJ", "RAK"}
TRN_PLACEHOLDERS = {
    "000000000000000",
    "123456789012345",
    "012345678901234",
}

PLACEHOLDER_TINS = {
    "1234567890",
    "0123456789",
}


@dataclass
class RuleViolation:
    rule_id: str
    citation: str
    field: str
    message: str
    severity: str = "error"


def rule_line_sum(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-001 / BR-CO-10 (tolerance 0.02 for line-level rounding)."""
    expected = sum((item.line_total for item in inv.line_items), Decimal("0"))
    if abs(inv.line_extension_amount - expected) > Decimal("0.02"):
        return [
            RuleViolation(
                "R-001",
                "Peppol BR-CO-10 (BT-106)",
                "line_extension_amount",
                f"line_extension_amount {inv.line_extension_amount} != sum of line totals {expected}",
            )
        ]
    return []


def rule_tax_exclusive_sum(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-002 / BR-CO-13 (tolerance 0.02 for VAT-category rounding)."""
    expected = sum((c.taxable_amount or Decimal("0") for c in inv.tax_categories), Decimal("0"))
    if abs(inv.tax_exclusive_amount - expected) > Decimal("0.02"):
        return [
            RuleViolation(
                "R-002",
                "Peppol BR-CO-13 (BT-109)",
                "tax_exclusive_amount",
                f"tax_exclusive_amount {inv.tax_exclusive_amount} != sum of taxable amounts {expected}",
            )
        ]
    return []


def rule_payable_amount(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-003 / BR-CO-16: payable = tax inclusive - prepaid + payable rounding."""
    prepaid = inv.prepaid_amount or Decimal("0")
    rounding = inv.payable_rounding_amount or Decimal("0")
    expected = inv.tax_inclusive_amount - prepaid + rounding
    if inv.payable_amount != expected:
        return [
            RuleViolation(
                "R-003",
                "Peppol BR-CO-16 (BT-115)",
                "payable_amount",
                f"payable_amount {inv.payable_amount} != tax_inclusive - prepaid + rounding "
                f"{expected}",
            )
        ]
    return []


def rule_total_tax(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-004 / BR-CO-15: tax total = amount with tax - amount without tax."""
    total_tax = sum((c.tax_amount or Decimal("0") for c in inv.tax_categories), Decimal("0"))
    expected = inv.tax_inclusive_amount - inv.tax_exclusive_amount
    tolerance = Decimal("0.01")
    if abs(total_tax - expected) > tolerance:
        return [
            RuleViolation(
                "R-004",
                "Peppol BR-CO-15 (BT-110)",
                "tax_categories",
                f"sum of tax_amounts {total_tax} != tax_inclusive - tax_exclusive {expected}",
            )
        ]
    return []


def rule_vat_rate_consistency(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-005 / UAE VAT Law FDL 8/2017 Art.3 + BR-S-05."""
    expected_rates = {"S": Decimal("5.00"), "Z": Decimal("0.00")}
    out: list[RuleViolation] = []
    for cat in inv.tax_categories:
        if cat.code not in expected_rates:
            continue
        if cat.percent is not None and cat.percent != expected_rates[cat.code]:
            out.append(
                RuleViolation(
                    "R-005",
                    "UAE VAT Law FDL 8/2017 Art.3 + Peppol BR-S-05 (BT-152)",
                    f"tax_category[{cat.code}].percent",
                    f"VAT category {cat.code} requires {expected_rates[cat.code]}, found {cat.percent}",
                )
            )
    return out


def rule_invoice_id_nonempty(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-006 / BR-02."""
    if not inv.invoice_id.strip():
        return [RuleViolation("R-006", "Peppol BR-02 (BT-1)", "invoice_id", "invoice_id is empty")]
    return []


@cache
def document_type_codes() -> frozenset[str]:
    """Document name codes from the official PINT AE 1.0.4 code lists (UNCL1001)."""
    codes: set[str] = set()
    for path in _DOCUMENT_CODE_LISTS:
        if not path.exists():
            continue
        root = etree.fromstring(path.read_bytes())
        for row in root.iter(f"{_GENERICODE_NS}Row"):
            for column in row.findall(f"{_GENERICODE_NS}Value"):
                if column.get("ColumnRef") != "id":
                    continue
                simple = column.find(f"{_GENERICODE_NS}SimpleValue")
                if simple is not None and simple.text:
                    codes.add(simple.text.strip())
    return frozenset(codes) if codes else frozenset(ALLOWED_TYPE_CODES)


def rule_valid_type_code(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-007 / BR-04 UNCL1001 (official PINT AE 1.0.4 code list)."""
    if inv.invoice_type_code not in document_type_codes():
        return [
            RuleViolation(
                "R-007",
                "Peppol BR-04 (BT-3) UNCL1001",
                "invoice_type_code",
                f"invoice_type_code '{inv.invoice_type_code}' not in allowed set",
            )
        ]
    return []


def rule_valid_currency(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-008 / BR-05 ISO 4217."""
    if inv.document_currency_code not in ALLOWED_CURRENCIES:
        return [
            RuleViolation(
                "R-008",
                "Peppol BR-05 (BT-5) ISO 4217",
                "document_currency_code",
                f"document_currency_code '{inv.document_currency_code}' not in allowed set",
            )
        ]
    return []


def rule_issue_date_not_far_future(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-009 / BR-03."""
    if inv.issue_date > date.today() + timedelta(days=30):
        return [
            RuleViolation(
                "R-009",
                "Peppol BR-03 (BT-2)",
                "issue_date",
                f"issue_date {inv.issue_date} more than 30 days in future",
            )
        ]
    return []


def rule_supplier_name_nonempty(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-010 / BR-06."""
    if not inv.supplier.name.strip():
        return [
            RuleViolation("R-010", "Peppol BR-06 (BT-27)", "supplier.name", "supplier.name empty")
        ]
    return []


def rule_customer_name_nonempty(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-011 / BR-07."""
    if not inv.customer.name.strip():
        return [
            RuleViolation("R-011", "Peppol BR-07 (BT-44)", "customer.name", "customer.name empty")
        ]
    return []


def rule_distinct_parties(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-012 / BR-08."""
    if inv.supplier.trn and inv.customer.trn and inv.supplier.trn == inv.customer.trn:
        return [
            RuleViolation(
                "R-012",
                "Peppol BR-08 (BT-31/BT-48)",
                "supplier.trn",
                f"supplier.trn == customer.trn ({inv.supplier.trn})",
            )
        ]
    return []


def rule_positive_quantity(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-013 / BR-21."""
    return [
        RuleViolation(
            "R-013",
            "Peppol BR-21 (BT-129)",
            f"line[{i.line_id}].quantity",
            f"quantity {i.quantity} <= 0",
        )
        for i in inv.line_items
        if i.quantity <= 0
    ]


def rule_line_description_nonempty(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-014 / BR-25."""
    return [
        RuleViolation(
            "R-014",
            "Peppol BR-25 (BT-153)",
            f"line[{i.line_id}].description",
            f"line {i.line_id} description empty",
        )
        for i in inv.line_items
        if not i.description.strip()
    ]


def rule_unique_line_ids(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-015 / BR-21."""
    seen: set[str] = set()
    dups: list[str] = []
    for i in inv.line_items:
        if i.line_id in seen:
            dups.append(i.line_id)
        seen.add(i.line_id)
    if dups:
        return [
            RuleViolation(
                "R-015", "Peppol BR-21 (BT-126)", "line_items", f"duplicate line IDs: {dups}"
            )
        ]
    return []


def rule_line_arithmetic(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-016 / BR-27 + IBR-147: line net = qty x net price + charges - allowances."""
    tol = Decimal("0.02")
    out: list[RuleViolation] = []
    for i in inv.line_items:
        base = i.base_quantity or Decimal("1")
        net = i.quantity * (i.unit_price / base)
        expected = (net - i.allowance_total + i.charge_total).quantize(Decimal("0.01"))
        if abs(i.line_total - expected) > tol:
            out.append(
                RuleViolation(
                    "R-016",
                    "Peppol BR-27 (BT-131)",
                    f"line[{i.line_id}].line_total",
                    f"line {i.line_id}: {i.line_total} != {expected}",
                )
            )
    return out


def rule_payable_positive(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-017 / BR-CO-15: invoices must have positive payable."""
    if inv.invoice_type_code == "380" and inv.payable_amount <= 0:
        return [
            RuleViolation(
                "R-017",
                "Peppol BR-CO-15 (BT-115)",
                "payable_amount",
                f"invoice payable_amount must be > 0, found {inv.payable_amount}",
            )
        ]
    return []


def rule_taxable_matches_tax(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-018 / BR-CO-17."""
    tol = Decimal("0.02")
    out: list[RuleViolation] = []
    for c in inv.tax_categories:
        if c.code not in {"S", "Z"}:
            # Reverse-charge (AE), exempt (E), not-subject (O) and standard
            # additional VAT (N) have their own zero/none rules in the official
            # layer; applying the S/Z formula to them would be wrong.
            continue
        if c.taxable_amount is None or c.tax_amount is None or c.percent is None:
            continue
        expected = (c.taxable_amount * c.percent / Decimal("100")).quantize(Decimal("0.01"))
        if abs(c.tax_amount - expected) > tol:
            out.append(
                RuleViolation(
                    "R-018",
                    "Peppol BR-CO-17 (BT-110/BT-152)",
                    f"tax_category[{c.code}].tax_amount",
                    f"category {c.code}: tax_amount {c.tax_amount} != taxable*percent/100 {expected}",
                )
            )
    return out


def rule_no_duplicate_tax_codes(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-019 / BR-CO: tax category codes must be unique."""
    codes = [c.code for c in inv.tax_categories]
    dups = sorted({c for c in codes if codes.count(c) > 1})
    if dups:
        return [
            RuleViolation(
                "R-019",
                "Peppol BR-CO (unique VAT category)",
                "tax_categories",
                f"duplicate tax category codes: {dups}",
            )
        ]
    return []


def rule_customization_id(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-020 / PINT AE BIS 1.0.4 BT-24."""
    expected = ("urn:peppol:pint:billing-1@ae-1", "urn:peppol:pint:selfbilling-1@ae-1")
    if inv.customization_id not in expected:
        return [
            RuleViolation(
                "R-020",
                "PINT AE BIS 1.0.4 BT-24 (billing or self-billing)",
                "customization_id",
                f"customization_id '{inv.customization_id}' is not a PINT AE identifier",
            )
        ]
    return []


def rule_emirate_code(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-021 / PINT AE BIS 1.0.4: emirate code must be UAE code if present."""
    sub = inv.supplier.country_subentity
    if sub is None:
        return []
    if sub not in EMIRATE_CODES:
        return [
            RuleViolation(
                "R-021",
                "PINT AE BIS 1.0.4 (emirate code)",
                "supplier.country_subentity",
                f"emirate code '{sub}' not in {sorted(EMIRATE_CODES)}",
            )
        ]
    return []


def rule_buyer_trn_quality(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-022 / data quality: buyer identifier, TRN and electronic address.

    The official PINT AE 1.0.4 samples carry the electronic address as
    ``scheme:value`` where the value may be a 10-digit TIN, a 15-digit TRN or a
    foreign identifier under another EAS scheme. Only the presence of a scheme
    and obvious placeholders are checked here; the official layer validates the
    scheme against the EAS code list.
    """
    trn = inv.customer.trn
    pid = inv.customer.peppol_id
    ttc = inv.transaction_type_code or ""
    is_export = len(ttc) == 8 and ttc[7] == "1"
    out: list[RuleViolation] = []

    if trn is None and pid is None and not is_export:
        out.append(
            RuleViolation(
                "R-022",
                "PINT AE data quality (BT-48, IBR-135-AE)",
                "customer.trn",
                "buyer TRN is missing and no buyer identifier is present",
            )
        )

    if trn is not None:
        if len(set(trn)) == 1:
            out.append(
                RuleViolation(
                    "R-022",
                    "PINT AE data quality (BT-48)",
                    "customer.trn",
                    f"buyer TRN {trn} is all-same-digit",
                )
            )
        elif trn in TRN_PLACEHOLDERS:
            out.append(
                RuleViolation(
                    "R-022",
                    "PINT AE data quality (BT-48)",
                    "customer.trn",
                    f"buyer TRN {trn} is a known placeholder",
                )
            )

    if pid is not None:
        scheme, _, value = pid.partition(":")
        if not scheme or not value:
            out.append(
                RuleViolation(
                    "R-022",
                    "Peppol electronic address (IBT-049, IBR-063)",
                    "customer.peppol_id",
                    f"buyer electronic address {pid} has no scheme identifier",
                )
            )
        elif len(set(value)) == 1:
            out.append(
                RuleViolation(
                    "R-022",
                    "Peppol electronic address (IBT-049)",
                    "customer.peppol_id",
                    f"buyer electronic address value {value} is all-same-character",
                )
            )
        elif len(value) == 10 and value in PLACEHOLDER_TINS:
            out.append(
                RuleViolation(
                    "R-022",
                    "Peppol electronic address (IBT-049)",
                    "customer.peppol_id",
                    f"buyer electronic address value {value} is a known placeholder TIN",
                )
            )
    return out


def _business_days_between(start: date, end: date) -> int:
    """Count business days (Mon-Fri) strictly between start and end."""
    if end <= start:
        return 0
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def rule_transmission_window(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-024 / MD 197 of 2026, Article 6(5): 14-business-day transmission.

    The law requires the issuer to issue **and transmit** the invoice through the
    system within 14 business days from the *date of the business transaction*.
    Transmission is not observable in the invoice itself, so this rule uses the
    issue date as the transaction date (documented proxy): if an invoice is
    already more than 14 business days old when inspected, the transmission
    window has almost certainly been missed.

    Only applies from the mandate start (1 Jan 2027; later phases for smaller
    businesses and government entities). Business days are Mon-Fri in line with
    the UAE working week; public holidays are not yet modelled, so the rule can
    under-count around holiday periods.
    """
    if inv.issue_date < MANDATE_START:
        return []
    biz_days = _business_days_between(inv.issue_date, _reference_today())
    if biz_days > 14:
        return [
            RuleViolation(
                "R-024",
                "MD 197 of 2026, Art. 6(5) - 14 business days from the date of the business transaction",
                "issue_date",
                f"invoice issued {biz_days} business days before inspection, beyond the "
                f"14-business-day transmission window",
                severity="warning",
            )
        ]
    return []


def rule_vat_group_exclusion(inv: PintAeInvoice) -> list[RuleViolation]:
    """R-025 / MD 197 of 2026, Art. 4(1)(f): intra-tax-group supplies excluded.

    Transactions between members of the same tax group are excluded from the
    system for 24 months from 1 January 2027 (i.e. until 31 December 2028).
    """
    if not _VAT_GROUP_TRNS:
        return []
    if inv.supplier.trn in _VAT_GROUP_TRNS and inv.customer.trn in _VAT_GROUP_TRNS:
        return [
            RuleViolation(
                "R-025",
                "MD 197 of 2026, Art. 4(1)(f) - intra-tax-group exclusion (1 Jan 2027 to 31 Dec 2028)",
                "supplier.trn/customer.trn",
                "intra-tax-group supply - excluded from e-invoicing until 31 Dec 2028",
                severity="warning",
            )
        ]
    return []


_RULES = [
    rule_line_sum,
    rule_tax_exclusive_sum,
    rule_payable_amount,
    rule_total_tax,
    rule_vat_rate_consistency,
    rule_invoice_id_nonempty,
    rule_valid_type_code,
    rule_valid_currency,
    rule_issue_date_not_far_future,
    rule_supplier_name_nonempty,
    rule_customer_name_nonempty,
    rule_distinct_parties,
    rule_positive_quantity,
    rule_line_description_nonempty,
    rule_unique_line_ids,
    rule_line_arithmetic,
    rule_payable_positive,
    rule_taxable_matches_tax,
    rule_no_duplicate_tax_codes,
    rule_customization_id,
    rule_emirate_code,
    rule_buyer_trn_quality,
    rule_transmission_window,
    rule_vat_group_exclusion,
]


def validate(
    inv: PintAeInvoice,
    xml_source: str | bytes | None = None,
    include_peppol_bis3: bool = False,
) -> list[RuleViolation]:
    """Run all registered rules.

    If ``xml_source`` is provided, the Schematron conformance layers are run too:
    the official PINT AE 1.0.4 set by default, plus the legacy Peppol BIS 3.0
    pair when ``include_peppol_bis3`` is True.
    """
    out: list[RuleViolation] = []
    for rule in _RULES:
        out.extend(rule(inv))
    if xml_source is not None:
        from pint_ae.schematron.validator import validate_schematron

        for sv in validate_schematron(xml_source, include_peppol_bis3=include_peppol_bis3):
            out.append(
                RuleViolation(
                    rule_id=sv.rule_id,
                    citation=sv.citation,
                    field=sv.location or "schematron",
                    message=sv.message,
                    severity=sv.severity,
                )
            )
        from pint_ae.xsd_validator import validate_xsd

        out.extend(validate_xsd(xml_source))
    return out
