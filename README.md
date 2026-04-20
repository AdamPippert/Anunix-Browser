# Anunix-Browser

**A collaborative web browser for humans and AI agents, deeply integrated with the Anunix OS.**

Anunix-Browser is not just another headless browser. It is a shared workspace where a human and an AI agent inhabit the same session, see each other's actions in real time, and hand off control fluidly. Every page load, click, and observation is recorded as a State Object in Anunix, giving each browsing session full provenance, replayability, and first-class participation in the OS.

---

## Vision

Two forces are reshaping the browser:

1. **Agents need browsers.** Tools like Perplexity Computer and Browserbase treat the browser as a remote agent substrate — something the AI sees and drives on behalf of a user.
2. **Humans still need browsers.** The UI remains the primary interface to the open web.

Most projects pick a side. Anunix-Browser picks both.

- **Shared sessions** — a human and an agent can collaborate on the same tab, with a live cursor overlay and a visible event log.
- **Provenance-native** — every action is a State Object in Anunix, versioned and content-addressed. Sessions can be snapshotted, replayed, diffed.
- **Tensor-aware** — screenshots and DOM trees are stored as Tensor Objects so agents can compute embeddings, diffs, and visual similarities directly against the Anunix tensor engine.
- **Cell-scoped** — each browser session is an Execution Cell with capability-gated access. An agent can be granted "read page" without "submit form", and the kernel enforces it.
- **Open protocol** — ANX-Browser Protocol (see [`docs/PROTOCOL.md`](docs/PROTOCOL.md)) is a minimal REST + WebSocket spec designed from the start for multi-agent, human-in-the-loop use.

---

## Architecture at a glance

```
  +--------------------+       +---------------------+
  |   Human (web UI)   |       |   Agent (API/SDK)   |
  +----------+---------+       +----------+----------+
             |                            |
             |     ANX-Browser Protocol   |
             |    (REST + WebSocket)      |
             v                            v
        +-------------------------------------+
        |       anxbrowserd (this repo)       |
        |   - session manager                 |
        |   - action dispatcher               |
        |   - event broadcaster               |
        |   - Anunix bridge                   |
        +--------+---------------------+------+
                 |                     |
                 v                     v
       +------------------+   +-------------------+
       |    Playwright    |   |    Anunix HTTP    |
       |   (Chromium)     |   |   POST /api/v1/   |
       +------------------+   +-------------------+
```

- **anxbrowserd** is the daemon. It speaks ANX-Browser Protocol on the north side and drives Playwright on the south side.
- **Anunix bridge** turns every significant browser event into a State Object and records provenance via the Anunix HTTP API on port 8080.
- **Web UI** (served by the daemon) streams a live view of each session to any number of human observers.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased plan.

---

## Quickstart

### Prerequisites

- Python 3.10 or newer
- An Anunix instance running locally (optional for Phase 0 — the bridge falls back to a null sink if Anunix is unreachable)

### Install

```
make deps
```

This creates a local virtual environment under `.venv/`, installs Python dependencies, and downloads the Chromium build Playwright needs.

### Run

```
make run
```

The daemon starts on `http://127.0.0.1:9090`. Open the collaborative UI in a browser:

```
http://127.0.0.1:9090/
```

### Drive a session from an agent

```
python3 examples/agent_session.py
```

This script opens a session, navigates to a page, observes its title and visible text, captures a screenshot, and closes the session — all through the ANX-Browser Protocol.

### Share a session with a human

```
./examples/collaborative_demo.sh
```

Starts the daemon, opens the UI in your default browser, and kicks off an agent that drives a session you can watch live.

---

## Project layout

```
anxbrowser/          # Daemon source (Python)
  server.py          # HTTP + WebSocket entry point
  session.py         # Session manager
  handlers/          # Route handlers (sessions, actions, streaming)
  bridge/            # Anunix bridge (State Objects, Cells, Tensors)
  protocol/          # ANX-Browser Protocol schemas
docs/                # Architecture, protocol, roadmap
web/                 # Collaborative UI (static HTML/JS)
examples/            # Agent-driven and collaborative demos
tests/               # Unit tests
scripts/             # Dev scripts
```

---

## Status

**2026.4.19** — Native kernel streaming. anxbrowserd now serves binary JPEG frames directly to the Anunix kernel via `GET /api/v1/sessions/{sid}/stream_raw`, enabling graphical browser rendering on bare metal and in QEMU. The daemon binds `0.0.0.0` by default so the QEMU guest can connect at `10.0.2.2:9090`. Frame rate is ~30 FPS. Session viewport auto-sizes to match the Anunix framebuffer dimensions.

**Phase 0 — Foundation.** Daemon boots, sessions launch Playwright engines (Chromium and Firefox) with per-session engine selection, basic actions (navigate, click, type, observe, screenshot) work end to end, the collaborative UI streams live screenshots, and the Anunix bridge records actions as State Objects when Anunix is reachable.

See [`RELEASE-2026.4.19.md`](RELEASE-2026.4.19.md) for the latest release notes and [`docs/ROADMAP.md`](docs/ROADMAP.md) for what comes next.

---

## License

MIT. See [`LICENSE`](LICENSE).

---

## Relationship to Anunix

Anunix-Browser is a **userland** companion to Anunix. The Anunix kernel is strictly C and assembly; Anunix-Browser is Python because the value here is integration speed and Playwright ecosystem reach, not kernel-adjacent performance. When the Anunix userland libc (`libanx`) matures, a native C client for the ANX-Browser Protocol can be added without changing the daemon.
