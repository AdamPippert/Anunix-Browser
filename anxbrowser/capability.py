"""Capability token parsing and enforcement.

v0.1 accepts unsigned tokens for local development. Each request either carries
a token (Authorization: ANX-Capability <json-b64>) or, if `allow_unauthenticated`
is set in config, synthesizes a token granting all known verbs.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .protocol import KNOWN_VERBS


@dataclass(frozen=True)
class Capability:
    """An unverified capability token.

    Phase 1 will add a `signature` field and verification against the Anunix
    capability service. For now the daemon trusts the caller's claim.
    """

    actor: str
    session: Optional[str]
    cell: Optional[str]
    verbs: List[str] = field(default_factory=list)

    def allows(self, verb: str) -> bool:
        if "*" in self.verbs:
            return True
        return verb in self.verbs

    def as_dict(self) -> dict:
        return {
            "actor": self.actor,
            "session": self.session,
            "cell": self.cell,
            "verbs": list(self.verbs),
        }


def parse_header(header: Optional[str]) -> Optional[Capability]:
    """Parse an Authorization header in the ANX-Capability scheme.

    Returns None if the header is absent. Raises ValueError if present but
    malformed.
    """

    if not header:
        return None
    if not header.lower().startswith("anx-capability"):
        raise ValueError("unsupported auth scheme")
    _, _, payload = header.partition(" ")
    payload = payload.strip()
    if not payload:
        raise ValueError("empty capability payload")
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"capability payload is not valid b64 JSON: {exc}") from exc
    return Capability(
        actor=obj.get("actor", "unknown"),
        session=obj.get("session"),
        cell=obj.get("cell"),
        verbs=list(obj.get("verbs", [])),
    )


def synthetic(actor: str = "local:dev") -> Capability:
    """Return an all-verbs token for unauthenticated local use."""
    return Capability(actor=actor, session=None, cell=None, verbs=list(KNOWN_VERBS))


def require_verbs(cap: Capability, verbs: Iterable[str]) -> None:
    missing = [v for v in verbs if not cap.allows(v)]
    if missing:
        raise PermissionError(f"token does not include verbs: {missing}")
