# Browser Harness Integration Notes (2026-04-18)

This document maps `browser-use/browser-harness` to Anunix-Browser and identifies what can be directly incorporated vs what should remain reference-only.

## First-principles fit

Browser Harness is a very thin CDP relay focused on one goal: giving an LLM full control of a real browser with minimal abstraction.

Anunix-Browser has different core constraints:
- multi-actor collaboration (human + agent)
- capability-gated verbs
- Anunix provenance/state-object recording
- stable REST/WS protocol boundary

So: this is not a drop-in replacement architecture. It is a source of tactical patterns.

## Directly incorporable patterns

1) Session resiliency pattern
- Harness auto-recovers stale CDP sessions by re-attaching a target.
- Equivalent for Anunix-Browser: keep robust recovery hooks when a page/context is invalidated.
- Action: implement retry/recover wrappers around high-value operations (`navigate`, `observe`, `screenshot`) as needed.

2) Internal-page filtering and real-tab selection
- Harness avoids `chrome://`, `devtools://`, etc. to prevent attaching unusable targets.
- Equivalent for Anunix-Browser: if/when multi-tab lands, prefer non-internal tabs by default.

3) Minimal helper surface
- Harness keeps a tiny primitive API (`goto`, `click`, `type_text`, raw `cdp`).
- Equivalent for Anunix-Browser: keep protocol verbs small and composable; avoid framework bloat.

4) Fast setup ergonomics
- Harness has idempotent daemon startup and quick health checks.
- Equivalent for Anunix-Browser: keep startup predictable, clear diagnostics, and strict failure messages.

## Not directly incorporable (without architectural conflict)

1) Raw CDP single-browser model
- Harness assumes direct CDP control of Chrome.
- Anunix-Browser needs engine abstraction and cross-engine parity path (Chromium + Firefox now, custom engine later).

2) Agent-self-modifying helper file as core workflow
- Harness expects helpers.py to be edited live by the agent.
- Anunix-Browser needs stable protocol contracts and reproducible behavior for multi-agent governance.

3) Chrome-specific operational assumptions
- Harness lifecycle is heavily Chrome/DevToolsActivePort centric.
- Anunix-Browser must treat Chromium/Firefox as parity references, not permanent runtime dependency.

## Integration decision

Use Browser Harness as a tactical pattern library, not a foundation.

Adopt:
- resiliency patterns
- minimal API philosophy
- operational simplicity

Do not adopt:
- CDP-only architecture
- Chrome-only assumptions
- mutable helper-first control plane

## Immediate implementation already done in this repo

- Added explicit per-session `browser_engine` selection (`chromium`/`firefox`).
- Added low-memory DOM mode (`dom_snapshot_mode=light`) so bridge hashing does not require full HTML capture by default.
- Updated protocol and README to reflect these changes.

These changes make Chromium/Firefox useful as parity/perf baselines while keeping the design open for a custom engine core.
