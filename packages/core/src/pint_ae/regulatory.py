"""Regulatory and specification metadata that every output must carry.

The tool validates against a *pinned* version of the standard and a *snapshot*
of the regulations in force. Both must appear in any artefact a client can see,
so a report can always be tied to the rules that produced it.

Sources and hashes: `docs/sources/regulatory-register.md`.
"""

from __future__ import annotations

from functools import cache
from hashlib import sha256
from pathlib import Path

#: The technical specification the rule set comes from.
SPEC_VERSION = "PINT AE Billing 1.0.4"
SPEC_RELEASED = "2026-06-02"
PINT_GENERAL_VERSION = "1.1.3"

#: Date on which the regulatory position below was verified against primary sources.
REGULATION_SNAPSHOT = "2026-11-01"

#: Instruments in force at the snapshot date, as they affect the product.
RULES_IN_FORCE = (
    "Ministerial Decision 243/2025 - Electronic Invoicing System (scope, obligations)",
    "Ministerial Decision 244/2025 + 66/2026 - phased implementation and ASP deadlines",
    "Cabinet Decision 106/2025 - violations and administrative penalties",
    "Ministerial Decision 197/2026 (in force 2026-10-01) - exclusions, 14-business-day "
    "transmission, storage/retention wording, repeal of Article 12",
    "FTA Decision 4/2026 (in force 2026-07-30) - records accessible to the FTA on request",
)

_VENDOR_DIR = Path(__file__).parent / "schematron" / "vendor" / "pint-ae-1.0.4"
_RULE_SET_FILES = ("shared.sch", "jurisdiction.sch")

#: Pinned SHA-256 over the two vendored official rule files. `pint-ae selftest`
#: compares against it: if an artefact is swapped or edited, the installation
#: reports itself as not intact instead of silently validating against a different
#: rule set. Updating the artefacts means deliberately updating this constant.
EXPECTED_RULE_SET_SHA256 = "faa4ca8007abe0d5fa2dfef72d511bdb51eb6b97b601c8a42df6e050ac80d583"


@cache
def rule_set_sha256() -> str:
    """SHA-256 over the vendored official rule files, in a fixed order."""
    digest = sha256()
    for name in _RULE_SET_FILES:
        digest.update((_VENDOR_DIR / name).read_bytes())
    return digest.hexdigest()


def provenance() -> dict[str, str]:
    """Provenance block for reports, packs and JSON output."""
    return {
        "tool": "pint-ae-toolkit",
        "spec_version": SPEC_VERSION,
        "spec_released": SPEC_RELEASED,
        "pint_general_version": PINT_GENERAL_VERSION,
        "rule_set_sha256": rule_set_sha256(),
        "regulation_snapshot": REGULATION_SNAPSHOT,
    }
