"""Generate the deterministic synthetic client corpus used to prove accuracy.

The corpus is a *portfolio* of 100 PINT AE documents that look like one mid-size
UAE business's quarter: several sellers (group entities), a dozen corporate
buyers across the seven emirates, standard / zero-rated / exempt / reverse-charge
supplies, document-level discounts and surcharges, and credit notes. A known
share of the documents carries one injected defect, so the expected finding for
every file is written into ``manifest.json`` and asserted by
``packages/core/tests/test_corpus.py``.

Two properties matter and both are tested:

1. **Deterministic** - the same command produces byte-identical documents, so a
   reviewed expectation stays valid and a regression is visible in the diff.
2. **Oracle-checked** - every document is also validated directly against the
   publisher's precompiled XSLT, so the corpus proves agreement with the official
   artefact rather than agreement with our own code.

Nothing here is real client data. Names, TRNs and identifiers are invented and
internally consistent (TRN = 10-digit TIN + "01" + "003", trade licence 15
digits), which is what the coherence rules (R-022, IBR-149-AE) expect.

Why it ships in the toolkit: a prospect who cannot hand over real invoices can
still run the tool end to end on a realistic portfolio::

    pint-ae corpus --out demo/
    pint-ae diagnose demo/documents --json demo/results.json

Documents are dated in Oct-Nov 2026, before the 1 January 2027 mandate start, so
the date-dependent rules (R-024 transmission window, R-009 not-in-the-future)
stay silent and the manifest does not rot with the calendar.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SEED = "pint-ae-client-corpus-v1"
AS_OF = date(2026, 11, 24)
MANDATE_SAFE = AS_OF - timedelta(days=40)  # first date the corpus may use

VAT_RATE = Decimal("5")
CENT = Decimal("0.01")

#: Local rules whose defect is also covered by an official assertion; the official
#: finding wins and the local one is recorded as suppressed (results.OVERLAP_MAP).
STANDARD_UNIT = "H87"


def _h(*parts: object) -> int:
    """Stable pseudo-random integer from the seed and the parts.

    A hash, not ``random``: the corpus must not change when Python's PRNG or its
    seeding does, because the manifest records reviewed expectations.
    """
    raw = "|".join(str(part) for part in (SEED, *parts)).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


@dataclass(frozen=True)
class Seller:
    key: str
    name: str
    trade_name: str
    tin: str
    licence: str
    emirate: str
    city: str
    street: str
    series: str

    @property
    def trn(self) -> str:
        return f"{self.tin}01003"


@dataclass(frozen=True)
class Buyer:
    key: str
    name: str
    tin: str
    licence: str
    emirate: str
    city: str

    @property
    def trn(self) -> str:
        return f"{self.tin}01003"


@dataclass(frozen=True)
class Item:
    description: str
    name: str
    price: Decimal  # multiple of 20 so a 5% tax is exact to the fils
    unit: str = STANDARD_UNIT


SELLERS: tuple[Seller, ...] = (
    Seller(
        "no",
        "Al Noor Trading LLC",
        "Al Noor",
        "1002345678",
        "112345678900003",
        "DXB",
        "Dubai",
        "Sheikh Zayed Road",
        "AN",
    ),
    Seller(
        "sm",
        "Sahara Metals Industries FZE",
        "Sahara Metals",
        "1003456789",
        "112345679000001",
        "SHJ",
        "Sharjah",
        "Hamriyah Free Zone",
        "SM",
    ),
    Seller(
        "gc",
        "Gulf Coast Contracting LLC",
        "Gulf Coast",
        "1004567890",
        "112345680000003",
        "AUH",
        "Abu Dhabi",
        "Corniche Road",
        "GC",
    ),
    Seller(
        "dh",
        "Desert Harvest Foods LLC",
        "Desert Harvest",
        "1005678901",
        "112345681000001",
        "AJM",
        "Ajman",
        "Sheikh Rashid Bin Humaid St",
        "DH",
    ),
    Seller(
        "fj",
        "Fujairah Logistics FZE",
        "Fujairah Logistics",
        "1006789012",
        "112345682000003",
        "FUJ",
        "Fujairah",
        "Port Road",
        "FL",
    ),
)

BUYERS: tuple[Buyer, ...] = (
    Buyer("mar", "Marina Bay Hospitality LLC", "1101234567", "112345690000001", "DXB", "Dubai"),
    Buyer("ema", "Emirates Star Retail PJSC", "1102345678", "112345691000003", "DXB", "Dubai"),
    Buyer(
        "kha", "Khalidiya Medical Centre LLC", "1103456789", "112345692000001", "AUH", "Abu Dhabi"
    ),
    Buyer("jba", "Jebel Ali Industrial FZE", "1104567890", "112345693000003", "DXB", "Dubai"),
    Buyer("shj", "Sharjah Educational Trust", "1105678901", "112345694000001", "SHJ", "Sharjah"),
    Buyer(
        "rak", "Ras Al Khaimah Cement Co", "1106789012", "112345695000003", "RAK", "Ras Al Khaimah"
    ),
    Buyer(
        "uaq",
        "Umm Al Quwain Fisheries LLC",
        "1107890123",
        "112345696000001",
        "UAQ",
        "Umm Al Quwain",
    ),
    Buyer("ajm", "Ajman Auto Spares LLC", "1108901234", "112345697000003", "AJM", "Ajman"),
    Buyer("fuj", "Fujairah Rock Works LLC", "1109012345", "112345698000001", "FUJ", "Fujairah"),
    Buyer(
        "gov",
        "Federal Water Resources Authority",
        "1100123456",
        "112345699000003",
        "AUH",
        "Abu Dhabi",
    ),
)

ITEMS: tuple[Item, ...] = (
    Item("Structural steel sections, grade S355", "Steel sections", Decimal("1250")),
    Item("Portland cement 50 kg bags", "Cement bags", Decimal("320"), "NAR"),
    Item("Cold-chain transport, Dubai to Abu Dhabi", "Cold-chain transport", Decimal("2400"), "K6"),
    Item("Facility maintenance, monthly retainer", "Maintenance retainer", Decimal("6000"), "MON"),
    Item("Office furniture, workstation", "Workstation", Decimal("1840"), "EA"),
    Item("Bottled water 500 ml, carton of 12", "Water carton", Decimal("60"), "CTN"),
    Item("IT support, engineer day", "Engineer day", Decimal("2800"), "DAY"),
    Item("Marine paints, 20 litre drum", "Marine paint", Decimal("980"), "LTR"),
    Item("Warehouse racking, pallet bay", "Pallet bay", Decimal("1520"), "EA"),
    Item("Accounting software, annual licence", "Software licence", Decimal("9600"), "ANN"),
    Item("Safety equipment, helmet", "Safety helmet", Decimal("160"), "EA"),
    Item("Catering services, per head", "Catering per head", Decimal("180"), "C62"),
)

VAT_LABEL = {"S": "Standard rated", "Z": "Zero rated", "E": "Exempt", "AE": "Reverse charge"}

#: Exempt supplies carry the exemption reason code on the line VAT category and
#: use the exempt invoice type code (480), never 380 (IBR-151-AE).
EXEMPT_TYPE_CODE = "480"
EXEMPT_REASON = "VATEX-AE-EDU"


def amount(value: Decimal) -> str:
    """Render a decimal the way the samples do: no trailing zero fils."""
    quant = value.quantize(CENT)
    if quant == quant.to_integral_value():
        return str(int(quant))
    return f"{quant:.2f}"


@dataclass
class Line:
    item: Item
    qty: int

    @property
    def net(self) -> Decimal:
        return self.item.price * self.qty


@dataclass
class Document:
    """One corpus document before rendering."""

    index: int
    kind: str  # "invoice" | "credit_note"
    seller: Seller
    buyer: Buyer
    lines: list[Line]
    vat: str
    issue: date
    due: date | None
    allowance: Decimal = Decimal("0")
    charge: Decimal = Decimal("0")
    type_code: str = "380"
    reference: str | None = None
    defects: tuple[str, ...] = field(default_factory=tuple)
    rate: Decimal | None = None  # overrides the category's normal rate

    # -- money ------------------------------------------------------------
    @property
    def percent(self) -> Decimal:
        if self.rate is not None:
            return self.rate
        return VAT_RATE if self.vat in {"S", "AE"} else Decimal("0")

    @property
    def line_net(self) -> Decimal:
        return sum((line.net for line in self.lines), Decimal("0"))

    @property
    def taxable(self) -> Decimal:
        return self.line_net - self.allowance + self.charge

    def tax_on(self, base: Decimal) -> Decimal:
        if self.vat not in {"S"}:
            return Decimal("0")
        return (base * self.percent / 100).quantize(CENT)

    @property
    def tax_total(self) -> Decimal:
        return self.tax_on(self.taxable)

    @property
    def tax_inclusive(self) -> Decimal:
        return self.taxable + self.tax_total

    @property
    def document_id(self) -> str:
        prefix = "CN" if self.kind == "credit_note" else "INV"
        return f"{self.seller.series}-{self.issue.year}-{prefix}-{self.index:04d}"

    @property
    def uuid(self) -> str:
        digest = hashlib.sha256(f"{SEED}:{self.index}".encode()).hexdigest()
        return f"{digest[:8]}-{digest[8:12]}-4{digest[13:16]}-a{digest[17:20]}-{digest[20:32]}"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _percent_xml(vat: str, percent: Decimal) -> str:
    if vat == "E":  # exempt carries no rate in the official samples
        return ""
    return f"<cbc:Percent>{amount(percent)}</cbc:Percent>"


def _tax_category(
    vat: str, percent: Decimal, tag: str = "TaxCategory", exemption: str | None = None
) -> str:
    reason = (
        f"\t\t\t\t\t<cbc:TaxExemptionReasonCode>{exemption}</cbc:TaxExemptionReasonCode>\n"
        if exemption
        else ""
    )
    return f"""\t\t\t\t<cac:{tag}>
