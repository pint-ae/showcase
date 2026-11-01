"""Schematron validation for PINT AE invoices.

Default conformance set = the official PINT AE Billing 1.0.4 artefacts that are
vendored in `schematron/vendor/pint-ae-1.0.4/`:

- ``shared.sch``       170 assertions — shared PINT rules
- ``jurisdiction.sch`` 132 assertions — UAE jurisdiction rules

All 302 assertions carry ``flag="fatal"`` in the publisher's source, so a failed
assertion is reported as ``severity="error"``. The publisher's precompiled
``.xslt`` files are used directly when present (no Saxon compilation, no writable
cache needed); a ``.sch`` file is compiled with the bundled ISO skeleton only
when no ``.xslt`` exists, and that compilation is cached via ``compiled_dir()``.

The older pair (``shared_pint.sch`` 171 + ``peppol_bis3.sch`` 160) is kept as an
optional legacy layer behind ``include_peppol_bis3=True`` (CLI:
``--peppol-bis3``). It is off by default because Peppol BIS 3.0 is not
CIUS-safe for PINT AE: it derives ``profile`` from a BIS ProfileID that PINT AE
does not use, so some of its rules can misfire. Its findings stay warnings.

Provenance: ``docs/sources/MANIFEST.yaml`` (package SHA-256) and
``vendor/pint-ae-1.0.4/README.md``.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from lxml import etree
from saxonche import PySaxonProcessor

SVRL_NS = {"svrl": "http://purl.oclc.org/dsdl/svrl"}

_HERE = Path(__file__).parent
RULES_DIR = _HERE / "rules"
VENDOR_DIR = _HERE / "vendor" / "pint-ae-1.0.4"
SB_VENDOR_DIR = _HERE / "vendor" / "pint-ae-sb-1.0.4"
SKELETON = _HERE / "xsl" / "iso_svrl_for_xslt2.xsl"


@dataclass(frozen=True)
class Layer:
    """One Schematron layer: source, optional precompiled XSLT, severity default."""

    name: str
    sch: Path
    xslt: Path | None
    default_severity: str


OFFICIAL_LAYERS: tuple[Layer, ...] = (
    Layer(
        "shared 1.0.4",
        VENDOR_DIR / "shared.sch",
        VENDOR_DIR / "shared.xslt",
        "error",
    ),
    Layer(
        "jurisdiction 1.0.4",
        VENDOR_DIR / "jurisdiction.sch",
        VENDOR_DIR / "jurisdiction.xslt",
        "error",
    ),
)

LEGACY_LAYERS: tuple[Layer, ...] = (
    Layer("shared_pint.sch", RULES_DIR / "shared_pint.sch", None, "warning"),
    Layer("peppol_bis3.sch", RULES_DIR / "peppol_bis3.sch", None, "warning"),
)

#: Self-billing documents use the same jurisdiction layer but a shared layer
#: preprocessed with the self-billing document-type codes (389/261), so the
#: customization identifier decides which shared layer applies.
SELF_BILLING_LAYERS: tuple[Layer, ...] = (
    Layer(
        "shared 1.0.4 (self-billing)",
        SB_VENDOR_DIR / "shared.sch",
        SB_VENDOR_DIR / "shared.xslt",
        "error",
    ),
    Layer(
        "jurisdiction 1.0.4 (self-billing)",
        SB_VENDOR_DIR / "jurisdiction.sch",
        SB_VENDOR_DIR / "jurisdiction.xslt",
        "error",
    ),
)

# Names of the .sch files that make up each set (used by scripts/verify.ps1).
SCHEMATRON_FILES: tuple[str, ...] = tuple(layer.sch.name for layer in OFFICIAL_LAYERS)
LEGACY_SCHEMATRON_FILES: tuple[str, ...] = tuple(layer.sch.name for layer in LEGACY_LAYERS)

_FLAG_TO_SEVERITY = {"fatal": "error", "error": "error", "warning": "warning"}


class SchematronRuntimeError(RuntimeError):
    """The official XSLT failed to evaluate a document (it is not valid XML data)."""

    def __init__(self, layer: str, message: str) -> None:
        super().__init__(f"{layer}: {message}")
        self.layer = layer
        self.detail = message


#: Compiled stylesheets are reused per process: Saxon compilation dominates the
#: runtime of a batch. `--jobs` runs in separate processes, so each worker keeps
#: its own processor. The processor is not used from threads concurrently.
_EXECUTABLES: dict[str, tuple[PySaxonProcessor, Any]] = {}
_EXECUTABLE_LOCK = threading.Lock()


def _executable_for(stylesheet: Path) -> tuple[PySaxonProcessor, Any]:
    key = str(stylesheet)
    with _EXECUTABLE_LOCK:
        cached = _EXECUTABLES.get(key)
        if cached is None:
            proc = PySaxonProcessor(license=False)
            xslt = proc.new_xslt30_processor()
            cached = (proc, xslt.compile_stylesheet(stylesheet_file=key))
            _EXECUTABLES[key] = cached
        return cached


def reset_processor_cache() -> None:
    """Drop cached Saxon processors (tests that mock the pipeline)."""
    with _EXECUTABLE_LOCK:
        _EXECUTABLES.clear()


@dataclass
class SchematronViolation:
    """A single Schematron failed-assert mapped to a violation."""

    rule_id: str
    citation: str
    message: str
    location: str
    severity: str = "error"


@cache
def compiled_dir() -> Path:
    """Directory for the compiled .xsl cache (only used when no .xslt exists).

    Preferred location is inside the package (source installs, CI). Fabric
    Environments, Docker and any read-only or shared install cannot write
    there, so fall back to the platform cache directory. PINT_AE_CACHE_DIR
    overrides both, which is how the Fabric notebook pins a writable path.
    """
    override = os.environ.get("PINT_AE_CACHE_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path

    package_dir = _HERE / "compiled"
    try:
        package_dir.mkdir(parents=True, exist_ok=True)
        probe = package_dir / ".write-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return package_dir
    except OSError:
        pass

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path(tempfile.gettempdir())
    fallback = root / "pint-ae" / "cache" / "schematron"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def active_layers(include_peppol_bis3: bool = False) -> tuple[Layer, ...]:
    """Layers that make up the conformance set for a run (billing profile)."""
    return OFFICIAL_LAYERS + (LEGACY_LAYERS if include_peppol_bis3 else ())


def layers_for_document(
    xml_source: str | bytes, include_peppol_bis3: bool = False
) -> tuple[Layer, ...]:
    """Conformance layers for a document, choosing the self-billing shared layer."""
    text = _to_text(xml_source)[:4000]
    layers = SELF_BILLING_LAYERS if "urn:peppol:pint:selfbilling" in text else OFFICIAL_LAYERS
    return layers + (LEGACY_LAYERS if include_peppol_bis3 else ())


def compile_schematron(sch_path: Path) -> Path:
    """Compile a .sch file to XSLT with the ISO skeleton, cached on disk."""
    if not sch_path.exists():
        raise FileNotFoundError(f"Schematron file missing: {sch_path}")

    cache = compiled_dir()
    compiled_path = cache / (sch_path.stem + ".xsl")
    if compiled_path.exists() and compiled_path.stat().st_mtime >= sch_path.stat().st_mtime:
        return compiled_path

    with PySaxonProcessor(license=False) as proc:
        xslt = proc.new_xslt30_processor()
        exec1 = xslt.compile_stylesheet(stylesheet_file=str(SKELETON))
        compiled = exec1.transform_to_string(source_file=str(sch_path))
    compiled_path.write_text(compiled, encoding="utf-8")
    return compiled_path


def stylesheet_for(layer: Layer) -> Path:
    """Return the XSLT to run: the publisher's precompiled one when available."""
    if layer.xslt is not None and layer.xslt.exists():
        return layer.xslt
    if not layer.sch.exists():
        raise FileNotFoundError(f"Schematron file missing: {layer.sch}")
    return compile_schematron(layer.sch)


