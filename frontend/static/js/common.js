const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE
  ? String(window.APP_CONFIG.API_BASE)
  : ""
).replace(/\/$/, "");

async function apiGet(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function apiPatch(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `PATCH ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(API_BASE + path, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `DELETE ${path} failed: ${res.status}`);
  }
  return res.json();
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fmtRelative(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return fmtDate(iso);
}

function fmtDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "-";
  const total = Math.max(0, Math.round(Number(seconds)));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (!mins) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function sentimentBadge(sentiment) {
  const s = sentiment || "Neutral";
  const cls = s === "Bullish" ? "badge-bullish" : s === "Bearish" ? "badge-bearish" : "badge-neutral";
  const icon = s === "Bullish" ? "↑" : s === "Bearish" ? "↓" : "→";
  return `<span class="badge-sentiment ${cls}">${icon} ${s}</span>`;
}

function tags(list, max) {
  if (!list || !list.length) return `<span class="text-muted" style="font-size:.78rem">None</span>`;
  const show = max ? list.slice(0, max) : list;
  const rest = max && list.length > max ? list.length - max : 0;
  let html = show.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  if (rest) html += `<span class="tag text-muted">+${rest}</span>`;
  return html;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function thumbFallback(url) {
  return url || "https://placehold.co/640x360/141820/4f7cff?text=Reel";
}

function avatarLetter(name) {
  if (!name) return "?";
  return name.replace(/^@/, "").charAt(0).toUpperCase();
}
