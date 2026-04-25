/*
 * agent-panel.js — Agent status panel for the Anunix Browser desktop UI.
 *
 * Hooks into app.js via window.onBrowserEvent(msg).
 * Depends on: app.js (pushEvent)
 */

function updateDriverDisplay(driver) {
  const el = document.getElementById("driver-name");
  if (!el) return;
  el.textContent = driver || "none";
  el.className =
    "driver-value " +
    (!driver ? "driver-none" : driver.startsWith("agent:") ? "driver-agent" : "driver-human");
}

function pushActionFeed(msg) {
  // Skip high-frequency cursor noise
  if (msg.kind === "cursor") return;
  const feed = document.getElementById("action-feed");
  if (!feed) return;
  const li = document.createElement("li");
  const time = new Date().toLocaleTimeString();
  const detail = JSON.stringify(msg.payload || {});
  li.innerHTML =
    `<span class="ev-time">${time}</span>` +
    `<span class="ev-kind">${msg.kind}</span>` +
    `<span>${detail.length > 80 ? detail.slice(0, 80) + "…" : detail}</span>`;
  feed.insertBefore(li, feed.firstChild);
  while (feed.children.length > 40) feed.removeChild(feed.lastChild);
}

window.onBrowserEvent = function (msg) {
  if (msg.kind === "driver_change") {
    updateDriverDisplay(msg.payload?.driver ?? null);
  }
  pushActionFeed(msg);
};

updateDriverDisplay(null);
