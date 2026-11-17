// ============================================================
// bonsai.js — Focused mode's growing bonsai
// One tree per drug, saved in this browser (localStorage) per user.
// Every level you finish = one growth step, and you pick what grows.
// Load after script.js (uses getUsername, apiFetch, BASE_URL).
// ============================================================
window.Bonsai = (function () {
  "use strict";

  // ---------------------------------------------------------- data
  const SPECIES = {
    juniper: {
      name: "Juniper", note: "Evergreen needles, rugged trunk",
      bark: "#7a4a2e", barkHi: "#a8714c", leaf: ["#2f5a49", "#3f7560", "#5f977c"],
      padWord: "Needle pad", flowers: false,
    },
    maple: {
      name: "Japanese maple", note: "Soft leaves that can turn red",
      bark: "#6b5a4e", barkHi: "#948274", leaf: ["#4a8638", "#64a54c", "#8ec771"],
      padWord: "Leaf cluster", flowers: false, autumn: true,
    },
    cherry: {
      name: "Cherry blossom", note: "Pale pink blossoms when leafy",
      bark: "#5a3b33", barkHi: "#83584c", leaf: ["#42773f", "#5c9c58", "#86c07d"],
      padWord: "Leaf cluster", flowers: true, flowerWord: "Blossoms",
      bloom: ["#f9c3d1", "#fde6ec", "#e27c9b"],
    },
    azalea: {
      name: "Azalea", note: "Small glossy leaves, bright blooms",
      bark: "#6a4b3a", barkHi: "#94705a", leaf: ["#2c5a33", "#3d7845", "#5c9a5e"],
      padWord: "Leaf cluster", flowers: true, flowerWord: "Blooms",
      bloom: ["#e8508a", "#f58cb3", "#a8235a"],
    },
  };
  const POTS = {
    slate:   { name: "Slate",      c: ["#4f5768", "#3a4151", "#6f7889"] },
    clay:    { name: "Terracotta", c: ["#b8643c", "#91482a", "#d4835a"] },
    celadon: { name: "Celadon",    c: ["#7fa89a", "#5d8a7b", "#a7c9bc"] },
  };
  const AUTUMN = [["#a8391e", "#d8532b", "#f08a3c"], ["#b5561c", "#e6822f", "#f6b14c"]];
  const GROUND = ["moss", "roots", "stone"];

  // ---------------------------------------------------------- storage
  const STORE_KEY = "grove:bonsai";
  function userKey() {
    let u = null;
    try { u = typeof getUsername === "function" ? getUsername() : null; } catch (e) {}
    return u || "anon";
  }
  function loadAll() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}") || {}; } catch (e) { return {}; }
  }
  function saveAll(all) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(all)); } catch (e) {}
  }
  function allTrees() { return loadAll()[userKey()] || {}; }
  function getTree(drug) { return allTrees()[drug] || null; }
  function setTree(drug, tree) {
    const all = loadAll(), u = userKey();
    all[u] = all[u] || {};
    all[u][drug] = tree;
    saveAll(all);
  }

  // ---------------------------------------------------------- growth rules
  // Replays the list of choices into concrete parts of the tree.
  function buildModel(choices) {
    const m = { branches: [], apex: {}, jin: [], roots: [], moss: [], stones: [] };
    const pads = () => [m.apex, ...m.branches.filter((b) => b.pad).map((b) => b.pad)];
    choices.forEach((type, step) => {
      if (type === "branch") m.branches.push({ slot: m.branches.length, step });
      else if (type === "foliage") { const b = m.branches.find((b) => !b.pad); if (b) b.pad = { step }; }
      else if (type === "flowers") { const p = pads().find((p) => p.flower == null); if (p) p.flower = step; }
      else if (type === "autumn") { const p = pads().find((p) => p.autumn == null); if (p) p.autumn = step; }
      else if (type === "jin") m.jin.push({ slot: m.jin.length, step });
      else if (type === "roots") m.roots.push({ slot: m.roots.length, step });
      else if (type === "moss") m.moss.push({ slot: m.moss.length, step });
      else if (type === "stone") m.stones.push({ slot: m.stones.length, step });
    });
    m.pads = pads();
    return m;
  }

  // What can realistically grow next
  function validOptions(tree) {
    const sp = SPECIES[tree.species];
    const m = buildModel(tree.choices);
    const steps = tree.choices.length;
    const branches = m.branches.length;
    const leafy = m.branches.filter((b) => b.pad).length;
    const out = [];
    if (branches < 7) out.push("branch");
    if (leafy < branches) out.push("foliage");                       // leaves only on existing branches
    if (sp.flowers && leafy >= 3 && steps >= 9 && m.pads.some((p) => p.flower == null)) out.push("flowers");
    if (sp.autumn && leafy >= 2 && m.pads.some((p) => p.autumn == null)) out.push("autumn");
    if (tree.species === "juniper" && branches >= 2 && m.jin.length < 2) out.push("jin");
    if (m.moss.length < 4) out.push("moss");
    if (steps >= 2 && m.roots.length < 3) out.push("roots");
    if (m.stones.length < 2) out.push("stone");
    return out;
  }

  // Up to 3 choices: the 2 most useful tree options + 1 ground option
  function offered(tree) {
    const opts = validOptions(tree);
    const m = buildModel(tree.choices);
    const steps = tree.choices.length;
    const branches = m.branches.length;
    const leafy = m.branches.filter((b) => b.pad).length;
    const score = {
      foliage: 100,
      branch: branches < 2 ? 95 : 70 - branches * 7,
      flowers: 80 - m.pads.filter((p) => p.flower != null).length * 6,
      autumn: 58 - m.pads.filter((p) => p.autumn != null).length * 6,
      jin: 52,
    };
    if (leafy === branches) score.foliage = 0;
    const treeOpts = opts.filter((t) => !GROUND.includes(t)).sort((a, b) => (score[b] || 0) - (score[a] || 0));
    const groundOpts = opts.filter((t) => GROUND.includes(t));
    const out = treeOpts.slice(0, 2);
    if (groundOpts.length) out.push(groundOpts[steps % groundOpts.length]);
    for (const t of [...treeOpts, ...groundOpts]) {
      if (out.length >= 3) break;
      if (!out.includes(t)) out.push(t);
    }
    return out;
  }

  function optionInfo(type, sp) {
    return {
      branch: { label: "New branch", desc: "Extends the tree's shape" },
      foliage: { label: sp.padWord, desc: "A cloud of foliage on a bare branch" },
      flowers: { label: sp.flowerWord || "Flowers", desc: "Flowers on a leafy pad" },
      autumn: { label: "Autumn color", desc: "Turns a leaf cluster red and orange" },
      jin: { label: "Deadwood (jin)", desc: "Silvery weathered wood, classic on junipers" },
      moss: { label: "Moss", desc: "Soft green cover on the soil" },
      roots: { label: "Surface roots", desc: "Roots that spread at the base" },
      stone: { label: "Accent stone", desc: "A small stone in the pot" },
    }[type];
  }

  // ---------------------------------------------------------- drawing helpers
  const f = (v) => (Math.round(v * 10) / 10).toString();
  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function bez(P, u) {
    const v = 1 - u;
    return [0, 1].map((i) => v * v * v * P[0][i] + 3 * v * v * u * P[1][i] + 3 * v * u * u * P[2][i] + u * u * u * P[3][i]);
  }
  // A filled shape that follows a cubic curve and narrows from w0 to w1
  function taper(P, w0, w1, n = 18) {
    const left = [], right = [];
    for (let i = 0; i <= n; i++) {
      const u = i / n;
      const p = bez(P, u);
      const a = bez(P, Math.max(0, u - 0.01)), b = bez(P, Math.min(1, u + 0.01));
      const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
      const nx = -dy / len, ny = dx / len, w = (w0 + (w1 - w0) * u) / 2;
      left.push([p[0] + nx * w, p[1] + ny * w]);
      right.push([p[0] - nx * w, p[1] - ny * w]);
    }
    const pts = left.concat(right.reverse());
    return "M" + pts.map((p) => f(p[0]) + " " + f(p[1])).join(" L") + " Z";
  }
  const circle = (x, y, r, fill, extra = "") => `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" fill="${fill}"${extra}/>`;
  const ellipse = (x, y, rx, ry, fill, extra = "") => `<ellipse cx="${f(x)}" cy="${f(y)}" rx="${f(rx)}" ry="${f(ry)}" fill="${fill}"${extra}/>`;

  // Bonsai foliage pad: a flat-bottomed cloud
  function padSvg(cx, cy, rx, ry, col, rand) {
    const [dark, mid, light] = col;
    let s = ellipse(cx, cy + ry * 0.3, rx, ry * 0.6, dark);
    const n = 5;
    for (let k = 0; k < n; k++) {
      const a = k / (n - 1);
      const x = cx - rx * 0.7 + a * rx * 1.4 + (rand() - 0.5) * rx * 0.12;
      const y = cy - Math.sin(Math.PI * a) * ry * 0.42 + (rand() - 0.5) * ry * 0.14;
      const r = ry * (0.55 + 0.32 * Math.sin(Math.PI * a)) * (0.92 + rand() * 0.16);
      s += circle(x, y, r, mid);
    }
    for (let k = 0; k < 3; k++) {
      const a = 0.22 + k * 0.2;
      const x = cx - rx * 0.62 + a * rx * 1.24;
      const y = cy - Math.sin(Math.PI * a) * ry * 0.6 - ry * 0.08;
      s += circle(x, y, ry * (0.26 + rand() * 0.08), light);
    }
    return s;
  }

  function flowersSvg(cx, cy, rx, ry, sp, rand, n) {
    const big = sp === SPECIES.azalea;
    let s = "";
    for (let i = 0; i < n; i++) {
      const ux = rand() * 2 - 1;
      const x = cx + ux * rx * 0.78;
      const top = cy - Math.sqrt(Math.max(0, 1 - ux * ux)) * ry * 0.75;
      const y = top + rand() * ry * 0.7;
      const r = (big ? 2.1 : 1.55) + rand() * 0.6;
      for (let p = 0; p < 5; p++) {
        const a = (p * 72 + rand() * 20) * Math.PI / 180;
        s += circle(x + Math.cos(a) * r, y + Math.sin(a) * r, r * 0.85, p % 2 ? sp.bloom[1] : sp.bloom[0]);
      }
      s += circle(x, y, r * 0.55, sp.bloom[2]);
    }
    return s;
  }

  function potSvg(potKey) {
    const c = (POTS[potKey] || POTS.slate).c;
    return `
      ${ellipse(150, 243, 74, 4.5, "rgba(22,39,30,0.09)")}
      <path d="M78 206 L222 206 L211 236 L89 236 Z" fill="${c[0]}"/>
      <path d="M86 229 L214 229 L211 236 L89 236 Z" fill="${c[1]}" opacity="0.45"/>
      <rect x="95" y="235.5" width="15" height="5.5" rx="1.6" fill="${c[1]}"/>
      <rect x="190" y="235.5" width="15" height="5.5" rx="1.6" fill="${c[1]}"/>
      <rect x="70" y="198" width="160" height="9.5" rx="3" fill="${c[1]}"/>
      <rect x="72" y="199" width="156" height="3" rx="1.5" fill="${c[2]}" opacity="0.75"/>
      ${ellipse(150, 199.2, 74, 4.4, "#45322a")}
      ${ellipse(150, 198.4, 69, 2.6, "#5c4436")}`;
  }

  // ---------------------------------------------------------- the tree
  function treeSvg(tree, o = {}) {
    const sp = SPECIES[tree.species] || SPECIES.juniper;
    const total = o.total || 20, units = o.units || 0;
    const steps = tree.choices.length;
    const mature = steps >= total && total >= 5;
    const t = Math.min(steps / 20, 1);
    const seed = hash(tree.species + ":" + (tree.planted || 0));
    const R = (k) => rng(hash(seed + ":" + k));
    const flip = seed % 2 ? 1 : -1;
    const isNew = (step) => step === o.newStep;
    const wrap = (step, inner) => (isNew(step) ? `<g class="bz-new">${inner}</g>` : inner);

    const H = 52 + 92 * t, s = 0.62 + 0.38 * t;
    const bx = 150, by = 199;
    const P = [[bx, by], [bx - 20 * s * flip, by - H * 0.36], [bx + 26 * s * flip, by - H * 0.7], [bx + 4 * s * flip, by - H]];
    const w0 = 6 + units * 2.4 + steps * 0.32, w1 = 2.6 + t * 1.6;
    const trunkW = (u) => w0 + (w1 - w0) * u;
    const m = buildModel(tree.choices);

    let out = "";
    if (o.backdrop) out += circle(150, 130, 112, o.backdropColor || "#e6f1ee");
    out += potSvg(tree.pot);

    // surface roots
    const ROOTS = [[-1, 46, 3], [1, 42, 4], [-1, 25, 5]];
    m.roots.forEach((r) => {
      const [side0, reach, drop] = ROOTS[r.slot];
      const side = side0 * flip, s2 = 0.7 + 0.3 * t;
      const RP = [[bx + side * w0 * 0.2, by - 3], [bx + side * w0 * 0.8, by - 2.5], [bx + side * reach * s2 * 0.6, by - 1.5], [bx + side * reach * s2, by + drop * 0.3]];
      out += wrap(r.step, `<path d="${taper(RP, w0 * 0.75 + 2, 1.6)}" fill="${sp.bark}"/>` +
        `<path d="M${f(RP[0][0])} ${f(RP[0][1] - 1.5)} C${f(RP[1][0])} ${f(RP[1][1] - 1.5)} ${f(RP[2][0])} ${f(RP[2][1] - 1)} ${f(RP[3][0])} ${f(RP[3][1] - 0.5)}" stroke="${sp.barkHi}" stroke-width="1.1" fill="none" opacity="0.8"/>`);
    });

    // branches (drawn before the trunk so the trunk covers the joints)
    const BRANCH_U = [0.38, 0.48, 0.57, 0.65, 0.73, 0.8, 0.87];
    const branchGeo = m.branches.map((b) => {
      const u = BRANCH_U[b.slot];
      const side = (b.slot % 2 ? 1 : -1) * flip;
      const p = bez(P, u);
      const len = (62 - b.slot * 5.5) * s;
      const end = [p[0] + side * len, p[1] - len * 0.18 - 3];
      const BP = [p, [p[0] + side * len * 0.3, p[1] + 5], [p[0] + side * len * 0.65, end[1] + 4], end];
      return { b, side, end, len, BP, w: trunkW(u) * 0.5 };
    });
    branchGeo.forEach((g) => {
      let svg = `<path d="${taper(g.BP, g.w, 2)}" fill="${sp.bark}"/>`;
      if (!g.b.pad) svg += circle(g.end[0], g.end[1] - 1, 2.4, sp.leaf[2]);     // leaf bud on a bare branch
      out += wrap(g.b.step, svg);
    });

    // trunk
    out += `<path d="${taper(P, w0, w1)}" fill="${sp.bark}"/>`;
    const HL = P.map((p, i) => [p[0] - (trunkW(i / 3) * 0.22), p[1]]);
    out += `<path d="M${f(HL[0][0])} ${f(HL[0][1] - 4)} C${f(HL[1][0])} ${f(HL[1][1])} ${f(HL[2][0])} ${f(HL[2][1])} ${f(HL[3][0])} ${f(HL[3][1] + 4)}" stroke="${sp.barkHi}" stroke-width="${f(Math.max(1.2, w0 * 0.14))}" fill="none" stroke-linecap="round" opacity="0.7"/>`;

    // foliage pads (+ flowers)
    const padPalette = (pad, i) => (pad.autumn != null ? AUTUMN[i % 2] : sp.leaf);
    const drawPad = (pad, i, cx, cy, rx, ry, key) => {
      let svg = padSvg(cx, cy, rx, ry, padPalette(pad, i), R(key));
      let fl = "";
      if (sp.flowers && (pad.flower != null || mature)) fl = flowersSvg(cx, cy, rx, ry, sp, R(key + ":f"), mature ? 13 : 7);
      const padStep = pad.step != null ? pad.step : -99;
      let g = wrap(padStep, svg);
      if (pad.autumn != null && isNew(pad.autumn)) g = `<g class="bz-new bz-fade">${svg}</g>`;
      if (fl) g += pad.flower != null && isNew(pad.flower) ? `<g class="bz-new bz-fade">${fl}</g>` : fl;
      return g;
    };
    let padIndex = 1;
    branchGeo.forEach((g) => {
      if (!g.b.pad) return;
      const rx = 15 + g.len * 0.2, ry = rx * 0.48;
      out += drawPad(g.b.pad, padIndex++, g.end[0] + g.side * 2, g.end[1] - 5, rx, ry, "pad" + g.b.slot);
    });
    const arx = 13 + 17 * t;
    out += drawPad(m.apex, 0, P[3][0], P[3][1] - 4, arx, arx * 0.56, "apex");

    // deadwood (jin)
    m.jin.forEach((j) => {
      const u = j.slot === 0 ? 0.52 : 0.3;
      const p = bez(P, u);
      const side = (j.slot === 0 ? 1 : -1) * flip;
      const end = j.slot === 0 ? [p[0] + side * 15, p[1] - 26] : [p[0] + side * 17, p[1] - 9];
      const JP = [p, [p[0] + side * 3, p[1] - 6], [end[0] - side * 4, end[1] + 5], end];
      out += wrap(j.step, `<path d="${taper(JP, Math.max(2.4, trunkW(u) * 0.45), 0.6)}" fill="#ece6d9" stroke="#bcb3a3" stroke-width="0.8"/>`);
    });

    // moss
    const MOSS_X = [116, 186, 132, 170];
    m.moss.forEach((mo) => {
      const r = R("moss" + mo.slot), x = MOSS_X[mo.slot];
      let svg = "";
      for (let k = 0; k < 4; k++) {
        const dx = (k - 1.5) * 4.2 + (r() - 0.5) * 2;
        svg += ellipse(x + dx, by - 1, 3.6 + r() * 1.6, 2.6 + r() * 1.2, k % 2 ? "#6c9c44" : "#5b8a39");
      }
      svg += ellipse(x - 2, by - 3, 2.4, 1.2, "#a3cf6c");
      out += wrap(mo.step, svg);
    });

    // accent stones
    const STONES = [[98, by - 1.5, 8, 5.5], [204, by - 1, 6.5, 4.5]];
    m.stones.forEach((st) => {
      const [x, y, rx, ry] = STONES[st.slot];
      out += wrap(st.step, ellipse(x, y, rx, ry, "#8d949e") + ellipse(x - rx * 0.3, y - ry * 0.35, rx * 0.4, ry * 0.3, "#c4c9cf"));
    });

    // a fully grown cherry drops a few petals
    if (mature && tree.species === "cherry") {
      const r = R("petals");
      for (let i = 0; i < 9; i++) {
        const x = 92 + r() * 116, y = i < 5 ? by - 1.5 - r() * 2 : 95 + r() * 80;
        out += ellipse(x, y, 1.9, 1.1, SPECIES.cherry.bloom[i % 2], ` transform="rotate(${Math.round(r() * 80 - 40)} ${f(x)} ${f(y)})"`);
      }
    }

    return `<svg viewBox="0 0 300 250" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${sp.name} bonsai, ${steps} growth steps">${out}</svg>`;
  }

  function emptyPotSvg() {
    return `<svg viewBox="0 0 300 250" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">${potSvg("slate")}${ellipse(150, 196, 4, 2.5, "#86c07d")}</svg>`;
  }

  function iconSvg(type, tree) {
    const sp = SPECIES[(tree && tree.species) || "maple"] || SPECIES.maple;
    const L = sp.leaf;
    const svg = (inner) => `<svg viewBox="0 0 36 36" width="34" height="34" aria-hidden="true">${inner}</svg>`;
    const cloud = (c) => `${ellipse(18, 22, 13, 6.5, c[0])}${circle(10, 19.5, 6, c[1])}${circle(18, 15.5, 7.5, c[1])}${circle(26, 19.5, 6, c[1])}${circle(14.5, 13, 2.8, c[2])}${circle(21, 12.5, 2.4, c[2])}`;
    switch (type) {
      case "branch": return svg(`<path d="M5 27 C13 25 20 19 31 12" stroke="${sp.bark}" stroke-width="3.6" fill="none" stroke-linecap="round"/><path d="M18 20.5 C20 15 22 12.5 25 9.5" stroke="${sp.bark}" stroke-width="2.2" fill="none" stroke-linecap="round"/>${circle(31, 12, 2.6, L[2])}${circle(25, 9.5, 2.1, L[2])}`);
      case "foliage": return svg(cloud(L));
      case "autumn": return svg(cloud(AUTUMN[0]));
      case "flowers": {
        let s = "";
        for (let p = 0; p < 5; p++) { const a = (p * 72 - 90) * Math.PI / 180; s += circle(18 + Math.cos(a) * 6, 18 + Math.sin(a) * 6, 5.4, p % 2 ? sp.bloom[1] : sp.bloom[0]); }
        return svg(s + circle(18, 18, 3.4, sp.bloom[2]));
      }
      case "moss": return svg(`${ellipse(9, 25, 6, 4.5, "#5b8a39")}${ellipse(18, 23, 7, 6, "#6c9c44")}${ellipse(27, 25, 6, 4.5, "#5b8a39")}${ellipse(16, 20, 3, 1.6, "#a3cf6c")}<rect x="2" y="26" width="32" height="5" rx="2.5" fill="#755642"/>`);
      case "roots": return svg(`<rect x="2" y="13" width="32" height="5" rx="2.5" fill="#755642"/><path d="M18 4 L18 16 C14 18 9 21 4 27 M18 16 C22 18 27 21 32 27 M18 17 C17 21 15 25 13 30" stroke="${sp.bark}" stroke-width="3" fill="none" stroke-linecap="round"/>`);
      case "stone": return svg(`<rect x="2" y="25" width="32" height="5" rx="2.5" fill="#755642"/>${ellipse(18, 22, 11, 7.5, "#8d949e")}${ellipse(14, 19, 4.5, 2.4, "#c4c9cf")}`);
      case "jin": return svg(`<path d="M10 31 C11 24 13 18 15 13 C17 9 21 6 26 4" stroke="#bcb3a3" stroke-width="5.4" fill="none" stroke-linecap="round"/><path d="M10 31 C11 24 13 18 15 13 C17 9 21 6 26 4" stroke="#ece6d9" stroke-width="3.6" fill="none" stroke-linecap="round"/>`);
    }
    return "";
  }

  // ---------------------------------------------------------- UI
  let ctx = null;                 // { drug, levels, units, total, mount, mode: "panel" | "lesson" }
  let draft = { species: "juniper", pot: "slate" };
  let newStep = -1;

  function levelsFrom(data) {
    const units = (data && data.units) || [];
    return {
      levels: units.reduce((n, u) => n + (u.min_crown || 0), 0),
      units: units.filter((u) => (u.min_crown || 0) >= 5).length,
      total: Math.max(units.length * 5, 5),
    };
  }

  function drugName(drug) {
    if (ctx && ctx.drug === drug && ctx.topicName) return escapeHtml(ctx.topicName);
    const sel = document.getElementById("drugSelect");
    const opt = sel && [...sel.options].find((o) => o.value === drug);
    return opt ? opt.text : drug.charAt(0).toUpperCase() + drug.slice(1);
  }

  function syncTree() {
    const tree = getTree(ctx.drug);
    if (tree) {
      tree.levels = ctx.levels; tree.units = ctx.units; tree.total = ctx.total;
      setTree(ctx.drug, tree);
    }
  }

  function draw() {
    if (!ctx || !ctx.mount) return;
    const tree = getTree(ctx.drug);
    ctx.mount.innerHTML = tree ? growHtml(tree) : plantHtml();
    newStep = -1;
  }

  function demoTree(species, pot) {
    const tree = { species, pot, choices: [], planted: 7 };
    for (let i = 0; i < 16; i++) {
      const o = offered(tree);
      if (!o.length) break;
      tree.choices.push(o[i % o.length]);
    }
    return tree;
  }

  function plantHtml() {
    const sp = SPECIES[draft.species];
    return `
      <div class="bz-head"><div><span class="bz-kicker">Grow a bonsai</span><h3>Pick a tree for ${drugName(ctx.drug)}</h3></div></div>
      <p class="bz-text">Each level you finish lets it grow, and you choose how.</p>
      <div class="bz-stage">
        ${treeSvg(demoTree(draft.species, draft.pot), { total: 20, units: 3, backdrop: true })}
        <span class="bz-demo-tag">Preview</span>
      </div>
      <div class="bz-species" role="radiogroup" aria-label="Bonsai species">
        ${Object.entries(SPECIES).map(([k, s]) => `
          <button type="button" role="radio" aria-checked="${k === draft.species}" class="bz-sp${k === draft.species ? " is-on" : ""}" onclick="Bonsai.pickSpecies('${k}')">
            <strong>${s.name}</strong><small>${s.note}</small>
          </button>`).join("")}
      </div>
      <div class="bz-pots"><span>Pot</span>
        ${Object.entries(POTS).map(([k, p]) => `<button type="button" class="bz-pot${k === draft.pot ? " is-on" : ""}" style="--pot:${p.c[0]}" onclick="Bonsai.pickPot('${k}')" aria-label="${p.name} pot" aria-pressed="${k === draft.pot}" title="${p.name}"></button>`).join("")}
      </div>
      <button type="button" class="bz-plant" onclick="Bonsai.plant()">Plant your ${sp.name.toLowerCase()}</button>
      ${shelfHtml()}`;
  }

  function chooserHtml(tree, pending) {
    const sp = SPECIES[tree.species];
    return `
      <div class="bz-grow">
        <p class="bz-grow-title">${pending > 1 ? `${pending} growth steps waiting` : "Ready to grow"}</p>
        <p class="bz-grow-sub">How should your bonsai grow?</p>
        <div class="bz-options">
          ${offered(tree).map((t) => {
            const info = optionInfo(t, sp);
            return `<button type="button" class="bz-opt" onclick="Bonsai.grow('${t}')">
              <span class="bz-ico">${iconSvg(t, tree)}</span>
              <span class="bz-opt-text"><strong>${info.label}</strong><small>${info.desc}</small></span>
            </button>`;
          }).join("")}
        </div>
        ${pending > 1 ? `<button type="button" class="bz-auto" onclick="Bonsai.autoGrow()">Let it grow on its own (${pending} steps)</button>` : ""}
      </div>`;
  }

  function growHtml(tree) {
    const sp = SPECIES[tree.species];
    const steps = tree.choices.length;
    const pending = Math.max(0, ctx.levels - steps);
    const mature = steps >= ctx.total;
    const svg = treeSvg(tree, { units: ctx.units, total: ctx.total, newStep, backdrop: true });
    const head = `
      <div class="bz-head">
        <div><span class="bz-kicker">Your bonsai · ${drugName(ctx.drug)}</span><h3>${sp.name}</h3></div>
        <span class="bz-level${mature ? " is-mature" : ""}">${mature ? "Mature" : `${steps}/${ctx.total}`}</span>
      </div>`;
    let bottom;
    if (pending > 0) bottom = chooserHtml(tree, pending);
    else if (mature) bottom = `<p class="bz-text">Fully grown. ${sp.flowers ? "It's in full bloom!" : "A beautiful, mature tree."}</p>`;
    else bottom = `<p class="bz-text">Finish your next level to grow it again.</p><div class="bz-bar"><i style="width:${Math.round((steps / ctx.total) * 100)}%"></i></div>`;

    if (ctx.mode === "lesson") {
      return `<div class="bz-lesson-grid"><div class="bz-stage">${svg}</div><div>${head}${bottom}</div></div>`;
    }
    return `${head}<div class="bz-stage">${svg}</div>${bottom}${shelfHtml()}`;
  }

  function shelfHtml() {
    const sel = document.getElementById("drugSelect");
    if (!sel || ctx.mode !== "panel" || sel.options.length < 2) return "";
    const trees = allTrees();
    const items = [...sel.options].map((o) => {
      const t = trees[o.value];
      const on = o.value === ctx.drug;
      return `<button type="button" class="bz-shelf-item${on ? " is-on" : ""}"${on ? ' aria-current="true"' : ""} onclick="Bonsai.showDrug('${o.value}')" title="${o.text}">
        <span class="bz-thumb">${t ? treeSvg(t, { units: t.units || 0, total: t.total || 20 }) : emptyPotSvg()}</span>
        <span class="bz-shelf-name">${o.text}</span>
        <span class="bz-shelf-sub">${t ? `${t.choices.length}/${t.total || 20}` : "Not planted"}</span>
      </button>`;
    }).join("");
    return `<div class="bz-shelf"><span class="bz-kicker">Bonsai shelf</span><div class="bz-shelf-row">${items}</div></div>`;
  }

  // ---------------------------------------------------------- public actions
  function renderPanel(drug, data, topicName = "") {
    const mount = document.getElementById("bonsaiPanel");
    if (!mount) return;
    ctx = Object.assign({ drug, mount, mode: "panel", topicName }, levelsFrom(data));
    syncTree();
    draw();
  }

  function renderPreview(topic) {
    const mount = document.getElementById("bonsaiPanel");
    if (!mount) return;
    mount.innerHTML = `
      <div class="bz-head"><div><span class="bz-kicker">Grow a bonsai</span><h3>${escapeHtml(topic)}</h3></div></div>
      <div class="bz-stage">
        ${treeSvg(demoTree("juniper", "slate"), { total: 20, units: 3, backdrop: true })}
        <span class="bz-demo-tag">Preview</span>
      </div>
      <p class="bz-text">Your bonsai can grow as you finish levels once lessons are available.</p>`;
  }

  async function afterLesson(drug, mount, { course = "" } = {}) {
    if (!mount) return;
    let data = null;
    try {
      const route = course
        ? `/topics/${encodeURIComponent(drug)}/path`
        : `/path/${encodeURIComponent(drug)}?username=${encodeURIComponent(getUsername())}`;
      const r = await apiFetch(BASE_URL + route);
      if (r.ok) data = await r.json();
    } catch (e) {}
    if (!data) return;
    ctx = Object.assign({ drug, mount, mode: "lesson", topicName: course ? data.topic : "" }, levelsFrom(data));
    syncTree();
    mount.classList.add("is-shown");
    if (!getTree(drug)) {
      mount.innerHTML = `
        <div class="bz-nudge">
          <span class="bz-ico">${iconSvg("foliage", { species: "maple" })}</span>
          <div><strong>Grow a bonsai as you learn</strong><p>Plant one on your lessons page. It grows with every level you finish.</p></div>
          <a href="${escapeHtml(course ? lessonPageUrl(course, "focused", drug) : `focused.html?drug=${encodeURIComponent(drug)}`)}">Plant one →</a>
        </div>`;
      return;
    }
    draw();
  }

  function grow(type) {
    if (!ctx) return;
    const tree = getTree(ctx.drug);
    if (!tree || ctx.levels - tree.choices.length <= 0) return;
    if (!offered(tree).includes(type)) return;
    tree.choices.push(type);
    setTree(ctx.drug, tree);
    newStep = tree.choices.length - 1;
    draw();
  }

  function autoGrow() {
    if (!ctx) return;
    const tree = getTree(ctx.drug);
    if (!tree) return;
    while (ctx.levels - tree.choices.length > 0) {
      const o = offered(tree);
      if (!o.length) break;
      tree.choices.push(o[tree.choices.length % o.length]);
    }
    setTree(ctx.drug, tree);
    newStep = -1;
    draw();
  }

  function pickSpecies(k) { if (SPECIES[k]) { draft.species = k; draw(); } }
  function pickPot(k) { if (POTS[k]) { draft.pot = k; draw(); } }
  function plant() {
    if (!ctx) return;
    setTree(ctx.drug, {
      species: draft.species, pot: draft.pot, choices: [], planted: Date.now(),
      levels: ctx.levels, units: ctx.units, total: ctx.total,
    });
    newStep = -1;
    draw();
  }
  function showDrug(drug) {
    const sel = document.getElementById("drugSelect");
    if (!sel || sel.value === drug) return;
    sel.value = drug;
    sel.dispatchEvent(new Event("change"));
  }
  function thumb(drug) {
    const t = getTree(drug);
    return t ? treeSvg(t, { units: t.units || 0, total: t.total || 20 }) : "";
  }

  return {
    renderPanel, renderPreview, afterLesson, grow, autoGrow, pickSpecies, pickPot, plant, showDrug, thumb,
    // for testing / previews
    _treeSvg: treeSvg, _offered: offered, _demo: demoTree, SPECIES, POTS,
  };
})();