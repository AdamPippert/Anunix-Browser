/*
 * Anunix-Browser collaborative viewer.
 *
 * Vanilla JS, no build step. Requires protocol.js loaded first
 * (provides apiFetch, apiWsUrl, window.ANXB_BASE).
 *
 * Extensible via optional window callbacks:
 *   onSessionCreated(sid)     — after createSession() succeeds
 *   onAttach(sid)             — after attach() opens a WebSocket
 *   onSessionsRefreshed(list) — after refreshSessions() fetches the list
 *   onBrowserEvent(msg)       — for every non-frame WebSocket message
 */

const STATE = {
  sessionId: null,
  ws: null,
  actor: `human:${Math.random().toString(36).slice(2, 8)}`,
};

const $ = (sel) => document.querySelector(sel);

async function refreshHealth() {
  try {
    const r = await apiFetch("/api/v1/health");
    const j = await r.json();
    const el = $("#status");
    if (el) el.textContent = `${j.sessions} session${j.sessions === 1 ? "" : "s"}`;
    const ind = $("#bridge-indicator");
    if (ind) {
      // "degraded" just means no Anunix OS instance is running — normal for desktop use.
      if (j.bridge === "connected") {
        ind.textContent = "anunix ●";
        ind.style.color = "var(--ax-ok)";
      } else if (j.bridge === "disabled") {
        ind.textContent = "";
      } else {
        ind.textContent = "anunix ○";
        ind.style.color = "var(--ax-ink-400)";
      }
    }
  } catch {
    const el = $("#status");
    if (el) el.textContent = "daemon unreachable";
  }
}

async function refreshSessions() {
  try {
    const r = await apiFetch("/api/v1/sessions");
    const j = await r.json();
    const sessions = j.sessions || [];
    const ul = $("#sessions");
    if (ul) {
      ul.innerHTML = "";
      for (const s of sessions) {
        const active = s.session_id === STATE.sessionId;
        const li = document.createElement("li");
        li.className = active ? "session-active" : "";
        li.innerHTML = `<strong>${s.session_id.slice(0, 8)}</strong>
          <span class="ev-time">${new Date(s.created_at * 1000).toLocaleTimeString()}</span>
          ${s.current_url}<br>
          <span class="ev-time">driver: ${s.driver || "–"} | subs: ${s.subscribers}</span>`;
        li.addEventListener("click", () => attach(s.session_id));
        ul.appendChild(li);
      }
    }
    // Auto-attach when there's exactly one session and we're not watching anything.
    if (!STATE.sessionId && sessions.length === 1) attach(sessions[0].session_id);
    if (typeof onSessionsRefreshed === "function") onSessionsRefreshed(sessions);
  } catch {}
}

async function createSession() {
  try {
    const r = await apiFetch("/api/v1/sessions", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({headless: true}),
    });
    if (!r.ok) {
      const txt = await r.text();
      pushEvent({kind: "error", payload: {msg: "create session failed", status: r.status, body: txt}});
      return;
    }
    const j = await r.json();
    if (!j.session_id) {
      pushEvent({kind: "error", payload: {msg: "daemon returned no session_id"}});
      return;
    }
    attach(j.session_id);
    refreshSessions();
    if (typeof onSessionCreated === "function") onSessionCreated(j.session_id);
  } catch (err) {
    pushEvent({kind: "error", payload: {msg: "create session error", detail: String(err)}});
  }
}

function attach(sid) {
  if (STATE.ws) {
    try { STATE.ws.close(); } catch {}
  }
  STATE.sessionId = sid;
  const ws = new WebSocket(apiWsUrl(`/api/v1/sessions/${sid}/stream`));
  STATE.ws = ws;

  ws.onopen = () => {
    pushEvent({kind: "connected", payload: {sid}});
    ws.send(JSON.stringify({type: "hello", actor: STATE.actor, role: "viewer"}));
  };
  ws.onmessage = (m) => {
    let msg;
    try { msg = JSON.parse(m.data); } catch { return; }
    if (msg.type === "frame") {
      const frame = $("#frame");
      if (frame) frame.src = `data:${msg.mime};base64,${msg.data_b64}`;
      const splash = $("#no-session");
      if (splash) splash.style.display = "none";
    } else if (msg.type === "event") {
      pushEvent({kind: msg.kind, payload: msg.payload, seq: msg.seq, ts: msg.ts});
      if (msg.kind === "cursor") placeCursor(msg.payload);
      if (msg.kind === "pii_warning") showPiiWarning(msg.payload, ws);
      if (typeof onBrowserEvent === "function") onBrowserEvent(msg);
    }
  };
  ws.onerror = (e) => pushEvent({kind: "error", payload: {msg: "WebSocket error", sid}});
  ws.onclose = () => pushEvent({kind: "disconnected", payload: {}});
  if (typeof onAttach === "function") onAttach(sid);
}

