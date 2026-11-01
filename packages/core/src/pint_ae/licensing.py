"""Signed entitlements: which modules this installation may actually use.

The engine is published under BUSL-1.1, so production use requires a licence. This
module is the technical half of that: an Ed25519-signed ``pint-ae.lic`` names the
modules a customer may run, and the engine refuses the rest instead of pretending
they were not asked for.

What "refuse" means, precisely:

* a **free** installation runs the free module set and reports every other module as
  ``not licensed`` with its check count - it never shows those findings and never
  calls the result clean (same honesty rule as entitlements, decision A13);
* **explicitly asking** for a module it is not licensed for is a usage error
  (exit 3), not a silent filter;
* the engagement private commercial tooling refuses to build a client pack unless the licence covers
  the modules being packed - the deliverable is what is sold.

Honest limit, recorded rather than glossed: the source is published under BUSL, so a
determined user can patch it. Enforcement makes that an infringement rather than a
licence right; it is not a technical impossibility. That is why prices, tiers, owner
routing and the pack structure stay in the private commercial layer as well.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pint_ae.modules import MODULE_IDS

#: Modules a free evaluation installation may report. Deliberately enough to run the
#: synthetic demo end to end and see the report shape, not enough to deliver a paid
#: diagnostic for a client.
FREE_MODULES: tuple[str, ...] = ("core-conformance", "arithmetic", "emirate")

#: Ed25519 public key (raw, hex) that signs licences. The private key is held offline
#: by the licensor; rotating it means shipping a new release with a new key here.
#: `PINT_AE_LICENCE_PUBKEY` overrides it for tests and for a staged rotation.
PUBLIC_KEY_HEX = "835b28da743f37006419019e980b8426c58eff59f33d0fa372cb4cd865c01b9f"

#: Environments that make an installation fully licensed for development and CI.
DEV_ENVIRONMENTS = ("test", "ci")

LICENCE_ENV = "PINT_AE_LICENCE"
LICENCE_NAME = "pint-ae.lic"


@dataclass(frozen=True)
class Licence:
    """The effective licence state of this process."""

    state: str  # "free" | "licensed"
    modules: tuple[str, ...]
    customer: str | None = None
    expires: str | None = None
    reason: str = ""
    source: str | None = None

    @property
    def licensed(self) -> bool:
        return self.state == "licensed"

    def covers(self, module_id: str) -> bool:
        """True when this licence grants the module.

        A free licence is still a grant: it grants the free module set. ``licensed``
        is about the *kind* of grant (commercial or evaluation), not about whether the
        free modules work.
        """
        return module_id in self.modules

    def covers_all(self, module_ids: list[str] | tuple[str, ...]) -> bool:
        return set(module_ids) <= set(self.modules)

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "modules": list(self.modules),
            "customer": self.customer,
            "expires": self.expires,
            "reason": self.reason,
            "source": self.source,
        }


def _public_key() -> Ed25519PublicKey:
    raw = bytes.fromhex(os.environ.get("PINT_AE_LICENCE_PUBKEY") or PUBLIC_KEY_HEX)
    if len(raw) != 32:  # pragma: no cover - only a mistyped environment variable
        raise ValueError("PINT_AE_LICENCE_PUBKEY must be 32 bytes of hex")
    return Ed25519PublicKey.from_public_bytes(raw)


def _candidate_paths(explicit: Path | None) -> list[Path]:
    paths: list[Path] = []
    if explicit is not None:
        return [explicit]
    env = os.environ.get(LICENCE_ENV)
    if env:
        paths.append(Path(env))
    paths.append(Path.cwd() / LICENCE_NAME)
    paths.append(Path.home() / ".pint-ae" / LICENCE_NAME)
    return paths


def _signed_payload(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_licence(path: Path, *, now: float | None = None) -> Licence:
    """Read and verify one licence file. Never raises: an unusable file is 'free'."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Licence("free", FREE_MODULES, reason=f"unreadable licence: {exc}", source=str(path))
    if not isinstance(payload, dict) or "signature" not in payload:
        return Licence("free", FREE_MODULES, reason="licence has no signature", source=str(path))
    modules = tuple(sorted(payload.get("modules") or ()))
    unknown = sorted(set(modules) - set(MODULE_IDS))
    if unknown:
        return Licence(
            "free",
            FREE_MODULES,
            reason=f"licence names unknown modules {unknown}",
            source=str(path),
        )
    try:
        signature = base64.b64decode(payload["signature"], validate=True)
        _public_key().verify(signature, _signed_payload(payload))
    except InvalidSignature:
        return Licence(
            "free",
            FREE_MODULES,
            reason="signature does not match this licence (wrong key or altered content)",
            source=str(path),
        )
    except ValueError:
        return Licence(
            "free", FREE_MODULES, reason="licence signature is not valid base64", source=str(path)
        )
    expires = str(payload.get("expires") or "")
    if expires:
        try:
            expired = time.mktime(time.strptime(expires, "%Y-%m-%d")) < (now or time.time())
        except ValueError:
            expired = True
        if expired:
            return Licence(
                "free", FREE_MODULES, reason=f"licence expired on {expires}", source=str(path)
            )
    return Licence(
        "licensed",
        modules,
        customer=payload.get("customer"),
        expires=expires or None,
        source=str(path),
    )


_CACHE: dict[str, Licence] = {}


def current_licence(path: Path | None = None) -> Licence:
    """The licence in force for this process (cached per path)."""
    if os.environ.get("PINT_AE_LICENCE_BYPASS") in DEV_ENVIRONMENTS:
        return Licence(
            "licensed", tuple(sorted(MODULE_IDS)), customer="development", reason="bypass"
        )
    key = str(path) if path is not None else "<search>"
    if key not in _CACHE:
        licence = Licence("free", FREE_MODULES, reason="no licence file found")
        for candidate in _candidate_paths(path):
            if candidate.exists():
                licence = verify_licence(candidate)
                break
        _CACHE[key] = licence
    return _CACHE[key]


def reset_licence_cache() -> None:
    """Drop the cached licence (tests, and after writing a new one)."""
    _CACHE.clear()


def module_state(module_id: str, licence: Licence | None = None) -> str:
    """'licensed' | 'free' for reporting, per module."""
    active = licence or current_licence()
    return "licensed" if active.covers(module_id) else "free"
