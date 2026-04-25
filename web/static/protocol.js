/*
 * protocol.js — ANX-Browser Protocol transport helpers.
 *
 * Set window.ANXB_BASE before loading this script to point at a remote daemon.
 * Default '' = same-origin, works when the page is served by anxbrowserd.
 *
 * Desktop:  window.ANXB_BASE = 'http://localhost:9191';  (set via init.js)
 */

window.ANXB_BASE = window.ANXB_BASE || '';

function apiFetch(path, opts) {
  return fetch(window.ANXB_BASE + path, opts);
}

function apiWsUrl(path) {
  const base = window.ANXB_BASE;
  if (base) return base.replace(/^http(s?)/, 'ws$1') + path;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return proto + '//' + location.host + path;
}