function pushEvent(e) {
  const ol = $("#events");
  if (!ol) return;
  const li = document.createElement("li");
  const time = new Date().toLocaleTimeString();
  li.innerHTML = `<span class="ev-time">${time}</span>
    <span class="ev-kind">${e.kind}</span>
    <span>${JSON.stringify(e.payload || {})}</span>`;
  ol.insertBefore(li, ol.firstChild);
  while (ol.children.length > 200) ol.removeChild(ol.lastChild);
}

function placeCursor(p) {
  const layer = $("#cursor-layer");
  if (!layer) return;
  let c = layer.querySelector(`.cursor[data-actor="${p.actor}"]`);
  if (!c) {
    c = document.createElement("div");
    c.className = "cursor";
    c.dataset.actor = p.actor;
    layer.appendChild(c);
  }
  const img = $("#frame");
  const rect = img.getBoundingClientRect();
  const layerRect = layer.getBoundingClientRect();
  const sx = rect.width / (img.naturalWidth || rect.width);
  const sy = rect.height / (img.naturalHeight || rect.height);
  c.style.left = `${(rect.left - layerRect.left) + p.x * sx}px`;
  c.style.top = `${(rect.top - layerRect.top) + p.y * sy}px`;
}

async function apiPost(path, body) {
  const r = await apiFetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    const txt = await r.text();
    pushEvent({kind: "error", payload: {status: r.status, body: txt}});
    return null;
  }
  return await r.json();
}

// Wire buttons — null-guarded so the same file works in web and desktop HTML.
const _newSession = $("#new-session");
if (_newSession) _newSession.addEventListener("click", createSession);

const _navigateBtn = $("#navigate-btn");
if (_navigateBtn) _navigateBtn.addEventListener("click", async () => {
  if (!STATE.sessionId) {
    pushEvent({kind: "info", payload: {msg: "no active session — create one first"}});
    return;
  }
  const url = ($("#url-input")?.value || "").trim() || "https://example.com";
  _navigateBtn.disabled = true;
  _navigateBtn.textContent = "…";
  try {
    await apiPost(`/api/v1/sessions/${STATE.sessionId}/navigate`, {url});
  } finally {
    _navigateBtn.disabled = false;
    _navigateBtn.textContent = _navigateBtn.dataset.label || "Navigate";
  }
});

const _observeBtn = $("#observe-btn");
if (_observeBtn) _observeBtn.addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/observe`, {});
});

const _claimBtn = $("#claim-btn");
if (_claimBtn) _claimBtn.addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/claim`, {});
});