def _rule_id(fa: etree._Element, fallback: str) -> str:
    """Extract a stable identifier from a failed-assert element."""
    rid = fa.get("id")
    if rid:
        return rid
    test = fa.get("test") or ""
    return test[:40] if test else fallback


def _severity(fa: etree._Element, default: str) -> str:
    """Map the SVRL ``flag`` to our severity; default when absent."""
    flag = (fa.get("flag") or "").strip().lower()
    return _FLAG_TO_SEVERITY.get(flag, default)


def _apply_layer(layer: Layer, xml_text: str) -> list[SchematronViolation]:
    """Apply one layer's XSLT to invoice XML, parse SVRL."""
    stylesheet = stylesheet_for(layer)
    proc, executable = _executable_for(stylesheet)
    try:
        with _EXECUTABLE_LOCK:
            source_node = proc.parse_xml(xml_text=xml_text)
            svrl = executable.transform_to_string(xdm_node=source_node)
    except Exception as exc:  # noqa: BLE001 - surfaced as a classified failure
        raise SchematronRuntimeError(layer.name, str(exc)) from exc

    doc = etree.fromstring(svrl.encode("utf-8"))
    out: list[SchematronViolation] = []
    for fa in doc.findall(".//svrl:failed-assert", namespaces=SVRL_NS):
        message = "".join(str(t) for t in fa.itertext()).strip() or "Schematron assertion failed"
        out.append(
            SchematronViolation(
                rule_id=_rule_id(fa, f"{layer.name}:unknown"),
                citation=f"PINT AE Schematron ({layer.name})",
                message=message,
                location=fa.get("location", ""),
                severity=_severity(fa, layer.default_severity),
            )
        )
    return out


