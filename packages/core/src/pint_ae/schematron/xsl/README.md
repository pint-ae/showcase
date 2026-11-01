# Schematron skeleton XSLTs

Downloaded from https://github.com/Schematron/schematron/tree/master/trunk/schematron/code
License: MIT (upstream).

**All 4 files are required and must be in the same directory** (relative imports):
- iso_svrl_for_xslt2.xsl — main entry
- iso_schematron_skeleton_for_saxon.xsl — core, imports the next two
- iso_dsdl_include.xsl
- iso_abstract_expand.xsl

Missing any of them breaks the compile step with FileNotFoundException.
Commit these files; never fetch at runtime.