\t\t\t\t\t<cbc:ID>{vat}</cbc:ID>
\t\t\t\t\t{_percent_xml(vat, percent)}
{reason}\t\t\t\t\t<cac:TaxScheme>
\t\t\t\t\t\t<cbc:ID>VAT</cbc:ID>
\t\t\t\t\t</cac:TaxScheme>
\t\t\t\t</cac:{tag}>"""


def render(doc: Document) -> str:
    """Render one document as PINT AE UBL XML."""
    defects = doc.defects
    seller, buyer = doc.seller, doc.buyer
    vat, percent = doc.vat, doc.percent
    is_cn = doc.kind == "credit_note"

    root = "CreditNote" if is_cn else "Invoice"
    line_tag = "CreditNoteLine" if is_cn else "InvoiceLine"
    qty_tag = "CreditedQuantity" if is_cn else "InvoicedQuantity"
    type_tag = "CreditNoteTypeCode" if is_cn else "InvoiceTypeCode"

    line_net = doc.line_net
    taxable = doc.taxable
    tax_total = doc.tax_total
    tax_inclusive = doc.tax_inclusive

    # A defect re-renders one declared value so it no longer matches the lines,
    # while the rest of the document stays internally consistent. That keeps each
    # defect isolated to the assertions it actually breaks.
    declared_line_net = line_net + Decimal("200") if "line_sum" in defects else line_net
    declared_taxable = taxable
    declared_tax = tax_total + Decimal("50") if "tax_total" in defects else tax_total
    declared_inclusive = tax_inclusive
    declared_payable = tax_inclusive + (Decimal("200") if "payable" in defects else Decimal("0"))

    invoice_type = "999" if "type_code" in defects else doc.type_code

    seller_name = "" if "seller_name" in defects else seller.name
    seller_street_xml = (
        f"\t\t\t\t<cbc:StreetName>{seller.street}</cbc:StreetName>\n"
        if "seller_address" not in defects
        else ""
    )
    buyer_address_xml = (
        f"""\t\t\t<cac:PostalAddress>
