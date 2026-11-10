// Turns Luma scanner output into results for Reachy. Shared by the extension and node tests.
(function (root) {
  const EXPRESS = /^https:\/\/api\.luma\.com\/event\/admin\/check-in\/express(\?|$)/;
  const TICKET = /^https:\/\/(www\.)?(luma\.com|lu\.ma)\/check-in\//;
  const LUMA_LINK = /^https:\/\/(www\.)?(luma\.com|lu\.ma)\//;

  // Luma's Express check-in API response -> {kind, name} | null (null = not a scan result).
  function parseScanResponse(url, status, body) {
    if (!EXPRESS.test(url || "")) return null;
    let data = null;
    try { data = JSON.parse(body); } catch (_) {}
    const name = (data && data.guest && typeof data.guest.name === "string" && data.guest.name.trim()) || null;
    if (status === 200 && data && data.status === "success") return { kind: "success", name };
    if (status === 200 && data && data.status === "already-checked-in") return { kind: "already", name };
    return { kind: "failure", name };
  }

  // A QR code Chrome saw in the camera -> "wrong_code" if it's a Luma link that isn't a ticket.
  function classifySeenCode(text) {
    if (LUMA_LINK.test(text || "") && !TICKET.test(text)) return "wrong_code";
    return null;
  }

  root.ReachyParse = { parseScanResponse, classifySeenCode };
  if (typeof module !== "undefined") module.exports = root.ReachyParse;
})(typeof globalThis !== "undefined" ? globalThis : this);
