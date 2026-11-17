// ============================================================
// ui.js — Grove visual layer
// Load AFTER script.js. It replaces only the functions that draw
// the learning path, the lesson screens and the Progress tab, so
// script.js itself stays untouched. All API calls and data are the
// same as before.
// ============================================================

// ---------- Shared helpers ----------

const UNIT_META = {
  Facts:      { color: "lav",   desc: "What it is" },
  Dosage:     { color: "peach", desc: "How much and how often" },
  Procedures: { color: "mint",  desc: "How to take it" },
  Rationales: { color: "sky",   desc: "Why it works" },
};
const UNIT_COLORS = ["lav", "peach", "mint", "sky"];

const EXTRA_ICONS = {
  trophy: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8"></path><path d="M12 17v4"></path><path d="M7 4h10v5a5 5 0 0 1-10 0V4z"></path><path d="M17 5h3v2a3 3 0 0 1-3 3"></path><path d="M7 5H4v2a3 3 0 0 0 3 3"></path></svg>',
  star: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" stroke="none"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z"></path></svg>',
  target: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="5"></circle><circle cx="12" cy="12" r="1"></circle></svg>',
  sound: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"></path><path d="M15.5 8.5a5 5 0 0 1 0 7"></path><path d="M19 5a10 10 0 0 1 0 14"></path></svg>',
  mute: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"></path><line x1="22" y1="9" x2="16" y2="15"></line><line x1="16" y1="9" x2="22" y2="15"></line></svg>',
  assistant: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="9.5" width="15" height="6.5" rx="3.25" transform="rotate(45 12 12.75)"></rect><line x1="9" y1="10" x2="15" y2="16"></line></svg>',
};

// ---------- Learning style: "game" (Duolingo-style) or "focused" (plain) ----------
let lastPath = null;

function getLearningStyle() {
  try { return localStorage.getItem("learningStyle"); } catch (e) { return null; }
}
function isFocused() { return (document.body.dataset.topicLessonMode || getLearningStyle()) === "focused"; }
function applyLearningStyle() {
  if (document.body) document.body.dataset.learning = document.body.dataset.topicLessonMode || getLearningStyle() || "unset";
}
function setLearningStyle(style) {
  try { localStorage.setItem("learningStyle", style); } catch (e) {}
  applyLearningStyle();
  if (lastPath) renderPath(lastPath.drug, lastPath.data);
}
applyLearningStyle();

// The standalone learning page for the current style
function pathPageUrl(drug) {
  const page = isFocused() ? "focused.html" : "game.html";
  return drug ? `${page}?drug=${encodeURIComponent(drug)}` : page;
}

function unitMeta(category, index = 0) {
  return UNIT_META[category] || { color: UNIT_COLORS[index % UNIT_COLORS.length], desc: "" };
}

function unitIcon(category) {
  return (typeof CATEGORY_ICONS !== "undefined" && CATEGORY_ICONS[category]) || ICONS.book;
}

// ============================================================
// LEARNING PATH (Learning Path tab in index.html)
// ============================================================

