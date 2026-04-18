# Anunix-Browser Architecture

This document describes the design of Anunix-Browser. It assumes familiarity with the Anunix RFCs, particularly State Objects (RFC-0002), Execution Cells (RFC-0003), and the HTTP API.

## 1. Goals and non-goals

### Goals

1. A single browser session is simultaneously **human-usable** (via a web UI) and **agent-drivable** (via an API).
2. Every significant event in a session becomes a first-class object in Anunix, with content-addressed provenance.
3. The browser engine is pluggable; Chromium via Playwright is the initial backend.
4. The protocol is simple enough that a shell script can drive a session, and rich enough that a multi-agent system can share one.
5. Security is capability-driven: an agent holds a capability token that names the session and the actions it may perform.

### Non-goals

- **Not a custom rendering engine.** We do not rewrite Blink. Anunix-Browser is glue and integration.
- **Not a browser OS.** The daemon runs as a userland process under Anunix (or under a Linux/macOS host during bootstrap), not as a kernel service.
- **Not a scraping framework.** Scrapers are a natural use case but not the design target; the design target is interactive collaboration.

## 2. Layer map

```
+------------------------------------------------------+
|  Control surfaces                                    |
|                                                      |
|  Human UI (web)     Agent SDK / REST     CLI tools   |
+-----+----------------------+----------------+--------+
      |                      |                |
      |  ANX-Browser Protocol (REST + WebSocket)       |
      v                      v                v
+------------------------------------------------------+
|  anxbrowserd                                         |
|                                                      |
|  - Session manager (one Cell per session)            |
|  - Action dispatcher                                 |
|  - Event bus (fans events to WS subscribers)         |
|  - Anunix bridge (State Objects, Tensors, Cells)     |
|  - Capability enforcement                            |
+----------+----------------------------------+--------+
           |                                  |
           v                                  v
+-----------------------+      +---------------------------+
|  Browser engine       |      |  Anunix HTTP API          |
|  (Playwright/Chromium)|      |  POST /api/v1/exec        |
|                       |      |  /state, /tensor, /cell   |
+-----------------------+      +---------------------------+
```

## 3. Core abstractions

### Session

A session is a single browser context — one Chromium BrowserContext with one or more pages. Sessions have:

- A UUID.
- A creation timestamp.
- An owning **Cell ID** in Anunix (the Execution Cell that holds capabilities for this session).
- A set of **subscribers** (WebSocket connections watching the session).
- A **policy** describing which action verbs are permitted (see Capabilities).
- A **namespace root** in Anunix under which State Objects are written, e.g. `/sessions/<uuid>/`.

Sessions are in-memory; on daemon restart they are gone. Replayable session *recordings* are persisted as State Objects and can be rehydrated into a new session.

### Action

An action is a verb the daemon can perform on behalf of a caller. The v0.1 verbs are:

| Verb       | Effect                                                          |
|------------|-----------------------------------------------------------------|
| `navigate` | Load a URL in the active page                                   |
| `observe`  | Return page title, URL, visible text, and base64 screenshot     |
| `click`    | Click an element matched by CSS or text selector                |
| `type`     | Type text into the focused element                              |
| `scroll`   | Scroll the page by pixels or to an element                      |
| `wait_for` | Wait for a selector, load state, or timeout                     |
| `eval`     | Run a JavaScript snippet in the page and return its result      |

Each action produces an **Event** (see below). Future verbs will include `upload`, `download`, `auth`, `tab_open`, `tab_close`.

### Event

An event is an observable fact about a session: an action was dispatched, a page loaded, a navigation happened, a console message fired, an error occurred. Events have a monotonic sequence number within a session and are broadcast over the session's WebSocket channel. Events are also the primary feed into the Anunix bridge.

### Capability

Every action request carries (or inherits) a **capability token**. The daemon verifies the token against the session's policy before dispatching. Tokens are minted by Anunix's capability subsystem (RFC-0007). In Phase 0 the daemon accepts an unsigned token for local use; in Phase 1 it verifies signatures against the kernel's capability service.

A token is a JSON object:

```json
{
  "session": "uuid",
  "cell": "cell-id",
  "verbs": ["navigate", "observe", "screenshot"],
  "expires_at": "2026-04-18T20:00:00Z"
}
```

Restricting the `verbs` array is how we say "this agent can read but not click".

## 4. Anunix integration

### 4.1 Session = Cell

When a session is created, the daemon issues a `POST /api/v1/exec` call to Anunix with a payload that spawns an Execution Cell representing the session. The returned Cell ID is recorded on the session.

Subsequent actions are **attributed** to the Cell. This gives Anunix accounting, scheduling, and capability enforcement over browser activity.

### 4.2 Pages as State Objects

On every successful `navigate`, the daemon:

1. Captures the rendered HTML and the current URL.
2. Optionally captures a screenshot.
3. POSTs a new State Object under `/sessions/<uuid>/pages/<seq>/` with:
   - `url`: the URL
   - `html`: the rendered HTML (hash-addressed)
   - `title`: the document title
   - `captured_at`: ISO timestamp
   - `parent`: the previous page's State Object hash, for navigation lineage

