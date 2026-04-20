"""Binary frame stream for native Anunix Browser Renderer Cell.

GET /api/v1/sessions/{sid}/stream_raw

Streams raw JPEG frames over a plain HTTP connection with no base64 or
JSON overhead. Protocol: [4-byte big-endian length][JPEG bytes] repeated.

Designed to be consumed by the kernel-side browser_cell.c, which cannot
easily decode JSON or base64 in interrupt context.
"""

from __future__ import annotations

import asyncio
import logging
import struct

from aiohttp import web

from ..session import BrowserSession, SessionManager

log = logging.getLogger(__name__)

# Mirror the main stream's frame interval; driven by FRAME_INTERVAL_S in stream.py
from .stream import FRAME_INTERVAL_S


async def stream_raw(request: web.Request) -> web.StreamResponse:
    """Stream raw JPEG frames to the Anunix Browser Renderer Cell."""
    manager: SessionManager = request.app["manager"]
    sid = request.match_info["sid"]

    session: BrowserSession | None = manager.get(sid)
    if session is None:
        return web.Response(status=404, text="session not found")

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "application/octet-stream",
            "Cache-Control": "no-cache",
            "X-Anunix-Stream": "native-jpeg",
        },
    )
    await response.prepare(request)

    log.info("stream_raw: native client connected for session %s", sid)

    try:
        while True:
            jpeg_bytes = await session.frame_screenshot()
            if jpeg_bytes:
                # [4-byte BE length][JPEG bytes]
                header = struct.pack(">I", len(jpeg_bytes))
                await response.write(header + jpeg_bytes)
            await asyncio.sleep(FRAME_INTERVAL_S)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    except Exception as exc:
        log.warning("stream_raw: session %s error: %s", sid, exc)
    finally:
        log.info("stream_raw: native client disconnected for session %s", sid)

    return response
