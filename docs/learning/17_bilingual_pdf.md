# Learning Note 17 - Bilingual PDF for the UAE Market

**Block:** 1.1b
**Date:** 2026-11-01
**Files:** packages/core/src/pint_ae/pdf.py, tests/test_pdf.py
**Samples:** docs/samples/INV-2026-001-report-{en,ar,both}.pdf

---

## The concept

Arabic is not "English with different characters." Three things break
naive PDF rendering:

1. Character shaping: Arabic letters change form by position (initial,
   medial, final, isolated). The raw Unicode codepoint is not what appears.
2. Bidirectional layout: Arabic is RTL, numbers and Latin words are LTR.
   Mixed lines require RTL layout with LTR islands.
3. Font coverage: Helvetica has zero Arabic glyphs. A covering TTF must
   be registered.

Three libraries solve this:
- arabic-reshaper (character shaping)
- python-bidi (bidirectional layout)
- A font with Arabic glyphs (Arial, Tahoma, Noto Sans Arabic)

Skip any one and you get broken output: disconnected letters, reversed
word order, or tofu boxes.

## How Block 1.1b implements it

- _find_arabic_font() searches bundled Noto font first, then Windows
  system fonts (arial.ttf, tahoma.ttf, segoeui.ttf), then macOS/Linux
  fallbacks.
- _ar(text) applies arabic_reshaper + bidi to every Arabic string.
- generate_report(..., language="en"|"ar"|"both") renders one or both
  languages. "both" stacks EN section then AR section.
- Footer disclaimer: "Diagnostic report only. The legal e-invoice is the
  structured PINT AE XML. Not a substitute for FTA-compliant e-invoicing."
- Footer retention: "Retain this report for 5 years alongside VAT records
  per FTA requirements."

## Why the disclaimer matters

PINT AE: only structured XML is the legal e-invoice. A PDF is a
supporting copy. Saying this clearly on every page:
- protects the client from accidentally treating the PDF as the invoice
- protects the practitioner from liability if the client submits the PDF
  as an "invoice"
- demonstrates UAE regulatory literacy

## Why the retention note matters

UAE VAT retention: 5 years general, 7 years real estate, 15 years for
evasion cases. A diagnostic report in the client's compliance file
follows the same retention. The footer note prompts this without managing
it (the client's responsibility).

## Sample size observations

- EN only: 2.4 KB (Latin fonts, no embedding)
- AR only: 48.9 KB (Arabic font subset embedded in PDF)
- BOTH: 49.9 KB (font embedded once, both languages use it)

The size jump from EN to AR is not bloat - it is the embedded Arabic
font glyphs. This is correct. A PDF that renders Arabic without an
embedded font would show tofu boxes on a machine without the font.

## Test counts

Block 1.1b: 5 PDF tests (en, ar, both, invalid language, with violations)
Total after Block 1.1b: 21 tests (16 original + 5 PDF)
Test suite runtime: ~34s (Arabic reshaping is slow per PDF, not a defect)

## Interview Q&A

Q: How do you render Arabic in a PDF?
A: Three layers. arabic-reshaper for character shaping. python-bidi for
bidirectional layout. A TTF font with Arabic glyphs registered with
reportlab. Skip any one and output is broken.

Q: Why not just use Arial for both languages?
A: Arial covers both. But processing differs. English needs no shaping.
Arabic does. The same font renders differently depending on whether you
pre-process the string.

Q: Why stack EN and AR sections instead of side-by-side?
A: Side-by-side halves column widths and breaks the Peppol citation
column. Stacked means each language gets full A4 width.

Q: How do you test Arabic renders correctly?
A: pypdf extracts text and asserts the Latin invoice ID appears (Latin
is language-independent). Full visual verification requires opening the
PDF - the samples are committed for reference.

Q: What if the environment has no Arabic font?
A: _ar() returns raw text (no shaping). PDF generates but Arabic shows
disconnected or boxes. Degraded mode for CI. For production, bundle
Noto Sans Arabic in packages/core/src/pint_ae/fonts/.

---

## Spec reference

- arabic-reshaper: https://github.com/awdeorio/arabic-reshaper
- python-bidi: https://github.com/MeirKohler/python-bidi
- Noto Sans Arabic: https://fonts.google.com/noto/specimen/Noto+Sans+Arabic
- Samples: docs/samples/