Because State Objects are content-addressed, identical pages hash to the same object — natural deduplication.

### 4.3 Screenshots as Tensors

A screenshot is a 3D tensor `(height, width, 4)` of RGBA bytes. The daemon uploads the raw pixel buffer as a **Tensor Object** via the Anunix tensor API. The State Object for the page references the tensor by hash. This means agents can run `tensor_ops.similarity(shot_a, shot_b)` inside Anunix to detect whether two screenshots depict the same UI state, without re-downloading the image.

In Phase 0 the daemon stores the screenshot as a compressed PNG in a State Object. Tensor upload is gated behind a feature flag until the tensor API stabilizes.

### 4.4 DOM as a tensor-addressable tree

A rendered DOM is a structured tree. For agent use cases (embeddings, diffs) the daemon serializes the DOM into a canonical form and stores it as a State Object whose payload is the canonical JSON. A companion embedding tensor can be produced by a future embedding cell; that is out of scope for Phase 0.

### 4.5 Credentials

Cookies, tokens, and login state are sensitive. The daemon never writes them to disk or to a normal State Object. Instead, credential material is pushed to the Anunix **credential store** (RFC-0008 Credential Objects) via the kernel, keyed by session and domain. The daemon retrieves credentials as needed via a sealed capability.

In Phase 0 this is stubbed: credentials live in memory and die with the session.

## 5. Collaborative model

### 5.1 Viewer protocol

Any number of clients (human browsers or other agents) can open a WebSocket to `/api/v1/sessions/<id>/stream`. The daemon sends:

- `event` messages for every session event
- `frame` messages at a configurable FPS carrying base64 JPEG screenshots
- `cursor` messages showing where each active participant's pointer is

### 5.2 Control arbitration

At any moment a session has exactly one **driver** — the participant currently allowed to submit actions. Drivers are identified by their capability token. To hand off control:

1. The current driver calls `POST /api/v1/sessions/<id>/release`.
2. Any waiting participant can call `POST /api/v1/sessions/<id>/claim` with its capability token.
3. The daemon assigns the driver role and broadcasts a `driver_changed` event.

This is intentionally simple. Phase 1 will add cooperative modes (agent and human drive simultaneously with locking on DOM subtrees).

## 6. Failure and recovery

- Playwright crashes: the daemon marks the session `failed`, broadcasts a terminal event, and releases resources. Clients must create a new session.
- Anunix unreachable: the bridge enters degraded mode. It queues State Object writes in memory and retries with exponential backoff. Actions still work; they are just not yet recorded. A `bridge_degraded` event is broadcast.
- Daemon crash: sessions are lost. Recordings, if enabled, are persisted to Anunix incrementally and can be replayed.

## 7. Threat model

- **Untrusted pages** run inside Chromium's sandbox. Standard CDP exposure.
- **Untrusted agents** are constrained by their capability token. The daemon refuses verbs not listed in the token.
- **Untrusted clients on the stream** are read-only by default. Control requires a token.
- **Credential exfiltration** is mitigated by keeping credentials in the Anunix credential store, not in the daemon's memory beyond the scope of a single request.

Phase 0 does not implement token signature verification. Running the daemon on an untrusted network in Phase 0 is unsafe.

## 8. Why Python

The Anunix kernel is C + assembly. The Anunix-Browser daemon is userland and has no kernel interface requirements; it talks to Anunix over HTTP like any other userland process. Python gives us Playwright, asyncio, and fast iteration. If profiling reveals a hot path we can't fix in Python, the hot path can be moved to a C helper and linked via a native extension.

## 9. File layout

| Path                          | Role                                                |
|-------------------------------|-----------------------------------------------------|
| `anxbrowser/server.py`        | Entry point; HTTP + WS routing                      |
| `anxbrowser/session.py`       | Session and event bus                               |
| `anxbrowser/handlers/`        | One file per protocol endpoint group                |
| `anxbrowser/bridge/`          | Anunix HTTP client and State Object helpers         |
| `anxbrowser/protocol/`        | Schemas and validation                              |
| `web/`                        | Collaborative UI (static HTML + JS)                 |
| `examples/`                   | Agent-driven and collaborative demos                |
| `tests/`                      | Unit tests                                          |

## 10. Open questions

- **Multi-page sessions.** Should a "session" be one BrowserContext (today) or one Page? Multi-page is natural for real browsing but complicates event streams. Current answer: one BrowserContext, one active Page, with `tab_open` / `tab_switch` verbs to be added.
- **Binary framing.** Screenshots at 10 FPS in base64 are heavy. WebSocket binary frames are the obvious upgrade; punted to Phase 1.
- **Offline replay.** Replaying a recorded session against a live target is subtle (the web changes). Initial replay target is a captured DOM snapshot, not a live re-fetch.