function renderReviewBanner(data) {
  const reviewBanner = document.getElementById("reviewBanner");
  if (!reviewBanner) return;
  const pending = data.review_items || [];
  const heartsLocked = (data.hearts_remaining || 0) <= 0;
  if (!heartsLocked) {
    reviewBanner.innerHTML = "";
    return;
  }
  const listHtml = pending.length
    ? `<div class="review-list">
        ${pending.map(item => `
          <div class="review-item">
            <p class="review-q">${item.question}</p>
            <p class="review-a">${item.remediation}</p>
          </div>`).join("")}
       </div>`
    : `<p class="review-empty">Nothing on file to review — you can go ahead and try again.</p>`;
  reviewBanner.innerHTML = `
    <div class="review-banner" id="reviewBannerBox">
      <div class="review-banner-head">
        <span class="review-banner-icon">${isFocused() ? ICONS.book : ICONS.heartOutline}</span>
        <div>
          <h3>${isFocused() ? "Review required" : "You're out of hearts"}</h3>
          <p>${isFocused() ? "You missed several questions in a row. Read through these before your next lesson." : "Read through what you missed, then refill your hearts to keep going."}</p>
        </div>
      </div>
      ${listHtml}
      <button class="btn-3d btn-amber" id="pathReviewDoneBtn" onclick="completeReview()">${isFocused() ? "I've reviewed this — continue" : "I've reviewed this — refill hearts"}</button>
    </div>`;
  setTimeout(() => {
    document.getElementById("reviewBannerBox")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 100);
}

// Zig-zag offsets for the five nodes in each unit (px). Units alternate
// direction so the path snakes down the page like Duolingo's.
const NODE_OFFSETS = [0, -56, -84, -56, 0];

function renderPathPreview(topic) {
  return `
    <div class="fp-next">
      <div class="fp-next-text">
        <span class="fp-kicker">Lesson preview</span>
        <h2>${escapeHtml(topic)}</h2>
        <p>Levels will open when lessons and quizzes are available.</p>
      </div>
    </div>`;
}

function pathLessonAction(key, unit) {
  const action = document.body.dataset.lessonSource === "topic" ? "goToTopicLesson" : "goToLesson";
  return escapeHtml(`${action}(${JSON.stringify(key)},${JSON.stringify(unit)})`);
}

function goToTopicLesson(topic, category) {
  const mode = document.body.dataset.pathView;
  const params = new URLSearchParams({
    topic, category, course: getUrlParam("category"), mode,
  });
  const page = mode === "focused" && getFocusedFormat() === "chat" ? "chat-quiz.html" : "lesson.html";
  window.location.href = `${page}?${params}`;
}

function renderPath(drug, data, { previewTopic = "", topicName = "" } = {}) {
  const pathMap = document.getElementById("pathMap");
  if (!pathMap) return;
  const view = document.body.dataset.pathView;
  const preview = Boolean(previewTopic);
  const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  if (preview || topicName) {
    document.body.dataset.learning = view;
  } else {
    lastPath = { drug, data };
    applyLearningStyle();
  }
  if (!preview) {
    setText("statXp", data.xp_total ?? 0);
    setText("statStreak", data.streak_current ?? 0);
    setText("statHearts", data.hearts_remaining ?? 5);
    setText("sideXp", data.xp_total ?? 0);
    setText("sideStreak", data.streak_current ?? 0);
    renderReviewBanner(data);
  }

  if (!data.units || !data.units.length) {
    if (document.body.dataset.pathView === "hub") renderHub(drug, null);
    else pathMap.innerHTML = `<div class="empty-state">No content for this drug yet.</div>`;
    return;
  }

  // Overall mastery (sidebar card)
  let crownSum = 0;
  data.units.forEach(u => { crownSum += u.min_crown; });
  const overallPct = Math.round((crownSum / (data.units.length * 5)) * 100);
  const overallFill = document.getElementById("overallFill");
  if (overallFill) overallFill.style.width = `${overallPct}%`;
  setText("overallLabel", preview ? "Lessons coming soon" : `${overallPct}% mastered`);
  const measure = view === "focused" ? "levels" : "crowns";
  setText("overallCrowns", `${crownSum} of ${data.units.length * 5} ${preview ? "planned " : ""}${measure}`);
  setText("sideLevels", `${crownSum}/${data.units.length * 5}`);
  setText("sideUnits", `${data.units.filter(u => u.min_crown >= 5).length}/${data.units.length}`);

  if (view === "hub") {
    renderHub(drug, data);
    return;
  }
  if (view === "focused" || (!view && isFocused())) {
    renderPathFocused(drug, data, pathMap, previewTopic);
    if (window.Bonsai) {
      if (preview) Bonsai.renderPreview(previewTopic);
      else Bonsai.renderPanel(drug, data, topicName);
    }
    return;
  }

  const heartsLocked = (data.hearts_remaining || 0) <= 0;
  const currentIndex = preview ? -1 : data.units.findIndex(u => u.unlocked && u.min_crown < 5);

  const unitsHtml = data.units.map((unit, i) => {
    const meta = unitMeta(unit.category, i);
    const label = escapeHtml(CATEGORY_LABELS[unit.category] || unit.category);
    const crowns = unit.min_crown;
    const mastered = crowns >= 5;
    const isCurrentUnit = i === currentIndex;
    const canPlay = !preview && unit.unlocked && !heartsLocked;
    const play = pathLessonAction(drug, unit.category);
    const dir = i % 2 === 0 ? 1 : -1;

    let action;
    if (preview) action = '<span class="unit-action is-locked">Coming soon</span>';
    else if (!unit.unlocked) action = `<span class="unit-action is-locked">${ICONS.lock} Locked</span>`;
    else if (mastered) action = `<button class="unit-action" onclick="${play}">Practice</button>`;
    else action = `<button class="unit-action" onclick="${play}">${crowns > 0 ? "Continue" : "Start"}</button>`;

    const nodes = Array.from({ length: 5 }, (_, k) => {
      let state;
      if (preview || !unit.unlocked) state = "locked";
      else if (k < crowns) state = "done";
      else if (k === crowns) state = "next";
      else state = "todo";

      const isLast = k === 4;
      let icon;
      if (state === "locked") icon = isLast ? EXTRA_ICONS.trophy : ICONS.lock;
      else if (state === "done") icon = isLast ? EXTRA_ICONS.trophy : ICONS.check;
      else if (state === "next") icon = isLast ? EXTRA_ICONS.trophy : unitIcon(unit.category);
      else icon = isLast ? EXTRA_ICONS.trophy : EXTRA_ICONS.star;

      const clickable = canPlay && (state === "done" || state === "next");
      const bubble = isCurrentUnit && state === "next" && !heartsLocked
        ? `<span class="start-bubble">${crowns > 0 ? "Continue" : "Start"}</span>`
        : "";
      const title = state === "done" ? `Crown ${k + 1} earned — practice again`
        : state === "next" ? `Earn crown ${k + 1}`
        : state === "locked" ? (preview ? `Level ${k + 1} coming soon` : "Locked") : `Crown ${k + 1}`;

      return `
        <div class="node-slot" style="--x:${NODE_OFFSETS[k] * dir}px">
          ${bubble}
          <button class="path-node ${state}${isCurrentUnit && state === "next" ? " current" : ""}"
            ${clickable ? `onclick="${play}"` : "disabled"} title="${title}" aria-label="${label}: ${title}">
            <span class="node-face">${icon}</span>
          </button>
        </div>`;
    }).join("");

    const crownDots = Array.from({ length: 5 }, (_, k) =>
      `<span class="crown-dot${k < crowns ? " filled" : ""}">${ICONS.crown}</span>`).join("");

    return `
      <section class="unit u-${meta.color}${unit.unlocked ? "" : " is-locked"}${mastered ? " is-mastered" : ""}" style="animation-delay:${i * 80}ms">
        <header class="unit-banner">
          <div class="unit-banner-text">
            <span class="unit-kicker">Unit ${i + 1}${mastered ? " · Mastered" : ""}</span>
            <h2>${label}</h2>
            ${preview ? "" : `<p>${meta.desc}${unit.objective_count ? ` · ${unit.objective_count} objective${unit.objective_count === 1 ? "" : "s"}` : ""}</p>`}
            <div class="unit-crowns">${crownDots}<span>${crowns}/5</span></div>
          </div>
          ${action}
        </header>
        <div class="unit-nodes">${nodes}</div>
        ${preview || unit.unlocked ? "" : `<p class="unit-lock-note">Earn a crown in every ${data.units[i - 1] ? (CATEGORY_LABELS[data.units[i - 1].category] || data.units[i - 1].category) : "earlier"} objective to unlock</p>`}
      </section>`;
  }).join("");
  pathMap.innerHTML = (preview ? renderPathPreview(previewTopic) : "") + unitsHtml;

  if (!preview && !topicName && window.Critter) {
    Critter.syncProgress(drug, data);
    Critter.renderCard();
    Critter.placeOnPath(pathMap);
  }
}

// Drug lesson mode chooser on index.html.
function renderHub(drug, data) {
  const pathMap = document.getElementById("pathMap");
  if (!pathMap) return;
  const q = drug ? `?drug=${encodeURIComponent(drug)}` : "";
  const label = (c) => (typeof CATEGORY_LABELS !== "undefined" && CATEGORY_LABELS[c]) || c;

  let gameMeta = getUsername() ? "" : "Sign in to save your progress";
  let focusedMeta = gameMeta;
  if (data && data.units && data.units.length) {
    const total = data.units.length * 5;
    const done = data.units.reduce((n, u) => n + u.min_crown, 0);
    const next = data.units.find(u => u.unlocked && u.min_crown < 5);
    gameMeta = `${done} of ${total} crowns · ${data.streak_current ?? 0}-day streak · ${data.xp_total ?? 0} XP`;
    focusedMeta = next
      ? `Next up: ${label(next.category)} · level ${next.min_crown + 1} of 5`
      : "All lessons complete";
  }
  const bonsaiThumb = window.Bonsai && drug ? Bonsai.thumb(drug) : "";
  const buddy = window.Critter && Critter.has() ? Critter.sprite(null, { background: false }) : "";
  renderModeChoices(pathMap, {
    gameHref: `game.html${q}`, focusedHref: `focused.html${q}`,
    gameMeta, focusedMeta, bonsaiThumb, buddy,
  });
}

function renderModeChoices(mount, { gameHref, focusedHref, gameMeta, focusedMeta, bonsaiThumb, buddy, outline = false }) {
  const last = getLearningStyle();
  const node = (cls, icon) => `<span class="mini-node ${cls}">${icon}</span>`;
  mount.innerHTML = `
    <div class="hub">
      <a class="style-card sc-game hub-card" href="${escapeHtml(gameHref)}">
        ${!outline && last === "game" ? `<span class="hub-badge">Last used</span>` : ""}
        <span class="style-preview">
          ${node("done", ICONS.check)}${node("done shift", ICONS.check)}${node("next", ICONS.book)}${buddy ? `<span class="crit-hub-pet">${buddy}</span>` : node("todo shift", EXTRA_ICONS.star)}
        </span>
        <span class="style-title">Game Mode</span>
        <span class="style-desc">${outline ? "Explore the core skills as a game path." : "A winding path with XP, daily streaks and hearts. Short rounds with sounds and celebrations."}</span>
        <span class="style-tags"><span>Motivating</span><span>Playful</span></span>
        ${gameMeta ? `<span class="hub-meta">${gameMeta}</span>` : ""}
        <span class="hub-open">Open game mode <span aria-hidden="true">→</span></span>
      </a>
      <a class="style-card sc-focused hub-card" href="${escapeHtml(focusedHref)}">
        ${!outline && last === "focused" ? `<span class="hub-badge">Last used</span>` : ""}
        ${bonsaiThumb
          ? `<span class="style-preview bz-hub-preview">${bonsaiThumb}</span>`
          : `<span class="style-preview list">
          <span class="mini-row"><i class="ok"></i><b></b></span>
          <span class="mini-row"><i class="ok"></i><b></b></span>
          <span class="mini-row"><i class="cur"></i><b></b></span>
          <span class="mini-row"><i class="lock"></i><b></b></span>
        </span>`}
        <span class="style-title">Focused Lessons</span>
        <span class="style-desc">${outline ? "Explore the core skills in a straightforward list." : "A simple lesson list. One question at a time with a clear explanation, and a bonsai that grows as you learn."}</span>
        <span class="style-tags"><span>Efficient</span><span>No distractions</span></span>
        ${focusedMeta ? `<span class="hub-meta">${focusedMeta}</span>` : ""}
        <span class="hub-open">Open focused lessons <span aria-hidden="true">→</span></span>
      </a>
    </div>
    ${outline ? "" : '<p class="hub-note">Both use the same progress, so you can switch between them any time.</p>'}`;
}

function renderPathFocused(drug, data, pathMap, previewTopic) {
  const preview = Boolean(previewTopic);
  const heartsLocked = (data.hearts_remaining || 0) <= 0;
  const units = data.units;
  const totalLevels = units.length * 5;
  const doneLevels = units.reduce((n, u) => n + u.min_crown, 0);
  const next = units.find(u => u.unlocked && u.min_crown < 5);
  const label = (c) => escapeHtml(CATEGORY_LABELS[c] || c);

  let nextCard;
  if (preview) {
    nextCard = renderPathPreview(previewTopic);
  } else if (next) {
    const meta = unitMeta(next.category);
    nextCard = `
      <div class="fp-next u-${meta.color}">
        <div class="fp-next-text">
          <span class="fp-kicker">Next lesson</span>
          <h2>${label(next.category)}: ${meta.desc}</h2>
          <p>Level ${next.min_crown + 1} of 5 · about 3 minutes</p>
        </div>
        ${heartsLocked
          ? `<span class="fp-btn is-disabled">Review required first</span>`
          : `<button class="fp-btn" onclick="${pathLessonAction(drug, next.category)}">Start lesson</button>`}
      </div>`;
  } else {
    nextCard = `
      <div class="fp-next is-done">
        <div class="fp-next-text">
          <span class="fp-kicker">All lessons complete</span>
          <h2>You've finished every level</h2>
          <p>Repeat any lesson below to keep it fresh.</p>
        </div>
      </div>`;
  }

  const rows = units.map((unit, i) => {
    const meta = unitMeta(unit.category, i);
    const crowns = unit.min_crown;
    const mastered = crowns >= 5;
    const canPlay = !preview && unit.unlocked && !heartsLocked;
    const play = pathLessonAction(drug, unit.category);
    const segs = Array.from({ length: 5 }, (_, k) => `<i class="${k < crowns ? "on" : ""}"></i>`).join("");
    let status;
    if (preview) status = '<span class="fp-status fp-preview-status">Coming soon</span>';
    else if (!unit.unlocked) status = `<span class="fp-status is-locked">${ICONS.lock} Locked</span>`;
    else if (mastered) status = `<span class="fp-status is-done">${ICONS.check} Completed</span>`;
    else status = `<span class="fp-status is-open">${crowns > 0 ? "Continue" : "Start"} <span aria-hidden="true">›</span></span>`;
    const tag = canPlay ? "button" : "div";
    return `
      <${tag} class="fp-row u-${meta.color}${preview || unit.unlocked ? "" : " is-locked"}${mastered ? " is-mastered" : ""}" ${canPlay ? `onclick="${play}"` : ""}>
        <span class="fp-icon">${preview ? unitIcon(unit.category) : unit.unlocked ? (mastered ? ICONS.check : unitIcon(unit.category)) : ICONS.lock}</span>
        <span class="fp-main">
          <span class="fp-title">${i + 1}. ${label(unit.category)}</span>
          ${preview ? "" : `<span class="fp-sub">${meta.desc}${unit.objective_count ? ` · ${unit.objective_count} objectives` : ""}${unit.unlocked ? "" : " · finish the previous unit to unlock"}</span>`}
          <span class="fp-levels" aria-label="${crowns} of 5 levels complete">${segs}<em>${crowns}/5 levels</em></span>
        </span>
        ${status}
      </${tag}>`;
  }).join("");

  pathMap.innerHTML = `
    ${nextCard}
    <div class="fp-list">
      <div class="fp-list-head">
        <span>Core skills</span>
        <span>${preview ? `${totalLevels} planned levels` : `${doneLevels} of ${totalLevels} levels complete`}</span>
      </div>
      ${rows}
    </div>`;
}

// ============================================================
// LESSON (lesson.html) — Duolingo-style flow
// ============================================================

let lessonUi = { answered: false, onContinue: null, busy: false };

// ---- Sound (tiny WebAudio chimes, no files needed) ----
function soundOn() {
  try { return localStorage.getItem("lessonSound") !== "off"; } catch (e) { return true; }
}
function toggleSound() {
  try { localStorage.setItem("lessonSound", soundOn() ? "off" : "on"); } catch (e) {}
  renderSoundButton();
}
function renderSoundButton() {
  const btn = document.getElementById("soundToggle");
  if (!btn) return;
  btn.innerHTML = soundOn() ? EXTRA_ICONS.sound : EXTRA_ICONS.mute;
  btn.setAttribute("aria-label", soundOn() ? "Mute sounds" : "Turn sounds on");
  btn.title = btn.getAttribute("aria-label");
}
let audioCtx = null;
function playTones(notes) {
  if (!soundOn() || isFocused()) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;
    notes.forEach(([freq, start, dur, type = "sine", vol = 0.12]) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + start);
      gain.gain.exponentialRampToValueAtTime(vol, now + start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + start);
      osc.stop(now + start + dur + 0.05);
    });
  } catch (e) { /* sound is optional */ }
}
const SOUNDS = {
  correct: () => playTones([[660, 0, 0.12], [880, 0.1, 0.22]]),
  wrong: () => playTones([[220, 0, 0.18, "triangle", 0.14], [180, 0.14, 0.28, "triangle", 0.12]]),
  complete: () => playTones([[523, 0, 0.14], [659, 0.12, 0.14], [784, 0.24, 0.14], [1047, 0.36, 0.35]]),
};

