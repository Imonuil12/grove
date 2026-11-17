// chat-core.js — shared chatbot engine for the full chatbot page (chatbot.html)
// and the floating widget (chat-widget.js).
//
// Needs script.js first (BASE_URL, apiFetch, getUsername, learningStorage,
// getSelectedDrug, escapeHtml, goToLesson).
//
// Backend endpoints used:
//   POST   /chat/stream                 streamed reply (NDJSON)
//   POST   /chat                        non-streaming fallback
//   GET    /chat/context/{drug}         learner snapshot + starter prompts
//   GET    /chat/history/{user}         messages of one conversation
//   GET    /conversations/{user}        conversation list
//   PATCH  /conversations/{id}          rename
//   DELETE /conversations/{id}          delete
(function () {
  "use strict";

  const ICONS = {
    send: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
    stop: '<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    retry: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.3L3 16"/><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
    path: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/>',
    clipboard: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  };

  const STYLES = [
    ["needs more explanations", "Needs more explanations"],
    ["the skeptic", "The Skeptic"],
    ["trying not to get worse", "Trying not to get worse"],
    ["all in until i'm not", "All in until I'm not"],
  ];
  const styleOptions = () => STYLES.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");

  const KIND_ICON = { review: "refresh", learn: "book", quiz: "target", profile: "user", safety: "shield" };

  function icon(name, size = 16) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
  }

  const esc = (s) => (typeof escapeHtml === "function" ? escapeHtml(s) : String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c])));

  // ------------------------------------------------------------------ markdown
  // Small, safe Markdown renderer: everything is escaped first, then a fixed
  // set of constructs is turned back into HTML.

  function inline(text) {
    let t = text;
    const codes = [];
    t = t.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
    t = t.replace(/\[([^\]]+)\]\(((?:https?:\/\/|[\w-]+\.html)[^\s)]*)\)/g, (_, label, href) =>
      `<a href="${href}"${/^https?:/.test(href) ? ' target="_blank" rel="noopener"' : ""}>${label}</a>`);
    t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/__(.+?)__/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, "$1<em>$2</em>");
    t = t.replace(/(^|[^_\w])_(?!\s)([^_]+?)_(?!\w)/g, "$1<em>$2</em>");
    t = t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
    return t;
  }

  // Legacy rule-based answers use emoji section titles ("💡 **Alternative Perspective:**").
  const CALLOUT = /^(💡|🎯|❓|🔍|🛡️|📌|📝|⚠️)\s*\*{0,2}([^*\n]{2,60}?):?\*{0,2}:?\s*$/u;
  const CALLOUT_TONE = { "💡": "idea", "🎯": "check", "❓": "check", "⚠️": "warn", "🛡️": "warn" };

  function renderMarkdown(src) {
    const lines = esc(String(src || "").replace(/\r\n?/g, "\n")).split("\n");
    const out = [];
    let i = 0;

    const isBlockStart = (l) => /^\s*([-*•]\s+|\d+[.)]\s+|#{1,4}\s|&gt;\s?|```|---+\s*$)/.test(l) || CALLOUT.test(l.trim());

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) { i++; continue; }

      if (trimmed.startsWith("```")) {
        const buf = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith("```")) buf.push(lines[i++]);
        i++;
        out.push(`<pre><code>${buf.join("\n")}</code></pre>`);
        continue;
      }

      const heading = trimmed.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        out.push(`<h4 class="mc-md-h">${inline(heading[2].replace(/#+\s*$/, ""))}</h4>`);
        i++;
        continue;
      }

      if (/^---+$/.test(trimmed)) { out.push("<hr>"); i++; continue; }

      const callout = trimmed.match(CALLOUT);
      if (callout) {
        const body = [];
        i++;
        while (i < lines.length && lines[i].trim() && !CALLOUT.test(lines[i].trim())) body.push(lines[i++].trim());
        const tone = CALLOUT_TONE[callout[1]] || "note";
        out.push(`<div class="mc-callout mc-callout--${tone}"><div class="mc-callout-title">${inline(callout[2])}</div>${body.length ? `<div>${inline(body.join(" "))}</div>` : ""}</div>`);
        continue;
      }

      if (/^&gt;\s?/.test(trimmed)) {
        const buf = [];
        while (i < lines.length && /^&gt;\s?/.test(lines[i].trim())) buf.push(lines[i++].trim().replace(/^&gt;\s?/, ""));
        out.push(`<blockquote>${inline(buf.join(" "))}</blockquote>`);
        continue;
      }

      const listMatch = trimmed.match(/^([-*•]|\d+[.)])\s+/);
      if (listMatch) {
        const ordered = /\d/.test(listMatch[1]);
        const start = ordered ? parseInt(listMatch[1], 10) : 1;
        const items = [];
        while (i < lines.length) {
          const l = lines[i];
          const t = l.trim();
          const m = t.match(/^([-*•]|\d+[.)])\s+(.*)$/);
          if (m && (/\d/.test(m[1]) === ordered || l.search(/\S/) >= 2)) {
            if (l.search(/\S/) >= 2 && items.length) items[items.length - 1].sub.push(m[2]);
            else items.push({ text: m[2], sub: [] });
            i++;
          } else if (t && !isBlockStart(l) && items.length && l.search(/\S/) >= 2) {
            items[items.length - 1].text += " " + t;  // wrapped continuation line
            i++;
          } else if (!t && i + 1 < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i + 1]) && /\d/.test((lines[i + 1].trim().match(/^([-*•]|\d+[.)])/) || [""])[0]) === ordered) {
            i++; // blank line between items of the same list
          } else break;
        }
        const tag = ordered ? "ol" : "ul";
        out.push(`<${tag}${ordered && start !== 1 ? ` start="${start}"` : ""}>` + items.map((it) =>
          `<li>${inline(it.text)}${it.sub.length ? `<ul>${it.sub.map((s) => `<li>${inline(s)}</li>`).join("")}</ul>` : ""}</li>`).join("") + `</${tag}>`);
        continue;
      }

      const para = [];
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) para.push(lines[i++].trim());
      if (!para.length) { para.push(trimmed); i++; }
      out.push(`<p>${inline(para.join("<br>"))}</p>`);
    }
    return out.join("");
  }

  // ------------------------------------------------------------------ api

  const api = (path, options) => apiFetch(`${BASE_URL}${path}`, options);
  const user = () => getUsername();

  function storageKey() { return `mysChatActive:${user()}`; }
  function rememberActive(id) {
    try {
      const store = typeof learningStorage === "function" ? learningStorage() : localStorage;
      if (id) store.setItem(storageKey(), id); else store.removeItem(storageKey());
    } catch (e) { /* storage unavailable: no cross-page continuity, nothing else breaks */ }
  }
  function recallActive() {
    try { return (typeof learningStorage === "function" ? learningStorage() : localStorage).getItem(storageKey()); } catch (e) { return null; }
  }

  async function fetchJSON(path, options) {
    const r = await api(path, options);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function streamChat(payload, handlers, signal) {
    const r = await api("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    if (!r.ok || !r.body || !r.body.getReader) {
      if (r.status === 404 || r.status === 405 || !r.body) {
        // Older backend without streaming: use the plain endpoint.
        const data = await fetchJSON("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal });
        handlers.meta && handlers.meta({ conversation_id: data.conversation_id, safety_warning: data.safety_warning });
        handlers.delta && handlers.delta(data.response);
        handlers.done && handlers.done(data);
        return;
      }
      let detail = "";
      try { detail = (await r.json()).detail || ""; } catch (e) {}
      throw new Error(detail || `HTTP ${r.status}`);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        let evt;
        try { evt = JSON.parse(line); } catch (e) { continue; }
        if (evt.type === "done") finished = true;
        const fn = handlers[evt.type];
        if (fn) fn(evt.type === "delta" ? evt.text : evt);
      }
    }
    if (!finished) throw new Error("The reply was cut off.");
  }

  // ------------------------------------------------------------------ helpers

  function timeLabel(ts) {
    const d = ts ? new Date(/Z|[+-]\d\d:?\d\d$/.test(ts) ? ts : ts + "Z") : new Date();
    return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function groupLabel(ts) {
    if (!ts) return "Older";
    const d = new Date(/Z|[+-]\d\d:?\d\d$/.test(ts) ? ts : ts + "Z");
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const day = new Date(d); day.setHours(0, 0, 0, 0);
    const diff = Math.round((today - day) / 86400000);
    if (diff <= 0) return "Today";
    if (diff === 1) return "Yesterday";
    if (diff < 7) return "Previous 7 days";
    if (diff < 30) return "Previous 30 days";
    return d.toLocaleDateString([], { month: "long", year: "numeric" });
  }

  function titleCase(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }

  function pageContext() {
    const page = (location.pathname.split("/").pop() || "index.html").replace(".html", "");
    if (page === "index" || page === "") return (location.hash || "#home").slice(1) || "home";
    if (page === "lesson") return `lesson:${(typeof getUrlParam === "function" && getUrlParam("category")) || ""}`;
    return page;
  }

  function actionHref(action, drug) {
    if (action.type === "lesson") {
      const focused = typeof isFocused === "function" && isFocused();
      const page = focused && typeof getFocusedFormat === "function" && getFocusedFormat() === "chat" ? "chat-quiz.html" : "lesson.html";
      return `${page}?drug=${encodeURIComponent(drug)}&category=${encodeURIComponent(action.category)}`;
    }
    if (action.type === "intake") return "index.html#intake";
    if (action.type === "progress") return "index.html#progress";
    return typeof pathPageUrl === "function" && localStorage.getItem("learningStyle") ? pathPageUrl(drug) : "index.html#drugs";
  }

  const ACTION_ICON = { lesson: "target", path: "path", intake: "clipboard", progress: "spark" };

  // ------------------------------------------------------------------ access
  // "account" (signed in), "guest" (temporary session) or "signed_out".
  function accessState() {
    if (typeof isGuest === "function" && isGuest()) return "guest";
    if (typeof hasAccount === "function" ? hasAccount() : !!getUsername()) return "account";
    return "signed_out";
  }

  function currentPage() {
    return (location.pathname.split("/").pop() || "index.html") + location.search + location.hash;
  }

  /** Card that asks the visitor to sign in (and, when signed out, offers guest mode). */
  function accountPromptHTML({ title, body, guest = true, compact = false }) {
    const page = JSON.stringify(currentPage()).replace(/"/g, "&quot;");
    return `
      <div class="mc-gate${compact ? " mc-gate--compact" : ""}">
        <div class="mc-gate-icon">${icon("user", compact ? 18 : 22)}</div>
        <h3>${esc(title)}</h3>
        <p>${esc(body)}</p>
        <div class="mc-gate-actions">
          <button type="button" class="mc-gate-primary" onclick="goToLogin()">Log in / Sign up</button>
          ${guest ? `<button type="button" class="mc-gate-secondary" onclick="startGuest(${page})">Continue as guest</button>` : ""}
        </div>
      </div>`;
  }

  // ------------------------------------------------------------------ controller

  /**
   * One chat surface. `els` holds the elements it renders into:
   *   thread, input, send, list (optional), title (optional), search (optional)
   * `opts`:
   *   variant: "full" | "widget"
   *   getDrug(): current drug key
   *   getArchetype(): persona to send, or null to use the saved one
   *   onContext(ctx), onTitle(title), onConversationChange(id)
   *   renderWelcome(ctx): custom welcome HTML (optional)
   */
  class ChatController {
    constructor(els, opts) {
      this.els = els;
      this.opts = Object.assign({ variant: "full" }, opts);
      this.conversationId = null;
      this.conversations = [];
      this.context = null;
      this.streaming = false;
      this.abort = null;
      this.lastUserText = "";
      this.stickToBottom = true;
      this.filter = "";
      this._bind();
      // Learning style / level changed somewhere on the page: reload what the chat knows.
      document.addEventListener("mys:preferences", async () => {
        await this.loadContext();
        if (!this.conversationId && this.els.thread.querySelector(".mc-welcome")) this.showWelcome();
      });
    }

    get drug() { return (this.opts.getDrug && this.opts.getDrug()) || "amoxicillin"; }

    _bind() {
      const { input, send, thread, search } = this.els;
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); this.send(); }
      });
      input.addEventListener("input", () => this._autosize());
      send.addEventListener("click", () => (this.streaming ? this.stop() : this.send()));
      thread.addEventListener("scroll", () => {
        this.stickToBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80;
      });
      thread.addEventListener("click", (e) => this._onThreadClick(e));
      if (search) search.addEventListener("input", () => { this.filter = search.value.trim().toLowerCase(); this.renderList(); });
      if (this.els.list) this.els.list.addEventListener("click", (e) => this._onListClick(e));
      this._setSendState();
    }

    _autosize() {
      const el = this.els.input;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, this.opts.variant === "widget" ? 120 : 200) + "px";
    }

    _setSendState() {
      const b = this.els.send;
      b.innerHTML = icon(this.streaming ? "stop" : "send", 18);
      b.setAttribute("aria-label", this.streaming ? "Stop generating" : "Send message");
      b.title = this.streaming ? "Stop" : "Send (Enter)";
      b.classList.toggle("is-stop", this.streaming);
    }

    // ---------- lifecycle

    async init() {
      await Promise.all([this.loadContext(), this.loadConversations()]);
      const wanted = new URLSearchParams(location.search).get("c") || recallActive();
      if (wanted && this.conversations.some((c) => c.conversation_id === wanted)) await this.open(wanted);
      else this.showWelcome();
    }

    async loadContext() {
      try {
        this.context = await fetchJSON(`/chat/context/${encodeURIComponent(this.drug)}?username=${encodeURIComponent(user())}`);
      } catch (e) {
        console.warn("Chat context unavailable:", e);
        this.context = null;
      }
      if (this.opts.onContext) this.opts.onContext(this.context);
      return this.context;
    }

    async loadConversations() {
      try {
        this.conversations = await fetchJSON(`/conversations/${encodeURIComponent(user())}`);
      } catch (e) {
        console.warn("Could not load conversations:", e);
        this.conversations = this.conversations || [];
      }
      this.renderList();
      return this.conversations;
    }

    newChat() {
      if (this.streaming) this.stop();
      this.conversationId = null;
      rememberActive(null);
      this._emitConversation();
      this.showWelcome();
      this.renderList();
      this.els.input.value = "";
      this._autosize();
      this.els.input.focus();
    }

    async open(id) {
      if (this.streaming) this.stop();
      this.conversationId = id;
      rememberActive(id);
      this._emitConversation();
      this.renderList();
      const thread = this.els.thread;
      thread.innerHTML = `<div class="mc-loading">${'<span></span>'.repeat(3)}</div>`;
      try {
        const rows = await fetchJSON(`/chat/history/${encodeURIComponent(user())}?conversation_id=${encodeURIComponent(id)}`);
        if (this.conversationId !== id) return;
        thread.innerHTML = "";
        if (!rows.length) { this.showWelcome(); return; }
        rows.forEach((row) => {
          if (row.sender === "user") this._addUser(row.message, row.timestamp);
          else {
            if (row.safety_warning) this._addSafety(row.safety_warning);
            this._addBot({ text: row.message, time: row.timestamp });
          }
        });
        this.stickToBottom = true;
        this._scroll(true);
      } catch (e) {
        thread.innerHTML = "";
        this._addError("Couldn't load this conversation.", () => this.open(id));
      }
    }

    async remove(id) {
      if (!confirm("Delete this conversation? This can't be undone.")) return;
      try {
        await api(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      } catch (e) { /* refreshed list below shows the truth */ }
      if (this.conversationId === id) this.newChat();
      await this.loadConversations();
    }

    async rename(id) {
      const conv = this.conversations.find((c) => c.conversation_id === id);
      const title = prompt("Rename conversation", conv ? conv.title : "");
      if (!title || !title.trim()) return;
      try {
        await api(`/conversations/${encodeURIComponent(id)}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim() }),
        });
      } catch (e) { /* keep old title */ }
      await this.loadConversations();
      this._emitConversation();
    }

    _emitConversation() {
      const conv = this.conversations.find((c) => c.conversation_id === this.conversationId);
      if (this.opts.onTitle) this.opts.onTitle(conv ? conv.title : null);
      if (this.opts.onConversationChange) this.opts.onConversationChange(this.conversationId);
    }

    // ---------- welcome

    showWelcome() {
      const ctx = this.context;
      const thread = this.els.thread;
      if (this.opts.renderWelcome) {
        thread.innerHTML = this.opts.renderWelcome(ctx, this);
      } else {
        const drugName = (ctx && ctx.drug_name) || titleCase(this.drug);
        thread.innerHTML = `
          <div class="mc-welcome">
            <div class="mc-welcome-mark">${icon("chat", 22)}</div>
            <h2>How can I help you learn about ${esc(drugName)}?</h2>
            <p>Ask anything about your medication or health. Answers adapt to your profile and progress.</p>
            ${this.starterHTML()}
          </div>`;
      }
    }

    starterHTML(extra = []) {
      const prompts = extra.concat((this.context && this.context.starter_prompts) || [
        { kind: "learn", label: `What is ${titleCase(this.drug)} used for?`, prompt: `What is ${titleCase(this.drug)} and what is it used for?` },
        { kind: "quiz", label: "Quiz me", prompt: `Quiz me on ${titleCase(this.drug)}, one question at a time.` },
      ]).slice(0, 4);
      return `<div class="mc-starters">${prompts.map((p) => `
        <button type="button" class="mc-starter" data-ask="${esc(p.prompt)}">
          <span class="mc-starter-icon mc-kind-${esc(p.kind)}">${icon(KIND_ICON[p.kind] || "spark", 16)}</span>
          <span>${esc(p.label)}</span>
        </button>`).join("")}</div>`;
    }

    // ---------- sending

    ask(text) {
      this.els.input.value = text;
      this.send();
    }

    async send() {
      const text = this.els.input.value.trim();
      if (!text || this.streaming) return;
      this.els.input.value = "";
      this._autosize();
      this.lastUserText = text;

      const welcome = this.els.thread.querySelector(".mc-welcome");
      if (welcome) this.els.thread.innerHTML = "";
      this._clearSuggestions();
      this._addUser(text);
      const bot = this._addBot({ pending: true });
      this.stickToBottom = true;
      this._scroll(true);

      this.streaming = true;
      this._setSendState();
      this.abort = new AbortController();

      let acc = "";
      let raf = 0;
      const caret = '<span class="mc-caret"></span>';
      const paint = () => {
        raf = 0;
        const html = renderMarkdown(acc);
        // Keep the caret inline at the end of the last paragraph / list item.
        const withCaret = html.replace(/(<\/(?:p|li|h4)>(?:<\/[ou]l>)?)$/, caret + "$1");
        bot.body.innerHTML = withCaret === html ? html + caret : withCaret;
        this._scroll();
      };

      const payload = {
        username: user(),
        message: text,
        drug: this.drug,
        conversation_id: this.conversationId,
        experience_level: (typeof learningStorage === "function" && learningStorage().getItem("experienceLevel")) || null,
        page_context: this.opts.pageContext ? this.opts.pageContext() : pageContext(),
      };
      const archetype = this.opts.getArchetype ? this.opts.getArchetype() : null;
      if (archetype) payload.archetype = archetype;

      try {
        await streamChat(payload, {
          meta: (m) => {
            if (m.conversation_id && m.conversation_id !== this.conversationId) {
              this.conversationId = m.conversation_id;
              rememberActive(m.conversation_id);
              if (this.opts.onConversationChange) this.opts.onConversationChange(this.conversationId);
            }
            if (m.safety_warning) this._addSafety(m.safety_warning, bot.el);
          },
          delta: (t) => {
            if (!acc) { bot.el.classList.remove("is-pending"); bot.meta.textContent = ""; }
            acc += t;
            if (!raf) raf = requestAnimationFrame(paint);
          },
          done: (d) => {
            if (raf) cancelAnimationFrame(raf);
            acc = d.response || acc;
            this._finishBot(bot, acc, d.suggestions, d.actions);
            if (d.conversation_title && this.opts.onTitle) this.opts.onTitle(d.conversation_title);
          },
        }, this.abort.signal);
      } catch (err) {
        if (raf) cancelAnimationFrame(raf);
        if (err.name === "AbortError") {
          this._finishBot(bot, acc || "_Stopped._", [], [], true);
        } else {
          console.error("Chat failed:", err);
          if (acc) this._finishBot(bot, acc, [], [], true);
          else bot.el.remove();
          this._addError(/Failed to fetch|NetworkError/i.test(err.message)
            ? "Can't reach the server. Check that the backend is running, then try again."
            : "Something went wrong while answering.", () => this.ask(text));
        }
      } finally {
        this.streaming = false;
        this.abort = null;
        this._setSendState();
        this.loadConversations();
        // Progress can change between messages (lessons in another tab): refresh quietly.
        if (this.opts.variant === "full") this.loadContext();
      }
    }

    stop() {
      if (this.abort) this.abort.abort();
    }

    // ---------- rendering

    _addUser(text, time) {
      const el = document.createElement("div");
      el.className = "mc-msg mc-msg--user";
      el.innerHTML = `<div class="mc-bubble"></div><div class="mc-meta">${esc(timeLabel(time))}</div>`;
      el.querySelector(".mc-bubble").textContent = text;
      this.els.thread.appendChild(el);
      return el;
    }

    _addBot({ text = "", time = null, pending = false } = {}) {
      const el = document.createElement("div");
      el.className = "mc-msg mc-msg--bot" + (pending ? " is-pending" : "");
      el.innerHTML = `
        <div class="mc-avatar" aria-hidden="true">${icon("spark", 14)}</div>
        <div class="mc-msg-main">
          <div class="mc-bubble mc-md">${pending ? '<div class="mc-typing"><span></span><span></span><span></span></div>' : renderMarkdown(text)}</div>
          <div class="mc-meta">
            <span>${pending ? "Thinking…" : esc(timeLabel(time))}</span>
            <button type="button" class="mc-icon-btn" data-copy title="Copy" aria-label="Copy reply"${pending ? " hidden" : ""}>${icon("copy", 14)}</button>
          </div>
          <div class="mc-extras"></div>
        </div>`;
      el._raw = text;
      this.els.thread.appendChild(el);
      return { el, body: el.querySelector(".mc-bubble"), meta: el.querySelector(".mc-meta span"), extras: el.querySelector(".mc-extras") };
    }

    _finishBot(bot, text, suggestions = [], actions = [], interrupted = false) {
      bot.el.classList.remove("is-pending");
      bot.el._raw = text;
      bot.body.innerHTML = renderMarkdown(text);
      bot.meta.textContent = timeLabel() + (interrupted ? " · stopped" : "");
      const copy = bot.el.querySelector("[data-copy]");
      if (copy) copy.hidden = false;
      const parts = [];
      if (actions && actions.length) {
        parts.push(`<div class="mc-actions">${actions.map((a) =>
          `<a class="mc-action" href="${esc(actionHref(a, this.drug))}">${icon(ACTION_ICON[a.type] || "arrow", 14)}<span>${esc(a.label)}</span></a>`).join("")}</div>`);
      }
      if (suggestions && suggestions.length) {
        parts.push(`<div class="mc-suggestions">${suggestions.map((s) => `<button type="button" class="mc-chip" data-ask="${esc(s)}">${esc(s)}</button>`).join("")}</div>`);
      }
      bot.extras.innerHTML = parts.join("");
      this._scroll();
    }

    _clearSuggestions() {
      this.els.thread.querySelectorAll(".mc-suggestions").forEach((el) => el.remove());
    }

    _addSafety(text, before = null) {
      const el = document.createElement("div");
      el.className = "mc-safety";
      el.setAttribute("role", "alert");
      el.innerHTML = `
        <div class="mc-safety-head">${icon("alert", 15)}<strong>Safety alert</strong><span>Based on your profile and question</span></div>
        <div class="mc-safety-body"></div>
        <div class="mc-safety-foot">Talk with your clinician or pharmacist before making any change.</div>`;
      el.querySelector(".mc-safety-body").innerHTML = String(text).split(/\n{2,}/)
        .map((p) => `<p>${esc(p.replace(/^⚠️\s*/, ""))}</p>`).join("");
      if (before && before.parentNode) before.parentNode.insertBefore(el, before);
      else this.els.thread.appendChild(el);
      this._scroll();
    }

    _addError(message, retry) {
      const el = document.createElement("div");
      el.className = "mc-error";
      el.innerHTML = `<span>${esc(message)}</span>${retry ? `<button type="button" class="mc-error-retry">${icon("retry", 14)} Try again</button>` : ""}`;
      if (retry) el.querySelector("button").addEventListener("click", () => { el.remove(); retry(); });
      this.els.thread.appendChild(el);
      this._scroll(true);
    }

    _scroll(force = false) {
      if (!force && !this.stickToBottom) return;
      const t = this.els.thread;
      t.scrollTop = t.scrollHeight;
    }

    _onThreadClick(e) {
      const ask = e.target.closest("[data-ask]");
      if (ask) { this.ask(ask.getAttribute("data-ask")); return; }
      const copy = e.target.closest("[data-copy]");
      if (copy) {
        const msg = copy.closest(".mc-msg");
        const text = (msg && msg._raw) || (msg && msg.querySelector(".mc-bubble").innerText) || "";
        const done = () => { copy.innerHTML = icon("check", 14); setTimeout(() => { copy.innerHTML = icon("copy", 14); }, 1400); };
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(done).catch(() => {});
      }
    }

    // ---------- conversation list

    renderList() {
      const list = this.els.list;
      if (!list) return;
      const items = (this.conversations || []).filter((c) => !this.filter || (c.title || "").toLowerCase().includes(this.filter));
      if (this.els.count) this.els.count.textContent = String((this.conversations || []).length);
      if (!items.length) {
        list.innerHTML = `<div class="mc-list-empty">${this.filter ? "No conversations match." : "No conversations yet.<br>Your chats will show up here."}</div>`;
        return;
      }
      let lastGroup = null;
      list.innerHTML = items.map((c) => {
        const group = groupLabel(c.updated_at || c.created_at);
        const header = group !== lastGroup ? `<div class="mc-list-group">${esc(group)}</div>` : "";
        lastGroup = group;
        const active = c.conversation_id === this.conversationId ? " is-active" : "";
        return `${header}
          <div class="mc-conv${active}" data-open="${esc(c.conversation_id)}" role="button" tabindex="0">
            <div class="mc-conv-text">
              <div class="mc-conv-title">${esc(c.title || "New conversation")}</div>
              <div class="mc-conv-sub">${esc(titleCase(c.drug || ""))}</div>
            </div>
            <div class="mc-conv-tools">
              <button type="button" class="mc-icon-btn" data-rename="${esc(c.conversation_id)}" title="Rename" aria-label="Rename conversation">${icon("pencil", 13)}</button>
              <button type="button" class="mc-icon-btn" data-delete="${esc(c.conversation_id)}" title="Delete" aria-label="Delete conversation">${icon("trash", 13)}</button>
            </div>
          </div>`;
      }).join("");
    }

    _onListClick(e) {
      const del = e.target.closest("[data-delete]");
      if (del) { e.stopPropagation(); this.remove(del.getAttribute("data-delete")); return; }
      const ren = e.target.closest("[data-rename]");
      if (ren) { e.stopPropagation(); this.rename(ren.getAttribute("data-rename")); return; }
      const item = e.target.closest("[data-open]");
      if (item) {
        this.open(item.getAttribute("data-open"));
        if (this.opts.onOpenFromList) this.opts.onOpenFromList();
      }
    }
  }

  window.MysChat = { ChatController, renderMarkdown, icon, esc, titleCase, actionHref, pageContext, timeLabel, STYLES, styleOptions, accessState, accountPromptHTML };
})();
