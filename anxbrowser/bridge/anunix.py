"""Client for the Anunix HTTP API.

The bridge is intentionally defensive: Anunix may not be running on the host,
and the daemon must still be useful. When Anunix is unreachable the bridge
enters degraded mode, logs the condition, and retries in the background.

Anunix contract (per project docs):
  POST /api/v1/exec
  Body: { "command": "...", "args": [...] }

This is the single entry point for now. More specific endpoints (state,
tensor, cell) will be added as the Anunix API stabilizes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

log = logging.getLogger(__name__)


class BridgeStatus(str, Enum):
    DISABLED = "disabled"
    CONNECTED = "connected"
    DEGRADED = "degraded"


@dataclass
class BridgeResult:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AnunixBridge:
    """Minimal, dependency-free HTTP client for Anunix.

    Uses urllib + asyncio.to_thread so we don't drag in aiohttp for a handful
    of small POSTs.
    """

    def __init__(
        self,
        base_url: str,
        enabled: bool = True,
        timeout_s: float = 2.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._enabled = enabled
        self._timeout_s = timeout_s
        self._status = (
            BridgeStatus.DISABLED if not enabled else BridgeStatus.DEGRADED
        )
        self._last_error: Optional[str] = None
        self._last_ok_at: Optional[float] = None

    @property
    def status(self) -> BridgeStatus:
        return self._status

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def probe(self) -> bool:
        """Check whether Anunix is reachable. Updates status."""
        if not self._enabled:
            return False
        try:
            data = await asyncio.to_thread(
                self._post,
                "/api/v1/exec",
                {"command": "echo", "args": ["anxbrowser-probe"]},
            )
        except Exception as exc:
            self._status = BridgeStatus.DEGRADED
            self._last_error = str(exc)
            log.debug("anunix probe failed: %s", exc)
            return False
        self._status = BridgeStatus.CONNECTED
        self._last_ok_at = time.time()
        log.info("anunix bridge connected: %s", data)
        return True

    async def bind_session_to_cell(
        self, session_id: str, cell_id: Optional[str] = None
    ) -> BridgeResult:
        """Create or attach an Execution Cell for this browser session.

        If cell_id is None, Anunix mints a new Cell and returns its id.
        """
        cmd = {
            "command": "cell.create" if not cell_id else "cell.attach",
            "args": ["--kind=browser", f"--session={session_id}"]
            + ([f"--id={cell_id}"] if cell_id else []),
        }
        return await self._call(cmd)

    async def store_page_as_state_object(
        self,
        session_id: str,
        ns_path: str,
        url: str,
        title: str,
        html: str,
        screenshot_png: Optional[bytes] = None,
    ) -> BridgeResult:
        """Record a page view as a State Object under ns_path.

        Payload layout is intentionally simple for v0.1. When the Anunix state
        API gains a dedicated endpoint, this method will call it directly.
        """
        html_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        shot_hash = (
            hashlib.sha256(screenshot_png).hexdigest() if screenshot_png else None
        )
        payload = {
            "command": "state.put",
            "args": [
                f"--namespace={ns_path}",
                f"--session={session_id}",
                f"--url={url}",
                f"--title={title}",
                f"--html-sha256={html_hash}",
            ]
            + ([f"--screenshot-sha256={shot_hash}"] if shot_hash else []),
        }
        result = await self._call(payload)
        if result.ok:
            result.data = result.data or {}
            result.data.setdefault(
                "state_object",
                f"anx:state:sha256:{html_hash}",
            )
        return result

    async def record_action(
        self,
        session_id: str,
        action: str,
        details: Dict[str, Any],
    ) -> BridgeResult:
        """Create a provenance entry for an action."""
        return await self._call(
            {
                "command": "state.action",
                "args": [
                    f"--session={session_id}",
                    f"--action={action}",
                    f"--details={json.dumps(details, separators=(',', ':'))}",
                ],
            }
        )

    async def _call(self, cmd: Dict[str, Any]) -> BridgeResult:
        if not self._enabled:
            return BridgeResult(ok=False, error="bridge disabled")
        try:
            data = await asyncio.to_thread(self._post, "/api/v1/exec", cmd)
        except Exception as exc:
            self._status = BridgeStatus.DEGRADED
            self._last_error = str(exc)
            log.debug("anunix call failed: %s", exc)
            return BridgeResult(ok=False, error=str(exc))
        self._status = BridgeStatus.CONNECTED
        self._last_ok_at = time.time()
        return BridgeResult(ok=True, data=data)

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urlrequest.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read()
        except urlerror.URLError as exc:
            raise RuntimeError(f"anunix unreachable: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {"raw": raw.decode("utf-8", errors="replace")}