\t\t\t\t<cbc:StreetName>Plot {doc.index % 97 + 3}, Industrial Area</cbc:StreetName>
\t\t\t\t<cbc:CityName>{buyer.city}</cbc:CityName>
\t\t\t\t<cbc:CountrySubentity>{buyer.emirate}</cbc:CountrySubentity>
\t\t\t\t<cac:Country>
\t\t\t\t\t<cbc:IdentificationCode>AE</cbc:IdentificationCode>
\t\t\t\t</cac:Country>
\t\t\t</cac:PostalAddress>"""
        if "buyer_address" not in defects
        else ""
    )
    uuid_xml = "" if "uuid" in defects else f"\t<cbc:UUID>{doc.uuid}</cbc:UUID>\n"
    due_xml = (
        f"\t<cbc:DueDate>{doc.due.isoformat()}</cbc:DueDate>\n"
        if doc.due and "due_date" not in defects
        else ""
    )
    payment_xml = (
        ""
        if "payment_means" in defects
        else """\t<cac:PaymentMeans>
\t\t<cbc:PaymentMeansCode name="Credit transfer">30</cbc:PaymentMeansCode>
\t\t<cac:PayeeFinancialAccount>
\t\t\t<cbc:ID schemeID="IBAN">AE070331234567890123456</cbc:ID>
\t\t\t<cbc:Name>current account</cbc:Name>
\t\t\t<cac:FinancialInstitutionBranch>
\t\t\t\t<cbc:ID>236000</cbc:ID>
\t\t\t</cac:FinancialInstitutionBranch>
\t\t</cac:PayeeFinancialAccount>
\t</cac:PaymentMeans>
"""
    )
    reference_xml = (
        f"""\t<cac:DiscrepancyResponse>
