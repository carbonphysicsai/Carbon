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
  const TABS = [["live", "Live"], ["conversation", "Conversation"], ["experiments", "Experiments"], ["reasoning", "Agent reasoning"], ["tools", "Tools"], ["contract", "Contract"], ["artifacts", "Artifacts"], ["submission", "Submission"], ["logs", "Logs"], ["settings", "Settings"]];
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
  // ---- Parts (LP-PROD-F). A campaign's page is a fixed set of parts, each
  // redrawn only when what it shows changed and nothing holds it (app.js's
  // live-region rules): a refresh never replaces the control under a
  // person's hand, nor a part whose data did not move.
  function part(parent, name, key, build, className = "rs-panel", tag = "section") {
    let node = null;
    for (const child of parent.children) if (child.dataset.part === name) { node = child; break; }
    if (!node) { node = el(tag, undefined, className); node.dataset.part = name; parent.append(node); }
    CC.rebuild(node, key, build);
    return node;
  }
  function head(parent, title, eyebrow) {
    const box = el("div", undefined, "rs-panel-head");
    if (eyebrow) box.append(el("p", eyebrow, "eyebrow"));
    box.append(el("h3", title));
    parent.append(box);
  }
  // ---- Recovery (LP-PROD-F). A campaign in one of these states needs
  // something done before it moves again; each says why, in a line, and its
  // controls stay in reach wherever the campaign is shown. When the record
  // carries the controller's own `recovery` (slice C's [{action,
  // operation}], empty when nothing is needed), its actions are the ones
  // offered; otherwise this page reads the state, and offers Reconcile.
  const RECOVERY = {
    PAUSE_REQUESTED: "A pause was asked for and the running step has not confirmed it. Wait for the step to end; if it stays here, Reconcile settles what it holds.",
    // Reconcile also settles each model call whose outcome is unknown
    // (LP-PROD-W2): booked at its full reservation, and never resent.
    RECONCILIATION_REQUIRED: "Work may still be held after an interruption. Reconcile checks what is held and cleans it up, and books each model call whose outcome is unknown at its full reservation; it resends nothing. Then Resume or Stop.",
    INTERRUPTED: "The controller stopped mid-step. Reconcile settles what was held, then Resume continues the campaign.",
  };
  // The same states, said as the controller's own recovery actions say them.
  const RECOVERY_OFFERED = {
    QUEUED: "Admitted, and nothing is carrying it out. Resume dispatches it again from its record; Stop ends it.",
    PAUSE_REQUESTED: "A pause was asked for and the running step has not confirmed it. Resume cancels the pause; if the step has ended and it stays here, Reconcile settles the pause; Stop ends the campaign.",
    INTERRUPTED: "The controller stopped mid-step. Resume continues the campaign from its record; Reconcile checks again what it holds and settles it; Stop ends it.",
    RECONCILIATION_REQUIRED: RECOVERY.RECONCILIATION_REQUIRED,
  };
  const RECOVERY_ACTIONS = {resume: "Resume", stop: "Stop", reconcile: "Reconcile", retry_interrupted: "Retry practice"};
  // An interrupted practice's one-step retry (LAUNCHPAD-PRACTICE-RETRY-01):
  // the header has no control for it, so its button is always the line's own.
  const RETRY_PRACTICE = "A practice stopped before it finished, most likely because the process running it exited. Retry practice sends it again exactly as it was: the same recipe, hypothesis and expected effect.";
  // A fresh launch is QUEUED, with no frozen record, until its run thread
  // creates its ledger: "never started" is said only once it has stayed so
  // this long, as this page has seen it.
  const UNSTARTED_GRACE_MS = 30000;
  const unstartedSince = new Map();
  function offeredRecovery(run, doc) {
    const list = Array.isArray(doc?.recovery) ? doc.recovery : Array.isArray(run?.recovery) ? run.recovery : null;
    if (!list) return null;
    return [...new Set(list.filter(item => item && Object.hasOwn(RECOVERY_ACTIONS, item.action)).map(item => item.action))];
  }
  // {text, actions} for a campaign that needs recovering, or null.
  function recovery(state, run, doc) {
    const actions = offeredRecovery(run, doc);
    if (actions) {
      // PAUSED is the miner's own choice: its Resume is the header's.
      if (!actions.length || state === "PAUSED") return null;
      if (actions[0] === "retry_interrupted") return {text: RETRY_PRACTICE, actions};
      return {text: RECOVERY_OFFERED[state] || "To move again it needs: " + actions.map(a => RECOVERY_ACTIONS[a]).join(" or ") + ".", actions};
    }
    // Recorded, but its campaign was never created here: no frozen manifest,
    // so nothing ran (the controller stopped before it started).
    const id = run?.id || doc?.campaign?.id;
    if (state === "QUEUED" && run && !run.runtime_revision && !(doc && doc.campaign.runtime_revision)) {
      if (!unstartedSince.has(id)) unstartedSince.set(id, Date.now());
      if (Date.now() - unstartedSince.get(id) < UNSTARTED_GRACE_MS) return null;
      return {text: "Recorded, but never started here: the campaign has no frozen record yet. Reconcile settles it; if it stays queued, Stop it and launch again.", actions: ["reconcile"]};
    }
    unstartedSince.delete(id);
    return RECOVERY[state] ? {text: RECOVERY[state], actions: ["reconcile"]} : null;
  }
  // The recovery line; nothing for a healthy state. With the campaign view,
  // its controls are the header's (and the Live tab's); without it, the line
  // carries its own, so recovery never needs the view.
  function recoveryNote(parent, state, run, doc) {
    const needs = recovery(state, run, doc);
    if (!needs) return null;
    const box = el("div", undefined, "rs-recovery");
    box.setAttribute("role", "status");
    box.append(el("p", "Needs attention · " + words(state).toLowerCase(), "eyebrow"), el("p", needs.text, "status-line"));
    const id = run?.id || doc?.campaign?.id;
    needs.actions.forEach((action, index) => {
      // With the view, only what the header has no control for.
      if (doc && action !== "retry_interrupted") return;
      const b = button(RECOVERY_ACTIONS[action], action === "stop" ? "rs-stop" : index === 0 ? "primary" : "", () => CC.researchAction(id, action));
      b.dataset.action = action;
      b.disabled = !CC.state().connected || CC.state().busy || TERMINAL.includes(state);
      box.append(b);
    });
    parent.append(box);
    return box;
  }
  // The campaign's last refusal (slice C's `last_refusal`), from the view
  // or the campaign record: what was refused, when, and what to do.
  function refusalOf(doc, run) { return CC.lastRefusal(doc, run); }

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
      // The help card sits beside the navigation, never in it: the
      // navigation lists the views and nothing else.
      const rail = el("div", undefined, "rail"); rail.id = "rail";
      nav.parentNode.insertBefore(rail, nav);
      rail.append(nav);
      const help = el("aside", undefined, "rail-help"); help.id = "rail-help";
      help.setAttribute("aria-label", "Help");
      help.append(el("p", "Help", "eyebrow"), el("p", "Stuck? Each step says what it needs, and Details names the code."));
      help.append(anchor("Wiring guide", "#guide", "link"), anchor("Bring your agent", "#connections", "link"));
      help.append(el("p", "DEVELOPMENT · testnet. Practice evidence ≠ qualification.", "rail-help-note"));
      rail.append(help);
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
    // A read the page did not ask for: drawn under the live-region rules.
    if (force) render(); else CC.quietly(render);
  }
  // What a view shows, without the clock: a panel rebuilds only on change.
  function docKey(doc) {
    if (!doc) return "";
    const {tiles, ...rest} = doc;
    return JSON.stringify(rest) + JSON.stringify({...tiles, now_unix: 0, elapsed_seconds: 0});
  }

  // Tab names this page wrote before the research surface (and a few
  // natural ones) still open the tab they meant (LP-PROD-F).
  const ALIASES = {overview: "live", metrics: "experiments", journal: "reasoning", notes: "reasoning", messages: "conversation", outcomes: "submission"};
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(part => { try { return decodeURIComponent(part); } catch (_) { return part; } });
    const named = ALIASES[parts[2]] || parts[2];
    const tab = TABS.some(([name]) => name === named) ? named : "live";
    return {view: parts[0] || "overview", id: parts[1] || "", tab, written: parts[2] || ""};
  }
  // A campaign link names its tab as the research surface does: an alias or
  // a missing tab is rewritten in place, so the address is the one shown.
  function canonical(r) {
    if (r.view !== "campaigns" || !r.id || r.written === r.tab) return;
    const hash = "#campaigns/" + encodeURIComponent(r.id) + "/" + r.tab;
    try { history.replaceState(null, "", hash); } catch (_) { /* the tab still opens */ }
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
    // Compact (the Overview's card): Pause and Stop, and what recovery the
    // state needs, so recovery is never only behind another page.
    const needs = recovery(doc.campaign.state, run, doc)?.actions || [];
    for (const control of doc.controls) {
      if (compact && control.action !== "stop" && control.action !== "pause" && !needs.includes(control.action)) continue;
      const b = button(control.label, control.action === "stop" ? "rs-stop" : needs.includes(control.action) ? "primary" : "", () => CC.researchAction(doc.campaign.id, control.action));
      b.disabled = !control.available || !CC.state().connected || CC.state().busy;
      if (control.reason) b.title = control.reason;
      b.dataset.action = control.action;
      actions.append(b);
    }
    if (compact) actions.append(anchor("Open campaign", CC.campaignHref(doc.campaign.id), "button primary"));
    else actions.append(button("Export", "", () => CC.researchAction(doc.campaign.id, "export")));
    head.append(actions);
    parent.append(head);
    if (doc.fixture) para(parent, "Synthetic fixture data, for seeing the surface. Not a campaign, not evidence, never LIVE.", "rs-fixture");
  }
  // What the header shows, as one key (no clock).
  function headerKey(doc, run, compact) {
    const s = CC.state();
    return JSON.stringify([compact, doc.campaign, doc.labels, doc.fixture, doc.controls, doc.tiles.started_unix, s.connected, s.busy, recovery(doc.campaign.state, run, doc)]);
  }
  function tilesKey(doc) { return JSON.stringify({...doc.tiles, now_unix: 0, elapsed_seconds: doc.tiles.elapsed_seconds === null ? null : 0}); }
  // A refusal and a recovery line, above the campaign's own parts.
  function attention(parent, doc, run, compact) {
    const refusal = refusalOf(doc, run);
    if (refusal) {
      const box = CC.refusalNote(parent, refusal, compact);
      if (box) box.classList.add("rs-refusal");
    }
    recoveryNote(parent, doc ? doc.campaign.state : run.state, run, doc);
  }
  function attentionKey(doc, run) {
    const s = CC.state();
    const state = doc ? doc.campaign.state : run.state;
    return JSON.stringify([refusalOf(doc, run), state, recovery(state, run, doc), Boolean(doc), s.connected, s.busy]);
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
    const runs = el("div");
    if (typeof t.practice_runs.attempted === "number") runs.append(el("span", "completed, of " + t.practice_runs.attempted + " attempted", "hint"));
    runs.append(el("span", t.trials && typeof t.trials.ceiling === "number" ? "Trials used " + t.trials.used + " of your " + t.trials.ceiling : "Trials used " + (t.trials ? t.trials.used : 0) + " · no cap set", "hint"));
    tile("Practice runs", String(t.practice_runs.completed), runs);
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

  // ---- Graphite (OWNER-GRAPHITE-MINER-01, GRAPHITE-MINER-S5). The campaign
  // view's `graphite` block: the mode frozen at launch, the stage now, the
  // plan it builds from (read from the Library by its digest), research
  // against build spend, and the hunt's progress. All text, from the record.
  function graphiteKey(doc) {
    const g = doc.graphite || null;
    const plan = g && typeof g.plan_digest === "string" && g.plan_digest && window.CarbonLibrary ? window.CarbonLibrary.planKey(g.plan_digest) : null;
    return JSON.stringify([g, doc.tiles.spend || null, doc.campaign?.state ?? null, plan]);
  }
  const STAGE_NOUNS = {hunt: "Hunt", plan: "Plan", build: "Build"};
  const STAGE_STATES = {DONE: "done", RUNNING: "running", PENDING: "waiting", STOPPED: "stopped"};
  function nano(value, name = "provider_nanodollars") {
    if (typeof value === "number") return value;
    return value && typeof value === "object" && typeof value[name] === "number" ? value[name] : null;
  }
  function drawGraphite(box, doc) {
    const g = doc.graphite;
    const G = CC.graphite;
    head(box, "Graphite · " + G.modeLabel(g.mode) + " mode", "Carbon's agent");
    para(box, "Now: " + G.now(g.stage, doc.campaign?.state), "status-line rs-graphite-stage");
    const grid = el("dl", undefined, "review-grid rs-graphite");
    const row = (label, value) => { const dd = el("dd"); if (typeof value === "string") dd.textContent = value; else dd.append(...value); grid.append(el("dt", label), dd); return dd; };
    const digest = typeof g.plan_digest === "string" && g.plan_digest ? g.plan_digest : null;
    row("Plan", digest ? [el("code", digest.slice(0, 12) + "…"), " ", anchor("Open the plan", "#library/plans/" + encodeURIComponent(digest))] : g.mode === "RESEARCH" ? "Not written yet: this campaign's Planner writes it" : "None yet: Graphite's Planner writes one first");
    // Each stage the campaign runs, in order, with its state and the code it
    // ended on (a research stage stopped at its share says so).
    const stages = Array.isArray(g.stages) ? g.stages.filter(item => item && typeof item.stage === "string") : [];
    if (stages.length) row("Stages", stages.map(item => (STAGE_NOUNS[item.stage] || words(item.stage)) + ": " + (STAGE_STATES[item.state] || "unknown") + (typeof item.code === "string" && item.code ? " (" + words(item.code) + ")" : "")).join(" · "));
    // Research spend against its share; build spend is the rest of the
    // campaign's model spend. The share narrows only the model ceilings the
    // miner set: with none, it does not bind, and that is said.
    const used = doc.tiles.spend ? doc.tiles.spend.used_nanodollars : null;
    const ceiling = doc.tiles.spend ? doc.tiles.spend.ceiling_nanodollars : null;
    const research = nano(g.research_spent);
    const share = typeof g.research_share === "number" ? g.research_share : null;
    // The cap the share sets, as the campaign states it (research_cap: only
    // the dimensions the miner capped); from the spend ceiling otherwise.
    const stated = g.research_cap && typeof g.research_cap === "object" ? g.research_cap : null;
    const caps = stated ? [nano(stated) !== null ? "up to " + G.usd(nano(stated)) + (typeof ceiling === "number" ? " of your " + G.usd(ceiling) : "") : null, nano(stated, "provider_attempts") !== null ? "up to " + nano(stated, "provider_attempts") + " model calls" : null].filter(Boolean)
      : share !== null && typeof ceiling === "number" && ceiling > 0 ? [G.usd(Math.floor(ceiling * share)) + " of your " + G.usd(ceiling)] : [];
    const shareText = share === null ? "" : " · its share " + Math.round(share * 10000) / 100 + "%" + (caps.length ? " (" + caps.join(" and ") + ")" : " (it narrows only a model-spend or model-call ceiling you set; with neither, it does not bind)");
    row("Research spend", (research === null ? "unavailable" : G.usd(research)) + shareText);
    if (g.mode !== "RESEARCH") row("Build spend", typeof used === "number" && research !== null && used >= research ? G.usd(used - research) : "unavailable");
    const attempts = nano(g.research_spent, "provider_attempts");
    if (attempts !== null) row("Research model calls", String(attempts));
    const hunt = g.hunt && typeof g.hunt === "object" ? g.hunt : null;
    if (hunt) {
      const parts = [];
      if (typeof hunt.fetched === "number") parts.push(hunt.fetched + " found on arXiv");
      if (typeof hunt.deduped === "number") parts.push(hunt.deduped + " already known, not paid for again");
      if (typeof hunt.triaged_out === "number") parts.push(hunt.triaged_out + " set aside at first reading");
      if (typeof hunt.extracted === "number") parts.push(hunt.extracted + " read into your Library");
      if (typeof hunt.reader_calls === "number") parts.push(hunt.reader_calls + " Reader call" + (hunt.reader_calls === 1 ? "" : "s"));
      parts.push("cost " + (typeof hunt.cost_nanodollars === "number" ? G.usd(hunt.cost_nanodollars) : "unavailable"));
      row("Hunt", parts.join(" · "));
      // arXiv unreachable (FAILED_INFRA: the hunt report's boolean, or a
      // count): an infrastructure failure, never a verdict on any paper.
      if (hunt.failed_infra === true || (typeof hunt.failed_infra === "number" && hunt.failed_infra > 0)) {
        const failed = row("arXiv", "Could not be reached, so the hunt ended where it was (literature fetch failed). That is not a verdict on any paper; the Planner went on with the cards you have. Next: hunt again in a later campaign.");
        failed.className = "reason"; failed.dataset.code = "literature_fetch_failed";
      }
    } else row("Hunt", "No hunt in this campaign: it reads the shared pack and your Library.");
    box.append(grid);
    if (digest && window.CarbonLibrary) {
      const read = window.CarbonLibrary.plan(digest);
      const plan = el("div", undefined, "rs-graphite-plan");
      plan.append(el("p", "The plan's first hypotheses", "eyebrow"));
      if (read.doc) window.CarbonLibrary.drawPlan(plan, read.doc, 3);
      else para(plan, read.error ? "The plan could not be read: " + words(read.error) + "." : "Reading the plan…", read.error ? "reason" : "hint");
      box.append(plan);
    }
    para(box, "Graphite runs on your model and key, within your own budget. Its cards are UNCHECKED; its plan is guidance, never evaluation.", "hint");
  }

  // ---- What Reconcile settles (LP-PROD-W2). The campaign view's
  // `reconciliation`: each model call whose outcome is unknown and what
  // Reconcile would book for it, while the campaign awaits reconciliation;
  // each call it settled, why, the charge it booked and any caveat, after.
  // All text from the record, set as text.
  function charge(nano) { return typeof nano === "number" ? money(nano) : "no money figure (this model is not priced)"; }
  function settlement(box, r) {
    if (!r) return;
    head(box, "Model calls whose outcome is unknown", "Reconcile");
    const awaiting = Array.isArray(r.awaiting_settlement) ? r.awaiting_settlement : [];
    const settled = Array.isArray(r.settled) ? r.settled : [];
    if (awaiting.length) {
      para(box, "Reconcile books each of these calls at its full reservation, the most its request could cost, because whether the provider ran it is unknown. It resends nothing: the next call goes out under a fresh identity, with its own reservation.", "status-line");
      const list = el("ul", undefined, "rs-settle");
      for (const call of awaiting) list.append(el("li", String(call.identity) + " · Reconcile books " + charge(call.booked_on_settlement_nanodollars)));
      box.append(list);
    }
    if (settled.length) {
      // A total only of calls booked in money: an unpriced call adds none.
      const priced = settled.some(call => typeof call.booked_nanodollars === "number");
      para(box, "Settled by Reconcile · booked " + charge(priced ? r.booked_nanodollars : null) + " in all", "status-line");
      const list = el("ul", undefined, "rs-settle");
      for (const call of settled) {
        const item = el("li");
        item.append(el("span", String(call.identity) + " · " + words(call.reason).toLowerCase() + " · booked " + charge(call.booked_nanodollars)));
        if (call.caveat) item.append(el("p", call.caveat, "hint rs-caveat"));
        list.append(item);
      }
      box.append(list);
    }
    if (r.accounting) para(box, r.accounting, "hint");
  }

  // ---- Tabs. ----
  function tabLive(panel, doc, run) {
    // The grid's parts are redrawn one by one: a new event redraws Recent
    // events, not the message being written to the agent below it.
    const grid = part(panel, "live", "grid", () => {}, "rs-live", "div");
    const s = CC.state();
    const tab = name => CC.campaignHref(doc.campaign.id, name);
    part(grid, "now", JSON.stringify([doc.current_operation, doc.campaign.state, doc.research_task, doc.hypothesis, doc.controls, s.connected, s.busy, recovery(doc.campaign.state, run, doc)]), now => {
      head(now, "Now", "Current work");
      if (doc.current_operation) para(now, "Running: " + words(doc.current_operation.phase) + " · " + doc.current_operation.id, "status-line");
      else para(now, "Nothing is running. State: " + words(doc.campaign.state).toLowerCase() + ".", "status-line");
      // The research task frozen at launch, exactly, as text (C-MLP-02-D6).
      if (doc.research_task) {
        now.append(el("p", "Frozen research task: " + doc.research_task.text, "frozen-guidance"));
        para(now, "Task identity: " + doc.research_task.digest, "hint");
      }
      if (doc.hypothesis) {
        const quote = el("blockquote", undefined, "rs-quote");
        quote.append(el("p", doc.hypothesis), el("cite", "Latest hypothesis · recorded text, shown as text"));
        now.append(quote);
      }
      // What recovery the state needs is here, first among the controls
      // (LP-PROD-F); why is said once, above the campaign's header.
      // Reconcile is offered here only then.
      const needs = recovery(doc.campaign.state, run, doc)?.actions || [];
      const quick = el("div", undefined, "rs-quick");
      for (const control of doc.controls.filter(c => c.action !== "reconcile" || needs.includes("reconcile"))) {
        const b = button(control.label, needs.includes(control.action) && control.action !== "stop" ? "primary" : "", () => CC.researchAction(doc.campaign.id, control.action));
        b.dataset.action = control.action;
        b.disabled = !control.available || !s.connected || s.busy; if (control.reason) b.title = control.reason;
        quick.append(b);
      }
      quick.append(button("Export", "", () => CC.researchAction(doc.campaign.id, "export")));
      quick.append(anchor("Contract", tab("contract"), "button"));
      now.append(quick);
    });
    // Beside Reconcile: the model calls whose outcome is unknown, what it
    // books for them, and once it has, what it booked (LP-PROD-W2). Kept in
    // place, hidden when there are none, so no other part moves.
    const reconciliation = doc.reconciliation || null;
    part(grid, "settlement", JSON.stringify(reconciliation), box => settlement(box, reconciliation), "rs-panel rs-wide").hidden = !reconciliation;
    const byId = Object.fromEntries(doc.charts.map(c => [c.id, c]));
    part(grid, "trend", JSON.stringify([byId.trend_score || null, byId.trend_components || null]), trend => {
      head(trend, "Practice runs", "Live metrics");
      if (byId.trend_score) chart(trend, byId.trend_score); else para(trend, "No practice run yet. Each completed run adds a point.", "empty-state");
      if (byId.trend_components) chart(trend, byId.trend_components);
    });
    part(grid, "gate-breakdown", JSON.stringify(doc.practice_gate_breakdown || null), box => drawGateBreakdown(box, doc.practice_gate_breakdown), "rs-gate-breakdown rs-panel rs-wide", "section");
    part(grid, "compare", JSON.stringify([byId.components || null, doc.comparison]), compare => {
      head(compare, "This run against the previous", "Experiment output");
      if (byId.components) chart(compare, byId.components);
      metricsTable(compare, doc);
    });
    part(grid, "curve", JSON.stringify([byId.learning_curve || null, doc.learning_curve]), curve => {
      head(curve, "Learning curve", "Training");
      if (byId.learning_curve) chart(curve, byId.learning_curve);
      else para(curve, "Not recorded. " + (doc.learning_curve.basis || ""), "empty-state");
    });
    part(grid, "cases", JSON.stringify(doc.per_case), cases => {
      head(cases, "A public practice case", "Predicted against reference");
      perCase(cases, doc);
    }, "rs-panel rs-wide");
    const ops = doc.events.operations.slice(-8).reverse();
    part(grid, "recent", JSON.stringify(ops), recent => {
      head(recent, "Recent events", "Logs");
      if (!ops.length) para(recent, "No operation recorded yet.", "hint");
      const list = el("ol", undefined, "events");
      for (const op of ops) { const li = el("li"); li.append(el("span", words(op.phase)), el("span", words(op.state).toLowerCase(), "hint")); list.append(li); }
      recent.append(list);
    });
    part(grid, "thoughts", JSON.stringify(doc.journal.entries.slice(0, 5)), thoughts => {
      head(thoughts, "Agent reasoning", "Journal");
      feed(thoughts, doc, 5);
      thoughts.append(anchor("All reasoning and notes", tab("reasoning")));
    });
    // The thread and the composer are separate parts: a reply arriving
    // never replaces the message being written.
    part(grid, "talk", JSON.stringify((doc.conversation?.thread || []).slice(-2)), talk => {
      head(talk, "Talk to your agent", "Conversation");
      thread(talk, doc, 2);
    }, "rs-panel rs-wide");
    part(grid, "compose", JSON.stringify([doc.campaign.id, s.connected]), box => {
      composer(box, doc, true);
      box.append(anchor("The whole conversation", tab("conversation")));
    }, "rs-panel rs-wide rs-compose-part");
  }

  // ---- The conversation with the miner's own agent (RSURF-D12). ----
  function thread(parent, doc, last) {
    const c = doc.conversation;
    if (!c || !c.thread.length) { para(parent, "No messages yet. Write to your agent below; it reads them with carbon_messages.", "hint"); return; }
    const list = el("ol", undefined, "rs-thread");
    for (const message of last ? c.thread.slice(-last) : c.thread) {
      const mine = el("li", undefined, "rs-msg rs-msg-miner");
      const meta = el("p", undefined, "rs-msg-meta");
      meta.append(el("strong", "You"), el("span", "#" + message.sequence + (message.posted_unix ? " · " + when(message.posted_unix) : ""), "hint"));
      // Untrusted text, set as text (RSURF-D5).
      mine.append(meta, el("p", message.text || "", "rs-msg-text"));
      if (message.read_by_carbon_agent === true) mine.append(el("p", "Read by Carbon's agent at a step boundary", "hint rs-msg-read"));
      else if (message.read_by_carbon_agent === false) mine.append(el("p", "Carbon's agent reads it at its next step", "hint rs-msg-read"));
      list.append(mine);
      for (const reply of message.replies) {
        const theirs = el("li", undefined, "rs-msg rs-msg-agent");
        const head = el("p", undefined, "rs-msg-meta");
        head.append(el("strong", reply.by === "carbon_agent" ? "Carbon's agent" : "Your agent"), el("span", "#" + reply.sequence + (reply.by === "carbon_agent" ? " · reply at a step" : " · reply with carbon_note"), "hint"));
        theirs.append(head, el("p", reply.text || "", "rs-msg-text"));
        list.append(theirs);
      }
      if (!message.replies.length) list.append(el("li", "No reply yet.", "rs-msg-wait hint"));
    }
    parent.append(list);
  }
  function composer(parent, doc, compact) {
    const id = "rs-msg-" + doc.campaign.id + (compact ? "-live" : "");
    const form = el("form", undefined, "rs-note rs-compose");
    const label = el("label", "Message to your agent"); label.htmlFor = id;
    const text = el("textarea"); text.id = id; text.rows = compact ? 2 : 3; text.maxLength = NOTE_MAX;
    const send = button("Send", "primary"); send.type = "submit"; send.disabled = !CC.state().connected;
    const result = el("p", "", "hint"); result.setAttribute("aria-live", "polite");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!text.value.trim()) { result.textContent = "Write a message first."; return; }
      send.disabled = true;
      try {
        await CC.api("/api/v1/conversation/" + encodeURIComponent(doc.campaign.id), {text: text.value}, undefined, 10000);
        text.value = ""; CC.sent(text); result.textContent = "Sent.";
        await load(doc.campaign.id, true);
      } catch (error) { result.textContent = "Not sent: " + words(error.message) + "."; }
      finally { send.disabled = false; }
    });
    form.append(label, text, send, result);
    parent.append(form);
    if (!compact) para(parent, doc.conversation.authority, "rs-authority");
  }
  function tabConversation(panel, doc) {
    const c = doc.conversation;
    part(panel, "thread", JSON.stringify([c.total, c.thread]), box => {
      head(box, "You and your agent", c.total + " message" + (c.total === 1 ? "" : "s"));
      thread(box, doc, 0);
    });
    part(panel, "compose", JSON.stringify([doc.campaign.id, CC.state().connected, c.authority]), box => composer(box, doc, false));
    part(panel, "how", JSON.stringify([c.your_agent, c.carbon_agent]), how => {
      head(how, "How your agent reads this", "Any MCP agent");
      const dl = el("dl", undefined, "review-grid");
      dl.append(el("dt", "Read"), el("dd", c.your_agent.read + " (campaign, after, limit): your messages after a cursor, with their replies."));
      dl.append(el("dt", "Reply"), el("dd", c.your_agent.reply));
      dl.append(el("dt", "Carbon's own agent"), el("dd", c.carbon_agent.basis));
      how.append(dl);
      para(how, "Messages and replies are untrusted text: shown as text, never run, and they grant nothing.", "hint");
    });
  }

  // ---- The toolbox (RSURF-D11): read from the Challenge's own records. ----
  function renderToolbox(parent, tb, compact) {
    if (!tb || tb.status === "UNAVAILABLE") { para(parent, "This Challenge's toolbox could not be read.", "empty-state"); return; }
    // Where this campaign runs: CPU, this machine's GPU or the remote GPU,
    // and why a GPU lane is not set up (RSURF-D19). Never hidden.
    if (tb.where) {
      const where = section(parent, "Where this runs", "CPU or GPU");
      const list = el("dl", undefined, "rs-where");
      list.append(el("dt", "Practice"), el("dd", tb.where.practice.label));
      list.append(el("dt", "Code cell"), el("dd", tb.where.code_cell.cpu + (tb.where.code_cell.gpu ? "; or " + tb.where.code_cell.gpu + ", per run" : ". GPU: " + tb.where.code_cell.gpu_reason)));
      for (const [name, label] of [["gpu", "GPU on this machine"], ["remote_gpu", "Your remote GPU"]]) {
        const lane = tb.where.lanes[name];
        list.append(el("dt", label), el("dd", lane.available === true ? "set up" : lane.available === false ? "not set up: " + words(lane.reason) : "could not be read"));
      }
      where.append(list);
      if (tb.where.set_up_gpu) where.append(anchor("Set up a GPU", tb.where.set_up_gpu, "button"));
      para(where, tb.where.validator, "rs-cost");
    }
    const runtimes = section(parent, "Runtimes", "Practice and the validator");
    const grid = el("div", undefined, "rs-runtimes");
    for (const r of tb.runtimes) {
      const box = el("div", undefined, "rs-runtime");
      box.append(el("p", r.id + (r.default ? " · default" : ""), "eyebrow"), el("strong", r.role), el("span", "Families: " + r.families, "hint"));
      if (r.runs_on) box.append(el("span", "This campaign runs it on: " + r.runs_on, "rs-runs-on"));
      if (r.pinned.length) box.append(el("span", "Pinned: " + r.pinned.slice(0, 4).map(d => d.name + " " + d.version).join(", ") + (r.pinned.length > 4 ? " and " + (r.pinned.length - 4) + " more" : ""), "hint"));
      if (r.validator_environment) box.append(el("span", "Validator environment: " + r.validator_environment.environment_id + " " + r.validator_environment.environment_version, "hint"));
      grid.append(box);
    }
    runtimes.append(grid);
    if (tb.execution) para(runtimes, tb.execution, "hint");
    if (tb.campaign_images?.length) para(runtimes, "This campaign's pinned images: " + tb.campaign_images.join(", "), "hint");
    const julia = section(parent, "Julia", "Research only");
    para(julia, tb.julia.role + ". " + (tb.julia.run_julia.available === true ? "run_julia is available on this host." : tb.julia.run_julia.available === false ? "run_julia is not available on this host: " + words(tb.julia.run_julia.reason) + "." : "Whether run_julia runs here could not be read."), "status-line");
    if (tb.julia.capability) para(julia, "Capability " + tb.julia.capability.id + ": " + words(tb.julia.capability.status) + " · blocker " + words(tb.julia.capability.blocker) + " (" + tb.julia.authority + "). " + (tb.julia.capability.summary || ""), "hint");
    const work = section(parent, "Workspace tools", "Your agent calls these");
    const wrap = el("div", undefined, "table-wrap"); const table = el("table", undefined, "metrics-table rs-tools");
    const head = el("tr"); for (const n of ["Tool", "What it does", "Here", compact ? null : "Limits", compact ? null : "MCP"].filter(Boolean)) head.append(el("th", n)); table.append(head);
    for (const t of tb.workspace) {
      const row = el("tr");
      row.append(el("td", t.id), el("td", t.description || ""), el("td", t.available === true ? "yes" : t.available === false ? "no · " + words(t.reason) : "unknown"));
      if (!compact) row.append(el("td", t.limits || "none"), el("td", t.mcp.tool + " kind=workspace action=" + t.id));
      table.append(row);
    }
    wrap.append(table); work.append(wrap);
    para(work, "Workspace tools appear after " + (tb.workspace[0]?.mcp.needs || "attach") + ". Carbon sets no limits on your own research; only your own budget binds.", "hint");
    const flow = section(parent, "Workflow", "Validate to submit");
    const steps = el("ol", undefined, "rs-list");
    for (const s of tb.workflow) { const li = el("li"); li.append(el("strong", s.label + ": "), el("span", s.description || ""), el("span", " · " + s.mcp.join(", "), "rs-mcp")); steps.append(li); }
    flow.append(steps);
    const families = section(parent, "Rebuildable model families", "And their backend");
    const fl = el("ul", undefined, "rs-list");
    for (const f of tb.families) { const li = el("li"); li.append(el("strong", f.selector || f.id), el("span", " · " + f.backend, "hint")); fl.append(li); }
    families.append(fl);
    const validator = section(parent, "What the validator rebuilds with", "Exam environment");
    para(validator, tb.validator.plain);
    const more = el("details"); more.append(el("summary", "Details"), el("pre", JSON.stringify(tb.validator.details, null, 2), "rs-pre"));
    validator.append(more);
    if (!compact) {
      const agent = section(parent, "Tell your agent", "MCP");
      para(agent, tb.agent.operations);
      para(agent, "Research tools after " + tb.agent.attach + ": " + tb.agent.research_tools.join(", "), "rs-mcp");
    }
    para(parent, tb.basis, "hint");
  }
  // The working toolbox first (RSURF-D15), then what each tool is.
  // The working bench is one persistent element (research_tools.js): it is
  // moved in once and never redrawn by a refresh.
  function tabTools(panel, doc) {
    const bench = part(panel, "bench", doc.campaign.id, () => {}, "rs-bench-slot", "div");
    if (window.CarbonTools) window.CarbonTools.mount(bench, doc);
    part(panel, "toolbox", JSON.stringify(doc.toolbox), box => renderToolbox(box, doc.toolbox, false), "rs-toolbox-part", "div");
  }
  // A Toolbox on each Challenge card, read when opened.
  function decorateChallengeCards() {
    const s = CC.state();
    if (!s.connected) return;
    for (const card of document.querySelectorAll("#challenge-catalog [data-challenge]")) {
      if (card.querySelector(".rs-toolbox")) continue;
      const box = el("details", undefined, "rs-toolbox");
      box.append(el("summary", "Toolbox"));
      const body = el("div", undefined, "detail-body");
      box.append(body);
      box.addEventListener("toggle", async () => {
        if (!box.open || body.dataset.loaded) return;
        body.dataset.loaded = "1";
        body.replaceChildren(el("p", "Reading the toolbox…", "hint"));
        try {
          const tb = await CC.api("/api/v1/operations/toolbox", {challenge: card.dataset.challenge}, undefined, 20000);
          body.replaceChildren(); renderToolbox(body, tb, true);
        } catch (error) { body.replaceChildren(el("p", "Not available: " + words(error.message) + ". It needs a runner profile on this controller.", "hint")); body.dataset.loaded = ""; }
      });
      // Before the card's own Details, which stays its last disclosure (the
      // machine code a status sentence stands for).
      const own = [...card.querySelectorAll(":scope > details")].pop();
      if (own) card.insertBefore(box, own); else card.append(box);
      // Its construction levels (LAUNCHPAD-LEVELS-01 S1), read when opened:
      // one generic table, the same for every level and every Challenge.
      const levels = el("details", undefined, "rs-ladder");
      levels.append(el("summary", "Construction levels"));
      const levelsBody = el("div", undefined, "detail-body");
      levels.append(levelsBody);
      levels.addEventListener("toggle", async () => {
        if (!levels.open || levelsBody.dataset.loaded) return;
        levelsBody.dataset.loaded = "1";
        levelsBody.replaceChildren(el("p", "Reading the construction levels…", "hint"));
        try {
          const view = await CC.api("/api/v1/operations/ladder", {challenge: card.dataset.challenge}, undefined, 20000);
          levelsBody.replaceChildren(); renderLadder(levelsBody, view);
        } catch (error) { levelsBody.replaceChildren(el("p", "Not available: " + words(error.message) + ". It needs a runner profile on this controller.", "hint")); levelsBody.dataset.loaded = ""; }
      });
      if (own) card.insertBefore(levels, own); else card.append(levels);
    }
  }
  // A Challenge's construction levels, read only (LAUNCHPAD-LEVELS-01 S1).
  // Every level is drawn by the same code from the same keys.
  function renderLadder(parent, view) {
    if (!view || view.status === "UNAVAILABLE") { para(parent, "The construction levels could not be read" + (view?.reason ? ": " + words(view.reason) : "") + ".", "hint"); return; }
    para(parent, view.status === "ON_LADDER" ? "On the ladder at Level " + view.ladder.level + "; chosen level: " + (view.ladder.chosen === null ? "none yet" : view.ladder.chosen) + "." : "Not yet on the construction ladder.", "lede");
    para(parent, view.read_only, "hint");
    para(parent, view.audience_basis, "hint");
    const wrap = el("div", undefined, "table-wrap"); const table = el("table", undefined, "metrics-table");
    const head = el("tr"); for (const n of ["Level", "State", "For", "Variant", "Capabilities", "Left out", "Compute budget"]) head.append(el("th", n)); table.append(head);
    for (const row of view.levels) {
      const tr = el("tr");
      const level = el("td"); level.append(el("strong", String(row.level)), el("span", " " + row.text, "hint"));
      const variant = row.variant ? row.variant.name + (row.variant.refusal ? " · " + words(row.variant.refusal) : "") + (row.arms.length ? " · arms: " + row.arms.map(a => a.arm).join(", ") : "") : (row.variant_refusal ? words(row.variant_refusal) : "–");
      const caps = el("td");
      if (row.capabilities.length) {
        const box = el("details"); box.append(el("summary", String(row.capabilities.length)));
        const list = el("ul", undefined, "rs-list");
        for (const c of row.capabilities) {
          const li = el("li"); li.append(el("strong", c.id), el("span", " " + (c.summary || ""), "hint"));
          for (const w of c.widened) li.append(el("span", " Widened by " + w.variant + (w.arm ? " (arm " + w.arm + ")" : "") + ": " + JSON.stringify(w.surface) + " " + JSON.stringify(w.bounds), "hint"));
          if (c.proposal) li.append(el("span", " Bounds: " + c.proposal.bounds, "hint"));
          list.append(li);
        }
        box.append(list); caps.append(box);
      } else caps.textContent = "none";
      const left = el("td");
      if (row.left_out.length) { const box = el("details"); box.append(el("summary", String(row.left_out.length))); const list = el("ul", undefined, "rs-list"); for (const t of row.left_out) list.append(el("li", t)); box.append(list); left.append(box); } else left.textContent = "–";
      const budget = row.compute_budget.status === "SET" ? row.compute_budget.value + " " + row.compute_budget.unit : words(row.compute_budget.status);
      tr.append(level, el("td", words(row.state)), el("td", words(row.audience)), el("td", variant), caps, left, el("td", budget));
      table.append(tr);
    }
    wrap.append(table); parent.append(wrap);
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
    // A chosen case redraws its part: the choice is made, so the select lets
    // go of it, and the new select takes focus back once drawn.
    select.addEventListener("change", () => { entry.practiceCase = select.value; entry.refocus = true; CC.sent(select); select.blur(); load(doc.campaign.id, true); });
    if (entry.refocus) { entry.refocus = false; setTimeout(() => select.focus(), 0); }
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
  // What a journey form (practice, or freeze and submit) is drawn from: it is
  // redrawn when one of these moves, never on a clock. Typed fields are
  // drafts, restored when it is.
  function journeyKey(run, which) {
    const s = CC.state();
    const status = CC.watchStatus(run);
    // A request held under its key (its answer lost) shows with Discard.
    const held = CC.heldOperation(run.id, which === "practice" ? ["practice"] : ["freeze_candidate", "submit"]);
    // Whether its Challenge can be evaluated now: the Submission form says so.
    const evaluation = which === "submission" && CC.evaluationFor ? CC.evaluationFor(run) : null;
    return JSON.stringify([which, run.id, run.state, run.journey || null, (run.experiments || []).map(e => e.recipe || null), Boolean(s.launchOptions), s.connected, s.busy, status ? [status.kind, status.text] : null, held, evaluation]);
  }
  function tabExperiments(panel, doc, run) {
    if (run && run.selects === "miner" && CC.renderJourneyPractice) part(panel, "journey", journeyKey(run, "practice"), box => CC.renderJourneyPractice(box, run), "rs-journey-part", "div");
    part(panel, "runs", JSON.stringify([doc.experiments, doc.charts, doc.declaration?.components || null, (doc.toolbox?.runtimes || []).find(r => r.default)?.id || null]), box => drawExperiments(box, doc));
  }
  function drawGateBreakdown(box, breakdown) {
    head(box, "Practice gate failures", "Local campaign");
    if (!breakdown || breakdown.status === "UNAVAILABLE_PUBLIC_GATE_LIST") {
      para(box, "Per-gate counts are unavailable because this Challenge has no registered public gate list here.", "hint");
      return;
    }
    if (breakdown.status === "NO_TRIALS") {
      para(box, "No practice trials recorded yet. No gate outcome has been measured.", "hint");
      return;
    }
    para(box, breakdown.checked_trials + " of " + breakdown.exported_trials + " trials have usable summaries; " + breakdown.unverified_trial_summaries + " are missing, incomplete, or contradictory. " + breakdown.trials_passing_all_gates + " trial summaries report passing every practice gate.", "hint");
    if (breakdown.status === "INSUFFICIENT_VERIFIED_SUMMARIES") para(box, "No trial summary is usable. Reported failure counts below may include contradictory feedback.", "reason");
    const wrap = el("div", undefined, "table-wrap");
    const table = el("table", undefined, "metrics-table");
    const labels = el("tr");
    for (const label of ["Gate", "Trials failed", "Cases failed"]) labels.append(el("th", label));
    table.append(labels);
    for (const [name, counts] of Object.entries(breakdown.gate_failures || {})) {
      const row = el("tr");
      row.append(el("td", words(name)), el("td", String(counts.trials)), el("td", String(counts.cases)));
      table.append(row);
    }
    wrap.append(table); box.append(wrap);
    if (breakdown.unrecognized_gate_names) para(box, breakdown.unrecognized_gate_names + " unrecognized gate name(s) were withheld.", "hint");
    para(box, "Counts use your local public PRACTICE summaries. One trial may fail more than one gate; this does not change a gate or the exam.", "hint");
  }
  function drawExperiments(box, doc) {
    const rows = doc.experiments.rows.slice().reverse();
    head(box, "Practice runs", doc.experiments.total + " recorded");
    if (!rows.length) { para(box, "No practice run has completed in this campaign.", "empty-state"); return; }
    const keys = Object.keys(rows[0].components || {});
    const labels = Object.fromEntries((doc.declaration?.components || []).map(c => [c.key, c.label]));
    const wrap = el("div", undefined, "table-wrap");
    const table = el("table", undefined, "metrics-table");
    const headRow = el("tr");
    for (const name of ["Run", "Model", "Gates", "Score", ...keys.map(k => labels[k] || k), "Final loss", "Compute budget", "Framework", "Ran on"]) headRow.append(el("th", name));
    table.append(headRow);
    const fallback = (doc.toolbox?.runtimes || []).find(r => r.default)?.id;
    for (const r of rows) {
      const row = el("tr");
      row.append(el("td", String(r.index)), el("td", r.backbone || "–"), el("td", r.eligible === true ? "passed" : r.eligible === false ? "failed" : "–"), el("td", fmt(r.score)));
      for (const k of keys) row.append(el("td", fmt(r.components[k])));
      // What the run actually ran on: its recipe's framework (or the
      // Challenge's default) and the worker record's backend and image.
      row.append(el("td", fmt(r.fit.final_loss)), el("td", (CC.budgetLine && CC.budgetLine(r.budget_status)) || "–"), el("td", r.framework || (fallback ? fallback + " (default)" : "default")), el("td", [r.ran_on || (r.backend ? words(r.backend).toLowerCase() : null), r.image].filter(Boolean).join(" · ") || "–"));
      table.append(row);
    }
    wrap.append(table); box.append(wrap);
    para(box, "Descriptive practice on public cases. Not an accepted improvement, a rank or an official score.", "hint");
    const byId = Object.fromEntries(doc.charts.map(c => [c.id, c]));
    for (const id of ["trend_score", "trend_components", "components"]) if (byId[id]) chart(box, byId[id]);
  }
  function tabReasoning(panel, doc) {
    part(panel, "compose", JSON.stringify([doc.campaign.id, CC.state().connected]), compose => noteForm(compose, doc));
    part(panel, "journal", JSON.stringify([doc.journal.total, doc.journal.entries, doc.journal.basis]), box => {
      head(box, "Reasoning and notes", doc.journal.total + " entries");
      para(box, doc.journal.basis, "hint");
      feed(box, doc);
    });
    const outcomes = part(panel, "outcomes", JSON.stringify(doc.journal.epoch_outcomes), box => {
      head(box, "Epoch outcomes", "Agent or miner reported");
      for (const o of doc.journal.epoch_outcomes) para(box, "Epoch " + o.epoch + ": " + words(o.status) + " · selected by " + (o.selected_by === "miner" ? "you" : "the agent") + (o.reason ? " · " + o.reason : "") + ". Reported, not independent science.");
    });
    outcomes.hidden = !doc.journal.epoch_outcomes.length;
  }
  function noteForm(compose, doc) {
    head(compose, "Add to the journal", "carbon_note");
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
        text.value = ""; CC.sent(text, kind); count.textContent = "0 / " + NOTE_MAX; result.textContent = "Posted.";
        await load(doc.campaign.id, true);
      } catch (error) { result.textContent = "Not posted: " + words(error.message) + "."; }
      finally { post.disabled = false; }
    });
    form.append(kindLabel, kind, textLabel, text, count, post, result);
    compose.append(form);
  }
  // The read-only tabs are one part each, keyed by what they draw.
  function tabContract(panel, doc) {
    part(panel, "contract", JSON.stringify(doc.contract), box => drawContract(box, doc), "rs-contract-part", "div");
  }
  function drawContract(panel, doc) {
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
    const cl = c.construction_level;
    fact("Construction level", cl.level === null ? "Not yet defined. " + cl.basis : ["Level " + cl.level, cl.text, cl.state && words(cl.state), cl.audience && words(cl.audience)].filter(Boolean).join(" · ") + ". " + (cl.basis || ""));
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
    part(panel, "artifacts", JSON.stringify([doc.candidates, doc.experiments.rows.map(r => [r.index, r.backbone, r.recipe || null])]), box => drawArtifacts(box, doc), "rs-artifacts-part", "div");
  }
  function drawArtifacts(panel, doc) {
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
    // The journey's freeze and submit form, then the outcomes: two parts, so
    // an outcome arriving never redraws the form (or a reason being typed).
    const evaluation = run && CC.evaluationFor ? CC.evaluationFor(run) : null;
    const journey = part(panel, "journey", run && run.selects === "miner" ? journeyKey(run, "submission") : JSON.stringify([doc.campaign.selects, evaluation]), box => {
      if (run && run.selects === "miner" && CC.renderJourneySubmission) CC.renderJourneySubmission(box, run);
      else if (doc.campaign.selects === "agent") {
        para(box, "Carbon's agent freezes and submits in this campaign.", "hint");
        // Whether its Challenge can be evaluated today, as the miner's form says.
        if (run && CC.evaluationNote) CC.evaluationNote(box, run);
      }
    }, "rs-journey-part", "div");
    journey.hidden = !journey.children.length;
    part(panel, "outcomes", JSON.stringify(doc.outcomes), box => drawOutcomes(box, doc), "rs-outcomes-part", "div");
  }
  function drawOutcomes(panel, doc) {
    const box = section(panel, "DEVELOPMENT outcomes", "Validator");
    if (!doc.outcomes.length) para(box, "No DEVELOPMENT outcome yet.", "empty-state");
    for (const o of doc.outcomes) {
      const r = o.result || {};
      const s = r.screening || {};
      const line = [typeof o.epoch === "number" ? "Epoch " + o.epoch : "Outcome", words(o.status).toLowerCase()];
      if (r.state) line.push(words(r.state).toLowerCase());
      if (typeof s.eligible === "boolean") line.push(s.eligible ? "eligible" : "not eligible");
      if (Array.isArray(s.gates_failed)) line.push("gates failed: " + (s.gates_failed.join(", ") || "none"));
      if (typeof s.score === "number") line.push("score " + fmt(s.score));
      if (r.disposition) line.push(words(r.disposition).toLowerCase());
      if (typeof r.accepted_development_improvement === "boolean") line.push("accepted DEVELOPMENT improvement: " + r.accepted_development_improvement);
      para(box, line.join(" · "), "status-line");
      if (r.withheld) para(box, "Withheld: " + r.withheld, "hint");
      if (r.feedback_mode && r.feedback_mode !== "FULL") para(box, "Shown through the frozen feedback mode " + r.feedback_mode + ".", "hint");
    }
    para(box, "DEVELOPMENT only: no qualification, reward, rank or chain write.", "hint");
  }
  function tabLogs(panel, doc, run) {
    part(panel, "logs", JSON.stringify([doc.events, run?.usage || null]), box => drawLogs(box, doc, run), "rs-logs-part", "div");
  }
  function drawLogs(panel, doc, run) {
    const box = section(panel, "Operations", doc.events.total + " recorded");
    const list = el("ol", undefined, "events");
    for (const op of doc.events.operations.slice().reverse()) { const li = el("li"); li.append(el("span", words(op.phase)), el("span", words(op.state).toLowerCase(), "hint"), el("code", op.id)); list.append(li); }
    if (!doc.events.operations.length) para(box, "No operation recorded.", "hint");
    box.append(list);
    para(box, "Provider payloads, worker output and errors stay private to the campaign; this shows operation states only.", "hint");
    const usage = run && run.usage;
    const res = section(panel, "Resources", "Your ledger");
    if (!usage) { para(res, "Appears once the campaign ledger exists.", "hint"); return; }
    // Every column in the unit your limit is set in (LP-PROD-F).
    CC.usageTable(res, usage);
    para(res, usage.cost_basis || "", "hint");
  }
  function tabSettings(panel, doc) {
    part(panel, "settings", docKey(doc), box => drawSettings(box, doc), "rs-settings-part", "div");
  }
  function drawSettings(panel, doc) {
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
  const TAB_DRAW = {live: tabLive, conversation: tabConversation, experiments: tabExperiments, reasoning: tabReasoning, tools: tabTools, contract: tabContract, artifacts: tabArtifacts, submission: tabSubmission, logs: tabLogs, settings: tabSettings};
  // The campaign page is a fixed frame of parts, made once per campaign:
  // back, notice, attention (a refusal and the recovery its state needs),
  // header, tiles, stages, tabs and the tab's own parts (LP-PROD-F). Each is
  // redrawn alone when what it shows changed and nothing holds it.
  function detail(container, run) {
    const r = route();
    canonical(r);
    const entry = viewState(run.id);
    load(run.id);
    const s = CC.state();
    if (container.dataset.frame !== run.id) {
      container.replaceChildren();
      container.dataset.frame = run.id; container.dataset.run = run.id; container.dataset.key = "";
      container.append(anchor("← All campaigns", "#campaigns", "rs-back"));
    }
    const doc = entry.doc;
    part(container, "notice", JSON.stringify([Boolean(doc), entry.error || null, s.connected]), box => {
      if (!doc) para(box, entry.error ? "The campaign view could not be read: " + words(entry.error) + ". " + (s.connected ? "It is read again shortly." : "Reconnect this browser.") : "Reading the campaign view…", entry.error ? "reason" : "hint");
      else if (entry.error) para(box, "Showing the last view read; the newest read failed: " + words(entry.error) + ".", "reason");
    }, "rs-notice", "div");
    // A refusal and a recovery line come first, and stay in reach even when
    // the campaign view cannot be read: Reconcile is drawn from the campaign's
    // own state then.
    part(container, "attention", attentionKey(doc, run), box => attention(box, doc, run, false), "rs-attention", "div");
    if (!doc) {
      part(container, "fallback", JSON.stringify([run.id, run.state, s.connected, s.busy, recovery(run.state, run, null)]), box => fallbackControls(box, run), "rs-fallback", "div");
      return;
    }
    part(container, "fallback", "", () => {}, "rs-fallback", "div");
    part(container, "head", headerKey(doc, run, false), box => header(box, doc, run, false), "rs-head-part", "div");
    part(container, "tiles", tilesKey(doc), box => tiles(box, doc), "rs-tiles-part", "div");
    updateClock(container, doc);
    part(container, "stages", JSON.stringify(doc.stages), box => stages(box, doc), "rs-stages-part", "div");
    // Always in the frame, hidden for a campaign without Graphite, so no
    // other part moves when it appears.
    part(container, "graphite", graphiteKey(doc), box => { if (doc.graphite) drawGraphite(box, doc); }, "rs-panel rs-graphite-part", "section").hidden = !doc.graphite;
    part(container, "nav", JSON.stringify([run.id, r.tab]), box => {
      for (const [name, label] of TABS) {
        const link = anchor(label, CC.campaignHref(run.id, name), "");
        if (name === r.tab) link.setAttribute("aria-current", "page");
        box.append(link);
      }
    }, "tabs", "nav").setAttribute("aria-label", "Campaign sections");
    // A new tab is a new panel; within one tab, its parts redraw alone.
    let panel = null;
    for (const child of container.children) if (child.dataset.part === "panel") panel = child;
    if (!panel || panel.dataset.tab !== r.tab) {
      const fresh = el("section", undefined, "tab-panel rs-tab"); fresh.dataset.part = "panel"; fresh.dataset.tab = r.tab;
      if (panel) panel.replaceWith(fresh); else container.append(fresh);
      panel = fresh;
    }
    TAB_DRAW[r.tab](panel, doc, run);
  }
  // When the campaign view cannot be read, its controls still can be: the
  // campaign's own state decides which are offered.
  function fallbackControls(box, run) {
    const s = CC.state();
    const done = TERMINAL.includes(run.state);
    const row = el("div", undefined, "rs-quick");
    // What recovery the state needs is the recovery line's own.
    const needs = recovery(run.state, run, null)?.actions || [];
    for (const [action, label, offered] of [["pause", "Pause", !done && !["PAUSED", "PAUSE_REQUESTED"].includes(run.state)], ["resume", "Resume", ["PAUSED", "INTERRUPTED"].includes(run.state)], ["stop", "Stop", !done], ["reconcile", "Reconcile", !done], ["export", "Export", true]]) {
      if (!offered || needs.includes(action)) continue;
      const b = button(label, "", () => CC.researchAction(run.id, action));
      b.dataset.action = action;
      b.disabled = !s.connected || s.busy;
      row.append(b);
    }
    para(box, "Campaign " + run.id + " · " + words(run.state).toLowerCase() + ". Its controls work without the view.", "hint");
    box.append(row);
  }
  function updateClock(container, doc) {
    if (!doc) return;
    const node = container.querySelector('[data-tile="elapsed"]');
    if (node && typeof doc.tiles.elapsed_seconds === "number") CC.setText(node, duration(doc.tiles.elapsed_seconds + Math.max(0, Math.round((Date.now() - viewState(doc.campaign.id).at) / 1000))));
  }

  // ---- Launchpad: the configured setup, then launch. ----
  function strip() {
    const target = $("launchpad-strip");
    if (!target) return;
    const s = CC.state();
    if (!s.connected || !s.caps) { CC.rebuild(target, "disconnected", node => node.append(el("p", "Connect this browser to see your setup.", "hint"))); return; }
    const setup = s.setupState || {};
    const steps = setup.steps || {};
    const entry = CC.challengeEntry(s.wizard.challenge);
    const agent = CC.agentEntry(s.wizard.agentChoice);
    const choiceName = (step, id) => (setup.choices?.[step] || []).find(c => c.id === id)?.display_name || words(id);
    // The budget in the units it was set in: dollars, minutes, megabytes.
    const parts = CC.budgetParts(s.composition.budget || {});
    const problem = CC.launchProblem();
    // Agent first, as setup is: who researches decides whether Inference
    // applies. Your own agent (own-agent) uses its own model and skips it,
    // as does a launch that calls no model.
    const j = CC.journey ? CC.journey() : null;
    const skipsInference = Boolean(j?.skipped?.inference) || Boolean(agent && !agent.uses_model);
    const cards = [
      {id: "challenge", title: "Challenge", value: entry ? entry.title + " · v" + entry.version : "Not chosen", note: entry ? (entry.selectable ? "Ready to launch" : "Set up first") : "Choose what to mine", go: () => CC.goWizard("challenge")},
      {id: "agent", title: "Agent", value: steps.agent?.checked ? choiceName("agent", steps.agent.choice) : agent ? agent.label : "Not chosen", note: agent ? (agent.launch_agent === "graphite" ? "Graphite · " + CC.graphite.summary() : agent.uses_model ? "Carbon's agent calls your model" : "Calls no model") : j?.skipped?.inference ? "Your own agent, with its own model" : "Who researches and submits", href: "#setup/agent"},
    ];
    if (!skipsInference) cards.push({id: "inference", title: "Inference", value: steps.inference?.checked ? choiceName("inference", steps.inference.provider_id) + " · " + steps.inference.model_id : "Not checked", note: "Only Carbon's own agent calls a model, with your key", href: "#setup/inference"});
    cards.push(
      {id: "compute", title: "Compute", value: steps.compute?.checked ? choiceName("compute", steps.compute.choice) : (s.caps.compute?.choices?.[0]?.label || "Not checked"), note: "Your machine, or your own remote one", href: "#setup/compute"},
      {id: "limits", title: "Limits", value: parts.length ? parts.join(", ") : "None set", note: "Your own campaign ledger. Carbon caps and bills nothing.", go: () => CC.goWizard("limits")},
      {id: "review", title: "Review", value: problem ? "Not ready" : "Ready", note: problem || "Every step can pass.", href: "#setup/review"},
    );
    const key = JSON.stringify([cards.map(c => [c.value, c.note]), problem, s.busy, s.pendingResearch ? 1 : 0]);
    CC.rebuild(target, key, node => drawStrip(node, cards, problem, s));
  }
  function drawStrip(target, cards, problem, s) {
    const head = el("div", undefined, "panel-heading");
    head.append(el("h2", "Launch a new campaign"), el("span", "Agent first · your accounts", "eyebrow"));
    target.append(head);
    const list = el("ol", undefined, "rs-strip");
    list.style.setProperty("--cards", String(cards.length));
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
    const launch = button(s.pendingResearch ? "Retry the launch with these choices" : "Launch campaign", "primary go", () => CC.launch());
    launch.id = "rs-launch";
    launch.disabled = Boolean(problem) || s.busy;
    actions.append(launch);
    // An unconfirmed launch can be let go of here too (LP-PROD-F).
    if (s.pendingResearch) {
      const discard = button("Discard the unconfirmed launch", "", () => CC.discardLaunch());
      discard.id = "rs-launch-discard"; discard.disabled = s.busy;
      actions.append(discard);
    }
    actions.append(button("Save as template", "", () => CC.goWizard("limits")));
    target.append(actions);
    if (s.pendingResearch) target.append(el("p", "Your last launch was not confirmed. Retrying sends these choices under the same request key, so a launch already recorded is never started twice. If it was recorded, it is under My Campaigns.", "reason"));
    if (problem) target.append(el("p", problem, "reason"));
    target.append(el("p", "Launch is the same launch operation, with the same checks: your registration is read first, and a lost response is retried, never duplicated.", "hint"));
  }
  // The Overview's active campaign: a heading and the same parts as its page
  // (attention, header, tiles, stages), each redrawn alone.
  function activePanel() {
    const target = $("active-campaign");
    if (!target) return;
    const s = CC.state();
    const live = s.connected ? s.research.runs.filter(run => !TERMINAL.includes(run.state)) : [];
    if (!live.length) { target.hidden = true; target.dataset.frame = ""; return; }
    const run = live[0];
    load(run.id);
    const doc = viewState(run.id).doc;
    target.hidden = false;
    if (target.dataset.frame !== run.id) {
      target.replaceChildren(el("h2", "Active campaign", "section-title"));
      target.dataset.frame = run.id;
    }
    const box = part(target, "active", run.id, () => {}, "panel rs-active", "div");
    part(box, "reading", String(Boolean(doc)), node => { if (!doc) para(node, "Reading the campaign view…", "hint"); }, "rs-reading", "div");
    part(box, "attention", attentionKey(doc, run), node => attention(node, doc, run, true), "rs-attention", "div");
    if (!doc) return;
    part(box, "head", headerKey(doc, run, true), node => header(node, doc, run, true), "rs-head-part", "div");
    part(box, "tiles", tilesKey(doc), node => tiles(node, doc), "rs-tiles-part", "div");
    updateClock(box, doc);
    part(box, "stages", JSON.stringify(doc.stages), node => stages(node, doc), "rs-stages-part", "div");
  }

  function render() {
    try { strip(); activePanel(); } catch (error) { console.error(error); }
    const r = route();
    if (r.view === "campaigns" && r.id) CC.renderCampaigns();
  }

  setupShell();
  window.CarbonResearch = {detail, render, TABS};
  CC.onRender(() => { try { strip(); activePanel(); decorateChallengeCards(); } catch (error) { console.error(error); } });
  render();
})();
