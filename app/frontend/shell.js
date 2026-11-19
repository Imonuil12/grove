// App shell: sidebar (desktop), tab bar (phones), and the top bar with the account.
// Each app page has <body data-page="..."> and a <main id="page"> with its content.
import { displayName, esc, icon, isGuest, requireSignIn, signOut } from "./core.js";

export const NAV = [
  { key: "today", label: "Today", href: "today.html" },
  { key: "habits", label: "Habits", href: "habits.html", soon: true },
  { key: "books", label: "Books", href: "books.html", soon: true },
  { key: "training", label: "Training", href: "training.html", soon: true },
  { key: "coach", label: "Coach", href: "coach.html" },
  { key: "feed", label: "Feed", href: "feed.html", soon: true },
  { key: "profile", label: "Profile", href: "profile.html" },
];
const TABS = ["today", "habits", "books", "training", "coach"];

export function mountShell() {
  if (!requireSignIn()) return false;
  const current = document.body.dataset.page;
  const page = document.getElementById("page");
  const link = (item, cls) => `<a class="${cls}" href="${item.href}"${item.key === current ? ' aria-current="page"' : ""}>
      ${icon(item.key)}<span>${item.label}</span>${cls === "nav-link" && item.soon ? '<span class="soon">Soon</span>' : ""}</a>`;
  const name = displayName();
  const shell = document.createElement("div");
  shell.className = "shell";
  shell.innerHTML = `
    <aside class="sidebar" aria-label="Main">
      <a class="brand" href="today.html"><img src="assets/grove-mark.svg" alt=""> Grove</a>
      <nav>${NAV.map((n) => link(n, "nav-link")).join("")}</nav>
      <div class="sidebar-foot">Every feature is backed by research. <a href="research.html">See the studies</a></div>
    </aside>
    <div class="main">
      <header class="topbar">
        <strong>${esc(NAV.find((n) => n.key === current)?.label || "Grove")}</strong>
        <div class="who">
          ${isGuest() ? '<span class="guest-pill" title="Guest data is temporary">Guest</span>' : ""}
          <a href="profile.html" class="avatar" title="${esc(name)}">${esc(name.charAt(0))}</a>
          <button class="btn btn-ghost" type="button" id="signOut" title="Sign out">${icon("logout", 16)}<span class="visually-hidden">Sign out</span></button>
        </div>
      </header>
    </div>
    <nav class="tabbar" aria-label="Main">${NAV.filter((n) => TABS.includes(n.key)).map((n) => link(n, "")).join("")}</nav>`;
  page.replaceWith(shell);
  shell.querySelector(".main").appendChild(page);
  shell.querySelector("#signOut").addEventListener("click", signOut);
  return true;
}

// Theme preference (system / light / dark), applied before paint by each page's inline snippet.
export function setTheme(value) {
  try { value === "system" ? localStorage.removeItem("grove:theme") : localStorage.setItem("grove:theme", value); } catch (e) { /* storage blocked */ }
  if (value === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", value);
}
