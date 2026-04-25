# Anunix-Browser 2026.4.24

## What's new

### Collaborative viewer input forwarding
The WebSocket stream (`/api/v1/sessions/{sid}/stream`) now forwards all
viewer input to the underlying Playwright page. Observers can click, type,
scroll, and use keyboard navigation directly from the collaborative UI —
not just watch.

- **Click** (`{type:"click", x, y}`) — Playwright `mouse.click(x, y)`
- **Keydown** (`{type:"keydown", key}`) — Playwright `keyboard.press` /
  `keyboard.type` with a key-name map covering Enter, Backspace, arrows, etc.
- **Scroll** (`{type:"scroll", dy}`) — `window.scrollBy(0, dy)` on the page
- **PII response** (`{type:"pii_response", action}`) — forwarded to the event
  bus so agents can react to the user's redaction decision

### Form submission endpoint
`POST /api/v1/sessions/{sid}/submit` — submits a form to `action` with
`fields` dict. GET forms are handled by URL construction + navigate; POST
forms are submitted via a synthetic `<form>` element evaluated in the page.

```
POST /api/v1/sessions/sess_abc123/submit
{"action": "https://example.com/search", "method": "GET", "fields": {"q": "anunix"}}
```

### Aether design system (from 2026.4.19 release, fully shipped)
Both the web UI and the desktop app now use the Anunix Aether visual
language: navy/teal gradient header, warm paper panels, glassmorphism
toolbar, JetBrains Mono for technical output, Inter for UI text. The
browser canvas area stays dark to maximise screenshot contrast.

### Desktop app (Tauri)
`desktop/` contains a Tauri-based native wrapper that presents the
collaborative viewer as a macOS/Windows window with:
- Traffic-light window buttons
- Glass tab bar (multi-session tabs with `+` to open new)
- Agent panel with quick-action buttons
- Native session restore on restart

### HTTPS proxy support
The kernel native browser sends HTTPS traffic through an HTTP CONNECT
tunnel. Run `tools/anxbproxy.py` on the host to terminate TLS at
`10.0.2.2:8118` (QEMU user-mode network alias).

## API surface changes

| Endpoint | Change |
|---|---|
| `POST /api/v1/sessions/{sid}/submit` | **New** — form submission |
| `GET /api/v1/sessions/{sid}/stream` | Now forwards `click`/`keydown`/`scroll`/`pii_response` |

## Bug fixes

- Session `created_at` on the Anunix kernel side now uses `arch_time_now()`
  (nanoseconds since epoch) instead of being hardcoded to 0.
- Stream handler bare exception `pass` blocks replaced with `log.debug`
  so dropped frames and WebSocket errors are visible in `--log-level debug`.
