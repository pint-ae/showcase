# Learning Note 07 — CLI Design for Compliance Tools

**Block:** 8
**Date:** 2026-10-31
**Code:** packages/core/src/pint_ae/cli.py
**Stack:** typer + rich

---

## The concept

A command-line interface (CLI) is a text-based interface invoked from a
terminal. For compliance tools specifically, the CLI is not a UI
convenience - it is the primary integration surface.

Typer turns a Python function into a CLI in one decorator. It handles
argument parsing, help text, type coercion, shell completion. Rich makes
terminal output readable - colors, tables, bold, structured layout.

Together they turn a Python module into a tool a CFO can run.

---

## How we implement it here

The CLI exposes one command: pint-ae diagnose <files...>

Flow:
1. Read each file
2. parse() -> PintAeInvoice
3. validate() -> list[RuleViolation]
4. Print report per file
5. Exit 0 (clean), 1 (violations), 2 (parse errors)

Exit codes are the primary API contract. Every compliance tool (Snyk,
Trivy, gitleaks) uses:
- 0 = safe to proceed
- 1 = issues found, review needed
- 2 = tool error, escalate

The [project.scripts] entry in pyproject.toml makes the CLI available as
a shell command after pip install. No wrappers.

---

## Why CLI and not web UI for tax tools

1. CI/CD integration - clients wire pint-ae into build pipeline to fail
   on non-compliant invoices
2. Batch processing - thousands of invoices in one command
3. Automation - cron jobs, pre-commit hooks, ETL pipelines
4. Air-gapped environments - banking and government clients require this

A web UI is nice-to-have. A CLI is have-to-have.

---

## Interview Q&A

Q: Why a CLI over a web UI?
A: CI/CD integration, batch processing, automation, air-gapped
compatibility. A CLI's exit code is a contract that lets a client's build
pipeline fail on non-compliant invoices. Web UI cannot do that.

Q: Why typer and not argparse?
A: Typer is built on Click, which is built on argparse. Type-hint based
parsing, auto-generated help, shell completion. Argparse works but
verbose.

Q: Why rich and not plain print?
A: Structured output. Colors by severity, tables, truncation. When a CFO
sees a red X they understand instantly.

Q: How do you test a CLI?
A: typer.testing.CliRunner. Simulates argv, captures stdout + exit code.
Every command should test success path (exit 0) and each failure path.

Q: What about exit codes in Python?
A: sys.exit(n) or typer.Exit(code=n). typer.Exit is preferred in typer
apps - it integrates with typer's error handling.

---

## Addendum — why B008 is ignored for typer

Ruff flags typer.Argument(...) in a function default as B008. For most
Python code this is correct advice. For typer (and FastAPI, click),
calling typer.Argument() in the default is the standard pattern - the
framework inspects it.

Fix is a per-file ignore:

    [tool.ruff.lint.per-file-ignores]
    "src/pint_ae/cli.py" = ["B008"]

Every typer project does this. Changing the code to satisfy B008 breaks
the framework pattern.

---

## Spec reference

- Typer: https://typer.tiangolo.com/
- Rich: https://rich.readthedocs.io/
- Python entry points: https://packaging.python.org/en/latest/specifications/entry-points/
- Unix exit codes: https://tldp.org/LDP/abs/html/exitcodes.html
