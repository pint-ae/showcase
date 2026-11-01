"""Parser for PINT AE documents (UBL 2.1 Invoice and CreditNote).

Exposes: parse(xml: str | bytes) -> PintAeInvoice

The parser follows what the official PINT AE 1.0.4 samples actually contain:
- two document roots: ``Invoice`` and ``CreditNote`` (with ``cbc:CreditNoteTypeCode``
  and ``cac:CreditNoteLine``), not just invoices;
- party names may live in ``cac:PartyName/cbc:Name`` or in
  ``cac:PartyLegalEntity/cbc:RegistrationName``;
- a buyer may have no VAT identifier (exports, zero-rated supplies), so the
  counterparty TRN is optional at parse time and reported as a finding instead;
- ``cac:TaxCategory/cbc:Percent`` is absent for Exempt and Not-subject items, and
  the aligned UAE category list includes ``N`` (standard rate, additional VAT);
- the transaction-type code is carried in ``cbc:ProfileExecutionID`` (IBR-154-AE),
  with ``cbc:TransactionTypeCode`` accepted as a fallback for older fixtures.
"""

from datetime import date
from decimal import Decimal

from lxml import etree

from pint_ae.types import LineItem, Party, PintAeInvoice, TaxCategory

NSMAP = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

INVOICE_ROOT = "Invoice"
CREDIT_NOTE_ROOT = "CreditNote"


def _text(el: etree._Element, xpath: str) -> str:
    found = el.find(xpath, namespaces=NSMAP)
    if found is None or found.text is None:
        raise ValueError(f"Missing required element: {xpath}")
    return str(found.text).strip()


def _opt_text(el: etree._Element, xpath: str) -> str | None:
    found = el.find(xpath, namespaces=NSMAP)
    if found is None or found.text is None:
        return None
    return str(found.text).strip()


def _decimal(el: etree._Element, xpath: str) -> Decimal:
    return Decimal(_text(el, xpath))


def _local_name(el: etree._Element) -> str:
    return str(etree.QName(el).localname)


def _party_name(el: etree._Element, base: str) -> str:
    """Party name from PartyName/Name, else PartyLegalEntity/RegistrationName."""
    for candidate in ("cac:PartyName/cbc:Name", "cac:PartyLegalEntity/cbc:RegistrationName"):
        value = _opt_text(el, f"{base}/cac:Party/{candidate}")
        if value:
            return value
    raise ValueError(f"Missing party name: {base}")


