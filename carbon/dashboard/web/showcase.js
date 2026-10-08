"use strict";
// Carbon design showcase (DASHBOARD-01, slice D2).
//
// Replays a precomputed run (carbon/dashboard/showcase.py): a model drives
// Carbon's registered design optimizer on a public EV4 decision, step by step,
// beside the reference solver's truth. The page shows where the model is
// wrong: every prediction is drawn next to the solver's value, a predicted-safe
// design the solver says breaks a limit is a safety miss, and a false-feasible
// pick is never priced as regret. Nothing runs a model here; the page replays.
//
// Every string is set as text. Pure functions are exported for the Node check
// (tests/cpu/showcase_check.cjs); the DOM part runs only in a browser.
(function (root) {
  const RAMP = ["#1c5cab", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]; // fastest (darkest) to slowest
  const OUTCOMES = {
    SELECTED_FEASIBLE: ["Picked a safe design", ""],
    SELECTED_INFEASIBLE: ["False-feasible pick: the solver says this design breaks a limit", "Counted as a safety failure, never priced as regret."],
    SELECTED_UNRESOLVED: ["Picked a design the solver cannot resolve", "Its reference value sits inside the uncertainty band of a limit."],
    MISSED_OPPORTUNITY: ["Abstained, but a safe design exists", ""],
    CORRECT_ABSTENTION: ["Correctly abstained: no design in this bank is safe", ""],
    ABSTENTION_UNRESOLVED: ["Abstained; the solver could not resolve every design", ""],
  };

  function num(value, digits) {
    return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
  }
  function signed(value, digits) {
    if (typeof value !== "number" || !Number.isFinite(value)) return "—";
    return (value > 0 ? "+" : value < 0 ? "−" : "±") + Math.abs(value).toFixed(digits);
  }
  function actionText(action) { return `c1 = ${action.c1} C · c2 = ${action.c2} C`; }
  function verdictText(view) {
    if (!view) return "no value";
    return view.feasible === true ? "meets every limit" : view.feasible === false ? "breaks a limit" : "unresolved";
  }

  // Quantile bins of the solver's time over safe designs: 0 is fastest.
  function rampBins(doc) {
    const times = doc.bank.filter(c => c.truth && c.truth.feasible === true && c.truth.reached)
      .map(c => c.truth.time_to_cv_onset_s).sort((a, b) => a - b);
    return function bin(time) {
      if (!times.length || typeof time !== "number") return null;
      const rank = times.filter(t => t < time).length / times.length;
      return Math.min(RAMP.length - 1, Math.floor(rank * RAMP.length));
    };
  }

  const QUANTITIES = [
    ["time_to_cv_onset_s", "Time to CV onset", "s", 0],
    ["plating_margin_v", "Plating margin", "V", 4],
    ["peak_temperature_c", "Peak temperature", "°C", 2],
  ];

  function stepView(doc, index) {
    const step = doc.steps[index];
    const rows = QUANTITIES.map(([key, name, unit, digits]) => {
      const p = step.predicted, t = step.truth;
      const pv = p ? (key === "time_to_cv_onset_s" && !p.reached ? null : p[key]) : null;
      const tv = t ? (key === "time_to_cv_onset_s" && !t.reached ? null : t[key]) : null;
      const pText = p && key === "time_to_cv_onset_s" && !p.reached ? "not reached" : num(pv, digits);
      const tText = t && key === "time_to_cv_onset_s" && !t.reached ? "not reached" : num(tv, digits);
      const error = typeof pv === "number" && typeof tv === "number" ? pv - tv : null;
      return {key, name, unit, predicted: pText, truth: tText, error: signed(error, digits)};
    });
    return {
      number: step.step,
      total: doc.steps.length,
      candidate: step.candidate,
      action: actionText(step.action),
      rows,
      predictedVerdict: step.model_failed ? "model gave no answer" : verdictText(step.predicted),
      truthVerdict: step.truth ? verdictText(step.truth) : "reference unavailable",
      safetyMiss: step.safety_miss,
      runningPick: step.running_pick,
    };
  }

  function resultView(doc) {
    const r = doc.result;
    const [title, note] = OUTCOMES[r.kind] || [r.kind, ""];
    const action = id => { const c = doc.bank.find(b => b.candidate === id); return c ? actionText(c.action) : "none"; };
    let regret;
    if (r.kind === "SELECTED_FEASIBLE") {
      regret = r.regret_s === null
        ? "Regret not defined: the solver could not resolve every design in the bank."
        : r.regret_s === 0 ? "Regret 0 s: the pick is the solver's best in the bank."
          : `Regret ${num(r.regret_s, 0)} s slower than the best, ${num(r.regret_buyer_units, 2)} × the ${doc.units.regret_buyer_unit}.`;
    } else regret = "No regret is priced for this outcome.";
    return {
      kind: r.kind, title, note, regret,
      pick: r.selected ? action(r.selected) : "abstained",
      best: r.best ? action(r.best) : r.reference_state === "NONE_FEASIBLE" ? "no safe design" : "not resolved",
      falseFeasible: r.false_feasible,
      safetyMisses: r.safety_misses,
      queries: `${doc.optimizer.accounting.attempted_queries} of ${doc.optimizer.query_budget} model queries`,
    };
  }

  function node(tag, attrs, children, text) {
    return {tag, attrs: attrs || {}, children: children || [], text: text === undefined ? null : String(text)};
  }

  // The (c1, c2) grid after `upto` steps; `reveal` shows the solver's surface.
  function gridLayout(doc, upto, reveal) {
    const c1s = doc.grid.c1, c2s = doc.grid.c2;
    const L = 64, T = 12, R = 12, B = 52, CW = 64, CH = 56;
    const W = L + c1s.length * CW + R, H = T + c2s.length * CH + B;
    const x = c1 => L + c1s.indexOf(c1) * CW, y = c2 => T + (c2s.length - 1 - c2s.indexOf(c2)) * CH;
    const svg = node("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Design grid: first-stage rate across, second-stage rate up"});
    svg.children.push(node("defs", {}, [node("pattern", {id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)"},
      [node("rect", {width: 6, height: 6, class: "hatch-bg"}), node("line", {x1: 0, y1: 0, x2: 0, y2: 6, class: "hatch-line"})])]));
    const bin = rampBins(doc);
    const shown = doc.steps.slice(0, upto);
    const firstVisit = new Map();
    shown.forEach(s => { if (!firstVisit.has(s.candidate)) firstVisit.set(s.candidate, s.step); });
    for (const cell of doc.bank) {
      const cx = x(cell.action.c1), cy = y(cell.action.c2);
      let cls = "cell unknown", mark = "";
      if (reveal) {
        const t = cell.truth;
        if (!t) { cls = "cell unavailable"; mark = "–"; }
        else if (t.feasible === false) cls = "cell infeasible";
        else if (t.feasible === null) { cls = "cell unresolved"; mark = "?"; }
        else cls = "cell safe ramp-" + bin(t.time_to_cv_onset_s);
      } else if (firstVisit.has(cell.candidate)) cls = "cell visited";
      svg.children.push(node("rect", {x: cx + 2, y: cy + 2, width: CW - 4, height: CH - 4, class: cls, "data-candidate": cell.candidate}));
      if (firstVisit.has(cell.candidate)) svg.children.push(node("text", {x: cx + 8, y: cy + 18, class: "cell-step"}, [], firstVisit.get(cell.candidate)));
      if (mark) svg.children.push(node("text", {x: cx + CW / 2, y: cy + CH / 2 + 5, "text-anchor": "middle", class: "cell-mark"}, [], mark));
    }
    const centre = s => [x(s.action.c1) + CW / 2, y(s.action.c2) + CH / 2];
    if (shown.length > 1) {
      const d = shown.map((s, i) => (i ? "L" : "M") + centre(s).map(v => v.toFixed(1)).join(" ")).join(" ");
      svg.children.push(node("path", {d, class: "search-path"}));
    }
    shown.forEach((s, i) => {
      const [px, py] = centre(s);
      svg.children.push(node("circle", {cx: px, cy: py, r: i === shown.length - 1 ? 7 : 4, class: "path-dot" + (s.safety_miss ? " miss" : "")}));
    });
    const misses = shown.filter(s => s.safety_miss);
    for (const s of misses) svg.children.push(node("rect", {x: x(s.action.c1) + 1, y: y(s.action.c2) + 1, width: CW - 2, height: CH - 2, class: "miss-ring"}));
    const pick = upto > 0 ? (upto === doc.steps.length ? doc.result.selected : shown[shown.length - 1].running_pick) : null;
    const tag = (id, label, cls) => {
      const c = doc.bank.find(b => b.candidate === id); if (!c) return;
      const bx = x(c.action.c1), by = y(c.action.c2);
      svg.children.push(node("rect", {x: bx + 4, y: by + CH - 18, width: CW - 8, height: 14, class: cls}));
      svg.children.push(node("text", {x: bx + CW / 2, y: by + CH - 7.5, "text-anchor": "middle", class: cls + "-text"}, [], label));
    };
    if (pick) tag(pick, upto === doc.steps.length ? "PICK" : "SO FAR", "pick-tag");
    if (reveal && doc.result.best) tag(doc.result.best, doc.result.best === pick ? "PICK = BEST" : "TRUE BEST", "best-tag");
    c1s.forEach(v => svg.children.push(node("text", {x: x(v) + CW / 2, y: T + c2s.length * CH + 18, "text-anchor": "middle", class: "axis"}, [], v)));
    c2s.forEach(v => svg.children.push(node("text", {x: L - 10, y: y(v) + CH / 2 + 4, "text-anchor": "end", class: "axis"}, [], v)));
    svg.children.push(node("text", {x: L + c1s.length * CW / 2, y: H - 8, "text-anchor": "middle", class: "axis-title"}, [], "First-stage rate c1 (C)"));
    svg.children.push(node("text", {x: 14, y: T + c2s.length * CH / 2, "text-anchor": "middle", class: "axis-title", transform: `rotate(-90 14 ${T + c2s.length * CH / 2})`}, [], "Second-stage rate c2 (C)"));
    return {svg, width: W, height: H};
  }

  const api = {RAMP, OUTCOMES, stepView, resultView, gridLayout, rampBins, actionText};
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document === "undefined") { return; }
  root.CarbonShowcase = api;

  // ---- DOM ----
  const SVG_NS = "http://www.w3.org/2000/svg";
  let timer = null;
  function el(tag, text, className) {
    const e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = String(text);
    if (className) e.className = className;
    return e;
  }
  function mount(tree) {
    const e = document.createElementNS(SVG_NS, tree.tag);
    for (const [k, v] of Object.entries(tree.attrs)) e.setAttribute(k, String(v));
    if (tree.text !== null) e.textContent = tree.text;
    for (const child of tree.children) e.append(mount(child));
    return e;
  }
  function pill(text, cls) { return el("span", text, "pill " + (cls || "")); }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }

  async function render(app, route, getJson, setLabels) {
    stop();
    app.replaceChildren(el("p", "Loading the replay…", "hint"));
    const index = await getJson("showcase/index.json");
    const file = route.file || index.replays[0].file;
    const entry = index.replays.find(r => r.file === file);
    if (!entry) { app.replaceChildren(el("p", "No such replay.", "notice")); return; }
    const doc = await getJson("showcase/" + encodeURIComponent(file));
    setLabels(doc.labels);
    const view = el("div");
    view.append(el("p", "Design showcase", "eyebrow section-label"), el("h1", "A model drives the design optimizer, checked against the solver"),
      el("p", doc.decision, "lede"));
    const notice = el("p", null, "notice");
    notice.append(el("strong", doc.model.kind === "CONTROL" ? "Synthetic control, not a miner. " : "Leader's model. "),
      document.createTextNode(doc.model.label + ". " + (doc.model.kind === "CONTROL"
        ? "The current leader's model takes its place once its predictions for this public task are produced. "
        : "") + "Public EV4 cases and public reference solves only; nothing here comes from a hidden or live exam."));
    view.append(notice);

    // Pickers
    const pickers = el("div", null, "pickers");
    const scenarioSelect = el("select"); scenarioSelect.setAttribute("aria-label", "Operating condition");
    const scenarios = [...new Map(index.replays.map(r => [r.scenario, r])).values()];
    for (const r of scenarios) { const o = el("option", `${r.scenario} (${r.split})`); o.value = r.scenario; o.selected = r.scenario === entry.scenario; scenarioSelect.append(o); }
    const modelSelect = el("select"); modelSelect.setAttribute("aria-label", "Model");
    for (const r of index.replays.filter(x => x.scenario === entry.scenario)) { const o = el("option", r.label); o.value = r.model; o.selected = r.model === entry.model; modelSelect.append(o); }
    const go = () => {
      const next = index.replays.find(r => r.scenario === scenarioSelect.value && r.model === modelSelect.value)
        || index.replays.find(r => r.scenario === scenarioSelect.value);
      location.hash = "#/showcase/" + encodeURIComponent(next.file);
    };
    scenarioSelect.addEventListener("change", go); modelSelect.addEventListener("change", go);
    const sc = doc.scenario;
    pickers.append(labelled("Operating condition", scenarioSelect), labelled("Model", modelSelect),
      el("p", `Ambient ${sc.t_amb_c} °C, initial state of charge ${sc.soc0}. Optimizer: ${words(doc.optimizer.class)} ${doc.optimizer.version}, ${doc.optimizer.query_budget} queries.`, "hint"));
    view.append(pickers);

    // Stage
    const stage = el("div", null, "stage");
    const figure = el("figure", null, "grid-figure");
    const side = el("div", null, "step-panel panel");
    stage.append(figure, side);
    view.append(stage);
    const legend = el("div", null, "legend");
    legend.append(swatch("ramp-0", "Fastest safe (solver)"), swatch("ramp-4", "Slowest safe"), swatch("infeasible", "Breaks a limit"),
      swatch("unresolved", "Unresolved"), swatch("miss-key", "Safety miss"));
    view.append(legend);

    // Controls
    const bar = el("div", null, "toolbar player");
    const back = button("◀ Step", "Previous step"), play = button("▶ Play", "Play"), fwd = button("Step ▶", "Next step");
    const scrub = el("input"); scrub.type = "range"; scrub.min = "0"; scrub.max = String(doc.steps.length); scrub.setAttribute("aria-label", "Step");
    const speed = el("select"); speed.setAttribute("aria-label", "Speed");
    for (const [v, t] of [["1600", "Slow"], ["900", "Normal"], ["400", "Fast"]]) { const o = el("option", t); o.value = v; o.selected = v === "900"; speed.append(o); }
    const reveal = el("label", null, "check"); const box = el("input"); box.type = "checkbox"; reveal.append(box, document.createTextNode(" Show the solver's truth now"));
    bar.append(back, play, fwd, scrub, speed, reveal);
    view.append(bar);
    const result = el("section", null, "result panel");
    view.append(result);
    const table = stepsTable(doc);
    view.append(table);
    app.replaceChildren(view);

    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let at = reduced ? doc.steps.length : 0;
    function draw() {
      scrub.value = String(at);
      const done = at === doc.steps.length;
      figure.replaceChildren(mount(gridLayout(doc, at, done || box.checked).svg));
      drawStep(side, doc, at);
      drawResult(result, doc, done);
      play.textContent = timer ? "❚❚ Pause" : at === doc.steps.length ? "↺ Replay" : "▶ Play";
    }
    function tick() { if (at < doc.steps.length) { at += 1; draw(); } if (at >= doc.steps.length) { stop(); draw(); } }
    back.addEventListener("click", () => { stop(); at = Math.max(0, at - 1); draw(); });
    fwd.addEventListener("click", () => { stop(); at = Math.min(doc.steps.length, at + 1); draw(); });
    scrub.addEventListener("input", () => { stop(); at = Number(scrub.value); draw(); });
    box.addEventListener("change", draw);
    speed.addEventListener("change", () => { if (timer) { stop(); timer = setInterval(tick, Number(speed.value)); draw(); } });
    play.addEventListener("click", () => {
      if (timer) { stop(); draw(); return; }
      if (at >= doc.steps.length) at = 0;
      timer = setInterval(tick, Number(speed.value)); draw();
    });
    window.addEventListener("hashchange", stop, {once: true});
    draw();
    if (!reduced) { timer = setInterval(tick, Number(speed.value)); draw(); }
  }

  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function labelled(text, control) { const l = el("label", null, "field"); l.append(el("span", text, "eyebrow"), control); return l; }
  function button(text, label) { const b = el("button", text); b.type = "button"; b.setAttribute("aria-label", label); return b; }
  function swatch(cls, text) { const s = el("span"); s.append(el("span", null, "swatch sw-" + cls), document.createTextNode(text)); return s; }

  function drawStep(side, doc, at) {
    side.replaceChildren();
    if (at === 0) { side.append(el("p", "Step 0", "eyebrow"), el("p", "The optimizer has not asked the model anything yet. Press play.", "hint")); return; }
    const v = stepView(doc, at - 1);
    side.append(el("p", `Step ${v.number} of ${v.total}`, "eyebrow"), el("h3", v.action));
    if (v.safetyMiss) side.append(el("p", "Safety miss: the model says this design is safe; the solver says it breaks a limit.", "miss-callout"));
    const t = el("table"); const h = el("tr");
    h.append(el("th", ""), el("th", "Model", "num"), el("th", "Solver", "num"), el("th", "Error", "num"));
    const head = el("thead"); head.append(h); const body = el("tbody");
    for (const r of v.rows) { const tr = el("tr"); tr.append(el("td", `${r.name} (${r.unit})`), el("td", r.predicted, "num"), el("td", r.truth, "num"), el("td", r.error, "num")); body.append(tr); }
    const vr = el("tr"); vr.append(el("td", "Verdict"), el("td", v.predictedVerdict, "num"), el("td", v.truthVerdict, "num"), el("td", ""));
    body.append(vr); t.append(head, body);
    const wrap = el("div", null, "table-wrap flat"); wrap.append(t); side.append(wrap);
    const pick = v.runningPick ? actionText(doc.bank.find(b => b.candidate === v.runningPick).action) : "nothing yet (no design predicted safe)";
    side.append(el("p", "The optimizer's pick so far, from the model's predictions: " + pick + ".", "hint"));
  }

  function drawResult(result, doc, done) {
    result.replaceChildren();
    result.hidden = !done;
    if (!done) return;
    const r = resultView(doc);
    result.append(el("p", "Result, judged against the solver", "eyebrow"), el("h3", r.title, r.falseFeasible ? "fail" : ""));
    if (r.note) result.append(el("p", r.note, "hint"));
    const meta = el("div", null, "meta");
    meta.append(el("span", "Final pick: " + r.pick), el("span", "Solver's best in the bank: " + r.best),
      el("span", r.safetyMisses + " safety miss(es) along the path"), el("span", r.queries));
    result.append(meta, el("p", r.regret, "regret"));
  }

  function stepsTable(doc) {
    const d = el("details"); d.append(el("summary", "Every step as a table"));
    const t = el("table"); const h = el("tr");
    for (const c of ["Step", "Design", "Model time (s)", "Solver time (s)", "Model verdict", "Solver verdict", "Safety miss"]) h.append(el("th", c));
    const head = el("thead"); head.append(h); const body = el("tbody");
    doc.steps.forEach((s, i) => {
      const v = stepView(doc, i); const tr = el("tr");
      tr.append(el("td", v.number, "num"), el("td", v.action), el("td", v.rows[0].predicted, "num"), el("td", v.rows[0].truth, "num"),
        el("td", v.predictedVerdict), el("td", v.truthVerdict), el("td", v.safetyMiss ? "yes" : "", v.safetyMiss ? "fail" : ""));
      body.append(tr);
    });
    t.append(head, body); const w = el("div", null, "table-wrap"); w.append(t); d.append(w);
    return d;
  }
  api.render = render;
})(typeof globalThis !== "undefined" ? globalThis : this);
