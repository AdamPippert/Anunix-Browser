"""Client for the Anunix HTTP API.

The bridge is intentionally defensive: Anunix may not be running on the host,
and the daemon must still be useful. When Anunix is unreachable the bridge
enters degraded mode, logs the condition, and retries in the background.

Anunix contract (verified against live kernel):
  POST /api/v1/exec
  Body: { "command": "sysinfo" }                  # single shell command string
  Response: { "status": "ok", "output": "..." }   # captured stdout

  GET /api/v1/health -> { "status": "healthy" }

Commands follow ansh syntax:
  - Object: write, cat, ls, inspect, rm, cp, mv
  - Tensor: tensor create|info|stats|fill|slice|diff|quantize|search|...
  - Model:  model info|layers|diff|import
  - Cell:   cell create <name>, cells, cell run <cid>
  - Network: dns, ping, http-get, fetch
  - System: sysinfo, mem stats, netinfo

This is the single entry point for now. More specific endpoints (binary
tensor upload, streaming, etc.) will be added as the Anunix API grows.
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
        """Check whether Anunix is reachable. Uses /api/v1/health."""
        if not self._enabled:
            return False
        try:
            data = await asyncio.to_thread(self._get, "/api/v1/health")
        except Exception as exc:
            self._status = BridgeStatus.DEGRADED
            self._last_error = str(exc)
            log.debug("anunix probe failed: %s", exc)
            return False
        self._status = BridgeStatus.CONNECTED
        self._last_ok_at = time.time()
        log.info("anunix bridge connected: %s", data)
        return True

    async def exec(self, command: str) -> BridgeResult:
        """Run a single ansh command string."""
        return await self._call(command)

    async def bind_session_to_cell(
        self, session_id: str, cell_id: Optional[str] = None
    ) -> BridgeResult:
        """Create or attach an Execution Cell for this browser session."""
        # Sanitise session_id: ansh cell names must not contain spaces.
        name = f"browser-{session_id[:8]}"
        return await self._call(f"cell create {name}")

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

        For v0.1 the payload is a short descriptor (url + title + sha256s).
        The full HTML/screenshot can be stored via dedicated endpoints once
        Anunix exposes binary state upload.
        """
        html_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        shot_hash = (
            hashlib.sha256(screenshot_png).hexdigest() if screenshot_png else None
        )
        descriptor = json.dumps(
            {
                "url": url,
                "title": title,
                "html_sha256": html_hash,
                "screenshot_sha256": shot_hash,
                "session": session_id,
            },
            separators=(",", ":"),
        )
        # ansh syntax: write <ns:path> <content...>
        # Escape spaces by wrapping in quotes (bridge can't pass multi-word
        # content through the single-string command API).  Use base64 for
        # safety — the receiver can decode if needed.
        import base64

        b64 = base64.b64encode(descriptor.encode()).decode()
        result = await self._call(f"write {ns_path} {b64}")
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
        """Log an action via echo (provenance dedicated endpoint is TBD)."""
        summary = f"browser[{session_id[:8]}]:{action}"
        return await self._call(f"echo {summary}")

    async def get_fb_info(self) -> Optional[Dict[str, Any]]:
        """Return current framebuffer dimensions from Anunix, or None."""
        if not self._enabled:
            return None
        try:
            data = await asyncio.to_thread(self._get, "/api/v1/fb")
        except Exception:
            return None
        if not data.get("available"):
            return None
        return data  # keys: available, width, height, pitch, bpp

    async def _call(self, command: str) -> BridgeResult:
        if not self._enabled:
            return BridgeResult(ok=False, error="bridge disabled")
        try:
            data = await asyncio.to_thread(
                self._post,
                "/api/v1/exec",
                {"command": command},
            )
        except Exception as exc:
            self._status = BridgeStatus.DEGRADED
            self._last_error = str(exc)
            log.debug("anunix call failed: %s", exc)
            return BridgeResult(ok=False, error=str(exc))
        self._status = BridgeStatus.CONNECTED
        self._last_ok_at = time.time()
        return BridgeResult(ok=True, data=data)

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with urlrequest.urlopen(url, timeout=self._timeout_s) as resp:
                raw = resp.read()
        except urlerror.URLError as exc:
            raise RuntimeError(f"anunix unreachable: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {"raw": raw.decode("utf-8", errors="replace")}

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
