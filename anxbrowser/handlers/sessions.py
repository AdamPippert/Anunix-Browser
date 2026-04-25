"""HTTP handlers for /api/v1/sessions/*.

Kept deliberately thin: parse + validate + delegate to the SessionManager,
translate errors into the canonical ANX-Browser error shape.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from aiohttp import web

from ..capability import Capability, require_verbs, parse_header, synthetic
from ..protocol import (
    ProtocolError,
    validate_click,
    validate_create_session,
    validate_eval,
    validate_navigate,
    validate_observe,
    validate_scroll,
    validate_submit,
    validate_type,
    validate_wait_for,
)
from ..session import SessionManager

log = logging.getLogger(__name__)


def _cap(request: web.Request) -> Capability:
    cfg = request.app["config"]
    try:
        cap = parse_header(request.headers.get("Authorization"))
    except ValueError as exc:
        raise _err("unauthorized", str(exc), 401) from exc
    if cap is None:
        if not cfg.allow_unauthenticated:
            raise _err("unauthorized", "capability required", 401)
        cap = synthetic()
    return cap


def _err(code: str, message: str, status: int) -> web.HTTPException:
    payload = {"error": code, "message": message}
    return web.HTTPException(reason=message, text=_json(payload))


def _json(obj: Dict[str, Any]) -> str:
    import json

    return json.dumps(obj)


def _problem(code: str, message: str, status: int) -> web.Response:
    return web.json_response({"error": code, "message": message}, status=status)


def _require_session(manager: SessionManager, sid: str):
    session = manager.get(sid)
    if not session:
        raise web.HTTPNotFound(
            text=_json({"error": "session_not_found", "message": sid})
        )
    return session


async def _read_json(request: web.Request) -> Dict[str, Any]:
    if request.content_length in (0, None):
        return {}
    try:
        return await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(
            text=_json({"error": "invalid_request", "message": f"not JSON: {exc}"})
        ) from exc


# --- Route handlers -----------------------------------------------------


async def create_session(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["navigate"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    body = await _read_json(request)
    try:
        params = validate_create_session(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    manager: SessionManager = request.app["manager"]
    try:
        session = await manager.create_session(
            headless=params["headless"],
            viewport=params["viewport"],
            browser_engine=params["browser_engine"],
            dom_snapshot_mode=params["dom_snapshot_mode"],
            dom_text_max_chars=params["dom_text_max_chars"],
            user_agent=params["user_agent"],
            cell_id=params["cell_id"],
            namespace=params["namespace"],
        )
    except Exception as exc:
        log.exception("failed to create session")
        return _problem("internal_error", str(exc), 500)
    return web.json_response(
        {
            "session_id": session.session_id,
            "cell_id": session.cell_id,
            "created_at": session.created_at,
            "browser_engine": session.browser_engine,
            "dom_snapshot_mode": session.dom_snapshot_mode,
            "stream_url": f"/api/v1/sessions/{session.session_id}/stream",
        },
        status=201,
    )


async def list_sessions(request: web.Request) -> web.Response:
    _cap(request)
    manager: SessionManager = request.app["manager"]
    return web.json_response(
        {"sessions": [info.__dict__ for info in manager.list()]}
    )


async def delete_session(request: web.Request) -> web.Response:
    _cap(request)
    manager: SessionManager = request.app["manager"]
    sid = request.match_info["sid"]
    ok = await manager.close_session(sid)
    if not ok:
        return _problem("session_not_found", sid, 404)
    return web.Response(status=204)


async def navigate(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["navigate"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_navigate(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.navigate(params["url"], params["wait_until"])
    except Exception as exc:
        log.exception("navigate failed")
        return _problem("navigation_failed", str(exc), 502)
    return web.json_response(result)


async def observe(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["observe"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_observe(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    result = await session.observe(**params)
    return web.json_response(result)


async def click(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["click"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_click(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.click(**params)
    except Exception as exc:
        return _problem("invalid_selector", str(exc), 422)
    return web.json_response(result)


async def type_text(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["type"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_type(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.type_text(**params)
    except Exception as exc:
        return _problem("invalid_selector", str(exc), 422)
    return web.json_response(result)


async def scroll(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["scroll"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_scroll(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    result = await session.scroll(**params)
    return web.json_response(result)


async def wait_for(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["wait_for"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_wait_for(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.wait_for(**params)
    except Exception as exc:
        return _problem("timeout", str(exc), 408)
    return web.json_response(result)


async def eval_js(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["eval"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_eval(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.eval_js(**params)
    except Exception as exc:
        return _problem("invalid_request", str(exc), 400)
    return web.json_response(result)


async def submit_form(request: web.Request) -> web.Response:
    cap = _cap(request)
    try:
        require_verbs(cap, ["navigate"])
    except PermissionError as exc:
        return _problem("forbidden_verb", str(exc), 403)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    body = await _read_json(request)
    try:
        params = validate_submit(body)
    except ProtocolError as exc:
        return _problem(exc.code, exc.message, exc.http_status)
    try:
        result = await session.submit_form(**params)
    except Exception as exc:
        log.exception("submit_form failed")
        return _problem("navigation_failed", str(exc), 502)
    return web.json_response(result)


async def claim(request: web.Request) -> web.Response:
    cap = _cap(request)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    if session.driver and session.driver != cap.actor:
        return _problem("conflict", f"driver is {session.driver}", 409)
    session.driver = cap.actor
    await session.bus.publish("driver_changed", {"driver": cap.actor})
    return web.json_response({"driver": cap.actor})


async def release(request: web.Request) -> web.Response:
    cap = _cap(request)
    manager: SessionManager = request.app["manager"]
    session = _require_session(manager, request.match_info["sid"])
    if session.driver and session.driver != cap.actor:
        return _problem(
            "forbidden_verb",
            f"only driver {session.driver} can release",
            403,
        )
    session.driver = None
    await session.bus.publish("driver_changed", {"driver": None})
    return web.Response(status=204)