// ---- Footer (the Duolingo bottom bar) ----
function renderFooter(state, opts = {}) {
  const footer = document.getElementById("lessonFooter");
  if (!footer) return;
  footer.className = `lesson-footer is-${state}`;

  if (state === "idle") {
    footer.innerHTML = `
      <div class="footer-inner">
        ${isFocused() ? "<span></span>" : `<button class="btn-3d btn-ghost" id="skipBtn" onclick="skipQuestion()">Skip</button>`}
        <button class="btn-3d btn-primary" id="checkBtn" onclick="submitLessonAnswer()" disabled>${isFocused() ? "Submit answer" : "Check"}</button>
      </div>`;
    return;
  }

  if (state === "correct" || state === "wrong") {
    const ok = state === "correct";
    const extra = isFocused() ? "" : ok
      ? (opts.combo >= 2 ? `<span class="fb-chip fb-combo">${ICONS.flame} ${opts.combo} in a row</span>` : "")
        + (opts.xp > 0 ? `<span class="fb-chip fb-xp">+${opts.xp} XP</span>` : "")
      : `<span class="fb-chip fb-heart">${ICONS.heartFilled} −1</span>`;
    footer.innerHTML = `
      <div class="footer-inner">
        <div class="fb">
          <span class="fb-icon">${ok ? ICONS.check : ICONS.x}</span>
          <div class="fb-text">
            <div class="fb-title">${isFocused() ? (ok ? "Correct" : "Not quite") : (ok ? "Nice!" : "Not quite")} ${extra}</div>
            <p class="fb-flavor">${opts.feedback || ""}</p>
            ${opts.detail ? `<p class="fb-detail"><strong>${ok ? "Why it's right:" : "Correct idea:"}</strong> ${opts.detail}</p>` : ""}
            ${typeof window.openChatWith === "function" ? `<a href="#" class="fb-ask" onclick="askAssistantAboutQuestion(${ok}); return false;">${ok ? "Ask the assistant to go deeper" : "Ask the assistant to explain this"} &rarr;</a>` : ""}
          </div>
        </div>
        <button class="btn-3d ${ok ? "btn-green" : "btn-red"}" id="continueBtn" onclick="lessonContinue()">${opts.label || "Continue"}</button>
      </div>`;
    setTimeout(() => document.getElementById("continueBtn")?.focus(), 50);
    return;
  }

  // summary / custom footer
  footer.innerHTML = `<div class="footer-inner footer-end">${opts.html || ""}</div>`;
}

