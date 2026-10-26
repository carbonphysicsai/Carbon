"use strict";
// Carbon Leaderboard (DASHBOARD-02 S2): the per-Challenge pages, drawn from
// board.v2 (`data/v2/<slug>.json`, carbon/dashboard/board_v2.py).
//
// The page renders board.v2 fields only. It computes no rank, king, margin,
// target or rule value of its own: every number is copied as the board gives
// it. A null field is not drawn (its reason stays in the JSON); a section
// with one shows a single muted line (MORE). Rule statements appear only
// while the rules card's status is OK, else one RULES_LINE stands in their
// place (in the target panel on a live board). No per-case, input or
// prediction value is drawn. The target's margins and noise guard, from the
// signed feed (VALIDATOR-33 A), are rule statements too: drawn only with an OK
// rules card (the Test Lead, #1144).
//
// Pages are pure functions from a board to a node tree ({tag, attrs,
// children}); `mount` turns a tree into DOM with createElement and text nodes,
// never HTML parsing. The pure part is exported for the Node checks
// (tests/cpu/dashboard_check.cjs); the DOM part runs only in a browser.
(function (root) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const REPO = "https://github.com/carbonphysicsai/Carbon";
  const LINKS = {
    launchpad: REPO + "/blob/main/carbon/miner_mcp/README.md",
    journey: REPO + "/blob/main/docs/development/FRESH_MINER_JOURNEY.md",
    source: REPO + "/tree/main/carbon/dashboard",
  };
  const ELIGIBLE = "Eligible for the championship";
  const RULES_LINE = "Rules unavailable";
  const MORE = "More coming as the Validator publishes it";
  const EMPTY_EPOCH = "no contenders: king paid";
  const PHASES = {
    LIVE: ["Live", "chip-live"],
    PRE_FIRST_RELEASE: ["Before first release", "chip-pre"],
    STALE: ["Stale", "chip-warn"],
  };
  const LADDER = {
    SHOWN: ["Shown", "chip-ok"],
    NO_IMPROVEMENT_BEYOND_GRAIN: ["no improvement beyond the grain", "chip-muted"],
    SEALED_UNTIL_GRAIN: ["sealed until the grain is posted", "chip-sealed"],
  };
  const REFUSALS = {
    malformed_submission: "Malformed submission",
    contract_digest_malformed: "Malformed contract digest",
    development_variant_not_served: "Development variant not served",
    contract_not_served: "Contract not served",
    challenge_mismatch: "Challenge mismatch",
    oversized_submission: "Submission too large",
    strategy_not_utf8: "Strategy is not UTF-8",
    strategy_bom: "Strategy has a byte-order mark",
    strategy_nesting_too_deep: "Strategy nesting too deep",
    strategy_not_json: "Strategy is not JSON",
    strategy_not_object: "Strategy must be an object",
    non_finite_value: "Non-finite value",
    duplicate_key: "Duplicate key",
    integer_out_of_range: "Integer out of range",
    hotkey_window_used: "Hotkey already used",
    receipt_block_missing: "Receipt block missing",
    level4_envelope_incomplete: "Level 4 submission incomplete",
    unclassified_refusal: "Other",
    other: "Other",
  };
  const SEALED_GRAIN = "Scores sealed until the screening grain is set";
  const ENTRANT_COLUMNS = [
    ["est_improvement_pct", "Estimate", "%"],
    ["lower_bound_pct", "Lower bound", "%"],
    ["guard_bar_pct", "Guard bar", "%"],
    ["gap_to_win_pct", "Gap to win", "%"],
    ["safety", "Safety", ""],
    ["outcome", "Outcome", ""],
  ];
  const STOPS = {efficacy: "stopped early: efficacy", futility: "stopped early: futility", max: "ran to the maximum"};
  const NETWORK_FIELDS = [["uids", "UIDs"], ["validators", "Validators"], ["emission", "Emission"]];

  // ---- Node trees ----
  function h(tag, attrs, ...kids) {
    const children = [];
    (function push(list) {
      for (const k of list) {
        if (k === null || k === undefined || k === false) continue;
        if (Array.isArray(k)) push(k);
        else if (typeof k === "object") children.push(k);
        else children.push({tag: "#text", attrs: {}, children: [], text: String(k)});
      }
    })(kids);
    return {tag, attrs: attrs || {}, children};
  }
  function walk(node, visit) { visit(node); for (const c of node.children) walk(c, visit); }
  function textOf(node) {
    const out = [];
    walk(node, n => { if (n.tag === "#text") out.push(n.text); });
    return out.join(" ").replace(/\s+/g, " ").trim();
  }
  function mount(node, doc, inSvg) {
    if (node.tag === "#text") return doc.createTextNode(node.text);
    const svg = inSvg || node.tag === "svg";
    const e = svg ? doc.createElementNS(SVG_NS, node.tag) : doc.createElement(node.tag);
    for (const [k, v] of Object.entries(node.attrs)) {
      if (v === null || v === undefined || v === false) continue;
      e.setAttribute(k, v === true ? "" : String(v));
    }
    for (const c of node.children) e.appendChild(mount(c, doc, svg));
    return e;
  }

  // ---- Formatting (display only) ----
  function isNum(v) { return typeof v === "number" && Number.isFinite(v); }
  function places(values) {
    let most = 0;
    for (const v of values) {
      if (!isNum(v)) continue;
      const text = String(v);
      if (text.includes("e")) return 6;
      const dot = text.indexOf(".");
      if (dot >= 0) most = Math.max(most, text.length - dot - 1);
    }
    return Math.min(6, most);
  }
  function fmt(v, digits) {
    if (!isNum(v)) return "—";
    return v.toFixed(digits === undefined ? places([v]) : digits);
  }
  function signed(v, digits) {
    if (!isNum(v)) return "—";
    return (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(digits === undefined ? places([v]) : digits);
  }
  function plain(v) {
    if (v === null || v === undefined) return null;
    if (isNum(v)) return fmt(v);
    if (typeof v === "string" || typeof v === "boolean") return String(v);
    return null;
  }
  function shortKey(key) {
    const text = String(key);
    return text.length > 14 ? text.slice(0, 6) + "…" + text.slice(-4) : text;
  }
  function shortDigest(digest) {
    const text = String(digest || "");
    return text.startsWith("sha256:") ? text.slice(7, 15) : text.slice(0, 8);
  }
  function block(n) { return isNum(n) ? "#" + n.toLocaleString("en-US") : "—"; }
  function words(v) { return String(v ?? "").replaceAll("_", " ").toLowerCase(); }
  function utcSeconds(text) {
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/.exec(String(text || ""));
    if (!m) return null;
    const ms = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
  }
  function utc(seconds) {
    if (!isNum(seconds)) return "—";
    return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }
  function span(seconds) {
    if (!isNum(seconds)) return "—";
    const s = Math.max(0, Math.round(seconds));
    const d = Math.floor(s / 86400), hr = Math.floor(s % 86400 / 3600), mi = Math.floor(s % 3600 / 60);
    if (d) return d + " d" + (hr ? " " + hr + " h" : "");
    if (hr) return hr + " h" + (mi ? " " + mi + " min" : "");
    if (mi) return mi + " min";
    return s + " s";
  }
  function countdown(seconds) {
    if (!isNum(seconds)) return "—";
    if (seconds <= 0) return "due now";
    const s = Math.floor(seconds);
    const d = Math.floor(s / 86400);
    const clock = [Math.floor(s % 86400 / 3600), Math.floor(s % 3600 / 60), s % 60].map(x => String(x).padStart(2, "0")).join(":");
    return (d ? d + " d " : "") + clock;
  }
  function rulesOk(board) { return !!board.rules && board.rules.status === "OK"; }
  function sectionShort(board) {
    const s = board.ranking_section;
    return s ? s.display || s.name : "Score";
  }
  function sectionLabel(board) {
    const s = board.ranking_section;
    if (!s) return "screening value";
    return s.label || s.display || s.name;
  }

  // ---- Routes ----
  function parseRoute(hash) {
    const parts = String(hash || "").replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
    if (parts[0] === "b" && parts[1] && parts[2] === "m" && parts[3]) return {view: "miner", slug: parts[1], hotkey: parts[3]};
    if (parts[0] === "b" && parts[1]) return {view: "board", slug: parts[1]};
    if (parts[0] === "mine") return {view: "mine"};
    if (parts[0] === "showcase") return {view: "showcase", file: parts[1] || null};
    return {view: "home"};
  }
  function boardHref(slug) { return "#/b/" + encodeURIComponent(slug); }
  function minerHref(slug, hotkey) { return boardHref(slug) + "/m/" + encodeURIComponent(hotkey); }
  function labelsOf(board) {
    const labels = Array.isArray(board && board.labels) ? board.labels.slice() : [];
    if (!labels.includes("DEVELOPMENT")) labels.unshift("DEVELOPMENT");
    return labels;
  }

  // ---- Small parts ----
  function chip(text, cls) { return h("span", {class: "chip " + (cls || "")}, text); }
  function eyebrow(text) { return h("p", {class: "eyebrow"}, text); }
  function copyButton(value, label) {
    return h("button", {type: "button", class: "copy", "data-copy": value, "aria-label": "Copy " + label, title: "Copy " + label}, "Copy");
  }
  function hotkey(value, opts) {
    const o = opts || {};
    return h("span", {class: "hotkey"}, o.href ? h("a", {href: o.href, class: "key", title: value}, shortKey(value)) : h("span", {class: "key", title: value}, shortKey(value)),
      o.copy ? copyButton(value, o.label || "hotkey") : null);
  }
  function stat(label, value, note, cls) {
    return h("div", {class: "stat " + (cls || "")}, h("dt", null, label), h("dd", null, value), note ? h("dd", {class: "note"}, note) : null);
  }
  function crown() {
    return h("svg", {viewBox: "0 0 24 16", class: "crown", "aria-hidden": "true", focusable: "false"},
      h("path", {d: "M2 14h20L20 4l-5 5-3-7-3 7-5-5z"}));
  }
  function table(caption, head, rows, opts) {
    // Never an empty table: callers draw a sentence instead.
    if (!rows.length) return null;
    const o = opts || {};
    return h("div", {class: "table-wrap"},
      h("table", {id: o.id || null},
        h("caption", {class: "sr-only"}, caption),
        h("thead", null, h("tr", null, head.map(([text, cls]) => h("th", {scope: "col", class: cls || null}, text)))),
        h("tbody", null, rows)));
  }

  // ---- Sparkline (pure layout) ----
  function niceRange(lo, hi) {
    if (lo === hi) { const pad = Math.abs(lo) * 0.05 || 0.05; return [lo - pad, hi + pad]; }
    const pad = (hi - lo) * 0.08;
    return [lo - pad, hi + pad];
  }
  function sparkline(spec) {
    const W = 900, H = 220, L = 8, R = 8, T = 22, B = 10;
    const main = spec.main || [], others = spec.others || [];
    const all = main.concat(others);
    const svg = h("svg", {viewBox: `0 0 ${W} ${H}`, class: "spark", role: "img", "aria-label": spec.title});
    svg.children.push(h("title", null, spec.title));
    if (!all.length) return svg;
    const [y0, y1] = niceRange(Math.min(...all.map(p => p.y)), Math.max(...all.map(p => p.y)));
    let x0 = Math.min(...all.map(p => p.x)), x1 = Math.max(...all.map(p => p.x));
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    const sx = x => L + (x - x0) / (x1 - x0) * (W - L - R);
    const sy = y => T + (1 - (y - y0) / (y1 - y0)) * (H - T - B);
    for (const t of [y0, (y0 + y1) / 2, y1]) {
      svg.children.push(h("line", {x1: L, x2: W - R, y1: sy(t).toFixed(1), y2: sy(t).toFixed(1), class: "grid"}));
    }
    for (const x of spec.handovers || []) {
      svg.children.push(h("line", {x1: sx(x).toFixed(1), x2: sx(x).toFixed(1), y1: T, y2: H - B, class: "handover"}));
      svg.children.push(h("text", {x: (sx(x) + 4).toFixed(1), y: T + 10, class: "axis handover-label"}, "new king"));
    }
    for (const p of others) svg.children.push(h("circle", {cx: sx(p.x).toFixed(1), cy: sy(p.y).toFixed(1), r: 2.5, class: "ghost"}));
    if (main.length) {
      const d = main.map((p, i) => (i ? "L" : "M") + sx(p.x).toFixed(1) + " " + sy(p.y).toFixed(1)).join(" ");
      svg.children.push(h("path", {d, class: "line"}));
      main.forEach((p, i) => svg.children.push(h("circle", {cx: sx(p.x).toFixed(1), cy: sy(p.y).toFixed(1), r: i === main.length - 1 ? 4.5 : 3, class: i === main.length - 1 ? "dot last" : "dot"})));
    }
    return svg;
  }
  // The chart with its axis labels as page text, so they stay readable at
  // every width (SVG text would scale with the chart).
  function sparkFigure(spec, caption) {
    const all = spec.main.concat(spec.others || []);
    const ys = all.map(p => p.y), xs = all.map(p => p.x);
    const digits = places(ys);
    return h("figure", {class: "card chart"},
      h("div", {class: "spark-y"}, h("span", null, "high " + fmt(Math.max(...ys), digits))),
      sparkline(spec),
      h("div", {class: "spark-x"}, h("span", null, "low " + fmt(Math.min(...ys), digits)), h("span", null, "blocks " + block(Math.min(...xs)) + " to " + block(Math.max(...xs)))),
      h("figcaption", {class: "hint"}, caption));
  }
  function historySpec(board) {
    const hist = board.history || {};
    const points = hist.points || {};
    const king = board.king && board.king.hotkey;
    const label = sectionLabel(board);
    // A king series with values; the feed's reigns (VALIDATOR-33 A) carry none
    // and are listed as handovers instead.
    if (Array.isArray(hist.kings) && hist.kings.some(k => isNum(k.value))) {
      const main = [], handovers = [];
      let previous = null;
      hist.kings.forEach((k, i) => {
        const x = [k.receipt_block, k.block, k.epoch].find(isNum);
        if (!isNum(k.value)) return;
        const at = isNum(x) ? x : i;
        if (previous !== null && k.hotkey !== previous) handovers.push(at);
        previous = k.hotkey;
        main.push({x: at, y: k.value, hotkey: k.hotkey});
      });
      return {kind: "kings", main, others: [], handovers, title: "King's " + label + " over released windows"};
    }
    const main = king && points[king] ? points[king].map(p => ({x: p.receipt_block, y: p.value, hotkey: king})) : [];
    const others = [];
    for (const [key, series] of Object.entries(points)) if (key !== king) for (const p of series) others.push({x: p.receipt_block, y: p.value, hotkey: key});
    return {kind: "points", main, others, handovers: [], title: "Current king's " + label + " over released windows, other eligible miners in grey"};
  }

  // ---- Page sections ----
  // A null field is never drawn: its reason stays in the board.v2 JSON. A
  // section with a null field shows one muted line (MORE) instead.
  function anyNull(obj, keys) { return !obj || keys.some(k => obj[k] === null || obj[k] === undefined); }
  function moreLine(show) { return show ? h("p", {class: "more-line"}, MORE) : null; }
  function section(name, attrs, ...kids) { return h("section", Object.assign({"data-section": name}, attrs), ...kids); }

  function boardBanners(board, ctx) {
    const out = [];
    if (board.feed_state && board.feed_state.state === "REFUSED") {
      out.push(h("div", {class: "alert", role: "alert"}, h("strong", null, "Newest feed refused (" + words(board.feed_state.code) + "). "),
        "Showing the last accepted version."));
    }
    if (board.phase === "STALE") {
      const age = board.freshness && board.freshness.age_seconds;
      const after = board.freshness && board.freshness.stale_after_seconds;
      const read = board.freshness && board.freshness.basis === "as_of_block" ? "The feed's chain time is " + span(age) + " old" : "The feed was generated " + span(age) + " ago";
      out.push(h("div", {class: "alert", role: "alert"}, h("strong", null, "Stale feed. "),
        isNum(age) ? read + (isNum(after) ? " (stale after " + span(after) + "). " : ". ") : "",
        "Values may be out of date."));
    }
    if (ctx.eraBefore && ctx.eraBefore !== board.era && board.launch) {
      out.push(h("div", {class: "alert alert-era", role: "note"}, h("strong", null, "New exam. "),
        "This board moved to " + board.launch.exam_version_label + " since your last visit. The ladder starts fresh in each exam."));
    } else if (ctx.eraBefore && ctx.eraBefore !== board.era) {
      out.push(h("div", {class: "alert alert-era", role: "note"}, h("strong", null, "New rule era. "),
        "This board moved from rule " + shortDigest(ctx.eraBefore) + " to " + shortDigest(board.era) + " since your last visit. History starts fresh in each era."));
    }
    return out;
  }

  function rulesLine() { return h("p", {class: "rules-line"}, RULES_LINE); }
  // `inTarget`: the target panel carries the page's one rules line instead.
  function boardHead(board, inTarget) {
    const phase = PHASES[board.phase] || [words(board.phase), ""];
    const ok = rulesOk(board);
    return h("header", {class: "board-head"},
      h("nav", {class: "crumbs", "aria-label": "Breadcrumb"}, h("a", {href: "#/"}, "Boards"), h("span", {"aria-hidden": "true"}, "/"), h("span", {"aria-current": "page"}, board.challenge.id)),
      h("h1", null, board.challenge.id),
      h("div", {class: "chips"},
        chip(phase[0], phase[1]),
        board.device_class ? chip(board.device_class, "chip-plain") : null,
        board.launch ? chip("Exam " + board.launch.exam_version_label, "chip-plain") : chip("Era " + shortDigest(board.era), "chip-plain"),
        ok && board.challenge.rule ? chip("Rule " + board.challenge.rule, "chip-plain") : null,
        chip("Version " + board.challenge.version, "chip-plain")),
      // The one place rule text would go while the rules card is not OK.
      ok || inTarget ? null : rulesLine());
  }

  function heroPre(board, ctx) {
    const lag = board.next_release && board.next_release.lag;
    const ok = rulesOk(board) && lag && isNum(lag.hours);
    const when = timingOf(board.next_release, ctx, !!board.as_of_block) || timingOf(board.next_round, ctx);
    return h("section", {class: "hero", "aria-labelledby": "hero-title"},
      eyebrow("First release"),
      h("h2", {id: "hero-title"}, ok ? "First scores publish about " + Math.round(lag.hours) + " h after the first round" : "First scores publish after the first round is released"),
      h("p", {class: "lede"}, "No window of this rule era has been released yet, so no score is shown.",
        rotationText(board) ? " " + rotationText(board) + "." : ""),
      when ? h("div", {class: "hero-count"}, when) : null,
      h("div", {class: "chips hero-labels"}, labelsOf(board).map(l => chip(l, l === "FIXTURE" ? "chip-warn" : "chip-label"))),
      h("div", {class: "actions"}, h("a", {class: "btn btn-primary", href: "#/mine"}, "How to mine"), h("a", {class: "btn", href: LINKS.launchpad}, "Launchpad docs")));
  }

  // The round period is a rule statement: shown only from a matching rules card
  // (the Test Lead, 2026-10-12; the card is the single source of public rules).
  function rotationText(board) {
    const r = board.rotation;
    return rulesOk(board) && r && isNum(r.blocks) ? "Rounds rotate every " + r.blocks.toLocaleString("en-US") + " blocks, about " + r.hours + " h" : null;
  }

  // What is scored: each section's name, sense and unit, as the feed states them.
  const SENSES = {lower_is_better: "lower is better", higher_is_better: "higher is better"};
  function scoredBlock(board) {
    const rows = (board.sections || []).map(s => h("li", {class: "scored-row"},
      h("span", {class: "scored-name"}, s.display || words(s.name)),
      h("span", {class: "scored-sense"}, s.name === "gates" ? "pass or fail" : [SENSES[s.sense], s.unit].filter(Boolean).join(" · "))));
    if (!rows.length) return null;
    return section("scored", {class: "block", "aria-labelledby": "scored-title"},
      h("div", {class: "block-head"}, h("h2", {id: "scored-title"}, "What is scored")),
      h("ul", {class: "scored"}, rows),
      rulesOk(board) ? h("p", {class: "hint"}, "A failed safety gate is never offset by a better score on another section.") : null);
  }

  // The king card's fields. Crowning and the next halving are given in UTC
  // (the feed's ledger clock) or, in an older shape, as an epoch: either fills
  // them. The coldkey and reward eligibility are drawn when present.
  const KING_FIELDS = ["uid", "value", "margin", "share_now", "next_halving_epoch", "since_block", "since_utc", "crowned_epoch", "defences"];
  const KING_EITHER = {crowned_epoch: "crowned_utc", next_halving_epoch: "next_halving_utc"};
  function kingMissing(k) {
    if (!k) return true;
    return KING_FIELDS.some(key => {
      if (key === "next_halving_epoch" && k.share_now === 0) return false; // not paid now: no halving
      const other = KING_EITHER[key];
      return (k[key] === null || k[key] === undefined) && (!other || k[other] === null || k[other] === undefined);
    });
  }
  function until(at, ctx) {
    return h("span", {class: "count-value", "data-until": at, "aria-live": "off"}, countdown(at - ctx.now));
  }
  function kingCard(board, ctx) {
    const k = board.king;
    const top = h("div", {class: "card-top"}, crown(), h("h2", {id: "king-title", class: "card-title"}, "King"),
      k && isNum(k.uid) ? chip("UID " + k.uid, "chip-plain") : null,
      k && k.challenger_state ? chip(words(k.challenger_state), "chip-muted") : null);
    if (!k) return section("king", {class: "card king", "aria-labelledby": "king-title"}, top, board.launch ? h("p", {class: "hint"}, "No king yet") : moreLine(true));
    const digits = places([k.value, k.margin]);
    const since = utcSeconds(k.since_utc);
    const crowned = utcSeconds(k.crowned_utc);
    const halving = utcSeconds(k.next_halving_utc);
    const stats = [
      isNum(k.margin) ? stat("Margin over runner-up", signed(k.margin, digits), k.runner_up ? "runner-up " + shortKey(k.runner_up) : null) : null,
      isNum(k.share_now) ? stat("Share now", fmt(k.share_now), "from the validator's reward clock") : null,
      halving !== null ? stat("Next halving", until(halving, ctx), utc(halving))
        : isNum(k.next_halving_epoch) ? stat("Next halving", "epoch " + k.next_halving_epoch) : null,
      since !== null ? stat("Held for", span(ctx.now - since), "since " + utc(since)) : null,
      since === null && isNum(k.since_block) ? stat("Held since", "block " + block(k.since_block)) : null,
      crowned !== null ? stat("Crowned", utc(crowned)) : isNum(k.crowned_epoch) ? stat("Crowned", "epoch " + k.crowned_epoch) : null,
      isNum(k.defences) ? stat("Defences", String(k.defences), "finals survived") : null,
      typeof k.eligible === "boolean" ? stat("Reward", k.eligible ? "eligible" : "not eligible", k.eligibility_reason ? words(k.eligibility_reason) : null) : null,
      k.coldkey ? stat("Coldkey", h("span", {class: "key", title: k.coldkey}, shortKey(k.coldkey))) : null,
    ].filter(Boolean);
    return section("king", {class: "card king", "aria-labelledby": "king-title"}, top,
      h("p", {class: "king-key"}, hotkey(k.hotkey, {copy: true, href: minerHref(board.slug, k.hotkey)})),
      isNum(k.value) ? h("div", {class: "metric"}, h("span", {class: "metric-value"}, fmt(k.value, digits)), h("span", {class: "metric-label"}, sectionLabel(board))) : null,
      stats.length ? h("dl", {class: "stats"}, stats) : null,
      moreLine(!board.launch && kingMissing(k)));
  }

  // The target's margins, noise guard, kind, registered score and gate list
  // are rule statements (the Test Lead, #1144): drawn only while the rules
  // card is OK, though board.v2 keeps them. Otherwise the panel shows the
  // king's score and gate results from the feed and the page's one rules line.
  const TARGET_FIELDS = ["value", "posted_margin", "noise_guard"];
  const POSTED = "posted by the validator";
  function percent(v) { return isNum(v) ? (v * 100).toFixed(2) + "%" : null; }
  function guardText(g) {
    if (g === null || g === undefined) return null;
    if (typeof g !== "object") return plain(g);
    const parts = [["alpha", "alpha"], ["n_min", "n_min"], ["n_boot", "n_boot"], ["important_min", "important_min"]]
      .filter(([key]) => isNum(g[key])).map(([key, name]) => name + " " + g[key].toLocaleString("en-US"));
    return parts.length ? parts.join(", ") : null;
  }
  function targetCard(board) {
    const t = board.target_to_beat || {};
    const ok = rulesOk(board);
    const k = board.king;
    const kingGates = k && k.gates ? Object.entries(k.gates) : [];
    const kingPart = [
      k && isNum(k.value) ? h("div", {class: "metric"}, h("span", {class: "metric-value"}, fmt(k.value)), h("span", {class: "metric-label"}, "king's " + sectionLabel(board))) : null,
      kingGates.length ? h("p", {class: "hint"}, "King's gates: " + kingGates.map(([name, v]) => words(name) + " " + String(v).toLowerCase()).join(", ") + ".") : null,
    ];
    if (!ok) {
      return section("target", {class: "card target", "aria-labelledby": "target-title"},
        h("div", {class: "card-top"}, h("h2", {id: "target-title", class: "card-title"}, "Target to beat")),
        kingPart, rulesLine(), moreLine(anyNull(t, TARGET_FIELDS)));
    }
    const margin = (v, what) => (isNum(v) ? what + ", " + percent(v) + ", " + POSTED : POSTED);
    const bars = [
      ["Posted margin", plain(t.posted_margin), margin(t.posted_margin, "relative, final")],
      isNum(t.screening_margin) ? ["Screening margin", plain(t.screening_margin), margin(t.screening_margin, "relative, screening entry")] : null,
      ["Noise guard", guardText(t.noise_guard), typeof t.noise_guard === "object" ? "the final comparison, " + POSTED : POSTED],
    ].filter(row => row && row[1] !== null)
      .map(([name, value, note]) => h("li", {class: "bar-row"}, h("span", {class: "bar-name"}, name), h("span", {class: "bar-value"}, value), h("span", {class: "bar-note"}, note)));
    const value = plain(t.value);
    const score = t.registered_score;
    const gates = Array.isArray(t.gates) ? t.gates : [];
    return section("target", {class: "card target", "aria-labelledby": "target-title"},
      h("div", {class: "card-top"}, h("h2", {id: "target-title", class: "card-title"}, "Target to beat"),
        t.kind ? chip(words(t.kind), "chip-plain") : null),
      value !== null ? h("div", {class: "metric"}, h("span", {class: "metric-value"}, value), h("span", {class: "metric-label"}, sectionLabel(board))) : kingPart[0],
      kingPart[1],
      bars.length ? h("ul", {class: "bars", "aria-label": "Both bars"}, bars) : null,
      score && score.decision ? h("p", {class: "hint"}, "Registered score: " + score.decision + (score.registry_sha256 ? ", registry " + shortDigest(score.registry_sha256) : "") + ".") : null,
      gates.length ? h("p", {class: "hint"}, "Gates: " + gates.map(words).join(", ") + ".") : null,
      h("p", {class: "hint"}, "Two bars, the posted margin and the noise guard, as the Validator's rules card sets them."),
      moreLine(anyNull(t, TARGET_FIELDS)));
  }

  // `estimate`: the time is the feed's block estimated at the nominal block time.
  function timingOf(part, ctx, estimate) {
    if (!part) return null;
    const at = utcSeconds(part.next_utc);
    if (at !== null) {
      const where = isNum(part.next_block) ? "block " + block(part.next_block) + ", " : "";
      return h("span", {class: "count"}, until(at, ctx),
        h("span", {class: "count-note"}, where + (estimate ? "about " + utc(at) + " at 12 s per block" : utc(at))));
    }
    if (isNum(part.next_block)) return h("span", {class: "count"}, h("span", {class: "count-value"}, "block " + block(part.next_block)));
    return null;
  }
  const RELEASE_FIELDS = ["next_utc", "next_block", "lag"];
  function timingCard(board, ctx) {
    const round = board.next_round || {}, release = board.next_release || {};
    const ok = rulesOk(board);
    const every = ok && round.every ? h("p", {class: "hint"}, "Every " + round.every.blocks.toLocaleString("en-US") + " blocks (about " + round.every.hours + " h)")
      : rotationText(board) ? h("p", {class: "hint"}, rotationText(board) + ".") : null;
    const lag = ok && release.lag ? "Release lag " + release.lag.blocks.toLocaleString("en-US") + " blocks (about " + Math.round(release.lag.hours) + " h)." : "";
    const roundWhen = timingOf(round, ctx);
    return section("timing", {class: "timing-block", "aria-label": "Next round and release"},
      h("div", {class: "timing"},
        roundWhen || every ? h("div", {class: "card tick"}, eyebrow("Next round"), roundWhen, every) : null,
        h("div", {class: "card tick"}, eyebrow("Next release"), timingOf(release, ctx, !!board.as_of_block),
          h("p", {class: "hint"}, release.released_windows + " released window" + (release.released_windows === 1 ? "" : "s") + " in this era. " + lag))),
      moreLine(anyNull(round, ["next_utc", "next_block"]) || (anyNull(round, ["every"]) && anyNull(board, ["rotation"])) || anyNull(release, RELEASE_FIELDS)));
  }

  function leaderboard(board) {
    const lb = board.eligible_leaderboard;
    const label = sectionLabel(board);
    const king = board.king && board.king.hotkey;
    const parts = [];
    const coldkeys = Array.isArray(lb.coldkeys);
    const sealed = coldkeys && !isNum(lb.grain_pct) && (lb.coldkeys.some(r => r.status === "SEALED_UNTIL_GRAIN")
      || lb.reasons && lb.reasons.grain_pct === "grain_human_input");
    const notes = coldkeys ? [] : ["Ranked by " + label + "."];
    if (rulesOk(board) && lb.release_lag && isNum(lb.release_lag.hours)) notes.push("Scores publish about " + Math.round(lb.release_lag.hours) + " h after a window.");
    if (rulesOk(board) && isNum(lb.grain_pct)) notes.push("Grain " + fmt(lb.grain_pct) + "%.");
    if (notes.length) parts.push(h("p", {class: "hint"}, notes.join(" ")));
    if (sealed) parts.push(h("p", {class: "hint grain-sealed"}, SEALED_GRAIN));
    if (Array.isArray(lb.coldkeys) && lb.coldkeys.length) {
      const digits = places(lb.coldkeys.map(r => r.displayed_score));
      const rows = lb.coldkeys.map(r => {
        const status = LADDER[r.status] || [words(r.status), "chip-muted"];
        const hasKing = r.hotkeys.includes(king);
        return h("tr", {"data-find": [r.coldkey].concat(r.hotkeys).join(" ").toLowerCase(), class: hasKing ? "is-king" : null},
          h("td", {class: "num rank"}, r.status !== "SEALED_UNTIL_GRAIN" && isNum(r.rank) ? r.rank : ""),
          h("td", null, h("span", {class: "key", title: r.coldkey}, shortKey(r.coldkey)), hasKing ? h("span", {class: "crown-tag"}, "king") : null),
          h("td", {class: "num"}, r.status !== "SEALED_UNTIL_GRAIN" && isNum(r.displayed_score) ? fmt(r.displayed_score, digits) : ""),
          h("td", null, chip(status[0], status[1])),
          h("td", {class: "opt"}, h("details", {class: "hotkeys"}, h("summary", null, r.hotkeys.length + " hotkey" + (r.hotkeys.length === 1 ? "" : "s")),
            h("ul", null, r.hotkeys.map(k => h("li", null, h("a", {href: minerHref(board.slug, k), class: "key", title: k}, shortKey(k)), k === king ? h("span", {class: "crown-tag"}, "king") : null))))));
      });
      parts.push(finder("ladder"), table(ELIGIBLE + ", per coldkey",
        [["Rank", "num"], ["Coldkey"], ["Displayed", "num"], ["Status"], ["Hotkeys", "opt"]], rows, {id: "ladder"}));
      parts.push(h("p", {class: "hint"}, "One pooled displayed score per coldkey; its hotkeys are listed for information."));
    } else if (!coldkeys && lb.entries.length) {
      const digits = places(lb.entries.map(r => r.screening_value));
      const rows = lb.entries.map(r => h("tr", {"data-find": String(r.hotkey).toLowerCase(), class: r.is_king ? "is-king" : null},
        h("td", {class: "num rank"}, r.rank),
        h("td", null, h("a", {href: minerHref(board.slug, r.hotkey), class: "key", title: r.hotkey}, shortKey(r.hotkey)), r.is_king ? h("span", {class: "crown-tag"}, "king") : null,
          isNum(r.uid) ? h("span", {class: "uid"}, "UID " + r.uid) : null),
        h("td", {class: "num"}, isNum(r.screening_value) ? fmt(r.screening_value, digits) : ""),
        board.launch ? h("td", {class: "bar-col opt"}, isNum(r.screening_value) ? miniBar(r.screening_value) : null) : h("td", {class: "num opt"}, isNum(r.best_at_block) ? block(r.best_at_block) : ""),
        h("td", {class: "opt"}, r.challenger_state ? chip(words(r.challenger_state), "chip-muted") : "")));
      parts.push(finder("ladder"), table((lb.label || ELIGIBLE) + ", per hotkey", [["Rank", "num"], ["Hotkey"], [sectionShort(board), "num"], board.launch ? ["", "bar-col opt"] : ["Best at block", "num opt"], [board.launch ? "Latest result" : "Challenge", "opt"]].filter(Boolean), rows, {id: "ladder"}));
    } else {
      parts.push(h("p", {class: "empty"}, "No eligible entries in this release yet."));
    }
    return section("leaderboard", {class: "block", "aria-labelledby": "lb-title"},
      h("div", {class: "block-head"}, h("h2", {id: "lb-title"}, lb.label || ELIGIBLE)),
      parts);
  }
  function finder(target) {
    return h("div", {class: "finder"},
      h("label", {for: "find-" + target, class: "sr-only"}, "Find a hotkey or coldkey"),
      h("input", {id: "find-" + target, type: "search", placeholder: "Find a hotkey or coldkey", autocomplete: "off", spellcheck: "false", "data-filter": target}));
  }

  function historyBlock(board) {
    const spec = historySpec(board);
    const label = sectionLabel(board);
    const has = spec.main.length || spec.others.length;
    const caption = spec.kind === "kings"
      ? "The king's " + label + " at each released window. A dashed line marks a new king."
      : "Each point is a released, scored submission in this era. The line is the current king's; grey points are other eligible miners.";
    const rows = spec.main.map(p => h("tr", null, h("td", {class: "num"}, block(p.x)), h("td", {class: "key"}, shortKey(p.hotkey)), h("td", {class: "num"}, fmt(p.y))));
    return section("history", {class: "block", "aria-labelledby": "hist-title"},
      h("div", {class: "block-head"}, h("h2", {id: "hist-title"}, "History"), chip("Era " + shortDigest(board.history && board.history.era), "chip-plain")),
      has ? sparkFigure(spec, caption) : h("p", {class: "empty"}, "No released windows in this rule era yet. Each rule digest is its own era; history never crosses eras."),
      rows.length ? h("details", {class: "more"}, h("summary", null, "Show the line as a table"),
        table("King history values", [["Block", "num"], ["Hotkey"], [label, "num"]], rows)) : null,
      handoverTable(board));
  }
  // Each change of king, newest first, from the validator's winner ledger. A
  // hotkey the feed does not name stays blank.
  function handoverTable(board) {
    const list = board.history && Array.isArray(board.history.handovers) ? board.history.handovers.slice().reverse() : [];
    const key = k => (k ? h("a", {href: minerHref(board.slug, k), class: "key", title: k}, shortKey(k)) : "");
    const rows = list.map(x => h("tr", null,
      h("td", null, x.utc ? utc(utcSeconds(x.utc)) : ""),
      h("td", null, key(x.to_hotkey)),
      h("td", {class: "opt"}, key(x.from_hotkey)),
      h("td", {class: "opt"}, x.kind ? words(x.kind) : ""),
      h("td", null, typeof x.eligible === "boolean" ? (x.eligible ? "eligible" : "not eligible") + (x.eligibility_reason ? ": " + words(x.eligibility_reason) : "") : "")));
    if (!rows.length) return null;
    return h("div", {class: "handovers"}, h("h3", null, "Handovers"),
      table("Handovers, newest first", [["When (UTC)"], ["New king"], ["Previous", "opt"], ["Kind", "opt"], ["Reward"]], rows));
  }

  const ENTRY_FIELDS = ["trigger_bar", "king_screening_display", "coldkeys"];
  function championshipBlock(board) {
    const c = board.championship || {};
    const ok = rulesOk(board);
    const columns = ENTRANT_COLUMNS.filter(([key]) => ok || !["guard_bar_pct", "gap_to_win_pct"].includes(key));
    const entry = c.entry || null;
    const head = h("div", {class: "block-head"}, h("h2", {id: "champ-title"}, "Championship"));
    const rounds = (Array.isArray(c.rounds) ? c.rounds : []).slice().sort((a, b) => (b.epoch ?? 0) - (a.epoch ?? 0)).map(r => {
      const entrants = Array.isArray(r.entrants) ? r.entrants : [];
      const facts = h("div", {class: "chips"},
        isNum(r.chunks_used) ? chip(r.chunks_used + " chunk" + (r.chunks_used === 1 ? "" : "s"), "chip-plain") : null,
        r.stopped ? chip(STOPS[r.stopped] || words(r.stopped), "chip-plain") : null,
        isNum(r.n_solved) ? chip(r.n_solved + " solved", "chip-plain") : null,
        ok && isNum(r.margin_pct) ? chip("margin " + fmt(r.margin_pct) + "%", "chip-plain") : null);
      const body = entrants.length
        ? table("Entrants, epoch " + r.epoch, [["Entrant"]].concat(columns.map(([, name, unit]) => [name, unit ? "num" : null])),
          entrants.map(e => h("tr", null, h("td", {class: "key", title: e.hotkey || e.coldkey || ""}, shortKey(e.hotkey || e.coldkey || "")),
            columns.map(([key, , unit]) => h("td", {class: unit ? "num" : null}, isNum(e[key]) ? fmt(e[key]) + unit : e[key] ? words(e[key]) : "")))))
        : h("p", {class: "empty-epoch"}, ok ? EMPTY_EPOCH : "no contenders");
      return h("article", {class: "card round"},
        h("div", {class: "round-head"}, h("h3", null, isNum(r.epoch) ? "Epoch " + r.epoch : "Round"), facts),
        body,
        r.new_king ? h("p", {class: "hint"}, "New king ", h("span", {class: "key"}, shortKey(r.new_king)), isNum(r.paid_from_epoch) ? ", paid from epoch " + r.paid_from_epoch : "") : null);
    });
    const entryStats = entry ? [
      ok && plain(entry.trigger_bar) !== null ? stat("Entry trigger bar", plain(entry.trigger_bar)) : null,
      plain(entry.king_screening_display) !== null ? stat("King's screening display", plain(entry.king_screening_display)) : null,
      Array.isArray(entry.coldkeys) ? stat("Entered coldkeys", String(entry.coldkeys.filter(x => x && x.entered === true).length)) : null,
    ].filter(Boolean) : [];
    return section("championship", {class: "block", "aria-labelledby": "champ-title"}, head,
      entryStats.length ? h("dl", {class: "stats compact"}, entryStats) : null,
      Array.isArray(c.rounds) && !c.rounds.length ? h("p", {class: "empty"}, "No rounds in this rule era yet.") : null,
      rounds,
      moreLine(!Array.isArray(c.rounds) || anyNull(entry, ENTRY_FIELDS)));
  }

  function gatesBlock(board) {
    const g = board.gates || {names: [], failing: {}};
    const title = g.display || "Safety gates";
    const badges = g.names.map(name => {
      const king = g.king ? g.king[name] : undefined;
      const failed = g.failing[name] || 0;
      const cls = king === "FAIL" ? "gate gate-fail" : king === "PASS" ? "gate gate-pass" : "gate";
      return h("li", {class: cls},
        h("span", {class: "gate-name"}, words(name)),
        king ? h("span", {class: "gate-king"}, "king " + String(king).toLowerCase()) : null,
        h("span", {class: "gate-count"}, failed + " of " + g.submissions_with_gates + " failed"));
    });
    return section("gates", {class: "block", "aria-labelledby": "gates-title"},
      h("div", {class: "block-head"}, h("h2", {id: "gates-title"}, title)),
      badges.length ? h("ul", {class: "gates"}, badges) : h("p", {class: "empty"}, "No gate results in this release yet."));
  }

  function feedBlock(board) {
    const f = board.freshness || {};
    const chainAge = f.basis === "as_of_block"; // the age runs from the chain time
    return section("feed", {class: "block feedinfo", "aria-label": "Feed"},
      h("dl", {class: "stats compact"},
        keyShort(board) ? stat("Signed feed", h("span", {class: "key", title: board.feed.key_id || null, "data-key-id": board.feed.key_id || null}, "key " + keyShort(board))) : null,
        stat("Feed version", String(board.version)),
        board.generated_at ? stat("Generated", board.generated_at, isNum(f.age_seconds) && !chainAge ? span(f.age_seconds) + " old when served" : null) : null,
        board.feed && board.feed.digest ? stat("Feed digest", shortDigest(board.feed.digest)) : null,
        board.as_of_block ? stat("Chain time", "block " + block(board.as_of_block.number),
          utc(utcSeconds(board.as_of_block.timestamp_utc)) + (chainAge && isNum(f.age_seconds) ? ", " + span(f.age_seconds) + " old when served" : "")) : null,
        stat("Canary miners excluded", String(board.excluded_canaries)),
        rulesOk(board) ? stat("Rules card", shortDigest(board.rules.card_digest)) : null));
  }

  // OWNER-DASHBOARD-01: a launch Challenge is graded on a sealed exam, so its board
  // shows the validator's rounded totals and counts only. Nothing finer than the
  // Ladder step, no case, target or pool; every number is the validator's.
  // One page per Challenge: the leader first, then the ladder, then the showcase.
  const LAUNCH_COUNTS = [["graded", "Graded"], ["scored", "Scored"], ["gate_failed", "Failed a gate"], ["not_scored", "Not scored"]];
  const GATE_WORDS = "A failed gate is named, never scored.";
  function launchHero(board) {
    const l = board.launch;
    return h("section", {class: "hero launch-hero", "aria-labelledby": "hero-title"},
      eyebrow("First grade"),
      h("h2", {id: "hero-title"}, "No hotkey has a graded result yet"),
      h("p", {class: "lede"}, "A score appears here the moment the validator grades a submission on the sealed exam. Totals are rounded down to the Ladder step.",
        isNum(l.baseline_total) ? " Carbon's baseline to beat: " + fmt(l.baseline_total) + (isNum(l.margin) ? " plus a margin of " + fmt(l.margin) + "." : ".") : ""),
      h("div", {class: "actions"}, h("a", {class: "btn btn-primary", href: "#/mine"}, "How to mine"), h("a", {class: "btn", href: LINKS.launchpad}, "Launchpad docs")));
  }
  function leaderCard(board) {
    const l = board.launch;
    const k = board.king;
    const digits = places([k && k.value, l.to_beat, l.margin, l.baseline_total]);
    const beat = isNum(l.to_beat) ? stat("To beat", fmt(l.to_beat, digits), isNum(l.margin) ? "the leader's total plus " + fmt(l.margin, digits) : null) : null;
    const gap = k && isNum(k.margin) ? stat("Lead over the runner-up", signed(k.margin, digits), k.runner_up ? shortKey(k.runner_up) : null) : null;
    const held = isNum(l.king_since_epoch) ? stat("Leader since", "epoch " + l.king_since_epoch) : null;
    const stats = [beat, gap, held].filter(Boolean);
    return section("leader", {class: "card leader", "aria-labelledby": "leader-title"},
      h("div", {class: "card-top"}, crown(), h("h2", {id: "leader-title", class: "card-title"}, "Current leader")),
      k ? h("p", {class: "leader-key"}, hotkey(k.hotkey, {copy: true, href: minerHref(board.slug, k.hotkey)})) : h("p", {class: "leader-key"}, "No leader yet"),
      k && isNum(k.value) ? h("div", {class: "metric leader-metric"}, h("span", {class: "metric-value"}, fmt(k.value, digits)), h("span", {class: "metric-label"}, "total score · higher is better")) : null,
      stats.length ? h("dl", {class: "stats leader-stats"}, stats) : null);
  }
  function countsStrip(board) {
    const l = board.launch;
    return h("dl", {class: "counts-strip", "aria-label": "Standing"},
      LAUNCH_COUNTS.map(([key, label]) => h("div", {class: "count-cell"}, h("dt", null, label), h("dd", null, String(l.counts[key])))));
  }
  function showcaseCard() {
    return section("showcase-teaser", {class: "card teaser", "aria-labelledby": "teaser-title"},
      eyebrow("Design showcase"),
      h("h2", {id: "teaser-title"}, "See a model drive the design optimizer"),
      h("p", {class: "lede"}, "A replay on a public task only: public cases and public reference solves, never a sealed exam or a miner's model."),
      h("div", {class: "actions"}, h("a", {class: "btn", href: "#/showcase"}, "Open the showcase")));
  }
  function miniBar(v) {
    return h("svg", {viewBox: "0 0 100 8", class: "minibar", preserveAspectRatio: "none", "aria-hidden": "true", focusable: "false"},
      h("rect", {x: 0, y: 0, width: 100, height: 8, class: "track"}),
      h("rect", {x: 0, y: 0, width: (Math.max(0, Math.min(1, v)) * 100).toFixed(1), height: 8, class: "fill"}));
  }
  function examLine(board) {
    const l = board.launch;
    return h("p", {class: "hint exam-line"}, "Exam " + l.exam_version_label + " · totals rounded down to the Ladder step · " + GATE_WORDS);
  }

  function boardPage(board, ctx) {
    const c = ctx || {now: Math.floor(Date.now() / 1000)};
    if (board.launch) {
      const pre = board.phase === "PRE_FIRST_RELEASE";
      const parts = [boardHead(board, true), boardBanners(board, c)];
      if (pre) parts.push(launchHero(board), countsStrip(board));
      else parts.push(leaderCard(board), countsStrip(board), leaderboard(board));
      parts.push(showcaseCard(), examLine(board), feedBlock(board));
      return h("div", {class: "page launch-page"}, parts);
    }
    const preRelease = board.phase === "PRE_FIRST_RELEASE" || (board.next_release && board.next_release.released_windows === 0);
    // A live board's one rules line sits in the target panel, where the bars would be.
    const out = [boardHead(board, !preRelease), boardBanners(board, c)];
    if (preRelease) {
      out.push(heroPre(board, c), scoredBlock(board), timingCard(board, c), championshipBlock(board));
    } else {
      out.push(h("div", {class: "duo"}, kingCard(board, c), targetCard(board)), timingCard(board, c), leaderboard(board),
        historyBlock(board), championshipBlock(board), gatesBlock(board), scoredBlock(board));
    }
    out.push(feedBlock(board));
    return h("div", {class: "page"}, out);
  }

  function submissionStatus(board, key) {
    const record = Array.isArray(board.miner_status) ? board.miner_status.find(r => r.hotkey === key) : null;
    if (!record || !Number.isSafeInteger(record.received) || record.received < 0
      || !Number.isSafeInteger(record.scored) || record.scored < 0
      || !record.refused || typeof record.refused !== "object" || Array.isArray(record.refused)
      || Object.values(record.refused).some(n => !Number.isSafeInteger(n) || n < 0)) return null;
    // The reader already closes these codes; keep the DOM closed as well.
    const counts = Object.entries(record.refused || {}).filter(([, n]) => Number.isSafeInteger(n) && n >= 0);
    const grouped = new Map();
    for (const [code, count] of counts) {
      const label = Object.hasOwn(REFUSALS, code) ? REFUSALS[code] : "Other";
      grouped.set(label, (grouped.get(label) || 0) + count);
    }
    const refused = Array.from(grouped.values()).reduce((sum, n) => sum + n, 0);
    if (!Number.isSafeInteger(refused)) return null;
    const rows = Array.from(grouped).filter(([, count]) => count > 0).map(([label, count]) =>
      h("tr", null, h("td", null, label), h("td", {class: "num"}, String(count))));
    return section("submission-status", {class: "card", "aria-labelledby": "status-title"},
      h("h2", {id: "status-title"}, "Submission status"),
      h("dl", {class: "stats compact"},
        stat("Received", String(record.received)), stat("Scored", String(record.scored)), stat("Refused", String(refused))),
      rows.length ? table("Refusals", [["Reason"], ["Count", "num"]], rows) : null);
  }

  function minerPage(board, key, ctx) {
    const lb = board.eligible_leaderboard;
    const entry = lb.entries.find(r => r.hotkey === key) || null;
    const coldkey = Array.isArray(lb.coldkeys) ? lb.coldkeys.find(r => r.hotkeys.includes(key)) || null : null;
    const series = (board.history.points || {})[key] || [];
    const activity = submissionStatus(board, key);
    const crumbs = h("nav", {class: "crumbs", "aria-label": "Breadcrumb"}, h("a", {href: "#/"}, "Boards"), h("span", {"aria-hidden": "true"}, "/"),
      h("a", {href: boardHref(board.slug)}, board.challenge.id), h("span", {"aria-hidden": "true"}, "/"), h("span", {"aria-current": "page"}, shortKey(key)));
    if (!entry && !coldkey && !series.length) {
      return h("div", {class: "page"}, crumbs, h("h1", {class: "key"}, shortKey(key)),
        activity,
        h("p", {class: "empty"}, "This hotkey has no released, eligible result on this board yet."), h("a", {class: "btn", href: "#/mine"}, "How to mine"));
    }
    const label = sectionLabel(board);
    const status = coldkey ? LADDER[coldkey.status] || [words(coldkey.status), "chip-muted"] : null;
    const rows = series.map(p => h("tr", null, h("td", {class: "num"}, block(p.receipt_block)), h("td", {class: "num"}, fmt(p.value))));
    return h("div", {class: "page"}, crumbs, boardBanners(board, ctx || {}),
      eyebrow("Miner"), h("h1", {class: "key"}, shortKey(key)),
      h("p", {class: "king-key"}, h("span", {class: "key full"}, key), copyButton(key, "hotkey")),
      activity,
      h("dl", {class: "stats"},
        entry ? stat("Rank", String(entry.rank)) : null,
        entry && isNum(entry.screening_value) ? stat(label, fmt(entry.screening_value)) : null,
        entry ? stat("Role", entry.is_king ? "king" : entry.challenger_state ? words(entry.challenger_state) : "eligible") : null,
        coldkey ? stat("Coldkey", h("span", {class: "key", title: coldkey.coldkey}, shortKey(coldkey.coldkey)), null) : null,
        status ? stat("Ladder status", chip(status[0], status[1])) : null),
      series.length ? sparkFigure({main: series.map(p => ({x: p.receipt_block, y: p.value})), others: [], title: label + " of this hotkey's released submissions"},
        "This hotkey's released, scored submissions in this era.") : null,
      table("Released submissions", [["Receipt block", "num"], [label, "num"]], rows),
      h("p", {class: "hint"}, "Recipes and per-case values are not shown."));
  }

  function homeCard(entry, board) {
    if (!entry.slug) return h("div", {class: "card board-card"}, eyebrow("Feed refused"), h("p", {class: "fail"}, words(entry.code)));
    const phase = board ? PHASES[board.phase] || [words(board.phase), ""] : null;
    const king = board && board.king;
    return h("a", {class: "card board-card", href: boardHref(entry.slug)},
      h("div", {class: "board-card-head"}, h("h3", null, entry.challenge.id), phase ? chip(phase[0], phase[1]) : null),
      h("div", {class: "chips"}, chip(entry.device_class || "no device class", "chip-plain"), labelsOf(entry).filter(l => l !== "DEVELOPMENT").map(l => chip(l, l === "FIXTURE" ? "chip-warn" : "chip-plain"))),
      king ? h("div", {class: "board-card-king"},
        h("span", {class: "eyebrow"}, "King"), h("span", {class: "key"}, shortKey(king.hotkey)),
        isNum(king.value) ? h("span", {class: "board-card-value"}, fmt(king.value), h("small", null, " " + sectionLabel(board))) : null)
        : board && board.phase === "PRE_FIRST_RELEASE" ? h("p", {class: "hint"}, board.launch ? "No hotkey graded yet" : "First scores after the first release") : null,
      entry.state !== "ACCEPTED" ? h("p", {class: "fail"}, "Newest feed refused: " + words(entry.code)) : null);
  }

  // S3's signed network snapshot: drawn only when the file is present.
  function networkStrip(network) {
    if (!network || typeof network !== "object" || Array.isArray(network)) return null;
    const items = NETWORK_FIELDS.filter(([key]) => plain(network[key]) !== null);
    return section("network", {class: "network-block", "aria-label": "Network"},
      items.length ? h("div", {class: "network"}, items.map(([key, name]) => h("div", {class: "net-item"}, h("span", {class: "eyebrow"}, name), h("span", {class: "net-value"}, plain(network[key]))))) : null,
      moreLine(items.length < NETWORK_FIELDS.length));
  }

  function homePage(index, boards, ctx) {
    const c = ctx || {};
    return h("div", {class: "page"},
      h("section", {class: "intro"},
        h("p", {class: "eyebrow section-label"}, "Carbon subnet"),
        h("h1", null, "Leaders by Challenge"),
        h("p", {class: "lede"}, "Each board is one Challenge on one device class, drawn from the Carbon Validator's signed score feed. CPU and GPU results are never ranked together."),
        h("div", {class: "actions"}, h("a", {class: "btn btn-primary", href: "#/mine"}, "How to mine"), h("a", {class: "btn", href: "#/showcase"}, "Design showcase"))),
      networkStrip(c.network),
      index.fixture ? h("p", {class: "notice"}, h("strong", null, "Fixture data. "), "These boards are synthetic, made to build and test the page. They are not results of any model or Challenge.") : null,
      index.boards.length ? h("div", {class: "board-grid"}, index.boards.map(e => homeCard(e, e.slug ? (boards || {})[e.slug] : null)))
        : h("p", {class: "empty"}, "No boards yet."));
  }

  function minePage() {
    const step = (n, title, body, extra) => h("li", {class: "step"}, h("span", {class: "step-n", "aria-hidden": "true"}, n), h("div", null, h("h3", null, title), h("p", null, body), extra || null));
    return h("div", {class: "page"},
      h("p", {class: "eyebrow section-label"}, "How to mine"),
      h("h1", null, "From a clean machine to your first submission"),
      h("p", {class: "lede"}, "The Launchpad sets up everything on your own machine, and any MCP agent can drive it. Carbon rents no compute and never holds your keys."),
      h("ol", {class: "steps"},
        step("1", "Start", "Clone Carbon and run the installer, then start your signer in your own terminal and open the Control Center. Register your hotkey from your own wallet.",
          h("pre", {class: "cmd"}, h("code", null, "git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon && ~/carbon/scripts/install_miner.sh"))),
        step("2", "Practice", "Run carbon_practice on public material. Practice is free and its signal is intentionally incomplete: it is never the official exam."),
        step("3", "Submit", "Freeze your candidate, commit it on chain, then submit: carbon_freeze_candidate, carbon_commit, carbon_submit."),
        step("4", "My status", "Find your hotkey or coldkey on a Challenge board once your window is released. Until then the board shows when the next release is due.")),
      h("div", {class: "actions"},
        h("a", {class: "btn btn-primary", href: LINKS.launchpad}, "Launchpad (miner MCP) docs"),
        h("a", {class: "btn", href: LINKS.journey}, "The fresh-miner journey"),
        h("a", {class: "btn", href: "#/"}, "Boards")));
  }

  function keyShort(board) {
    const key = board && board.feed && board.feed.public_key;
    return typeof key === "string" && key.length > 12 ? key.slice(0, 8) + "…" + key.slice(-4) : null;
  }
  function footerStamp(board, loadedAt) {
    if (!board) return "Verified signed feed";
    const key = keyShort(board) ? " · key " + keyShort(board) : "";
    return "Verified signed feed" + key + " · last verified " + utc(loadedAt);
  }

  const api = {sparkFigure, sectionShort, SVG_NS, LINKS, ELIGIBLE, RULES_LINE, MORE, EMPTY_EPOCH, LADDER, REFUSALS, SEALED_GRAIN, PHASES,
    KING_FIELDS, TARGET_FIELDS, RELEASE_FIELDS, ENTRY_FIELDS, NETWORK_FIELDS, keyShort, rotationText, kingMissing, guardText, POSTED,
    h, walk, textOf, mount, places, fmt, signed, block, shortKey, shortDigest, utcSeconds, utc, span, countdown, parseRoute, boardHref, minerHref, labelsOf,
    rulesOk, sectionLabel, sparkline, targetCard, historySpec, boardPage, minerPage, homePage, minePage, networkStrip, footerStamp};
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- DOM ----
  const app = document.getElementById("app");
  const cache = new Map();
  const CACHE_MS = 60000;
  let ticker = null;

  function show(tree) {
    app.replaceChildren(mount(tree, document));
    tick();
  }
  function tick() {
    const now = Date.now() / 1000;
    for (const e of app.querySelectorAll("[data-until]")) e.textContent = countdown(Number(e.getAttribute("data-until")) - now);
  }
  function setLabels(labels) {
    const box = document.getElementById("labels");
    box.replaceChildren(...labels.map(l => mount(chip(l, l === "FIXTURE" ? "chip-warn" : "chip-label"), document)));
  }
  function setStamp(text, board) {
    const e = document.getElementById("feedstamp");
    if (!e) return;
    e.textContent = text;
    const id = board && board.feed && board.feed.key_id;
    if (id) { e.setAttribute("title", id); e.setAttribute("data-key-id", id); } else { e.removeAttribute("title"); e.removeAttribute("data-key-id"); }
  }
  async function getJson(path) {
    const hit = cache.get(path);
    if (hit && Date.now() - hit.at < CACHE_MS) return hit.value;
    const response = await fetch(path, {cache: "no-cache"});
    if (!response.ok) throw new Error(path + " " + response.status);
    const value = await response.json();
    cache.set(path, {at: Date.now(), value});
    return value;
  }
  async function optional(path) { try { return await getJson(path); } catch { return null; } }
  function eraBefore(slug, era) {
    let before = null;
    try {
      before = localStorage.getItem("carbon.era." + slug);
      localStorage.setItem("carbon.era." + slug, era);
    } catch { before = null; }
    return before;
  }
  async function copy(button) {
    const value = button.getAttribute("data-copy");
    try { await navigator.clipboard.writeText(value); button.textContent = "Copied"; } catch { button.textContent = "Select and copy"; }
    setTimeout(() => { button.textContent = "Copy"; }, 1600);
  }
  app.addEventListener("click", event => {
    const button = event.target.closest && event.target.closest("[data-copy]");
    if (button) copy(button);
  });
  app.addEventListener("input", event => {
    const input = event.target;
    if (!input.hasAttribute || !input.hasAttribute("data-filter")) return;
    const query = input.value.trim().toLowerCase();
    const target = document.getElementById(input.getAttribute("data-filter"));
    if (!target) return;
    for (const row of target.querySelectorAll("tbody tr")) row.hidden = !!query && !row.getAttribute("data-find").includes(query);
  });

  async function render() {
    try {
      app.setAttribute("aria-busy", "true");
      const index = await getJson("data/index.json");
      const route = parseRoute(location.hash);
      for (const a of document.querySelectorAll(".topnav a")) {
        const current = a.dataset.view === (route.view === "miner" ? "board" : route.view === "home" ? "board" : route.view);
        if (current) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      }
      const now = Math.floor(Date.now() / 1000);
      document.title = "Carbon Leaderboard";
      if (route.view === "showcase") {
        if (!root.CarbonShowcase) throw new Error("showcase unavailable");
        setStamp("Verified signed feed");
        return await root.CarbonShowcase.render(app, route, getJson, setLabels);
      }
      if (route.view === "mine") { setLabels(["DEVELOPMENT"]); setStamp("Verified signed feed"); return show(minePage()); }
      if (route.view === "home") {
        const boards = {};
        await Promise.all(index.boards.filter(b => b.slug).map(async b => { boards[b.slug] = await optional("data/v2/" + encodeURIComponent(b.slug) + ".json"); }));
        setLabels(index.fixture ? ["DEVELOPMENT", "FIXTURE"] : ["DEVELOPMENT"]);
        const first = Object.values(boards).find(Boolean);
        setStamp(footerStamp(first, now), first);
        // Fetched only when the index says a signed snapshot exists (S3).
        const network = index.network === true ? await optional("data/network.json") : null;
        return show(homePage(index, boards, {now, network}));
      }
      const entry = index.boards.find(b => b.slug === route.slug);
      if (!entry) return show(h("p", {class: "notice"}, "No such board. ", h("a", {href: "#/"}, "All boards")));
      const board = await getJson("data/v2/" + encodeURIComponent(route.slug) + ".json");
      board.feed_state = board.feed_state || {state: entry.state, code: entry.code};
      setLabels(labelsOf(board));
      setStamp(footerStamp(board, now), board);
      const ctx = {now, eraBefore: route.view === "board" ? eraBefore(board.slug, board.era) : null};
      document.title = board.challenge.id + " · " + document.title;
      return show(route.view === "miner" ? minerPage(board, route.hotkey, ctx) : boardPage(board, ctx));
    } catch (error) {
      show(h("p", {class: "notice"}, h("strong", null, "Feed unavailable. "), String(error.message || error)));
    } finally {
      app.removeAttribute("aria-busy");
    }
  }
  // Light and dark themes: the stored choice, else the system's (style.css).
  const themeRoot = document.documentElement;
  function storedTheme() { try { const t = localStorage.getItem("carbon.theme"); return t === "light" || t === "dark" ? t : null; } catch { return null; } }
  function systemDark() { return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches); }
  function paintTheme(forced) {
    const chosen = forced || storedTheme();
    if (chosen) themeRoot.setAttribute("data-theme", chosen); else themeRoot.removeAttribute("data-theme");
    const button = document.getElementById("theme");
    if (button) { const dark = (chosen || (systemDark() ? "dark" : "light")) === "dark"; button.setAttribute("aria-pressed", dark ? "true" : "false"); button.textContent = dark ? "Light" : "Dark"; }
  }
  const themeButton = document.getElementById("theme");
  if (themeButton) themeButton.addEventListener("click", () => {
    const next = (themeRoot.getAttribute("data-theme") || (systemDark() ? "dark" : "light")) === "dark" ? "light" : "dark";
    try { localStorage.setItem("carbon.theme", next); } catch { /* the choice then lasts for this view only */ }
    paintTheme(next);
  });
  paintTheme();
  window.addEventListener("hashchange", () => { render().then(() => { window.scrollTo(0, 0); app.focus({preventScroll: true}); }); });
  if (!ticker) ticker = setInterval(tick, 1000);
  render();
})(typeof globalThis !== "undefined" ? globalThis : this);
