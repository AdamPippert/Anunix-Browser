"""Anunix-Browser daemon entry point.

Run with: `python3 -m anxbrowser.server`
or via the Makefile `make run` target.
"""

from __future__ import annotations

import logging
import os
import signal

from aiohttp import web

from .bridge import AnunixBridge
from .config import Config
from .handlers import sessions as sessions_h
from .handlers import stream as stream_h
from .handlers import stream_native as stream_native_h
from .session import SessionManager

log = logging.getLogger(__name__)


async def _health(request: web.Request) -> web.Response:
    cfg: Config = request.app["config"]
    manager: SessionManager = request.app["manager"]
    bridge: AnunixBridge = request.app["bridge"]
    return web.json_response(
        {
            "status": "ok",
            "version": "0.1.0",
            "sessions": len(manager.list()),
            "bridge": bridge.status.value,
            "config": {
                "host": cfg.host,
                "port": cfg.port,
                "anunix_enabled": bridge.enabled,
                "anunix_url": cfg.anunix_base_url if bridge.enabled else None,
            },
        }
    )


async def _index(request: web.Request) -> web.StreamResponse:
    cfg: Config = request.app["config"]
    index_path = os.path.join(cfg.static_dir, "index.html")
    if not os.path.exists(index_path):
        return web.Response(
            text="Anunix-Browser daemon is running. UI not installed.",
            content_type="text/plain",
        )
    return web.FileResponse(index_path)


@web.middleware
async def _cors_middleware(request: web.Request, handler) -> web.Response:
    if request.method == "OPTIONS":
        return web.Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    response = await handler(request)
    # WebSocketResponse (and other StreamResponse subclasses) are already
    # prepared by the time the handler returns — headers are immutable.
    if not response.prepared:
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
    return response


def build_app(cfg: Config | None = None) -> web.Application:
    cfg = cfg or Config.from_env()
    app = web.Application(
        client_max_size=16 * 1024 * 1024,
        middlewares=[_cors_middleware],
    )
    bridge = AnunixBridge(
        base_url=cfg.anunix_base_url,
        enabled=cfg.anunix_enabled,
    )
    manager = SessionManager(bridge=bridge, headless_default=cfg.headless_default)

    app["config"] = cfg
    app["bridge"] = bridge
    app["manager"] = manager

    app.router.add_get("/", _index)
    app.router.add_get("/api/v1/health", _health)

    app.router.add_post("/api/v1/sessions", sessions_h.create_session)
    app.router.add_get("/api/v1/sessions", sessions_h.list_sessions)
    app.router.add_delete("/api/v1/sessions/{sid}", sessions_h.delete_session)
    app.router.add_post("/api/v1/sessions/{sid}/navigate", sessions_h.navigate)
    app.router.add_post("/api/v1/sessions/{sid}/observe", sessions_h.observe)
    app.router.add_post("/api/v1/sessions/{sid}/click", sessions_h.click)
    app.router.add_post("/api/v1/sessions/{sid}/type", sessions_h.type_text)
    app.router.add_post("/api/v1/sessions/{sid}/scroll", sessions_h.scroll)
    app.router.add_post("/api/v1/sessions/{sid}/wait_for", sessions_h.wait_for)
    app.router.add_post("/api/v1/sessions/{sid}/eval", sessions_h.eval_js)
    app.router.add_post("/api/v1/sessions/{sid}/claim", sessions_h.claim)
    app.router.add_post("/api/v1/sessions/{sid}/release", sessions_h.release)
    app.router.add_get("/api/v1/sessions/{sid}/stream", stream_h.stream)
    app.router.add_get("/api/v1/sessions/{sid}/stream_raw", stream_native_h.stream_raw)

    if os.path.isdir(cfg.static_dir):
        app.router.add_static("/ui/", cfg.static_dir, show_index=False)

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


async def _on_startup(app: web.Application) -> None:
    bridge: AnunixBridge = app["bridge"]
    await bridge.probe()
    manager: SessionManager = app["manager"]
    await manager.start()
    log.info(
        "anxbrowserd ready on http://%s:%d (bridge=%s)",
        app["config"].host,
        app["config"].port,
        bridge.status.value,
    )


async def _on_cleanup(app: web.Application) -> None:
    manager: SessionManager = app["manager"]
    await manager.stop()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("ANXB_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = Config.from_env()
    app = build_app(cfg)

    # Graceful shutdown.
    def _handle_sig(*_a):
        raise KeyboardInterrupt

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handle_sig)
        except (ValueError, OSError):
            pass

    web.run_app(app, host=cfg.host, port=cfg.port, print=None)


if __name__ == "__main__":
    main()
