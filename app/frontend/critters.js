// ============================================================
// critters.js — Game mode companions
// Pick an animal, color and name; earn coins from lessons;
// spend them on accessories. Saved in this browser per user.
// Needs critter-art.js (pixel data) loaded first.
// ============================================================
window.Critter = (function () {
  "use strict";
  const ART = window.CRITTER_ART;
  const S = 32;

  // ---------------------------------------------------------- items
  // slot: head | face | neck | bg.  price: coins.  earn: unit that unlocks it for free
  const ITEMS = [
    { id: "beanie",      slot: "head", name: "Beanie",          price: 20 },
    { id: "cap",         slot: "head", name: "Ball cap",        price: 30 },
    { id: "party",       slot: "head", name: "Party hat",       price: 60 },
    { id: "flowers",     slot: "head", name: "Flower crown",    price: 80 },
    { id: "crown",       slot: "head", name: "Crown",           price: 120 },
    { id: "glasses",     slot: "face", name: "Round glasses",   price: 30 },
    { id: "shades",      slot: "face", name: "Sunglasses",      price: 50 },
    { id: "scarf",       slot: "neck", name: "Scarf",           price: 40 },
    { id: "bowtie",      slot: "neck", name: "Bow tie",         price: 40 },
    { id: "bandana",     slot: "neck", name: "Bandana",         price: 50 },
    { id: "bg_meadow",   slot: "bg",   name: "Meadow",          price: 40 },
    { id: "bg_beach",    slot: "bg",   name: "Beach",           price: 60 },
    { id: "bg_night",    slot: "bg",   name: "Night sky",       price: 80 },
    { id: "bg_sunset",   slot: "bg",   name: "Sunset hills",    price: 80 },
    // earned by mastering a unit (any drug)
    { id: "mortarboard", slot: "head", name: "Scholar cap",     earn: "Facts" },
    { id: "pillband",    slot: "neck", name: "Pill-print bandana", earn: "Dosage" },
    { id: "stetho",      slot: "neck", name: "Stethoscope",     earn: "Procedures" },
    { id: "goggles",     slot: "face", name: "Lab goggles",     earn: "Rationales" },
  ];
  const ITEM = Object.fromEntries(ITEMS.map((i) => [i.id, i]));
  const SLOTS = [["head", "Hats"], ["face", "Eyewear"], ["neck", "Neckwear"], ["bg", "Backgrounds"]];

  const REWARDS = { starter: 30, lesson: 10, perfect: 5, unit: 25, streak: { 3: 25, 7: 50, 30: 100 } };

  // ---------------------------------------------------------- storage
  const KEY = "grove:critter";
  function user() {
    let u = null;
    try { u = typeof getUsername === "function" ? getUsername() : null; } catch (e) {}
    return u || "anon";
  }
  function loadAll() { try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { return {}; } }
  function load() { return loadAll()[user()] || null; }
  function save(st) {
    const all = loadAll();
    all[user()] = st;
    try { localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) {}
  }
  function has() { const st = load(); return !!(st && st.animal); }

  // ---------------------------------------------------------- pixel drawing
  function bodyPixels(animalKey) {
    const a = ART.animals[animalKey];
    const px = {};
    a.rows.forEach((row, y) => {
      for (let x = 0; x < S; x++) {
        const ch = row[x];
        if (ch !== ".") px[x + "," + y] = ART.parts["abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".indexOf(ch)];
      }
    });
    return px;
  }

  // Accessories are drawn from each animal's anchor points so they fit every body
  const ACC_COLORS = {
    beanie: "#e04848", band: "#b83232", pom: "#ffffff",
    cap: "#3b6fd8", capdark: "#2a53a8",
    gold: "#f5b400", golddark: "#c98f00", jewel: "#e0457d",
    leaf: "#4fa64f", pink: "#f58cb3", yellow: "#ffd34d", white: "#ffffff",
    party1: "#8b5cf6", party2: "#fbbf24",
    lens: "#1f3529", glint: "#cfe3ff",
    scarf: "#2bb3a3", stripe: "#1c8378",
    bow: "#e04848", bowdark: "#a62f2f",
    bandana: "#f59e0b", bandanadark: "#c27803",
    teal: "#0f9f95", pillred: "#ef4444",
    board: "#1f3529", tassel: "#f5b400",
    steth: "#374151", silver: "#e5e7eb",
    goggle: "#a7d8f5", strap: "#5a6660",
  };
  function shapeFor(id, a) {
    const p = {};
    const put = (x, y, c) => { if (x >= 0 && x < S && y >= 0 && y < S) p[x + "," + y] = c; };
    const [hx, hy] = a.hat, [ex, ey] = a.eye, [nx, ny] = a.neck;
    switch (id) {
      case "beanie":
        for (let x = hx - 4; x <= hx + 4; x++) for (let y = hy - 3; y <= hy; y++)
          if (((x + 0.5 - (hx + 0.5)) / 4.7) ** 2 + ((y + 0.5 - (hy + 1)) / 3.8) ** 2 <= 1) put(x, y, "beanie");
        for (let x = hx - 4; x <= hx + 4; x++) put(x, hy + 1, "band");
        put(hx, hy - 4, "pom"); put(hx + 1, hy - 4, "pom");
        break;
      case "cap":
        for (let x = hx - 3; x <= hx + 3; x++) for (let y = hy - 2; y <= hy; y++)
          if (((x + 0.5 - (hx + 0.5)) / 3.8) ** 2 + ((y + 0.5 - (hy + 1)) / 3) ** 2 <= 1) put(x, y, "cap");
        for (let x = hx - 3; x <= hx + 6; x++) put(x, hy + 1, x > hx + 3 ? "capdark" : "cap");
        put(hx, hy - 3, "capdark");
        break;
      case "crown":
        for (let x = hx - 3; x <= hx + 3; x++) { put(x, hy, "gold"); put(x, hy + 1, "golddark"); }
        [hx - 3, hx, hx + 3].forEach((x) => put(x, hy - 1, "gold"));
        put(hx, hy + 1, "jewel");
        break;
      case "flowers":
        for (let x = hx - 4; x <= hx + 4; x++) put(x, hy + 1, "leaf");
        [[hx - 3, "pink"], [hx, "yellow"], [hx + 3, "white"]].forEach(([x, c]) => {
          put(x, hy - 1, c); put(x - 1, hy, c); put(x + 1, hy, c); put(x, hy + 1, c); put(x, hy, "yellow");
        });
        break;
      case "party":
        for (let i = 0; i < 6; i++) {
          const y = hy + 1 - i, half = Math.floor((5 - i) / 2);
          for (let x = hx - half; x <= hx + half; x++) put(x, y, i % 2 ? "party2" : "party1");
        }
        put(hx, hy - 5, "white"); put(hx + 1, hy - 5, "white");
        break;
      case "mortarboard":
        for (let x = hx - 4; x <= hx + 4; x++) put(x, hy - 1, "board");
        for (let x = hx - 2; x <= hx + 2; x++) { put(x, hy, "board"); put(x, hy + 1, "board"); }
        put(hx + 4, hy, "tassel"); put(hx + 4, hy + 1, "tassel"); put(hx + 4, hy + 2, "tassel");
        break;
      case "glasses":
        [[-1, -1], [0, -2], [1, -2], [2, -1], [2, 0], [2, 1], [1, 2], [0, 2], [-1, 1]].forEach(([dx, dy]) => put(ex + dx, ey + dy, "lens"));
        for (let k = 1; k <= 3; k++) put(ex - 1 - k, ey - 1, "lens");
        break;
      case "shades":
        for (let dx = -1; dx <= 2; dx++) for (let dy = -1; dy <= 1; dy++) put(ex + dx, ey + dy, "lens");
        put(ex + 1, ey - 1, "glint");
        for (let k = 1; k <= 3; k++) put(ex - 1 - k, ey - 1, "lens");
        break;
      case "goggles":
        for (let dx = -2; dx <= 2; dx++) for (let dy = -2; dy <= 2; dy++) {
          const edge = Math.abs(dx) === 2 || Math.abs(dy) === 2;
          put(ex + dx, ey + dy, edge ? "strap" : "goggle");
        }
        put(ex, ey, "lens");
        for (let k = 3; k <= 5; k++) put(ex - k, ey - 1, "strap");
        break;
      case "scarf":
        for (let x = nx - 2; x <= nx + 2; x++) for (let y = ny - 1; y <= ny + 1; y++) put(x, y, x % 2 ? "stripe" : "scarf");
        for (let y = ny + 2; y <= ny + 4; y++) { put(nx - 2, y, "scarf"); put(nx - 1, y, y % 2 ? "stripe" : "scarf"); }
        break;
      case "bowtie":
        put(nx - 2, ny - 1, "bow"); put(nx - 2, ny, "bow"); put(nx - 2, ny + 1, "bow"); put(nx - 1, ny, "bow");
        put(nx, ny, "bowdark");
        put(nx + 1, ny, "bow"); put(nx + 2, ny - 1, "bow"); put(nx + 2, ny, "bow"); put(nx + 2, ny + 1, "bow");
        break;
      case "bandana":
      case "pillband": {
        const main = id === "bandana" ? "bandana" : "teal";
        const rows = [[-3, 3], [-2, 2], [-1, 1], [0, 0]];
        rows.forEach(([a0, a1], i) => { for (let x = nx + a0; x <= nx + a1; x++) put(x, ny - 1 + i, main); });
        if (id === "bandana") { put(nx - 1, ny, "bandanadark"); put(nx + 1, ny, "bandanadark"); }
        else { put(nx - 2, ny - 1, "white"); put(nx - 1, ny - 1, "pillred"); put(nx + 1, ny - 1, "white"); put(nx + 2, ny - 1, "pillred"); put(nx, ny, "white"); }
        break;
      }
      case "stetho":   // draped around the neck, chest piece hanging in front
        for (let x = nx - 2; x <= nx + 2; x++) put(x, ny - 1, "steth");
        for (let y = ny; y <= ny + 2; y++) put(nx - 2, y, "steth");
        for (let y = ny; y <= ny + 3; y++) put(nx + 2, y, "steth");
        for (let x = nx + 1; x <= nx + 3; x++) for (let y = ny + 4; y <= ny + 5; y++) put(x, y, "silver");
        break;
    }
    return p;
  }
  const NO_OUTLINE = new Set(["glasses", "shades"]);

  function outlined(p) {
    const out = Object.assign({}, p);
    Object.keys(p).forEach((k) => {
      const [x, y] = k.split(",").map(Number);
      [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([dx, dy]) => {
        const n = (x + dx) + "," + (y + dy);
        if (!(n in p) && x + dx >= 0 && x + dx < S && y + dy >= 0 && y + dy < S) out[n] = "outline";
      });
    });
    return out;
  }

  // Pixel backgrounds (feet sit on row 24, so the ground starts at row 25)
  function bgPixels(id) {
    const grid = [];
    const fill = (y0, y1, c) => { for (let y = y0; y <= y1; y++) grid[y] = Array(S).fill(c); };
    const dot = (x, y, c) => { if (grid[y]) grid[y][x] = c; };
    if (id === "bg_meadow") {
      fill(0, 24, "#bfe3f7"); fill(25, 31, "#7cc36a"); fill(27, 31, "#64ad55");
      [[3, 4], [4, 4], [5, 4], [4, 3], [24, 7], [25, 7], [26, 7], [27, 7], [25, 6], [26, 6]].forEach(([x, y]) => dot(x, y, "#ffffff"));
      [[4, 27, "#f58cb3"], [12, 29, "#ffd34d"], [21, 28, "#ffffff"], [28, 30, "#f58cb3"]].forEach(([x, y, c]) => dot(x, y, c));
    } else if (id === "bg_beach") {
      fill(0, 18, "#a6dcf7"); fill(19, 22, "#4aa8d8"); fill(23, 24, "#7cc4e8"); fill(25, 31, "#f3d79b"); fill(29, 31, "#e8c57e");
      for (let x = 24; x <= 27; x++) for (let y = 3; y <= 6; y++) if (!((x === 24 || x === 27) && (y === 3 || y === 6))) dot(x, y, "#ffd34d");
      [[6, 27], [17, 30]].forEach(([x, y]) => dot(x, y, "#ffffff"));
    } else if (id === "bg_night") {
      fill(0, 24, "#1e2a4a"); fill(14, 24, "#25335a"); fill(25, 31, "#2f4a3a"); fill(28, 31, "#263d30");
      [[3, 3], [9, 6], [15, 2], [21, 8], [28, 4], [6, 12], [26, 13], [13, 10]].forEach(([x, y]) => dot(x, y, "#ffffff"));
      [[24, 3], [25, 3], [23, 4], [24, 4], [23, 5], [24, 5], [24, 6], [25, 6]].forEach(([x, y]) => dot(x, y, "#fde68a"));
    } else if (id === "bg_sunset") {
      fill(0, 7, "#f9a8b8"); fill(8, 14, "#fbbf8a"); fill(15, 24, "#fdd8a1"); fill(25, 31, "#8a6bb5"); fill(28, 31, "#6f539a");
      for (let x = 0; x < S; x++) { const h = Math.round(3 * Math.sin(x / 5) + 2); for (let y = 24 - h; y <= 24; y++) dot(x, y, "#a98bd0"); }
      for (let x = 12; x <= 19; x++) for (let y = 13; y <= 17; y++) if ((x - 15.5) ** 2 + (y - 17) ** 2 <= 16) dot(x, y, "#ffe08a");
    } else return null;
    return grid;
  }

  // Merge runs of equal color into wide rects → small, crisp SVG
  function toSvg(layers, opts = {}) {
    const color = (x, y) => {
      for (let i = layers.length - 1; i >= 0; i--) {
        const c = layers[i](x, y);
        if (c) return c;
      }
      return null;
    };
    let rects = "";
    for (let y = 0; y < S; y++) {
      let x = 0;
      while (x < S) {
        const c = color(x, y);
        if (!c) { x++; continue; }
        let w = 1;
        while (x + w < S && color(x + w, y) === c) w++;
        rects += `<rect x="${x}" y="${y}" width="${w}" height="1" fill="${c}"/>`;
        x += w;
      }
    }
    const label = opts.label ? ` role="img" aria-label="${opts.label}"` : ' aria-hidden="true"';
    return `<svg class="crit-svg" viewBox="0 0 ${S} ${S}" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"${label}>${rects}</svg>`;
  }

  // st: { animal, color, worn: {head, face, neck, bg} }
  function sprite(st, opts = {}) {
    st = st || load();
    if (!st || !st.animal || !ART.animals[st.animal]) return "";
    const a = ART.animals[st.animal];
    const variant = (a.colors[st.color] || a.colors[0]).over;
    const pal = Object.assign({}, a.palette, variant);
    const outlineCol = pal.outline;
    const worn = Object.assign({}, st.worn || {}, opts.tryOn || {});
    const layers = [];
    if (opts.background !== false && worn.bg) {
      const g = bgPixels(worn.bg);
      if (g) layers.push((x, y) => (g[y] && g[y][x]) || null);
    }
    const body = bodyPixels(st.animal);
    layers.push((x, y) => { const p = body[x + "," + y]; return p ? (pal[p] || outlineCol) : null; });
    ["neck", "face", "head"].forEach((slot) => {
      const id = worn[slot];
      if (!id || !ITEM[id]) return;
      let shape = shapeFor(id, a.anchors);
      if (!NO_OUTLINE.has(id)) shape = outlined(shape);
      layers.push((x, y) => {
        const c = shape[x + "," + y];
        return c ? (c === "outline" ? outlineCol : ACC_COLORS[c]) : null;
      });
    });
    return toSvg(layers, { label: opts.label || `${st.name || a.name} the ${a.name.toLowerCase()}` });
  }

  // ---------------------------------------------------------- coins & rewards
  function addCoins(st, n) { st.coins = Math.max(0, (st.coins || 0) + n); }

  // Called at the end of a Game-mode lesson. Returns what was earned.
  function rewardLesson(r) {
    const st = load();
    if (!st || !st.animal) return null;
    const lines = [];
    let total = 0;
    if (!r.ranOut) { total += REWARDS.lesson; lines.push(["Lesson complete", REWARDS.lesson]); }
    if (!r.ranOut && r.accuracy === 100) { total += REWARDS.perfect; lines.push(["Perfect lesson", REWARDS.perfect]); }
    st.claimed = st.claimed || {};
    Object.entries(REWARDS.streak).forEach(([days, coins]) => {
      if ((r.streak || 0) >= Number(days) && !st.claimed["streak" + days]) {
        st.claimed["streak" + days] = true;
        total += coins;
        lines.push([`${days}-day streak`, coins]);
      }
    });
    addCoins(st, total);
    save(st);
    return { total, lines, coins: st.coins };
  }

  // Unit mastery unlocks themed items + bonus coins (checked when the path loads)
  function syncProgress(drug, data, opts = {}) {
    const st = load();
    if (!st || !st.animal || !data || !data.units) return [];
    st.owned = st.owned || [];
    st.claimed = st.claimed || {};
    const unlocked = [];
    data.units.forEach((u) => {
      if ((u.min_crown || 0) < 5) return;
      const key = "unit:" + drug + ":" + u.category;
      if (!st.claimed[key]) { st.claimed[key] = true; addCoins(st, REWARDS.unit); }
      const item = ITEMS.find((i) => i.earn === u.category);
      if (item && !st.owned.includes(item.id)) { st.owned.push(item.id); unlocked.push(item); }
    });
    save(st);
    updateCoinBadges();
    if (unlocked.length && !opts.silent) toast(`${st.name} unlocked the ${unlocked.map((i) => i.name).join(" and ")}!`);
    return unlocked;
  }

  // ---------------------------------------------------------- UI helpers
  const coinIcon = '<svg class="coin-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#f5b400"/><circle cx="12" cy="12" r="7.2" fill="#ffd34d"/><path d="M12 7.5v9M9.6 9.6h3.6a1.8 1.8 0 0 1 0 3.6h-2.4a1.8 1.8 0 0 0 0 3.6h3.6" stroke="#c98f00" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>';

  function updateCoinBadges() {
    const st = load();
    document.querySelectorAll("[data-coins]").forEach((el) => { el.textContent = st && st.animal ? (st.coins || 0) : 0; });
    const stat = document.getElementById("coinStat");
    if (stat) stat.hidden = !(st && st.animal);
  }

  function toast(msg) {
    let t = document.getElementById("critToast");
    if (!t) {
      t = document.createElement("div");
      t.id = "critToast";
      t.className = "crit-toast";
      t.setAttribute("role", "status");
      document.body.appendChild(t);
    }
    t.innerHTML = `${coinIcon}<span>${msg}</span>`;
    t.classList.remove("is-on");
    void t.offsetWidth;
    t.classList.add("is-on");
    clearTimeout(t._h);
    t._h = setTimeout(() => t.classList.remove("is-on"), 3200);
  }

  function esc(s) { return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  // ---------------------------------------------------------- companion card (game.html)
  function renderCard() {
    const el = document.getElementById("critterCard");
    if (!el) return;
    const st = load();
    updateCoinBadges();
    if (!st || !st.animal) {
      const keys = Object.keys(ART.animals);
      el.innerHTML = `
        <span class="bz-kicker crit-kicker">Your companion</span>
        <h3>Pick a study buddy</h3>
        <p class="crit-text">Choose an animal to cheer you on. Earn coins in lessons and dress it up.</p>
        <div class="crit-lineup">${keys.map((k) => `<span class="crit-mini">${sprite({ animal: k, color: 0 }, { background: false })}</span>`).join("")}</div>
        <button type="button" class="crit-cta" onclick="Critter.openCreate()">Choose your companion</button>`;
      return;
    }
    const a = ART.animals[st.animal];
    el.innerHTML = `
      <div class="crit-head">
        <div><span class="bz-kicker crit-kicker">Your companion</span><h3>${esc(st.name)}</h3><p class="crit-sub">${a.name} · ${a.trait}</p></div>
        <span class="crit-coins" title="Coins">${coinIcon}<span data-coins>${st.coins || 0}</span></span>
      </div>
      <div class="crit-stage${st.worn && st.worn.bg ? " has-bg" : ""}"><span class="crit-idle">${sprite(st)}</span></div>
      <div class="crit-actions">
        <button type="button" class="crit-cta" onclick="Critter.openShop('shop')">Shop</button>
        <button type="button" class="crit-cta is-ghost" onclick="Critter.openShop('wardrobe')">Wardrobe</button>
      </div>
      <p class="crit-earn">Earn ${REWARDS.lesson} coins per lesson, +${REWARDS.perfect} for a perfect one, plus streak and unit bonuses.</p>`;
  }

  // Stand the companion next to the node you should do next
  function placeOnPath(pathMap) {
    const st = load();
    if (!st || !st.animal || !pathMap) return;
    const node = pathMap.querySelector(".path-node.current") || pathMap.querySelector(".path-node.next");
    if (!node) return;
    const slot = node.closest(".node-slot");
    if (!slot || slot.querySelector(".path-critter")) return;
    const x = parseFloat(getComputedStyle(slot).getPropertyValue("--x")) || 0;
    const span = document.createElement("span");
    span.className = "path-critter crit-idle" + (x > 0 ? " on-left" : "");
    span.innerHTML = sprite(st, { background: false });
    slot.appendChild(span);
  }

  // ---------------------------------------------------------- dialogs
  let dlg = null;
  let draft = null;     // creation draft
  let tab = "shop";
  let tryOn = {};

  function dialog() {
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.className = "crit-dialog";
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("close", () => { tryOn = {}; renderCard(); refreshPathCritter(); });
    document.body.appendChild(dlg);
    return dlg;
  }
  function refreshPathCritter() {
    const map = document.getElementById("pathMap");
    if (!map) return;
    map.querySelectorAll(".path-critter").forEach((n) => n.remove());
    placeOnPath(map);
  }

  function openCreate() {
    const st = load();
    draft = st && st.animal
      ? { animal: st.animal, color: st.color || 0, name: st.name || "", editing: true }
      : { animal: "tortoise", color: 0, name: "", editing: false };
    drawCreate();
    const d = dialog();
    if (!d.open) d.showModal();
  }

  function drawCreate() {
    const d = dialog();
    const a = ART.animals[draft.animal];
    const preview = sprite({ animal: draft.animal, color: draft.color }, { background: false });
    d.innerHTML = `
      <form method="dialog" class="crit-dlg-inner" onsubmit="return false">
        <header class="crit-dlg-head">
          <div><span class="bz-kicker crit-kicker">${draft.editing ? "Edit companion" : "New companion"}</span><h2>Choose your companion</h2></div>
          <button type="button" class="crit-x" aria-label="Close" onclick="this.closest('dialog').close()">×</button>
        </header>
        <div class="crit-create">
          <div class="crit-preview crit-idle">${preview}</div>
          <div class="crit-create-side">
            <div class="crit-animals" role="radiogroup" aria-label="Animal">
              ${Object.entries(ART.animals).map(([k, an]) => `
                <button type="button" role="radio" aria-checked="${k === draft.animal}" class="crit-animal${k === draft.animal ? " is-on" : ""}" onclick="Critter._pickAnimal('${k}')">
                  <span class="crit-mini">${sprite({ animal: k, color: k === draft.animal ? draft.color : 0 }, { background: false })}</span>
                  <strong>${an.name}</strong><small>${an.trait}</small>
                </button>`).join("")}
            </div>
            <span class="crit-label">Color</span>
            <div class="crit-colors" role="radiogroup" aria-label="Color">
              ${a.colors.map((c, i) => `
                <button type="button" role="radio" aria-checked="${i === draft.color}" class="crit-color${i === draft.color ? " is-on" : ""}" onclick="Critter._pickColor(${i})" title="${c.name}">
                  <span class="crit-mini">${sprite({ animal: draft.animal, color: i }, { background: false })}</span><small>${c.name}</small>
                </button>`).join("")}
            </div>
            <label class="crit-label" for="critName">Name</label>
            <input id="critName" class="crit-name" maxlength="16" autocomplete="off" placeholder="${a.suggest}" value="${esc(draft.name)}" oninput="Critter._setName(this.value)">
          </div>
        </div>
        <footer class="crit-dlg-foot">
          ${draft.editing ? "" : `<span class="crit-gift">${coinIcon} Starter gift: ${REWARDS.starter} coins</span>`}
          <button type="button" class="crit-cta" onclick="Critter._confirmCreate()">${draft.editing ? "Save changes" : `Meet ${esc(draft.name || a.suggest)}`}</button>
        </footer>
      </form>`;
  }

  function confirmCreate() {
    const a = ART.animals[draft.animal];
    const name = (draft.name || "").trim() || a.suggest;
    let st = load();
    if (st && st.animal) {
      st.animal = draft.animal; st.color = draft.color; st.name = name;
    } else {
      st = { animal: draft.animal, color: draft.color, name, coins: REWARDS.starter, owned: [], worn: {}, claimed: {}, created: Date.now() };
    }
    save(st);
    const wasNew = !draft.editing;
    // pick up any units already mastered (bonus coins + themed items)
    const lp = typeof lastPath !== "undefined" ? lastPath : null;   // set by ui.js renderPath
    const unlocked = lp && lp.data ? syncProgress(lp.drug, lp.data, { silent: true }) : [];
    dialog().close();
    if (wasNew) {
      const extra = unlocked.length ? ` Your mastered units unlocked the ${unlocked.map((i) => i.name).join(" and ")}.` : "";
      toast(`Meet ${name}! Here are your starter coins.${extra}`);
    }
  }

  function openShop(which) {
    if (!has()) return openCreate();
    tab = which || "shop";
    tryOn = {};
    drawShop();
    const d = dialog();
    if (!d.open) d.showModal();
  }

  function drawShop() {
    const d = dialog();
    const st = load();
    const a = ART.animals[st.animal];
    st.owned = st.owned || [];
    st.worn = st.worn || {};
    const card = (it) => {
      const owned = st.owned.includes(it.id);
      const wearing = st.worn[it.slot] === it.id;
      const mini = sprite(Object.assign({}, st, { worn: it.slot === "bg" ? { bg: it.id } : { [it.slot]: it.id } }), { background: it.slot === "bg" });
      let action;
      if (tab === "wardrobe") {
        if (owned) action = `<button type="button" class="crit-btn${wearing ? " is-on" : ""}" onclick="Critter._toggleWear('${it.id}')">${wearing ? "Take off" : "Wear"}</button>`;
        else action = `<span class="crit-lock">Master ${it.earn} to unlock</span>`;
      } else {
        const short = (st.coins || 0) < it.price;
        action = `<button type="button" class="crit-btn is-buy" ${short ? "disabled" : ""} onclick="Critter._buy('${it.id}')">${coinIcon}${it.price}</button>`;
        if (short) action += `<span class="crit-need">Need ${it.price - (st.coins || 0)} more</span>`;
      }
      return `
        <div class="crit-item${wearing ? " is-wearing" : ""}${!owned && tab === "wardrobe" ? " is-locked" : ""}"
             ${tab === "shop" ? `onmouseenter="Critter._try('${it.slot}','${it.id}')" onfocusin="Critter._try('${it.slot}','${it.id}')"` : ""}>
          <span class="crit-item-art${it.slot === "bg" ? " is-bg" : ""}">${mini}</span>
          <strong>${it.name}</strong>
          ${it.earn ? `<small class="crit-earned">${owned ? "Earned" : "Unit reward"} · ${it.earn}</small>` : ""}
          ${action}
        </div>`;
    };
    let body = "";
    SLOTS.forEach(([slot, label]) => {
      const list = ITEMS.filter((it) => it.slot === slot && (tab === "wardrobe" ? (st.owned.includes(it.id) || it.earn) : (!it.earn && !st.owned.includes(it.id))));
      if (!list.length) return;
      body += `<h3 class="crit-sec">${label}</h3><div class="crit-grid">${list.map(card).join("")}</div>`;
    });
    if (!body) body = tab === "shop"
      ? `<p class="crit-empty">You own everything in the shop. Nice!</p>`
      : `<p class="crit-empty">Nothing here yet. Buy something in the shop.</p>`;

    d.innerHTML = `
      <div class="crit-dlg-inner is-wide">
        <header class="crit-dlg-head">
          <div><span class="bz-kicker crit-kicker">${esc(st.name)} the ${a.name.toLowerCase()}</span><h2>${tab === "shop" ? "Shop" : "Wardrobe"}</h2></div>
          <span class="crit-coins">${coinIcon}<span data-coins>${st.coins || 0}</span></span>
          <button type="button" class="crit-x" aria-label="Close" onclick="this.closest('dialog').close()">×</button>
        </header>
        <div class="crit-shop">
          <aside class="crit-shop-side">
            <div class="crit-stage${(tryOn.bg || st.worn.bg) ? " has-bg" : ""}"><span class="crit-idle">${sprite(st, { tryOn })}</span></div>
            ${Object.keys(tryOn).length ? `<p class="crit-trying">Trying on: ${ITEM[Object.values(tryOn)[0]].name}</p>` : ""}
            <div class="crit-tabs" role="tablist">
              <button type="button" role="tab" aria-selected="${tab === "shop"}" class="${tab === "shop" ? "is-on" : ""}" onclick="Critter.openShop('shop')">Shop</button>
              <button type="button" role="tab" aria-selected="${tab === "wardrobe"}" class="${tab === "wardrobe" ? "is-on" : ""}" onclick="Critter.openShop('wardrobe')">Wardrobe</button>
            </div>
            <button type="button" class="crit-edit" onclick="Critter.openCreate()">Change animal, color or name</button>
          </aside>
          <div class="crit-shop-main">${body}</div>
        </div>
      </div>`;
    updateCoinBadges();
  }

  function tryItem(slot, id) {
    if (tryOn[slot] === id) return;
    tryOn = { [slot]: id };
    const st = load();
    const stage = dlg && dlg.querySelector(".crit-shop-side .crit-stage");
    if (stage) {
      stage.classList.toggle("has-bg", !!(tryOn.bg || (st.worn || {}).bg));
      stage.innerHTML = `<span class="crit-idle">${sprite(st, { tryOn })}</span>`;
    }
    const note = dlg && dlg.querySelector(".crit-trying");
    const html = `Trying on: ${ITEM[id].name}`;
    if (note) note.textContent = html;
    else if (stage) stage.insertAdjacentHTML("afterend", `<p class="crit-trying">${html}</p>`);
  }

  function buy(id) {
    const st = load();
    const it = ITEM[id];
    if (!st || !it || it.earn || (st.owned || []).includes(id) || (st.coins || 0) < it.price) return;
    st.coins -= it.price;
    st.owned = st.owned || [];
    st.owned.push(id);
    st.worn = st.worn || {};
    st.worn[it.slot] = id;               // wear it right away
    save(st);
    tryOn = {};
    drawShop();
    toast(`${st.name} is wearing the ${it.name}!`);
  }

  function toggleWear(id) {
    const st = load();
    const it = ITEM[id];
    if (!st || !it || !(st.owned || []).includes(id)) return;
    st.worn = st.worn || {};
    st.worn[it.slot] = st.worn[it.slot] === id ? null : id;
    save(st);
    drawShop();
  }

  return {
    has, sprite, renderCard, placeOnPath, rewardLesson, syncProgress, openCreate, openShop, toast, coinIcon,
    _pickAnimal: (k) => { draft.animal = k; draft.color = 0; drawCreate(); },
    _pickColor: (i) => { draft.color = i; drawCreate(); },
    _setName: (v) => {
      draft.name = v;
      const btn = dlg && dlg.querySelector(".crit-dlg-foot .crit-cta");
      if (btn && !draft.editing) btn.textContent = `Meet ${v.trim() || ART.animals[draft.animal].suggest}`;
    },
    _confirmCreate: confirmCreate, _buy: buy, _toggleWear: toggleWear, _try: tryItem,
    ITEMS, REWARDS,
  };
})();