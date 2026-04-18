"""Anunix bridge tests — no real Anunix required.

We spin up a tiny local HTTP server in a thread, point the bridge at it, and
assert the bridge speaks the expected ansh shell-command shape (single
"command" string per request, matching the real kernel API).
"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from anxbrowser.bridge import AnunixBridge, BridgeStatus


class _Recorder(BaseHTTPRequestHandler):
    received = []  # type: ignore[var-annotated]

    def log_message(self, *_a, **_kw):  # silence test output
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/api/v1/health":
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {"raw": raw}
        _Recorder.received.append({"path": self.path, "body": payload})
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        # Mimic the real Anunix response shape.
        reply = {"status": "ok", "output": f"ran: {payload.get('command', '')}\n"}
        self.wfile.write(json.dumps(reply).encode("utf-8"))


@pytest.fixture()
def fake_anunix():
    _Recorder.received.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _Recorder)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", _Recorder.received
    finally:
        httpd.shutdown()
        thread.join(timeout=1.0)


@pytest.mark.asyncio
async def test_probe_marks_connected(fake_anunix):
    url, _ = fake_anunix
    bridge = AnunixBridge(url, enabled=True)
    ok = await bridge.probe()
    assert ok is True
    assert bridge.status == BridgeStatus.CONNECTED


@pytest.mark.asyncio
async def test_disabled_bridge_never_calls(fake_anunix):
    url, received = fake_anunix
    bridge = AnunixBridge(url, enabled=False)
    await bridge.probe()
    assert bridge.status == BridgeStatus.DISABLED
    result = await bridge.bind_session_to_cell("sess_1")
    assert result.ok is False
    assert received == []


@pytest.mark.asyncio
async def test_bind_session_to_cell(fake_anunix):
    url, received = fake_anunix
    bridge = AnunixBridge(url, enabled=True)
    result = await bridge.bind_session_to_cell("sess_12345678")
    assert result.ok is True
    assert received[0]["path"] == "/api/v1/exec"
    # ansh: "cell create browser-sess_123"  (first 8 chars of session id)
    cmd = received[0]["body"]["command"]
    assert cmd.startswith("cell create browser-")


@pytest.mark.asyncio
async def test_exec_passes_through(fake_anunix):
    url, received = fake_anunix
    bridge = AnunixBridge(url, enabled=True)
    result = await bridge.exec("sysinfo")
    assert result.ok is True
    assert received[-1]["body"]["command"] == "sysinfo"


@pytest.mark.asyncio
async def test_store_page_includes_hash(fake_anunix):
    url, received = fake_anunix
    bridge = AnunixBridge(url, enabled=True)
    result = await bridge.store_page_as_state_object(
        session_id="sess_1",
        ns_path="default:/sessions/sess_1/pages",
        url="https://example.com",
        title="Example",
        html="<html></html>",
    )
    assert result.ok is True
    assert result.data["state_object"].startswith("anx:state:sha256:")
    cmd = received[-1]["body"]["command"]
    assert cmd.startswith("write default:/sessions/sess_1/pages ")


@pytest.mark.asyncio
async def test_unreachable_marks_degraded():
    bridge = AnunixBridge("http://127.0.0.1:1", enabled=True, timeout_s=0.2)
    result = await bridge.bind_session_to_cell("sess_x")
    assert result.ok is False
    assert bridge.status == BridgeStatus.DEGRADED