// Opens the floating learning assistant with the question the learner just answered.
function askAssistantAboutQuestion(correct) {
  if (typeof window.openChatWith !== "function" || !lessonUi.question) return;
  const unit = lessonUi.questionCategory || lessonState.category || "lesson";
  const answer = lessonUi.lastAnswer ? `"${lessonUi.lastAnswer}"` : "nothing (I skipped it)";
  window.openChatWith(correct
    ? `I got this ${unit} question right: "${lessonUi.question}". Can you explain the idea a bit deeper?`
    : `I got this ${unit} question wrong: "${lessonUi.question}". I answered ${answer}. Can you explain the right idea in a different way?`);
}

function lessonContinue() {
  if (typeof lessonUi.onContinue === "function") {
    const fn = lessonUi.onContinue;
    lessonUi.onContinue = null;
    fn();
  }
}

// Keyboard: Enter checks, Enter again continues (like Duolingo)
document.addEventListener("keydown", (e) => {
  if (!document.getElementById("lessonFooter")) return;
  if (e.target && e.target.closest && e.target.closest("#mcwRoot")) return; // typing in the chat widget
  if (e.key !== "Enter" || e.shiftKey) return;
  if (lessonUi.answered && lessonUi.onContinue) {
    e.preventDefault();
    lessonContinue();
  } else if (document.activeElement && document.activeElement.id === "lessonAnswer") {
    e.preventDefault();
    const btn = document.getElementById("checkBtn");
    if (btn && !btn.disabled) submitLessonAnswer();
  }
});

