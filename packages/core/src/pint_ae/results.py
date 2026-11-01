"""Result model, ordering, de-duplication, module ownership and the JSON contract.

The JSON document produced here is the product's machine-readable output: the
packager (M3), CI and any client integration consume it instead of scraping
console text. It carries its own provenance so a report can be tied to the exact
rule set and regulation snapshot that produced it.

Every finding also names the **module** that owns it (`pint_ae.modules`), which is
what makes a report answer "which part of my setup is wrong" rather than only
"something is wrong". The field is additive: `pint-ae/results-v1` consumers that
ignore unknown fields keep working.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from pint_ae.config import PintAeConfig
from pint_ae.modules import checks_per_module, module_of
from pint_ae.regulatory import provenance
from pint_ae.rules import RuleViolation

SCHEMA_ID = "pint-ae/results-v1"

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}

#: Local rule -> official assertion(s) covering the same defect. When both fire
#: for the same document the official finding is kept and the local one is
#: recorded as suppressed, so a single defect is not reported three times and the
#: official rule stays the source of truth.
OVERLAP_MAP: dict[str, tuple[str, ...]] = {
    "R-001": ("ibr-co-10",),
    "R-002": ("ibr-co-13",),
    "R-003": ("ibr-co-16",),
    "R-004": ("ibr-co-15",),
    "R-005": ("ibr-190-ae",),
    "R-007": ("ibr-cl-01",),
    "R-016": ("ibr-147-ae",),
    "R-018": ("aligned-ibrp-s-09", "aligned-ibrp-z-09"),
    "R-020": ("aligned-ibrp-001-ae",),
    "R-021": ("ibr-128-ae",),
    "R-022": ("ibr-132-ae", "ibr-148-ae", "ibr-135-ae"),
}

_PREDICATE = re.compile(r"\[[^\]]*\]")


def layer_of(citation: str) -> str:
    """Derive the rule layer from the citation string."""
    if citation.startswith("UBL 2.1 XSD"):
        return "xsd"
    if "Schematron (shared 1.0.4)" in citation:
        return "official-shared"
    if "Schematron (jurisdiction 1.0.4)" in citation:
        return "official-jurisdiction"
    if "Schematron (" in citation:
        return "legacy-peppol-bis3"
    return "local"


def human_location(location: str, field: str) -> str:
    """Turn an SVRL XPath into 'Party › EndpointID'-style text.

    Raw XPaths are unreadable in a client report; the last three meaningful
    segments are enough to tell an ERP team where to look.
    """
    if location:
        segments: list[str] = []
        for raw in _PREDICATE.sub("", location).split("/"):
            segment = raw.strip().lstrip("*").split(":")[-1]
            if not segment or segment in {"Invoice", "CreditNote"}:
                continue
            segments.append(segment)
        if segments:
            return " › ".join(segments[-3:])
    return field or "document"


@dataclass
class Finding:
    """A single client-facing finding."""

    rule_id: str
    severity: str
    layer: str
    module: str
    field: str
    location: str
    message: str
    citation: str


def make_finding(violation: RuleViolation, config: PintAeConfig | None = None) -> Finding:
    """Turn a rule violation into a finding, honouring a configured severity override."""
    layer = layer_of(violation.citation)
    severity = (
        config.severity_for(violation.rule_id, violation.severity) if config else violation.severity
    )
    return Finding(
        rule_id=violation.rule_id,
        severity=severity,
        layer=layer,
        module=module_of(violation.rule_id, layer),
        field=violation.field,
        location=human_location(violation.field, violation.field),
        message=violation.message,
        citation=violation.citation,
    )


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_RANK.get(f.severity, 9), f.rule_id, f.location, f.message),
    )


def dedupe(findings: list[Finding]) -> tuple[list[Finding], list[dict[str, str]]]:
    """Keep the official finding, record the local duplicate as suppressed."""
    present = {f.rule_id for f in findings}
    kept: list[Finding] = []
    suppressed: list[dict[str, str]] = []
    for finding in findings:
        counterpart = next((c for c in OVERLAP_MAP.get(finding.rule_id, ()) if c in present), None)
        if counterpart is not None:
            suppressed.append(
                {
                    "rule_id": finding.rule_id,
                    "layer": finding.layer,
                    "module": finding.module,
                    "field": finding.field,
                    "reason": f"duplicate of {counterpart}",
                }
            )
        else:
            kept.append(finding)
    return kept, suppressed


def filter_modules(findings: list[Finding], selected: list[str] | None) -> list[Finding]:
    """Keep only the findings owned by the selected modules (``None`` keeps all)."""
    if selected is None:
        return findings
    wanted = set(selected)
    return [finding for finding in findings if finding.module in wanted]


def filter_not_entitled(findings: list[Finding], not_entitled: list[str]) -> list[Finding]:
    """Drop findings from modules this deployment is not entitled to report.

    The caller must *say* the modules were skipped (decision A13): a disabled
    module is never allowed to look clean.
    """
    if not not_entitled:
        return findings
    skipped = set(not_entitled)
    return [finding for finding in findings if finding.module not in skipped]


@dataclass
class FileResult:
    """One input file, its classification and findings."""

    source: str
    classification: str
    detail: str = ""
    sha256: str = ""
    size: int = 0
    document_id: str = ""
    document_type: str = "unknown"
    scope: str = "unknown"
    scope_reason: str = ""
    findings: list[Finding] = field(default_factory=list)
    suppressed: list[dict[str, str]] = field(default_factory=list)
    elapsed_ms: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")


@dataclass
class RunResult:
    """A whole run: header, per-file results, summary."""

    files: list[FileResult] = field(default_factory=list)
    started: str = ""
    finished: str = ""
    environment: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        by_classification = Counter(f.classification for f in self.files)
        clean = sum(1 for f in self.files if f.classification == "accepted" and not f.findings)
        with_errors = sum(1 for f in self.files if f.error_count)
        with_warnings = sum(1 for f in self.files if f.warning_count and not f.error_count)
        suppressed = sum(len(f.suppressed) for f in self.files)
        return {
            "total": len(self.files),
            "clean": clean,
            "with_errors": with_errors,
            "with_warnings": with_warnings,
            "excluded": sum(1 for f in self.files if f.scope == "excluded-tax-group"),
            "failed": sum(1 for f in self.files if f.classification != "accepted"),
            "errors": sum(f.error_count for f in self.files),
            "warnings": sum(f.warning_count for f in self.files),
            "suppressed": suppressed,
            "by_classification": dict(sorted(by_classification.items())),
            "modules": self.module_summary(),
            "not_entitled": list(
                self.extra.get("config", {}).get("entitlements", {}).get("not_entitled", [])
            ),
        }

    def module_summary(self) -> dict[str, dict[str, int]]:
        """Checks evaluated and findings raised per module, in a stable order."""
        counts = checks_per_module()
        raised: Counter[str] = Counter()
        errors: Counter[str] = Counter()
        for file in self.files:
            for finding in file.findings:
                raised[finding.module] += 1
                if finding.severity == "error":
                    errors[finding.module] += 1
        return {
            module_id: {
                "checks": checks,
                "findings": raised.get(module_id, 0),
                "errors": errors.get(module_id, 0),
            }
            for module_id, checks in counts.items()
        }

    def to_dict(self) -> dict[str, Any]:
        header = {
            "schema": SCHEMA_ID,
            **provenance(),
            "started": self.started,
            "finished": self.finished,
            "environment": self.environment,
            **self.extra,
        }
        return {
            "header": header,
            "files": [
                {
                    **asdict(f),
                    "findings": [asdict(x) for x in f.findings],
                }
                for f in self.files
            ],
            "summary": self.summary(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
