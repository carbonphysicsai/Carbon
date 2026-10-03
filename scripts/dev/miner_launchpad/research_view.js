"use strict";
// Carbon research surface (OWNER-MINER-RESEARCH-SURFACE-01).
//
// The screen a miner and their agent work from once setup is done: the
// Launchpad strip, the active campaign and its tabs. Every panel is drawn from
// one document, the campaign view, read through the operations table - the
// same document an MCP client gets from carbon_campaign_view (RSURF-D1).
//
// Every piece of text from the controller, journal notes above all, is set as
// text (textContent), never parsed as HTML. Nothing loads from the internet.
(() => {
  const CC = window.CarbonControlCenter;
  const Charts = window.CarbonCharts;
  if (!CC || !Charts) return;
  const {el} = CC;
  const $ = id => document.getElementById(id);
  const TABS = [["live", "Live"], ["experiments", "Experiments"], ["reasoning", "Agent reasoning"], ["contract", "Contract"], ["artifacts", "Artifacts"], ["submission", "Submission"], ["logs", "Logs"], ["settings", "Settings"]];
  const TERMINAL = ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE", "EXPIRED"];
  const POLL_MS = 3000;
  const NOTE_MAX = 2000;
  // Per-campaign view state: the last document, when it was read, and the
  // miner's own choices of case and run. Never a token or key.
  const views = new Map();

  // ---- Small helpers, all text. ----
  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function para(parent, text, className) { const p = el("p", text, className); parent.append(p); return p; }
  function button(label, className, onClick) {
    const b = el("button", label, className); b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
  }
  function anchor(label, href, className = "link") { const a = el("a", label, className); a.href = href; return a; }
  function section(parent, title, eyebrow) {
    const box = el("section", undefined, "rs-panel");
    const head = el("div", undefined, "rs-panel-head");
    if (eyebrow) head.append(el("p", eyebrow, "eyebrow"));
    head.append(el("h3", title));
    box.append(head); parent.append(box);
    return box;
  }
  function chart(parent, spec) {
    if (!spec) return;
    try { parent.append(Charts.render(spec)); }
    catch (_) { para(parent, "This chart could not be drawn; its numbers are under Data in the export.", "hint"); }
  }
  function money(nano) {
    if (typeof nano !== "number") return "unavailable";
    const dollars = nano / 1e9;
    return "$" + (dollars >= 1 ? dollars.toFixed(2) : dollars.toPrecision(3));
  }
  function duration(seconds) {
    if (typeof seconds !== "number" || seconds < 0) return "unavailable";
    const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = Math.floor(seconds % 60);
    return (h ? h + "h " : "") + (h || m ? m + "m " : "") + s + "s";
  }
  function when(unix) { return typeof unix === "number" ? new Date(unix * 1000).toLocaleString() : "unavailable"; }
  function fmt(value) { return Charts.fmt(value); }
  function copyButton(text, label) {
    const b = button("Copy", "rs-copy");
    b.setAttribute("aria-label", "Copy " + label);
    b.addEventListener("click", async () => {
      let done = false;
      try { await navigator.clipboard.writeText(text); done = true; } catch (_) { done = false; }
      b.textContent = done ? "Copied" : "Select it";
      setTimeout(() => { b.textContent = "Copy"; }, 1600);
    });
    return b;
  }
  function stateKind(state) {
    if (TERMINAL.includes(state)) return "pill-wait";
    if (["PAUSED", "PAUSE_REQUESTED", "INTERRUPTED", "RECONCILIATION_REQUIRED"].includes(state)) return "pill-need";
    return "pill-done";
  }

  // ---- Theme: light by default, the system's dark when it asks, a toggle. ----
  const themeKey = "carbon.control-center.theme.v1";
  function storedTheme() { try { return localStorage.getItem(themeKey) || "system"; } catch (_) { return "system"; } }
  function applyTheme(choice) {
    const html = document.documentElement;
    if (choice === "light" || choice === "dark") html.dataset.theme = choice; else delete html.dataset.theme;
    const toggle = $("theme-toggle");
    if (toggle) {
      toggle.textContent = {system: "Theme: system", light: "Theme: light", dark: "Theme: dark"}[choice] || "Theme: system";
      toggle.setAttribute("aria-label", "Colour theme: " + choice + ". Change it.");
    }
  }
  function cycleTheme() {
    const next = {system: "light", light: "dark", dark: "system"}[storedTheme()] || "system";
    try { localStorage.setItem(themeKey, next); } catch (_) { /* this tab keeps it */ }
    applyTheme(next);
  }

  // ---- Shell: the rail, collapsible on a narrow screen, with a help card. ----
  function setupShell() {
    const topbar = document.querySelector(".topbar");
    const state = document.querySelector(".topbar-state");
    if (topbar && !$("rail-toggle")) {
      const menu = button("Menu", "rail-toggle");
      menu.id = "rail-toggle";
      menu.setAttribute("aria-controls", "tool-nav");
      menu.setAttribute("aria-expanded", "false");
      menu.addEventListener("click", () => {
        const open = document.documentElement.classList.toggle("rail-open");
        menu.setAttribute("aria-expanded", String(open));
      });
      topbar.prepend(menu);
    }
    if (state && !$("theme-toggle")) {
      const toggle = button("Theme", "theme-toggle", cycleTheme);
      toggle.id = "theme-toggle";
      state.append(toggle);
    }
    applyTheme(storedTheme());
    const nav = $("tool-nav");
    if (nav && !$("rail-help")) {
      const help = el("aside", undefined, "rail-help"); help.id = "rail-help";
      help.append(el("p", "Help", "eyebrow"), el("p", "Stuck? Each step says what it needs, and Details names the code."));
      help.append(anchor("Wiring guide", "#guide", "link"), anchor("Bring your agent", "#connections", "link"));
      help.append(el("p", "DEVELOPMENT · testnet. Practice evidence ≠ qualification.", "rail-help-note"));
      nav.append(help);
    }
    window.addEventListener("hashchange", () => {
      document.documentElement.classList.remove("rail-open");
      $("rail-toggle")?.setAttribute("aria-expanded", "false");
    });
  }

  // ---- The campaign view, read through the operations table. ----
  function viewState(id) {
    if (!views.has(id)) views.set(id, {doc: null, at: 0, loading: false, error: null, practiceCase: null, experiment: null});
    return views.get(id);
  }
  async function load(id, force = false) {
    const entry = viewState(id);
    if (entry.loading || (!force && Date.now() - entry.at < POLL_MS)) return;
    entry.loading = true;
    const body = {campaign: id};
    if (entry.practiceCase) body.practice_case = entry.practiceCase;
    if (entry.experiment) body.experiment = entry.experiment;
    try { entry.doc = await CC.api("/api/v1/operations/campaign_view", body, undefined, 20000); entry.error = null; }
    catch (error) {
      entry.error = error.message;
      // A choice the view no longer knows is dropped, then read again.
      if (/unknown_practice_case|unknown_experiment/.test(error.message)) { entry.practiceCase = null; entry.experiment = null; entry.at = 0; }
    } finally { entry.loading = false; entry.at = Date.now(); }
    render();
  }
  // What a view shows, without the clock: a panel rebuilds only on change.
  function docKey(doc) {
    if (!doc) return "";
    const {tiles, ...rest} = doc;
    return JSON.stringify(rest) + JSON.stringify({...tiles, now_unix: 0, elapsed_seconds: 0});
  }

  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    const tab = TABS.some(([name]) => name === parts[2]) ? parts[2] : "live";
    return {view: parts[0] || "overview", id: parts[1] || "", tab};
  }

  // ---- Shared pieces of the active campaign. ----
  function header(parent, doc, run, compact) {
    const head = el("div", undefined, "rs-head");
    const title = el("div", undefined, "rs-title");
    const challenge = doc.campaign.challenge;
    title.append(el("p", "Campaign · " + doc.labels.mode + " · " + doc.labels.network + " " + doc.labels.netuid, "eyebrow section-label"));
    title.append(el(compact ? "h3" : "h2", challenge ? (challenge.title || challenge.id) + " · v" + challenge.version : "Campaign without a Challenge"));
    const meta = el("div", undefined, "rs-meta");
    meta.append(CC.pill(words(doc.campaign.state), stateKind(doc.campaign.state)));
    if (doc.fixture) meta.append(CC.pill("Synthetic fixture", "pill-need"));
    meta.append(el("span", "Started " + when(doc.tiles.started_unix), "rs-started"));
    const id = el("code", doc.campaign.id, "rs-id");
    meta.append(id, copyButton(doc.campaign.id, "campaign id"));
    title.append(meta);
    head.append(title);
    const actions = el("div", undefined, "rs-actions");
    for (const control of doc.controls) {
      if (compact && control.action !== "stop" && control.action !== "pause") continue;
      const b = button(control.label, control.action === "stop" ? "rs-stop" : "", () => CC.researchAction(doc.campaign.id, control.action));
      b.disabled = !control.available || !CC.state().connected;
      if (control.reason) b.title = control.reason;
      b.dataset.action = control.action;
      actions.append(b);
    }
    if (compact) actions.append(anchor("Open campaign", "#campaigns/" + encodeURIComponent(doc.campaign.id) + "/live", "button primary"));
    else actions.append(button("Export", "", () => CC.researchAction(doc.campaign.id, "export")));
    head.append(actions);
    parent.append(head);
    if (doc.fixture) para(parent, "Synthetic fixture data, for seeing the surface. Not a campaign, not evidence, never LIVE.", "rs-fixture");
  }
  function tiles(parent, doc) {
    const t = doc.tiles;
    const grid = el("div", undefined, "rs-tiles");
    const tile = (label, value, note, id) => {
      const box = el("div", undefined, "rs-tile");
      box.append(el("p", label, "eyebrow"));
      const strong = el("strong", value); if (id) strong.dataset.tile = id;
      box.append(strong);
      if (note) box.append(note);
      grid.append(box);
      return box;
    };
    tile("Elapsed", t.elapsed_seconds === null ? (t.deadline_unix ? "Deadline " + when(t.deadline_unix) : "Not running") : duration(t.elapsed_seconds), t.deadline_unix ? el("span", "Your deadline: " + when(t.deadline_unix), "hint") : el("span", "No deadline: you set no elapsed limit.", "hint"), "elapsed");
    if (t.spend) {
      const note = el("div");
      if (typeof t.spend.ceiling_nanodollars === "number" && t.spend.ceiling_nanodollars > 0) {
        const bar = el("progress"); bar.max = t.spend.ceiling_nanodollars; bar.value = Math.min(t.spend.used_nanodollars + t.spend.reserved_nanodollars, t.spend.ceiling_nanodollars);
        bar.setAttribute("aria-label", "Model spend against your own ceiling");
        note.append(bar, el("span", "Your ceiling: " + money(t.spend.ceiling_nanodollars), "hint"));
      } else note.append(el("span", "No ceiling set: Carbon caps nothing.", "hint"));
      note.append(el("span", "Billed by your provider to you. Carbon bills nothing.", "hint"));
      tile("Model spend · your ledger", money(t.spend.used_nanodollars), note);
    } else tile("Model spend · your ledger", "No ledger yet", el("span", "Appears once the campaign ledger exists.", "hint"));
    tile("Practice runs", String(t.practice_runs.completed) + (typeof t.practice_runs.attempted === "number" ? " of " + t.practice_runs.attempted + " attempted" : ""), t.trials && typeof t.trials.ceiling === "number" ? el("span", "Trials used " + t.trials.used + " of your " + t.trials.ceiling, "hint") : el("span", "Trials used " + (t.trials ? t.trials.used : 0) + " · no cap set", "hint"));
    tile("Compute", t.compute.backend ? words(t.compute.backend).toLowerCase() : (t.compute.lane || "unavailable"), el("span", typeof t.compute.numerical_seconds === "number" ? t.compute.numerical_seconds + " s of worker time" : "Worker time appears once a trial runs.", "hint"));
    parent.append(grid);
  }
  function stages(parent, doc) {
    const list = el("ol", undefined, "rs-stages");
    list.setAttribute("aria-label", "Campaign lifecycle");
    doc.stages.forEach((stage, index) => {
      const item = el("li", undefined, "rs-stage is-" + stage.state);
      if (stage.state === "current" || stage.state === "halted") item.setAttribute("aria-current", "step");
      item.append(el("span", String(index + 1).padStart(2, "0"), "rs-stage-num"));
      const body = el("div");
      body.append(el("strong", stage.label), el("span", stage.detail, "hint"));
      item.append(body, CC.pill({done: "Done", current: "Now", halted: "Halted", waiting: "Waiting", not_reached: "Not reached"}[stage.state] || words(stage.state), {done: "pill-done", current: "pill-next", halted: "pill-need"}[stage.state] || "pill-wait"));
      list.append(item);
    });
    parent.append(list);
  }

  // ---- Tabs. ----
  function tabLive(panel, doc, run) {
    const grid = el("div", undefined, "rs-live");
    const now = section(grid, "Now", "Current work");
    if (doc.current_operation) para(now, "Running: " + words(doc.current_operation.phase) + " · " + doc.current_operation.id, "status-line");
    else para(now, "Nothing is running. State: " + words(doc.campaign.state).toLowerCase() + ".", "status-line");
    if (doc.hypothesis) {
      const quote = el("blockquote", undefined, "rs-quote");
      quote.append(el("p", doc.hypothesis), el("cite", "Latest hypothesis · recorded text, shown as text"));
      now.append(quote);
    }
    const quick = el("div", undefined, "rs-quick");
    for (const control of doc.controls.filter(c => c.action !== "reconcile")) {
      const b = button(control.label, "", () => CC.researchAction(doc.campaign.id, control.action));
      b.disabled = !control.available || !CC.state().connected; if (control.reason) b.title = control.reason;
      quick.append(b);
    }
    quick.append(button("Export", "", () => CC.researchAction(doc.campaign.id, "export")));
    quick.append(anchor("Contract", "#campaigns/" + encodeURIComponent(doc.campaign.id) + "/contract", "button"));
    now.append(quick);
    const trend = section(grid, "Practice runs", "Live metrics");
    const byId = Object.fromEntries(doc.charts.map(c => [c.id, c]));
    if (byId.trend_score) chart(trend, byId.trend_score); else para(trend, "No practice run yet. Each completed run adds a point.", "empty-state");
    if (byId.trend_components) chart(trend, byId.trend_components);
    const compare = section(grid, "This run against the previous", "Experiment output");
    if (byId.components) chart(compare, byId.components);
    metricsTable(compare, doc);
    const curve = section(grid, "Learning curve", "Training");
    if (byId.learning_curve) chart(curve, byId.learning_curve);
    else para(curve, "Not recorded. " + (doc.learning_curve.basis || ""), "empty-state");
    const cases = section(grid, "A public practice case", "Predicted against reference");
    cases.classList.add("rs-wide");
    perCase(cases, doc);
    const recent = section(grid, "Recent events", "Logs");
    const ops = doc.events.operations.slice(-8).reverse();
    if (!ops.length) para(recent, "No operation recorded yet.", "hint");
    const list = el("ol", undefined, "events");
    for (const op of ops) { const li = el("li"); li.append(el("span", words(op.phase)), el("span", words(op.state).toLowerCase(), "hint")); list.append(li); }
    recent.append(list);
    const thoughts = section(grid, "Agent reasoning", "Journal");
    feed(thoughts, doc, 5);
    thoughts.append(anchor("All reasoning and notes", "#campaigns/" + encodeURIComponent(doc.campaign.id) + "/reasoning"));
    panel.append(grid);
  }
  function metricsTable(parent, doc) {
    const c = doc.comparison;
    if (!c) { para(parent, "Appears after the first practice run.", "hint"); return; }
    const wrap = el("div", undefined, "table-wrap");
    const table = el("table", undefined, "metrics-table rs-compare");
    const head = el("tr");
    for (const name of ["Metric", c.previous ? "Run " + c.previous : "Previous", "Run " + c.current, "Change"]) head.append(el("th", name));
    table.append(head);
    for (const m of c.metrics) {
      const row = el("tr");
      row.append(el("td", m.label), el("td", m.previous === null ? "–" : fmt(m.previous)), el("td", m.current === null ? "–" : fmt(m.current)));
      const change = el("td", undefined, m.better === true ? "rs-better" : m.better === false ? "rs-worse" : "");
      change.textContent = m.delta === null ? "–" : (m.delta < 0 ? "▼ " : m.delta > 0 ? "▲ " : "= ") + fmt(Math.abs(m.delta)) + (m.better === true ? " better" : m.better === false ? " worse" : "");
      row.append(change); table.append(row);
    }
    wrap.append(table); parent.append(wrap);
    para(parent, (c.direction === "lower_is_better" ? "Lower is better. " : "Higher is better. ") + c.basis, "hint");
  }
  function perCase(parent, doc) {
    const pc = doc.per_case;
    const entry = viewState(doc.campaign.id);
    if (pc.status !== "AVAILABLE") {
      para(parent, pc.status === "WITHHELD" ? "Aggregates only: " + (pc.basis || "per-case detail is not disclosed for this Challenge.") : "Not available: " + words(pc.reason) + ".", "empty-state");
      if (pc.status !== "WITHHELD" && pc.basis) para(parent, pc.basis, "hint");
      return;
    }
    const pick = el("div", undefined, "rs-case-pick");
    const label = el("label", "Public practice case"); label.htmlFor = "rs-case-" + doc.campaign.id;
    const select = el("select"); select.id = label.htmlFor;
    for (const id of pc.case_ids) { const option = el("option", id); option.value = id; select.append(option); }
    select.value = pc.selected.case_id;
    select.addEventListener("change", () => { entry.practiceCase = select.value; load(doc.campaign.id, true); });
    pick.append(label, select);
    parent.append(pick);
    const inputs = Object.entries(pc.selected.inputs).map(([k, v]) => k + " " + fmt(v)).join(" · ");
    para(parent, "Run " + pc.experiment_index + (pc.previous_experiment ? " and the run before it" : "") + ", against the public reference. Inputs: " + inputs, "hint");
    const charts = el("div", undefined, "rs-case-charts");
    for (const spec of pc.selected.charts) chart(charts, spec);
    parent.append(charts);
    para(parent, pc.basis + " Public practice only: never an evaluation case.", "hint");
  }
  function feed(parent, doc, limit) {
    const entries = doc.journal.entries.slice(0, limit || undefined);
    if (!entries.length) { para(parent, "Nothing in the journal yet. Hypotheses, decisions and notes appear here.", "hint"); return; }
    const list = el("ol", undefined, "rs-feed");
    for (const item of entries) {
      const li = el("li", undefined, "rs-feed-item kind-" + item.kind);
      const meta = el("p", undefined, "rs-feed-meta");
      meta.append(CC.pill(words(item.kind), item.via === "carbon_note" ? "pill-open" : "pill-wait"), el("span", {carbon_note: "Posted with carbon_note", trial: "Recorded with a trial", agent_or_controller: "Agent or controller", controller: "Controller", notebook: "Workspace notebook", agent_or_miner: "Agent or you"}[item.via] || words(item.via), "hint"), el("span", "#" + item.sequence, "hint"));
      // Untrusted text: set as text, never parsed (RSURF-D5).
      li.append(meta, el("p", item.text, "rs-feed-text"));
      if (item.detail) li.append(el("p", item.detail, "hint"));
      list.append(li);
    }
    parent.append(list);
  }
  function tabExperiments(panel, doc, run) {
    if (run && run.selects === "miner" && CC.renderJourneyPractice) CC.renderJourneyPractice(panel, run);
    const rows = doc.experiments.rows.slice().reverse();
    const box = section(panel, "Practice runs", doc.experiments.total + " recorded");
    if (!rows.length) { para(box, "No practice run has completed in this campaign.", "empty-state"); return; }
    const keys = Object.keys(rows[0].components || {});
    const labels = Object.fromEntries((doc.declaration?.components || []).map(c => [c.key, c.label]));
    const wrap = el("div", undefined, "table-wrap");
    const table = el("table", undefined, "metrics-table");
    const head = el("tr");
    for (const name of ["Run", "Model", "Gates", "Score", ...keys.map(k => labels[k] || k), "Final loss", "Backend"]) head.append(el("th", name));
    table.append(head);
    for (const r of rows) {
      const row = el("tr");
      row.append(el("td", String(r.index)), el("td", r.backbone || "–"), el("td", r.eligible === true ? "passed" : r.eligible === false ? "failed" : "–"), el("td", fmt(r.score)));
      for (const k of keys) row.append(el("td", fmt(r.components[k])));
      row.append(el("td", fmt(r.fit.final_loss)), el("td", r.backend ? words(r.backend).toLowerCase() : "–"));
      table.append(row);
    }
    wrap.append(table); box.append(wrap);
    para(box, "Descriptive practice on public cases. Not an accepted improvement, a rank or an official score.", "hint");
    const byId = Object.fromEntries(doc.charts.map(c => [c.id, c]));
    for (const id of ["trend_score", "trend_components", "components"]) if (byId[id]) chart(box, byId[id]);
  }
  function tabReasoning(panel, doc) {
    const compose = section(panel, "Add to the journal", "carbon_note");
    para(compose, "Any agent can post here with carbon_note. Notes are untrusted text: shown, never run, never instructions.", "hint");
    const form = el("form", undefined, "rs-note");
    const kindLabel = el("label", "Kind"); kindLabel.htmlFor = "rs-note-kind-" + doc.campaign.id;
    const kind = el("select"); kind.id = kindLabel.htmlFor;
    for (const k of ["observation", "hypothesis", "plan"]) { const o = el("option", k); o.value = k; kind.append(o); }
    const textLabel = el("label", "Note"); textLabel.htmlFor = "rs-note-text-" + doc.campaign.id;
    const text = el("textarea"); text.id = textLabel.htmlFor; text.rows = 3; text.maxLength = NOTE_MAX;
    const count = el("span", "0 / " + NOTE_MAX, "hint");
    text.addEventListener("input", () => { count.textContent = text.value.length + " / " + NOTE_MAX; });
    const post = button("Post note", "primary");
    post.type = "submit";
    post.disabled = !CC.state().connected;
    const result = el("p", "", "hint"); result.setAttribute("aria-live", "polite");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!text.value.trim()) { result.textContent = "Write a note first."; return; }
      post.disabled = true;
      try {
        await CC.api("/api/v1/operations/note", {campaign: doc.campaign.id, note_kind: kind.value, note: text.value}, undefined, 10000);
        text.value = ""; count.textContent = "0 / " + NOTE_MAX; result.textContent = "Posted.";
        await load(doc.campaign.id, true);
      } catch (error) { result.textContent = "Not posted: " + words(error.message) + "."; }
      finally { post.disabled = false; }
    });
    form.append(kindLabel, kind, textLabel, text, count, post, result);
    compose.append(form);
    const box = section(panel, "Reasoning and notes", doc.journal.total + " entries");
    para(box, doc.journal.basis, "hint");
    feed(box, doc);
    if (doc.journal.epoch_outcomes.length) {
      const outcomes = section(panel, "Epoch outcomes", "Agent or miner reported");
      for (const o of doc.journal.epoch_outcomes) para(outcomes, "Epoch " + o.epoch + ": " + words(o.status) + " · selected by " + (o.selected_by === "miner" ? "you" : "the agent") + (o.reason ? " · " + o.reason : "") + ". Reported, not independent science.");
    }
  }
  function tabContract(panel, doc) {
    const c = doc.contract;
    if (!c || c.status === "UNAVAILABLE") { para(panel, "This Challenge's contract could not be read.", "empty-state"); return; }
    const top = section(panel, "What you may change", "Contract");
    para(top, "Read from the Challenge's registered construction contract. Only what is rebuildable can be submitted; everything else is research only or excluded, with the blocker that keeps it there.", "lede");
    const facts = el("dl", undefined, "review-grid");
    const fact = (k, v) => facts.append(el("dt", k), el("dd", v));
    fact("Challenge", (c.challenge.title || c.challenge.id) + " · version " + c.challenge.version);
    fact("Contract digest", c.contract_digest || "unavailable");
    fact("Exam rule", [c.exam.rule.status, c.exam.rule.authority].filter(Boolean).map(words).join(" · ") || "unavailable");
    fact("Feedback mode", (c.feedback_mode?.frozen || "FULL") + " · " + (c.feedback_mode?.basis || ""));
    fact("Construction level", c.construction_level.level === null ? "Not yet defined. " + c.construction_level.basis : String(c.construction_level.level));
    top.append(facts);
    const models = section(panel, "Rebuildable models", c.rebuildable_models.length + " families");
    const ml = el("ul", undefined, "rs-list");
    for (const m of c.rebuildable_models) { const li = el("li"); li.append(el("strong", m.selector || m.id), el("span", " " + (m.summary || ""), "hint")); ml.append(li); }
    models.append(ml);
    const controls = section(panel, "Controls", "Ranges and defaults");
    const wrap = el("div", undefined, "table-wrap"); const table = el("table", undefined, "metrics-table");
    const head = el("tr"); for (const n of ["Control", "Type", "Range or choices", "Default", "Families"]) head.append(el("th", n)); table.append(head);
    for (const [name, k] of Object.entries(c.controls)) {
      const row = el("tr");
      const range = Array.isArray(k.minimum_or_choices) ? k.minimum_or_choices.join(", ") : (k.minimum_or_choices ?? "–") + (k.maximum !== null && k.maximum !== undefined ? " to " + k.maximum : "");
      row.append(el("td", name), el("td", k.type || "–"), el("td", String(range)), el("td", k.default === null || k.default === undefined ? "–" : JSON.stringify(k.default)), el("td", k.families ? k.families.join(", ") : "all"));
      table.append(row);
    }
    wrap.append(table); controls.append(wrap);
    const caps = section(panel, "Capabilities", Object.entries(c.capability_counts).map(([s, n]) => n + " " + words(s)).join(" · "));
    const order = ["admitted", "rebuildable_development", "research_only", "excluded"];
    for (const status of order) {
      const items = c.capabilities.filter(item => item.status === status);
      if (!items.length) continue;
      const group = el("details", undefined, "rs-caps");
      group.append(el("summary", words(status) + " · " + items.length));
      if (c.status_meaning?.[status]) group.append(el("p", c.status_meaning[status], "hint"));
      const list = el("ul", undefined, "rs-list");
      for (const item of items) { const li = el("li"); li.append(el("strong", item.id), el("span", " " + (item.summary || ""), "hint")); if (item.blocker && item.blocker !== "none") li.append(el("span", " Blocker: " + words(item.blocker), "rs-blocker")); list.append(li); }
      group.append(list); caps.append(group);
    }
    const exam = section(panel, "Exam gates and what is never disclosed", "Evaluation");
    para(exam, "Gates: " + c.exam.gates.map(words).join(", ") + ". A gate failure is never compensated by score.");
    para(exam, "Components: " + c.exam.components.join(", ") + ".");
    const never = el("ul", undefined, "rs-list"); for (const item of c.never_disclosed) never.append(el("li", item)); exam.append(el("p", "Never disclosed:", "status-line"), never);
    const limits = section(panel, "Limits", "Yours, or none");
    const ld = el("dl", undefined, "review-grid");
    for (const [k, v] of Object.entries(c.limits || {})) ld.append(el("dt", words(k)), el("dd", typeof v === "string" ? v : JSON.stringify(v)));
    limits.append(ld);
  }
  function tabArtifacts(panel, doc) {
    const box = section(panel, "Frozen candidates", "Artifacts");
    if (!doc.candidates.length) para(box, "No candidate frozen yet. Freeze a practiced recipe under Submission.", "empty-state");
    for (const c of doc.candidates) {
      para(box, "Epoch " + c.epoch + " · " + (c.strategy_hash || "") + (c.reason ? " · " + c.reason : ""), "status-line");
      const pre = el("pre", JSON.stringify(c.strategy, null, 2), "rs-pre"); box.append(pre);
    }
    const recipes = section(panel, "Practiced recipes", "Your own");
    const seen = new Set();
    for (const r of doc.experiments.rows) {
      if (!r.recipe) continue;
      const text = JSON.stringify(r.recipe, null, 2); if (seen.has(text)) continue; seen.add(text);
      recipes.append(el("p", "Run " + r.index + " · " + (r.backbone || ""), "hint"), el("pre", text, "rs-pre"));
    }
    if (!seen.size) para(recipes, "No practiced recipe recorded yet.", "hint");
    para(panel, "Trained weights stay on your machine. Export gives the campaign's full public record as JSON.", "hint");
  }
  function tabSubmission(panel, doc, run) {
    if (run && run.selects === "miner" && CC.renderJourneySubmission) CC.renderJourneySubmission(panel, run);
    else if (doc.campaign.selects === "agent") para(panel, "Carbon's agent freezes and submits in this campaign.", "hint");
    const box = section(panel, "DEVELOPMENT outcomes", "Validator");
    if (!doc.outcomes.length) para(box, "No DEVELOPMENT outcome yet.", "empty-state");
    for (const o of doc.outcomes) {
      const r = o.result || {};
      const s = r.screening || {};
      const line = ["Epoch " + o.epoch, words(o.status).toLowerCase()];
      if (r.state) line.push(words(r.state).toLowerCase());
      if (typeof s.eligible === "boolean") line.push(s.eligible ? "eligible" : "not eligible");
      if (Array.isArray(s.gates_failed)) line.push("gates failed: " + (s.gates_failed.join(", ") || "none"));
      if (typeof s.score === "number") line.push("score " + fmt(s.score));
      if (r.disposition) line.push(words(r.disposition).toLowerCase());
      para(box, line.join(" · "), "status-line");
      if (r.withheld) para(box, "Withheld: " + r.withheld, "hint");
      if (r.feedback_mode && r.feedback_mode !== "FULL") para(box, "Shown through the frozen feedback mode " + r.feedback_mode + ".", "hint");
    }
    para(box, "DEVELOPMENT only: no qualification, reward, rank or chain write.", "hint");
  }
  function tabLogs(panel, doc, run) {
    const box = section(panel, "Operations", doc.events.total + " recorded");
    const list = el("ol", undefined, "events");
    for (const op of doc.events.operations.slice().reverse()) { const li = el("li"); li.append(el("span", words(op.phase)), el("span", words(op.state).toLowerCase(), "hint"), el("code", op.id)); list.append(li); }
    if (!doc.events.operations.length) para(box, "No operation recorded.", "hint");
    box.append(list);
    para(box, "Provider payloads, worker output and errors stay private to the campaign; this shows operation states only.", "hint");
    const usage = run && run.usage;
    const res = section(panel, "Resources", "Your ledger");
    if (!usage) { para(res, "Appears once the campaign ledger exists.", "hint"); return; }
    const wrap = el("div", undefined, "table-wrap"); const table = el("table", undefined, "metrics-table");
    const head = el("tr"); for (const n of ["Resource", "Your limit", "Reported", "Reserved", "Uncertain"]) head.append(el("th", n)); table.append(head);
    const budget = usage.budget || {};
    for (const name of Object.keys(usage.reported || {})) {
      const cap = budget.ceilings ? budget.ceilings[name] : budget[name];
      const row = el("tr");
      row.append(el("td", words(name)), el("td", cap === undefined || cap === null ? "No limit" : String(cap)), el("td", String(usage.reported[name])), el("td", String(usage.reserved?.[name] ?? "")), el("td", String(usage.uncertain?.[name] ?? "")));
      table.append(row);
    }
    wrap.append(table); res.append(wrap);
    para(res, usage.cost_basis || "", "hint");
  }
  function tabSettings(panel, doc) {
    const grid = el("dl", undefined, "review-grid");
    const row = (k, v) => grid.append(el("dt", k), el("dd", v === null || v === undefined ? "unavailable" : String(v)));
    row("Campaign", doc.campaign.id);
    row("Challenge", doc.campaign.challenge ? doc.campaign.challenge.id + " · " + doc.campaign.challenge.version : null);
    row("Who selects", doc.campaign.selects === "miner" ? "You" : doc.campaign.selects === "agent" ? "Carbon's agent" : null);
    row("Agent", doc.campaign.agent);
    row("Model", doc.campaign.model || "none");
    row("Admission", words(doc.campaign.admission));
    row("Runtime revision", doc.campaign.runtime_revision);
    row("Evidence", words(doc.labels.evidence));
    panel.append(grid);
    const box = el("details");
    box.append(el("summary", "The campaign view document (what an agent reads)"));
    box.append(el("pre", JSON.stringify(doc, null, 2), "rs-pre"));
    panel.append(box);
    para(panel, doc.non_claims.join(" "), "hint");
  }

  // ---- The campaign detail, drawn into app.js's container. ----
  function detail(container, run) {
    const r = route();
    const entry = viewState(run.id);
    load(run.id);
    const active = document.activeElement;
    if (active && container.contains(active) && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName) && container.dataset.run === run.id) { updateClock(container, entry.doc); return; }
    const key = run.id + "|" + r.tab + "|" + docKey(entry.doc) + "|" + (entry.error || "") + "|" + CC.state().connected + "|" + JSON.stringify(run.journey || {}) + "|" + run.state;
    if (container.dataset.key === key) { updateClock(container, entry.doc); return; }
    const open = new Set([...container.querySelectorAll("details[open]")].map(node => node.dataset.key));
    container.dataset.key = key; container.dataset.run = run.id;
    container.replaceChildren(anchor("← All campaigns", "#campaigns", "rs-back"));
    if (!entry.doc) {
      para(container, entry.error ? "The campaign view could not be read: " + words(entry.error) + ". " + (CC.state().connected ? "It is read again shortly." : "Reconnect this browser.") : "Reading the campaign view…", entry.error ? "reason" : "hint");
      return;
    }
    const doc = entry.doc;
    if (entry.error) para(container, "Showing the last view read; the newest read failed: " + words(entry.error) + ".", "reason");
    header(container, doc, run, false);
    tiles(container, doc);
    stages(container, doc);
    const nav = el("nav", undefined, "tabs"); nav.setAttribute("aria-label", "Campaign sections");
    for (const [name, label] of TABS) {
      const link = anchor(label, "#campaigns/" + encodeURIComponent(run.id) + "/" + name, "");
      if (name === r.tab) link.setAttribute("aria-current", "page");
      nav.append(link);
    }
    container.append(nav);
    const panel = el("section", undefined, "tab-panel rs-tab"); panel.dataset.tab = r.tab;
    ({live: tabLive, experiments: tabExperiments, reasoning: tabReasoning, contract: tabContract, artifacts: tabArtifacts, submission: tabSubmission, logs: tabLogs, settings: tabSettings})[r.tab](panel, doc, run);
    container.append(panel);
    [...container.querySelectorAll("details")].forEach((node, index) => { node.dataset.key = String(index); if (open.has(String(index))) node.open = true; });
  }
  function updateClock(container, doc) {
    if (!doc) return;
    const node = container.querySelector('[data-tile="elapsed"]');
    if (node && typeof doc.tiles.elapsed_seconds === "number") node.textContent = duration(doc.tiles.elapsed_seconds + Math.max(0, Math.round((Date.now() - viewState(doc.campaign.id).at) / 1000)));
  }

  // ---- Launchpad: the configured setup, then launch. ----
  function strip() {
    const target = $("launchpad-strip");
    if (!target) return;
    const s = CC.state();
    if (!s.connected || !s.caps) { target.replaceChildren(el("p", "Connect this browser to see your setup.", "hint")); target.dataset.key = ""; return; }
    const setup = s.setupState || {};
    const steps = setup.steps || {};
    const entry = CC.challengeEntry(s.wizard.challenge);
    const agent = CC.agentEntry(s.wizard.agentChoice);
    const choiceName = (step, id) => (setup.choices?.[step] || []).find(c => c.id === id)?.display_name || words(id);
    const budget = s.composition.budget || {};
    const parts = [];
    if ("elapsed_seconds" in budget) parts.push(budget.elapsed_seconds + " s elapsed");
    for (const [name, cap] of Object.entries(budget.ceilings || {})) parts.push(words(name) + " ≤ " + cap);
    const problem = CC.launchProblem();
    const cards = [
      {id: "challenge", title: "Challenge", value: entry ? entry.title + " · v" + entry.version : "Not chosen", note: entry ? (entry.selectable ? "Ready to launch" : "Set up first") : "Choose what to mine", go: () => CC.goWizard("challenge")},
      {id: "agent", title: "Agent", value: agent ? agent.label : steps.agent?.checked ? choiceName("agent", steps.agent.choice) : "Not chosen", note: agent ? (agent.uses_model ? "Carbon's agent calls your model" : "Calls no model") : "Who researches and submits", href: "#setup/agent"},
    ];
    if (!agent || agent.uses_model) cards.push({id: "inference", title: "Inference", value: steps.inference?.checked ? choiceName("inference", steps.inference.provider_id) + " · " + steps.inference.model_id : "Not checked", note: "Only Carbon's own agent calls a model, with your key", href: "#setup/inference"});
    cards.push(
      {id: "compute", title: "Compute", value: steps.compute?.checked ? choiceName("compute", steps.compute.choice) : (s.caps.compute?.choices?.[0]?.label || "Not checked"), note: "Your machine, or your own remote one", href: "#setup/compute"},
      {id: "limits", title: "Limits", value: parts.length ? parts.join(", ") : "None set", note: "Your own campaign ledger. Carbon caps and bills nothing.", go: () => CC.goWizard("limits")},
      {id: "review", title: "Review", value: problem ? "Not ready" : "Ready", note: problem || "Every step can pass.", href: "#setup/review"},
    );
    const key = JSON.stringify([cards.map(c => [c.value, c.note]), problem, s.busy, s.pendingResearch ? 1 : 0]);
    if (target.dataset.key === key) return;
    target.dataset.key = key;
    target.replaceChildren();
    const head = el("div", undefined, "panel-heading");
    head.append(el("h2", "Launch a new campaign"), el("span", "Agent first · your accounts", "eyebrow"));
    target.append(head);
    const list = el("ol", undefined, "rs-strip");
    cards.forEach((card, index) => {
      const item = el("li", undefined, "rs-card" + (card.id === "review" && !problem ? " is-ready" : ""));
      item.dataset.card = card.id;
      item.append(el("span", String(index + 1).padStart(2, "0"), "rs-card-num"), el("p", card.title, "eyebrow"), el("strong", card.value), el("span", card.note, "hint"));
      // A setup step is the setup wizard's own page; the Challenge and limits
      // are the launch wizard's steps.
      const change = card.href ? anchor("Change", card.href, "rs-change") : button("Change", "rs-change", card.go);
      change.setAttribute("aria-label", "Change " + card.title);
      item.append(change);
      list.append(item);
    });
    target.append(list);
    const actions = el("div", undefined, "rs-launch");
    const launch = button(s.pendingResearch ? "Retry the same launch" : "Launch campaign", "primary go", () => CC.launch());
    launch.id = "rs-launch";
    launch.disabled = Boolean(problem) || s.busy;
    actions.append(launch, button("Save as template", "", () => CC.goWizard("limits")));
    target.append(actions);
    if (problem) target.append(el("p", problem, "reason"));
    target.append(el("p", "Launch is the same launch operation, with the same checks: your registration is read first, and a lost response is retried, never duplicated.", "hint"));
  }
  function activePanel() {
    const target = $("active-campaign");
    if (!target) return;
    const s = CC.state();
    const live = s.connected ? s.research.runs.filter(run => !TERMINAL.includes(run.state)) : [];
    if (!live.length) { target.hidden = true; target.dataset.key = ""; return; }
    const run = live[0];
    load(run.id);
    const doc = viewState(run.id).doc;
    target.hidden = false;
    const key = run.id + docKey(doc);
    if (target.dataset.key === key) { updateClock(target, doc); return; }
    target.dataset.key = key;
    target.replaceChildren(el("h2", "Active campaign", "section-title"));
    if (!doc) { target.append(el("p", "Reading the campaign view…", "hint")); return; }
    const box = el("div", undefined, "panel rs-active");
    header(box, doc, run, true);
    tiles(box, doc);
    stages(box, doc);
    target.append(box);
  }

  function render() {
    try { strip(); activePanel(); } catch (error) { console.error(error); }
    const r = route();
    if (r.view === "campaigns" && r.id) CC.renderCampaigns();
  }

  setupShell();
  window.CarbonResearch = {detail, render, TABS};
  CC.onRender(() => { try { strip(); activePanel(); } catch (error) { console.error(error); } });
  render();
})();