// ---- Hearts + progress ----
function updateHearts(hearts, animateLossIndex) {
  const el = document.getElementById("heartsDisplay");
  if (!el) return;
  const lost = animateLossIndex !== undefined;
  el.innerHTML = `<span class="hearts-icon${hearts <= 0 ? " empty" : ""}">${hearts > 0 ? ICONS.heartFilled : ICONS.heartOutline}</span><span class="hearts-count">${hearts}</span>`;
  el.setAttribute("aria-label", `${hearts} hearts left`);
  if (lost) {
    el.classList.remove("shake");
    void el.offsetWidth;
    el.classList.add("shake");
  }
  lessonState.currentHearts = hearts;
}

function updateProgress(index, total) {
  const fill = document.getElementById("progressFill");
  if (!fill) return;
  const pct = total > 0 ? Math.min(100, Math.round((index / total) * 100)) : 0;
  fill.style.width = `${Math.max(pct, 2)}%`;
}

// ---- Screens ----
function lessonScreen(html) {
  const body = document.getElementById("lessonBody");
  if (body) body.innerHTML = html;
}

function lessonReturnUrl() {
  if (lessonState.topic) {
    return lessonPageUrl(lessonState.course, lessonState.mode, lessonState.topic);
  }
  return pathPageUrl(lessonState.drug);
}

