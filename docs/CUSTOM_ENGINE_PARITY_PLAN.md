# Custom Engine Parity Plan (C/ASM-first)

Goal: use Chromium/Firefox for compatibility and performance baselines, while building a custom Anunix-native browser core.

## Constraints

- Core runtime target: C + ASM where practical.
- JS/TS/WASM allowed for extension layers, scripting, and optional feature modules.
- Chromium/Firefox are benchmark references, not long-term substitutes.

## Architecture decomposition

1) Control Plane (existing, keep)
- ANX-Browser Protocol (REST + WS)
- capabilities, session ownership, event model
- Anunix bridge/state-object provenance

2) Engine Adapter Interface (stabilize now)
- `navigate(url, wait_until)`
- `observe(mode)`
- `click(selector)`
- `type(text, selector)`
- `scroll(dx, dy|selector)`
- `eval(js)`
- `screenshot()`

3) Baseline Adapters (now)
- Chromium adapter (Playwright-backed)
- Firefox adapter (Playwright-backed)

4) Custom Core (build)
- parser + DOM tree + style/layout pipeline (incremental milestones)
- networking stack integration (reuse hardened libs where needed)
- rendering and compositing path
- input/event dispatch

## Feature parity strategy

Use an explicit parity matrix per verb and behavior class:

- Navigation semantics (`load`, `domcontentloaded`, redirects)
- Selector behavior and action success rates
- Form interactions and keyboard events
- Scrolling behavior
- JS evaluation correctness subset
- Screenshot fidelity at target resolutions

Each matrix row must be testable against:
- Chromium baseline
- Firefox baseline
- Custom engine implementation

## Performance baseline strategy

For each workload profile:
- lightweight docs (news/article)
- app-like SPA
- form-heavy pages

Track:
- time-to-first-observe
- navigate p50/p95 latency
- observe payload size
- Python-side memory and engine process RSS where measurable

Custom engine acceptance should be framed as:
- parity threshold met (functional)
- resource target met (memory + latency)

## Near-term coding priorities

1) Keep protocol stable while swapping backends.
2) Continue reducing DOM transfer costs (default light descriptor mode is now implemented).
3) Add explicit parity test fixtures and baseline capture scripts.
4) Define C ABI for future engine adapter so Python daemon can host custom engine incrementally.

## Definition of done for “baseline-ready”

- Chromium + Firefox run the same protocol test corpus.
- Results are captured and diffable.
- Custom engine can plug into the same adapter contract and report gaps via the same corpus.

This keeps engineering pressure on custom implementation while preventing regressions against current web behavior.
