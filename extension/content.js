// Isolated-world script: turns Luma scanner results into /scan events for Reachy.
// DEBUG = true also records page text and raw API bodies to /debug (contains guest data; logs/ only).
const DEBUG = false;
const { parseScanResponse, classifySeenCode } = globalThis.ReachyParse;
const send = (msg) => { try { chrome.runtime.sendMessage(msg); } catch (_) {} };

window.addEventListener("message", (e) => {
  if (e.source !== window || e.data?.source !== "reachy-greeter") return;
  const d = e.data;
  if (d.type === "api") {
    if (DEBUG) send({ type: "debug", text: `API ${d.status} ${d.url}\n${d.body}` });
    const result = parseScanResponse(d.url, d.status, d.body);
    if (result) send({ type: "scan", ...result });
  } else if (d.type === "seen") {
    if (DEBUG) send({ type: "debug", text: `SEEN ${d.luma ? "luma" : "other"} ${d.text}` });
    if (!d.luma && classifySeenCode(d.text) === "wrong_code") send({ type: "scan", kind: "wrong_code", name: null });
  } else if (d.type === "debug") {
    send({ type: "debug", text: d.text });
  }
});

// Debug-only page-text recorder (used to discover Luma's result wording).
const recent = new Map();
function record(text) {
  text = (text || "").trim();
  if (!text || text.length > 500) return;
  const now = Date.now();
  if (now - (recent.get(text) || 0) < 2000) return;
  recent.set(text, now);
  send({ type: "debug", text: `TEXT ${text}` });
}

function start() {
  if (DEBUG) {
    new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type === "characterData") record(m.target.parentElement?.innerText);
        for (const n of m.addedNodes) record(n.nodeType === 1 ? n.innerText : n.textContent);
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  send({ type: "debug", text: `bridge loaded on ${location.pathname}${location.search}` });
}
if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
