// Relays messages from the content script to the local greeter app (pages can't reach localhost).
const BASE = "http://127.0.0.1:8765";
chrome.runtime.onMessage.addListener((msg) => {
  const path = msg?.type === "scan" ? "/scan" : msg?.type === "debug" ? "/debug" : null;
  if (!path) return;
  const body = msg.type === "scan" ? { kind: msg.kind, name: msg.name ?? null } : { text: msg.text };
  fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {});
});
