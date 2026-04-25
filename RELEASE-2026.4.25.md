# Anunix-Browser 2026.4.25

Release date: 2026-04-25

## Summary

Maintenance release. Merges the 2026.4.24 feature batch into `main` via PR #2
and declares the daemon stable for the current OS integration sprint.
No new runtime features; test suite and protocol schema are the release
artifacts for this checkpoint.

## Status

- **Test suite**: 46 tests passing (pytest, asyncio_mode=auto)
- **Python**: 3.11+, aiohttp 3.x, Playwright
- **Protocol version**: v1 (stable)
- **Branch**: `main` @ `cd00839`

## Included since 2026.4.19

All items from the [2026.4.24 release](RELEASE-2026.4.24.md) are included:

- WebSocket input forwarding (`click`, `keydown`, `scroll`, `pii_response`)
- Form submit endpoint (`POST /api/v1/sessions/{sid}/submit`)
- `validate_submit` protocol schema with full test coverage
- Aether design system applied to web and desktop UIs
- CORS middleware, desktop app shell, scrollwheel forwarding

## Known limitations

- Playwright-based rendering (Lite mode); native C engine integration
  is tracked in the Anunix kernel repo
- `hwd`/`celf` userland tools and QMP VM backend are kernel-side only;
  no daemon-level VM management API yet
- `stubs` and `push` subcommands in `hwd` are not yet implemented

## Next

Development pauses on the browser daemon while OS-level work continues.
The next browser release will target native engine integration once the
kernel browser driver (`kernel/drivers/browser/`) reaches parity with
the Playwright baseline.
