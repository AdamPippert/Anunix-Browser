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

document.addEventListener("mousemove", (e) => {
  if (!STATE.ws || STATE.ws.readyState !== 1) return;
  const img = $("#frame");
  if (!img) return;
  const rect = img.getBoundingClientRect();
  if (e.clientX < rect.left || e.clientX > rect.right) return;
  if (e.clientY < rect.top || e.clientY > rect.bottom) return;
  const xr = (e.clientX - rect.left) / rect.width;
  const yr = (e.clientY - rect.top) / rect.height;
  STATE.ws.send(JSON.stringify({
    type: "cursor",
    actor: STATE.actor,
    x: Math.round(xr * (img.naturalWidth || rect.width)),
    y: Math.round(yr * (img.naturalHeight || rect.height)),
  }));
});

refreshHealth();
refreshSessions();
setInterval(refreshHealth, 4000);
setInterval(refreshSessions, 5000);