function lessonRequest(action, payload = {}) {
  const { topic, attemptId, drug } = lessonState;
  const base = topic ? `/topics/${encodeURIComponent(topic)}/lesson` : "/lesson";
  const scope = topic ? { attempt_id: attemptId } : { username: getUsername(), drug };
  return apiFetch(`${BASE_URL}${base}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...scope, ...payload }),
  });
}

function finishLessonReview() {
  if (lessonState.topic) window.location.href = lessonReturnUrl();
  else completeReview();
}

async function initLesson() {
  const drug = getUrlParam("drug") || "amoxicillin";
  const category = getUrlParam("category") || "Facts";
  const topic = getUrlParam("topic");
  const course = getUrlParam("course") || "conditions";
  const mode = document.body.dataset.topicLessonMode;
  lessonState = { drug, category, topic, course, mode, totalQuestions: 0, currentOid: null, questionNumber: 0, currentHearts: 5 };
  lessonUi = { answered: false, onContinue: null, busy: false };
  if (!topic) loadSavedArchetype();
  renderSoundButton();
  document.body.dataset.unit = unitMeta(category).color;
  const exitLink = document.getElementById("exitLesson");
  if (exitLink) exitLink.href = lessonReturnUrl();

  try {
    const response = await lessonRequest("start", { category });
    if (response.status === 403) {
      updateHearts(0);
      lessonScreen(`
        <div class="end-screen">
          <div class="end-badge is-hearts">${isFocused() ? ICONS.book : ICONS.heartOutline}</div>
          <h1>${isFocused() ? "Review required" : "You're out of hearts"}</h1>
          <p class="end-note">${isFocused() ? "Read through the questions you missed on the lessons page, then continue." : "Review what you missed on your learning path, then refill your hearts to keep going."}</p>
        </div>`);
      renderFooter("end", { html: `<button class="btn-3d btn-primary" onclick="window.location.href=lessonReturnUrl()">Go to review</button>` });
      return;
    }
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    lessonState.attemptId = data.attempt_id;
    lessonState.totalQuestions = data.total_questions;
    updateHearts(data.hearts);
    updateProgress(0, data.total_questions);

    if (data.question) {
      lessonState.currentOid = data.question.oid;
      lessonState.questionNumber = 1;
      renderQuestion(data.question);
    } else {
      renderNoQuestions();
    }
  } catch (error) {
    console.error("Failed to start lesson:", error);
    lessonScreen(`
      <div class="end-screen">
        <h1>Couldn't start this lesson</h1>
        <p class="end-note">Check that the server is running, then try again.</p>
      </div>`);
    renderFooter("end", { html: `<button class="btn-3d btn-primary" onclick="window.location.href=lessonReturnUrl()">Back to path</button>` });
  }
}

function renderQuestion(question) {
  const category = question.category || lessonState.category;
  const meta = unitMeta(category);
  const label = (typeof CATEGORY_LABELS !== "undefined" && CATEGORY_LABELS[category]) || category;
  lessonUi.answered = false;
  lessonUi.onContinue = null;
  lessonUi.question = question.question;
  lessonUi.questionCategory = category;

  lessonScreen(`
    <div class="q-wrap" id="lessonCard">
      <div class="q-kicker">
        <span class="cat-chip u-${meta.color}">${unitIcon(category)} ${label}</span>
        <span class="q-count">Question ${lessonState.questionNumber} of ${lessonState.totalQuestions}</span>
      </div>
      <h1 class="q-title">${isFocused() ? "" : "Answer in your own words"}</h1>
      <div class="q-prompt">
        ${!lessonState.topic && !isFocused() && window.Critter && Critter.has()
          ? `<span class="q-avatar q-critter crit-idle" id="lessonCritter">${Critter.sprite(null, { background: false })}</span>`
          : `<span class="q-avatar">${EXTRA_ICONS.assistant}</span>`}
        <div class="q-bubble">${question.question}</div>
      </div>
      <textarea id="lessonAnswer" class="q-input" placeholder="Type your answer…" rows="3"></textarea>
      <p class="q-hint">A few key words are enough. Press <kbd>Enter</kbd> to check.</p>
    </div>`);
  renderFooter("idle");

  const textarea = document.getElementById("lessonAnswer");
  const checkBtn = document.getElementById("checkBtn");
  if (textarea) {
    textarea.addEventListener("input", () => {
      if (checkBtn) checkBtn.disabled = !textarea.value.trim();
    });
    textarea.focus();
  }
}

function renderNoQuestions() {
  lessonScreen(`
    <div class="end-screen">
      <h1>Nothing to practice here yet</h1>
      <p class="end-note">This unit doesn't have any questions for this drug.</p>
    </div>`);
  renderFooter("end", { html: `<button class="btn-3d btn-primary" onclick="window.location.href=lessonReturnUrl()">Back to path</button>` });
}

function skipQuestion() {
  submitLessonAnswer(true);
}

async function submitLessonAnswer(skipped = false) {
  if (lessonUi.busy || lessonUi.answered) return;
  const textarea = document.getElementById("lessonAnswer");
  if (!textarea) return;
  const answer = skipped ? "" : textarea.value.trim();
  if (!answer && !skipped) return;
  lessonUi.lastAnswer = answer;

  lessonUi.busy = true;
  const checkBtn = document.getElementById("checkBtn");
  const skipBtn = document.getElementById("skipBtn");
  if (checkBtn) { checkBtn.disabled = true; checkBtn.textContent = "Checking…"; }
  if (skipBtn) skipBtn.disabled = true;

  try {
    const response = await lessonRequest("answer", { oid: lessonState.currentOid, answer });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    lessonUi.answered = true;
    const lostIndex = (!data.correct && data.hearts < lessonState.currentHearts) ? data.hearts : undefined;
    updateHearts(data.hearts, lostIndex);
    updateProgress(lessonState.questionNumber, lessonState.totalQuestions);

    textarea.disabled = true;
    const card = document.getElementById("lessonCard");
    if (card) card.classList.add(data.correct ? "is-correct" : "is-wrong");
    const buddy = document.getElementById("lessonCritter");
    if (buddy) { buddy.classList.remove("crit-idle"); buddy.classList.add(data.correct ? "crit-happy" : "crit-sad"); }
    (data.correct ? SOUNDS.correct : SOUNDS.wrong)();

    renderFooter(data.correct ? "correct" : "wrong", {
      feedback: data.feedback,
      detail: data.detail,
      xp: data.xp_gained,
      combo: data.combo,
      label: data.session_over ? "See results" : "Continue",
    });

    lessonUi.onContinue = () => {
      if (data.session_over) {
        finishLesson();
      } else {
        lessonState.currentOid = data.next_question.oid;
        lessonState.questionNumber += 1;
        renderQuestion(data.next_question);
      }
    };
  } catch (error) {
    console.error("Failed to submit answer:", error);
    if (checkBtn) { checkBtn.disabled = false; checkBtn.textContent = "Check"; }
    if (skipBtn) skipBtn.disabled = false;
    const hint = document.querySelector(".q-hint");
    if (hint) hint.innerHTML = `<span class="q-error">Couldn't reach the server — try again.</span>`;
  } finally {
    lessonUi.busy = false;
  }
}

