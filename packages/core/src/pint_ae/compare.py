"""Compare two diagnostic runs: what was fixed, what broke, what stayed.

A diagnostic is sold once; the *second* pack is the retainer. That second
conversation needs an answer to one question - "did the remediation work?" - and
that answer must be machine-generated from the two JSON result files, not
re-derived by hand.

The comparison is per **document id**, not per file name, because the second export
rarely reuses the first one's file names. Documents that appear only in one run are
reported as added/removed rather than as fixes.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CompareError(ValueError):
    """Raised when a result file cannot be used as the basis of a comparison."""


@dataclass
class DocumentChange:
    """Per-document delta between two runs."""

    document_id: str
    before: list[str]
    after: list[str]

    @property
    def fixed(self) -> list[str]:
        return sorted(set(self.before) - set(self.after))

    @property
    def introduced(self) -> list[str]:
        return sorted(set(self.after) - set(self.before))

    @property
    def remaining(self) -> list[str]:
        return sorted(set(self.after) & set(self.before))

    @property
    def changed(self) -> bool:
        return bool(self.fixed or self.introduced)


@dataclass
class Comparison:
    """A whole-run comparison, ready to print or serialise."""

    before_label: str
    after_label: str
    before_errors: int
    after_errors: int
    documents: list[DocumentChange] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def fixed(self) -> dict[str, int]:
        """Rule id -> number of documents that no longer raise it."""
        counts: Counter[str] = Counter()
        for change in self.documents:
            counts.update(change.fixed)
        return dict(sorted(counts.items()))

    @property
    def introduced(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for change in self.documents:
            counts.update(change.introduced)
        return dict(sorted(counts.items()))

    @property
    def remaining(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for change in self.documents:
            counts.update(change.remaining)
        return dict(sorted(counts.items()))

    @property
    def improved_documents(self) -> int:
        return sum(1 for change in self.documents if change.fixed and not change.introduced)

    @property
    def regressed_documents(self) -> int:
        return sum(1 for change in self.documents if change.introduced)

    @property
    def unchanged_documents(self) -> int:
        return sum(1 for change in self.documents if not change.changed)

    def summary(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "before": self.before_label,
            "after": self.after_label,
            "before_errors": self.before_errors,
            "after_errors": self.after_errors,
            "documents_compared": len(self.documents),
            "documents_improved": self.improved_documents,
            "documents_regressed": self.regressed_documents,
            "documents_unchanged": self.unchanged_documents,
            "added_documents": self.added,
            "removed_documents": self.removed,
            "fixed": self.fixed,
            "introduced": self.introduced,
            "remaining": self.remaining,
            "regressions": self.regressed_documents > 0,
        }
        return payload

    def lines(self) -> list[str]:
        """Human-readable report, most actionable first."""
        out = [
            f"Compared {self.before_label} -> {self.after_label}",
            f"  documents compared : {len(self.documents)}",
            f"  errors             : {self.before_errors} -> {self.after_errors}",
            f"  improved documents : {self.improved_documents}",
            f"  regressed documents: {self.regressed_documents}",
            f"  unchanged          : {self.unchanged_documents}",
        ]
        if self.added:
            out.append(f"  documents added    : {len(self.added)}")
        if self.removed:
            out.append(f"  documents removed  : {len(self.removed)}")
        if self.introduced:
            out.append("\nRegressions (present after, absent before):")
            for rule_id, count in sorted(self.introduced.items(), key=lambda item: -item[1]):
                affected = [c.document_id for c in self.documents if rule_id in c.introduced]
                out.append(
                    f"  {rule_id:<16} {count:>3} document(s)  e.g. {', '.join(affected[:3])}"
                )
        if self.fixed:
            out.append("\nFixed (present before, absent after):")
            for rule_id, count in sorted(self.fixed.items(), key=lambda item: -item[1]):
                out.append(f"  {rule_id:<16} {count:>3} document(s)")
        if self.remaining:
            out.append("\nStill failing:")
            for rule_id, count in sorted(self.remaining.items(), key=lambda item: -item[1]):
                out.append(f"  {rule_id:<16} {count:>3} document(s)")
        if not self.fixed and not self.introduced:
            out.append("\nNo change in findings between the two runs.")
        return out


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CompareError(f"result file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompareError(f"{path}: not valid JSON ({exc})") from exc
    if payload.get("header", {}).get("schema") != "pint-ae/results-v1":
        raise CompareError(
            f"{path}: not a pint-ae results file (schema "
            f"{payload.get('header', {}).get('schema')!r})"
        )
    return payload  # type: ignore[no-any-return]


def _rules_by_document(payload: dict[str, Any]) -> dict[str, list[str]]:
    """Document id -> sorted error rule ids (warnings excluded from remediation)."""
    documents: dict[str, list[str]] = {}
    for file_result in payload.get("files", []):
        document_id = file_result.get("document_id") or Path(file_result.get("source", "")).name
        rules = sorted(
            {
                finding["rule_id"]
                for finding in file_result.get("findings", [])
                if finding.get("severity") == "error"
            }
        )
        documents[document_id] = rules
    return documents


def compare_runs(before_path: Path, after_path: Path) -> Comparison:
    """Compare two `pint-ae diagnose --json` results."""
    before = _load(before_path)
    after = _load(after_path)
    before_docs = _rules_by_document(before)
    after_docs = _rules_by_document(after)

    changes = [
        DocumentChange(document_id, before_docs[document_id], after_docs[document_id])
        for document_id in sorted(set(before_docs) & set(after_docs))
    ]
    return Comparison(
        before_label=f"{before_path.name} ({before['header'].get('finished', '?')})",
        after_label=f"{after_path.name} ({after['header'].get('finished', '?')})",
        before_errors=int(before.get("summary", {}).get("errors", 0)),
        after_errors=int(after.get("summary", {}).get("errors", 0)),
        documents=changes,
        added=sorted(set(after_docs) - set(before_docs)),
        removed=sorted(set(before_docs) - set(after_docs)),
    )
