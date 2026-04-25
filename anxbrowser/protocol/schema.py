"""Protocol request validators.

These are deliberately hand-written rather than relying on pydantic or
jsonschema. The protocol surface is small, the dependencies stay few, and the
error messages are legible at the API boundary.
"""

from __future__ import annotations

from typing import Any, Dict


ALLOWED_WAIT_UNTIL = ("load", "domcontentloaded", "networkidle", "commit")
ALLOWED_BROWSER_ENGINES = ("chromium", "firefox")
ALLOWED_DOM_SNAPSHOT_MODES = ("light", "full")

KNOWN_VERBS = (
    "navigate",
    "observe",
    "click",
    "type",
    "scroll",
    "wait_for",
    "eval",
    "screenshot",
)


class ProtocolError(ValueError):
    """Raised when a request body fails protocol validation."""

    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _require(body: Dict[str, Any], key: str, typ: type) -> Any:
    if key not in body:
        raise ProtocolError("invalid_request", f"missing field: {key}")
    val = body[key]
    if not isinstance(val, typ):
        raise ProtocolError(
            "invalid_request",
            f"field {key!r} must be {typ.__name__}, got {type(val).__name__}",
        )
    return val


def _optional(body: Dict[str, Any], key: str, typ: type, default: Any) -> Any:
    if key not in body or body[key] is None:
        return default
    val = body[key]
    if not isinstance(val, typ):
        raise ProtocolError(
            "invalid_request",
            f"field {key!r} must be {typ.__name__}, got {type(val).__name__}",
        )
    return val


def validate_create_session(body: Dict[str, Any]) -> Dict[str, Any]:
    body = body or {}
    headless = _optional(body, "headless", bool, True)
    viewport = _optional(body, "viewport", dict, {"width": 1280, "height": 800})
    if not (
        isinstance(viewport.get("width"), int) and isinstance(viewport.get("height"), int)
    ):
        raise ProtocolError("invalid_request", "viewport requires integer width/height")

    browser_engine = _optional(body, "browser_engine", str, "chromium").lower()
    if browser_engine not in ALLOWED_BROWSER_ENGINES:
        raise ProtocolError(
            "invalid_request",
            f"browser_engine must be one of {ALLOWED_BROWSER_ENGINES}",
        )

    dom_snapshot_mode = _optional(body, "dom_snapshot_mode", str, "light").lower()
    if dom_snapshot_mode not in ALLOWED_DOM_SNAPSHOT_MODES:
        raise ProtocolError(
            "invalid_request",
            f"dom_snapshot_mode must be one of {ALLOWED_DOM_SNAPSHOT_MODES}",
        )

    dom_text_max_chars = _optional(body, "dom_text_max_chars", int, 4096)
    if not (256 <= dom_text_max_chars <= 65536):
        raise ProtocolError(
            "invalid_request",
            "dom_text_max_chars must be between 256 and 65536",
        )

    user_agent = _optional(body, "user_agent", str, "")
    cell_id = _optional(body, "cell_id", str, "")
    namespace = _optional(body, "namespace", str, "/sessions")
    record = _optional(body, "record", bool, False)
    return {
        "headless": headless,
        "viewport": viewport,
        "browser_engine": browser_engine,
        "dom_snapshot_mode": dom_snapshot_mode,
        "dom_text_max_chars": dom_text_max_chars,
        "user_agent": user_agent or None,
        "cell_id": cell_id or None,
        "namespace": namespace,
        "record": record,
    }


def validate_navigate(body: Dict[str, Any]) -> Dict[str, Any]:
    url = _require(body, "url", str)
    if not url.strip():
        raise ProtocolError("invalid_request", "url must not be empty")
    wait_until = _optional(body, "wait_until", str, "load")
    if wait_until not in ALLOWED_WAIT_UNTIL:
        raise ProtocolError(
            "invalid_request",
            f"wait_until must be one of {ALLOWED_WAIT_UNTIL}",
        )
    return {"url": url, "wait_until": wait_until}


def validate_observe(body: Dict[str, Any]) -> Dict[str, Any]:
    body = body or {}
    return {
        "include_screenshot": _optional(body, "include_screenshot", bool, True),
        "include_html": _optional(body, "include_html", bool, False),
        "text_only": _optional(body, "text_only", bool, True),
    }


def validate_click(body: Dict[str, Any]) -> Dict[str, Any]:
    selector = _require(body, "selector", str)
    button = _optional(body, "button", str, "left")
    if button not in ("left", "middle", "right"):
        raise ProtocolError("invalid_request", "button must be left|middle|right")
    timeout_ms = _optional(body, "timeout_ms", int, 5000)
    return {"selector": selector, "button": button, "timeout_ms": timeout_ms}


def validate_type(body: Dict[str, Any]) -> Dict[str, Any]:
    text = _require(body, "text", str)
    selector = _optional(body, "selector", str, "")
    press_enter = _optional(body, "press_enter", bool, False)
    return {
        "selector": selector or None,
        "text": text,
        "press_enter": press_enter,
    }


def validate_scroll(body: Dict[str, Any]) -> Dict[str, Any]:
    body = body or {}
    if "to_selector" in body and body["to_selector"]:
        return {"to_selector": _require(body, "to_selector", str)}
    dy = _optional(body, "dy", int, 0)
    dx = _optional(body, "dx", int, 0)
    return {"dx": dx, "dy": dy}


def validate_wait_for(body: Dict[str, Any]) -> Dict[str, Any]:
    selector = _require(body, "selector", str)
    timeout_ms = _optional(body, "timeout_ms", int, 10000)
    return {"selector": selector, "timeout_ms": timeout_ms}


def validate_eval(body: Dict[str, Any]) -> Dict[str, Any]:
    expression = _require(body, "expression", str)
    return {"expression": expression}


def validate_submit(body: Dict[str, Any]) -> Dict[str, Any]:
    body = body or {}
    action = _optional(body, "action", str, "")
    method = _optional(body, "method", str, "GET").upper()
    if method not in ("GET", "POST"):
        raise ProtocolError("invalid_request", "method must be GET or POST")
    fields = body.get("fields", {})
    if not isinstance(fields, dict):
        raise ProtocolError("invalid_request", "fields must be an object")
    clean: Dict[str, str] = {}
    for k, v in fields.items():
        if not isinstance(k, str):
            raise ProtocolError("invalid_request", "field keys must be strings")
        clean[k] = str(v)
    return {"action": action, "method": method, "fields": clean}
