"""Which module owns which check.

The 302 official PINT AE assertions and the 24 local rules are grouped into eight
**modules**, so a client can be told not just "326 checks" but *which* of them
relate to party master data, emirate mapping, VAT categories and so on. Module
ids are a public, stable identifier: the private commercial tooling and the
entitlement switch (milestones M3 and M4) reference them, so renaming one is a
breaking change.

How the official table was built
--------------------------------
The assertion texts and ids were extracted from the vendored `.sch` files and
classified with the ordered decision table below (first match wins), then the
result was reviewed and corrected where a keyword would have misled. The two
mechanical rules are stated here so the table can be re-reviewed:

1. Postal-address vocabulary (`postal address`, `address line`,
   `country subdivision`, `city`, `street`) goes to ``emirate``; the electronic
   address and endpoint vocabulary goes to ``parties``.
2. Anything an amount has to reconcile (`MUST equal`, `sum of`, totals, rounding,
   decimals) goes to ``arithmetic`` - except the VAT category rules, which are
   matched earlier because they are about tax treatment rather than arithmetic.

Ambiguity is resolved by what a client would buy: if the finding is fixed by
cleaning the buyer master, it is ``parties``; if it is fixed by choosing the right
VAT category, it is ``vat-categories``.

**No commercial content lives here.** The public package states ownership, never
money or buyer personas; the module-to-service mapping and the fees belong to the
private commercial layer by decision A6/A9.

The completeness test (``tests/test_modules.py``) fails when the artefact gains an
assertion that this table does not own, so a rule-set update is a reviewed change
rather than a silent gap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Module:
    """A named group of checks with a client-facing title."""

    id: str
    title: str
    description: str


MODULES: tuple[Module, ...] = (
    Module(
        "core-conformance",
        "PINT AE conformance core",
        "Mandatory fields, document structure, code lists and cardinality from the official PINT AE 1.0.4 artefact, plus the UBL 2.1 schema.",
    ),
    Module(
        "arithmetic",
        "Amounts and arithmetic",
        "Line and document totals, VAT breakdown sums, allowances and charges, rounding and decimal places.",
    ),
    Module(
        "parties",
        "Party master data",
        "Seller and buyer identifiers: VAT numbers (TRN/TIN), legal registration, electronic addresses and endpoint schemes.",
    ),
    Module(
        "emirate",
        "Address and emirate mapping",
        "Postal addresses and the UAE country-subdivision (emirate) codes the authority expects on every address that says AE.",
    ),
    Module(
        "transaction-type",
        "Transaction type coding",
        "The BTAE-002 transaction-type flags and the profile execution identifier.",
    ),
    Module(
        "currency",
        "Currency and AED accounting",
        "Invoice and tax accounting currency codes, exchange rates and the AED amounts the tax accounting requires.",
    ),
    Module(
        "vat-categories",
        "VAT category logic",
        "Standard, zero-rated, exempt, reverse-charge and free-zone category handling: category codes, rates, exemption reasons and their amounts.",
    ),
    Module(
        "payments",
        "Payment means and terms",
        "Payment means, due dates, payment terms, IBAN and payee details.",
    ),
)

MODULE_IDS: frozenset[str] = frozenset(module.id for module in MODULES)

CORE = "core-conformance"

#: Official assertion id -> module id (302 entries, reviewed).
ASSERTION_MODULES: dict[str, str] = {
    "aligned-ibrp-001-ae": "core-conformance",
    "aligned-ibrp-002-ae": "core-conformance",
    "aligned-ibrp-004": "arithmetic",
    "aligned-ibrp-032": "vat-categories",
    "aligned-ibrp-037": "vat-categories",
    "aligned-ibrp-045": "vat-categories",
    "aligned-ibrp-046": "vat-categories",
    "aligned-ibrp-047": "vat-categories",
    "aligned-ibrp-048": "vat-categories",
    "aligned-ibrp-057": "core-conformance",
    "aligned-ibrp-058": "core-conformance",
    "aligned-ibrp-ae-01-ae": "vat-categories",
    "aligned-ibrp-ae-05-ae": "vat-categories",
    "aligned-ibrp-ae-06": "vat-categories",
    "aligned-ibrp-ae-07": "vat-categories",
    "aligned-ibrp-ae-08-ae": "vat-categories",
    "aligned-ibrp-ae-09-ae": "vat-categories",
    "aligned-ibrp-e-01": "vat-categories",
    "aligned-ibrp-e-05": "vat-categories",
    "aligned-ibrp-e-06": "vat-categories",
    "aligned-ibrp-e-07": "vat-categories",
    "aligned-ibrp-e-08": "vat-categories",
    "aligned-ibrp-e-09": "vat-categories",
    "aligned-ibrp-o-01": "vat-categories",
    "aligned-ibrp-o-05": "vat-categories",
    "aligned-ibrp-o-06": "vat-categories",
    "aligned-ibrp-o-07": "vat-categories",
    "aligned-ibrp-o-08": "vat-categories",
    "aligned-ibrp-o-09": "vat-categories",
    "aligned-ibrp-o-11-ae": "vat-categories",
    "aligned-ibrp-s-01": "vat-categories",
    "aligned-ibrp-s-05": "vat-categories",
    "aligned-ibrp-s-06": "vat-categories",
    "aligned-ibrp-s-07": "vat-categories",
    "aligned-ibrp-s-08": "vat-categories",
    "aligned-ibrp-s-09": "vat-categories",
    "aligned-ibrp-s-10": "vat-categories",
    "aligned-ibrp-sr-12": "core-conformance",
    "aligned-ibrp-z-01": "vat-categories",
    "aligned-ibrp-z-05": "vat-categories",
    "aligned-ibrp-z-06": "vat-categories",
    "aligned-ibrp-z-07": "vat-categories",
    "aligned-ibrp-z-08": "vat-categories",
    "aligned-ibrp-z-09": "vat-categories",
    "ibr-001": "core-conformance",
    "ibr-001-ae": "core-conformance",
    "ibr-002": "core-conformance",
    "ibr-002-ae": "currency",
    "ibr-003": "core-conformance",
    "ibr-004": "core-conformance",
    "ibr-005": "currency",
    "ibr-005-ae": "core-conformance",
    "ibr-006": "parties",
    "ibr-006-ae": "vat-categories",
    "ibr-007": "parties",
    "ibr-007-ae": "transaction-type",
    "ibr-008": "emirate",
    "ibr-009": "emirate",
    "ibr-010": "emirate",
    "ibr-010-ae": "parties",
    "ibr-011": "emirate",
    "ibr-011-ae": "core-conformance",
    "ibr-012": "arithmetic",
    "ibr-012-ae": "parties",
    "ibr-013": "arithmetic",
    "ibr-013-ae": "core-conformance",
    "ibr-014": "arithmetic",
    "ibr-015": "arithmetic",
    "ibr-016": "core-conformance",
    "ibr-017": "payments",
    "ibr-018": "parties",
    "ibr-019": "emirate",
    "ibr-020": "emirate",
    "ibr-021": "core-conformance",
    "ibr-022": "core-conformance",
    "ibr-023": "core-conformance",
    "ibr-024": "core-conformance",
    "ibr-025": "core-conformance",
    "ibr-026": "core-conformance",
    "ibr-027": "core-conformance",
    "ibr-028": "core-conformance",
    "ibr-029": "core-conformance",
    "ibr-030": "core-conformance",
    "ibr-031": "core-conformance",
    "ibr-033": "core-conformance",
    "ibr-036": "core-conformance",
    "ibr-038": "core-conformance",
    "ibr-041": "core-conformance",
    "ibr-042": "core-conformance",
    "ibr-043": "core-conformance",
    "ibr-044": "core-conformance",
    "ibr-049": "payments",
    "ibr-052": "core-conformance",
    "ibr-053": "currency",
    "ibr-054": "core-conformance",
    "ibr-055": "core-conformance",
    "ibr-055-ae": "core-conformance",
    "ibr-056": "parties",
    "ibr-057": "core-conformance",
    "ibr-062": "parties",
    "ibr-063": "parties",
    "ibr-064": "parties",
    "ibr-065": "parties",
    "ibr-066": "payments",
    "ibr-067": "payments",
    "ibr-068": "parties",
    "ibr-069": "parties",
    "ibr-070": "parties",
    "ibr-071": "core-conformance",
    "ibr-072": "core-conformance",
    "ibr-073": "core-conformance",
    "ibr-074": "core-conformance",
    "ibr-075": "core-conformance",
    "ibr-076": "core-conformance",
    "ibr-077": "currency",
    "ibr-078": "core-conformance",
    "ibr-079": "core-conformance",
    "ibr-080": "parties",
    "ibr-081": "parties",
    "ibr-082": "core-conformance",
    "ibr-083": "core-conformance",
    "ibr-084": "currency",
    "ibr-085": "core-conformance",
    "ibr-086": "core-conformance",
    "ibr-087": "core-conformance",
    "ibr-088": "core-conformance",
    "ibr-089": "core-conformance",
    "ibr-090": "core-conformance",
    "ibr-091": "arithmetic",
    "ibr-092": "core-conformance",
    "ibr-093": "payments",
    "ibr-094": "core-conformance",
    "ibr-095": "core-conformance",
    "ibr-096": "core-conformance",
    "ibr-097": "core-conformance",
    "ibr-098": "parties",
    "ibr-099": "parties",
    "ibr-100": "parties",
    "ibr-101": "core-conformance",
    "ibr-101-ae": "parties",
    "ibr-102": "parties",
    "ibr-102-ae": "vat-categories",
    "ibr-103": "parties",
    "ibr-103-ae": "vat-categories",
    "ibr-104": "parties",
    "ibr-104-ae": "arithmetic",
    "ibr-105": "payments",
    "ibr-105-ae": "vat-categories",
    "ibr-106": "payments",
    "ibr-107": "core-conformance",
    "ibr-108": "parties",
    "ibr-108-ae": "vat-categories",
    "ibr-109": "core-conformance",
    "ibr-110": "core-conformance",
    "ibr-111": "core-conformance",
    "ibr-111-ae": "vat-categories",
    "ibr-112": "parties",
    "ibr-113": "parties",
    "ibr-114": "parties",
    "ibr-114-ae": "vat-categories",
    "ibr-115": "parties",
    "ibr-115-ae": "vat-categories",
    "ibr-116": "parties",
    "ibr-116-ae": "transaction-type",
    "ibr-119": "core-conformance",
    "ibr-119-ae": "vat-categories",
    "ibr-120": "parties",
    "ibr-120-ae": "vat-categories",
    "ibr-121": "arithmetic",
    "ibr-121-ae": "vat-categories",
    "ibr-122": "arithmetic",
    "ibr-122-ae": "vat-categories",
    "ibr-123": "arithmetic",
    "ibr-123-ae": "core-conformance",
    "ibr-124": "arithmetic",
    "ibr-124-ae": "core-conformance",
    "ibr-125": "arithmetic",
    "ibr-125-ae": "core-conformance",
    "ibr-126": "currency",
    "ibr-126-ae": "arithmetic",
    "ibr-127": "parties",
    "ibr-127-ae": "payments",
    "ibr-128-ae": "emirate",
    "ibr-131-ae": "arithmetic",
    "ibr-132-ae": "parties",
    "ibr-133-ae": "core-conformance",
    "ibr-134-ae": "parties",
    "ibr-135-ae": "parties",
    "ibr-136-ae": "parties",
    "ibr-137-ae": "transaction-type",
    "ibr-138-ae": "transaction-type",
    "ibr-139-ae": "vat-categories",
    "ibr-140-ae": "currency",
    "ibr-141-ae": "core-conformance",
    "ibr-142-ae": "emirate",
    "ibr-143-ae": "emirate",
    "ibr-144-ae": "emirate",
    "ibr-145-ae": "vat-categories",
    "ibr-146-ae": "arithmetic",
    "ibr-147-ae": "arithmetic",
    "ibr-148-ae": "core-conformance",
    "ibr-149-ae": "parties",
    "ibr-150-ae": "parties",
    "ibr-151-ae": "vat-categories",
    "ibr-152-ae": "emirate",
    "ibr-153-ae": "currency",
    "ibr-154-ae": "transaction-type",
    "ibr-157-ae": "transaction-type",
    "ibr-158-ae": "core-conformance",
    "ibr-159-ae": "currency",
    "ibr-160-ae": "core-conformance",
    "ibr-162-ae": "vat-categories",
    "ibr-163-ae": "vat-categories",
    "ibr-165-ae": "vat-categories",
    "ibr-166-ae": "vat-categories",
    "ibr-167-ae": "vat-categories",
    "ibr-168-ae": "vat-categories",
    "ibr-169-ae": "vat-categories",
    "ibr-172-ae": "parties",
    "ibr-173-ae": "parties",
    "ibr-174-ae": "vat-categories",
    "ibr-175-ae": "currency",
    "ibr-176-ae": "parties",
    "ibr-177-ae": "parties",
    "ibr-178-ae": "core-conformance",
    "ibr-179-ae": "parties",
    "ibr-180-ae": "parties",
    "ibr-181-ae": "parties",
    "ibr-183-ae": "parties",
    "ibr-184-ae": "core-conformance",
    "ibr-185-ae": "core-conformance",
    "ibr-186-ae": "core-conformance",
    "ibr-187-ae": "core-conformance",
    "ibr-188-ae": "parties",
    "ibr-189-ae": "parties",
    "ibr-190-ae": "vat-categories",
    "ibr-191-ae": "payments",
    "ibr-192-ae": "payments",
    "ibr-193-ae": "core-conformance",
    "ibr-194-ae": "arithmetic",
    "ibr-196-ae": "core-conformance",
    "ibr-cl-01": "core-conformance",
    "ibr-cl-03": "currency",
    "ibr-cl-04": "currency",
    "ibr-cl-05": "currency",
    "ibr-cl-07": "core-conformance",
    "ibr-cl-10": "core-conformance",
    "ibr-cl-11": "core-conformance",
    "ibr-cl-13": "core-conformance",
    "ibr-cl-14": "core-conformance",
    "ibr-cl-15": "core-conformance",
    "ibr-cl-16": "payments",
    "ibr-cl-19": "core-conformance",
    "ibr-cl-20": "core-conformance",
    "ibr-cl-21": "parties",
    "ibr-cl-23": "core-conformance",
    "ibr-cl-24": "core-conformance",
    "ibr-cl-25": "parties",
    "ibr-cl-26": "parties",
    "ibr-co-10": "arithmetic",
    "ibr-co-11": "arithmetic",
    "ibr-co-12": "arithmetic",
    "ibr-co-13": "arithmetic",
    "ibr-co-14": "arithmetic",
    "ibr-co-15": "arithmetic",
    "ibr-co-16": "payments",
    "ibr-co-19": "core-conformance",
    "ibr-co-20": "core-conformance",
    "ibr-co-26": "parties",
    "ibr-sr-05": "payments",
    "ibr-sr-06": "core-conformance",
    "ibr-sr-07": "core-conformance",
    "ibr-sr-16": "parties",
    "ibr-sr-19": "payments",
    "ibr-sr-22": "parties",
    "ibr-sr-23": "parties",
    "ibr-sr-27": "payments",
    "ibr-sr-28": "core-conformance",
    "ibr-sr-30": "core-conformance",
    "ibr-sr-31": "core-conformance",
    "ibr-sr-32": "vat-categories",
    "ibr-sr-33": "core-conformance",
    "ibr-sr-34": "core-conformance",
    "ibr-sr-38": "vat-categories",
    "ibr-sr-39": "core-conformance",
    "ibr-sr-42": "core-conformance",
    "ibr-sr-46": "payments",
    "ibr-sr-49": "core-conformance",
    "ibr-sr-50": "core-conformance",
    "ibr-sr-51": "core-conformance",
    "ibr-sr-52": "core-conformance",
    "ibr-sr-53": "emirate",
    "ibr-sr-54": "emirate",
    "ibr-sr-55": "emirate",
    "ibr-sr-56": "emirate",
    "ibr-sr-57": "core-conformance",
    "ibr-sr-58": "core-conformance",
    "ibr-sr-59": "emirate",
    "ibr-sr-60": "payments",
    "ibr-sr-61": "vat-categories",
    "ibr-sr-62": "core-conformance",
    "ibr-sr-63": "core-conformance",
}

#: Local rule id -> module id (24 entries).
RULE_MODULES: dict[str, str] = {
    "R-001": "arithmetic",
    "R-002": "arithmetic",
    "R-003": "arithmetic",
    "R-004": "arithmetic",
    "R-005": "vat-categories",
    "R-006": "core-conformance",
    "R-007": "core-conformance",
    "R-008": "currency",
    "R-009": "core-conformance",
    "R-010": "parties",
    "R-011": "parties",
    "R-012": "parties",
    "R-013": "core-conformance",
    "R-014": "core-conformance",
    "R-015": "core-conformance",
    "R-016": "arithmetic",
    "R-017": "arithmetic",
    "R-018": "arithmetic",
    "R-019": "vat-categories",
    "R-020": "core-conformance",
    "R-021": "emirate",
    "R-022": "parties",
    "R-024": "core-conformance",
    "R-025": "core-conformance",
}

#: Assertions deliberately left unowned, with the reason. Expected empty:
#: an exclusion is a decision, never a silent gap.
EXCLUDED_ASSERTIONS: dict[str, str] = {}


def module_of(rule_id: str, layer: str) -> str:
    """Return the module that owns a finding, from its id and layer."""
    if layer == "local":
        return RULE_MODULES.get(rule_id, CORE)
    return ASSERTION_MODULES.get(rule_id, CORE)


def checks_per_module() -> dict[str, int]:
    """Number of checks each module owns, in a stable order."""
    counts: dict[str, int] = {module.id: 0 for module in MODULES}
    for module_id in (*ASSERTION_MODULES.values(), *RULE_MODULES.values()):
        counts[module_id] = counts.get(module_id, 0) + 1
    return counts


def resolve_selection(names: list[str]) -> list[str]:
    """Expand a --modules selection, raising ValueError for unknown ids."""
    selected: list[str] = []
    for raw in names:
        for name in raw.split(","):
            candidate = name.strip().lower()
            if not candidate:
                continue
            if candidate == "all":
                return [module.id for module in MODULES]
            if candidate not in MODULE_IDS:
                valid = ", ".join(module.id for module in MODULES)
                raise ValueError(f"unknown module {candidate!r}; valid: {valid}")
            if candidate not in selected:
                selected.append(candidate)
    if not selected:
        raise ValueError("no module selected")
    return selected
