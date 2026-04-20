# Anunix-Browser 2026.4.19 Release Notes

Milestone: **Native QEMU/kernel streaming** — anxbrowserd can now serve live JPEG frames directly to the Anunix kernel, enabling graphical browser rendering on bare metal and in QEMU without any userspace layer.

## Highlights

- **Binary stream endpoint** — new `GET /api/v1/sessions/{sid}/stream_raw` serves raw `[4-byte BE length][JPEG]` frames over a persistent HTTP connection; no base64, no JSON, designed for kernel-side consumption.
- **Public bind address** — daemon now defaults to `0.0.0.0` so the QEMU guest (at `10.0.2.2`) can connect without configuration changes.
- **30 FPS streaming** — frame rate increased from 1 FPS to ~30 FPS.
- **Viewport auto-sizing** — session creation queries `GET /api/v1/fb` on the connected Anunix instance and uses its framebuffer dimensions as the Playwright viewport.

## New Features

### Binary Stream Endpoint (`stream_native.py`)

`GET /api/v1/sessions/{sid}/stream_raw`

Streams JPEG frames in the protocol expected by the Anunix Browser Renderer Cell:

```
[4-byte big-endian frame length][JPEG bytes] [4-byte big-endian frame length][JPEG bytes] ...
```

- `Content-Type: application/octet-stream`
- `X-Anunix-Stream: native-jpeg`
- Frame rate governed by `FRAME_INTERVAL_S` (shared with the WebSocket stream)
- Designed for `anx_tcp_recv()` in interrupt-free kernel context

### Default Bind Address

`ANXB_HOST` default changed from `127.0.0.1` to `0.0.0.0`.

To restore localhost-only binding:
```
ANXB_HOST=127.0.0.1 make run
```

### 30 FPS Frame Rate

`FRAME_INTERVAL_S` changed from `1.0` to `0.033` seconds (~30 FPS) in `handlers/stream.py`. Both the WebSocket stream and the binary stream use this value.

### Viewport Auto-Sizing from Anunix Framebuffer

When `anx_browser_cell_init()` creates a session without an explicit viewport, `anxbrowserd` calls `GET /api/v1/fb` on the Anunix bridge URL and uses the returned `width` × `height` as the Playwright viewport. Falls back to 1280×800 if the bridge is unreachable.

New method: `AnunixBridge.get_fb_info()` returns `{"width": int, "height": int}` or `None`.

## API Changes

### New endpoint

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/sessions/{sid}/stream_raw` | Binary JPEG frame stream |

### No breaking changes

All existing endpoints are unchanged.

## Usage with Anunix Kernel

From the Anunix shell:

```
anx> browser_init          # connects to 10.0.2.2:9090 (QEMU host default)
anx> browser https://example.com
anx> browser status        # → active
anx> browser_stop
```

`browser_init` accepts an optional host and port:

```
anx> browser_init 10.0.2.2 9090
```

The kernel streams frames at ~30 FPS to the framebuffer. DPI-aware scaling ensures readability at all supported resolutions (1× QEMU, 2× 1080p, 3× 2560×1600, 4× 4K).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANXB_HOST` | `0.0.0.0` | Bind address (was `127.0.0.1`) |
| `ANXB_PORT` | `9090` | Listen port |
| `ANXB_ANUNIX_URL` | `http://127.0.0.1:8080` | Anunix HTTP API URL |

## Statistics

- 3 new/modified Python source files
- 2 new routes registered
- 0 breaking API changes