\t\t<cbc:ResponseCode>DL8.61.1.E</cbc:ResponseCode>
\t</cac:DiscrepancyResponse>
\t<cac:BillingReference>
\t\t<cac:InvoiceDocumentReference>
\t\t\t<cbc:ID>{doc.reference}</cbc:ID>
\t\t\t<cbc:IssueDate>{(doc.issue - timedelta(days=14)).isoformat()}</cbc:IssueDate>
\t\t</cac:InvoiceDocumentReference>
\t</cac:BillingReference>
"""
        if doc.reference
        else ""
    )

    allowance_xml = ""
    charge_xml = ""
    allowance_total = ""
    charge_total = ""
    if doc.allowance:
        allowance_xml = f"""\t<cac:AllowanceCharge>
\t\t<cbc:ChargeIndicator>false</cbc:ChargeIndicator>
\t\t<cbc:AllowanceChargeReasonCode>95</cbc:AllowanceChargeReasonCode>
\t\t<cbc:AllowanceChargeReason>Volume discount</cbc:AllowanceChargeReason>
\t\t<cbc:Amount currencyID="AED">{amount(doc.allowance)}</cbc:Amount>
{_tax_category(vat, percent)}
\t</cac:AllowanceCharge>
"""
        allowance_total = f'\t\t<cbc:AllowanceTotalAmount currencyID="AED">{amount(doc.allowance)}</cbc:AllowanceTotalAmount>\n'
    if doc.charge:
        charge_xml = f"""\t<cac:AllowanceCharge>
\t\t<cbc:ChargeIndicator>true</cbc:ChargeIndicator>
\t\t<cbc:AllowanceChargeReasonCode>AAT</cbc:AllowanceChargeReasonCode>
\t\t<cbc:AllowanceChargeReason>Rush delivery</cbc:AllowanceChargeReason>
\t\t<cbc:Amount currencyID="AED">{amount(doc.charge)}</cbc:Amount>
{_tax_category(vat, percent)}
\t</cac:AllowanceCharge>
"""
        charge_total = f'\t\t<cbc:ChargeTotalAmount currencyID="AED">{amount(doc.charge)}</cbc:ChargeTotalAmount>\n'

    lines_xml: list[str] = []
    for number, line in enumerate(doc.lines, start=1):
        item = line.item
        net = line.net
        line_tax = doc.tax_on(net)
        description_xml = (
            ""
            if "item_description" in defects
            else f"\t\t\t\t<cbc:Description>{item.description}</cbc:Description>\n"
        )
        base_quantity_xml = (
            ""
            if "base_quantity" in defects
            else f'<cbc:BaseQuantity unitCode="{item.unit}">1</cbc:BaseQuantity>'
        )
        if "item_price_extension" in defects:
            extension_xml = ""
        elif vat == "E":
            # An exempt line carries no VAT line amount (IBR-163-AE).
            extension_xml = f"""\t\t<cac:ItemPriceExtension>
\t\t\t<cbc:Amount currencyID="AED">{amount(net)}</cbc:Amount>
\t\t</cac:ItemPriceExtension>
"""
        else:
            extension_xml = f"""\t\t<cac:ItemPriceExtension>
\t\t\t<cbc:Amount currencyID="AED">{amount(net + line_tax)}</cbc:Amount>
\t\t\t<cac:TaxTotal>
\t\t\t\t<cbc:TaxAmount currencyID="AED">{amount(line_tax)}</cbc:TaxAmount>
\t\t\t</cac:TaxTotal>
\t\t</cac:ItemPriceExtension>
"""
        exemption = EXEMPT_REASON if vat == "E" else None
        # A reverse-charge line must say what was supplied (BTAE-09) and carry the
        # item standard identifier (IBT-157, scheme 0160).
        reverse_charge_xml = (
            f"""\t\t\t<cac:StandardItemIdentification>
