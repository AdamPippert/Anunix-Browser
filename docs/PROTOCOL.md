# ANX-Browser Protocol v0.1

**Status:** Draft. Subject to change before v1.0.
**Transport:** HTTP/1.1 and WebSocket over TCP. TLS optional; strongly recommended for non-loopback use.
**Default port:** 9090.
**Content type:** `application/json; charset=utf-8` unless noted.

The ANX-Browser Protocol is a small REST + WebSocket surface for creating browser sessions, dispatching actions, and streaming events. It is inspired by Chrome DevTools Protocol but is **not** a direct translation — it is higher level, multi-agent by design, and speaks in terms of semantic verbs rather than CDP commands.

## 1. Authentication

Every mutating request carries a capability token:

```
Authorization: ANX-Capability <token>
```

In v0.1 the token is opaque to the daemon; it is forwarded to Anunix for validation when the bridge is live. In local development the daemon accepts any non-empty token, and if no `Authorization` header is present, a synthetic token with all verbs is minted — this is documented as unsafe for non-loopback use.

## 2. Endpoints

### 2.1 `GET /api/v1/health`

Liveness probe. No auth required.

Response 200:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "sessions": 2,
  "bridge": "connected"
}
```

The `bridge` field is one of `connected`, `degraded`, `disabled`.

### 2.2 `POST /api/v1/sessions`

Create a new browser session.

Request:
```json
{
  "headless": true,
  "viewport": { "width": 1280, "height": 800 },
  "user_agent": null,
  "cell_id": null,
  "namespace": "/sessions",
  "record": false
}
```

All fields optional. `cell_id` binds the session to an existing Anunix Execution Cell; if null, the bridge creates one. `namespace` is the Anunix path under which State Objects will be written. `record` enables continuous session recording.

Response 201:
```json
{
  "session_id": "01HX7YQG4R9ZPQ2K7N8H3M5VGC",
  "cell_id": "cell:browser:01HX7...",
  "created_at": "2026-04-18T14:02:11Z",
  "stream_url": "/api/v1/sessions/01HX7YQG4R9ZPQ2K7N8H3M5VGC/stream"
}
```

### 2.3 `GET /api/v1/sessions`

List active sessions.

Response 200:
```json
{
  "sessions": [
    {
      "session_id": "01HX7...",
      "cell_id": "cell:browser:...",
      "current_url": "https://example.com/",
      "created_at": "2026-04-18T14:02:11Z",
      "subscribers": 3,
      "driver": "agent:perplexity"
    }
  ]
}
```

### 2.4 `DELETE /api/v1/sessions/{id}`

Close a session and release resources. Broadcasts a terminal event on the stream.

Response 204. If the session does not exist, 404.

### 2.5 `POST /api/v1/sessions/{id}/navigate`

Request:
```json
{ "url": "https://example.com/", "wait_until": "load" }
```

`wait_until` may be `load`, `domcontentloaded`, `networkidle`, or omitted. Response 200:
```json
{
  "event_id": 14,
  "status": 200,
  "url": "https://example.com/",
  "title": "Example Domain",
  "page_state_object": "anx:state:sha256:abc..."
}
```

### 2.6 `POST /api/v1/sessions/{id}/observe`

Captures a "look" at the current page. Request body is empty or:
```json
{ "include_screenshot": true, "include_html": false, "text_only": true }
```

Response 200:
```json
{
  "event_id": 15,
  "url": "https://example.com/",
  "title": "Example Domain",
  "visible_text": "Example Domain ...",
  "screenshot_b64": "iVBORw0KGgoAAAANSUhEU...",
  "screenshot_mime": "image/png",
  "page_state_object": "anx:state:sha256:abc..."
}
```

`visible_text` is the best-effort innerText of the body with whitespace normalized.

### 2.7 `POST /api/v1/sessions/{id}/click`

Request:
```json
{ "selector": "button[type=submit]", "button": "left", "timeout_ms": 5000 }
```

`selector` can be a CSS selector or a Playwright text selector (`text=Sign in`). Response 200:
```json
{ "event_id": 16, "clicked": true }
```

### 2.8 `POST /api/v1/sessions/{id}/type`

Request:
```json
{ "selector": "input[name=q]", "text": "hello world", "press_enter": false }
```

If `selector` is omitted, typing happens on the currently focused element. Response 200:
```json
{ "event_id": 17, "typed": 11 }
```

### 2.9 `POST /api/v1/sessions/{id}/scroll`

Request:
```json
{ "dy": 400 }
```
or
```json
{ "to_selector": "#footer" }
```

Response 200 with `event_id`.

### 2.10 `POST /api/v1/sessions/{id}/wait_for`

Request:
```json
{ "selector": "main.loaded", "timeout_ms": 10000 }
```

Response 200 on success with `event_id`, 408 on timeout.

### 2.11 `POST /api/v1/sessions/{id}/eval`

Request:
```json
{ "expression": "document.title" }
```

Response 200:
```json
{ "event_id": 19, "result": "Example Domain", "type": "string" }
```

The `eval` verb is privileged. Tokens without `eval` in their verb list receive 403.

### 2.12 `POST /api/v1/sessions/{id}/release`

Current driver releases control. Response 204.

### 2.13 `POST /api/v1/sessions/{id}/claim`

Caller requests driver role. Response 200 on success, 409 if already driven.

### 2.14 `WS /api/v1/sessions/{id}/stream`

Upgrade request. Auth via `Authorization` header on the upgrade or via `?token=` query param.

Server-sent messages are JSON with a `type` discriminator:

```json
{ "type": "event", "seq": 42, "kind": "navigated", "payload": { "url": "..." } }
{ "type": "frame", "seq": 43, "mime": "image/jpeg", "data_b64": "..." }
{ "type": "cursor", "seq": 44, "actor": "agent:x", "x": 480, "y": 210 }
{ "type": "driver_changed", "seq": 45, "driver": "human:adam" }
{ "type": "terminal", "seq": 99, "reason": "closed" }
```

Clients may send:
```json
{ "type": "hello", "actor": "human:adam", "role": "viewer" }
{ "type": "cursor", "x": 120, "y": 30 }
```

## 3. Error format

All errors are JSON with consistent shape:

```json
{
  "error": "invalid_selector",
  "message": "Selector did not resolve to a unique element",
  "event_id": 22
}
```

Standard error codes:

| Code                  | HTTP | Meaning                                        |
|-----------------------|------|------------------------------------------------|
| `session_not_found`   | 404  | No such session                                 |
| `unauthorized`        | 401  | Missing or invalid capability                   |
| `forbidden_verb`      | 403  | Token does not include this verb                |
| `invalid_request`     | 400  | Malformed body or parameters                    |
| `invalid_selector`    | 422  | Selector did not resolve                        |
| `navigation_failed`   | 502  | Upstream navigation error                       |
| `timeout`             | 408  | Operation exceeded `timeout_ms`                 |
| `bridge_unavailable`  | 503  | Anunix bridge required for this call is down    |

## 4. Event kinds

| Kind              | Payload                                                   |
|-------------------|-----------------------------------------------------------|
| `session_created` | `{ session_id, cell_id, created_at }`                     |
| `navigated`       | `{ url, title, status, page_state_object }`               |
| `clicked`         | `{ selector }`                                            |
| `typed`           | `{ selector, length }`                                    |
| `scrolled`        | `{ dy, to_selector }`                                     |
| `observed`        | `{ url, title, screenshot_state_object }`                 |
| `console`         | `{ level, text }`                                         |
| `page_error`      | `{ message, stack }`                                      |
| `driver_changed`  | `{ driver }`                                              |
| `bridge_degraded` | `{ since, error }`                                        |
| `terminal`        | `{ reason }`                                              |

## 5. Versioning

The protocol is versioned by the `/api/v1/` prefix. Additive changes (new optional fields, new verbs, new event kinds) are permitted within v1. Breaking changes increment the version prefix.

## 6. Future (non-v0.1)

- Binary WebSocket frames for screenshots.
- Tab management verbs: `tab_open`, `tab_close`, `tab_switch`.
- File upload verb (`upload`).
- Structured DOM observation: a `dom_snapshot` verb returning a canonical tree, addressable as a State Object.
- Assertions: `assert_text`, `assert_selector` for agent test frameworks.
- Session fork: clone an existing session's state into a new session.
