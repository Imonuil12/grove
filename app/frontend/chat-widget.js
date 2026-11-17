// chat-widget.js — floating learning-assistant widget.
// Include after script.js and chat-core.js; it builds its own markup, so a page
// only needs:
//   <link rel="stylesheet" href="chat.css">
//   <script src="chat-core.js"></script>
//   <script src="chat-widget.js"></script>
(function () {
  "use strict";
  if (!window.MysChat || document.getElementById("mcwRoot")) return;
  const { ChatController, icon, esc, titleCase, accessState, accountPromptHTML } = window.MysChat;

  const page = (location.pathname.split("/").pop() || "index.html").replace(".html", "");
  const lessonCategory = page === "lesson" && typeof getUrlParam === "function" ? getUrlParam("category") : null;

  function currentDrug() {
    if (typeof getSelectedDrug === "function") return getSelectedDrug() || "amoxicillin";
    return "amoxicillin";
  }

  function build() {
    const root = document.createElement("div");
    root.id = "mcwRoot";
    root.innerHTML = `
      <section class="mcw-panel" id="mcwPanel" role="dialog" aria-label="Learning assistant" aria-hidden="true">
        <header class="mcw-head">
          <div class="mcw-head-mark">${icon("spark", 17)}</div>
          <div class="mcw-head-text">
            <strong id="mcwTitle">Learning assistant</strong>
            <span><i></i><em id="mcwSub" style="font-style:normal">Personalized to you</em></span>
          </div>
          <button type="button" class="mc-icon-btn" id="mcwHistoryBtn" title="Chat history" aria-label="Chat history">${icon("chat", 17)}</button>
          <button type="button" class="mc-icon-btn" id="mcwNewBtn" title="New chat" aria-label="New chat">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
          </button>
          <a class="mc-icon-btn" id="mcwExpand" href="chatbot.html" title="Open full chat" aria-label="Open full chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/></svg>
          </a>
          <button type="button" class="mc-icon-btn" id="mcwClose" title="Close" aria-label="Close coach">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M5 12h14"/></svg>
          </button>
        </header>
        <div class="mcw-body">
          <div class="mc-thread" id="mcwThread" aria-live="polite"></div>
          <div class="mcw-history" id="mcwHistory" aria-label="Chat history">
            <button type="button" class="mc-new" id="mcwHistoryNew"><span>New chat</span>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></button>
            <label class="mc-search">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
              <input type="search" id="mcwSearch" placeholder="Search chats" aria-label="Search conversations">
            </label>
            <div class="mc-list" id="mcwList"></div>
          </div>
        </div>
        <footer class="mcw-foot">
          <div class="mc-composer">
            <textarea id="mcwInput" rows="1" placeholder="Ask anything, or say “quiz me”…" aria-label="Message"></textarea>
            <div class="mc-composer-row">
              <div class="mc-composer-tools">
                <select class="mc-select" id="mcwStyle" aria-label="Learning style" title="How the assistant explains things">${window.MysChat.styleOptions()}</select>
              </div>
              <button type="button" class="mc-send" id="mcwSend"></button>
            </div>
          </div>
          <p class="mc-disclaimer">Educational tool, not medical advice. In an emergency, call 911.</p>
        </footer>
      </section>
      <button type="button" class="mcw-launcher" id="mcwLauncher" aria-label="Open coach" aria-controls="mcwPanel" aria-expanded="false">
        <span class="mcw-chat-icon">${icon("chat", 24)}</span>
        <span class="mcw-close-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></span>
      </button>`;
    document.body.appendChild(root);
    if (page === "lesson") document.body.classList.add("mcw-raised");
    return root;
  }

  function init() {
    if (["outline", "topic"].includes(document.body.dataset.lessonSource)) return;
    const root = build();
    const $ = (id) => document.getElementById(id);
    let ready = false;
    let initPromise = null;
    const access = accessState();
    const GUEST_NOTE = `<div class="mc-guest-note">Guest session: chats and progress reset when you close this tab. <a href="#" onclick="goToLogin(); return false;">Log in</a> to save them.</div>`;

    if (access === "guest") {
      // Saved chat history is an account feature: show a sign-in prompt instead of the list.
      $("mcwList").innerHTML = accountPromptHTML({
        title: "Keep your chat history",
        body: "Guest chats disappear when you close this tab. Log in or sign up to save and search your conversations.",
        guest: false, compact: true,
      });
      $("mcwSearch").closest(".mc-search").hidden = true;
    }

    const chat = new ChatController(
      { thread: $("mcwThread"), input: $("mcwInput"), send: $("mcwSend"),
        list: access === "account" ? $("mcwList") : null, search: access === "account" ? $("mcwSearch") : null },
      {
        variant: "widget",
        getDrug: currentDrug,
        getArchetype: () => null, // use the learning style saved in the user's profile
        onTitle: (title) => { $("mcwTitle").textContent = title || "Learning assistant"; },
        onConversationChange: (id) => { $("mcwExpand").href = `chatbot.html?drug=${encodeURIComponent(currentDrug())}${id ? `&c=${encodeURIComponent(id)}` : ""}`; },
        onContext: (ctx) => {
          $("mcwSub").textContent = ctx ? `${ctx.drug_name} · ${ctx.archetype_label || titleCase(ctx.archetype)} · ${titleCase(ctx.experience_level)}` : "Personalized to you";
          if (ctx && ctx.archetype) $("mcwStyle").value = ctx.archetype;
        },
        onOpenFromList: () => toggleHistory(false),
        renderWelcome: (ctx, c) => {
          const drugName = (ctx && ctx.drug_name) || titleCase(currentDrug());
          const extra = lessonCategory ? [{
            kind: "lesson", label: `Explain this ${lessonCategory} lesson`,
            prompt: `I'm working on the ${lessonCategory} lesson for ${drugName}. Can you explain the key ideas simply?`,
          }] : [];
          const progress = ctx ? `
            <div class="mcw-progress">
              <div class="mc-ring" style="--p:${ctx.percent}"><b>${ctx.percent}%</b></div>
              <div><strong>${ctx.mastered_count}/${ctx.total_objectives}</strong> ${esc(drugName)} topics mastered${ctx.struggling.length ? ` · <strong>${ctx.struggling.length}</strong> to review` : ""}</div>
            </div>` : "";
          return `
            <div class="mc-welcome">
              <div class="mc-welcome-mark">${icon("spark", 20)}</div>
              <h2>Hi! What can I help with?</h2>
              <p>Ask about ${esc(drugName)} or your health. I know your progress, so I can explain, quiz you, or review what you missed.</p>
              ${access === "guest" ? GUEST_NOTE : ""}
              ${progress}
              ${c.starterHTML(extra)}
            </div>`;
        },
      }
    );

    function setOpen(open) {
      root.classList.toggle("mcw-open", open);
      $("mcwPanel").setAttribute("aria-hidden", String(!open));
      $("mcwLauncher").setAttribute("aria-expanded", String(open));
      $("mcwLauncher").setAttribute("aria-label", open ? "Close coach" : "Open coach");
      try { sessionStorage.setItem("mcwOpen", open ? "1" : "0"); } catch (e) {}
      if (open) {
        if (!ready) {
          ready = true;
          if (access === "signed_out") showSignedOut();
          else initPromise = chat.init();
        }
        if (access !== "signed_out") setTimeout(() => $("mcwInput").focus(), 60);
      }
    }

    // Signed out: no fake account, just an invitation to sign in or try guest mode.
    function showSignedOut() {
      $("mcwThread").innerHTML = accountPromptHTML({
        title: "Sign in to use the assistant",
        body: "Log in to get a tutor that knows your progress and saves your chats, or continue as a guest to try it now.",
      });
      $("mcwInput").disabled = true;
      $("mcwInput").placeholder = "Sign in or continue as a guest to chat";
      root.querySelector(".mcw-foot .mc-composer").classList.add("is-locked");
      ["mcwHistoryBtn", "mcwNewBtn", "mcwExpand"].forEach((id) => { $(id).hidden = true; });
      $("mcwSub").textContent = "Not signed in";
    }

    function toggleHistory(open) {
      const panel = $("mcwHistory");
      const isOpen = typeof open === "boolean" ? open : !panel.classList.contains("is-open");
      panel.classList.toggle("is-open", isOpen);
      $("mcwHistoryBtn").classList.toggle("is-on", isOpen);
      if (isOpen && access === "account") { chat.loadConversations(); $("mcwSearch").focus(); }
    }

    $("mcwLauncher").addEventListener("click", () => setOpen(!root.classList.contains("mcw-open")));
    $("mcwClose").addEventListener("click", () => setOpen(false));
    $("mcwStyle").addEventListener("change", (e) => {
      if (typeof saveLearningPreferences === "function") saveLearningPreferences({ archetype: e.target.value });
    });
    $("mcwHistoryBtn").addEventListener("click", () => toggleHistory());
    $("mcwNewBtn").addEventListener("click", () => { toggleHistory(false); chat.newChat(); });
    $("mcwHistoryNew").addEventListener("click", () => { toggleHistory(false); chat.newChat(); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || !root.classList.contains("mcw-open")) return;
      if ($("mcwHistory").classList.contains("is-open")) toggleHistory(false);
      else if (chat.streaming) chat.stop();
      else setOpen(false);
    });

    // Follow the page's medication picker.
    const drugSelect = document.getElementById("drugSelect");
    if (drugSelect) {
      drugSelect.addEventListener("change", async () => {
        if (!ready) return;
        await chat.loadContext();
        if (!chat.conversationId) chat.showWelcome();
      });
    }

    // Older inline handlers on some pages call these.
    window.toggleChat = () => setOpen(!root.classList.contains("mcw-open"));
    window.openChatWith = async (text) => {
      setOpen(true);
      if (access === "signed_out" || chat.streaming) return;
      if (initPromise) await initPromise;
      chat.newChat();  // a fresh thread for each lesson question keeps history tidy
      chat.ask(text);
    };

    let wasOpen = null;
    try { wasOpen = sessionStorage.getItem("mcwOpen"); } catch (e) {}
    // Reopen where the learner left it, except during a lesson (it would cover the question;
    // there it opens from "Ask the assistant" instead).
    if (wasOpen === "1" && page !== "lesson") setOpen(true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