\t\t\t\t<cbc:ID schemeID="0160">{_h(SEED, "gtin", doc.index, number) % 10**12:012d}</cbc:ID>
\t\t\t</cac:StandardItemIdentification>
\t\t\t<cac:CommodityClassification>
\t\t\t\t<cbc:NatureCode>DL8.48.3.1</cbc:NatureCode>
\t\t\t</cac:CommodityClassification>
"""
            if vat == "AE"
            else ""
        )
        lines_xml.append(
            f"""\t<cac:{line_tag}>
\t\t<cbc:ID>{number}</cbc:ID>
\t\t<cbc:{qty_tag} unitCode="{item.unit}">{line.qty}</cbc:{qty_tag}>
\t\t<cbc:LineExtensionAmount currencyID="AED">{amount(net)}</cbc:LineExtensionAmount>
\t\t<cac:Item>
{description_xml}\t\t\t<cbc:Name>{item.name}</cbc:Name>
{reverse_charge_xml}{_tax_category(vat, percent, "ClassifiedTaxCategory", exemption)}
\t\t</cac:Item>
\t\t<cac:Price>
\t\t\t<cbc:PriceAmount currencyID="AED">{amount(item.price)}</cbc:PriceAmount>
\t\t\t{base_quantity_xml}
\t\t\t<cac:AllowanceCharge>
\t\t\t\t<cbc:ChargeIndicator>false</cbc:ChargeIndicator>
\t\t\t\t<cbc:Amount currencyID="AED">0</cbc:Amount>
\t\t\t\t<cbc:BaseAmount currencyID="AED">{amount(item.price)}</cbc:BaseAmount>
\t\t\t</cac:AllowanceCharge>
\t\t</cac:Price>
{extension_xml}\t</cac:{line_tag}>
"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="urn:oasis:names:specification:ubl:schema:xsd:{root}-2"
\txmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
\txmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
\t<cbc:CustomizationID>urn:peppol:pint:billing-1@ae-1</cbc:CustomizationID>
\t<cbc:ProfileID>urn:peppol:bis:billing</cbc:ProfileID>
\t<cbc:ProfileExecutionID>00000000</cbc:ProfileExecutionID>
\t<cbc:ID>{doc.document_id}</cbc:ID>
{uuid_xml}\t<cbc:IssueDate>{doc.issue.isoformat()}</cbc:IssueDate>
{due_xml}\t<cbc:{type_tag}>{invoice_type}</cbc:{type_tag}>
\t<cbc:Note>Tax {"credit note" if is_cn else "invoice"}</cbc:Note>
\t<cbc:DocumentCurrencyCode>AED</cbc:DocumentCurrencyCode>
{reference_xml}\t<cac:AccountingSupplierParty>
\t\t<cac:Party>
\t\t\t<cbc:EndpointID schemeID="0235">{seller.tin}</cbc:EndpointID>
\t\t\t<cac:PartyName>
\t\t\t\t<cbc:Name>{seller.trade_name}</cbc:Name>
\t\t\t</cac:PartyName>
\t\t\t<cac:PostalAddress>
{seller_street_xml}\t\t\t\t<cbc:CityName>{seller.city}</cbc:CityName>
\t\t\t\t<cbc:CountrySubentity>{seller.emirate}</cbc:CountrySubentity>
\t\t\t\t<cac:Country>
\t\t\t\t\t<cbc:IdentificationCode>AE</cbc:IdentificationCode>
\t\t\t\t</cac:Country>
\t\t\t</cac:PostalAddress>
\t\t\t<cac:PartyTaxScheme>
\t\t\t\t<cbc:CompanyID>{seller.trn}</cbc:CompanyID>
\t\t\t\t<cac:TaxScheme>
\t\t\t\t\t<cbc:ID>VAT</cbc:ID>
\t\t\t\t</cac:TaxScheme>
\t\t\t</cac:PartyTaxScheme>
\t\t\t<cac:PartyLegalEntity>
\t\t\t\t<cbc:RegistrationName>{seller_name}</cbc:RegistrationName>
\t\t\t\t<cbc:CompanyID schemeAgencyID="TL" schemeAgencyName="Trade License issuing Authority">{seller.licence}</cbc:CompanyID>
\t\t\t</cac:PartyLegalEntity>
\t\t</cac:Party>
\t</cac:AccountingSupplierParty>
\t<cac:AccountingCustomerParty>
\t\t<cac:Party>
\t\t\t<cbc:EndpointID schemeID="0235">{buyer.tin}</cbc:EndpointID>
\t\t\t<cac:PartyName>
\t\t\t\t<cbc:Name>{buyer.name}</cbc:Name>
\t\t\t</cac:PartyName>
{buyer_address_xml}
\t\t\t<cac:PartyTaxScheme>
\t\t\t\t<cbc:CompanyID>{buyer.trn}</cbc:CompanyID>
\t\t\t\t<cac:TaxScheme>
\t\t\t\t\t<cbc:ID>VAT</cbc:ID>
\t\t\t\t</cac:TaxScheme>
\t\t\t</cac:PartyTaxScheme>
\t\t\t<cac:PartyLegalEntity>
\t\t\t\t<cbc:RegistrationName>{buyer.name}</cbc:RegistrationName>
\t\t\t\t<cbc:CompanyID schemeAgencyID="TL" schemeAgencyName="Trade License issuing Authority">{buyer.licence}</cbc:CompanyID>
\t\t\t</cac:PartyLegalEntity>
\t\t</cac:Party>
\t</cac:AccountingCustomerParty>
{payment_xml}\t<cac:PaymentTerms>
\t\t<cbc:Note>Due within {30 if doc.due else 15} days</cbc:Note>
\t</cac:PaymentTerms>
{allowance_xml}{charge_xml}\t<cac:TaxTotal>
\t\t<cbc:TaxAmount currencyID="AED">{amount(declared_tax)}</cbc:TaxAmount>
\t\t<cbc:TaxIncludedIndicator>false</cbc:TaxIncludedIndicator>
\t\t<cac:TaxSubtotal>
\t\t\t<cbc:TaxableAmount currencyID="AED">{amount(declared_taxable)}</cbc:TaxableAmount>
\t\t\t<cbc:TaxAmount currencyID="AED">{amount(declared_tax)}</cbc:TaxAmount>
{_tax_category(vat, percent)}
\t\t</cac:TaxSubtotal>
\t</cac:TaxTotal>
\t<cac:LegalMonetaryTotal>
\t\t<cbc:LineExtensionAmount currencyID="AED">{amount(declared_line_net)}</cbc:LineExtensionAmount>
\t\t<cbc:TaxExclusiveAmount currencyID="AED">{amount(declared_taxable)}</cbc:TaxExclusiveAmount>
\t\t<cbc:TaxInclusiveAmount currencyID="AED">{amount(declared_inclusive)}</cbc:TaxInclusiveAmount>
{allowance_total}{charge_total}\t\t<cbc:PayableAmount currencyID="AED">{amount(declared_payable)}</cbc:PayableAmount>
\t</cac:LegalMonetaryTotal>
{"".join(lines_xml)}</{root}>
"""


# ---------------------------------------------------------------------------
# The portfolio
# ---------------------------------------------------------------------------

#: (profile, count, vat, kind, allowance %, charge %)
PROFILES: tuple[tuple[str, int, str, str, Decimal, Decimal], ...] = (
    ("standard", 40, "S", "invoice", Decimal("0"), Decimal("0")),
    ("multi_line", 10, "S", "invoice", Decimal("0"), Decimal("0")),
    ("discount", 10, "S", "invoice", Decimal("10"), Decimal("0")),
    ("surcharge", 8, "S", "invoice", Decimal("0"), Decimal("5")),
    ("zero_rated", 10, "Z", "invoice", Decimal("0"), Decimal("0")),
    ("exempt", 8, "E", "invoice", Decimal("0"), Decimal("0")),
    ("reverse_charge", 6, "AE", "invoice", Decimal("0"), Decimal("0")),
    ("credit_note", 8, "S", "credit_note", Decimal("0"), Decimal("0")),
)

#: Defect catalogue. Each entry: code -> (human description, expected finding ids).
#:
#: One injected defect often breaks more than one assertion, and that is the
#: honest expectation: a line total that no longer adds up breaks both the "sum of
#: lines" rule and the "amount without tax" rule, a missing line amount breaks both
#: the jurisdiction "line amount payable" rule and its invoice-level twin. These
#: sets were reviewed against the publisher's own XSLT: the corpus test asserts
#: that our findings equal exactly this set *and* that the official artefact,
#: applied directly, reports the same rule ids.
DEFECTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "line_sum": (
        "declared line total does not equal the sum of the lines",
        ("ibr-co-10", "ibr-co-13"),
    ),
    "payable": ("payable amount overstated", ("ibr-co-16",)),
    "tax_total": (
        "document VAT total overstated",
        ("ibr-co-15", "aligned-ibrp-s-09"),
    ),
    "bad_rate": ("standard-rated supply carries 7% instead of 5%", ("ibr-190-ae",)),
    "zero_with_rate": (
        "zero-rated supply carries a 5% VAT rate and VAT",
        ("R-005", "R-018", "aligned-ibrp-z-05", "ibr-120-ae"),
    ),
    "uuid": ("unique identifier (BTAE-07) missing", ("ibr-193-ae",)),
    "payment_means": ("payment means missing", ("ibr-191-ae",)),
    "due_date": ("payment due date missing while an amount is payable", ("ibr-127-ae",)),
    "type_code": ("document type code outside UNCL1001", ("ibr-cl-01",)),
    "seller_name": (
        "seller registration name missing",
        ("ibr-006", "ibr-079"),
    ),
    "buyer_address": ("buyer postal address missing", ("ibr-010",)),
    "item_description": ("item description missing", ("ibr-125-ae",)),
    "item_price_extension": (
        "line amount payable (BTAE-10) missing",
        ("ibr-104-ae", "ibr-194-ae"),
    ),
    "base_quantity": (
        "item price base quantity missing",
        ("ibr-126-ae", "ibr-147-ae"),
    ),
    "seller_address": ("seller street name missing", ("ibr-143-ae",)),
}

#: Which documents (1-based) carry a defect. Hand-picked so every defect lands on
#: a document whose profile can express it: a due-date defect needs a payable
#: invoice, a rate defect needs a standard-rated document, a zero-rate defect
#: needs a zero-rated one.
DEFECT_PLAN: dict[int, str] = {
    # standard, single line (1-40)
    2: "line_sum",
    5: "payable",
    9: "tax_total",
    14: "bad_rate",
    17: "uuid",
    21: "payment_means",
    25: "due_date",
    29: "type_code",
    33: "seller_name",
    37: "buyer_address",
    39: "seller_address",
    # multi-line standard (41-50)
    41: "item_description",
    43: "base_quantity",
    45: "item_price_extension",
    46: "uuid",
    # standard with document-level discount (51-60)
    51: "tax_total",
    53: "buyer_address",
    55: "item_price_extension",
    57: "line_sum",
    58: "payment_means",
    60: "seller_address",
    # standard with document-level surcharge (61-68)
    61: "payable",
    62: "seller_name",
    63: "bad_rate",
    66: "item_description",
    68: "uuid",
    # zero rated (69-78)
    70: "zero_with_rate",
    74: "zero_with_rate",
    75: "zero_with_rate",
    77: "buyer_address",
    # exempt (79-86)
    80: "type_code",
    84: "due_date",
    # reverse charge (87-92)
    87: "item_description",
    88: "base_quantity",
    90: "payment_means",
    91: "seller_address",
    # credit notes (93-100)
    94: "seller_name",
    95: "item_price_extension",
    96: "line_sum",
    97: "payable",
}


def _profile_for(index: int) -> tuple[str, str, str, Decimal, Decimal]:
    """Pick the profile for a 1-based document index."""
    cursor = 0
    for name, count, vat, kind, allowance, charge in PROFILES:
        cursor += count
        if index <= cursor:
            return name, vat, kind, allowance, charge
    raise AssertionError(index)


#: The portfolio's shape is defined for 100 documents; larger batches repeat the
#: same mix (profiles and defect plan) with different parties, items and dates, so a
#: benchmark of 500 or 10,000 documents keeps the same 60/40 clean/defective ratio.
CORPUS_CYCLE = 100


def _position(index: int) -> int:
    """1-based position inside the 100-document cycle."""
    return ((index - 1) % CORPUS_CYCLE) + 1


def _build(index: int) -> Document:
    profile, vat, kind, allowance_pct, charge_pct = _profile_for(_position(index))
    seller = SELLERS[_h(SEED, "seller", index) % len(SELLERS)]
    buyer = BUYERS[_h(SEED, "buyer", index) % len(BUYERS)]

    if profile == "multi_line":
        count = 2 + _h(SEED, "lines", index) % 3
    else:
        count = 1
    lines: list[Line] = []
    for slot in range(count):
        item = ITEMS[_h(SEED, "item", index, slot) % len(ITEMS)]
        qty = 1 + _h(SEED, "qty", index, slot) % 12
        lines.append(Line(item, qty))

    # Document-level allowance and charge are percentages of the line total,
    # rounded to a multiple of 20 so the 5% VAT they carry stays exact to the fils
    # and never exceeds the line total (a discount cannot make the invoice negative).
    line_net = sum((line.net for line in lines), Decimal("0"))
    allowance = _round_to_20(line_net * allowance_pct / 100)
    charge = _round_to_20(line_net * charge_pct / 100)

    issue = MANDATE_SAFE + timedelta(days=_h(SEED, "issue", index) % 40)
    due = issue + timedelta(days=30) if kind == "invoice" else None

    defect = DEFECT_PLAN.get(_position(index))
    defects: tuple[str, ...] = ()
    if defect:
        defects = (defect,)

    if kind == "credit_note":
        type_code = "381"
    elif vat == "E":
        type_code = EXEMPT_TYPE_CODE
    else:
        type_code = "380"

    doc = Document(
        index=index,
        kind=kind,
        seller=seller,
        buyer=buyer,
        lines=lines,
        vat=vat,
        issue=issue,
        due=due,
        allowance=allowance,
        charge=charge,
        type_code=type_code,
        reference=f"ORIG-{index:04d}" if kind == "credit_note" else None,
        defects=defects,
    )

    # Defects that need a different rate are applied here, on the data model.
    if "bad_rate" in defects:
        doc.rate = Decimal("7")
    if "zero_with_rate" in defects:
        doc.rate = VAT_RATE  # a zero-rated supply carrying the standard rate
    return doc


def _round_to_20(value: Decimal) -> Decimal:
    """Round to the nearest multiple of 20 (keeps a 5% VAT exact to the fils)."""
    return (value / 20).quantize(Decimal("1")) * 20


def build_corpus(count: int = 100) -> list[tuple[str, Document, str]]:
    """Return (filename, document, xml) for the first ``count`` documents."""
    out: list[tuple[str, Document, str]] = []
    for index in range(1, count + 1):
        doc = _build(index)
        name = f"{doc.seller.series}-{doc.issue.year}-{index:04d}.xml"
        out.append((name, doc, render(doc)))
    return out


def expected_for(doc: Document) -> dict[str, object]:
    """The reviewed expectation for one document."""
    ids: list[str] = []
    for defect in doc.defects:
        ids.extend(DEFECTS[defect][1])
    return {
        "file": None,
        "document_id": doc.document_id,
        "kind": "credit_note" if doc.kind == "credit_note" else "invoice",
        "profile": _profile_for(_position(doc.index))[0],
        "vat_category": doc.vat,
        "defects": list(doc.defects),
        "expected_findings": sorted(set(ids)),
    }


def manifest(count: int = 100) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for name, doc, xml in build_corpus(count):
        entry = expected_for(doc)
        entry["file"] = name
        entry["sha256"] = hashlib.sha256(xml.encode("utf-8")).hexdigest()
        entry["net_total"] = str(doc.taxable)
        entries.append(entry)
    return {
        "schema": "pint-ae/corpus-v1",
        "seed": SEED,
        "as_of": AS_OF.isoformat(),
        "documents": count,
        "clean": sum(1 for e in entries if not e["defects"]),
        "defective": sum(1 for e in entries if e["defects"]),
        "defect_catalogue": {
            code: {"description": description, "findings": list(ids)}
            for code, (description, ids) in DEFECTS.items()
        },
        "entries": entries,
    }


def write_corpus(out: Path, count: int = 100, *, force: bool = False) -> dict[str, object]:
    """Write the corpus to ``out`` and return the manifest.

    Documents go into ``out/documents`` and the expectations into
    ``out/manifest.json``: a folder that is safe to point ``diagnose`` at contains
    documents only, so the manifest is never reported as an unreadable invoice.

    Refuses to write into a directory that already holds files unless ``force`` is
    given, so a client folder can never be overwritten by accident.
    """
    document_dir = out / "documents"
    if out.exists() and any(out.iterdir()) and not force:
        raise FileExistsError(f"{out} is not empty - pass --force to overwrite")
    document_dir.mkdir(parents=True, exist_ok=True)
    for existing in document_dir.glob("*.xml"):
        existing.unlink()

    for name, _doc, xml in build_corpus(count):
        (document_dir / name).write_text(xml, encoding="utf-8", newline="\n")
    payload = manifest(count)
    (out / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return payload
