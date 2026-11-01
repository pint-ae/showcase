# Learning Note 22 - Schematron Pipeline Verified

**Block:** 1.4b Paste 3
**Date:** 2026-11-01
**Files:** src/pint_ae/schematron/xsl/, tests/test_schematron.py

---

## What was proven

- saxonche 13.1.1 installs cleanly on Windows / Python 3.12
- .sch -> XSLT -> SVRL pipeline works end to end
- The mandatory toolchain is **4 files, not 3**
- Compiled XSLT is generated once, applied many times

## The 4-file skeleton (all required, same directory)

| File | Size | Role |
|---|---|---|
| iso_svrl_for_xslt2.xsl | 24 KB | Main entry point |
| iso_schematron_skeleton_for_saxon.xsl | 98 KB | Core generator |
| iso_dsdl_include.xsl | 54 KB | Handles xinclude directives |
| iso_abstract_expand.xsl | 12 KB | Expands abstract patterns |

Imports are relative: the entry file imports the skeleton, which imports
the other two. Missing any one produces FileNotFoundException pointing at
the missing file (not at the importer). Discovery: 4 files, not 3.

## The pipeline

1. Load `iso_svrl_for_xslt2.xsl` into `PySaxonProcessor.new_xslt30_processor()`
2. `compile_stylesheet(stylesheet_file=iso_svrl_for_xslt2.xsl)`
3. `.transform_to_string(source_file=your.sch)` -> compiled XSLT (as string)
4. Save compiled XSLT to disk
5. `compile_stylesheet(stylesheet_file=compiled.xsl)`
6. `.transform_to_string(source_file=your_invoice.xml)` -> SVRL
7. Parse SVRL with `lxml`: `failed-assert`, `fired-rule`, `active-pattern`

## The gotchas

- Saxon version reported is `SaxonC-HE 13.1` (not Saxon-HE 12.5). The C
  binding is one minor version ahead of the Java one.
- Compile is slow on first call (~1-2s). Subsequent transforms on the same
  `PySaxonProcessor` instance are fast (~50ms). Reuse the processor.
- The 4 skeleton files total ~187 KB — commit them, never fetch at runtime.
  If the skeleton directory is incomplete, the compile fails with a
  confusing error pointing at the wrong file.

## What this proves for the product

The riskiest external dependency for Block 1.4b is now verified. The tool
can:
- Compile any Schematron .sch file to XSLT (in ~1s, once)
- Apply that XSLT to any invoice XML (in ~50ms, cached)
- Extract failed-assert elements from the SVRL output
- Map them to `RuleViolation` objects

The only remaining unknown for full Schematron integration (Paste 3.2) is
whether the PINT AE .sch file is publicly downloadable and whether its
imports resolve without additional skeleton files.

## Interview Q&A

Q: How do you evaluate Schematron rules in Python?
A: saxonche (Saxon-HE C binding) transforms .sch to XSLT once, then
applies the compiled XSLT to each invoice. Output is SVRL XML, from
which failed-assert elements are extracted.

Q: Why saxonche and not lxml?
A: lxml cannot execute XSLT 2.0/3.0, which Schematron requires. Saxon is
the reference XSLT processor. saxonche is its Python binding.

Q: Why commit the skeleton XSLTs into the repo?
A: The 4 files are stable (Schematron 2017+), MIT-licensed, and total
187 KB. Committing them means the tool works offline, is version-pinned
to a tested state, and does not depend on a runtime fetch from GitHub.

Q: What is SVRL?
A: Schematron Validation Report Language. Structured XML output listing
active-pattern, fired-rule, failed-assert, successful-report elements.
Each failed-assert carries @test, @location, @id, and the diagnostic
message text.

---

## Spec reference

- Schematron skeleton: https://github.com/Schematron/schematron
- saxonche: https://pypi.org/project/saxonche/
- SVRL: ISO/IEC 19757-3
