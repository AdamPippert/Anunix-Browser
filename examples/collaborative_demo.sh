#!/usr/bin/env bash
#
# collaborative_demo.sh — spin up the daemon, open the collaborative UI, and
# run an agent that drives a session a human can watch live.
#
# Usage:
#   ./examples/collaborative_demo.sh [URL]
#
# The daemon is assumed to be installed via `make deps`.

set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

URL="${1:-https://example.com/}"
PORT="${ANXB_PORT:-9090}"

if ! curl -fs "http://127.0.0.1:${PORT}/api/v1/health" >/dev/null 2>&1; then
    echo "[demo] starting anxbrowserd on port ${PORT}"
    # shellcheck disable=SC1091
    source .venv/bin/activate 2>/dev/null || true
    python3 -m anxbrowser.server &
    DAEMON_PID=$!
    trap 'kill ${DAEMON_PID} 2>/dev/null || true' EXIT
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if curl -fs "http://127.0.0.1:${PORT}/api/v1/health" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi

UI_URL="http://127.0.0.1:${PORT}/"
echo "[demo] collaborative UI: ${UI_URL}"

case "$(uname -s)" in
    Darwin) open "${UI_URL}" ;;
    Linux) xdg-open "${UI_URL}" >/dev/null 2>&1 || true ;;
esac

sleep 2
echo "[demo] running agent against ${URL}"
python3 examples/agent_session.py "${URL}"

echo "[demo] agent finished; daemon still running for manual exploration"
echo "[demo] press Ctrl-C to stop"
wait