async function finishLesson() {
  lessonUi.answered = false;
  renderFooter("end", { html: `<button class="btn-3d btn-primary" disabled>Saving…</button>` });
  try {
    const response = await lessonRequest("complete");
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    updateProgress(lessonState.totalQuestions, lessonState.totalQuestions);

    const ranOut = !!data.ran_out_of_hearts;
    const answered = data.questions_answered || 0;
    const correct = data.questions_correct || 0;
    const accuracy = answered > 0 ? Math.round((correct / answered) * 100) : 0;
    const mostlyWrong = !ranOut && answered > 0 && accuracy < 60;
    const celebrate = !ranOut && !mostlyWrong;

    const headline = ranOut ? "Out of hearts" : mostlyWrong ? "Lesson finished" : (accuracy === 100 ? "Perfect lesson!" : "Lesson complete!");
    const sub = ranOut
      ? `You answered ${answered} of ${data.total_questions} before running out of hearts. Crowns you earned are saved.`
      : mostlyWrong
        ? `You got ${correct} of ${answered} right. Another round will help this stick.`
        : `You got ${correct} of ${answered} right. Keep the streak going!`;
    const badgeClass = ranOut ? "is-hearts" : mostlyWrong ? "is-review" : "is-win";
    const badgeIcon = ranOut ? ICONS.heartOutline : mostlyWrong ? ICONS.book : EXTRA_ICONS.trophy;

    const badges = (data.badges_earned || []).map(b =>
      `<span class="badge-pill">${EXTRA_ICONS.star} ${b.replace(/_/g, " ")}</span>`).join("");

    const reviewItems = data.review_items || [];
    const reviewHtml = ranOut ? `
      <div class="end-review">
        <h3>Review before you retry</h3>
        ${reviewItems.map(item => `
          <div class="review-item">
            <p class="review-q">${item.question}</p>
            <p class="review-a">${item.remediation}</p>
          </div>`).join("") || `<p class="end-note">No missed questions to review — you can try again.</p>`}
      </div>` : "";

    if (isFocused()) {
      const focusedHeadline = ranOut ? "Review required" : mostlyWrong ? "Lesson finished" : "Lesson complete";
      const focusedNote = ranOut
        ? `You answered ${answered} of ${data.total_questions}. Read the points below, then continue.`
        : mostlyWrong
          ? "Repeating this lesson will help it stick."
          : "Your progress has been saved.";
      lessonScreen(`
        <div class="end-screen end-focused">
          <span class="fp-kicker">${(typeof CATEGORY_LABELS !== "undefined" && CATEGORY_LABELS[lessonState.category]) || lessonState.category}</span>
          <h1>${focusedHeadline}</h1>
          <p class="end-note">${focusedNote}</p>
          <dl class="end-summary">
            <div><dt>Score</dt><dd>${correct} of ${answered}</dd></div>
            <div><dt>Accuracy</dt><dd>${accuracy}%</dd></div>
            <div><dt>Questions</dt><dd>${answered} of ${data.total_questions}</dd></div>
          </dl>
          ${reviewHtml}
        </div>
        <div id="bonsaiSlot" class="bz-lesson"></div>`);
      if (window.Bonsai) {
        Bonsai.afterLesson(lessonState.topic || lessonState.drug, document.getElementById("bonsaiSlot"), {
          course: lessonState.topic ? lessonState.course : "",
        });
      }
      renderFooter("end", {
        html: ranOut
          ? `<button class="btn-3d btn-primary" id="reviewDoneBtn" onclick="finishLessonReview()">I've reviewed this — continue</button>`
          : `<button class="btn-3d btn-ghost" onclick="window.location.reload()">Repeat lesson</button>
             <button class="btn-3d btn-primary" id="continueBtn" onclick="window.location.href=lessonReturnUrl()">Back to lessons</button>`
      });
      lessonUi.onContinue = ranOut ? null : () => { window.location.href = lessonReturnUrl(); };
      lessonUi.answered = !ranOut;
      return;
    }

    const reward = !lessonState.topic && window.Critter ? Critter.rewardLesson({ ranOut, accuracy, streak: data.streak_current }) : null;
    const buddyHtml = !lessonState.topic && window.Critter && Critter.has()
      ? `<div class="end-critter ${celebrate ? "crit-happy is-loop" : "crit-sad"}">${Critter.sprite(null)}</div>`
      : `<div class="end-badge ${badgeClass}">${badgeIcon}</div>`;
    const coinsHtml = reward && reward.total > 0
      ? `<div class="coin-earned">${Critter.coinIcon}<strong>+${reward.total} coins</strong><span>${reward.lines.map(([t, n]) => `${t} +${n}`).join(" · ")}</span></div>`
      : "";

    lessonScreen(`
      <div class="end-screen">
        ${buddyHtml}
        <h1>${headline}</h1>
        <p class="end-note">${sub}</p>
        ${coinsHtml}
        <div class="end-stats">
          <div class="end-stat s-xp"><span class="end-stat-label">Total XP</span><span class="end-stat-value">${ICONS.bolt} ${data.xp_earned}</span></div>
          <div class="end-stat s-acc"><span class="end-stat-label">Accuracy</span><span class="end-stat-value">${EXTRA_ICONS.target} ${accuracy}%</span></div>
          <div class="end-stat s-streak"><span class="end-stat-label">Streak</span><span class="end-stat-value">${ICONS.flame} ${data.streak_current}</span></div>
          <div class="end-stat s-hearts"><span class="end-stat-label">Hearts</span><span class="end-stat-value">${ICONS.heartFilled} ${data.hearts_remaining}</span></div>
        </div>
        ${badges ? `<div class="badge-row"><span class="badge-row-label">New badge${(data.badges_earned || []).length > 1 ? "s" : ""}</span>${badges}</div>` : ""}
        ${reviewHtml}
      </div>`);

    renderFooter("end", {
      html: ranOut
        ? `<button class="btn-3d btn-amber" id="reviewDoneBtn" onclick="finishLessonReview()">I've reviewed this — refill hearts</button>`
        : `<button class="btn-3d btn-ghost" onclick="window.location.reload()">Practice again</button>
           <button class="btn-3d btn-primary" id="continueBtn" onclick="window.location.href=lessonReturnUrl()">Continue</button>`
    });
    lessonUi.onContinue = ranOut ? null : () => { window.location.href = lessonReturnUrl(); };
    lessonUi.answered = !ranOut;

    if (celebrate) { SOUNDS.complete(); launchConfetti(); }
  } catch (error) {
    console.error("Failed to complete lesson:", error);
    lessonScreen(`
      <div class="end-screen">
        <h1>Lesson finished</h1>
        <p class="end-note">We couldn't save the summary, but your answers were recorded.</p>
      </div>`);
    renderFooter("end", { html: `<button class="btn-3d btn-primary" onclick="window.location.href=lessonReturnUrl()">Back to path</button>` });
  }
}

