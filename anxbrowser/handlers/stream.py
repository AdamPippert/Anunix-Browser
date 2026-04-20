"""WebSocket stream handler.

Each client connected to /api/v1/sessions/{id}/stream receives:
 - replayed history events upon connect
 - live events as they are published
 - periodic JPEG frames captured from the live page

Clients may send cursor updates and hello messages.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from aiohttp import WSMsgType, web

from ..session import SessionManager

log = logging.getLogger(__name__)

FRAME_INTERVAL_S = 0.033  # ~30 FPS


async def stream(request: web.Request) -> web.StreamResponse:
    manager: SessionManager = request.app["manager"]
    sid = request.match_info["sid"]
    session = manager.get(sid)
    if not session:
        return web.json_response(
            {"error": "session_not_found", "message": sid}, status=404
        )

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    queue = await session.bus.subscribe()
    frame_task = asyncio.create_task(_frame_loop(ws, session))
    event_task = asyncio.create_task(_event_loop(ws, queue))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _handle_client_message(ws, session, msg.data)
            elif msg.type == WSMsgType.ERROR:
                log.debug("ws error: %s", ws.exception())
                break
    finally:
        frame_task.cancel()
        event_task.cancel()
        await session.bus.unsubscribe(queue)

    return ws


async def _event_loop(ws: web.WebSocketResponse, queue: asyncio.Queue) -> None:
    try:
        while not ws.closed:
            event = await queue.get()
            if ws.closed:
                return
            await ws.send_json(event.to_dict())
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.debug("event loop error: %s", exc)


async def _frame_loop(ws: web.WebSocketResponse, session: Any) -> None:
    seq = 0
    try:
        while not ws.closed and not session.closed:
            await asyncio.sleep(FRAME_INTERVAL_S)
            if ws.closed or session.closed:
                return
            data = await session.frame_screenshot()
            if not data:
                continue
            seq += 1
            payload = {
                "type": "frame",
                "seq": seq,
                "mime": "image/jpeg",
                "data_b64": base64.b64encode(data).decode("ascii"),
            }
            try:
                await ws.send_json(payload)
            except ConnectionResetError:
                return
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.debug("frame loop error: %s", exc)


async def _handle_client_message(
    ws: web.WebSocketResponse, session: Any, data: str
) -> None:
    try:
        msg = json.loads(data)
    except ValueError:
        return
    kind = msg.get("type")
    if kind == "hello":
        actor = str(msg.get("actor", "viewer"))
        await session.bus.publish(
            "viewer_joined", {"actor": actor, "role": msg.get("role", "viewer")}
        )
    elif kind == "cursor":
        x = int(msg.get("x", 0))
        y = int(msg.get("y", 0))
        actor = str(msg.get("actor", "viewer"))
        await session.bus.publish("cursor", {"actor": actor, "x": x, "y": y})
