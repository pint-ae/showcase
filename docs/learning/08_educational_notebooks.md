# Learning Note 08 — Educational Notebooks as Portfolio Signal

**Block:** 9a
**Date:** 2026-10-31
**Files:** notebooks/01_parsing.ipynb, notebooks/02_validation.ipynb
**Builder:** scripts/build_notebooks.py

---

## The concept

A notebook is not a script. A script runs. A notebook is code plus prose
plus rendered output — readable by someone who will never run it.

For a portfolio, that distinction is decisive. An engineer opening your
repo on GitHub sees a rendered notebook with markdown headers, executable
code, cell order. They understand the project in 5 minutes without cloning.
A raw .py file requires reading code like a detective.

---

## How we implement it here

Two notebooks:

1. notebooks/01_parsing.ipynb — parse() on a real fixture. Typed access,
   Decimal vs float.
2. notebooks/02_validation.ipynb — validate() on the same fixture.
   Business rules, breaking a rule, Peppol citations.

Both are GENERATED from scripts/build_notebooks.py using nbformat. The
.ipynb files are build artifacts, not hand-edited source.

Why generate:
- Regenerable if the API changes
- No accumulated hidden state (the #1 problem with hand-edited notebooks)
- Version control sees the build script, not a 10,000-line JSON diff
- CI can regenerate and diff to detect drift

---

## Why notebooks for a portfolio

1. Renderable on GitHub. The .ipynb renders as HTML — markdown headers,
   syntax-highlighted code, cell order. A hiring manager sees the finished
   product.
2. Shareable as a link. The rendered URL pastes into LinkedIn, email, or a
   client proposal. A .py file cannot.
3. Executable proof. When someone opens the notebook in VS Code, they can
   run each cell and see output.

---

## Interview Q&A

Q: Why generate notebooks from scripts instead of editing .ipynb by hand?
A: Hand-edited notebooks accumulate hidden state. Generating from a build
script gives reproducibility, clean diffs, CI-detectable drift.

Q: Why two notebooks instead of one?
A: Each teaches one concept. 01_parsing is XML → typed object.
02_validation is typed object → violations with citations.

Q: How do you keep notebooks current when the API changes?
A: The build script imports and calls the same functions. If parse()
changes signature, the build script fails — CI catches it.

Q: Why check in output cells?
A: For portfolio notebooks, the rendered output IS the demo.

Q: How does a notebook differ from documentation?
A: Documentation describes what code does. A notebook demonstrates it with
executable proof. "Show, don't tell" for a technical audience.

---

## Spec reference

- nbformat: https://nbformat.readthedocs.io/
- GitHub notebook rendering: https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files
