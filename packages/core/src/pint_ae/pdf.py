"""PDF report generator for PINT AE diagnostic results (AR/EN bilingual).

Renders a compliance report with:
- Summary table (invoice metadata, violation counts, status)
- Violations table (rule, field, message, Peppol citation)
- Audit trail (source SHA-256, generator version, timestamp)
- Footer: disclaimer + retention note (FTA context)

Supports --lang en, ar, or both. Arabic uses arabic-reshaper + python-bidi
for correct shaping and RTL layout. Font auto-detected: bundled
NotoSansArabic if present, else Windows Arial/Tahoma/Segoe UI, else Helvetica
fallback (Arabic rendering will be degraded without a covering font).
"""

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pint_ae.regulatory import provenance
from pint_ae.rules import RuleViolation
from pint_ae.types import PintAeInvoice

GENERATOR_VERSION = "0.6.1"


def _rule_counts() -> dict[str, int]:
    """Return counts from custom rules + Schematron files."""
    from pint_ae.rules import _RULES
    from pint_ae.schematron.validator import schematron_assertion_count

    n_custom = len(_RULES)
    n_schematron = schematron_assertion_count()
    return {
        "custom": n_custom,
        "schematron": n_schematron,
        "total": n_custom + n_schematron,
    }


def _find_arabic_font() -> Path | None:
    base = Path(__file__).parent / "fonts"
    candidates = [
        base / "NotoSansArabic-Regular.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/System/Library/Fonts/GeezaPro.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def arabic_font_status() -> dict[str, str | bool | None]:
    """Which font bilingual reports use, for `pint-ae selftest` and support.

    Arabic shaping needs a font that actually has Arabic glyphs. The package looks
    for `pint_ae/fonts/NotoSansArabic-Regular.ttf` first, then a handful of system
    fonts. If none is available the report is still generated (Latin content is
    complete), but Arabic text will not render - a limitation stated in the README.
    """
    return {
        "font_name": _ARABIC_FONT_NAME,
        "font_path": str(_font_path) if _font_path is not None else None,
        "bundled": bool(_font_path is not None and "fonts" in str(_font_path)),
    }


_ARABIC_FONT_NAME = "Helvetica"
_font_path = _find_arabic_font()
if _font_path is not None:
    try:
        pdfmetrics.registerFont(TTFont("PintAeArabic", str(_font_path)))
        _ARABIC_FONT_NAME = "PintAeArabic"
    except Exception:
        pass


def _ar(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return str(get_display(arabic_reshaper.reshape(text)))
    except Exception:
        return text


LABELS = {
    "title": {
        "en": "PINT AE Diagnostic Report",
        "ar": "\u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0627\u0644\u062a\u0634\u062e\u064a\u0635\u064a \u0644\u0640 PINT AE",
    },
    "summary": {"en": "Summary", "ar": "\u0627\u0644\u0645\u0644\u062e\u0635"},
    "violations": {
        "en": "Violations",
        "ar": "\u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0627\u062a",
    },
    "audit": {
        "en": "Audit trail",
        "ar": "\u0633\u062c\u0644 \u0627\u0644\u062a\u062f\u0642\u064a\u0642",
    },
    "no_violations": {
        "en": "No violations detected.",
        "ar": "\u0644\u0645 \u064a\u062a\u0645 \u0627\u0643\u062a\u0634\u0627\u0641 \u0623\u064a \u0645\u062e\u0627\u0644\u0641\u0627\u062a.",
    },
    "inv_id": {
        "en": "Invoice ID",
        "ar": "\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629",
    },
    "supplier": {"en": "Supplier", "ar": "\u0627\u0644\u0645\u0648\u0631\u062f"},
    "customer": {"en": "Customer", "ar": "\u0627\u0644\u0639\u0645\u064a\u0644"},
    "issue_date": {
        "en": "Issue date",
        "ar": "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0635\u062f\u0627\u0631",
    },
    "payable": {
        "en": "Payable amount",
        "ar": "\u0627\u0644\u0645\u0628\u0644\u063a \u0627\u0644\u0645\u0633\u062a\u062d\u0642",
    },
    "errors": {
        "en": "Violations (error)",
        "ar": "\u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0627\u062a (\u0623\u062e\u0637\u0627\u0621)",
    },
    "warnings": {
        "en": "Violations (warning)",
        "ar": "\u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0627\u062a (\u062a\u062d\u0630\u064a\u0631\u0627\u062a)",
    },
    "status": {"en": "Status", "ar": "\u0627\u0644\u062d\u0627\u0644\u0629"},
    "compliant": {"en": "COMPLIANT", "ar": "\u0645\u062a\u0648\u0627\u0641\u0642"},
    "non_compliant": {
        "en": "NON-COMPLIANT",
        "ar": "\u063a\u064a\u0631 \u0645\u062a\u0648\u0627\u0641\u0642",
    },
    "rule": {"en": "Rule", "ar": "\u0627\u0644\u0642\u0627\u0639\u062f\u0629"},
    "field": {"en": "Field", "ar": "\u0627\u0644\u062d\u0642\u0644"},
    "message": {"en": "Message", "ar": "\u0627\u0644\u0631\u0633\u0627\u0644\u0629"},
    "citation": {"en": "Citation", "ar": "\u0627\u0644\u0645\u0631\u062c\u0639"},
    "sha": {
        "en": "Source SHA-256",
        "ar": "\u0628\u0635\u0645\u0629 SHA-256 \u0644\u0644\u0645\u0635\u062f\u0631",
    },
    "generator": {
        "en": "Generator",
        "ar": "\u0627\u0644\u0645\u064f\u0648\u0644\u0650\u0651\u062f",
    },
    "generated": {
        "en": "Generated",
        "ar": "\u062a\u0645 \u0627\u0644\u062a\u0648\u0644\u064a\u062f",
    },
}


def _add_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    counts = _rule_counts()
    line1 = f"Validates {counts['total']} PINT AE checks ({counts['custom']} custom + {counts['schematron']} Schematron) + UBL 2.1 XSD"
    line2 = "Includes MD 197/2026: 14-business-day transmission window, VAT group exclusion"
    line3 = "Retention: 5 years. Diagnostic only - not substitute for FTA-compliant e-invoicing."
    canvas.drawString(20 * mm, 13 * mm, line1)
    canvas.drawString(20 * mm, 9 * mm, line2)
    canvas.drawString(20 * mm, 5 * mm, line3)
    canvas.restoreState()


def _txt(key: str, lang: str) -> str:
    raw = LABELS[key].get(lang, LABELS[key]["en"])
    return _ar(raw) if lang == "ar" else raw


def _styles(lang: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    font = _ARABIC_FONT_NAME if lang == "ar" else "Helvetica"
    align = 2 if lang == "ar" else 0
    return {
        "title": ParagraphStyle(
            "T", parent=base["Heading1"], fontName=font, fontSize=16, alignment=align, spaceAfter=4
        ),
        "section": ParagraphStyle(
            "S",
            parent=base["Heading2"],
            fontName=font,
            fontSize=12,
            alignment=align,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "B", parent=base["Normal"], fontName=font, fontSize=9, alignment=align
        ),
        "small": ParagraphStyle(
            "SM",
            parent=base["Normal"],
            fontName=font,
            fontSize=8,
            alignment=align,
            textColor=colors.grey,
        ),
    }


def _summary_table(inv: PintAeInvoice, violations: list[RuleViolation], lang: str) -> Table:
    err = sum(1 for v in violations if v.severity == "error")
    warn = sum(1 for v in violations if v.severity == "warning")
    status = _txt("compliant", lang) if not violations else _txt("non_compliant", lang)
    data = [
        [_txt("inv_id", lang), inv.invoice_id],
        [_txt("supplier", lang), f"{inv.supplier.name} (TRN {inv.supplier.trn})"],
        [_txt("customer", lang), f"{inv.customer.name} (TRN {inv.customer.trn})"],
        [_txt("issue_date", lang), inv.issue_date.isoformat()],
        [_txt("payable", lang), f"{inv.payable_amount} {inv.document_currency_code}"],
        [_txt("errors", lang), str(err)],
        [_txt("warnings", lang), str(warn)],
        [_txt("status", lang), status],
    ]
    t = Table(data, colWidths=[50 * mm, 120 * mm])
    t.setStyle(
        TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    _ARABIC_FONT_NAME if lang == "ar" else "Helvetica-Bold",
                ),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    return t


def _violations_table(violations: list[RuleViolation], lang: str) -> Table:
    data = [
        [_txt("rule", lang), _txt("field", lang), _txt("message", lang), _txt("citation", lang)]
    ]
    for v in violations:
        msg = _ar(v.message) if lang == "ar" else v.message
        cit = _ar(v.citation) if lang == "ar" else v.citation
        fld = _ar(v.field) if lang == "ar" else v.field
        data.append([v.rule_id, fld, msg, cit])
    t = Table(data, colWidths=[18 * mm, 32 * mm, 68 * mm, 52 * mm], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    _ARABIC_FONT_NAME if lang == "ar" else "Helvetica-Bold",
                ),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
            ]
        )
    )
    return t