const _releaseBtn = $("#release-btn");
if (_releaseBtn) _releaseBtn.addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/release`, {});
});

/* ── Pointer helpers ──────────────────────────────────────────────── */

function _pageCoords(e) {
  const img  = $("#frame");
  if (!img) return null;
  const rect = img.getBoundingClientRect();
  if (e.clientX < rect.left || e.clientX > rect.right) return null;
  if (e.clientY < rect.top  || e.clientY > rect.bottom) return null;
  return {
    x: Math.round((e.clientX - rect.left) / rect.width  * (img.naturalWidth  || rect.width)),
    y: Math.round((e.clientY - rect.top)  / rect.height * (img.naturalHeight || rect.height)),
  };
}

document.addEventListener("mousemove", (e) => {
  if (!STATE.ws || STATE.ws.readyState !== 1) return;
  const coords = _pageCoords(e);
  if (!coords) return;
  STATE.ws.send(JSON.stringify({type: "cursor", actor: STATE.actor, ...coords}));
});

document.addEventListener("click", (e) => {
  if (!STATE.ws || STATE.ws.readyState !== 1) return;
  const coords = _pageCoords(e);
  if (!coords) return;
  STATE.ws.send(JSON.stringify({type: "click", ...coords}));
  /* Capture keyboard input to the frame element so keydown fires */
  const frame = $("#frame");
  if (frame) { frame.tabIndex = 0; frame.focus(); }
});

document.addEventListener("keydown", (e) => {
  if (!STATE.ws || STATE.ws.readyState !== 1) return;
  /* Only forward keys when the frame (or body) has focus */
  const frame = $("#frame");
  if (frame && document.activeElement !== frame &&
      document.activeElement !== document.body) return;
  /* Don't forward browser shortcuts */
  if (e.ctrlKey || e.metaKey) return;
  STATE.ws.send(JSON.stringify({type: "keydown", key: e.key, code: e.code}));
});

/* ── PII warning modal ─────────────────────────────────────────── */

function showPiiWarning(payload, ws) {
  const existing = document.getElementById("pii-modal");
  if (existing) existing.remove();

  const domain = payload.domain || "this page";
  const types  = payload.types  || "unknown";

  const modal = document.createElement("div");
  modal.id = "pii-modal";
  modal.innerHTML = `
    <div class="pii-backdrop"></div>
    <div class="pii-dialog">
      <div class="pii-icon">⚠</div>
      <h3>PII Detected</h3>
      <p>An agent is accessing <strong>${domain}</strong>, which contains
         personally identifiable information.</p>
      <p class="pii-types">Detected: <code>${types}</code></p>
      <p class="pii-note">The agent received redacted content.
         You can allow the original below.</p>
      <div class="pii-actions">
        <button class="pii-btn pii-redact" data-action="redact_once">
          Keep Redacted
        </button>
        <button class="pii-btn pii-bypass" data-action="bypass_once">
          Allow Once
        </button>
        <button class="pii-btn pii-always" data-action="bypass_always">
          Always Allow ${domain}
        </button>
      </div>
    </div>`;

  const style = document.createElement("style");
  style.textContent = `
    .pii-backdrop {
      position:fixed; inset:0; background:rgba(11,26,43,.55);
      backdrop-filter:blur(4px); z-index:9998;
    }
    .pii-dialog {
      position:fixed; top:50%; left:50%;
      transform:translate(-50%,-50%);
      background:#fdfcf9; border-radius:10px;
      padding:28px 32px; width:420px; max-width:90vw;
      box-shadow:0 8px 40px rgba(11,26,43,.35);
      font-family:Inter,sans-serif; z-index:9999;
      border:1px solid rgba(14,35,56,.12);
    }
    .pii-icon { font-size:2rem; text-align:center; margin-bottom:8px; }
    .pii-dialog h3 {
      margin:0 0 10px; font-size:1.1rem; font-weight:600;
      color:#0e2338; text-align:center;
    }
    .pii-dialog p { font-size:.875rem; color:#1a2733; margin:0 0 8px; }
    .pii-types code {
      background:#efece6; padding:2px 6px; border-radius:4px;
      font-family:'JetBrains Mono',monospace; font-size:.8rem;
    }
    .pii-note { color:#6b7280; font-size:.8rem; margin-top:4px; }
    .pii-actions {
      display:flex; flex-direction:column; gap:8px; margin-top:18px;
    }
    .pii-btn {
      padding:9px 14px; border-radius:6px; border:none; cursor:pointer;
      font-family:Inter,sans-serif; font-size:.875rem; font-weight:500;
      transition:opacity .15s;
    }
    .pii-btn:hover { opacity:.85; }
    .pii-redact  { background:#efece6; color:#1a2733; }
    .pii-bypass  { background:#1d4470; color:#fff; }
    .pii-always  { background:linear-gradient(135deg,#163454,#3a94a6);
                   color:#fff; }
  `;
  document.head.appendChild(style);
  document.body.appendChild(modal);

  modal.querySelectorAll(".pii-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({type: "pii_response", action}));
      }
      modal.remove();
      style.remove();
      if (action !== "redact_once") {
        pushEvent({kind: "pii_bypassed",
                   payload: {domain, action}});
      }
    });
  });

  pushEvent({kind: "pii_warning",
             payload: {domain, types}});
}

refreshHealth();
refreshSessions();
setInterval(refreshHealth, 4000);
setInterval(refreshSessions, 5000);
