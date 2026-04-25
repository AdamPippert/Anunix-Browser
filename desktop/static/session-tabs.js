/*
 * session-tabs.js — Tab strip for the Anunix Browser desktop UI.
 *
 * Hooks into app.js via window callbacks (defined below):
 *   onSessionCreated(sid)     — called when createSession() creates a new session
 *   onAttach(sid)             — called when attach() connects to a session
 *   onSessionsRefreshed(list) — called by refreshSessions() with the sessions array
 *
 * Depends on: protocol.js (apiFetch), app.js (STATE, attach, createSession)
 */

const TABS = { sessions: [], activeSid: null };

function renderTabs() {
  const bar = document.getElementById("tab-bar");
  if (!bar) return;
  bar.querySelectorAll(".tab").forEach((t) => t.remove());
  const newBtn = bar.querySelector(".tab-new");

  for (const { sid, title } of TABS.sessions) {
    const tab = document.createElement("button");
    tab.className = "tab" + (sid === TABS.activeSid ? " tab-active" : "");
    tab.dataset.sid = sid;
    tab.title = sid;
    tab.innerHTML =
      `<span class="tab-title">${title || sid.slice(0, 8)}</span>` +
      `<span class="tab-close" data-sid="${sid}">&#x2715;</span>`;
    tab.addEventListener("click", (e) => {
      if (e.target.classList.contains("tab-close")) {
        closeTab(e.target.dataset.sid);
      } else {
        attach(sid);
      }
    });
    bar.insertBefore(tab, newBtn);
  }
}

function closeTab(sid) {
  apiFetch(`/api/v1/sessions/${sid}`, { method: "DELETE" }).catch(() => {});
  TABS.sessions = TABS.sessions.filter((s) => s.sid !== sid);
  if (TABS.activeSid === sid) {
    const next = TABS.sessions[TABS.sessions.length - 1];
    if (next) attach(next.sid);
    else {
      TABS.activeSid = null;
      const splash = document.getElementById("no-session");
      if (splash) splash.style.display = "";
    }
  }
  renderTabs();
}

window.onSessionCreated = function (sid) {
  if (!TABS.sessions.find((s) => s.sid === sid))
    TABS.sessions.push({ sid, title: "new tab" });
  TABS.activeSid = sid;
  renderTabs();
};

window.onAttach = function (sid) {
  if (!TABS.sessions.find((s) => s.sid === sid))
    TABS.sessions.push({ sid, title: sid.slice(0, 8) });
  TABS.activeSid = sid;
  renderTabs();
};

window.onSessionsRefreshed = function (sessions) {
  const ids = sessions.map((s) => s.session_id);
  // Remove stale tabs
  TABS.sessions = TABS.sessions.filter((t) => ids.includes(t.sid));
  // Add tabs for new sessions that appeared on the daemon
  for (const s of sessions) {
    if (!TABS.sessions.find((t) => t.sid === s.session_id))
      TABS.sessions.push({ sid: s.session_id, title: s.session_id.slice(0, 8) });
  }
  renderTabs();
};

// "+" button
const _newTabBtn = document.getElementById("new-tab");
if (_newTabBtn) _newTabBtn.addEventListener("click", () => createSession());
