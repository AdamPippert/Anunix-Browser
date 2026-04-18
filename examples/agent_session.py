#!/usr/bin/env python3
"""Example: an agent drives a browser session through the ANX-Browser Protocol.

Uses only the Python standard library so the example runs without extra deps.

    $ python3 examples/agent_session.py [URL]

Spins up one session, navigates to the given URL (or https://example.com),
observes the page (title + short text + PNG screenshot), and exits cleanly.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from urllib import error, request

BASE = os.environ.get("ANXB_BASE", "http://127.0.0.1:9090")


def post(path: str, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def delete(path: str) -> int:
    req = request.Request(f"{BASE}{path}", method="DELETE")
    with request.urlopen(req, timeout=10) as r:
        return r.status


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
    print(f"[agent] creating session on {BASE}")
    try:
        s = post("/api/v1/sessions", {"headless": True})
    except error.URLError as exc:
        print(f"[agent] daemon unreachable: {exc}", file=sys.stderr)
        return 2
    sid = s["session_id"]
    print(f"[agent] session {sid} cell={s.get('cell_id')}")
    try:
        nav = post(f"/api/v1/sessions/{sid}/navigate", {"url": url})
        print(f"[agent] navigated: {nav['title']} ({nav['status']})")
        time.sleep(0.5)
        obs = post(
            f"/api/v1/sessions/{sid}/observe",
            {"include_screenshot": True, "text_only": True},
        )
        print(f"[agent] observed: {obs['title']}")
        print(f"[agent] text:     {obs['visible_text'][:180]}")
        if "screenshot_b64" in obs:
            path = f"/tmp/anxb-{sid}.png"
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(obs["screenshot_b64"]))
            print(f"[agent] screenshot saved to {path}")
    finally:
        try:
            delete(f"/api/v1/sessions/{sid}")
            print("[agent] session closed")
        except Exception as exc:
            print(f"[agent] close error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
