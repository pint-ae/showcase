"""Configuration: one file that changes behaviour without touching code.

`pint-ae.toml` is how a client deployment differs from the default: which tax-group
TRNs are excluded, which modules are entitled, how strict the transmission window
is, whether a rule is downgraded, where output goes, whether the pack is anonymised.

Two decisions shape this module:

1. **The schema is public, the tiering is not.** This file describes mechanisms
   (modules, thresholds, severity, output). Which modules a client bought, and what
   that costs, is commercial and lives in the private layer (decisions A6/A9/A12).
2. **Unknown keys are errors.** A typo in a client's config must fail loudly at
   `pint-ae config validate`, not silently leave a tax-group exclusion switched off.

Entitlements never produce a false "clean": a disabled module is removed from the
findings *and reported as not entitled* with its check count (decision A13), so a
report can never imply it checked something it did not.
"""

from __future__ import annotations

import hashlib
import json
import tomllib  # Python 3.11 is the floor, so no fallback dependency is needed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from pint_ae.modules import MODULE_IDS

DEFAULT_FILENAME = "pint-ae.toml"

#: Severity values a rule may be overridden to. `error` is the default everywhere.
ALLOWED_SEVERITIES = ("error", "warning", "info")


class ConfigError(ValueError):
    """A configuration file that cannot be used, with a human explanation."""


class ModuleEntitlements(RootModel[dict[str, bool]]):
    """Which modules this deployment may report: ``[modules] parties = false``.

    Missing ids default to enabled, so a client file only names what they did *not*
    buy (or explicitly switch off).
    """

    root: dict[str, bool] = Field(default_factory=dict)

    def is_enabled(self, module_id: str) -> bool:
        return self.root.get(module_id, True)

    def disabled(self) -> list[str]:
        return sorted(module for module in MODULE_IDS if not self.is_enabled(module))


class Thresholds(BaseModel):
    """Numeric knobs the rules already use."""

    model_config = ConfigDict(extra="forbid")

    transmission_days: int = Field(default=14, ge=1, le=90)


class TaxGroup(BaseModel):
    """Intra-tax-group TRNs; both parties in the set are excluded from the system."""

    model_config = ConfigDict(extra="forbid")

    trns: list[str] = Field(default_factory=list)

    def normalised(self) -> set[str]:
        return {trn.strip() for trn in self.trns if trn.strip()}


class Output(BaseModel):
    """Defaults for reports and packs."""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(default="both", pattern=r"^(en|ar|both)$")
    anonymise: bool = True
    reports_dir: str = "reports"


