# Learning Note 13 - Building and Publishing Python Wheels

**Block:** W1 Block 12
**Date:** 2026-11-01
**File:** docs/learning/13_publishing_python_wheels.md

---

## The concept

A wheel is a Python package distribution. When `pip install pint-ae-toolkit`
runs, pip downloads the wheel, extracts it, and places the package in the
user's site-packages. The wheel includes the code, package metadata (name,
version, dependencies from pyproject.toml), and a RECORD of hashes.

`uv build` creates two artifacts:
- `pint_ae_toolkit-0.1.0-py3-none-any.whl` - the wheel (used by pip)
- `pint_ae_toolkit-0.1.0.tar.gz` - the source distribution

`uv publish` uploads both to PyPI. Once uploaded, `pip install pint-ae-toolkit`
works globally.

## Why the fresh-venv verification matters

The development venv has `pint_ae` installed in editable mode (from source).
A wheel install puts code in site-packages. These are different. A wheel can
fail in a fresh venv even when everything works in the dev venv - missing
package data, missing `__init__.py`, missing dependency declarations.

The verification is: create a fresh venv, pip install the wheel, import the
package. If it works, the wheel is valid. If not, fix pyproject.toml.

## Why the token is not in the repo

PyPI tokens are personal. Automating them into a script or config file that
gets committed is a security anti-pattern. The token goes in `$env:PYPI_TOKEN`
for local publishing, or `secrets.PYPI_TOKEN` in GitHub Actions. It never
touches the repo.

## What "closing G1" means

Before this block:
- Public repo: live ✓
- pip install: works only from git clone (editable install)
After successful publish:
- pip install pint-ae-toolkit: works from anywhere ✓

If the token wasn't set, G1 stays at 90% - the wheel is built and verified,
but not published. Set the token, re-run, G1 closes.

## Interview Q&A

Q: How do you verify a wheel works before publishing?
A: Create a fresh venv, pip install the wheel, import the package. If it
imports, the wheel is valid. The dev venv is not a valid test because it
has the package in editable mode.

Q: Why not `pip install .`?
A: `pip install .` builds and installs from source, but doesn't verify the
wheel is publishable. A wheel that installs locally can fail on PyPI (bad
metadata, missing files). The fresh-venv verify catches this.

Q: Why environment variable for the token?
A: Config files (.pypirc) persist and can be accidentally committed.
Env vars are session-scoped and standard for CI/CD.

Q: What if you publish the same version twice?
A: PyPI rejects it - version numbers are immutable. Bump to 0.1.1 in
pyproject.toml and rebuild.

Q: What is in the wheel?
A: Package code, METADATA (name/version/dependencies/description from
pyproject.toml), RECORD (hashes of every file). It is a ZIP file with
a specific naming convention.

---

## Spec reference

- uv build: https://docs.astral.sh/uv/guides/package/
- uv publish: https://docs.astral.sh/uv/guides/publish/
- PyPI token: https://pypi.org/manage/account/token/
