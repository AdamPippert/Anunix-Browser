"""Runtime configuration for anxbrowserd.

All configuration flows through environment variables so the daemon is trivial
to run under systemd, launchd, or an Anunix Execution Cell.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Daemon configuration."""

    host: str
    port: int
    anunix_base_url: str
    anunix_enabled: bool
    headless_default: bool
    allow_unauthenticated: bool
    static_dir: str
    default_namespace: str

    @classmethod
    def from_env(cls) -> "Config":
        here = os.path.dirname(os.path.abspath(__file__))
        web_dir = os.path.abspath(os.path.join(here, "..", "web"))
        return cls(
            host=os.environ.get("ANXB_HOST", "127.0.0.1"),
            port=int(os.environ.get("ANXB_PORT", "9090")),
            anunix_base_url=os.environ.get("ANXB_ANUNIX_URL", "http://127.0.0.1:8080"),
            anunix_enabled=_truthy(os.environ.get("ANXB_ANUNIX", "auto")),
            headless_default=_truthy(os.environ.get("ANXB_HEADLESS", "true")),
            allow_unauthenticated=_truthy(
                os.environ.get("ANXB_ALLOW_UNAUTH", "true")
            ),
            static_dir=os.environ.get("ANXB_WEB_DIR", web_dir),
            default_namespace=os.environ.get("ANXB_NAMESPACE", "/sessions"),
        )


def _truthy(val: str) -> bool:
    if val is None:
        return False
    return val.lower() in ("1", "true", "yes", "on", "auto")
