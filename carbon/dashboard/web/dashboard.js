"use strict";
// Carbon Leaderboard (DASHBOARD-01, slice D1).
//
// Draws the board files `python -m carbon.dashboard build` writes. Those files
// were already checked against the validator's signed feed (feed.py): this
// page adds no score, rank or incumbent of its own and copies the validator's
// as given. Every string from a board is set as text (textContent), never
// parsed as HTML. Nothing loads from the internet.
//
// The pure view-model functions are exported for the Node check
// (tests/cpu/dashboard_check.cjs); the DOM part runs only in a browser.
(function (root) {
  const SECTIONS = [
    ["accuracy", "Accuracy"],
    ["design_q", "Design decisions"],
    ["near_limit", "Near-limit"],
  ];
  const GATES_NAME = "Safety gates";
  const SERIES_SLOTS = 5;
  const RECIPE = "Recipe not disclosed";
  const LAG_NOTE = "Scores appear once every window they used is retired and published, so this board trails the live exam.";

  // ---- Pure helpers ----
  function decimals(precision) {
    if (!(precision > 0)) return 2;
    return Math.max(0, Math.min(6, Math.ceil(-Math.log10(precision) - 1e-9)));
  }
  function fmt(value, precision) {
    if (typeof value !== "number" || !Number.isFinite(value)) return "—";
    return value.toFixed(decimals(precision));
  }
  function shortKey(hotkey) {
    const text = String(hotkey);
    return text.length > 16 ? text.slice(0, 6) + "…" + text.slice(-4) : text;
  }
  function block(n) { return typeof n === "number" ? "#" + n.toLocaleString("en-US") : "—"; }
  function words(value) { return String(value ?? "").replaceAll("_", " ").toLowerCase(); }

  function parseRoute(hash) {
    const parts = String(hash || "").replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
    if (parts[0] === "b" && parts[1] && parts[2] === "m" && parts[3]) return {view: "miner", slug: parts[1], hotkey: parts[3]};
    if (parts[0] === "b" && parts[1]) return {view: "board", slug: parts[1]};
    return {view: "home"};
  }
  function boardHref(slug) { return "#/b/" + encodeURIComponent(slug); }
  function minerHref(slug, hotkey) { return boardHref(slug) + "/m/" + encodeURIComponent(hotkey); }

  function labelsOf(board) {
    const labels = Array.isArray(board && board.labels) ? board.labels.slice() : [];
    if (!labels.includes("DEVELOPMENT")) labels.unshift("DEVELOPMENT");
    return labels;
  }
  function gatesFailed(sections) {
    const gates = (sections && sections.gates) || {};
    return Object.keys(gates).filter(g => gates[g] === "FAIL").sort();
  }
  // Section names, units and sense come from the feed when it gives them; the
  // page assumes no "better" direction of its own.
  function sectionInfo(board, key) {
    const meta = (board.section_meta || {})[key] || {};
    const fallback = SECTIONS.find(s => s[0] === key)[1];
    const sense = meta.sense === "lower_is_better" ? "lower is better" : meta.sense === "higher_is_better" ? "higher is better" : "";
    return {name: meta.display || fallback, unit: meta.unit || "", sense};
  }
  function sectionValues(board, sections) {
    const precision = board.values.precision;
    return SECTIONS.map(([key]) => {
      const info = sectionInfo(board, key);
      const value = sections ? sections[key] : undefined;
      return {key, name: info.name, sense: info.sense, unit: info.unit, value, text: fmt(value, precision)};
    });
  }
  // Series colour follows the miner's standing order on the board, which the
  // validator sets; miners past the fifth share one neutral "other" colour.
  function seriesSlots(board) {
    const slots = {};
    (board.standing || []).forEach((row, i) => { slots[row.hotkey] = i < SERIES_SLOTS ? "c" + (i + 1) : "c-other"; });
    Object.keys(board.miners || {}).forEach(h => { if (!(h in slots)) slots[h] = "c-other"; });
    return slots;
  }

  function boardView(board) {
    const challengers = new Map((board.challengers || []).map(c => [c.hotkey, c.state]));
    const incumbent = board.incumbent;
    return {
      labels: labelsOf(board),
      title: board.challenge.id,
      device: board.device_class,
      lag: LAG_NOTE,
      incumbent: incumbent && {
        hotkey: incumbent.hotkey,
        since: typeof incumbent.since_block === "number" ? block(incumbent.since_block) : null,
        sections: sectionValues(board, incumbent.sections),
        failed: gatesFailed(incumbent.sections),
      },
      challengers: (board.challengers || []).map(c => ({hotkey: c.hotkey, state: words(c.state)})),
      standing: (board.standing || []).map(row => ({
        rank: row.rank,
        hotkey: row.hotkey,
        incumbent: !!incumbent && incumbent.hotkey === row.hotkey,
        challenger: challengers.has(row.hotkey) ? words(challengers.get(row.hotkey)) : "",
        sections: sectionValues(board, row.best),
        at: block(row.best_at_block),
        submissions: ((board.miners[row.hotkey] || {}).submissions || []).length,
      })),
      health: {
        state: board.feed_state ? board.feed_state.state : "ACCEPTED",
        code: board.feed_state ? board.feed_state.code : null,
        version: board.version,
        key: board.feed.key_id,
        released: block(board.released_through_block),
        windows: (board.released_windows || []).length,
        lag: board.release && typeof board.release.expected_lag_blocks === "number" ? board.release.expected_lag_blocks.toLocaleString("en-US") : null,
        canaries: board.excluded_canaries,
        generated: board.generated_at || "—",
        values: board.values.registered,
        precision: board.values.precision,
      },
    };
  }

  function minerView(board, hotkey) {
    const miner = (board.miners || {})[hotkey];
    if (!miner) return null;
    const standing = (board.standing || []).find(r => r.hotkey === hotkey) || null;
    const challenger = (board.challengers || []).find(c => c.hotkey === hotkey) || null;
    const released = new Set(board.released_windows || []);
    const detail = [];
    for (const row of miner.submissions) {
      for (const [fingerprint, body] of Object.entries(row.detail || {})) {
        if (!released.has(fingerprint)) continue; // feed.py refuses this already; never draw it
        detail.push({submission: row.submission_id, window: fingerprint.slice(7, 19), cases: body.cases});
      }
    }
    return {
      labels: labelsOf(board),
      hotkey,
      recipe: RECIPE,
      incumbent: !!board.incumbent && board.incumbent.hotkey === hotkey,
      rank: standing ? standing.rank : null,
      challenger: challenger ? words(challenger.state) : "",
      best: standing ? sectionValues(board, standing.best) : null,
      submissions: miner.submissions.slice().reverse().map(row => ({
        id: row.submission_id,
        receipt: block(row.receipt_block),
        state: words(row.state),
        scored: row.state === "SCORED",
        sections: sectionValues(board, row.sections),
        failed: gatesFailed(row.sections),
        windows: row.windows.length,
      })),
      detail,
    };
  }

  // ---- Trend chart: a pure layout, a tree of {tag, attrs, children, text} ----
  function node(tag, attrs, children, text) {
    return {tag, attrs: attrs || {}, children: children || [], text: text === undefined ? null : String(text)};
  }
  function niceTicks(low, high, count) {
    if (low === high) { low -= 0.05; high += 0.05; }
    const raw = (high - low) / Math.max(1, count);
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map(m => m * power).find(s => s >= raw) || 10 * power;
    const ticks = [];
    const first = Math.floor(low / step + 1e-9), last = Math.ceil(high / step - 1e-9);
    for (let i = first; i <= last; i++) ticks.push(Number((i * step).toPrecision(12)));
    return ticks;
  }
  function trendSeries(board, section, only) {
    const slots = seriesSlots(board);
    const order = new Map((board.standing || []).map((row, i) => [row.hotkey, i]));
    const rank = h => order.has(h) ? order.get(h) : Infinity;
    const keys = only ? [only] : Object.keys(board.history || {}).sort((a, b) => rank(a) - rank(b) || (a < b ? -1 : 1));
    return keys.filter(h => (board.history || {})[h]).map(h => ({
      hotkey: h,
      slot: only ? "c1" : slots[h] || "c-other",
      points: board.history[h]
        .filter(p => typeof p.sections[section] === "number")
        .map(p => ({x: p.receipt_block, y: p.sections[section]})),
    })).filter(s => s.points.length);
  }
  function trendLayout(series, opts) {
    const W = 720, H = 260, L = 48, R = 16, T = 12, B = 30;
    const xs = series.flatMap(s => s.points.map(p => p.x));
    const ys = series.flatMap(s => s.points.map(p => p.y));
    const svg = node("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.title});
    if (!xs.length) { svg.children.push(node("text", {x: L, y: H / 2, class: "axis"}, [], "No released scores yet")); return {svg, points: []}; }
    const yTicks = niceTicks(Math.min(...ys), Math.max(...ys), 4);
    const y0 = yTicks[0], y1 = yTicks[yTicks.length - 1];
    let x0 = Math.min(...xs), x1 = Math.max(...xs);
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    const sx = x => L + (x - x0) / (x1 - x0) * (W - L - R);
    const sy = y => T + (1 - (y - y0) / (y1 - y0 || 1)) * (H - T - B);
    for (const t of yTicks) {
      svg.children.push(node("line", {x1: L, x2: W - R, y1: sy(t), y2: sy(t), class: "grid"}));
      svg.children.push(node("text", {x: L - 8, y: sy(t) + 4, "text-anchor": "end", class: "axis"}, [], fmt(t, opts.precision)));
    }
    svg.children.push(node("text", {x: L, y: H - 8, class: "axis"}, [], block(x0)));
    svg.children.push(node("text", {x: W - R, y: H - 8, "text-anchor": "end", class: "axis"}, [], block(x1)));
    const placed = [];
    // Others first, so the ranked series draw on top.
    const ordered = series.slice().sort((a, b) => (a.slot === "c-other") === (b.slot === "c-other") ? 0 : a.slot === "c-other" ? -1 : 1);
    for (const s of ordered) {
      const d = s.points.map((p, i) => (i ? "L" : "M") + sx(p.x).toFixed(1) + " " + sy(p.y).toFixed(1)).join(" ");
      svg.children.push(node("path", {d, class: "series " + s.slot}));
      for (const p of s.points) {
        const cx = sx(p.x), cy = sy(p.y);
        svg.children.push(node("circle", {cx: cx.toFixed(1), cy: cy.toFixed(1), r: 4, class: "dot " + s.slot}));
        placed.push({cx, cy, hotkey: s.hotkey, x: p.x, y: p.y});
      }
    }
    return {svg, points: placed, width: W};
  }

  const api = {SECTIONS, GATES_NAME, RECIPE, LAG_NOTE, fmt, decimals, shortKey, parseRoute, boardHref, minerHref,
    labelsOf, gatesFailed, seriesSlots, sectionInfo, boardView, minerView, trendSeries, trendLayout};
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- DOM ----
  const SVG_NS = "http://www.w3.org/2000/svg";
  const app = document.getElementById("app");
  const cache = new Map();
  let index = null;
  let section = "accuracy";

  function el(tag, text, className) {
    const e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = String(text);
    if (className) e.className = className;
    return e;
  }
  function add(parent, ...children) { parent.append(...children); return parent; }
  function link(href, text, className) { const a = el("a", text, className); a.href = href; return a; }
  function pill(text, className) { return el("span", text, "pill " + (className || "")); }
  function mountSvg(tree) {
    const e = document.createElementNS(SVG_NS, tree.tag);
    for (const [k, v] of Object.entries(tree.attrs)) e.setAttribute(k, String(v));
    if (tree.text !== null) e.textContent = tree.text;
    for (const child of tree.children) e.append(mountSvg(child));
    return e;
  }
  function setLabels(labels) {
    const box = document.getElementById("labels");
    box.replaceChildren(...labels.map(l => pill(l, l === "FIXTURE" ? "pill-fixture" : "pill-label")));
  }
  async function getJson(path) {
    if (cache.has(path)) return cache.get(path);
    const response = await fetch(path, {cache: "no-cache"});
    if (!response.ok) throw new Error(path + " " + response.status);
    const value = await response.json();
    cache.set(path, value);
    return value;
  }

  function sectionTiles(values) {
    const grid = el("div", null, "sections");
    for (const v of values) {
      const tile = add(el("div", null, "section-tile"), el("p", v.name, "eyebrow"), el("p", v.text, "value"));
      const note = [v.unit, v.sense].filter(Boolean).join(" · ");
      if (note) tile.append(el("p", note, "hint"));
      grid.append(tile);
    }
    return grid;
  }
  function gatePills(failed, passedText) {
    const box = el("div", null, "gates");
    box.append(el("span", GATES_NAME + ":", "eyebrow"));
    if (!failed.length) box.append(pill(passedText || "all pass", "pill-done"));
    for (const g of failed) box.append(pill(words(g) + " failed", "pill-fail"));
    return box;
  }
  function crumbs(...items) {
    const nav = el("nav", null, "crumbs"); nav.setAttribute("aria-label", "Breadcrumb");
    items.forEach((item, i) => { if (i) nav.append(el("span", "/")); nav.append(item); });
    return nav;
  }
  function healthLine(h) {
    const box = el("div", null, "health");
    const state = h.state === "ACCEPTED" ? "Signature verified" : "Newest feed refused (" + h.code + "); showing the last accepted version";
    box.append(el("span", state, h.state === "ACCEPTED" ? "" : "fail"), el("span", "Feed version " + h.version), el("span", "Key " + h.key),
      el("span", "Released through block " + h.released), el("span", h.windows + " released windows"),
      el("span", h.lag ? "Expected lag " + h.lag + " blocks" : "Expected lag not stated"),
      el("span", "Rounded to " + h.precision), el("span", h.canaries + " canary miner(s) excluded"),
      el("span", "Values: " + h.values), el("span", "Generated " + h.generated));
    return box;
  }

  function trendChart(board, only) {
    const wrap = el("div");
    const bar = el("div", null, "toolbar"); bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "Section");
    for (const [key] of SECTIONS) {
      const b = el("button", sectionInfo(board, key).name); b.type = "button"; b.setAttribute("aria-pressed", String(key === section));
      b.addEventListener("click", () => { section = key; render(); });
      bar.append(b);
    }
    wrap.append(bar);
    const series = trendSeries(board, section, only);
    const info = sectionInfo(board, section), name = info.name, precision = board.values.precision;
    const built = trendLayout(series, {title: name + " by receipt block", precision});
    const figure = el("figure", null, "chart");
    const svg = mountSvg(built.svg);
    const readout = el("p", "Hover a point for its value.", "readout");
    svg.addEventListener("mousemove", event => {
      const box = svg.getBoundingClientRect();
      const x = (event.clientX - box.left) / box.width * built.width, y = (event.clientY - box.top) / box.height * (built.width * 260 / 720);
      let best = null, dist = Infinity;
      for (const p of built.points) { const d = Math.hypot(p.cx - x, p.cy - y); if (d < dist) { dist = d; best = p; } }
      readout.textContent = best && dist < 40 ? `${shortKey(best.hotkey)} · block ${block(best.x)} · ${name} ${fmt(best.y, precision)}` : "Hover a point for its value.";
    });
    figure.append(svg);
    if (!only) {
      const legend = el("div", null, "legend");
      const slots = seriesSlots(board);
      const shown = new Set();
      for (const s of series) {
        const slot = slots[s.hotkey] || "c-other";
        if (slot === "c-other") { if (shown.has(slot)) continue; shown.add(slot); }
        const item = el("span"); const sw = el("span", null, "swatch bg-" + slot);
        item.append(sw, document.createTextNode(slot === "c-other" ? "Other miners" : shortKey(s.hotkey)));
        legend.append(item);
      }
      figure.append(legend);
    }
    if (info.sense) figure.append(el("p", name + ": " + info.sense + ", as the feed states.", "hint"));
    figure.append(readout);
    const table = el("details"); table.append(el("summary", "Show the values as a table"));
    const t = el("table"); const head = el("tr"); head.append(el("th", "Miner"), el("th", "Receipt block", "num"), el("th", name, "num"));
    const body = el("tbody");
    for (const s of series) for (const p of s.points) { const r = el("tr"); r.append(el("td", shortKey(s.hotkey), "key"), el("td", block(p.x), "num"), el("td", fmt(p.y, precision), "num")); body.append(r); }
    const thead = el("thead"); thead.append(head); t.append(thead, body);
    const tw = el("div", null, "table-wrap"); tw.append(t); table.append(tw);
    wrap.append(figure, table);
    return wrap;
  }

  function renderHome() {
    setLabels(["DEVELOPMENT"]);
    const view = el("div");
    view.append(el("p", "Carbon Leaderboard", "eyebrow section-label"), el("h1", "Leaders by Challenge and device class"),
      el("p", "Each board is one Challenge on one device class. CPU and GPU results are never ranked together. " + LAG_NOTE, "lede"));
    if (index.fixture) view.append(add(el("p", null, "notice"), el("strong", "Fixture data. "), document.createTextNode("These boards are synthetic, made to build and test the page. They are not results of any model or Challenge.")));
    const cards = el("div", null, "cards");
    for (const b of index.boards) {
      if (!b.slug) { cards.append(add(el("div", null, "card"), el("p", "Feed refused", "eyebrow"), el("p", b.code, "fail"))); continue; }
      const card = link(boardHref(b.slug), null, "card");
      const head = add(el("div", null, "card-head"), el("h3", b.challenge.id), pill(b.device_class || "no class"));
      const labels = el("div", null, "gates"); for (const l of labelsOf(b)) labels.append(pill(l, l === "FIXTURE" ? "pill-fixture" : ""));
      const meta = add(el("div", null, "meta"), add(el("span", "Incumbent "), el("b", b.incumbent ? shortKey(b.incumbent) : "none")),
        el("span", b.miners + " miners"), el("span", "through block " + block(b.released_through_block)));
      card.append(head, labels, meta);
      if (b.state !== "ACCEPTED") card.append(el("p", "Newest feed refused: " + b.code, "fail"));
      cards.append(card);
    }
    view.append(cards);
    app.replaceChildren(view);
  }

  function renderBoard(board) {
    const v = boardView(board);
    setLabels(v.labels);
    const view = el("div");
    view.append(crumbs(link("#/", "Boards"), el("span", v.title)), el("h1", v.title),
      add(el("div", null, "meta"), add(el("span", "Device class "), el("b", v.device || "none")), add(el("span", "Rule "), el("b", board.challenge.rule || board.challenge.rule_digest.slice(0, 19))),
        add(el("span", "Version "), el("b", board.challenge.version))),
      add(el("p", null, "notice"), el("strong", "Lagged. "), document.createTextNode(v.lag)));
    const leader = el("div", null, "leader");
    const inc = el("section", null, "panel");
    inc.append(el("p", "Incumbent", "eyebrow"));
    if (v.incumbent) {
      inc.append(add(el("p", null, "big-key"), link(minerHref(board.slug, v.incumbent.hotkey), shortKey(v.incumbent.hotkey))),
        el("p", v.incumbent.since ? "Holds since block " + v.incumbent.since : "Incumbent as the validator states it", "hint gap"), sectionTiles(v.incumbent.sections), gatePills(v.incumbent.failed));
    } else inc.append(el("p", "No incumbent yet.", "hint"));
    const ch = el("section", null, "panel");
    ch.append(el("p", "Challengers", "eyebrow"));
    const list = el("ul", null, "list");
    for (const c of v.challengers) list.append(add(el("li"), link(minerHref(board.slug, c.hotkey), shortKey(c.hotkey), "key"), pill(c.state)));
    if (!v.challengers.length) list.append(el("li", "No open challenges."));
    ch.append(list, el("p", "Final states are the validator's, copied as given.", "hint"));
    leader.append(inc, ch);
    view.append(leader);

    view.append(el("h2", "Standing"), el("p", "The validator's rank and best released score, rounded to the feed's registered precision. A failed gate is never offset by another section.", "hint"));
    const tw = el("div", null, "table-wrap"); const t = el("table");
    const head = el("tr"); head.append(el("th", "Rank", "num"), el("th", "Miner"), el("th", "Role"));
    for (const [key] of SECTIONS) head.append(el("th", sectionInfo(board, key).name, "num"));
    head.append(el("th", "Best at block", "num"), el("th", "Submissions", "num"));
    const thead = el("thead"); thead.append(head);
    const body = el("tbody");
    for (const row of v.standing) {
      const r = el("tr");
      const who = el("td", null, "key"); who.append(link(minerHref(board.slug, row.hotkey), shortKey(row.hotkey)));
      r.append(el("td", row.rank, "num"), who, el("td", row.incumbent ? "incumbent" : row.challenger));
      for (const s of row.sections) r.append(el("td", s.text, "num"));
      r.append(el("td", row.at, "num"), el("td", row.submissions, "num"));
      body.append(r);
    }
    t.append(thead, body); tw.append(t); view.append(tw);
    view.append(el("h2", "Trends"), el("p", "Each released, scored submission by receipt block. Colours follow standing; miners past the fifth share one colour.", "hint"), trendChart(board, null));
    view.append(healthLine(v.health));
    app.replaceChildren(view);
  }

  function renderMiner(board, hotkey) {
    const v = minerView(board, hotkey);
    setLabels(labelsOf(board));
    if (!v) { app.replaceChildren(add(el("div"), crumbs(link("#/", "Boards"), link(boardHref(board.slug), board.challenge.id)), el("p", "This miner has no released scores on this board.", "notice"))); return; }
    const view = el("div");
    view.append(crumbs(link("#/", "Boards"), link(boardHref(board.slug), board.challenge.id), el("span", shortKey(hotkey))),
      el("p", "Miner", "eyebrow section-label"), el("h1", shortKey(hotkey), "key"), el("p", hotkey, "hint key"),
      add(el("div", null, "meta"), add(el("span", "Rank "), el("b", v.rank ?? "unranked")), add(el("span", "Role "), el("b", v.incumbent ? "incumbent" : v.challenger || "—")),
        add(el("span", "Device class "), el("b", board.device_class || "none")), el("span", v.recipe)));
    if (v.best) view.append(el("h2", "Best released score"), add(el("section", null, "panel"), sectionTiles(v.best)));
    view.append(el("h2", "Trend"), trendChart(board, hotkey));
    view.append(el("h2", "Submissions"));
    const tw = el("div", null, "table-wrap"); const t = el("table");
    const head = el("tr"); head.append(el("th", "Submission"), el("th", "Receipt block", "num"), el("th", "State"));
    for (const [key] of SECTIONS) head.append(el("th", sectionInfo(board, key).name, "num"));
    head.append(el("th", GATES_NAME), el("th", "Windows", "num"));
    const thead = el("thead"); thead.append(head); const body = el("tbody");
    for (const s of v.submissions) {
      const r = el("tr"); r.append(el("td", s.id, "key"), el("td", s.receipt, "num"), el("td", s.state));
      for (const x of s.sections) r.append(el("td", s.scored ? x.text : "—", "num"));
      r.append(el("td", !s.scored ? "—" : s.failed.length ? s.failed.map(words).join(", ") + " failed" : "all pass", s.failed.length ? "fail" : ""), el("td", s.windows, "num"));
      body.append(r);
    }
    t.append(thead, body); tw.append(t); view.append(tw);
    view.append(el("h2", "Case-level detail"), el("p", "Shown only for released windows, whose cases are already published in the public training pool.", "hint"));
    if (!v.detail.length) view.append(el("p", "No released case-level detail for this miner.", "hint"));
    for (const d of v.detail) {
      const box = el("details"); box.append(el("summary", `${d.submission} · window ${d.window}… · ${d.cases.length} cases`));
      const ct = el("table"); const h = el("tr"); h.append(el("th", "Case"), el("th", "Error", "num")); const th = el("thead"); th.append(h);
      const cb = el("tbody"); for (const c of d.cases) { const r = el("tr"); r.append(el("td", c.case_id, "key"), el("td", typeof c.error === "number" ? c.error.toFixed(4) : "—", "num")); cb.append(r); }
      ct.append(th, cb); const w = el("div", null, "table-wrap"); w.append(ct); box.append(w); view.append(box);
    }
    app.replaceChildren(view);
  }

  async function render() {
    try {
      index = index || await getJson("data/index.json");
      const route = parseRoute(location.hash);
      if (route.view === "home") return renderHome();
      const entry = index.boards.find(b => b.slug === route.slug);
      if (!entry) { app.replaceChildren(add(el("p", null, "notice"), document.createTextNode("No such board. "), link("#/", "All boards"))); return; }
      const board = await getJson("data/boards/" + encodeURIComponent(route.slug) + ".json");
      board.feed_state = board.feed_state || {state: entry.state, code: entry.code};
      return route.view === "miner" ? renderMiner(board, route.hotkey) : renderBoard(board);
    } catch (error) {
      app.replaceChildren(add(el("p", null, "notice"), el("strong", "Feed unavailable. "), document.createTextNode(String(error.message || error))));
    }
  }
  window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
  render();
})(typeof globalThis !== "undefined" ? globalThis : this);