class PintAeConfig(BaseModel):
    """The whole `pint-ae.toml` document."""

    model_config = ConfigDict(extra="forbid")

    reference_date: date | None = None
    modules: ModuleEntitlements = Field(default_factory=ModuleEntitlements)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    tax_group: TaxGroup = Field(default_factory=TaxGroup)
    severity: dict[str, str] = Field(default_factory=dict)
    output: Output = Field(default_factory=Output)

    # -- derived ----------------------------------------------------------
    def severity_for(self, rule_id: str, default: str) -> str:
        """Severity for a rule, honouring an explicit override."""
        return self.severity.get(rule_id, default)

    def normalised(self) -> dict[str, Any]:
        """A stable, JSON-safe view used for the config hash and provenance."""
        payload = self.model_dump(mode="json")
        payload["tax_group"]["trns"] = sorted(self.tax_group.normalised())
        payload["severity"] = dict(sorted(self.severity.items()))
        payload["modules"] = dict(sorted(self.modules.root.items()))
        return payload

    def sha256(self) -> str:
        """Hash of the effective configuration: same behaviour, same hash."""
        blob = json.dumps(self.normalised(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def disabled_modules(self) -> list[str]:
        return self.modules.disabled()


def default_config() -> PintAeConfig:
    """Every module enabled, no exclusions, default thresholds."""
    return PintAeConfig()


#: Where a deployment usually keeps its file, relative to the working directory.
def find_config(explicit: Path | None = None) -> Path | None:
    """Return the config path to use: explicit, else `./pint-ae.toml`, else none."""
    if explicit is not None:
        return explicit
    candidate = Path.cwd() / DEFAULT_FILENAME
    return candidate if candidate.exists() else None


def load_config(path: Path | None) -> PintAeConfig:
    """Load and validate a config file; no file means defaults."""
    if path is None:
        return default_config()
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - message passthrough
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc

    # Accept both a bare document and a [pint_ae] table, so a client can nest it
    # inside a larger tool config if that is their convention.
    table = raw.get("pint_ae", raw) if isinstance(raw, dict) else raw
    if not isinstance(table, dict):  # pragma: no cover - TOML guarantees a dict
        raise ConfigError(f"{path}: [pint_ae] must be a table")

    unknown = sorted(set(table) - set(PintAeConfig.model_fields))
    if unknown:
        raise ConfigError(
            f"{path}: unknown key(s) {unknown}; valid keys: {sorted(PintAeConfig.model_fields)}"
        )
    try:
        config = PintAeConfig.model_validate(table)
    except ValidationError as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    bad_rules = {rule for rule in config.severity if not rule}
    if bad_rules:  # pragma: no cover - an empty key is not expressible in TOML
        raise ConfigError(f"{path}: empty rule id in [severity]")
    for rule_id, severity in config.severity.items():
        if severity not in ALLOWED_SEVERITIES:
            raise ConfigError(
                f"{path}: [severity] {rule_id} = {severity!r}; allowed: {ALLOWED_SEVERITIES}"
            )
    unknown_modules = sorted(set(config.modules.root) - set(MODULE_IDS))
    if unknown_modules:
        raise ConfigError(
            f"{path}: [modules] unknown module(s) {unknown_modules}; valid: {sorted(MODULE_IDS)}"
        )
    for trn in config.tax_group.normalised():
        if not trn.isdigit() or len(trn) != 15:
            raise ConfigError(f"{path}: tax-group TRN {trn!r} must be 15 digits")
    return config


@dataclass
class AppliedConfig:
    """Config plus the effects it had, for provenance and for honest reporting."""

    config: PintAeConfig
    disabled_modules: list[str] = field(default_factory=list)

    @property
    def sha256(self) -> str:
        return self.config.sha256()

    def provenance(self) -> dict[str, Any]:
        return {
            "config_sha256": self.sha256,
            "entitlements": {
                "enabled": sorted(set(MODULE_IDS) - set(self.disabled_modules)),
                "not_entitled": self.disabled_modules,
            },
            "thresholds": self.config.thresholds.model_dump(mode="json"),
            "tax_group_trns": sorted(self.config.tax_group.normalised()),
            "severity_overrides": dict(sorted(self.config.severity.items())),
            "output": self.config.output.model_dump(mode="json"),
        }


def apply_config(config: PintAeConfig) -> AppliedConfig:
    """Push the config into the rule globals; no rule code changes needed."""
    from pint_ae import rules

    rules.set_vat_group(config.tax_group.normalised())
    rules.set_reference_date(config.reference_date)
    return AppliedConfig(config=config, disabled_modules=config.disabled_modules())


CONFIG_TEMPLATE = """# pint-ae.toml - client deployment configuration.
# Validate with: pint-ae config validate --config pint-ae.toml

[pint_ae]
# reference_date = "2026-11-20"   # fixes R-024/R-009 evaluation time; default: today

[modules]
# Disabled modules are reported as "not entitled", never as clean.
# core-conformance = true
# vat-categories = true
# parties = true
# arithmetic = true
# emirate = true
# payments = true
# currency = true
# transaction-type = true

[thresholds]
transmission_days = 14            # MD 197/2026 Art. 6(5)

[tax_group]
trns = []                         # 15-digit TRNs; both parties in the set are excluded

[severity]
# "R-024" = "warning"             # per-rule override; official assertions stay errors

[output]
language = "both"                 # en | ar | both
anonymise = true
reports_dir = "reports"
"""
