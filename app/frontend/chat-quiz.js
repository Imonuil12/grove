// ============================================================
// chat-quiz.js — Focused mode, "Chat quiz" format (chat-quiz.html)
//
// One continuous conversation:
//   1. Ask every question in a section once. A wrong answer gets notes right
//      away and the quiz keeps going.
//   2. At the end of the section, loop back over the missed questions, again
//      and again, until every one is answered correctly.
//   3. Then offer the next section and keep the same conversation going.
//
// The backend decides the question order: /lesson/answer only accepts the
// question the server handed out last. So every round is a server lesson
// (/lesson/start -> /lesson/answer ...), and this file only decides when a
// round has asked everything it needs. Levels (and the bonsai) grow the same
// way as in the mini quizzes. Load after script.js, ui.js and bonsai.js.
// ============================================================
(function () {
  "use strict";

  const UNITS = ["Facts", "Dosage", "Procedures", "Rationales"];
  const SKIP_WORDS = ["skip", "pass", "idk", "i don't know", "i dont know", "not sure", "no idea"];
  const QUESTION_START = /^(what|why|how|when|where|who|which|can|could|should|would|will|is|are|does|do|did)\b/i;
  // Messages that are clearly a request for help, not an answer (even without "?").
  const ASIDE_START = /^(explain|tell me|help( me)?|hint|give me a hint|i\s*(do\s*not|don'?t|dont)\s*(get|understand|know what)|i'?m (confused|lost)|can you|could you|please explain)\b/i;
  const QUESTION_PHRASE_START = /^(?:(?:what|why|how|when|where|who|which)\s+(?:is|are|was|were|do|does|did|can|could|should|would|will)|what['’]s|what\s+happens|how\s+(?:much|many|long|often))\b/i;
  const YES = /^(y|yes|yeah|yep|yup|sure|ok|okay|go|start|continue|next|let'?s)\b/i;
  const NO = /^(n|no|nope|nah|not now|later|stop|done|quit)\b/i;
  const MAX_ROUNDS = 15; // safety stop so a section can never loop forever
  const BOT_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"></path><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"></path></svg>';

  const cq = {
    drug: (getUrlParam("drug") || "amoxicillin").toLowerCase(),
    topic: getUrlParam("topic"),
    course: getUrlParam("course") || "conditions",
    topicName: "",
    topicChatAvailable: false,
    attemptId: null,
    category: getUrlParam("category") || "Facts",
    content: {},          // category -> [{ oid, lesson_text, ... }] (for fuller notes)
    pending: new Set(),   // oids in this section not answered correctly yet
    seen: new Set(),      // oids the server has asked in this section
    asked: new Set(),     // oids asked in the current round
    misses: {},           // oid -> times answered wrong in this section
    round: 1,
    current: null,        // question being asked: { oid, question, category }
    endedCleanly: false,  // last server lesson reached its final question
    mode: "idle",         // "answer" | "choice" | "idle"
    choice: null,
    busy: false,
    conversationId: null, // questions asked mid-quiz share one chatbot conversation
    topicHistory: [],
  };

  let thread, input, sendBtn, askBtn;

  // ---------------------------------------------------------- helpers
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  // Escape, then allow **bold** and line breaks (the /chat replies use both).
  function fmt(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  }
  // lesson_text can be a plain string or { beginner, intermediate, advanced }.
  function pickText(t) {
    if (t && typeof t === "object") {
      const lvl = String(learningStorage().getItem("experienceLevel") || "beginner").toLowerCase();
      const key = lvl.includes("advanced") ? "advanced" : lvl.includes("intermediate") ? "intermediate" : "beginner";
      return t[key] || t.beginner || Object.values(t)[0] || "";
    }
    return t || "";
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const subjectLabel = () => cq.topic ? cq.topicName : cq.drug.charAt(0).toUpperCase() + cq.drug.slice(1);
  const label = (cat) => (typeof CATEGORY_LABELS !== "undefined" && CATEGORY_LABELS[cat]) || cat;
  const sectionList = () => (cq.topic ? Object.keys(cq.content) : UNITS).filter((u) => (cq.content[u] || []).length);
  const contentFor = (oid) => (cq.content[cq.category] || []).find((o) => o.oid === oid);
  const backUrl = () => lessonPageUrl(cq.topic ? cq.course : "drugs", "focused", cq.topic || cq.drug);
  const topicRoute = () => `/topics/${encodeURIComponent(cq.topic)}`;
  const answerPlaceholder = "Type your answer or ask a question…";
  const stillNeeded = () => [...cq.pending].some((oid) => !cq.asked.has(oid));

  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ username: getUsername() }, body)),
    };
    const r = await apiFetch(`${BASE_URL}${path}`, opts);
    let data = null;
    try { data = await r.json(); } catch (e) {}
    return { ok: r.ok, status: r.status, data };
  }

  function lessonApi(action, payload = {}) {
    const base = cq.topic ? topicRoute() : "";
    const scope = cq.topic ? (action === "start" ? {} : { attempt_id: cq.attemptId }) : { drug: cq.drug };
    return api(`${base}/lesson/${action}`, { ...scope, ...payload });
  }

  // ---------------------------------------------------------- chat UI
  function scrollDown() { thread.scrollTop = thread.scrollHeight; }

  function addMsg(who, html, extraClass) {
    const row = document.createElement("div");
    row.className = `cq-msg cq-${who}${extraClass ? " " + extraClass : ""}`;
    row.innerHTML = who === "bot"
      ? `<span class="cq-avatar" aria-hidden="true">${BOT_ICON}</span><div class="cq-bubble">${html}</div>`
      : `<div class="cq-bubble">${html}</div>`;
    thread.appendChild(row);
    scrollDown();
    return row;
  }

  function addRow(className, html) {
    const row = document.createElement("div");
    row.className = className;
    row.innerHTML = html;
    thread.appendChild(row);
    scrollDown();
    return row;
  }

  function showTyping() {
    const row = addMsg("bot", '<span class="cq-dots" aria-label="Typing"><i></i><i></i><i></i></span>', "cq-typing");
    return () => row.remove();
  }

  // Bot message after a short "typing…" pause, so it reads like a conversation.
  async function say(html, extraClass, delay = 450) {
    const stop = showTyping();
    await wait(delay);
    stop();
    return addMsg("bot", html, extraClass);
  }

  function updateComposeButtons() {
    const disabled = input.disabled || !input.value.trim();
    sendBtn.disabled = disabled;
    askBtn.disabled = disabled;
  }

  function setInput(on, placeholder) {
    input.disabled = !on;
    updateComposeButtons();
    cq.choice?.buttons.forEach((button) => { button.disabled = !on; });
    if (placeholder) input.placeholder = placeholder;
    if (on) input.focus();
  }

  function updateHeader() {
    const total = Math.max(cq.seen.size, (cq.content[cq.category] || []).length);
    const right = total - cq.pending.size;
    const sections = sectionList();
    document.getElementById("cqKicker").textContent =
      `${subjectLabel()} · Section ${Math.max(sections.indexOf(cq.category) + 1, 1)} of ${sections.length || 1}`;
    document.getElementById("cqTitle").textContent = label(cq.category);
    const fill = document.getElementById("cqFill");
    if (fill) fill.style.width = total ? `${Math.round((right / total) * 100)}%` : "0%";
    const count = document.getElementById("cqCount");
    if (count) {
      count.textContent = total && !cq.pending.size
        ? "Section complete"
        : cq.round === 1 ? `${right} of ${total} right` : `Review round ${cq.round} · ${cq.pending.size} to go`;
    }
  }

  // Quick-reply buttons under a bot message ("Start Dosage" / "Not now").
  async function offerChoice(html, yes, no) {
    const msg = await say(html, "", 500);
    const chips = document.createElement("div");
    chips.className = "cq-chips";
    chips.innerHTML =
      `<button type="button" class="cq-chip is-primary">${esc(yes.label)}</button>` +
      `<button type="button" class="cq-chip">${esc(no.label)}</button>`;
    msg.querySelector(".cq-bubble").appendChild(chips);
    const [yesBtn, noBtn] = chips.querySelectorAll("button");
    const pick = (which, typed) => {
      if (cq.mode !== "choice" || cq.busy) return;
      cq.mode = "idle";
      cq.choice = null;
      chips.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      (which === "yes" ? yesBtn : noBtn).classList.add("is-picked");
      if (!typed) addMsg("user", esc(which === "yes" ? yes.label : no.label));
      (which === "yes" ? yes.run : no.run)();
    };
    yesBtn.addEventListener("click", () => pick("yes"));
    noBtn.addEventListener("click", () => pick("no"));
    cq.choice = { pick, buttons: [yesBtn, noBtn] };
    cq.mode = "choice";
    setInput(true, "Type yes or no…");
    scrollDown();
  }

  // Side panel: a picture of this drug's bonsai.
  function renderSideTree() {
    const mount = document.getElementById("cqTree");
    const note = document.getElementById("cqTreeNote");
    if (!mount || !window.Bonsai) return;
    const svg = Bonsai.thumb(cq.topic || cq.drug);
    mount.innerHTML = svg || '<span class="cq-tree-empty">No bonsai yet</span>';
    if (note) {
      note.innerHTML = svg
        ? "Get every question in a section right to grow it."
        : `Plant one on your <a href="${backUrl()}">lessons page</a>. It grows with every level you finish.`;
    }
  }

  // ---------------------------------------------------------- server lessons
  // Opens a server lesson for the section. Returns its first question, or
  // null if the section can't be started.
  async function openLesson(category, allowGate = true) {
    let r = await lessonApi("start", { category });
    if (!cq.topic && r.status === 403 && allowGate) {
      await clearReviewGate();
      r = await lessonApi("start", { category });
    }
    if (r.status === 400) {
      await say(`${esc(label(category))} isn't unlocked yet. Finish the section before it first.`);
      return null;
    }
    if (!r.ok || !r.data || !r.data.question) throw new Error(`lesson/start ${r.status}`);
    cq.attemptId = r.data.attempt_id;
    cq.endedCleanly = false;
    return r.data.question;
  }

  // Out of hearts (left over from a mini quiz): show the notes for what was
  // missed, then mark them reviewed so learning can continue.
  async function clearReviewGate() {
    const p = await api(`/path/${cq.drug}?username=${encodeURIComponent(getUsername())}`);
    const items = (p.ok && p.data && p.data.review_items) || [];
    if (items.length) {
      const list = items.map((it) => `<li><strong>${fmt(it.question)}</strong>${fmt(it.remediation)}</li>`).join("");
      await say(`Before we start, here are notes on what you missed last time:<ul class="cq-review">${list}</ul>`);
    }
    await api("/lesson/review-complete", {});
  }

  // Hearts ran out mid-section. The notes were already shown in the chat, so
  // close that lesson, count it as reviewed and open a fresh one.
  async function refreshLesson() {
    await lessonApi("complete");
    if (!cq.topic) await api("/lesson/review-complete", {});
    return openLesson(cq.category, false);
  }

  // ---------------------------------------------------------- flow
  async function start() {
    thread = document.getElementById("cqThread");
    input = document.getElementById("cqInput");
    sendBtn = document.getElementById("cqSend");
    askBtn = document.getElementById("cqAsk");
    document.querySelectorAll("[data-cq-back]").forEach((a) => { a.href = backUrl(); });
    renderSideTree();

    input.addEventListener("input", () => {
      updateComposeButtons();
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 140) + "px";
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
    });
    document.getElementById("cqForm").addEventListener("submit", (e) => { e.preventDefault(); onSend(); });
    askBtn.addEventListener("click", () => onSend(true));

    if (!getUsername()) {
      addMsg("bot", 'Please <a href="login.html">log in</a>, or go to the <a href="index.html">home page</a> and choose <strong>Try without an account</strong>, to start.');
      return;
    }

    try {
      const r = await api(cq.topic ? `${topicRoute()}/content` : `/drug-content/${cq.drug}`);
      if (r.ok && r.data && r.data.categories) {
        cq.content = r.data.categories;
        cq.topicName = r.data.topic || "";
        cq.topicChatAvailable = r.data.topic_chat === true;
      }
    } catch (err) {
      console.warn("Chat quiz: content unavailable", err);
    }
    if (cq.topic && !sectionList().length) {
      await say("I couldn't load the questions for this topic. Check that the backend is running with the updated curriculum.");
      offerBack();
      return;
    }
    if (sectionList().length && !sectionList().includes(cq.category)) cq.category = sectionList()[0];

    await say(`Hi! Let's work through <strong>${esc(subjectLabel())}</strong> together. I'll ask you questions one at a time. Just reply in your own words; a few key words are enough.`, "", 350);
    await say("If you miss one, I'll give you notes and we'll keep going. At the end of each section we'll circle back to anything you missed until you've got it.", "", 650);
    await say('For help, type a question or send it with <strong>Ask assistant</strong>. You can also type <strong>hint</strong>. To see the answer and move on, type <strong>skip</strong>.', "", 650);
    await runSection(cq.category);
  }

  async function runSection(category) {
    cq.category = category;
    cq.pending = new Set((cq.content[category] || []).map((o) => o.oid));
    cq.seen = new Set();
    cq.misses = {};
    cq.round = 1;
    cq.current = null;
    updateHeader();

    let first;
    try {
      first = await openLesson(category);
    } catch (err) {
      console.error("Chat quiz: could not start section", err);
      await say("I couldn't start this section. Check that the server is running, then refresh the page.");
      return;
    }
    if (!first) { offerBack(); return; }

    const n = cq.pending.size;
    addRow("cq-divider", `<span>${esc(label(category))}</span>`);
    await say(`<strong>${esc(label(category))}</strong>${n ? `: ${n} question${n === 1 ? "" : "s"}` : ""}. Here's the first one.`, "", 400);
    cq.asked = new Set();
    await serve(first);
  }

  // Ask the question the server handed out, unless this round already asked
  // everything still needed (then the round ends and the lesson is left open;
  // the next /lesson/start replaces it).
  async function serve(q) {
    if (!q) { await endRound(); return; }
    const knownList = !!(cq.content[cq.category] || []).length;
    if (!knownList && cq.round === 1 && !cq.seen.has(q.oid)) cq.pending.add(q.oid); // no content list: learn the oids as we go
    if (!cq.topic && (knownList || cq.round > 1) && !stillNeeded()) { await endRound(); return; }

    cq.current = q;
    updateHeader();
    const tag = !cq.seen.has(q.oid) ? label(cq.category) : cq.pending.has(q.oid) ? "Try again" : "Quick check";
    await say(`<span class="cq-qnum">${esc(tag)}</span>${fmt(q.question)}`, "cq-question", 550);
    cq.mode = "answer";
    setInput(true, answerPlaceholder);
  }

  function onSend(askAssistant = false) {
    if (cq.busy || input.disabled || cq.mode === "idle") return;
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "auto";
    updateComposeButtons();
    addMsg("user", fmt(text));

    const choosing = cq.mode === "choice";
    if (choosing && !askAssistant) {
      if (YES.test(text)) return cq.choice.pick("yes", true);
      if (NO.test(text)) return cq.choice.pick("no", true);
    }

    if (askAssistant || ASIDE_START.test(text) || QUESTION_PHRASE_START.test(text) ||
        (text.endsWith("?") && (choosing || QUESTION_START.test(text)))) {
      return answerAside(text, choosing ? null : cq.current);
    }
    if (choosing) return say("Just say <strong>yes</strong> or <strong>no</strong>, or use the buttons above.");
    const skipped = SKIP_WORDS.includes(text.toLowerCase().replace(/[.!]+$/, ""));
    submitAnswer(skipped ? "" : text, skipped, text);
  }

  // Offer help without advancing the active quiz question.
  async function answerAside(text, returnTo) {
    if (cq.topic && !cq.topicChatAvailable) {
      addMsg("bot", "Restart the backend from the current project folder to enable the assistant for this topic.");
      setInput(true);
      return;
    }
    cq.busy = true;
    setInput(false);
    const stop = showTyping();
    let reply = "Sorry, I couldn't reach the server for that one.";
    let safetyWarning = null;
    try {
      const scope = cq.topic ? {
        topic_code: cq.topic,
        attempt_id: cq.attemptId,
        quiz_oid: returnTo?.oid,
        topic_history: cq.topicHistory,
      } : {
        drug: cq.drug,
        experience_level: learningStorage().getItem("experienceLevel"),
        conversation_id: cq.conversationId,
        page_context: `chat-quiz:${cq.category}`,
        quiz_question: returnTo?.question,
      };
      const r = await apiFetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: getUsername(), message: text, ...scope }),
      });
      if (r.ok) {
        const data = await r.json();
        reply = data.response || reply;
        safetyWarning = data.safety_warning;
        cq.conversationId = data.conversation_id || cq.conversationId;
        if (cq.topic && data.response) {
          cq.topicHistory = [...cq.topicHistory, {
            question: text.slice(0, 1000), reply: data.response.slice(0, 2000),
          }].slice(-3);
        }
      }
    } catch (err) {
      console.error("Chat quiz: aside failed", err);
    }
    stop();
    // The chatbot replies in Markdown (lists, bold); chat-core.js renders it safely.
    addMsg("bot", window.MysChat ? `<div class="mc-md">${window.MysChat.renderMarkdown(reply)}</div>` : fmt(reply));
    if (safetyWarning && typeof renderSafetyWarning === "function") renderSafetyWarning(safetyWarning, thread);
    if (returnTo) await say(`Back to the question: <strong>${fmt(returnTo.question)}</strong>`, "cq-question", 650);
    cq.busy = false;
    setInput(true, cq.mode === "choice" ? "Type yes or no…" : answerPlaceholder);
  }

  async function submitAnswer(answer, skipped, original) {
    cq.busy = true;
    cq.mode = "idle";
    setInput(false);
    const q = cq.current;
    const stop = showTyping();
    let r;
    try {
      r = await lessonApi("answer", { oid: q.oid, answer });
    } catch (err) {
      console.error("Chat quiz: answer failed", err);
      stop();
      addMsg("bot", "I couldn't reach the server, so that answer wasn't saved. Try sending it again.");
      input.value = original;
      cq.busy = false;
      cq.mode = "answer";
      setInput(true);
      return;
    }
    if ((!cq.topic && r.status === 400) || (cq.topic && r.status === 404)) {
      // The server's lesson moved on (e.g. a lesson was started in another tab). Re-sync.
      stop();
      cq.busy = false;
      await say("Let's pick up where we left off.");
      try { await serve(await openLesson(cq.category, true)); } catch (e) { await say("I couldn't reconnect to this lesson. Refresh the page to try again."); }
      return;
    }
    if (!r.ok) {
      stop();
      addMsg("bot", "Something went wrong saving that answer. Try sending it again.");
      input.value = original;
      cq.busy = false;
      cq.mode = "answer";
      setInput(true);
      return;
    }
    const data = r.data;
    await wait(300);
    stop();

    cq.seen.add(q.oid);
    cq.asked.add(q.oid);
    if (data.correct) {
      const wasMissed = !!cq.misses[q.oid];
      cq.pending.delete(q.oid);
      const lead = wasMissed ? "You've got it now." : (data.feedback || "Correct.");
      addMsg("bot", `<span class="cq-verdict is-ok">Correct</span>${esc(lead)}<span class="cq-detail">${fmt(pickText(data.detail))}</span>`);
    } else {
      cq.misses[q.oid] = (cq.misses[q.oid] || 0) + 1;
      cq.pending.add(q.oid);
      const lead = skipped ? "No problem, here are the notes:" : "Here are the notes:";
      // A second miss on the same question also gets the full lesson text.
      const c = contentFor(q.oid);
      const full = c ? pickText(c.lesson_text) : "";
      const extra = cq.misses[q.oid] > 1 && full && full !== pickText(data.detail)
        ? `<span class="cq-notes-more">${fmt(full)}</span>` : "";
      addMsg("bot", `<span class="cq-verdict is-no">${skipped ? "Skipped" : "Not quite"}</span>${esc(lead)}` +
        `<span class="cq-notes"><span class="cq-notes-label">Notes</span>${fmt(pickText(data.detail))}${extra}</span>` +
        `<span class="cq-later">We'll come back to this one.</span>`);
    }
    cq.current = null;
    updateHeader();
    cq.busy = false;

    let next = data.next_question;
    if (data.session_over) {
      if (data.hearts === 0) {
        // Hidden hearts ran out: refill quietly and keep the same round going.
        try { next = await refreshLesson(); } catch (e) { console.error("Chat quiz: refresh failed", e); next = null; }
      } else {
        cq.endedCleanly = true;
        next = null;
        // The server lesson holds at most 5 questions; drop any it never asks.
        if (cq.round === 1) [...cq.pending].forEach((oid) => { if (!cq.seen.has(oid)) cq.pending.delete(oid); });
      }
    }
    await serve(next);
  }

  async function endRound() {
    cq.current = null;
    if (cq.topic && cq.endedCleanly) {
      try {
        const r = await lessonApi("complete");
        if (!r.ok) throw new Error(`lesson/complete ${r.status}`);
        cq.endedCleanly = false;
      } catch (err) {
        console.error("Chat quiz: complete failed", err);
        await say("I couldn't finish saving this round. Your answers were recorded. Return to the lessons page to continue.");
        offerBack();
        return;
      }
    }
    if (cq.pending.size && cq.round < MAX_ROUNDS) {
      cq.round += 1;
      cq.asked = new Set();
      updateHeader();
      const n = cq.pending.size;
      await say(`That's every ${esc(label(cq.category))} question once. Let's go back over the ${n === 1 ? "one" : n} you missed.`, "cq-loop", 600);
      let first;
      try {
        first = await openLesson(cq.category);
      } catch (err) {
        console.error("Chat quiz: could not start review round", err);
        await say("I couldn't start the review. Check that the server is running, then refresh the page.");
        return;
      }
      if (!first) { offerBack(); return; }
      await serve(first);
      return;
    }
    await sectionDone();
  }

  async function sectionDone() {
    cq.mode = "idle";
    setInput(false, "…");
    updateHeader();
    // Only a lesson that reached its last question can be completed (streak, badges).
    if (cq.endedCleanly) {
      try { await lessonApi("complete"); } catch (err) { console.error("Chat quiz: complete failed", err); }
    }
    if (cq.pending.size) {
      await say("Let's pause here. You can retry this section from the lessons page.");
      offerBack();
      return;
    }

    const total = cq.seen.size;
    const firstTry = total - Object.keys(cq.misses).length;
    await say(firstTry === total
      ? `<strong>${esc(label(cq.category))} complete!</strong> You got all ${total} right the first time.`
      : `<strong>${esc(label(cq.category))} complete!</strong> You got ${firstTry} of ${total} right the first time, and now you've got all ${total}.`, "", 500);

    // Bonsai: same growth card as the end of a mini quiz.
    if (window.Bonsai) {
      const row = addRow("cq-msg cq-full", '<div class="bz-lesson"></div>');
      const slot = row.firstElementChild;
      await Bonsai.afterLesson(cq.topic || cq.drug, slot, { course: cq.topic ? cq.course : "" });
      slot.addEventListener("click", () => setTimeout(renderSideTree, 60));
      scrollDown();
    }
    renderSideTree();

    const sections = sectionList().length ? sectionList() : UNITS;
    const next = sections[sections.indexOf(cq.category) + 1];
    if (next) {
      await offerChoice(`Want to start the next section, <strong>${esc(label(next))}</strong>?`,
        { label: `Start ${label(next)}`, run: () => runSection(next) },
        { label: "Not now", run: stopHere });
    } else {
      await offerChoice(`That's every section for ${esc(subjectLabel())}! Want to go around again from <strong>${esc(label(sections[0]))}</strong> to level up?`,
        { label: `Start ${label(sections[0])} again`, run: () => runSection(sections[0]) },
        { label: "I'm done for now", run: stopHere });
    }
  }

  async function stopHere() {
    setInput(false, "Quiz paused");
    await say("Sounds good. Your progress is saved, so you can pick up the next section anytime.");
    offerBack();
  }

  function offerBack() {
    addRow("cq-msg cq-full cq-actions", `<a class="cq-btn is-primary" href="${backUrl()}">Back to lessons</a>`);
  }

  document.addEventListener("DOMContentLoaded", start);
})();
