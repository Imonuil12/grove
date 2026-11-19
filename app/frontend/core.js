// Shared helpers for every Grove page: API access, identity, evidence and icons.

// In production the backend serves these pages (same origin). Local static dev
// servers on ports 5500-5599 talk to a backend on port 8000.
export const BASE_URL = window.API_BASE_URL || (/^55\d\d$/.test(location.port)
  ? `http://${location.hostname || "127.0.0.1"}:8000`
  : location.origin);

// ---------- Identity ----------
// Guests are scoped to this browser tab (sessionStorage); accounts use localStorage.
export const isGuest = () => !!sessionStorage.getItem("guestToken");
export const hasAccount = () => !isGuest() && !!localStorage.getItem("idToken");
export const isSignedIn = () => isGuest() || hasAccount();
export const accountEmail = () => (hasAccount() ? localStorage.getItem("userEmail") : null);

export function displayName() {
  if (isGuest()) return "Guest";
  const email = accountEmail() || "";
  const local = email.split("@")[0].replace(/[._-]+/g, " ").trim();
  return local ? local.replace(/\b\w/g, (c) => c.toUpperCase()) : "Friend";
}

export async function startGuest(next = "today.html") {
  const res = await fetch(`${BASE_URL}/auth/guest`, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.token) throw new Error(data.detail || "Could not start a guest session.");
  sessionStorage.setItem("guestToken", data.token);
  sessionStorage.setItem("guestIdentity", data.username);
  location.href = safeNext(next);
}

export function signOut() {
  const token = sessionStorage.getItem("guestToken");
  if (token) fetch(`${BASE_URL}/auth/guest`, { method: "DELETE", headers: { "X-Guest-Session": token } }).catch(() => {});
  sessionStorage.clear();
  localStorage.removeItem("idToken");
  localStorage.removeItem("accessToken");
  localStorage.removeItem("userEmail");
  location.href = "index.html";
}

// Only same-site page names, so a crafted ?next= can't send people elsewhere.
export function safeNext(value) {
  return typeof value === "string" && /^[\w-]+\.html(\?[^#]*)?(#[\w-]*)?$/.test(value) ? value : "today.html";
}

export function requireSignIn() {
  if (isSignedIn()) return true;
  const here = location.pathname.split("/").pop() || "today.html";
  location.replace(`login.html?next=${encodeURIComponent(here + location.search)}`);
  return false;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (isGuest()) headers.set("X-Guest-Session", sessionStorage.getItem("guestToken"));
  else if (localStorage.getItem("idToken")) headers.set("Authorization", `Bearer ${localStorage.getItem("idToken")}`);
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 401 && isSignedIn()) {
    sessionStorage.clear();
    localStorage.removeItem("idToken");
    location.replace(`login.html?expired=1&next=${encodeURIComponent(location.pathname.split("/").pop())}`);
    throw new Error("Your session ended. Please sign in again.");
  }
  return res;
}

// ---------- Text ----------
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal, safe Markdown for coach replies: paragraphs, lists, bold, italics,
// and evidence IDs turned into links to the Research page.
export function renderMarkdown(text, knownIds = null) {
  const inline = (s) => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/\(?\b([A-Z]{2,4}-\d+)\b\)?/g, (m, id) => (!knownIds || knownIds.has(id)) ? `<a class="cite" href="research.html#${id}">${id}</a>` : m);
  const blocks = String(text || "").trim().split(/\n{2,}/);
  return blocks.map((block) => {
    const lines = block.split("\n");
    if (lines.every((l) => /^\s*[-*•]\s+/.test(l))) return `<ul>${lines.map((l) => `<li>${inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>`).join("")}</ul>`;
    if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) return `<ol>${lines.map((l) => `<li>${inline(l.replace(/^\s*\d+[.)]\s+/, ""))}</li>`).join("")}</ol>`;
    return `<p>${lines.map(inline).join("<br>")}</p>`;
  }).join("");
}

// ---------- Evidence ----------
let evidencePromise = null;
export function loadEvidence() {
  evidencePromise ||= fetch("data/evidence.json").then((r) => r.json()).then((d) => d.entries);
  return evidencePromise;
}

// "Why this works" panel: the research behind a feature, from the evidence library.
export async function renderWhy(container, ids, intro = "") {
  const entries = await loadEvidence();
  const byId = Object.fromEntries(entries.map((e) => [e.id, e]));
  const items = ids.map((id) => byId[id]).filter(Boolean);
  container.innerHTML = `
    <details class="card why">
      <summary><span class="card-icon tone-leaf">${icon("flask")}</span> Why this works</summary>
      ${intro ? `<p class="muted" style="margin-top:12px">${esc(intro)}</p>` : ""}
      <div class="why-list">
        ${items.map((e) => `
          <div class="why-item">
            <div><a class="cite" href="research.html#${e.id}">${e.id}</a> <span class="grade grade-${e.grade}">Grade ${e.grade}</span>
              <strong>${esc(e.title)}</strong></div>
            <p class="small">${esc(e.finding || e.use)}</p>
          </div>`).join("")}
      </div>
      <p class="small muted" style="margin:14px 0 0">Full citations are on the <a href="research.html">Research</a> page.</p>
    </details>`;
}

// ---------- Icons (Lucide-style, stroke = currentColor) ----------
const ICONS = {
  today: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  habits: '<path d="M12 22c4-3 7-6.5 7-11a7 7 0 0 0-14 0c0 4.5 3 8 7 11z"/><path d="m9 11 2 2 4-4"/>',
  books: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  training: '<path d="M6.5 6.5v11"/><path d="M17.5 6.5v11"/><path d="M3 9v6"/><path d="M21 9v6"/><path d="M6.5 12h11"/>',
  coach: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 1 1 21 11.5z"/>',
  feed: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10"/><path d="M7 13h10"/><path d="M7 17h6"/>',
  profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  flask: '<path d="M9 3h6"/><path d="M10 3v6L4.5 18.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3"/><path d="M7 15h10"/>',
  arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m6 6 2 2M16 16l2 2M6 18l2-2M16 8l2-2"/>',
  run: '<circle cx="13" cy="4" r="2"/><path d="m4 22 4-7 4 2 1 5"/><path d="M8 11l3-4 4 3 3 1"/><path d="M11 7l-1 6"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
};
export function icon(name, size = null) {
  const dims = size ? ` width="${size}" height="${size}"` : "";
  return `<svg viewBox="0 0 24 24"${dims} fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}