def _parse_party(el: etree._Element, base: str) -> Party:
    name = _party_name(el, base)
    trn = _opt_text(el, f"{base}/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
    # Electronic address: PINT AE uses cbc:EndpointID (IBT-034/IBT-049);
    # PartyIdentification is kept as a fallback for older fixtures.
    peppol_id: str | None = None
    endpoint = el.find(f"{base}/cac:Party/cbc:EndpointID", namespaces=NSMAP)
    if endpoint is not None and endpoint.text:
        scheme = endpoint.get("schemeID")
        peppol_id = f"{scheme}:{endpoint.text.strip()}" if scheme else endpoint.text.strip()
    else:
        id_el = el.find(f"{base}/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=NSMAP)
        if id_el is not None and id_el.text is not None:
            scheme = id_el.get("schemeID")
            peppol_id = f"{scheme}:{id_el.text.strip()}" if scheme else id_el.text.strip()
    country = _opt_text(
        el, f"{base}/cac:Party/cac:PostalAddress/cac:Country/cbc:IdentificationCode"
    )
    country_subentity = _opt_text(el, f"{base}/cac:Party/cac:PostalAddress/cbc:CountrySubentity")
    legal_registration = _opt_text(el, f"{base}/cac:Party/cac:PartyLegalEntity/cbc:CompanyID")
    is_person = el.find(f"{base}/cac:Party/cac:Person", namespaces=NSMAP) is not None
    return Party(
        name=name,
        trn=trn,
        peppol_id=peppol_id,
        country_code=country,
        country_subentity=country_subentity,
        legal_registration=legal_registration,
        is_person=is_person,
    )


def _parse_tax_category(cat_el: etree._Element) -> TaxCategory:
    code = cat_el.findtext("cbc:ID", namespaces=NSMAP)
    if code is None:
        raise ValueError("TaxCategory missing cbc:ID")
    pct = cat_el.findtext("cbc:Percent", namespaces=NSMAP)
    return TaxCategory(
        code=code.strip(),
        percent=Decimal(pct.strip()) if pct is not None else None,
    )


def _parse_line(line_el: etree._Element) -> LineItem:
    line_id = _text(line_el, "cbc:ID")
    desc = _text(line_el, "cac:Item/cbc:Name")
    qty_el = line_el.find("cbc:InvoicedQuantity", namespaces=NSMAP)
    if qty_el is None:
        qty_el = line_el.find("cbc:CreditedQuantity", namespaces=NSMAP)
    if qty_el is None or qty_el.text is None:
        raise ValueError("Line missing InvoicedQuantity/CreditedQuantity")
    qty = Decimal(qty_el.text.strip())
    unit = qty_el.get("unitCode", "EA")
    price = _decimal(line_el, "cac:Price/cbc:PriceAmount")
    base_qty_text = _opt_text(line_el, "cac:Price/cbc:BaseQuantity")
    base_qty = Decimal(base_qty_text) if base_qty_text else None
    allowance_total = Decimal("0")
    charge_total = Decimal("0")
    for ac_el in line_el.findall("cac:AllowanceCharge", namespaces=NSMAP):
        amount_text = ac_el.findtext("cbc:Amount", namespaces=NSMAP)
        if amount_text is None:
            continue
        indicator = (ac_el.findtext("cbc:ChargeIndicator", namespaces=NSMAP) or "").strip().lower()
        if indicator == "true":
            charge_total += Decimal(amount_text.strip())
        else:
            allowance_total += Decimal(amount_text.strip())
    total = _decimal(line_el, "cbc:LineExtensionAmount")
    cat_el = line_el.find("cac:Item/cac:ClassifiedTaxCategory", namespaces=NSMAP)
    if cat_el is None:
        raise ValueError("Line missing cac:ClassifiedTaxCategory")
    return LineItem(
        line_id=line_id,
        description=desc,
        quantity=qty,
        unit_code=unit,
        unit_price=price,
        base_quantity=base_qty,
        allowance_total=allowance_total,
        charge_total=charge_total,
        line_total=total,
        tax_category=_parse_tax_category(cat_el),
    )


def parse(xml: str | bytes) -> PintAeInvoice:
    """Parse a PINT AE UBL 2.1 Invoice or CreditNote into a PintAeInvoice."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    root_name = _local_name(root)
    if root_name not in (INVOICE_ROOT, CREDIT_NOTE_ROOT):
        raise ValueError(f"Unsupported document root: {root_name}")

    is_credit_note = root_name == CREDIT_NOTE_ROOT
    type_code_xpath = "cbc:CreditNoteTypeCode" if is_credit_note else "cbc:InvoiceTypeCode"
    line_xpath = "cac:CreditNoteLine" if is_credit_note else "cac:InvoiceLine"

    supplier = _parse_party(root, "cac:AccountingSupplierParty")
    customer = _parse_party(root, "cac:AccountingCustomerParty")

    tax_cats: list[TaxCategory] = []
    for sub in root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NSMAP):
        cat_el = sub.find("cac:TaxCategory", namespaces=NSMAP)
        if cat_el is None:
            raise ValueError("TaxSubtotal missing cac:TaxCategory")
        base = _parse_tax_category(cat_el)
        taxable = sub.findtext("cbc:TaxableAmount", namespaces=NSMAP)
        tax_amt = sub.findtext("cbc:TaxAmount", namespaces=NSMAP)
        tax_cats.append(
            TaxCategory(
                code=base.code,
                percent=base.percent,
                taxable_amount=Decimal(taxable.strip()) if taxable else None,
                tax_amount=Decimal(tax_amt.strip()) if tax_amt else None,
            )
        )

    line_items = [_parse_line(line) for line in root.findall(line_xpath, namespaces=NSMAP)]

    transaction_type_code = _opt_text(root, "cbc:ProfileExecutionID") or _opt_text(
        root, "cbc:TransactionTypeCode"
    )
    customization_id = _text(root, "cbc:CustomizationID")
    self_billed = "selfbilling" in customization_id
    if is_credit_note:
        document_type = "self-billed-credit-note" if self_billed else "credit-note"
    else:
        document_type = "self-billed-invoice" if self_billed else "invoice"

    line_extension_amount = _decimal(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount")
    tax_exclusive_amount = _decimal(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount")
    tax_inclusive_amount = _decimal(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount")
    prepaid = _opt_text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount")
    rounding = _opt_text(root, "cac:LegalMonetaryTotal/cbc:PayableRoundingAmount")

    return PintAeInvoice(
        customization_id=customization_id,
        profile_id=_text(root, "cbc:ProfileID"),
        document_type=document_type,
        invoice_id=_text(root, "cbc:ID"),
        issue_date=date.fromisoformat(_text(root, "cbc:IssueDate")),
        invoice_type_code=_text(root, type_code_xpath),
        document_currency_code=_text(root, "cbc:DocumentCurrencyCode"),
        transaction_type_code=transaction_type_code,
        supplier=supplier,
        customer=customer,
        tax_categories=tax_cats,
        line_items=line_items,
        line_extension_amount=line_extension_amount,
        tax_exclusive_amount=tax_exclusive_amount,
        tax_inclusive_amount=tax_inclusive_amount,
        prepaid_amount=Decimal(prepaid.strip()) if prepaid else None,
        payable_rounding_amount=Decimal(rounding.strip()) if rounding else None,
        payable_amount=_decimal(root, "cac:LegalMonetaryTotal/cbc:PayableAmount"),
    )
