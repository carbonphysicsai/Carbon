"use strict";
// Carbon Leaderboard (DASHBOARD-02 S2): the per-Challenge pages, drawn from
// board.v2 (`data/v2/<slug>.json`, carbon/dashboard/board_v2.py).
//
// The page renders board.v2 fields only. It computes no rank, king, margin,
// target or rule value of its own: every number is copied as the board gives
// it, and a null is shown with its reason ("to be announced", "not yet
// published", "rules unavailable"). Rule statements appear only while the
// rules card's status is OK. No per-case, input or prediction value is drawn.
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
  const TBA = "to be announced";
  const UNPUBLISHED = "not yet published";
  const RULES_UNAVAILABLE = "rules unavailable";
  const CHAMPIONSHIP_PENDING = "Championship results: not yet published";
  const EMPTY_EPOCH = "no contenders: king paid";
  const TIMING_UNAVAILABLE = "timing unavailable";
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
  const REASONS = {
    not_in_feed: UNPUBLISHED,
    no_released_incumbent: "no king yet",
    no_standing: "no eligible entries yet",
    ranking_section_ambiguous: "ranking section not stated",
    no_ranking_section: "ranking section not stated",
    no_runner_up: "no runner-up yet",
    not_a_challenger: "",
    generated_at_unparseable: "feed time unreadable",
    rules_unavailable: RULES_UNAVAILABLE,
    rules_digest_mismatch: RULES_UNAVAILABLE + " (the rules card does not match this rule)",
    sealed_until_grain: "sealed until the grain is posted",
    grain_human_input: TBA,
  };
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
  function reason(obj, key) {
    const code = obj && obj.reasons ? obj.reasons[key] : undefined;
    if (code === undefined) return UNPUBLISHED;
    return code in REASONS ? REASONS[code] : words(code);
  }
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
  function pending(text) { return h("span", {class: "pending"}, text); }
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
    if (Array.isArray(hist.kings) && hist.kings.length) {
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
  function boardBanners(board, ctx) {
    const out = [];
    if (board.feed_state && board.feed_state.state === "REFUSED") {
      out.push(h("div", {class: "alert", role: "alert"}, h("strong", null, "Newest feed refused (" + words(board.feed_state.code) + "). "),
        "Showing the last accepted version."));
    }
    if (board.phase === "STALE") {
      const age = board.freshness && board.freshness.age_seconds;
      const after = board.freshness && board.freshness.stale_after_seconds;
      out.push(h("div", {class: "alert", role: "alert"}, h("strong", null, "Stale feed. "),
        isNum(age) ? "The feed was generated " + span(age) + " ago" : "The feed's time is " + reason(board.freshness, "age_seconds"),
        isNum(after) ? " (stale after " + span(after) + "). " : ". ", "Values may be out of date."));
    }
    if (ctx.eraBefore && ctx.eraBefore !== board.era) {
      out.push(h("div", {class: "alert alert-era", role: "note"}, h("strong", null, "New rule era. "),
        "This board moved from rule " + shortDigest(ctx.eraBefore) + " to " + shortDigest(board.era) + " since your last visit. History starts fresh in each era."));
    }
    return out;
  }

  function boardHead(board) {
    const phase = PHASES[board.phase] || [words(board.phase), ""];
    const ok = rulesOk(board);
    return h("header", {class: "board-head"},
      h("nav", {class: "crumbs", "aria-label": "Breadcrumb"}, h("a", {href: "#/"}, "Boards"), h("span", {"aria-hidden": "true"}, "/"), h("span", {"aria-current": "page"}, board.challenge.id)),
      h("h1", null, board.challenge.id),
      h("div", {class: "chips"},
        chip(phase[0], phase[1]),
        chip(board.device_class || "no device class", "chip-plain"),
        chip("Era " + shortDigest(board.era), "chip-plain"),
        ok && board.challenge.rule ? chip("Rule " + board.challenge.rule, "chip-plain") : chip(reason(board.challenge, "rule"), "chip-muted"),
        chip("Version " + board.challenge.version, "chip-plain")));
  }

  function heroPre(board, ctx) {
    const lag = board.next_release && board.next_release.lag;
    const ok = rulesOk(board) && lag && isNum(lag.hours);
    const when = timingOf(board.next_release, ctx) || timingOf(board.next_round, ctx);
    return h("section", {class: "hero", "aria-labelledby": "hero-title"},
      eyebrow("First release"),
      h("h2", {id: "hero-title"}, ok ? "First scores publish ~" + Math.round(lag.hours) + " h after the first round" : "First scores publish after the first round is released"),
      h("p", {class: "lede"}, "No window of this rule era has been released yet, so no score is shown. ",
        ok ? "" : "Release lag: " + reason(board.next_release, "lag") + "."),
      when ? h("div", {class: "hero-count"}, when) : h("p", {class: "hint"}, "Next release: " + TIMING_UNAVAILABLE),
      h("div", {class: "actions"}, h("a", {class: "btn btn-primary", href: "#/mine"}, "How to mine"), h("a", {class: "btn", href: LINKS.launchpad}, "Launchpad docs")));
  }

  function kingCard(board, ctx) {
    const k = board.king;
    const label = sectionLabel(board);
    if (!k) {
      return h("section", {class: "card king", "aria-labelledby": "king-title"},
        h("div", {class: "card-top"}, crown(), h("h2", {id: "king-title", class: "card-title"}, "King")),
        h("p", {class: "empty"}, "No king yet: " + reason(board, "king") + "."));
    }
    const digits = places([k.value, k.margin]);
    let held;
    const since = utcSeconds(k.since_utc);
    if (since !== null) held = stat("Held for", span(ctx.now - since), "since " + utc(since));
    else if (isNum(k.since_block)) held = stat("Held since", "block " + block(k.since_block), isNum(k.crowned_epoch) ? "crowned in epoch " + k.crowned_epoch : "duration " + UNPUBLISHED);
    else held = stat("Held since", pending(reason(k, "since_block")));
    let margin;
    if (isNum(k.margin)) {
      margin = stat("Margin over runner-up", signed(k.margin, digits), k.runner_up ? "runner-up " + shortKey(k.runner_up) : null);
    } else margin = stat("Margin over runner-up", pending(reason(k, "margin")));
    return h("section", {class: "card king", "aria-labelledby": "king-title"},
      h("div", {class: "card-top"}, crown(), h("h2", {id: "king-title", class: "card-title"}, "King"),
        isNum(k.uid) ? chip("UID " + k.uid, "chip-plain") : null,
        k.challenger_state ? chip(words(k.challenger_state), "chip-muted") : null),
      h("p", {class: "king-key"}, hotkey(k.hotkey, {copy: true, href: minerHref(board.slug, k.hotkey)})),
      h("div", {class: "metric"},
        h("span", {class: "metric-value"}, isNum(k.value) ? fmt(k.value, digits) : "—"),
        h("span", {class: "metric-label"}, label)),
      h("dl", {class: "stats"},
        margin,
        stat("Share now", isNum(k.share_now) ? fmt(k.share_now) : pending(reason(k, "share_now"))),
        stat("Next halving", isNum(k.next_halving_epoch) ? "epoch " + k.next_halving_epoch : pending(reason(k, "next_halving_epoch"))),
        held,
        stat("Defences", isNum(k.defences) ? String(k.defences) : pending(reason(k, "defences")))));
  }

  function targetCard(board) {
    const t = board.target_to_beat || {reasons: {}};
    const bar = (name, key, note) => {
      const value = plain(t[key]);
      return h("li", {class: "bar-row" + (value === null ? " is-pending" : "")},
        h("span", {class: "bar-name"}, name),
        h("span", {class: "bar-value"}, value === null ? TBA : value),
        h("span", {class: "bar-note"}, note));
    };
    const value = plain(t.value);
    return h("section", {class: "card target", "aria-labelledby": "target-title"},
      h("div", {class: "card-top"}, h("h2", {id: "target-title", class: "card-title"}, "Target to beat")),
      h("div", {class: "metric"}, h("span", {class: "metric-value" + (value === null ? " is-pending" : "")}, value === null ? TBA : value),
        h("span", {class: "metric-label"}, sectionLabel(board))),
      h("ul", {class: "bars", "aria-label": "Both bars"},
        bar("Posted margin", "posted_margin", "the margin the rule posts"),
        bar("Noise guard", "noise_guard", "the comparison's noise guard")),
      h("p", {class: "hint"}, "Both bars come from the Validator's rules card. Until it publishes them, they are " + TBA + "."));
  }

  function timingOf(part, ctx) {
    if (!part) return null;
    const at = utcSeconds(part.next_utc);
    if (at !== null) {
      return h("span", {class: "count"},
        h("span", {class: "count-value", "data-until": at, "aria-live": "off"}, countdown(at - ctx.now)),
        h("span", {class: "count-note"}, utc(at)));
    }
    if (isNum(part.next_block)) return h("span", {class: "count"}, h("span", {class: "count-value"}, "block " + block(part.next_block)), h("span", {class: "count-note"}, "countdown needs a published time"));
    return null;
  }
  function timingCard(board, ctx) {
    const round = board.next_round || {}, release = board.next_release || {};
    const every = round.every;
    const lag = release.lag;
    const ok = rulesOk(board);
    return h("section", {class: "timing", "aria-label": "Next round and release"},
      h("div", {class: "card tick"}, eyebrow("Next round"), timingOf(round, ctx) || h("p", {class: "count-value is-pending"}, TIMING_UNAVAILABLE),
        h("p", {class: "hint"}, ok && every ? "Every " + every.blocks.toLocaleString("en-US") + " blocks (~" + every.hours + " h)" : "Round period: " + reason(round, "every"))),
      h("div", {class: "card tick"}, eyebrow("Next release"), timingOf(release, ctx) || h("p", {class: "count-value is-pending"}, TIMING_UNAVAILABLE),
        h("p", {class: "hint"}, release.released_windows + " released window" + (release.released_windows === 1 ? "" : "s") + " in this era. ",
          ok && lag ? "Release lag " + lag.blocks.toLocaleString("en-US") + " blocks (~" + Math.round(lag.hours) + " h)." : "Release lag: " + reason(release, "lag") + ".")));
  }

  function lagNote(board) {
    const lb = board.eligible_leaderboard;
    if (rulesOk(board) && lb.release_lag && isNum(lb.release_lag.hours)) return "Scores publish about " + Math.round(lb.release_lag.hours) + " h after a window.";
    return "Release lag: " + reason(lb, "release_lag") + ".";
  }

  function leaderboard(board) {
    const lb = board.eligible_leaderboard;
    const label = sectionLabel(board);
    const king = board.king && board.king.hotkey;
    const parts = [];
    const notes = [lagNote(board)];
    if (isNum(lb.grain_pct)) notes.push("Grain " + fmt(lb.grain_pct) + "%.");
    else if (Array.isArray(lb.coldkeys)) notes.push("Grain: " + reason(lb, "grain_pct") + ".");
    notes.unshift("Ranked by " + label + ".");
    parts.push(h("p", {class: "hint"}, notes.join(" ")));
    if (Array.isArray(lb.coldkeys) && lb.coldkeys.length) {
      const digits = places(lb.coldkeys.map(r => r.displayed_score));
      const rows = lb.coldkeys.map(r => {
        const status = LADDER[r.status] || [words(r.status), "chip-muted"];
        const hasKing = r.hotkeys.includes(king);
        return h("tr", {"data-find": [r.coldkey].concat(r.hotkeys).join(" ").toLowerCase(), class: hasKing ? "is-king" : null},
          h("td", {class: "num rank"}, isNum(r.rank) ? r.rank : "—"),
          h("td", null, h("span", {class: "key", title: r.coldkey}, shortKey(r.coldkey)), hasKing ? h("span", {class: "crown-tag"}, "king") : null),
          h("td", {class: "num"}, isNum(r.displayed_score) ? fmt(r.displayed_score, digits) : pending("sealed")),
          h("td", null, chip(status[0], status[1])),
          h("td", {class: "opt"}, h("details", {class: "hotkeys"}, h("summary", null, r.hotkeys.length + " hotkey" + (r.hotkeys.length === 1 ? "" : "s")),
            h("ul", null, r.hotkeys.map(k => h("li", null, h("a", {href: minerHref(board.slug, k), class: "key", title: k}, shortKey(k)), k === king ? h("span", {class: "crown-tag"}, "king") : null))))));
      });
      parts.push(finder("ladder"), table(ELIGIBLE + ", per coldkey",
        [["Rank", "num"], ["Coldkey"], ["Displayed", "num"], ["Status"], ["Hotkeys", "opt"]], rows, {id: "ladder"}));
      parts.push(h("p", {class: "hint"}, "One pooled displayed score per coldkey; its hotkeys are listed for information."));
    } else if (lb.entries.length) {
      const digits = places(lb.entries.map(r => r.screening_value));
      const rows = lb.entries.map(r => h("tr", {"data-find": String(r.hotkey).toLowerCase(), class: r.is_king ? "is-king" : null},
        h("td", {class: "num rank"}, r.rank),
        h("td", null, h("a", {href: minerHref(board.slug, r.hotkey), class: "key", title: r.hotkey}, shortKey(r.hotkey)), r.is_king ? h("span", {class: "crown-tag"}, "king") : null,
          isNum(r.uid) ? h("span", {class: "uid"}, "UID " + r.uid) : null),
        h("td", {class: "num"}, isNum(r.screening_value) ? fmt(r.screening_value, digits) : pending(reason(r, "screening_value"))),
        h("td", {class: "num opt"}, block(r.best_at_block)),
        h("td", {class: "opt"}, r.challenger_state ? chip(words(r.challenger_state), "chip-muted") : "")));
      parts.push(finder("ladder"), table(ELIGIBLE + ", per hotkey", [["Rank", "num"], ["Hotkey"], [sectionShort(board), "num"], ["Best at block", "num opt"], ["Challenge", "opt"]], rows, {id: "ladder"}));
    } else {
      parts.push(h("p", {class: "empty"}, "No eligible entries in this release yet."));
    }
    return h("section", {class: "block", "aria-labelledby": "lb-title"},
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
      : "Each point is a released, scored submission in this era. The line is the current king's; grey points are other eligible miners. The full king history is " + UNPUBLISHED + ".";
    const rows = spec.main.map(p => h("tr", null, h("td", {class: "num"}, block(p.x)), h("td", {class: "key"}, shortKey(p.hotkey)), h("td", {class: "num"}, fmt(p.y))));
    return h("section", {class: "block", "aria-labelledby": "hist-title"},
      h("div", {class: "block-head"}, h("h2", {id: "hist-title"}, "History"), chip("Era " + shortDigest(board.history && board.history.era), "chip-plain")),
      has ? sparkFigure(spec, caption) : h("p", {class: "empty"}, "No released windows in this rule era yet. Each rule digest is its own era; history never crosses eras."),
      rows.length ? h("details", {class: "more"}, h("summary", null, "Show the line as a table"),
        table("King history values", [["Block", "num"], ["Hotkey"], [label, "num"]], rows)) : null);
  }

  function championshipBlock(board) {
    const c = board.championship || {reasons: {}};
    const head = h("div", {class: "block-head"}, h("h2", {id: "champ-title"}, "Championship"));
    if (!Array.isArray(c.rounds)) {
      return h("section", {class: "block", "aria-labelledby": "champ-title"}, head,
        h("div", {class: "card quiet"}, h("p", {class: "quiet-title"}, CHAMPIONSHIP_PENDING), entryBlock(c.entry)));
    }
    if (!c.rounds.length) {
      return h("section", {class: "block", "aria-labelledby": "champ-title"}, head, h("p", {class: "empty"}, "No rounds in this rule era yet."), entryBlock(c.entry));
    }
    const rounds = c.rounds.slice().sort((a, b) => (b.epoch ?? 0) - (a.epoch ?? 0)).map(r => {
      const entrants = Array.isArray(r.entrants) ? r.entrants : [];
      const facts = h("div", {class: "chips"},
        isNum(r.chunks_used) ? chip(r.chunks_used + " chunk" + (r.chunks_used === 1 ? "" : "s"), "chip-plain") : null,
        r.stopped ? chip(STOPS[r.stopped] || words(r.stopped), "chip-plain") : null,
        isNum(r.n_solved) ? chip(r.n_solved + " solved", "chip-plain") : null,
        isNum(r.margin_pct) ? chip("margin " + fmt(r.margin_pct) + "%", "chip-plain") : null);
      const body = entrants.length
        ? table("Entrants, epoch " + r.epoch, [["Entrant"]].concat(ENTRANT_COLUMNS.map(([, name, unit]) => [name, unit ? "num" : null])),
          entrants.map(e => h("tr", null, h("td", {class: "key", title: e.hotkey || e.coldkey || ""}, shortKey(e.hotkey || e.coldkey || "—")),
            ENTRANT_COLUMNS.map(([key, , unit]) => h("td", {class: unit ? "num" : null}, isNum(e[key]) ? fmt(e[key]) + unit : e[key] ? words(e[key]) : "—")))))
        : h("p", {class: "empty-epoch"}, EMPTY_EPOCH);
      return h("article", {class: "card round"},
        h("div", {class: "round-head"}, h("h3", null, "Epoch " + (r.epoch ?? "—")), facts),
        body,
        r.new_king ? h("p", {class: "hint"}, "New king ", h("span", {class: "key"}, shortKey(r.new_king)), isNum(r.paid_from_epoch) ? ", paid from epoch " + r.paid_from_epoch : "") : null);
    });
    return h("section", {class: "block", "aria-labelledby": "champ-title"}, head, entryBlock(c.entry), rounds);
  }
  function entryBlock(entry) {
    if (!entry) return null;
    return h("dl", {class: "stats compact"},
      stat("Entry trigger bar", plain(entry.trigger_bar) ?? pending(reason(entry, "trigger_bar"))),
      stat("King's screening display", plain(entry.king_screening_display) ?? pending(reason(entry, "king_screening_display"))),
      stat("Entered coldkeys", Array.isArray(entry.coldkeys) ? String(entry.coldkeys.filter(x => x && x.entered === true).length) : pending(reason(entry, "coldkeys"))));
  }

  function gatesBlock(board) {
    const g = board.gates || {names: [], failing: {}, reasons: {}};
    const title = g.display || "Safety gates";
    const badges = g.names.map(name => {
      const king = g.king ? g.king[name] : undefined;
      const failed = g.failing[name] || 0;
      const cls = king === "FAIL" ? "gate gate-fail" : king === "PASS" ? "gate gate-pass" : "gate";
      return h("li", {class: cls},
        h("span", {class: "gate-name"}, words(name)),
        h("span", {class: "gate-king"}, king ? "king " + String(king).toLowerCase() : "king —"),
        h("span", {class: "gate-count"}, failed + " of " + g.submissions_with_gates + " failed"));
    });
    return h("section", {class: "block", "aria-labelledby": "gates-title"},
      h("div", {class: "block-head"}, h("h2", {id: "gates-title"}, title)),
      badges.length ? h("ul", {class: "gates"}, badges) : h("p", {class: "empty"}, "No gate results in this release yet."),
      h("p", {class: "hint"}, "A failed gate is never offset by a better score on another section."));
  }

  function feedBlock(board) {
    const f = board.freshness || {};
    return h("section", {class: "block feedinfo", "aria-label": "Feed"},
      h("dl", {class: "stats compact"},
        stat("Signed feed", "key " + (board.feed && board.feed.key_id || "—")),
        stat("Feed version", String(board.version)),
        stat("Generated", board.generated_at || reason(board, "generated_at"), isNum(f.age_seconds) ? span(f.age_seconds) + " old when served" : null),
        stat("Feed digest", shortDigest(board.feed && board.feed.digest)),
        stat("Canary miners excluded", String(board.excluded_canaries)),
        stat("Rules card", board.rules ? words(board.rules.status) : RULES_UNAVAILABLE)));
  }

  function boardPage(board, ctx) {
    const c = ctx || {now: Math.floor(Date.now() / 1000)};
    const preRelease = board.phase === "PRE_FIRST_RELEASE" || (board.next_release && board.next_release.released_windows === 0);
    const out = [boardHead(board), boardBanners(board, c)];
    if (preRelease) {
      out.push(heroPre(board, c), timingCard(board, c), championshipBlock(board), gatesBlock(board));
    } else {
      out.push(h("div", {class: "duo"}, kingCard(board, c), targetCard(board)), timingCard(board, c), leaderboard(board),
        historyBlock(board), championshipBlock(board), gatesBlock(board));
    }
    out.push(feedBlock(board));
    return h("div", {class: "page"}, out);
  }

  function minerPage(board, key, ctx) {
    const lb = board.eligible_leaderboard;
    const entry = lb.entries.find(r => r.hotkey === key) || null;
    const coldkey = Array.isArray(lb.coldkeys) ? lb.coldkeys.find(r => r.hotkeys.includes(key)) || null : null;
    const series = (board.history.points || {})[key] || [];
    const crumbs = h("nav", {class: "crumbs", "aria-label": "Breadcrumb"}, h("a", {href: "#/"}, "Boards"), h("span", {"aria-hidden": "true"}, "/"),
      h("a", {href: boardHref(board.slug)}, board.challenge.id), h("span", {"aria-hidden": "true"}, "/"), h("span", {"aria-current": "page"}, shortKey(key)));
    if (!entry && !coldkey && !series.length) {
      return h("div", {class: "page"}, crumbs, h("h1", {class: "key"}, shortKey(key)),
        h("p", {class: "empty"}, "This hotkey has no released, eligible result on this board yet."), h("a", {class: "btn", href: "#/mine"}, "How to mine"));
    }
    const label = sectionLabel(board);
    const status = coldkey ? LADDER[coldkey.status] || [words(coldkey.status), "chip-muted"] : null;
    const rows = series.map(p => h("tr", null, h("td", {class: "num"}, block(p.receipt_block)), h("td", {class: "num"}, fmt(p.value))));
    return h("div", {class: "page"}, crumbs, boardBanners(board, ctx || {}),
      eyebrow("Miner"), h("h1", {class: "key"}, shortKey(key)),
      h("p", {class: "king-key"}, h("span", {class: "key full"}, key), copyButton(key, "hotkey")),
      h("dl", {class: "stats"},
        stat("Rank", entry ? String(entry.rank) : "—"),
        stat(label, entry && isNum(entry.screening_value) ? fmt(entry.screening_value) : "—"),
        stat("Role", entry && entry.is_king ? "king" : entry && entry.challenger_state ? words(entry.challenger_state) : "eligible"),
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
        : h("p", {class: "hint"}, board && board.phase === "PRE_FIRST_RELEASE" ? "First scores after the first release" : "No king yet"),
      entry.state !== "ACCEPTED" ? h("p", {class: "fail"}, "Newest feed refused: " + words(entry.code)) : null);
  }

  function networkStrip(network) {
    if (!network || typeof network !== "object") return null;
    const items = NETWORK_FIELDS.filter(([key]) => plain(network[key]) !== null);
    if (!items.length) return null;
    return h("section", {class: "network", "aria-label": "Network"},
      items.map(([key, name]) => h("div", {class: "net-item"}, h("span", {class: "eyebrow"}, name), h("span", {class: "net-value"}, plain(network[key])))));
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

  function footerStamp(board, loadedAt) {
    if (!board) return "Verified signed feed";
    return "Verified signed feed · key " + (board.feed && board.feed.key_id ? board.feed.key_id.replace(/^feed-/, "").slice(0, 8) : "—") + " · last verified " + utc(loadedAt);
  }

  const api = {sparkFigure, sectionShort, SVG_NS, LINKS, ELIGIBLE, TBA, UNPUBLISHED, RULES_UNAVAILABLE, CHAMPIONSHIP_PENDING, EMPTY_EPOCH, TIMING_UNAVAILABLE, LADDER, PHASES,
    h, walk, textOf, mount, places, fmt, signed, shortKey, shortDigest, utcSeconds, utc, span, countdown, parseRoute, boardHref, minerHref, labelsOf,
    rulesOk, sectionLabel, sparkline, historySpec, boardPage, minerPage, homePage, minePage, networkStrip, footerStamp};
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
  function setStamp(text) { const e = document.getElementById("feedstamp"); if (e) e.textContent = text; }
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
        setStamp(footerStamp(first, now));
        return show(homePage(index, boards, {now, network: await optional("data/network.json")}));
      }
      const entry = index.boards.find(b => b.slug === route.slug);
      if (!entry) return show(h("p", {class: "notice"}, "No such board. ", h("a", {href: "#/"}, "All boards")));
      const board = await getJson("data/v2/" + encodeURIComponent(route.slug) + ".json");
      board.feed_state = board.feed_state || {state: entry.state, code: entry.code};
      setLabels(labelsOf(board));
      setStamp(footerStamp(board, now));
      const ctx = {now, eraBefore: route.view === "board" ? eraBefore(board.slug, board.era) : null};
      document.title = board.challenge.id + " · " + document.title;
      return show(route.view === "miner" ? minerPage(board, route.hotkey, ctx) : boardPage(board, ctx));
    } catch (error) {
      show(h("p", {class: "notice"}, h("strong", null, "Feed unavailable. "), String(error.message || error)));
    } finally {
      app.removeAttribute("aria-busy");
    }
  }
  window.addEventListener("hashchange", () => { render().then(() => { window.scrollTo(0, 0); app.focus({preventScroll: true}); }); });
  if (!ticker) ticker = setInterval(tick, 1000);
  render();
})(typeof globalThis !== "undefined" ? globalThis : this);
