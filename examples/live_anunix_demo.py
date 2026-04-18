#!/usr/bin/env python3
"""Demo: drive a live Anunix instance through the AnunixBridge.

Requires a running Anunix QEMU VM with the HTTP API exposed.  The default
URL assumes the Jekyll deployment (http://127.0.0.1:18080 via SSH tunnel,
or hit Jekyll directly).

Usage:
    # From Jekyll itself, where the port is forwarded:
    python3 live_anunix_demo.py http://localhost:18080

    # From your Mac, through SSH port forwarding:
    ssh -L 18080:localhost:18080 jekyll -N &
    python3 live_anunix_demo.py http://localhost:18080
"""

import asyncio
import sys

from anxbrowser.bridge import AnunixBridge


async def main(base_url: str) -> int:
    bridge = AnunixBridge(base_url, enabled=True, timeout_s=5.0)

    print(f"probing {base_url} …")
    if not await bridge.probe():
        print("  anunix is not reachable")
        return 1
    print(f"  connected (status: {bridge.status.value})")

    print("\n--- exec: sysinfo ---")
    r = await bridge.exec("sysinfo")
    if r.ok and r.data:
        print(r.data.get("output", ""))

    print("--- exec: mem stats ---")
    r = await bridge.exec("mem stats")
    if r.ok and r.data:
        print(r.data.get("output", ""))

    print("--- bind browser session to a cell ---")
    r = await bridge.bind_session_to_cell("demo_sess_abcdef01")
    if r.ok and r.data:
        print(r.data.get("output", ""))

    print("--- store a fake page as a state object ---")
    r = await bridge.store_page_as_state_object(
        session_id="demo_sess_abcdef01",
        ns_path="default:/browser/demo-page",
        url="https://example.com",
        title="Example Domain",
        html="<html><body><h1>Example</h1></body></html>",
    )
    if r.ok and r.data:
        print(f"  {r.data.get('output', '')}")
        print(f"  state_object: {r.data['state_object']}")

    print("--- exec: cat the stored page descriptor ---")
    r = await bridge.exec("cat default:/browser/demo-page")
    if r.ok and r.data:
        print(r.data.get("output", ""))

    print("--- exec: ls the browser namespace ---")
    r = await bridge.exec("ls default:/browser")
    if r.ok and r.data:
        print(r.data.get("output", ""))

    return 0


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18080"
    sys.exit(asyncio.run(main(url)))
