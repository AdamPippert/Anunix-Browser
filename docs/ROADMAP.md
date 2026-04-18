# Anunix-Browser Roadmap

This roadmap is a living document. Each phase ends with demonstrable, tested functionality. No phase is "complete" until its examples run clean on a fresh machine.

## Phase 0 — Foundation (this release)

Goal: prove the shape. One human and one agent can share a session.

- [x] Project scaffold, license, docs skeleton
- [x] ANX-Browser Protocol v0.1 spec
- [x] Daemon with HTTP routes: create, navigate, observe, click, type, delete
- [x] WebSocket event stream
- [x] Playwright backend for Chromium
- [x] Anunix bridge stub with one working `POST /api/v1/exec` call
- [x] Collaborative UI: live screenshot viewer + event log + take-control button
- [x] Example agent script
- [x] Collaborative demo script
- [x] Unit tests for protocol schemas and session manager

Known gaps intentionally left for later:
- Capability tokens are not signature-verified.
- Screenshots ride the WebSocket as base64, not binary.
- Multi-tab is not supported (one page per session).
- Session recordings are not persisted.

## Phase 1 — Hardening

Goal: usable for real collaborative browsing by a single trusted user + agent.

- Capability token verification against Anunix capability service (RFC-0007).
- Binary WebSocket frames for screenshots.
- Multi-tab: `tab_open`, `tab_close`, `tab_switch` verbs.
- File download support; downloads materialize as State Objects.
- Session recording: every event + DOM snapshot persisted to Anunix.
- Deterministic replay against recorded DOMs.
- Rich DOM observation: canonical tree + stable element IDs.
- Screenshots uploaded as Tensor Objects once the tensor HTTP API is stable.
- Rate limiting and per-session quotas enforced via Cell metrics.
- Configurable persistent profiles per session (cookies, local storage).
- Packaged release: single static binary (where feasible) or `pipx`-installable package.

## Phase 2 — Multi-agent

Goal: two or more agents plus a human in the same session, safely.

- Cooperative driving: DOM subtree locks; an agent can claim a form while another reads.
- Per-verb capability scoping at the DOM level ("agent may click inside `#search-results` only").
- Observer channel: read-only agents receive events at reduced fidelity.
- Intent layer: a higher-level verb set (`search`, `fill_form`, `complete_checkout`) that expands to primitive actions with built-in observability.
- Audit trail: every action is attributable to an actor, persisted as a provenance edge on the State Object.
- Native C client for `libanx`: ANX-Browser Protocol callable from C userland without an HTTP detour.

## Phase 3 — Deep Anunix integration

Goal: Anunix-Browser becomes the primary browsing surface of Anunix, with kernel-level primitives.

- Browser sessions as first-class `anx` shell objects: `ansh browser list`, `ansh browser fork`.
- Execution Cells for browser sessions scheduled by the Anunix unified scheduler (RFC-0005).
- Page renders as tensor pipelines: agents compose `render -> embed -> search -> select` graphs via the routing plane (RFC-0005).
- Kernel-backed credential store fully wired: zero credential material touches userland memory outside a sealed cell.
- Offline browsing: State Objects can be served to an offline agent from the local Anunix store.
- Session fork as a first-class primitive: clone a browser state the way Unix forks a process.

## Phase 4 — Ecosystem

Goal: others can build on the protocol.

- Published protocol reference with JSON Schemas.
- Reference clients in Python, Go, TypeScript, and C.
- Compatibility test suite any ANX-Browser server must pass.
- Alternate backends: Firefox/Gecko, WebKit, and a minimal text-only backend for low-footprint agents.
- Hosted Anunix-Browser instance mode (multi-tenant) with resource accounting via Cells.

## Anti-goals

Things we will **not** do, unless strongly motivated:

- Build our own rendering engine.
- Add a plugin system before the core protocol is stable.
- Ship a desktop app wrapper (Electron/Tauri). The web UI is enough; native wrappers can come from the community.
- Target mobile browser automation in Phase 0 or 1.

## Success metrics per phase

- **Phase 0**: `make run` + `python3 examples/agent_session.py` works on a fresh Mac with only `make deps` run once.
- **Phase 1**: A 60-minute unattended agent session produces a complete, replayable recording and zero orphaned resources.
- **Phase 2**: Two agents + one human can interact with the same session for 15 minutes with no dropped events and no unauthorized actions.
- **Phase 3**: A browser session can be forked and replayed entirely inside Anunix with no external dependencies.
