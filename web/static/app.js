/*
 * Anunix-Browser collaborative viewer.
 *
 * Vanilla JS intentionally — no build step. This file talks to the daemon
 * over the same ANX-Browser Protocol any agent would use.
 */

const STATE = {
  sessionId: null,
  ws: null,
  actor: `human:${Math.random().toString(36).slice(2, 8)}`,
};

const $ = (sel) => document.querySelector(sel);

async function refreshHealth() {
  try {
    const r = await fetch("/api/v1/health");
    const j = await r.json();
    $("#status").textContent = `sessions:${j.sessions}`;
    const ind = $("#bridge-indicator");
    ind.textContent = `anunix bridge: ${j.bridge}`;
    ind.style.color = j.bridge === "connected" ? "var(--ok)"
      : j.bridge === "degraded" ? "var(--warn)" : "var(--muted)";
  } catch (e) {
    $("#status").textContent = "daemon unreachable";
  }
}

async function refreshSessions() {
  const r = await fetch("/api/v1/sessions");
  const j = await r.json();
  const ul = $("#sessions");
  ul.innerHTML = "";
  for (const s of j.sessions || []) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${s.session_id}</strong><br>
      <span class="ev-time">${new Date(s.created_at * 1000).toLocaleTimeString()}</span>
      ${s.current_url}<br>
      <span class="ev-time">driver: ${s.driver || "-"} | subs: ${s.subscribers}</span>`;
    li.addEventListener("click", () => attach(s.session_id));
    ul.appendChild(li);
  }
}

async function createSession() {
  const r = await fetch("/api/v1/sessions", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({headless: true}),
  });
  const j = await r.json();
  attach(j.session_id);
  refreshSessions();
}

function attach(sid) {
  if (STATE.ws) {
    try { STATE.ws.close(); } catch {}
  }
  STATE.sessionId = sid;
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/api/v1/sessions/${sid}/stream`);
  STATE.ws = ws;

  ws.onopen = () => {
    pushEvent({kind: "connected", payload: {sid}});
    ws.send(JSON.stringify({type: "hello", actor: STATE.actor, role: "viewer"}));
  };
  ws.onmessage = (m) => {
    let msg;
    try { msg = JSON.parse(m.data); } catch { return; }
    if (msg.type === "frame") {
      $("#frame").src = `data:${msg.mime};base64,${msg.data_b64}`;
    } else if (msg.type === "event") {
      pushEvent({kind: msg.kind, payload: msg.payload, seq: msg.seq, ts: msg.ts});
      if (msg.kind === "cursor") placeCursor(msg.payload);
    }
  };
  ws.onclose = () => pushEvent({kind: "disconnected", payload: {}});
}

function pushEvent(e) {
  const ol = $("#events");
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
  const r = await fetch(path, {
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

$("#new-session").addEventListener("click", createSession);
$("#navigate-btn").addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  const url = $("#url-input").value.trim() || "https://example.com";
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/navigate`, {url});
});
$("#observe-btn").addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/observe`, {});
});
$("#claim-btn").addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/claim`, {});
});
$("#release-btn").addEventListener("click", async () => {
  if (!STATE.sessionId) return;
  await apiPost(`/api/v1/sessions/${STATE.sessionId}/release`, {});
});

document.addEventListener("mousemove", (e) => {
  if (!STATE.ws || STATE.ws.readyState !== 1) return;
  const img = $("#frame");
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