def _to_text(xml_source: str | bytes) -> str:
    """Decode XML bytes to text, honouring UTF-16 and UTF-8 byte-order marks."""
    if isinstance(xml_source, str):
        return xml_source
    if xml_source.startswith((b"\xff\xfe", b"\xfe\xff")):
        return xml_source.decode("utf-16")
    if xml_source.startswith(b"\xef\xbb\xbf"):
        return xml_source.decode("utf-8-sig")
    return xml_source.decode("utf-8", "replace")


def validate_schematron(
    xml_source: str | bytes, include_peppol_bis3: bool = False
) -> list[SchematronViolation]:
    """Run the conformance layers against invoice XML.

    Default: the official PINT AE 1.0.4 layers (302 assertions, failures are
    errors). With ``include_peppol_bis3=True`` the legacy Peppol BIS 3.0 pair is
    added and reported as warnings.
    """
    xml_text = _to_text(xml_source)
    violations: list[SchematronViolation] = []
    for layer in layers_for_document(xml_text, include_peppol_bis3):
        violations.extend(_apply_layer(layer, xml_text))
    return violations


def schematron_assertion_count(include_peppol_bis3: bool = False) -> int:
    """Total <sch:assert> count across the active layers (for scope lines)."""
    total = 0
    for layer in active_layers(include_peppol_bis3):
        source = layer.sch.read_text(encoding="utf-8", errors="replace")
        total += len(re.findall(r"<[a-z:]*assert\b", source))
    return total


def assertion_counts(layers: tuple[Layer, ...] | None = None) -> dict[str, int]:
    """<sch:assert> count per layer, keyed by layer name (`rules` command)."""
    counts: dict[str, int] = {}
    for layer in layers if layers is not None else active_layers():
        source = layer.sch.read_text(encoding="utf-8", errors="replace")
        counts[layer.name] = len(re.findall(r"<[a-z:]*assert\b", source))
    return counts


def warm_up(layers: tuple[Layer, ...] | None = None) -> list[str]:
    """Load (compile if needed) every layer's stylesheet; return the layer names.

    Used by `pint-ae selftest` and useful before a demo: it moves the Saxon
    compilation cost out of the first invoice a client sees, and it proves the
    vendored artefacts are readable in this installation.
    """
    names: list[str] = []
    for layer in layers if layers is not None else active_layers():
        _executable_for(stylesheet_for(layer))
        names.append(layer.name)
    return names