def generate_report(
    invoice: PintAeInvoice,
    violations: list[RuleViolation],
    source_bytes: bytes,
    output_path: Path,
    language: str = "en",
    generated_at: datetime | None = None,
) -> Path:
    """Generate a bilingual PDF diagnostic report.

    language: "en", "ar", or "both".

    ``generated_at`` fixes the timestamp printed on the report and in the audit
    trail. It defaults to "now", which is what the CLI wants; the engagement
    packager passes the engagement date so two packs built from the same inputs
    are byte-identical (a reproducible deliverable needs no random bytes, and a
    timestamp is the only non-deterministic content this report contains).
    """
    if language not in ("en", "ar", "both"):
        raise ValueError(f"language must be en, ar, or both; got {language}")

    moment = generated_at or datetime.now(UTC)

    langs = ["en"] if language == "en" else (["ar"] if language == "ar" else ["en", "ar"])
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
        title=f"PINT AE Diagnostic - {invoice.invoice_id}",
        author="pint-ae-toolkit",
        onFirstPage=_add_footer,
        onLaterPages=_add_footer,
    )

    story = []
    for i, lang in enumerate(langs):
        s = _styles(lang)
        if i > 0:
            story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(_txt("title", lang), s["title"]))
        story.append(
            Paragraph(
                f"{invoice.invoice_id} \u00b7 {moment.strftime('%Y-%m-%d %H:%M UTC')}",
                s["small"],
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(_txt("summary", lang), s["section"]))
        story.append(_summary_table(invoice, violations, lang))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(_txt("violations", lang), s["section"]))
        if violations:
            story.append(_violations_table(violations, lang))
        else:
            story.append(Paragraph(_txt("no_violations", lang), s["body"]))

    # Audit trail (EN only, technical content)
    s_en = _styles("en")
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_txt("audit", "en"), s_en["section"]))
    source_hash = sha256(source_bytes).hexdigest()
    story.append(
        Paragraph(f"Source SHA-256: <font face='Courier'>{source_hash}</font>", s_en["small"])
    )
    story.append(Paragraph(f"Generator: pint-ae-toolkit v{GENERATOR_VERSION}", s_en["small"]))
    story.append(Paragraph(f"Generated: {moment.isoformat()}", s_en["small"]))
    prov = provenance()
    story.append(
        Paragraph(
            f"Specification: {prov['spec_version']} (released {prov['spec_released']}, "
            f"PINT General {prov['pint_general_version']})",
            s_en["small"],
        )
    )
    story.append(
        Paragraph(
            f"Rule set SHA-256: <font face='Courier'>{prov['rule_set_sha256']}</font>",
            s_en["small"],
        )
    )
    story.append(Paragraph(f"Regulation snapshot: {prov['regulation_snapshot']}", s_en["small"]))

    # Scope line as Paragraph (pypdf-extractable; _add_footer draws it visually too)
    counts = _rule_counts()
    s_scope = _styles("en")["small"]
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Validates {counts['total']} PINT AE checks ({counts['custom']} custom + {counts['schematron']} Schematron) + UBL 2.1 XSD.",
            s_scope,
        )
    )
    story.append(
        Paragraph(
            "Includes MD 197/2026: 14-business-day transmission window, VAT group exclusion.",
            s_scope,
        )
    )
    story.append(
        Paragraph(
            "Retention: 5 years. Diagnostic only - not a substitute for FTA-compliant e-invoicing.",
            s_scope,
        )
    )

    doc.build(story)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buffer.getvalue())
    return output_path
