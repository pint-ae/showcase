"""XSD validation against UBL 2.1 (Invoice and CreditNote)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lxml import etree

if TYPE_CHECKING:
    from pint_ae.rules import RuleViolation

XSD_DIR = Path(__file__).parent / "xsd" / "maindoc"

_SCHEMA_FILES = {
    "Invoice": "UBL-Invoice-2.1.xsd",
    "CreditNote": "UBL-CreditNote-2.1.xsd",
}


@cache
def _schema(root_name: str = "Invoice") -> etree.XMLSchema:
    """Load the UBL 2.1 schema for the given document root (cached)."""
    return etree.XMLSchema(etree.parse(str(XSD_DIR / _SCHEMA_FILES[root_name])))


def validate_xsd(xml_source: str | bytes) -> list[RuleViolation]:
    from pint_ae.rules import RuleViolation

    if isinstance(xml_source, str):
        xml_source = xml_source.encode("utf-8")

    try:
        doc = etree.fromstring(xml_source)
    except etree.XMLSyntaxError:
        return []

    root_name = str(etree.QName(doc).localname)
    if root_name not in _SCHEMA_FILES:
        # Not a document type we validate; the rule engine reports unsupported roots.
        return []

    schema = _schema(root_name)
    if schema.validate(doc):
        return []

    out: list[RuleViolation] = []
    # lxml-stubs types _ErrorLog as non-sized/non-indexable, but runtime
    # supports both. Cast to Any to satisfy mypy without disabling checks.
    error_log: Any = schema.error_log
    for i in range(len(error_log)):
        err = error_log[i]
        path_val = str(err.path) if err.path else "structure"
        msg = str(err.message)
        # Rule id = schema error class, field = failing element path. Line
        # numbers were the id before; they shift on reformatting and collide,
        # and a rule id must identify the rule, not a location in one file.
        error_type = str(getattr(err, "type_name", "") or "SCHEMA")
        out.append(
            RuleViolation(
                rule_id=f"XSD-{error_type}",
                citation="UBL 2.1 XSD (OASIS)",
                field=path_val,
                message=msg,
                severity="error",
            )
        )
    return out