// ============================================================
// PROGRESS TAB (index.html)
// ============================================================

// Opens the Initial Quiz tab (it lives under "Classic mode" in the sidebar)
function openInitialQuiz() {
  const btn = document.querySelector(`.sidebar .nav-menu-item[onclick*="'quiz'"]`);
  const group = btn && btn.closest("details");
  if (group) group.open = true;
  showTab("quiz", btn);
}

async function loadProgress() {
  const progressContent = document.getElementById("progressContent");
  if (!progressContent) return;

  if (!getUsername()) {
    progressContent.innerHTML = `
      <div class="pg-empty">
        <span class="tint t-lav">${ICONS.lock}</span>
        <div>
          <h3>Sign in to see your progress</h3>
          <p>Log in or try without an account to start tracking what you've learned.</p>
        </div>
      </div>`;
    return;
  }

  try {
    const drug = getSelectedDrug();
    const user = encodeURIComponent(getUsername());
    const [progressRes, profileRes] = await Promise.all([
      apiFetch(`${BASE_URL}/progress/${drug}?username=${user}`),
      apiFetch(`${BASE_URL}/profile/${user}`).catch(() => null),
    ]);
    if (!progressRes.ok) throw new Error(`HTTP error ${progressRes.status}`);
    const data = await progressRes.json();
    let profile = {};
    if (profileRes && profileRes.ok) {
      try { profile = await profileRes.json(); } catch (e) {}
    }

    const pct = data.total ? Math.round((data.known / data.total) * 100) : 0;
    const R = 52, C = 2 * Math.PI * R;
    const order = ["Facts", "Dosage", "Procedures", "Rationales"];
    const cats = Object.entries(data.by_category || {})
      .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
    const results = data.last_results || [];

    progressContent.innerHTML = `
      <p class="pg-lead">How well you know <strong>${data.drug}</strong>, based on your quizzes and lessons.</p>

      <div class="pg-hero">
        <div class="pg-ring-card">
          <svg class="pg-ring" viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r="${R}" class="pg-ring-bg"></circle>
            <circle cx="60" cy="60" r="${R}" class="pg-ring-fill" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct / 100)}"></circle>
          </svg>
          <div class="pg-ring-text"><strong>${pct}%</strong><span>mastered</span></div>
          <div class="pg-ring-meta">
            <h3>${data.known} of ${data.total} objectives</h3>
            <p>${pct === 100 ? "Everything mastered — nice work." : "Keep going on your learning path to fill the ring."}</p>
            <a class="pg-link" href="index.html#path">Open learning path →</a>
          </div>
        </div>
        <div class="pg-stat s-xp"><span class="pg-stat-icon">${ICONS.bolt}</span><strong>${profile.xp_total ?? 0}</strong><span>Total XP</span></div>
        <div class="pg-stat s-streak"><span class="pg-stat-icon">${ICONS.flame}</span><strong>${profile.streak_current ?? 0}</strong><span>Day streak</span></div>
        <div class="pg-stat s-hearts"><span class="pg-stat-icon">${ICONS.heartFilled}</span><strong>${profile.hearts_remaining ?? 5}</strong><span>Hearts</span></div>
      </div>

      <h2 class="pg-h2">By knowledge type</h2>
      <div class="pg-cats">
        ${cats.map(([category, stats]) => {
          const meta = unitMeta(category);
          const p = stats.total ? Math.round((stats.known / stats.total) * 100) : 0;
          return `
            <div class="pg-cat u-${meta.color}">
              <div class="pg-cat-head">
                <span class="pg-cat-icon">${unitIcon(category)}</span>
                <div><h3>${category}</h3><p>${meta.desc}</p></div>
                <span class="pg-cat-pct">${p}%</span>
              </div>
              <div class="pg-bar"><i style="width:${p}%"></i></div>
              <p class="pg-cat-count">${stats.known} of ${stats.total} mastered</p>
            </div>`;
        }).join("")}
      </div>

      <div class="pg-h2-row">
        <h2 class="pg-h2">Initial quiz results</h2>
        ${results.length ? `<button type="button" class="pg-quiz-link" onclick="openInitialQuiz()">Retake the initial quiz →</button>` : ""}
      </div>
      <div class="pg-results">
        ${results.length ? results.map(r => `
          <div class="pg-result ${r.correct ? "ok" : "miss"}">
            <span class="pg-result-icon">${r.correct ? ICONS.check : ICONS.x}</span>
            <div>
              <p class="pg-result-q">${r.question || r.oid}</p>
              <p class="pg-result-m">${r.correct ? "Correct" : r.message}</p>
            </div>
            ${r.category ? `<span class="pg-result-cat">${r.category}</span>` : ""}
          </div>`).join("")
        : `<div class="pg-quiz-cta">
             <span class="tint t-lav">${ICONS.book}</span>
             <div>
               <h3>See what you already know</h3>
               <p>The initial quiz is a quick one-time check of every topic for ${data.drug}. Your answers show up here, and the learning path takes care of the rest.</p>
             </div>
             <button type="button" class="pg-quiz-btn" onclick="openInitialQuiz()">Take the initial quiz</button>
           </div>`}
      </div>`;
  } catch (error) {
    console.error("Failed to load progress:", error);
    progressContent.innerHTML = `<div class="pg-empty"><div><h3>Couldn't load your progress</h3><p>Check that the server is running and you've completed the security check.</p></div></div>`;
  }
}