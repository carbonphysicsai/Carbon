"use strict";
(() => {
  let token = "";
  let selected = "";
  let runs = [];
  let pending = null;
  let busy = false;
  let polling = false;
  let connected = false;
  let landed = false;
  let developmentSources = [];
  let research = {preflight: {available: false}, runs: []};
  let pendingResearch = null;
  const expandedResearch = new Set();
  // The Control Center's capability document: every choice this page offers is
  // rendered from it, with its real availability. Never a static list.
  let caps = null;
  // Bumped on each read, so the views built from it rebuild only then.
  let capsVersion = 0;
  const CAPS_SCHEMA = "carbon.control-center.capabilities.v1";
  // Every launch-time choice with its true availability, from the options
  // operation - the same one an MCP client reads.
  let launchOptions = null;
  // The one launch composition. The no-limits and set-limits paths edit this
  // same object, templates save and load it, and the launch body is built from
  // it; there is no second copy to disagree with. `agent` stays null until the
  // person or a template chooses, so a default is never mistaken for a choice.
  let composition = {agent: null, budget: {}};
  let launchPath = "quick";
  let launchShape = null;
  // The wizard's own choices. Persisted in this browser (never a token or key).
  let wizard = {step: "challenge", challenge: null, agentChoice: null, provider: null, model: null};
  const STEPS = [["challenge", "Challenge"], ["agent", "Agent"], ["model", "Model"], ["compute", "Compute"], ["limits", "Tools & limits"], ["review", "Review"], ["launch", "Launch"]];
  const TABS = [["overview", "Overview"], ["experiments", "Experiments"], ["metrics", "Metrics"], ["journal", "Research Journal"], ["artifacts", "Artifacts"], ["submission", "Submission"], ["logs", "Logs"], ["settings", "Settings"]];
  const TERMINAL = ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE", "EXPIRED"];
  const templateKey = "carbon.launchpad.launch-templates.v1";
  const wizardKey = "carbon.control-center.wizard.v1";
  const draftKey = "carbon.control-center.journey-drafts.v1";
  const routeKey = "carbon.control-center.route.v1";
  const researchKey = "carbon.launchpad.pending-research.v1";
  const pendingKey = "carbon.launchpad.pending.v1";
  let storageError = false;
  try { pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null"); pendingResearch = JSON.parse(sessionStorage.getItem(researchKey) || "null"); }
  catch (_) { storageError = true; }
  // Local conveniences only: a refused storage never blocks the page.
  function stored(key, fallback) {
    try { const value = JSON.parse(localStorage.getItem(key) || "null"); return value && typeof value === "object" && !Array.isArray(value) ? value : fallback; }
    catch (_) { return fallback; }
  }
  function store(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; } }
  // What a person has typed into a campaign's journey, kept across reloads.
  const journeyDrafts = stored(draftKey, {});
  {
    const saved = stored(wizardKey, null);
    if (saved) {
      wizard = {...wizard, ...saved};
      if (saved.budget && typeof saved.budget === "object") composition = {...composition, budget: saved.budget};
      if (saved.launchPath === "advanced") launchPath = "advanced";
    }
  }
  function saveWizard() { store(wizardKey, {...wizard, budget: composition.budget, launchPath}); }
  const $ = id => document.getElementById(id);
  const message = (text, error = false) => {
    $("message").textContent = text;
    $("message").className = error ? "message error" : "message";
  };
  function words(value) { return String(value ?? "").replaceAll("_", " "); }
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function researchNote(parent, text, className = "") {
    const note = document.createElement("p"); note.textContent = text; note.className = className; parent.append(note);
  }
  // An unavailable thing, shown as such (LINKONLY-D10): one plain sentence,
  // one link to the place that fixes it, and its code and full next action
  // behind Details.
  function unavailableNote(parent, item, extra = []) {
    const plain = item.plain || {sentence: "Unavailable: " + words(item.reason) + ".", next: null};
    parent.append(el("p", plain.sentence, "status-line"));
    if (plain.next) parent.append(link(plain.next, "button fix"));
    details(parent, "Details", [item.reason ? "Code: " + item.reason : null, item.next_action ? "Next: " + item.next_action : null, ...extra]);
  }
  function link(go, className = "link") {
    const anchor = el("a", go.label, className); anchor.href = go.href; return anchor;
  }
  function pill(text, kind = "") { return el("span", text, ("pill " + kind).trim()); }
  function details(parent, summary, lines) {
    const box = el("details"); box.append(el("summary", summary));
    const body = el("div", undefined, "detail-body");
    for (const line of lines.filter(Boolean)) body.append(typeof line === "string" ? el("p", line) : line);
    box.append(body); parent.append(box);
    return box;
  }
  function card(parent, title, tag, kind) {
    const box = el("div", undefined, "integration card");
    const head = el("div", undefined, "card-head");
    head.append(el("h3", title));
    if (tag) head.append(pill(tag, kind));
    box.append(head); parent.append(box);
    return box;
  }
  // Rebuild a region only when what it shows changed, keeping open Details
  // open: a person reading one is never collapsed by the 1.5 s refresh.
  function rebuild(target, key, build) {
    if (target.dataset.key === key) return;
    const open = new Set([...target.querySelectorAll("details[open]")].map(node => node.dataset.key));
    target.replaceChildren();
    build(target);
    [...target.querySelectorAll("details")].forEach((node, index) => { node.dataset.key = String(index); node.open = open.has(String(index)); });
    target.dataset.key = key;
  }
  // A command the miner runs, with a button that copies it.
  function copyRow(parent, label, command, id) {
    const row = el("div", undefined, "copy-row");
    if (label) row.append(el("p", label));
    const line = el("div", undefined, "copy-line");
    const code = el("code", command);
    const button = el("button", "Copy"); button.type = "button"; button.className = "copy";
    if (id) button.id = id;
    button.setAttribute("aria-label", "Copy " + (label || "this command"));
    button.addEventListener("click", async () => {
      let copied = false;
      try { await navigator.clipboard.writeText(code.textContent); copied = true; } catch (_) { copied = false; }
      if (!copied) {
        // Without clipboard access the command is selected, ready to copy.
        const range = document.createRange(); range.selectNodeContents(code);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
        try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      }
      button.textContent = copied ? "Copied" : "Selected";
      setTimeout(() => { button.textContent = "Copy"; }, 1600);
    });
    line.append(code, button); row.append(line); parent.append(row);
    return code;
  }
  // The wiring guide's text data (guide.py), rendered as text: never HTML.
  function renderSpans(parent, spans) {
    for (const span of spans || []) {
      let node;
      if (span.code) node = el("code", span.text);
      else if (span.anchor) { node = el("a", span.text); node.href = "#guide/" + span.anchor; }
      else if (span.strong) node = el("strong", span.text, /^UNVERIFIED/.test(span.text) ? "unverified" : undefined);
      else node = document.createTextNode(span.text);
      if (span.strong && (span.code || span.anchor)) { const strong = el("strong"); strong.append(node); node = strong; }
      parent.append(node);
    }
  }
  function renderList(ordered, items) {
    const list = el(ordered ? "ol" : "ul");
    for (const item of items) {
      const entry = el("li"); renderSpans(entry, item.text);
      if (item.items?.length) entry.append(renderList(item.ordered, item.items));
      list.append(entry);
    }
    return list;
  }
  function renderBlocks(parent, blocks) {
    for (const block of blocks || []) {
      if (block.type === "heading") {
        const heading = el(block.level <= 2 ? "h2" : "h3"); heading.dataset.anchor = "guide/" + block.anchor;
        renderSpans(heading, block.text); parent.append(heading);
      } else if (block.type === "paragraph") { const p = el("p"); renderSpans(p, block.text); parent.append(p); }
      else if (block.type === "list") parent.append(renderList(block.ordered, block.items));
      else if (block.type === "table") {
        const wrap = el("div", undefined, "guide-table-wrap"); const table = el("table", undefined, "guide-table");
        const head = el("tr"); for (const cell of block.header) { const th = el("th"); renderSpans(th, cell); head.append(th); }
        table.append(head);
        for (const row of block.rows) { const tr = el("tr"); for (const cell of row) { const td = el("td"); renderSpans(td, cell); tr.append(td); } table.append(tr); }
        wrap.append(table); parent.append(wrap);
      }
    }
  }
  // Carbon holds no key: the miner's own `carbon-miner-signer` signs. Each
  // way reaching it can fail is its own code and its own correction.
  const SIGNER_HELP = {
    signer_not_running: "your signer is not running. Start `carbon-miner-signer --wallet NAME --hotkey HOTKEY` in a terminal and leave it open",
    signer_refused: "your signer declined the request; its terminal shows why",
    signer_wrong_hotkey: "the signer running holds a different hotkey than this profile's registered miner",
    signer_timeout: "your signer did not answer in time. Check its terminal",
    signer_invalid_signature: "your signer returned a signature that does not verify for this hotkey",
    signer_protocol: "something other than carbon-miner-signer answered on the signer socket"
  };
  async function api(path, body, key, timeout = 5000) {
    const headers = {Authorization: "Bearer " + token};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (key) headers["Idempotency-Key"] = key;
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeout), cache: "no-store", redirect: "error"
    });
    const result = await response.json();
    if (!response.ok) {
      const code = result.error || "request_failed";
      const error = new Error(SIGNER_HELP[code] ? code + ": " + SIGNER_HELP[code] : code);
      error.status = response.status;
      // A setup refusal names its field and, when there is one, the next step.
      error.field = result.field || null;
      error.nextStep = result.next_step || null;
      throw error;
    }
    return result;
  }

  // ---- Routing. One view at a time; a campaign has its own deep link. ----
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    const views = [...document.querySelectorAll("main > .view")].map(view => view.id);
    return {view: views.includes(parts[0]) ? parts[0] : "overview", id: parts[1] || "", tab: TABS.some(([name]) => name === parts[2]) ? parts[2] : "overview"};
  }
  function show() {
    const current = route();
    for (const view of document.querySelectorAll("main > .view")) view.hidden = view.id !== current.view;
    for (const link of document.querySelectorAll("#tool-nav a")) {
      if (link.getAttribute("href") === "#" + current.view) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (location.hash) store(routeKey, {hash: location.hash});
    render();
    // Setup shows one step at a time; #setup/<step> names it.
    if (current.view === "setup") applySetupStep();
  }
  window.addEventListener("hashchange", show);
  // The navigation is built from the page's own views: a view marked data-nav
  // is listed, and nothing else can be, so the two cannot drift. Development
  // diagnostics are listed apart, under their own label.
  function buildNavigation() {
    const nav = $("tool-nav");
    const primary = document.createElement("ul");
    const development = document.createElement("ul"); development.className = "nav-development";
    for (const section of document.querySelectorAll("[data-nav]")) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = "#" + section.id; link.textContent = section.dataset.nav;
      item.append(link);
      (section.dataset.navGroup === "development" ? development : primary).append(item);
    }
    const label = el("p", "Development", "nav-label");
    nav.replaceChildren(primary, label, development);
  }

  // ---- Rendering. ----
  function render() {
    renderOnboarding();
    renderDevelopment();
    renderOverview();
    renderCatalogs();
    renderCampaigns();
    renderWizard();
    if (route().view === "guide") renderGuide(route().id);
    $("settings-recheck").disabled = !connected || busy;
    // Connected: the token form steps aside; interrupted or new, it returns.
    $("connect-panel").hidden = connected;
  }
  // ---- The wiring guide, served by this controller (LINKONLY-D10). ----
  let guideDoc = null;
  let guideLoading = null;
  let guideAnchor = null;
  async function renderGuide(anchor) {
    const body = $("guide-body");
    if (!connected) { body.replaceChildren(el("p", "Connect this browser to read the guide.", "hint")); body.dataset.built = ""; return; }
    if (!guideDoc) {
      guideLoading ||= api("/api/v1/guide/remote-setup").then(value => { guideDoc = value; }, error => { body.replaceChildren(el("p", "The guide could not be read: " + error.message, "reason")); }).finally(() => { guideLoading = null; });
      await guideLoading;
      if (!guideDoc) return;
    }
    if (body.dataset.built !== "1") {
      body.replaceChildren();
      if (!guideDoc.available) body.append(el("p", "This checkout has no guide at " + guideDoc.source + ".", "reason"));
      else { $("guide-heading").textContent = guideDoc.title; renderBlocks(body, guideDoc.blocks); }
      body.dataset.built = "1";
    }
    // Scroll once per anchor, not on every refresh.
    if (anchor && anchor !== guideAnchor) document.querySelector('[data-anchor="guide/' + CSS.escape(anchor) + '"]')?.scrollIntoView();
    guideAnchor = anchor || null;
  }
  function renderDevelopment() {
    const sources = $("development-sources");
    sources.replaceChildren();
    if (!connected || !developmentSources.length) {
      const note = document.createElement("p"); note.className = "hint";
      note.textContent = connected ? "No historical DEVELOPMENT source is attached. Current research campaigns are under Campaigns." : "Reconnect to verify current source state.";
      sources.append(note);
    }
    if (connected) for (const source of developmentSources) {
      const box = document.createElement("div"); box.className = "integration";
      const title = document.createElement("h3");
      title.textContent = source.receipt ? source.receipt.disposition : "Readback unavailable";
      const note = document.createElement("p");
      note.textContent = source.receipt ? "DEVELOPMENT EVALUATION · Receipt " + source.receipt.receipt_id : "Source validation failed. No receipt or result is being inferred.";
      const button = document.createElement("button"); button.type = "button";
      button.textContent = "Export verified public receipt";
      button.disabled = busy || source.status !== "VERIFIED_SOURCE";
      button.addEventListener("click", async () => {
        if (busy || !connected) return;
        busy = true; render();
        try {
          const fresh = await api("/api/v1/development/" + source.id);
          if (fresh.status !== "VERIFIED_SOURCE") throw new Error("development_source_unavailable");
          download(fresh, "carbon-development-" + source.id + ".json");
        } catch (error) { message("Receipt export unavailable: " + error.message, true); }
        finally { busy = false; await refresh(); render(); }
      });
      box.append(title, note, button); sources.append(box);
    }
    $("launch-fields").disabled = !connected || storageError;
    $("launch-button").disabled = busy;
    $("launch-button").firstChild.textContent = pending ? "Retry same launch " : "Launch rehearsal ";
    $("steps").disabled = Boolean(pending);
    $("seconds").disabled = Boolean(pending);
    const picker = $("run-picker");
    picker.replaceChildren();
    for (const run of runs) {
      const option = document.createElement("option");
      option.value = run.id;
      option.textContent = run.id.slice(0, 10) + " · " + run.state;
      picker.append(option);
    }
    const run = runs.find(r => r.id === selected) || runs[0];
    $("empty").hidden = Boolean(run);
    $("run-detail").hidden = !run;
    picker.hidden = !run;
    $("picker-label").hidden = !run;
    if (!run) return;
    selected = run.id;
    picker.value = selected;
    $("run-id").textContent = run.id;
    $("run-state").textContent = run.state;
    $("run-steps").textContent = run.steps + " / " + run.spec.max_steps;
    $("progress").max = run.spec.max_steps;
    $("progress").value = run.steps;
    $("deadline").textContent = "Fixed deadline: " + new Date(run.deadline * 1000).toLocaleString();
    $("pause").disabled = !connected || busy || !["QUEUED", "RUNNING"].includes(run.state);
    $("resume").disabled = !connected || busy || !["PAUSED", "INTERRUPTED"].includes(run.state);
    $("stop").disabled = !connected || busy || !["QUEUED", "RUNNING", "PAUSED", "INTERRUPTED"].includes(run.state);
    $("export").disabled = !connected || busy;
    const events = $("events");
    events.replaceChildren();
    for (const event of run.events.slice(-30).reverse()) {
      const item = document.createElement("li");
      const at = document.createElement("time");
      at.textContent = new Date(event.at * 1000).toLocaleTimeString();
      const kind = document.createElement("span");
      kind.textContent = event.kind.replaceAll("_", " ");
      item.append(at, kind);
      events.append(item);
    }
  }
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: "application/json"}));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = name;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Registration. The panel exists because the endpoints were reachable and the
  // page was not: a human with no agent could not begin the journey at all.
  function onboardingLine(text, kind) {
    const node = document.createElement("p");
    node.className = kind === "error" ? "notice" : "hint";
    node.textContent = text;
    return node;
  }

  function showOnboarding(nodes) {
    const target = $("onboarding-result");
    target.replaceChildren(...nodes);
  }

  function renderOnboarding() {
    for (const control of ["onboarding-address", "onboarding-status",
                           "onboarding-prepare", "onboarding-confirm"]) {
      $(control).disabled = !connected || busy;
    }
    if (!connected) {
      $("onboarding-facts").replaceChildren();
      showOnboarding([onboardingLine(
        "Connect this browser to read the current registration requirements. "
        + "Registration itself needs no Carbon account - this page just needs "
        + "its local session token."
      )]);
    }
  }

  async function onboardingRequirements() {
    try {
      const value = await api("/api/v1/onboarding/requirements");
      // The network this controller registers on, always in view.
      $("network-pill").textContent = (String(value.network).includes("test") ? "Testnet" : words(value.network)) + " · netuid " + value.netuid;
      const facts = $("onboarding-facts");
      facts.replaceChildren();
      // The cost is shown as Carbon actually knows it. NOT_READ is a different
      // claim from unknown, and neither is a figure to plan around.
      const rows = [
        ["Network", value.network + " · netuid " + value.netuid],
        ["Mechanism", value.mechanism],
        ["Recycle amount", value.cost && value.cost.value === "NOT_READ"
          ? "Not read by Carbon — your wallet shows it at signing"
          : String((value.cost || {}).value)],
        ["Carbon signs", "Never"]
      ];
      for (const [label, detail] of rows) {
        const key = document.createElement("dt");
        key.textContent = label;
        const definition = document.createElement("dd");
        definition.textContent = detail;
        facts.append(key, definition);
      }
      const listed = [
        ["You need", value.you_need || []],
        ["Carbon never", value.carbon_never || []]
      ];
      for (const [label, items] of listed) {
        const key = document.createElement("dt");
        key.textContent = label;
        facts.append(key);
        for (const item of items) {
          const definition = document.createElement("dd");
          definition.textContent = item;
          facts.append(definition);
        }
      }
      return value;
    } catch (error) {
      showOnboarding([onboardingLine("Could not read the registration requirements: " + error.message, "error")]);
      return null;
    }
  }

  async function onboardingCall(action) {
    if (busy || !connected) return;
    const address = $("onboarding-address").value.trim();
    if (!address) {
      showOnboarding([onboardingLine("Enter the hotkey address you want to register.", "error")]);
      return;
    }
    try {
      const value = await api("/api/v1/onboarding/" + action, {address});
      const lines = [];
      if (action === "status" || action === "confirm") {
        lines.push(onboardingLine(
          value.registered
            ? "Registered. UID " + value.uid + " at block " + (value.observed_block ?? "unknown") + "."
            : "Not registered on netuid " + value.netuid + " yet."
        ));
        lines.push(onboardingLine("Research environment: " + value.research_environment));
        if (action === "confirm" && value.registered && value.confirmed) {
          // Registered: setup opens at its next step, and reads the chain
          // again itself.
          const begun = await setupCall("begin", {address});
          location.hash = begun ? "#setup/inference" : "#setup/register";
        }
      } else {
        lines.push(onboardingLine("Prepared an UNSIGNED " + value.extrinsic + ". Carbon has not signed and will not submit it."));
        lines.push(onboardingLine("Execute it in " + value.execute_in + ". The recycle amount comes from your coldkey."));
      }
      showOnboarding(lines);
    } catch (error) {
      // Refusals carry a reason and a next action; show both rather than a
      // generic failure, because the reason is what tells a miner what to do.
      showOnboarding([onboardingLine(error.message, "error")]);
    }
  }

  // ---- Environment setup (C-MLP-03): six steps, one at a time. ----
  // OWNER-MINER-COMPUTE-LINK-ONLY-01, LINKONLY-D10: the miner's path is the
  // same six steps on Overview and here. A step is done only when the
  // controller confirmed it: registration by its chain read, each check by its
  // live check, the signer by the Agent step's handshake, the last step by a
  // campaign on record.
  const SETUP_STEPS = [
    ["signer", "Start your signer", "Your signer holds your hotkey on this machine. Carbon never sees your key."],
    ["register", "Register on the subnet", "Your hotkey must be registered on the subnet. You sign that in your own wallet."],
    ["inference", "Inference", "Choose the model your agent calls, with your own key."],
    ["compute", "Compute", "Choose where practice runs: this machine, or a GPU you run elsewhere."],
    ["agent", "Agent", "Choose who researches. This step also checks your signer."],
    ["review", "Review and launch", "Carbon writes your runner profile and loads it. Then you choose a Challenge."],
  ];
  const SETUP_IDS = SETUP_STEPS.map(([id]) => id);
  const STATE_LABEL = {done: "Done", next: "Next", waiting: "Waiting"};
  // Per-browser conveniences only: never a token, key or address.
  const signerSeenKey = "carbon.control-center.signer-started.v1";
  const whereKey = "carbon.control-center.where.v1";
  let setupState = null;
  let setupRead = false;
  let setupVersion = 0;
  let setupStepShown = null;
  function setupLine(text, kind) { const line = el("p", text, kind === "error" ? "reason" : ""); return line; }
  async function readSetup() {
    if (!connected) return;
    try { setupState = await api("/api/v1/setup"); }
    catch (_) { setupState = null; }
    setupVersion++;
    renderSetup();
    render();
  }
  async function setupCall(step, body, timeout = 60000) {
    try {
      const result = await api("/api/v1/setup/" + step, body, undefined, timeout);
      // Carbon rents no compute (OWNER-MINER-COMPUTE-LINK-ONLY-01): when the
      // compute check deleted Carbon's copy of a rented-GPU key, it says so.
      const removed = step === "compute" ? result.steps?.compute?.check?.retired_compute_key : null;
      $("setup-result").replaceChildren(setupLine(step === "review" ? (result.attached ? "Profile written and loaded. Choose a Challenge to launch." : "Profile written. A different profile is already loaded here, so restart the controller to use this one.") : step === "begin" ? "Registration confirmed. Set up inference, compute and agent next." : "Checked: " + step + "." + (removed ? " " + removed : "")));
      // The written profile changes what can launch: read it again now.
      if (step === "review") { try { await readCapabilities(); } catch (_) { /* re-read on request */ } }
      await readSetup();
      if (step === "review") refresh();
      return true;
    } catch (error) {
      const text = (error.field ? error.field.replaceAll("_", " ") + ": " : "") + words(error.message) + (error.nextStep ? ". Next: " + error.nextStep : "");
      $("setup-result").replaceChildren(setupLine(text, "error"));
      return false;
    }
  }
  // Where the miner is on the path, from what the controller confirmed.
  function journey() {
    const steps = setupState?.steps || {};
    const registered = Boolean(setupState?.registered_hotkey);
    const sendPending = Boolean(steps.compute?.checked && steps.compute.check?.next_step);
    const profile = Boolean(caps?.profile?.configured);
    const done = {
      signer: Boolean(steps.agent?.checked),
      register: registered,
      inference: Boolean(steps.inference?.checked),
      compute: Boolean(steps.compute?.checked) && !sendPending,
      agent: Boolean(steps.agent?.checked),
      review: research.runs.length > 0,
    };
    const ready = done.inference && done.compute && done.agent;
    // A signer is confirmed only by the Agent step; until then a started one
    // waits for that check rather than holding the miner at step 1.
    const signerSeen = Boolean(stored(signerSeenKey, null));
    const state = {};
    for (const id of SETUP_IDS) {
      if (done[id]) state[id] = "done";
      else if (id === "signer") state[id] = registered || signerSeen ? "waiting" : "next";
      else if (id === "register") state[id] = "next";
      else if (id === "review") state[id] = (registered && ready) || profile ? "next" : "waiting";
      else state[id] = registered ? "next" : "waiting";
    }
    const current = SETUP_IDS.find(id => state[id] === "next") || null;
    return {state, done, current, registered, ready, profile, sendPending, steps};
  }
  function stepTitle(id, j) {
    if (id === "review" && j.profile && !j.done.review) return "Choose a Challenge and launch";
    return SETUP_STEPS.find(([step]) => step === id)[1];
  }
  function shortKey(value) { return value ? value.slice(0, 6) + "…" + value.slice(-4) : ""; }
  // A setup choice by the name setup offers it under, not its id.
  function choiceName(step, id) {
    return (setupState?.choices?.[step] || []).find(choice => choice.id === id)?.display_name || words(id);
  }
  // What a checked step holds, in plain words.
  function checkedText(id, steps) {
    if (id === "inference") return choiceName("inference", steps.inference.provider_id) + " · " + steps.inference.model_id;
    if (id === "compute") return choiceName("compute", steps.compute.choice) + (steps.compute.remote_machine ? " · " + steps.compute.remote_machine.destination + " (" + steps.compute.remote_machine.transport + ")" : "");
    return choiceName("agent", steps.agent.choice);
  }
  function stepSentence(id, j) {
    const state = j.state[id];
    const steps = j.steps;
    if (id === "signer") return state === "done" ? "Your signer answered for your registered hotkey." : state === "next" ? "Start carbon-miner-signer in your own terminal and leave it open." : "Leave it running. Carbon checks it at step 5.";
    if (id === "register") return state === "done" ? "Registered: " + shortKey(setupState.registered_hotkey) + "." : "Confirm your hotkey is registered on the subnet.";
    if (state === "waiting" && id !== "review") return "Opens once your registration is confirmed.";
    if (id === "inference") return state === "done" ? "Checked: " + checkedText(id, steps) + "." : "Choose a provider and model, and check your key.";
    if (id === "compute") return state === "done" ? "Checked: " + checkedText(id, steps) + "." : j.sendPending ? "Send your worker to your machine." : "Choose where practice runs.";
    if (id === "agent") return state === "done" ? "Checked: " + checkedText(id, steps) + ", and your signer answered." : "Choose your agent. This checks your signer.";
    if (state === "done") return "Campaigns on record: " + research.runs.length + ".";
    if (state === "waiting") return "Opens when steps 3 to 5 are done.";
    return j.profile ? "Your profile is loaded. Pick a Challenge that is ready." : "Write your profile, then choose a Challenge.";
  }
  function stepHref(id, j) {
    if (id === "review" && j.profile) return j.done.review ? "#launch" : "#challenges";
    return "#setup/" + id;
  }
  function reachable(id, j) { return id === "signer" || id === "register" || j.registered; }
  // Why Next cannot be taken from this step yet, or null.
  function nextProblem(id, j) {
    if (id === "signer") return null;
    if (id === "register") return j.registered ? null : "Confirm your registration first.";
    if (id === "compute" && j.sendPending) return "Send your worker first.";
    if (["inference", "compute", "agent"].includes(id)) return j.done[id] ? null : "Run this step's check first.";
    return null;
  }
  function setupTarget() {
    const j = journey();
    const current = route();
    let wanted = current.view === "setup" && SETUP_IDS.includes(current.id) ? current.id : setupStepShown || j.current || "review";
    if (!reachable(wanted, j)) wanted = j.state.signer === "next" ? "signer" : "register";
    return wanted;
  }
  // Show one step: its heading, progress, done state, Back and Next.
  function applySetupStep() {
    const body = $("setup-body");
    const panels = body.querySelectorAll("[data-step-panel]");
    const j = journey();
    const id = setupTarget();
    // A result belongs to the step it came from.
    if (setupStepShown && setupStepShown !== id) $("setup-result").replaceChildren();
    setupStepShown = id;
    const index = SETUP_IDS.indexOf(id);
    for (const panel of panels) panel.hidden = panel.dataset.stepPanel !== id;
    const [, title, lede] = SETUP_STEPS[index];
    $("setup-eyebrow").textContent = "Set up · Step " + (index + 1) + " of " + SETUP_STEPS.length;
    $("setup-heading").textContent = id === "review" ? stepTitle(id, j) : title;
    $("setup-lede").textContent = lede;
    const progress = $("setup-progress");
    progress.replaceChildren();
    SETUP_STEPS.forEach(([step, label], position) => {
      const item = el("li", undefined, "is-" + j.state[step]);
      const button = el("button"); button.type = "button";
      button.append(el("span", String(position + 1).padStart(2, "0"), "wp-num"), el("span", label));
      button.disabled = !connected || !setupState || !reachable(step, j);
      if (step === id) button.setAttribute("aria-current", "step");
      button.setAttribute("aria-label", "Step " + (position + 1) + ": " + label + " · " + STATE_LABEL[j.state[step]]);
      button.addEventListener("click", () => { location.hash = "#setup/" + step; });
      item.append(button); progress.append(item);
    });
    const ready = connected && Boolean(setupState);
    progress.hidden = !ready;
    $("setup-nav").hidden = !ready;
    $("setup-back").disabled = index === 0;
    const problem = nextProblem(id, j);
    $("setup-next").hidden = index === SETUP_STEPS.length - 1;
    $("setup-next").disabled = Boolean(problem);
    $("setup-next").textContent = index < SETUP_STEPS.length - 1 ? "Next: " + SETUP_STEPS[index + 1][1] : "Next";
    $("setup-next-reason").textContent = problem || "";
  }
  $("setup-back").addEventListener("click", () => {
    const index = SETUP_IDS.indexOf(setupStepShown);
    if (index > 0) location.hash = "#setup/" + SETUP_IDS[index - 1];
  });
  $("setup-next").addEventListener("click", () => {
    const index = SETUP_IDS.indexOf(setupStepShown);
    // Moving on from step 1 says the signer is started; it is still checked
    // at the Agent step.
    if (setupStepShown === "signer") store(signerSeenKey, {started: true});
    if (index < 0 || index >= SETUP_IDS.length - 1 || nextProblem(setupStepShown, journey())) return;
    location.hash = "#setup/" + SETUP_IDS[index + 1];
  });
  function setupField(form, name, labelText, type = "text") {
    const id = "setup-" + form.dataset.step + "-" + name;
    const label = el("label", labelText); label.htmlFor = id;
    const input = document.createElement("input");
    input.id = id; input.name = name; input.type = type; input.autocomplete = "off"; input.spellcheck = false;
    form.append(label, input);
    return input;
  }
  function setupSelect(form, name, labelText, options) {
    const id = "setup-" + form.dataset.step + "-" + name;
    const label = el("label", labelText); label.htmlFor = id;
    const select = document.createElement("select"); select.id = id; select.name = name;
    for (const [value, text] of options) { const option = el("option", text); option.value = value; select.append(option); }
    form.append(label, select);
    return select;
  }
  // One wizard step's panel, with its done state when the controller has one.
  function stepPanel(parent, id, doneText) {
    const panel = el("section", undefined, "setup-step"); panel.dataset.stepPanel = id;
    if (doneText) { const done = el("p", undefined, "step-done"); done.append(pill("Done", "pill-done"), el("span", doneText)); panel.append(done); }
    parent.append(panel);
    return panel;
  }
  function stepForm(parent, step) {
    const form = document.createElement("form"); form.dataset.step = step;
    parent.append(form);
    return form;
  }
  function advanced(parent, summary = "Advanced") {
    const box = el("details", undefined, "advanced"); box.append(el("summary", summary));
    const body = el("div", undefined, "detail-body"); body.dataset.step = parent.dataset.step;
    box.append(body); parent.append(box);
    return body;
  }
  function costNote(form, choice) {
    if (!choice) return;
    researchNote(form, "Cost: " + choice.cost_basis, "hint");
    researchNote(form, "Live check: " + choice.live_check, "hint");
  }
  async function confirmRegistration(address) {
    if (busy || !connected) return;
    const result = $("setup-result");
    if (!address) { result.replaceChildren(setupLine("Enter the hotkey address you registered.", "error")); return; }
    try {
      const value = await api("/api/v1/onboarding/confirm", {address});
      if (value.registered && value.confirmed) {
        if (await setupCall("begin", {address})) location.hash = "#setup/inference";
        return;
      }
      const line = el("p", "Not registered on netuid " + value.netuid + " yet. Prepare the unsigned registration under Wallet & Identity, sign it in your own wallet, then check again.", "reason");
      result.replaceChildren(line, link({label: "Wallet & Identity", href: "#wallet"}));
    } catch (error) {
      result.replaceChildren(setupLine(error.message, "error"));
    }
  }
  function renderSetup() {
    const body = $("setup-body");
    if (!connected) { body.replaceChildren(el("p", "Connect this browser to begin.", "hint")); applySetupStep(); return; }
    if (!setupState) {
      body.replaceChildren(el("p", "Setup is off on this controller: start it with a state directory (the installer does).", "reason"));
      applySetupStep();
      return;
    }
    const offered = setupState.choices || {inference: [], compute: [], agent: []};
    const steps = setupState.steps || {};
    const j = journey();
    body.replaceChildren();

    // 1. Start your signer.
    const signer = stepPanel(body, "signer", j.done.signer ? "Your signer answered for your registered hotkey." : null);
    signer.append(el("p", "Start it in your own terminal and leave it open:", "step-lede"));
    copyRow(signer, null, offered.signer?.command || "carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>", "setup-signer-copy");
    researchNote(signer, "Use your own wallet and hotkey names. Carbon never asks for your key or its password.", "hint");
    if (!j.done.signer) researchNote(signer, "Carbon checks it at step 5, Agent.", "hint");

    // 2. Register on the subnet: confirmed here, prepared under Wallet.
    const register = stepPanel(body, "register", j.registered ? "Registered: " + setupState.registered_hotkey : null);
    if (!j.registered) {
      register.append(el("p", "Paste your hotkey address. Carbon reads the chain to confirm it is registered.", "step-lede"));
      const label = el("label", "Your hotkey address (ss58)"); label.htmlFor = "setup-register-address";
      const address = el("input"); address.id = "setup-register-address"; address.type = "text"; address.autocomplete = "off"; address.spellcheck = false; address.placeholder = "5...";
      address.value = $("onboarding-address").value.trim();
      const confirm = el("button", "Check my registration", "primary go"); confirm.type = "button"; confirm.id = "setup-register-confirm";
      confirm.addEventListener("click", () => confirmRegistration(address.value.trim()));
      const action = el("div", undefined, "step-action"); action.append(confirm);
      register.append(label, address, action);
      researchNote(register, "Not registered yet? Wallet & Identity prepares the unsigned call; you sign it in your own wallet, paid from your coldkey.", "hint");
      register.append(link({label: "Register under Wallet & Identity", href: "#wallet"}));
      // What opens once registration is confirmed.
      register.append(el("p", "What happens next", "eyebrow"));
      const next = el("ol", undefined, "guide-steps");
      next.start = 3;
      for (const [, title, lede] of SETUP_STEPS.slice(2)) { const item = el("li"); item.append(el("strong", title + ": "), lede); next.append(item); }
      register.append(next);
    }

    // 3. Inference.
    const inferencePanel = stepPanel(body, "inference", steps.inference?.checked ? "Checked: " + checkedText("inference", steps) + "." : null);
    const inference = stepForm(inferencePanel, "inference");
    const provider = setupSelect(inference, "provider_id", "Provider", offered.inference.map(c => [c.id, c.display_name]));
    const model = setupField(inference, "model_id", "Model id");
    // A generic adapter has no endpoint of its own: the miner names it here,
    // with an optional declared price (nanodollars per token). Without one the
    // spend is stated as unknown and no money ceiling can be set.
    const generic = el("div"); generic.dataset.step = "inference"; inference.append(generic);
    const endpoint = setupField(generic, "endpoint", "Endpoint URL (https, the full completion route)");
    const priceBox = advanced(generic, "Your price (optional)");
    researchNote(priceBox, "Nanodollars per token, the date you read it and where.", "hint");
    const declared = {};
    for (const [name, label, type] of [["input_nano", "Input", "number"], ["cached_input_nano", "Cached input", "number"], ["output_nano", "Output (including reasoning)", "number"], ["observed", "Observed (YYYY-MM-DD)", "text"], ["note", "Where this price comes from", "text"]]) {
      declared[name] = setupField(priceBox, name, label, type);
    }
    const key = setupField(inference, "key", "API key (entered once; leave empty to keep the stored key)", "password");
    researchNote(inference, "Written once to an owner-only file on this machine, never shown again, and sent only to this provider.", "hint");
    const inferenceCost = el("div"); inference.append(inferenceCost);
    const describeProvider = () => {
      const choice = offered.inference.find(c => c.id === provider.value);
      inferenceCost.replaceChildren();
      if (choice) researchNote(inferenceCost, "Billed by " + choice.display_name + " to your account. Carbon bills nothing.", "hint");
      const listed = (choice?.models || []).map(m => m.model_id);
      const about = details(inferenceCost, "About this provider", []);
      const aboutBody = about.querySelector(".detail-body");
      costNote(aboutBody, choice);
      if (choice) researchNote(aboutBody, "Price: " + choice.pricing, "hint");
      researchNote(aboutBody, (listed.length ? "Models: " + listed.join(", ") + " (" : "Models: (") + (choice?.model_policy || "") + ")", "hint");
      generic.hidden = !choice?.needs_endpoint;
      if (!model.value) model.value = (choice?.models || []).find(m => m.default)?.model_id || listed[0] || "";
    };
    const inferenceSpec = () => {
      const choice = offered.inference.find(c => c.id === provider.value);
      const spec = {provider_id: provider.value, model_id: model.value.trim()};
      if (!choice?.needs_endpoint) return spec;
      spec.endpoint = endpoint.value.trim();
      if (Object.values(declared).some(input => input.value.trim())) {
        spec.declared_pricing = {};
        for (const [name, input] of Object.entries(declared)) {
          const value = input.value.trim();
          spec.declared_pricing[name] = input.type === "number" && value !== "" && /^\d+$/.test(value) ? Number(value) : value;
        }
      }
      return spec;
    };
    // Consent is to a quoted amount: the server states the check's maximum
    // cost for this model, the miner ticks to agree to that amount, and only
    // that amount is sent. Nothing is ticked by default, and any change of
    // provider or model clears the agreement.
    const agree = document.createElement("input");
    agree.type = "checkbox"; agree.id = "setup-inference-consent"; agree.checked = false;
    const agreeLabel = el("label", "Quoting the cost of this check..."); agreeLabel.htmlFor = agree.id;
    const agreeRow = el("div", undefined, "consent"); agreeRow.append(agree, agreeLabel);
    inference.append(agreeRow);
    const check = el("button", "Check with my key (billed to me)", "primary"); check.disabled = true;
    inference.append(check);
    let quote = null, quoting = 0;
    const requote = async () => {
      const mine = ++quoting;
      quote = null; agree.checked = false; check.disabled = true; agree.disabled = true;
      const wanted = inferenceSpec();
      if (!wanted.model_id) { agreeLabel.textContent = "Choose a model to see what this check costs."; return; }
      if (wanted.endpoint === "") { agreeLabel.textContent = "Enter your endpoint to see what this check costs."; return; }
      try {
        const answer = await api("/api/v1/setup/quote", wanted, undefined, 15000);
        if (mine !== quoting) return;
        quote = answer; agree.disabled = false;
        agreeLabel.textContent = "I agree to this charge on my own account: " + answer.statement;
      } catch (error) {
        if (mine !== quoting) return;
        agreeLabel.textContent = "No quote: " + (error.field ? error.field + ": " : "") + words(error.message);
      }
    };
    agree.addEventListener("change", () => { check.disabled = !(agree.checked && quote); });
    provider.addEventListener("change", () => { model.value = ""; describeProvider(); requote(); });
    model.addEventListener("change", requote);
    for (const input of [endpoint, ...Object.values(declared)]) input.addEventListener("change", requote);
    if (steps.inference?.checked) {
      provider.value = steps.inference.provider_id; model.value = steps.inference.model_id;
      endpoint.value = steps.inference.endpoint || "";
      for (const [name, input] of Object.entries(declared)) input.value = steps.inference.declared_pricing?.[name] ?? "";
    }
    describeProvider();
    requote();
    inference.addEventListener("submit", async event => {
      event.preventDefault();
      if (!(agree.checked && quote)) return;
      // The quote was for this exact spec; any edit since re-quoted it.
      const request = {...inferenceSpec(), consent: {max_cost_nano: quote.max_cost_nano}};
      if (key.value) request.key = key.value;
      key.value = "";
      await setupCall("inference", request);
    });

    // 4. Compute: "Where's your GPU?" (LINKONLY-D10).
    // Checked but still waiting for its worker is not done yet.
    const computeDone = steps.compute?.checked && !j.sendPending ? "Checked: " + checkedText("compute", steps) + "." : null;
    const computePanel = stepPanel(body, "compute", computeDone);
    const compute = stepForm(computePanel, "compute");
    const remoteChoice = offered.compute.find(c => c.needs_remote);
    const guides = remoteChoice?.guides || {cards: [], notes: []};
    const where = el("fieldset", undefined, "where"); where.append(el("legend", "Where's your GPU?"));
    const grid = el("div", undefined, "where-grid"); where.append(grid);
    compute.append(where);
    const wherePanel = el("div", undefined, "guide-panel"); wherePanel.id = "setup-guide-panel"; wherePanel.hidden = true;
    compute.append(wherePanel);
    // Shown for a GPU choice: the Challenge to practise.
    const gpuBox = el("div"); gpuBox.dataset.step = "compute"; compute.append(gpuBox);
    const gpuChallenge = setupSelect(gpuBox, "challenge", "Challenge to practise on the GPU", []);
    // Your own remote machine or container (OWNER-MINER-COMPUTE-LINK-ONLY-01,
    // amended 2026-10-02): you start, stop and pay for it; Carbon reaches it
    // with your own SSH and never starts, stops or bills it.
    const remoteBox = el("div"); remoteBox.dataset.step = "compute"; compute.append(remoteBox);
    const destination = setupField(remoteBox, "destination", "SSH destination (user@host, or your ssh-config alias)");
    const sshPort = setupField(remoteBox, "port", "SSH port (optional; leave empty for your ssh config's)", "number");
    researchNote(remoteBox, "Make `ssh <destination>` work from this machine without a prompt first: your key in your agent, the host key in your known hosts. Carbon passes no key and installs nothing.", "hint");
    const missing = el("div"); compute.append(missing);
    // Everything setup fills in for you, or a miner changes on purpose.
    const more = advanced(compute, "Advanced: images and transport");
    const computeChoice = setupSelect(more, "choice", "Where research runs (set by the cards above)", offered.compute.map(c => [c.id, c.display_name]));
    const transportBox = el("div"); transportBox.dataset.step = "compute"; more.append(transportBox);
    const transport = setupSelect(transportBox, "transport", "How Carbon reaches it (set by your card)", []);
    const transportNote = el("div"); transportBox.append(transportNote);
    const images = setupState.images || {};
    const installed = setupState.installed || {};
    const imageNote = field => {
      const found = images[field];
      return found?.path ? "Filled in: found by " + found.found_by + "." : "Not found yet.";
    };
    const image = setupField(more, "image_manifest", "Your worker image (manifest path)");
    researchNote(more, imageNote("image_manifest"), "hint");
    const analysis = setupField(more, "analysis_image_manifest", "Your analysis image (manifest path)");
    researchNote(more, imageNote("analysis_image_manifest"), "hint");
    const gpuImageBox = el("div"); gpuImageBox.dataset.step = "compute"; more.append(gpuImageBox);
    const gpuImage = setupField(gpuImageBox, "gpu_image_manifest", "Your GPU worker image (manifest path)");
    researchNote(gpuImageBox, imageNote("gpu_image_manifest"), "hint");
    // Filled in from what scripts/install_miner.sh built here (C-MLP-04), or
    // where the GPU worker's build script wrote it.
    image.value = images.image_manifest?.path || installed.image_manifest || "";
    analysis.value = images.analysis_image_manifest?.path || installed.analysis_image_manifest || "";
    gpuImage.value = images.gpu_image_manifest?.path || installed.gpu_image_manifest || "";
    const computeButton = el("button", "Check on this machine", "primary"); computeButton.id = "setup-compute-submit";
    const commandCodes = [];
    const fill = command => {
      const target = destination.value.trim();
      if (!command.destination || !target) return command.command;
      return command.command.replace("<destination>", (sshPort.value.trim() ? "-p " + sshPort.value.trim() + " " : "") + target);
    };
    const updateCommands = () => { for (const [code, command] of commandCodes) code.textContent = fill(command); };
    destination.addEventListener("input", updateCommands);
    sshPort.addEventListener("input", updateCommands);
    const describeMissing = () => {
      missing.replaceChildren();
      if (!image.value.trim() || !analysis.value.trim()) {
        missing.append(el("p", "Carbon hasn't found your worker images. Build and record them in your Carbon checkout, then reload this page:", "reason"));
        copyRow(missing, null, images.image_manifest?.build || "scripts/install_miner.sh --no-start");
      }
      if (!gpuImageBox.hidden && !gpuImage.value.trim()) {
        missing.append(el("p", "Build your GPU worker image once (no GPU needed here), then reload this page:", "reason"));
        copyRow(missing, null, images.gpu_image_manifest?.build || "scripts/dev/accelerator_worker_image.sh");
      }
    };
    for (const input of [image, analysis, gpuImage]) input.addEventListener("input", describeMissing);
    const describeTransport = () => {
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      const chosen = (choice?.transports || []).find(t => t.id === transport.value);
      transportNote.replaceChildren();
      if (chosen?.summary) researchNote(transportNote, chosen.summary, "hint");
    };
    transport.addEventListener("change", describeTransport);
    const describeCompute = () => {
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      gpuBox.hidden = !choice?.needs_gpu_image;
      gpuImageBox.hidden = !choice?.needs_gpu_image;
      remoteBox.hidden = !choice?.needs_remote;
      transportBox.hidden = !choice?.needs_remote;
      computeButton.textContent = choice?.needs_remote ? "Check my setup over my SSH" : "Check on this machine";
      const forChallenges = choice?.for_challenges || [];
      const previous = gpuChallenge.value;
      gpuChallenge.replaceChildren(...forChallenges.map(item => { const option = el("option", item.title + " · v" + item.version); option.value = JSON.stringify({id: item.id, version: item.version}); return option; }));
      if ([...gpuChallenge.options].some(option => option.value === previous)) gpuChallenge.value = previous;
      // Only what is built can be chosen; the endpoint transport says why not.
      const previousTransport = transport.value;
      transport.replaceChildren(...(choice?.transports || []).map(item => {
        const option = el("option", item.display_name + (item.available ? "" : " · not built: " + words(item.reason)));
        option.value = item.id; option.disabled = !item.available; return option;
      }));
      if ([...transport.options].some(option => option.value === previousTransport && !option.disabled)) transport.value = previousTransport;
      describeTransport();
      describeMissing();
    };
    // The cards: this machine, then each setup the wiring guide covers.
    const local = offered.compute.filter(c => !c.needs_remote);
    const cards = [
      ...local.map(c => ({id: c.id, title: "This machine", sub: c.needs_gpu_image ? "My GPU" : "CPU · the default", choice: c.id})),
      ...(remoteChoice ? guides.cards.map(g => ({id: g.id, title: g.display_name, sub: g.transport === "ssh-container" ? "Container · SSH" : "Machine with Docker · SSH", choice: remoteChoice.id, transport: g.transport, guide: g})) : []),
    ];
    const aboutRemote = (parent, choice) => details(parent, "About remote practice", ["Cost: " + choice.cost_basis, "Live check: " + choice.live_check, choice.note, "Wiring guide: " + choice.guide]);
    const showWhere = card => {
      wherePanel.replaceChildren(); commandCodes.length = 0;
      const choice = offered.compute.find(c => c.id === computeChoice.value);
      wherePanel.hidden = !card && !choice?.needs_remote;
      if (!card) {
        // The remote choice made under Advanced, with no card picked.
        if (choice?.needs_remote) {
          wherePanel.append(el("p", "Pick where your GPU runs above to see its steps."));
          wherePanel.append(link({label: "Open the full guide", href: "#guide"}));
          aboutRemote(wherePanel, choice);
        }
        return;
      }
      if (!card.guide) {
        wherePanel.append(el("h3", card.title + " · " + card.sub));
        wherePanel.append(el("p", choice.needs_gpu_image ? "Practice runs on your own GPU, for speed only." : "Practice runs in an isolated container on this machine. Nothing is rented."));
        details(wherePanel, "About this choice", ["Cost: " + choice.cost_basis, "Live check: " + choice.live_check, choice.note]);
        return;
      }
      const g = card.guide;
      const head = el("div", undefined, "card-head"); head.append(el("h3", g.display_name), pill(g.transport, "pill-dev"));
      wherePanel.append(head);
      wherePanel.append(el("p", "You start, stop and pay for it" + (g.id === "own-server" ? "" : " at " + g.display_name) + ". Carbon reaches it with your own SSH and never starts, stops or bills it."));
      wherePanel.append(el("p", "Your steps, from the guide", "eyebrow"));
      const steps = el("div", undefined, "guide-steps");
      if (g.steps.length) renderBlocks(steps, g.steps);
      else steps.append(el("p", "This checkout has no guide section for it.", "hint"));
      wherePanel.append(steps);
      wherePanel.append(el("p", "Commands you run", "eyebrow"));
      g.commands.forEach((command, index) => commandCodes.push([copyRow(wherePanel, command.label, fill(command), "setup-copy-" + g.id + "-" + index), command]));
      const full = link({label: "Open the full guide", href: "#guide/" + g.anchor}); full.id = "setup-guide-link";
      wherePanel.append(full);
      const notes = el("div", undefined, "hint"); renderBlocks(notes, guides.notes); wherePanel.append(notes);
      aboutRemote(wherePanel, choice);
    };
    const pick = (card, remember) => {
      for (const input of grid.querySelectorAll("input")) input.checked = Boolean(card) && input.value === card.id;
      if (card) {
        computeChoice.value = card.choice;
        describeCompute();
        if (card.transport) { transport.value = card.transport; describeTransport(); }
        if (remember) store(whereKey, {id: card.id});
      }
      showWhere(card);
    };
    for (const card of cards) {
      const label = el("label", undefined, "where-card");
      const input = el("input"); input.type = "radio"; input.name = "setup-where"; input.value = card.id; input.id = "setup-where-" + card.id;
      input.addEventListener("change", () => pick(card, true));
      const text = el("span"); text.append(el("strong", card.title), el("small", card.sub));
      label.append(input, text); grid.append(label);
    }
    // A choice made directly in Advanced keeps the cards in step.
    computeChoice.addEventListener("change", () => {
      describeCompute();
      const shown = cards.find(card => card.id === stored(whereKey, {}).id && card.choice === computeChoice.value) || cards.find(card => !card.guide && card.choice === computeChoice.value) || null;
      pick(shown, false);
    });
    const checkedMachine = steps.compute?.remote_machine;
    const remembered = cards.find(card => card.id === stored(whereKey, {}).id) || null;
    let initial = cards[0] || null;
    if (steps.compute?.checked && steps.compute.choice) {
      initial = steps.compute.choice === remoteChoice?.id
        ? (remembered?.guide && remembered.transport === checkedMachine?.transport ? remembered : null)
        : cards.find(card => card.choice === steps.compute.choice) || null;
      computeChoice.value = steps.compute.choice;
    } else if (remembered) initial = remembered;
    if (initial) pick(initial, false);
    else describeCompute();
    if (checkedMachine) {
      transport.value = checkedMachine.transport; destination.value = checkedMachine.destination;
      sshPort.value = checkedMachine.port ?? "";
      describeTransport(); updateCommands();
    }
    const action = el("div", undefined, "step-action"); action.append(computeButton); compute.append(action);
    compute.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {choice: computeChoice.value, image_manifest: image.value.trim(), analysis_image_manifest: analysis.value.trim()};
      if (!gpuBox.hidden) {
        request.gpu_image_manifest = gpuImage.value.trim();
        if (gpuChallenge.value) request.challenge = JSON.parse(gpuChallenge.value);
      }
      if (!remoteBox.hidden) {
        request.remote = {transport: transport.value, destination: destination.value.trim()};
        if (sshPort.value.trim()) request.remote.port = Number(sshPort.value.trim());
      }
      await setupCall("compute", request);
    });

    // Send your worker: a machine with Docker that does not hold the pinned
    // GPU worker yet. Nothing is sent without consent to that destination and
    // that image, unticked by default; it streams over your own SSH.
    const remoteCheck = steps.compute?.check?.remote;
    if (checkedMachine && checkedMachine.transport === "ssh-docker" && remoteCheck?.worker_image === "missing") {
      const sendBox = el("section", undefined, "guide-panel"); computePanel.append(sendBox);
      sendBox.append(el("h3", "Send your worker"));
      const send = stepForm(sendBox, "send_worker");
      const workerImage = steps.compute.check.gpu_image;
      const target = checkedMachine.destination + (checkedMachine.port ? " (port " + checkedMachine.port + ")" : "");
      researchNote(send, "Your machine does not hold the pinned GPU worker. Carbon can stream it there over your own SSH (docker save | ssh docker load) and check its image ID. It can take minutes.", "hint");
      const sendAgree = document.createElement("input");
      sendAgree.type = "checkbox"; sendAgree.id = "setup-send-worker-consent"; sendAgree.checked = false;
      const sendLabel = el("label", "Send the pinned GPU worker " + workerImage + " to " + target + "."); sendLabel.htmlFor = sendAgree.id;
      const sendRow = el("div", undefined, "consent"); sendRow.append(sendAgree, sendLabel);
      send.append(sendRow);
      const sendButton = el("button", "Send my worker", "primary"); sendButton.disabled = true;
      sendAgree.addEventListener("change", () => { sendButton.disabled = !sendAgree.checked; });
      send.append(sendButton);
      send.addEventListener("submit", async event => {
        event.preventDefault();
        if (!sendAgree.checked) return;
        const consent = {destination: checkedMachine.destination, image: workerImage};
        if (checkedMachine.port) consent.port = checkedMachine.port;
        sendButton.disabled = true;
        $("setup-result").replaceChildren(setupLine("Sending your worker over your SSH. This can take minutes."));
        await setupCall("send_worker", {consent: {send: consent}}, 3600000);
      });
    }

    // 5. Agent.
    const agentPanel = stepPanel(body, "agent", steps.agent?.checked ? "Checked: " + checkedText("agent", steps) + ", and your signer answered." : null);
    const agent = stepForm(agentPanel, "agent");
    const agentChoice = setupSelect(agent, "choice", "Agent", offered.agent.map(c => [c.id, c.display_name]));
    const agentCost = el("div"); agent.append(agentCost);
    researchNote(agent, "Carbon never asks for your hotkey or its password. Start carbon-miner-signer for your registered hotkey in your own terminal; this step asks it which hotkey it holds.", "hint");
    // Hermes (C-MLP-03 slice 5): nothing is written to the miner's Hermes
    // without their consent to the exact files, unticked by default.
    const hermesBox = el("div"); agent.append(hermesBox);
    const hermesAgree = document.createElement("input");
    hermesAgree.type = "checkbox"; hermesAgree.id = "setup-agent-hermes-consent"; hermesAgree.checked = false;
    const hermesLabel = el("label"); hermesLabel.htmlFor = hermesAgree.id;
    const hermesRow = el("div", undefined, "consent"); hermesRow.append(hermesAgree, hermesLabel);
    hermesBox.append(hermesRow);
    // Miners leave these empty: setup reads Carbon's testnet and its
    // publisher from the chain. Only an operator running Carbon's deployment
    // names a config.
    const agentMore = advanced(agent);
    const operator = setupField(agentMore, "operator_config", "Operator config (operators only; leave empty)");
    const socket = setupField(agentMore, "signer_socket", "Signer socket (optional; leave empty for the default)");
    const describeAgent = () => {
      const choice = offered.agent.find(c => c.id === agentChoice.value);
      agentCost.replaceChildren();
      const about = details(agentCost, "About this agent", []);
      costNote(about.querySelector(".detail-body"), choice);
      hermesBox.hidden = !choice?.needs_consent_to_write;
      hermesAgree.checked = false;
      if (choice?.needs_consent_to_write) {
        hermesLabel.textContent = "Write my Hermes profile: " + (choice.writes || []).join(", ") + ". Then start it with: " + choice.start;
      }
    };
    agentChoice.addEventListener("change", describeAgent);
    if (steps.agent?.checked && steps.agent.choice) agentChoice.value = steps.agent.choice;
    describeAgent();
    const agentAction = el("div", undefined, "step-action"); agentAction.append(el("button", "Check my signer", "primary")); agent.append(agentAction);
    agent.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {choice: agentChoice.value};
      if (operator.value.trim()) request.operator_config = operator.value.trim();
      if (socket.value.trim()) request.signer_socket = socket.value.trim();
      const choice = offered.agent.find(c => c.id === agentChoice.value);
      if (choice?.needs_consent_to_write) {
        if (!hermesAgree.checked) { $("setup-result").replaceChildren(setupLine("consent: tick to agree to the files your Hermes profile needs.")); return; }
        request.consent = {writes: choice.writes};
      }
      await setupCall("agent", request);
    });

    // 6. Review and launch.
    const written = Boolean(steps.review?.profile_written);
    const reviewPanel = stepPanel(body, "review", written ? "Your profile is written." : null);
    const review = stepForm(reviewPanel, "review");
    const summary = el("dl", undefined, "review-grid"); review.append(summary);
    for (const [name, label] of [["inference", "Inference"], ["compute", "Compute"], ["agent", "Agent"]]) {
      const state = steps[name] || {};
      summary.append(el("dt", label), el("dd", state.checked ? checkedText(name, steps) : "Not checked yet"));
    }
    researchNote(review, "Writes your runner profile beside this controller and loads it. Nothing is launched and nothing is spent.", "hint");
    // A validator's intake, when a Challenge's validator runs elsewhere
    // (C-MLP-03 slice 6, per Challenge since C-MLP-04). Its public facts are
    // read and checked by that Challenge; nothing is signed.
    const reviewMore = advanced(review, "Advanced: a validator's intake");
    const intakeChallenges = offered.intake_challenges || [];
    const intakeChallenge = setupSelect(reviewMore, "intake_challenge", "Validator intake for", intakeChallenges.map(item => [item.id, item.title + " · v" + item.version]));
    const intake = setupField(reviewMore, "intake_url", "Validator intake URL (optional; https, or loopback)");
    intakeChallenge.disabled = intake.disabled = !intakeChallenges.length;
    const write = el("button", written ? "Write my profile again" : "Write my profile", written ? "" : "primary");
    write.disabled = !steps.review?.ready;
    const reviewAction = el("div", undefined, "step-action"); reviewAction.append(write);
    if (caps?.profile?.configured) {
      const go = link({label: "Choose a Challenge", href: "#challenges"}, "button primary"); go.id = "setup-choose-challenge";
      reviewAction.prepend(go);
    }
    review.append(reviewAction);
    if (!steps.review?.ready) researchNote(review, "Check inference, compute and agent first.", "hint");
    review.addEventListener("submit", async event => {
      event.preventDefault();
      const request = {confirm: true};
      if (intake.value.trim() && intakeChallenge.value) request.intakes = {[intakeChallenge.value]: intake.value.trim()};
      await setupCall("review", request);
    });
    applySetupStep();
  }

  $("onboarding-status").addEventListener("click", () => onboardingCall("status"));
  $("onboarding-prepare").addEventListener("click", () => onboardingCall("prepare"));
  $("onboarding-confirm").addEventListener("click", () => onboardingCall("confirm"));

  // ---- Capabilities: read on connect and on request, never assumed. ----
  async function readCapabilities() {
    const value = await api("/api/v1/control-center/capabilities", undefined, undefined, 20000);
    if (value.schema !== CAPS_SCHEMA) throw new Error("unsupported_controller_version");
    caps = value;
    capsVersion++;
    // A remembered choice is checked against what exists now.
    if (wizard.challenge && !challengeEntry(wizard.challenge)) wizard.challenge = null;
    if (wizard.agentChoice && !caps.agents.choices.some(choice => choice.id === wizard.agentChoice)) wizard.agentChoice = null;
    if (wizard.agentChoice) composition = {...composition, agent: agentEntry(wizard.agentChoice).launch_agent};
  }
  function challengeEntry(selection) {
    if (!caps || !selection) return null;
    return caps.challenges.find(entry => entry.challenge_id === selection.id && entry.version === selection.version) || null;
  }
  function agentEntry(id) { return caps?.agents.choices.find(choice => choice.id === id) || null; }
  function selectedProvider() {
    const providers = caps?.model.providers || [];
    return providers.find(provider => provider.id === wizard.provider) || null;
  }
  function computeChoice() { return caps?.compute.choices[0] || null; }

  async function refresh() {
    if (!token || polling) return;
    polling = true;
    try {
      runs = (await api("/api/v1/runs")).runs;
      developmentSources = (await api("/api/v1/development")).sources;
      research = await api("/api/v1/research");
      if (research.preflight.available && !launchOptions) {
        try { launchOptions = await api("/api/v1/operations/options", {}); }
        catch (_) { launchOptions = null; }
      }
      if (!launchShape) {
        try { launchShape = (await api("/api/v1/operations")).operations.find(op => op.operation === "launch") || null; }
        catch (_) { launchShape = null; }
      }
      connected = true;
      land();
      render();
      if (!setupRead) { setupRead = true; readSetup(); }
      $("connection-state").textContent = "Connected";
    } catch (error) {
      connected = false;
      render();
      $("connection-state").textContent = "Connection interrupted";
      message("Controller connection interrupted. Runs may still be active. Reconnect before issuing another command.", true);
    } finally { polling = false; }
  }
  // A returning miner lands on their active campaign; otherwise where they were.
  function land() {
    if (landed) return;
    landed = true;
    if (location.hash) return;
    const active = research.runs.find(run => !TERMINAL.includes(run.state));
    if (active) { location.hash = "#campaigns/" + encodeURIComponent(active.id) + "/overview"; return; }
    const last = stored(routeKey, null);
    if (last && typeof last.hash === "string" && last.hash.startsWith("#")) location.hash = last.hash;
  }
  $("connect-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || polling) return;
    connected = false;
    render();
    token = $("token").value.trim();
    try {
      await readCapabilities();
      const catalog = await api("/api/v1/capabilities");
      if (catalog.schema !== "carbon.launchpad.rehearsal.v1" || catalog.mode !== "REHEARSAL") {
        throw new Error("unsupported_controller_version");
      }
      $("token").value = "";
      $("integrations").replaceChildren();
      for (const item of catalog.unavailable) {
        const box = document.createElement("div"); box.className = "integration";
        const title = document.createElement("strong"); title.textContent = item.id;
        const reason = document.createElement("p"); reason.textContent = item.reason.replaceAll("_", " ");
        box.append(title, reason); $("integrations").append(box);
      }
      // Order matters: renderExamEnvironment clears the panel before filling
      // it, so the compute choices are appended after it rather than before.
      await renderExamEnvironment();
      renderComputeChoices(caps.compute.destinations || []);
      await onboardingRequirements();
      message("Connected. Records persist on this machine.");
      await refresh();
      if (storageError) message("Browser retry storage is unavailable. Launch is disabled to preserve duplicate protection.", true);
    } catch (error) {
      token = "";
      connected = false;
      $("connection-state").textContent = "Disconnected";
      render();
      message("Could not connect: " + error.message, true);
    }
  });
  $("settings-recheck").addEventListener("click", async () => {
    if (busy || !connected) return;
    busy = true; render();
    try { await readCapabilities(); launchOptions = null; message("Capabilities re-read from the controller."); }
    catch (error) { message("Capabilities not re-read: " + error.message, true); }
    finally { busy = false; await refresh(); render(); }
  });
  $("settings-clear").addEventListener("click", () => {
    for (const key of [wizardKey, draftKey, routeKey]) { try { localStorage.removeItem(key); } catch (_) { /* nothing stored */ } }
    for (const key of Object.keys(journeyDrafts)) delete journeyDrafts[key];
    wizard = {step: "challenge", challenge: null, agentChoice: null, provider: null, model: null};
    composition = {agent: null, budget: {}};
    $("settings-note").textContent = "Saved choices and drafts forgotten. Templates are kept; delete them in the launch wizard.";
    render();
  });
  $("launch-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || !connected || storageError) return;
    if (!pending) {
      pending = {key: crypto.randomUUID(), spec: {
        mode: "REHEARSAL", challenge: "controller-rehearsal-v1", agent: "fixture",
        reasoning: "none", compute: "local", max_steps: Number($("steps").value),
        max_seconds: Number($("seconds").value)
      }};
      try { sessionStorage.setItem(pendingKey, JSON.stringify(pending)); }
      catch (_) {
        storageError = true; render();
        message("Could not preserve the retry request. Nothing was dispatched.", true);
        return;
      }
    }
    busy = true; $("launch-button").disabled = true;
    try {
      const run = await api("/api/v1/runs", pending.spec, pending.key);
      selected = run.id;
      sessionStorage.removeItem(pendingKey); pending = null;
      message("Rehearsal started. These fixture steps produce no physics or mining evidence.");
      await refresh();
    } catch (error) {
      message("Launch not confirmed: " + error.message + ". Retry keeps this request, including after reconnect. Free an active slot if required.", true);
    } finally { busy = false; $("launch-button").disabled = false; render(); }
  });
  for (const action of ["pause", "resume", "stop"]) {
    $(action).addEventListener("click", async () => {
      if (busy || !connected || !selected) return;
      busy = true; render();
      try {
        await api("/api/v1/runs/" + selected + "/" + action, {});
        message("Controller acknowledged: " + action + ".");
        await refresh();
      } catch (error) { message("Command not confirmed: " + error.message + ". Check the run state before retrying.", true); }
      finally { busy = false; render(); }
    });
  }
  $("run-picker").addEventListener("change", () => { selected = $("run-picker").value; render(); });
  $("export").addEventListener("click", async () => {
    if (busy || !connected || !selected) return;
    busy = true; render();
    try {
      const run = await api("/api/v1/runs/" + selected);
      download(run, "carbon-rehearsal-" + run.id + ".json");
    } catch (error) { message("Export not confirmed: " + error.message, true); }
    finally { busy = false; render(); }
  });
  function renderComputeChoices(choices) {
    // Where the miner may run their own research, and what each route needs,
    // beside the exam environment on purpose: they choose the first and are
    // told the second. Kept behind Details: the route cards above lead.
    const panel = $("exam-environment");
    if (!choices.length) return;
    const box = details(panel, "What each research route needs", []);
    const body = box.querySelector(".detail-body");
    body.append(el("h3", "Your research compute"));
    for (const choice of choices.filter(entry => entry.selectable !== false)) {
      const item = el("div", undefined, "integration");
      item.append(el("strong", choice.id.replaceAll("-", " ")), el("p", choice.summary));
      if (choice.requires?.length) researchNote(item, "Needs: " + choice.requires.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      if (choice.not_required?.length) researchNote(item, "Not needed: " + choice.not_required.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      body.append(item);
    }
  }

  async function renderExamEnvironment() {
    const panel = $("exam-environment");
    panel.replaceChildren();
    let contract;
    try {
      contract = await api("/api/v1/exam-environment");
    } catch (error) {
      researchNote(panel, "The published exam environment could not be read. It is a disclosure, not a launch requirement; research and submission are unaffected.");
      return;
    }
    // The plain reading first; the validator's internals behind Details.
    // Declared is not qualified, and the page says which this is.
    researchNote(panel, "Declared, not qualified: published so you can read it before you submit.", "status-line");
    researchNote(panel, "You submit: " + contract.submission.accepted.replaceAll("_", " ").toLowerCase() + ". Not accepted: " + contract.submission.not_accepted.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ".", "hint");
    researchNote(panel, "Your research hardware is not constrained by this contract and does not have to match it. No provider is prescribed, for you or for a validator.", "hint");
    const inside = details(panel, "Exam environment details", []);
    const body = inside.querySelector(".detail-body");
    researchNote(body, "Backend profile: " + contract.backend_profile.profile_id + " · " + contract.backend_profile.backend + " · " + contract.backend_profile.scope);
    researchNote(body, "Qualification: declared, not qualified · Backend support " + contract.qualification.backend_support + " · " + contract.qualification.basis);
    for (const limitation of contract.known_limitations || []) {
      researchNote(body, "Disclosed limitation · " + limitation.statement + " " + limitation.consequence);
    }
    const full = el("details"); full.append(el("summary", "Pinned versions, resource envelope and containment"));
    const data = el("pre"); data.textContent = JSON.stringify(contract, null, 2);
    full.append(data); body.append(full);
  }

  // ---- Overview. ----
  // Get started: the six steps, each done only when the controller confirmed
  // it, the current one highlighted, and one primary action that goes to it.
  function renderGettingStarted() {
    const list = $("getting-started-steps");
    const primary = $("overview-primary");
    if (!connected) {
      list.replaceChildren(el("li", "Connect this browser to see your next step.", "hint"));
      list.dataset.key = "";
      primary.textContent = "Get started"; primary.href = "#setup";
      $("getting-started-progress").textContent = "";
      return;
    }
    const j = journey();
    const key = JSON.stringify([j.state, j.profile, research.runs.length, setupState?.registered_hotkey ?? null, setupVersion]);
    primary.textContent = j.current ? "Next: " + stepTitle(j.current, j) : "New campaign";
    primary.href = j.current ? stepHref(j.current, j) : "#launch";
    $("overview-lede").textContent = j.current ? "Step " + (SETUP_IDS.indexOf(j.current) + 1) + " of 6 is next. Each step is checked before it counts." : "You are set up. Choose a Challenge and launch.";
    if (list.dataset.key === key) return;
    list.dataset.key = key;
    list.replaceChildren();
    SETUP_IDS.forEach((id, index) => {
      const state = j.state[id];
      const item = el("li", undefined, "gs-step is-" + state + (id === j.current ? " is-current" : ""));
      item.dataset.step = id;
      if (id === j.current) item.setAttribute("aria-current", "step");
      const body = el("div", undefined, "gs-body");
      const title = el("h3"); const go = el("a", stepTitle(id, j)); go.href = stepHref(id, j); title.append(go);
      body.append(title, el("p", stepSentence(id, j)));
      item.append(el("span", String(index + 1).padStart(2, "0"), "gs-num"), body, pill(STATE_LABEL[state], "gs-state pill-" + (state === "done" ? "done" : state === "next" ? "next" : "wait")));
      list.append(item);
    });
    const count = Object.values(j.state).filter(state => state === "done").length;
    $("getting-started-progress").textContent = count + " of 6 done";
  }
  function prerequisites() {
    // What a launch needs, each read from the controller - never assumed met.
    if (!caps) return [];
    const items = [];
    items.push(caps.profile.configured
      ? {ok: true, text: "Your runner profile is loaded.", detail: ["Profile: " + caps.profile.profile_id]}
      : {ok: false, area: "Runner profile", item: caps.profile});
    items.push({ok: null, text: "Your subnet registration is read at launch, before anything is recorded.", fix: {label: "Check it", href: "#wallet"}});
    const selectable = caps.challenges.filter(entry => entry.selectable);
    items.push(selectable.length
      ? {ok: true, text: "You can launch: " + selectable.map(entry => entry.title).join(", ") + "."}
      : {ok: false, area: "Challenges", item: caps.challenges.find(entry => entry.implemented) || caps.challenges[0]});
    const agents = caps.agents.choices.filter(choice => choice.availability === "available");
    items.push(agents.length
      ? {ok: true, text: "Agents ready: " + agents.map(choice => choice.label).join(", ") + "."}
      : {ok: false, area: "Agents", item: caps.agents.choices[0]});
    const provider = caps.model.providers.find(item => item.availability === "available");
    items.push(provider
      ? {ok: true, text: "Model key set for " + provider.provider + "."}
      : {ok: false, area: "Model key (only Carbon's own agent needs one)", item: caps.model.providers[0]});
    const compute = computeChoice();
    items.push(compute && compute.availability === "available"
      ? {ok: true, text: "Compute: " + compute.label + "."}
      : {ok: false, area: "Compute", item: compute});
    return items;
  }
  // One line per need: the same missing cause is said once, with the parts
  // waiting on it, one fix, and each code behind Details.
  function renderReadiness(list, items) {
    list.replaceChildren();
    const groups = new Map();
    for (const item of items) {
      if (item.ok !== false) {
        const entry = el("li", undefined, item.ok ? "ok" : "pending");
        entry.append(pill(item.ok ? "Ready" : "At launch", item.ok ? "pill-done" : "pill-wait"), el("span", item.text));
        if (item.fix) entry.append(link(item.fix));
        if (item.detail) details(entry, "Details", item.detail);
        list.append(entry);
        continue;
      }
      const source = item.item || {};
      const plain = source.plain || {sentence: "Unavailable: " + words(source.reason) + ".", next: null};
      const key = plain.sentence + "|" + (plain.next?.href || "");
      if (!groups.has(key)) {
        const entry = el("li", undefined, "missing");
        const group = {entry, plain, areas: [], lines: []};
        groups.set(key, group);
        list.append(entry);
      }
      const group = groups.get(key);
      group.areas.push(item.area);
      group.lines.push(item.area + ": " + (source.reason || "unknown") + (source.next_action ? " · " + source.next_action : ""));
    }
    for (const group of groups.values()) {
      group.entry.append(pill("Needed", "pill-need"), el("span", group.plain.sentence));
      if (group.areas.length > 1) group.entry.append(el("span", "Waiting on it: " + group.areas.join(", ") + ".", "next"));
      else group.entry.append(el("span", group.areas[0] + ".", "next"));
      if (group.plain.next) group.entry.append(link(group.plain.next, "button fix"));
      details(group.entry, "Details", group.lines);
    }
  }
  function renderChecklist(list, items) {
    list.replaceChildren();
    for (const item of items) {
      const entry = el("li", undefined, item.ok === true ? "ok" : item.ok === false ? "missing" : "pending");
      entry.append(pill(item.ok === true ? "Ready" : item.ok === false ? "Needed" : "At launch", item.ok === true ? "pill-done" : item.ok === false ? "pill-need" : "pill-wait"), el("span", item.text));
      if (item.next) entry.append(el("span", "Next: " + item.next, "next"));
      if (item.href) { const open = el("a", "Open", "inline-link"); open.href = item.href; entry.append(open); }
      list.append(entry);
    }
  }
  function renderOverview() {
    renderGettingStarted();
    const list = $("overview-prerequisites");
    if (!connected || !caps) { list.replaceChildren(el("li", "Connect to read what this controller can do.", "hint")); list.dataset.key = ""; }
    else rebuild(list, "caps:" + capsVersion, target => renderReadiness(target, prerequisites()));
    const active = $("overview-active");
    active.replaceChildren();
    if (!connected) { researchNote(active, "Connect to see your campaigns.", "hint"); return; }
    const live = research.runs.filter(run => !TERMINAL.includes(run.state));
    if (!research.runs.length) {
      researchNote(active, "No campaigns yet. They appear here once you launch.", "hint");
      return;
    }
    for (const run of (live.length ? live : research.runs.slice(0, 3))) campaignCard(active, run);
  }
  function challengeLabel(run) {
    if (run.challenge) {
      const entry = challengeEntry({id: run.challenge.id, version: run.challenge.version});
      return (entry ? entry.title : run.challenge.id) + " · v" + run.challenge.version;
    }
    return run.selects ? "Recorded without a Challenge (historical DEVELOPMENT campaign)" : "Challenge not yet recorded";
  }
  function campaignCard(parent, run) {
    const box = el("a", undefined, "integration card campaign-card");
    box.href = "#campaigns/" + encodeURIComponent(run.id) + "/overview";
    const head = el("div", undefined, "card-head");
    head.append(el("h3", run.id.slice(0, 10)), el("span", run.state, "badge state-" + String(run.state).toLowerCase()));
    box.append(head);
    researchNote(box, challengeLabel(run));
    researchNote(box, (run.selects === "miner" ? "You select and submit" : run.selects === "agent" ? "Carbon's agent selects" : "Awaiting runtime") + " · Attempts: " + (run.attempted_experiments ?? 0) + " · Completed practice: " + (run.completed_experiments ?? 0), "hint");
    parent.append(box);
  }

  // ---- Catalog views: Challenges, Agents, Compute, Connections, Wallet. ----
  // Rebuilt only when what they show changes, so an open Details stays open.
  function renderCatalogs() {
    const views = ["challenge-catalog", "agent-catalog", "compute-catalog", "connection-catalog", "wallet-profile"];
    if (!connected || !caps) {
      for (const id of views) { $(id).replaceChildren(el("p", id === "wallet-profile" ? "" : "Connect to read this controller's capabilities.", "hint")); $(id).dataset.key = ""; }
      return;
    }
    const key = capsVersion + ":" + setupVersion;
    rebuild($("challenge-catalog"), key, renderChallengeCatalog);
    rebuild($("agent-catalog"), key, renderAgentCatalog);
    rebuild($("compute-catalog"), key, renderComputeCatalog);
    rebuild($("connection-catalog"), key, renderConnections);
    rebuild($("wallet-profile"), key, renderWallet);
  }
  function challengeStatus(entry) {
    return entry.status + (entry.selectable ? " · launchable" : "");
  }
  // The card's state in a word: ready, set up first, or why it never is here.
  function challengePill(entry) {
    if (entry.selectable) return ["Ready", "pill-done"];
    if (entry.implemented) return ["Set up first", "pill-need"];
    return [{RESERVED: "Reserved", DEFERRED: "Deferred", RETIRED: "Retired"}[entry.status] || words(entry.status), "pill-wait"];
  }
  function renderChallengeCatalog(target) {
    for (const entry of caps.challenges) {
      const [tag, kind] = challengePill(entry);
      const box = card(target, entry.title, tag, kind);
      box.dataset.challenge = entry.challenge_id;
      if (entry.selectable) {
        box.append(el("p", "Ready to launch.", "status-line"));
        const choose = el("button", "Use for a new campaign", "primary"); choose.type = "button";
        choose.addEventListener("click", () => { selectChallenge(entry); location.hash = "#launch"; });
        box.append(choose);
      } else {
        box.append(el("p", entry.plain?.sentence || "Unavailable: " + words(entry.reason) + ".", "status-line"));
        if (entry.plain?.next) box.append(link(entry.plain.next, "button fix"));
      }
      if (entry.implemented) {
        const description = details(box, "Description", []);
        renderDescription(description.querySelector(".detail-body"), entry);
      }
      details(box, "Details", [
        entry.challenge_id + (entry.version ? " · version " + entry.version : "") + " · " + words(entry.portfolio) + (entry.tracking ? " · " + entry.tracking : ""),
        "Status: " + challengeStatus(entry),
        entry.implemented ? "This host: " + (entry.usable_here ? "shows every requirement of " + entry.profile : "has not shown " + entry.missing_here.map(words).join(", ") + " (the launch still reads your profile's runtime)") : null,
        entry.reason ? "Code: " + entry.reason : null,
        entry.next_action ? "Next: " + entry.next_action : null,
      ]);
    }
  }
  function renderDescription(parent, entry) {
    // Straight from the Challenge's own registered description.
    const d = entry.description || {};
    const grid = el("dl", undefined, "review-grid");
    const row = (label, value) => { if (value === undefined || value === null || value === "") return; grid.append(el("dt", label), el("dd", value)); };
    row("Objective", d.task);
    row("Intended use", d.intended_use);
    const inputs = d.interface?.inputs || {};
    row("Inputs", Object.entries(inputs).map(([name, spec]) => name + " [" + (spec.bounds || []).join(", ") + "] " + (spec.unit || "")).join(" · "));
    const outputs = d.interface?.outputs || {};
    row("Outputs", Object.entries(outputs).map(([name, spec]) => name + " " + JSON.stringify(spec.shape ?? []) + " " + (spec.unit || "") + (spec.grid ? " (" + spec.grid + ")" : "") + (spec.meaning ? " (" + spec.meaning + ")" : "")).join(" · "));
    const material = d.public_material || {};
    row("Public data", [(material.names || []).join(", "), material.train ? "TRAIN " + material.train.version + ": " + material.train.cases + " cases" : "", material.practice ? "PRACTICE: " + material.practice.cases + " cases" : ""].filter(Boolean).join(" · "));
    row("Never disclosed", (material.never_disclosed || []).join("; "));
    row("Tools", Object.entries(entry.tools?.workflow || {}).map(([name, detail]) => name + ": " + detail).join(" · "));
    row("Rebuildable models", (entry.tools?.rebuildable_models || []).join(", "));
    row("Practice metrics", [d.feedback?.practice, d.exam?.components ? "components: " + d.exam.components.join(", ") : ""].filter(Boolean).join(" · "));
    row("Exam gates", (d.exam?.gates || []).join(", "));
    row("Submission", [d.prediction_contract?.produced_by, d.workflow?.freeze, d.workflow?.submit].filter(Boolean).join(" · "));
    row("Reconstruction", d.exclusion_scope?.submission);
    row("Exam version", "version " + entry.version + (d.contract_digest ? " · contract " + d.contract_digest : "") + (d.exam?.rule?.status ? " · " + words(d.exam.rule.status) : ""));
    row("Limits", Object.entries(entry.tools?.limits || {}).map(([name, detail]) => name + ": " + (typeof detail === "object" ? JSON.stringify(detail) : detail)).join(" · "));
    row("Authority", d.authority);
    // What the Challenge gives a miner to research with, and what setup can
    // prepare for it (C-MLP-04): every Challenge reports the same way.
    if (entry.provisions && !entry.provisions.retired) {
      row("Research environment", Object.entries(entry.provisions).map(([name, state]) => name + (state.status === "gap" ? ": gap (" + state.reason + ")" : ": provided")).join(" · "));
    }
    const offers = entry.setup_offers || {};
    row("Setup offers", [offers.gpu ? "GPU practice on your machine" : "", offers.remote_gpu ? "GPU practice on your own remote machine or container" : "", offers.intake ? "submission to a remote validator's intake" : "", offers.feedback_modes?.length ? "feedback modes: " + offers.feedback_modes.join(", ") : ""].filter(Boolean).join(" · "));
    parent.append(grid);
  }
  const readiness = item => item.availability === "available" ? ["Ready", "pill-done"] : ["Needs setup", "pill-need"];
  function renderAgentCatalog(target) {
    for (const choice of caps.agents.choices) {
      const box = card(target, choice.label, ...readiness(choice));
      box.append(el("p", choice.summary, "hint"));
      if (choice.command && choice.availability === "available") copyRow(box, "Connect your client with:", choice.command);
      if (choice.availability !== "available") unavailableNote(box, choice);
    }
    // Model providers in one card: a row each, the fix beside the ones that
    // need it, every credential and code behind Details.
    const providers = card(target, "Model providers", "Used by Carbon's agent");
    const rows = el("ul", undefined, "checklist");
    for (const provider of caps.model.providers) {
      const entry = el("li", undefined, provider.availability === "available" ? "ok" : "missing");
      entry.append(pill(...readiness(provider)), el("span", provider.provider));
      if (provider.availability !== "available") {
        entry.append(el("span", provider.plain?.sentence || words(provider.reason) + ".", "next"));
        if (provider.plain?.next) entry.append(link(provider.plain.next));
      }
      details(entry, "Details", [
        "Models: " + provider.models.map(model => model.id).join(", ") + " · used by Carbon's autonomous agent only",
        "Credential: " + provider.credential.reference + " · " + (provider.credential.configured === null ? provider.credential.basis : provider.credential.configured ? "configured" : "not configured") + " · held by " + provider.credential.held_by,
        provider.reason ? "Code: " + provider.reason : null,
        provider.next_action ? "Next: " + provider.next_action : null,
      ]);
      rows.append(entry);
    }
    providers.append(rows);
    for (const item of [...caps.agents.unavailable, ...caps.model.unavailable]) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  // Where research runs, side by side (LINKONLY-D10): this machine, and a GPU
  // the miner runs elsewhere, each with its state and the place to set it.
  function renderComputeCatalog(target) {
    const routes = caps.compute.routes || [];
    const choice = computeChoice();
    const checked = setupState?.steps?.compute;
    for (const route of routes) {
      if (route.id === "this-machine") {
        const [tag, kind] = route.availability === "available" ? [route.in_use ? "In use" : "Ready", "pill-done"] : ["Needs setup", "pill-need"];
        const box = card(target, route.label, tag, kind);
        const facts = choice ? [
          "Lanes: " + Object.entries(choice.lanes).map(([lane, state]) => lane + " " + state.availability + (state.reason ? " (" + words(state.reason) + ")" : "")).join(" · "),
          caps.compute.selection,
          "Host facts: " + (choice.host_facts || []).join(", "),
        ] : [];
        if (route.availability === "available") {
          box.append(el("p", "Practice runs in an isolated container here, on the " + route.lane.toUpperCase() + ".", "status-line"));
          details(box, "Details", facts);
        } else unavailableNote(box, route, facts);
        continue;
      }
      const set = route.availability === "configured";
      const box = card(target, route.label, set ? "In use" : "Not set up", set ? "pill-done" : "pill-wait");
      if (set) box.append(el("p", "In your profile: " + route.transport + ", over your own SSH.", "status-line"));
      else if (checked?.checked && checked.remote_machine) box.append(el("p", "Checked over your SSH: " + checked.remote_machine.destination + " (" + checked.remote_machine.transport + "). Write your profile to use it.", "status-line"));
      else box.append(el("p", "Use a GPU you run anywhere: RunPod, Lium, Targon, Vast.ai, Lambda or your own server, reached with your own SSH.", "status-line"));
      box.append(el("p", "You start, stop and pay for it. Carbon never does.", "hint"));
      const go = checked?.checked && checked.remote_machine && !set ? {label: "Write your profile", href: "#setup/review"} : route.plain.next;
      box.append(link(go, set ? "button fix" : "button primary"));
      details(box, "Details", ["Started, stopped and billed by: " + route.started_stopped_and_billed_by, set ? "Transport: " + route.transport : null]);
    }
    for (const item of caps.compute.unavailable) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  function renderConnections(target) {
    const mcp = agentEntry("external_mcp");
    if (mcp) {
      const box = card(target, "Your own MCP client · stdio", ...readiness(mcp));
      box.append(el("p", "Run on this machine with your runner profile. Every operation - launch, observe, practice, freeze, submit, halt, resume - is the same one this page calls, over the same records. Nothing is issued by Carbon.", "hint"));
      copyRow(box, "Connect your client with:", mcp.command);
      if (mcp.availability !== "available") unavailableNote(box, mcp);
    }
    for (const item of caps.connections) unavailableNote(card(target, words(item.id), "Not offered", "pill-wait"), item);
  }
  function renderWallet(target) {
    const box = card(target, "Research identity", ...(caps.profile.configured ? ["Ready", "pill-done"] : ["Needs setup", "pill-need"]));
    if (caps.profile.configured) {
      box.append(el("p", "Your runner profile is loaded. Your registered miner is read from it at launch; signing stays in your own wallet.", "status-line"));
      details(box, "Details", ["Runner profile " + caps.profile.profile_id]);
    } else unavailableNote(box, caps.profile);
    // Registration is the miner's own transaction: said here, with no link
    // back to this same page.
    for (const item of caps.wallet) {
      const entry = card(target, "Registration", "Your wallet", "pill-dev");
      entry.append(el("p", item.plain?.sentence || words(item.reason) + ".", "status-line"));
      details(entry, "Details", ["Code: " + item.reason, "Next: " + item.next_action]);
    }
  }

  // ---- Campaigns: list, deep-linked detail and tabs. ----
  function renderCampaigns() {
    const list = $("research-runs");
    const current = route();
    const detail = $("campaign-detail");
    // Read what is open now, before anything is rebuilt. The toggle event is
    // asynchronous, so a miner's click that lands just before a live refresh
    // would otherwise fire on a replaced element and be lost.
    for (const node of detail.querySelectorAll("details[data-research-run]")) {
      if (node.open) expandedResearch.add(node.dataset.researchRun); else expandedResearch.delete(node.dataset.researchRun);
    }
    const run = current.view === "campaigns" && current.id ? research.runs.find(r => r.id === current.id) : null;
    list.hidden = Boolean(run);
    detail.hidden = !run && !(current.view === "campaigns" && current.id);
    if (!(list.contains(document.activeElement))) {
      list.replaceChildren();
      if (!connected) researchNote(list, "Reconnect to reconcile research state. Controls are disabled.", "hint");
      else if (!research.runs.length) {
        const empty = el("div", undefined, "empty");
        empty.append(el("h3", "No campaign yet."), el("p", "New campaign walks you through Challenge, agent, model, compute, tools and limits."));
        list.append(empty);
      }
      for (const item of research.runs) campaignCard(list, item);
    }
    if (current.view === "campaigns" && current.id && !run) {
      detail.replaceChildren(el("p", connected ? "No campaign " + current.id + " on this controller." : "Reconnect to open this campaign.", "hint"));
      return;
    }
    if (!run) return;
    // Never rebuild under a person's cursor: the journey is typed into.
    const active = document.activeElement;
    if (active && detail.contains(active) && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName) && detail.dataset.run === run.id) return;
    detail.dataset.run = run.id;
    detail.replaceChildren();
    const back = el("a", "← All campaigns", "inline-link"); back.href = "#campaigns";
    const head = el("div", undefined, "run-top");
    const title = el("div");
    title.append(el("p", "CAMPAIGN · " + challengeLabel(run), "eyebrow"), el("code", run.id));
    head.append(title, el("span", run.state, "badge state-" + String(run.state).toLowerCase()));
    const controls = document.createElement("div"); controls.className = "controls sticky-controls";
    for (const action of ["pause", "resume", "stop", "reconcile", "export"]) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = action; button.dataset.action = action;
      // A disabled control says why, rather than leaving the miner to guess.
      const reason = !connected ? "Reconnect this browser first."
        : busy ? "Another request is in progress."
        : action === "resume" && !research.preflight.available ? "Resume needs a configured runner profile."
        : action !== "export" && ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE"].includes(run.state) ? "This campaign is " + run.state + "; there is nothing left to " + action + ". Export still gives its full record."
        : "";
      button.disabled = Boolean(reason);
      if (reason) button.title = reason;
      button.addEventListener("click", () => researchAction(run.id, action)); controls.append(button);
    }
    const tabs = el("nav", undefined, "tabs"); tabs.setAttribute("aria-label", "Campaign sections");
    for (const [name, label] of TABS) {
      const link = el("a", label); link.href = "#campaigns/" + encodeURIComponent(run.id) + "/" + name;
      if (name === current.tab) link.setAttribute("aria-current", "page");
      tabs.append(link);
    }
    detail.append(back, head, controls, tabs);
    const panels = {};
    for (const [name] of TABS) { panels[name] = el("section", undefined, "tab-panel"); panels[name].dataset.tab = name; panels[name].hidden = name !== current.tab; detail.append(panels[name]); }
    tabOverview(panels.overview, run);
    tabExperiments(panels.experiments, run);
    tabMetrics(panels.metrics, run);
    tabJournal(panels.journal, run);
    tabArtifacts(panels.artifacts, run);
    tabSubmission(panels.submission, run);
    tabLogs(panels.logs, run);
    tabSettings(panels.settings, run);
  }
  function missing(parent, text) { researchNote(parent, "Not yet available: " + text, "empty-state"); }
  function tabOverview(panel, run) {
    researchNote(panel, (run.agent || "Awaiting runtime") + " / " + (run.reasoning || "unavailable") + " / " + (run.compute || "unavailable") + " · Attempts: " + (run.attempted_experiments ?? 0) + " · Completed practice: " + (run.completed_experiments ?? 0));
    if (run.execution_label) researchNote(panel, run.execution_label, "hint");
    if (run.deadline_unix) researchNote(panel, "Deadline from your elapsed limit: " + new Date(run.deadline_unix * 1000).toLocaleString());
    else researchNote(panel, "No deadline: you set no elapsed limit.", "hint");
    if (run.research_guidance) {
      const task = document.createElement("p"); task.className = "frozen-guidance";
      task.textContent = "Frozen research task: " + run.research_guidance.text;
      panel.append(task);
      researchNote(panel, "Task identity: " + run.research_guidance.digest);
    }
    if (run.current_hypothesis) researchNote(panel, "Research hypothesis: " + (run.current_hypothesis.hypothesis || "unavailable"));
    const current = (run.operations || []).filter(op => op.state === "RESERVED");
    researchNote(panel, current.length ? "Active reserved operations: " + current.map(op => op.phase + " / " + op.id).join(", ") : "No active reserved operation reported.");
    if (run.usage) {
      const usage = document.createElement("div"); usage.className = "research-usage";
      for (const kind of ["available", "reserved", "reported", "uncertain"]) {
        const amount = run.usage[kind]?.provider_nanodollars;
        researchNote(usage, kind + ": " + (Number.isFinite(amount) ? "$" + (amount / 1e9).toFixed(8) : "unavailable"));
      }
      panel.append(usage);
      researchNote(panel, run.usage.cost_basis || "Cost basis unavailable.");
    } else missing(panel, "usage appears once the campaign ledger exists.");
    const results = run.final_results || [];
    researchNote(panel, results.length ? "Independent DEVELOPMENT results: " + results.length + " (see Submission)" : "No independent DEVELOPMENT result yet.", "development-summary");
  }
  function tabExperiments(panel, run) {
    if (run.selects === "miner") renderJourneyPractice(panel, run);
    const experiments = run.experiments || [];
    experiments.forEach((experiment, index) => renderPractice(panel, experiment, index));
    if (!experiments.length) missing(panel, "no practice experiment has completed in this campaign.");
  }
  function tabMetrics(panel, run) {
    if (!run.usage) { missing(panel, "resource metrics appear once the campaign ledger exists."); return; }
    const table = el("table", undefined, "metrics-table");
    const header = el("tr"); for (const name of ["Resource", "Your limit", "Reported", "Reserved", "Uncertain"]) header.append(el("th", name));
    table.append(header);
    const budget = run.usage.budget || {};
    for (const name of Object.keys(run.usage.reported || {})) {
      const row = el("tr");
      const cap = budget.ceilings ? budget.ceilings[name] : budget[name];
      row.append(el("td", words(name)), el("td", cap === undefined || cap === null ? "No limit" : String(cap)), el("td", String(run.usage.reported[name])), el("td", String(run.usage.reserved?.[name] ?? "")), el("td", String(run.usage.uncertain?.[name] ?? "")));
      table.append(row);
    }
    const wrap = el("div", undefined, "table-wrap"); wrap.append(table); panel.append(wrap);
    const scores = (run.experiments || []).map((experiment, index) => "#" + (index + 1) + ": " + (experiment.diagnostics?.descriptive_score ?? experiment.summary?.score ?? "unavailable"));
    researchNote(panel, scores.length ? "Descriptive practice scores (not accepted improvements): " + scores.join(" · ") : "No practice score yet.");
  }
  function tabJournal(panel, run) {
    const hypotheses = run.hypotheses || [];
    const decisions = run.decisions || [];
    for (const item of hypotheses) researchNote(panel, "Hypothesis " + (item.sequence ?? "") + ": " + (item.hypothesis || JSON.stringify(item)));
    for (const item of decisions) researchNote(panel, "Decision " + (item.sequence ?? "") + ": " + JSON.stringify(item));
    for (const item of run.capability_requests || []) researchNote(panel, "Capability request (grants nothing): " + JSON.stringify(item));
    for (const item of run.refusals || []) researchNote(panel, "Refused request (nothing ran): " + JSON.stringify(item));
    for (const outcome of run.epoch_outcomes || []) researchNote(panel, (outcome.selected_by === "miner" ? "Your" : "Agent") + " epoch " + outcome.epoch + ": " + outcome.status + " · " + (outcome.reason || "No reason reported") + " · " + (outcome.selected_by === "miner" ? "Your" : "Agent-reported") + " decision, not independent science.");
    if (!hypotheses.length && !decisions.length && !(run.epoch_outcomes || []).length) missing(panel, "the journal fills as hypotheses, decisions and epoch outcomes are recorded.");
  }
  function tabArtifacts(panel, run) {
    const freezes = run.candidate_freezes || [];
    for (const item of freezes) researchNote(panel, "Frozen candidate: " + JSON.stringify(item));
    const recipes = (run.experiments || []).filter(experiment => experiment.recipe).map(experiment => JSON.stringify(experiment.recipe));
    for (const text of [...new Set(recipes)]) researchNote(panel, "Practiced recipe: " + text, "code");
    if (!freezes.length && !recipes.length) missing(panel, "the controller does not expose trained weights or files; recipes and frozen candidates appear here once recorded.");
    researchNote(panel, "Export gives the full public record of this campaign as JSON.", "hint");
  }
  function renderValidatorOutcome(panel, result) {
    const o = result.result;
    const s = o.screening;
    const cases = s && s.cases && typeof s.cases === "object" ? Object.entries(s.cases).map(([k, v]) => words(k) + " " + v).join(", ") : "unavailable";
    const lines = [
      "Validator outcome, epoch " + result.epoch + ": " + o.state + (o.waiting ? " · waiting: " + o.waiting : ""),
      "Submission: " + (o.submission_id || "unavailable"),
      s ? "Screening on pool version " + (s.pool_version ?? "?") + ": " + (s.eligible === true ? "eligible" : s.eligible === false ? "not eligible" : "eligibility unavailable") + " · gates failed: " + ((s.gates_failed || []).join(", ") || "none") + " · cases: " + cases : "Screening: not shown in this feedback mode.",
      s && typeof s.score === "number" ? "Score: " + s.score + (typeof s.important_score === "number" ? " · important region: " + s.important_score : "") : "Score: not shown in this feedback mode.",
      "Nominated for a final: " + (o.nominated === true ? "yes" : o.nominated === false ? "no" : "unavailable") + ((o.finals || []).length ? " · finals: " + o.finals.map(f => f.state + (f.promoted ? " (promoted)" : "")).join(", ") : ""),
      (o.evidence || "DEVELOPMENT") + ": no qualification, no reward, no chain write.",
    ];
    for (const line of lines) researchNote(panel, line, "development-result");
  }
  function tabSubmission(panel, run) {
    if (run.selects === "miner") renderJourneySubmission(panel, run);
    else if (run.selects === "agent") researchNote(panel, "Carbon's agent freezes and submits in this campaign.", "hint");
    for (const result of run.final_results || []) {
      if (result.status === "VALIDATOR_OUTCOME" && result.result) { renderValidatorOutcome(panel, result); continue; }
      const verified = result.status === "VERIFIED_SOURCE" && result.result;
      researchNote(panel, "DEVELOPMENT evaluation: " + (verified ? (result.result.disposition || "disposition unavailable") + " · Accepted DEVELOPMENT improvement: " + (typeof result.result.accepted_development_improvement === "boolean" ? String(result.result.accepted_development_improvement) : "unavailable") : "Readback unavailable; no disposition inferred."), "development-result");
    }
    if (!(run.final_results || []).length) researchNote(panel, "DEVELOPMENT evaluation: no independent result available.", "development-result");
  }
  function tabLogs(panel, run) {
    const operations = run.operations || [];
    for (const op of operations) researchNote(panel, op.phase + " · " + op.state + " · " + op.id, "code");
    const held = operations.filter(op => op.state === "HELD");
    if (held.length) researchNote(panel, "Held capacity, never dispatched: " + held.map(op => op.phase + " / " + op.id).join(", "));
    if (!operations.length) missing(panel, "no operation has been recorded.");
    researchNote(panel, "Provider payloads, worker output and errors stay private to the campaign; the controller exposes operation states only.", "hint");
  }
  function tabSettings(panel, run) {
    const grid = el("dl", undefined, "review-grid");
    const row = (label, value) => grid.append(el("dt", label), el("dd", value));
    row("Challenge", challengeLabel(run));
    row("Profile", run.profile || "unavailable");
    row("Runtime revision", run.runtime_revision || "unavailable");
    row("Your budget", run.usage ? (Object.keys(run.usage.budget || {}).length ? JSON.stringify(run.usage.budget) : "none: no limit") : "unavailable");
    row("Admission", words(run.admission || "unavailable"));
    panel.append(grid);
    const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Research, usage, candidate and independent result";
    details.dataset.researchRun = run.id;
    details.open = expandedResearch.has(run.id);
    details.addEventListener("toggle", () => { if (details.isConnected) { if (details.open) expandedResearch.add(run.id); else expandedResearch.delete(run.id); } });
    const record = document.createElement("pre"); record.style.whiteSpace = "pre-wrap"; record.style.overflowWrap = "anywhere";
    record.textContent = JSON.stringify({challenge: run.challenge, runtime_revision: run.runtime_revision, agent_policy: run.agent_policy, research_guidance: run.research_guidance, effective_research_inputs: run.effective_research_inputs, hypothesis: run.current_hypothesis, hypotheses: run.hypotheses, decisions: run.decisions, outcomes: run.epoch_outcomes, usage: run.usage, experiments: run.experiments, operations: run.operations, freezes: run.candidate_freezes, development: run.final_results, capability_requests: run.capability_requests, refusals: run.refusals}, null, 2);
    details.append(summary, record); panel.append(details);
  }
  // A Challenge's own practice feedback (battery's summary, fit and backend),
  // as recorded; a field it does not report is shown as unavailable.
  // One Challenge's own model families (its construction contract), or the
  // historical list when the controller predates the per-Challenge field.
  function familiesFor(challengeId) {
    const by = launchOptions && launchOptions.families_by_challenge;
    return (by && challengeId && by[challengeId]) || (launchOptions ? launchOptions.families : []);
  }
  function renderChallengePractice(section, experiment) {
    const s = experiment.summary, fit = experiment.fit || {}, backend = experiment.backend || {};
    const num = v => typeof v === "number" && Number.isFinite(v) ? String(v) : "unavailable";
    researchNote(section, "Recipe: " + (experiment.backbone || experiment.recipe?.backbone || "unavailable") + (experiment.recipe?.parameters ? " · " + JSON.stringify(experiment.recipe.parameters) : ""), "code");
    researchNote(section, "Descriptive practice score: " + num(s.score) + " · important region: " + num(s.important_score) + " · lower is better · Not an accepted improvement.");
    const failures = s.gate_failures && typeof s.gate_failures === "object" ? Object.entries(s.gate_failures).filter(([, v]) => v).map(([k, v]) => k + " " + v) : [];
    researchNote(section, "Practice gates: " + (s.eligible === true ? "all passed" : s.eligible === false ? "failed · " + (failures.join(", ") || "gate counts unavailable") : "unavailable") + " · final admissibility is separate.");
    researchNote(section, "Cases: " + num(s.n_scored) + " scored of " + num(s.n_cases) + " · " + num(s.n_reference_invalid) + " reference invalid · " + num(s.n_failed_infra) + " infrastructure failed");
    researchNote(section, "Training: final loss " + num(fit.final_loss) + " · " + num(fit.n_params) + " parameters · " + num(fit.train_s) + " s training · backend " + (backend.kind || "unavailable"));
  }
  function renderPractice(parent, experiment, index) {
    const section = document.createElement("section"); section.className = "practice-result";
    const heading = document.createElement("h4"); heading.textContent = "Practice experiment " + (index + 1); section.append(heading);
    if (experiment.summary && typeof experiment.summary === "object") { renderChallengePractice(section, experiment); parent.append(section); return; }
    researchNote(section, "Completed updates: " + experiment.completed_steps + " · Worker seconds: " + experiment.worker_seconds);
    const diagnostics = experiment.diagnostics || {};
    researchNote(section, "Descriptive practice score: " + (diagnostics.descriptive_score ?? "unavailable") + " · Not an accepted improvement.");
    const failures = diagnostics.sampled_gate_failures;
    researchNote(section, Array.isArray(failures) ? "Sampled gate failures: " + (failures.length ? failures.join(", ") : "none reported; final admissibility is separate") : "Sampled gate failures unavailable.");
    const points = experiment.inline_curve;
    if (Array.isArray(points) && points.length >= 2 && points.length <= 8 && points.every((p, i) => p && Number.isFinite(p.step) && Number.isFinite(p.data_loss) && p.data_loss >= 0 && (!i || p.step > points[i - 1].step))) {
      const first = points[0], last = points[points.length - 1];
      const maximum = Math.max(...points.map(p => p.data_loss)) || 1;
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 480 190"); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Sampled training data loss by optimizer update, not a physical field or final evaluation");
      const add = (name, attributes, text) => {
        const node = document.createElementNS(ns, name);
        for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
        if (text !== undefined) node.textContent = text;
        svg.append(node);
      };
      const x = p => 65 + 395 * (p.step - first.step) / (last.step - first.step);
      const y = p => 145 - 125 * p.data_loss / maximum;
      for (const fraction of [0, 0.5, 1]) {
        const at = 145 - fraction * 125;
        add("line", {x1: 65, y1: at, x2: 460, y2: at, class: "curve-grid"});
        add("text", {x: 58, y: at + 4, "text-anchor": "end"}, (maximum * fraction).toPrecision(3));
      }
      add("polyline", {points: points.map(p => x(p) + "," + y(p)).join(" "), class: "curve-line"});
      for (const p of points) add("circle", {cx: x(p), cy: y(p), r: 3, class: "curve-point"});
      add("text", {x: 65, y: 164}, String(first.step));
      add("text", {x: 460, y: 164, "text-anchor": "end"}, String(last.step));
      add("text", {x: 265, y: 184, "text-anchor": "middle"}, "Optimizer update");
      section.append(svg);
      researchNote(section, "Training data loss · " + points.length + " recorded samples, joined for readability. First: " + first.data_loss + "; last: " + last.data_loss + ". Full projected samples remain in the record under Settings.");
    } else researchNote(section, "Training curve unavailable; no measurements inferred.");
    parent.append(section);
  }
  function draft(id, field, fallback) {
    const key = id + ":" + field;
    return key in journeyDrafts ? journeyDrafts[key] : fallback;
  }
  function journeyField(parent, id, field, labelText, element, fallback) {
    const label = document.createElement("label"); label.textContent = labelText;
    element.id = "journey-" + field + "-" + id; label.htmlFor = element.id;
    element.value = draft(id, field, fallback);
    element.addEventListener("input", () => { journeyDrafts[id + ":" + field] = element.value; store(draftKey, journeyDrafts); });
    parent.append(label, element);
    return element;
  }
  // The example recipe for a campaign's own Challenge, from its registered
  // description (validated by the same admission a submission meets). A
  // campaign recorded without a Challenge is the historical DEVELOPMENT one.
  function exampleRecipe(run) {
    const entry = run.challenge
      ? challengeEntry({id: run.challenge.id, version: run.challenge.version})
      : caps?.challenges.find(item => item.portfolio === "historical_development");
    return entry?.example_strategy ? JSON.stringify(entry.example_strategy, null, 2) : "";
  }
  function journeyState(run) {
    const journey = run.journey || {};
    return {journey, frozen: journey.frozen_awaiting_submission === true, exhausted: journey.final_exams_remaining === 0, ready: run.state === "READY"};
  }
  function practicedRecipes(run) {
    const practiced = [];
    for (const experiment of run.experiments || []) {
      if (!experiment.recipe) continue;
      const text = JSON.stringify(experiment.recipe);
      if (!practiced.includes(text)) practiced.push(text);
    }
    return practiced;
  }
  function renderJourneyPractice(parent, run) {
    // A person's own journey, with no Carbon agent: practice, freeze, submit.
    // Each step is an operation from the same table the agent and MCP use.
    const box = document.createElement("div"); box.className = "journey"; box.id = "journey-" + run.id;
    box.append(el("h4", "Your research · no Carbon agent"));
    researchNote(box, "1 · Practice a recipe here. 2 · Freeze one you practiced and 3 · submit it under Submission. Nothing reaches the chain.");
    const {journey, exhausted, ready} = journeyState(run);
    const example = exampleRecipe(run);
    const recipe = journeyField(box, run.id, "recipe", "Recipe to practice (JSON)", document.createElement("textarea"), example);
    recipe.rows = 8; recipe.className = "research-guidance";
    if (example) researchNote(box, "Prefilled with this Challenge's registered example, which passes admission. Edit it freely.", "hint");
    else researchNote(box, "No registered example for this campaign's Challenge; write a recipe.", "hint");
    const hypothesis = journeyField(box, run.id, "hypothesis", "What this trial tests", document.createElement("input"), "");
    if (!ready) researchNote(box, "Working: " + String(run.state).replaceAll("_", " ").toLowerCase() + ". The next step opens when the campaign is ready.");
    researchNote(box, "Final exams remaining: " + (journey.final_exams_remaining ?? "unavailable"));
    const buttons = document.createElement("div"); buttons.className = "controls";
    const practice = document.createElement("button"); practice.type = "button"; practice.id = "journey-practice-" + run.id; practice.textContent = "Run practice trial";
    practice.disabled = !connected || busy || !ready || exhausted;
    practice.addEventListener("click", () => {
      let strategy;
      try { strategy = JSON.parse(recipe.value); } catch (_) { message("The recipe is not valid JSON.", true); return; }
      operate("practice", {campaign: run.id, strategy, hypothesis: hypothesis.value || "practice"}, "Practice trial started. Its result appears under Experiments when training finishes.");
    });
    buttons.append(practice); box.append(buttons);
    if (launchOptions) {
      // Each family's true availability now, by its registry verdict.
      const byVerdict = {};
      for (const family of familiesFor(run.challenge && run.challenge.id)) (byVerdict[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      const labels = {supported: "Families you can freeze and submit now", not_yet_rebuildable: "Not yet rebuildable (research only)", needs_owner_decision: "Waiting on an owner decision", excluded: "Excluded"};
      for (const [verdict, label] of Object.entries(labels)) if (byVerdict[verdict]) researchNote(box, label + ": " + byVerdict[verdict].join(", "));
    }
    parent.append(box);
  }
  function renderJourneySubmission(parent, run) {
    const box = document.createElement("div"); box.className = "journey-submit";
    box.append(el("h4", "Freeze and submit"));
    const {journey, frozen, exhausted, ready} = journeyState(run);
    const practiced = practicedRecipes(run);
    researchNote(box, "Final exams remaining: " + (journey.final_exams_remaining ?? "unavailable") + " · Submitted epochs: " + ((journey.submitted_epochs || []).join(", ") || "none") + (frozen ? " · A frozen candidate is waiting for submission." : ""));
    const choose = document.createElement("select");
    for (const text of practiced) { const option = document.createElement("option"); option.value = text; option.textContent = text; choose.append(option); }
    journeyField(box, run.id, "candidate", "Practiced recipe to freeze", choose, practiced[0] || "");
    const reason = journeyField(box, run.id, "reason", "Why this candidate", document.createElement("input"), "");
    if (!practiced.length) researchNote(box, "No practiced recipe yet: a candidate must have a practice result before it can be frozen. Practice under Experiments.", "reason");
    const second = document.createElement("div"); second.className = "controls";
    const freeze = document.createElement("button"); freeze.type = "button"; freeze.id = "journey-freeze-" + run.id; freeze.textContent = "Freeze candidate";
    freeze.disabled = !connected || busy || !ready || !practiced.length || frozen || exhausted;
    freeze.addEventListener("click", () => operate("freeze_candidate", {campaign: run.id, strategy: JSON.parse(choose.value), reason: reason.value || "practiced"}, "Candidate frozen for this epoch."));
    const submit = document.createElement("button"); submit.type = "button"; submit.id = "journey-submit-" + run.id; submit.textContent = "Submit frozen candidate";
    submit.disabled = !connected || busy || !ready || !frozen;
    submit.addEventListener("click", () => operate("submit", {campaign: run.id}, "Submitted for the DEVELOPMENT comparison. The independent result appears below."));
    second.append(freeze, submit); box.append(second);
    parent.append(box);
  }

  // ---- Launch wizard. ----
  function selectChallenge(entry) {
    wizard = {...wizard, challenge: {id: entry.challenge_id, version: entry.version}};
    saveWizard(); render();
  }
  function describeComposition(value) {
    const budget = value.budget || {};
    const parts = [];
    if ("elapsed_seconds" in budget) parts.push(budget.elapsed_seconds + " s elapsed");
    if (budget.final_reserve) parts.push("final phase held back");
    for (const [name, cap] of Object.entries(budget.ceilings || {})) parts.push(words(name) + " ≤ " + cap);
    const agent = agentEntry(wizard.agentChoice);
    return "Launches with " + (value.agent ? (agent ? agent.label : value.agent) : "no choice yet") + " · budget: " + (parts.length ? parts.join(", ") : "none, no cap");
  }
  // Why this composition cannot launch right now, or null. Availability is
  // the options operation's, read from the host - never assumed.
  function compositionProblem(value) {
    if (!launchOptions) return "launch options have not been read yet";
    const agent = launchOptions.agents.find(option => option.value === value.agent);
    if (!agent) return "choose who selects and submits";
    if (agent.availability !== "available") return "the " + value.agent + " agent is unavailable: " + words(agent.reason);
    return budgetProblem(value.budget);
  }
  function budgetProblem(budget = {}) {
    const vocabulary = caps?.budget || launchOptions?.budget || {keys: [], ceilings: []};
    for (const key of Object.keys(budget)) if (!vocabulary.keys.includes(key)) return "a budget cannot set " + key;
    if ("elapsed_seconds" in budget && !(Number.isInteger(budget.elapsed_seconds) && budget.elapsed_seconds >= 1)) return "the elapsed limit must be a whole number of seconds, at least 1";
    if ("final_reserve" in budget && typeof budget.final_reserve !== "boolean") return "the final reserve is on or off";
    for (const [name, cap] of Object.entries(budget.ceilings || {})) {
      if (!vocabulary.ceilings.includes(name)) return "no resource is called " + name;
      if (!(Number.isInteger(cap) && cap >= 0)) return "the " + words(name) + " ceiling must be a whole number, 0 or more";
    }
    return null;
  }
  // Why a step cannot be passed yet, with what to do; null when it can.
  function stepProblem(step) {
    if (!connected || !caps) return "Connect this browser first.";
    if (step === "challenge") {
      const entry = challengeEntry(wizard.challenge);
      if (!entry) return "Choose a Challenge.";
      if (!entry.selectable) return entry.title + " cannot launch: " + words(entry.reason) + ". Next: " + entry.next_action;
    }
    if (step === "agent") {
      const agent = agentEntry(wizard.agentChoice);
      if (!agent) return "Choose who selects and submits.";
      if (agent.availability !== "available") return agent.label + " is unavailable: " + words(agent.reason) + ". Next: " + agent.next_action;
    }
    if (step === "model") {
      const agent = agentEntry(wizard.agentChoice);
      if (agent?.uses_model) {
        const provider = selectedProvider();
        if (!provider) return "Choose a model provider.";
        if (provider.availability !== "available") return provider.provider + " is unavailable: " + words(provider.reason) + ". Next: " + provider.next_action;
        if (!provider.models.some(model => model.id === wizard.model)) return "Choose a model.";
      }
    }
    if (step === "compute") {
      const compute = computeChoice();
      if (!compute || compute.availability !== "available") return "Compute unavailable: " + words(compute?.reason) + ". Next: " + (compute?.next_action || "Re-read capabilities.");
    }
    if (step === "limits") {
      const problem = budgetProblem(composition.budget);
      if (problem) return "Fix your limits: " + problem + ".";
    }
    if (step === "review") {
      for (const [name] of STEPS.slice(0, 5)) { const problem = stepProblem(name); if (problem) return problem; }
      if (!research.preflight.available) return "Research launch is unavailable: " + words(research.preflight.reason || research.preflight.status) + ".";
      const problem = compositionProblem(composition);
      if (problem) return "Cannot launch: " + problem + ".";
    }
    return null;
  }
  function renderWizard() {
    const index = Math.max(0, STEPS.findIndex(([name]) => name === wizard.step));
    const list = $("wizard-steps");
    list.replaceChildren();
    STEPS.forEach(([name, label], position) => {
      const item = el("li");
      const button = el("button", (position + 1) + " · " + label); button.type = "button";
      if (position === index) button.setAttribute("aria-current", "step");
      // A later step opens only once every step before it can be passed.
      button.disabled = position > index && STEPS.slice(0, position).some(([earlier]) => stepProblem(earlier));
      button.addEventListener("click", () => { wizard.step = name; saveWizard(); render(); });
      item.append(button); list.append(item);
    });
    for (const section of document.querySelectorAll("#launch .step")) section.hidden = section.dataset.step !== STEPS[index][0];
    const problem = stepProblem(STEPS[index][0]);
    $("wizard-back").disabled = index === 0;
    $("wizard-next").hidden = index === STEPS.length - 1;
    $("wizard-next").disabled = Boolean(problem);
    $("wizard-next-reason").textContent = problem && index < STEPS.length - 1 ? problem : "";
    renderWizardChallenges();
    renderWizardAgents();
    renderWizardModel();
    renderWizardCompute();
    renderWizardTools();
    renderLaunchComposition();
    renderWizardReview();
    renderResearchPreflight();
    const blocked = stepProblem("review");
    $("research-launch").disabled = !connected || busy || storageError || !research.preflight.available || Boolean(blocked);
    $("research-launch").textContent = pendingResearch ? "Retry same research launch" : "Launch research";
    const chosen = challengeEntry(wizard.challenge);
    $("wizard-launch-summary").textContent = chosen ? chosen.title + " \u00b7 version " + chosen.version + " \u00b7 " + describeComposition(composition) : "";
    $("wizard-launch-reason").textContent = blocked ? blocked : storageError ? "Browser retry storage is unavailable; launch is disabled to preserve duplicate protection." : "";
  }
  $("wizard-back").addEventListener("click", () => { const index = STEPS.findIndex(([name]) => name === wizard.step); if (index > 0) { wizard.step = STEPS[index - 1][0]; saveWizard(); render(); } });
  $("wizard-next").addEventListener("click", () => { const index = STEPS.findIndex(([name]) => name === wizard.step); if (index < STEPS.length - 1 && !stepProblem(wizard.step)) { wizard.step = STEPS[index + 1][0]; saveWizard(); render(); } });
  function renderWizardChallenges() {
    const target = $("wizard-challenges");
    if (!caps) { target.replaceChildren(el("p", "Connect to read the Challenge registry.", "hint")); $("wizard-challenge-description").replaceChildren(); return; }
    if (target.dataset.built !== JSON.stringify([wizard.challenge, caps.challenges.map(entry => entry.selectable), connected])) {
      target.replaceChildren();
      for (const entry of caps.challenges) {
        const label = el("label", undefined, "choice" + (entry.selectable ? "" : " unavailable"));
        const input = el("input"); input.type = "radio"; input.name = "wizard-challenge"; input.value = entry.challenge_id;
        input.checked = Boolean(wizard.challenge && wizard.challenge.id === entry.challenge_id && wizard.challenge.version === entry.version);
        // Unimplemented Challenges are shown, never offered as working choices.
        input.disabled = !entry.implemented;
        input.addEventListener("change", () => selectChallenge(entry));
        const text = el("span");
        text.append(el("strong", entry.title), el("span", " " + challengeStatus(entry) + (entry.version ? " · v" + entry.version : ""), "small-tag"));
        if (!entry.selectable) text.append(el("span", "Unavailable: " + words(entry.reason) + " · Next: " + entry.next_action, "reason"));
        label.append(input, text); target.append(label);
      }
      target.dataset.built = JSON.stringify([wizard.challenge, caps.challenges.map(entry => entry.selectable), connected]);
    }
    const description = $("wizard-challenge-description");
    const entry = challengeEntry(wizard.challenge);
    if (description.dataset.key !== (entry ? entry.challenge_id + "@" + entry.version : "")) {
      description.replaceChildren();
      if (entry?.implemented) { description.append(el("h3", entry.title)); renderDescription(description, entry); }
      description.dataset.key = entry ? entry.challenge_id + "@" + entry.version : "";
    }
  }
  function renderWizardAgents() {
    const box = $("research-selects");
    const notes = $("wizard-agent-notes");
    const key = JSON.stringify([caps?.agents.choices.map(choice => [choice.id, choice.availability]), wizard.agentChoice]);
    if (box.dataset.built === key) return;
    box.replaceChildren(el("legend", "Who selects and submits"));
    notes.replaceChildren();
    if (!caps) { box.dataset.built = key; return; }
    for (const choice of caps.agents.choices) {
      const label = el("label", undefined, "choice" + (choice.availability === "available" ? "" : " unavailable"));
      const input = el("input"); input.type = "radio"; input.name = "research-agent"; input.value = choice.id;
      input.checked = wizard.agentChoice === choice.id;
      input.disabled = choice.availability !== "available";
      input.addEventListener("change", () => { wizard.agentChoice = choice.id; composition = {...composition, agent: choice.launch_agent}; saveWizard(); render(); });
      const text = el("span");
      text.append(el("strong", choice.label), el("span", " " + choice.summary, "hint"));
      if (choice.availability !== "available") text.append(el("span", "Unavailable: " + words(choice.reason) + " · Next: " + choice.next_action, "reason"));
      label.append(input, text); box.append(label);
    }
    const external = agentEntry("external_mcp");
    if (wizard.agentChoice === "external_mcp" && external) researchNote(notes, "After launch, connect your client with: " + external.command + ". It sees this campaign and calls the same practice, freeze and submit operations.", "code");
    for (const item of caps.agents.unavailable) researchNote(notes, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
    box.dataset.built = key;
  }
  function renderWizardModel() {
    const target = $("wizard-model");
    target.replaceChildren();
    if (!caps) return;
    const agent = agentEntry(wizard.agentChoice);
    if (agent && !agent.uses_model) {
      researchNote(target, agent.label + " calls no model: nothing to choose here, and no credential is needed.");
      return;
    }
    researchNote(target, "You choose the provider and model and supply your own credential. " + caps.model.selection, "hint");
    for (const provider of caps.model.providers) {
      const group = el("fieldset", undefined, "selects");
      group.append(el("legend", provider.provider));
      for (const model of provider.models) {
        const label = el("label", undefined, "choice" + (provider.availability === "available" ? "" : " unavailable"));
        const input = el("input"); input.type = "radio"; input.name = "wizard-model"; input.value = provider.id + "/" + model.id;
        input.checked = wizard.provider === provider.id && wizard.model === model.id;
        input.disabled = provider.availability !== "available";
        input.addEventListener("change", () => { wizard.provider = provider.id; wizard.model = model.id; saveWizard(); render(); });
        label.append(input, el("span", model.id)); group.append(label);
      }
      researchNote(group, "Credential: " + provider.credential.reference + " · " + (provider.credential.configured === null ? provider.credential.basis : provider.credential.configured ? "configured" : "not configured"), "hint");
      if (provider.availability !== "available") unavailableNote(group, provider);
      target.append(group);
    }
    for (const item of caps.model.unavailable) researchNote(target, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
  }
  function renderWizardCompute() {
    const target = $("wizard-compute");
    target.replaceChildren();
    if (!caps) return;
    researchNote(target, caps.compute.selection, "hint");
    for (const choice of caps.compute.choices) {
      const box = card(target, choice.label, ...readiness(choice));
      researchNote(box, "Lane: " + choice.lane + " · " + Object.entries(choice.lanes).map(([lane, state]) => lane + " " + state.availability + (state.reason ? " (" + words(state.reason) + ")" : "")).join(" · "));
      if (choice.availability !== "available") unavailableNote(box, choice);
    }
    for (const item of caps.compute.unavailable) researchNote(target, item.id + " · unavailable: " + words(item.reason) + " · Next: " + item.next_action, "reason");
  }
  function renderWizardTools() {
    const target = $("wizard-tools");
    const entry = challengeEntry(wizard.challenge);
    const key = entry ? entry.challenge_id + "@" + entry.version : "";
    if (target.dataset.key === key) return;
    target.replaceChildren();
    target.dataset.key = key;
    if (!entry) { researchNote(target, "Choose a Challenge first: its tools come from its description.", "hint"); return; }
    target.append(el("h3", "Tools for " + entry.title));
    const grid = el("dl", undefined, "review-grid");
    for (const [name, detail] of Object.entries(entry.tools?.workflow || {})) grid.append(el("dt", name), el("dd", detail));
    if (entry.tools?.public_material?.length) grid.append(el("dt", "public material"), el("dd", entry.tools.public_material.join(", ")));
    if (entry.tools?.rebuildable_models?.length) grid.append(el("dt", "rebuildable models"), el("dd", entry.tools.rebuildable_models.join(", ")));
    target.append(grid);
    // The Challenge's own feedback modes; FULL is every Challenge's default.
    const modes = entry.setup_offers?.feedback_modes || [];
    if (modes.length > 1) {
      const id = "wizard-feedback-mode";
      const label = el("label", "Practice feedback"); label.htmlFor = id;
      const select = document.createElement("select"); select.id = id;
      for (const mode of modes) { const option = el("option", words(mode)); option.value = mode; select.append(option); }
      select.value = modes.includes(wizard.feedbackMode) ? wizard.feedbackMode : "FULL";
      select.addEventListener("change", () => { wizard.feedbackMode = select.value; saveWizard(); });
      target.append(label, select);
    }
    if (entry.tools?.how_to_request_unsupported) researchNote(target, entry.tools.how_to_request_unsupported, "hint");
  }
  function renderResearchPreflight() {
    const guidance = research.preflight.research_guidance;
    $("research-guidance-review").hidden = !connected || !guidance;
    $("research-guidance").value = connected && guidance ? guidance.text : "";
    $("research-runtime").textContent = connected && guidance ? "Configured runtime: " + research.preflight.runtime_revision + " · Task identity (frozen on launch): " + guidance.digest : "";
    $("research-preflight").textContent = connected ? research.preflight.status.replaceAll("_", " ") + (research.preflight.reason ? " · " + research.preflight.reason : "") + (research.preflight.available ? " · Admission: your subnet registration, read at launch · Budget: yours to set, or none" : "") : "Reconnect to reconcile research state. Controls are disabled.";
    const reviewPanel = $("research-review"); reviewPanel.replaceChildren();
    const review = connected && research.preflight.review;
    if (!review) return;
    researchNote(reviewPanel, "Experiment pause: " + review.experiment_pause);
    if (review.blockers?.length) researchNote(reviewPanel, "Launch unavailable: " + review.blockers.map(value => value.replaceAll("_", " ")).join("; "));
    researchNote(reviewPanel, "Your research runs on: " + review.execution.profile + " · Backend: " + review.execution.backend + " · Lane: " + review.execution.lane + " · " + review.execution.basis);
    // Stated before launch rather than discovered afterwards. Choosing a GPU
    // to research with never selects or rewrites the evaluator.
    if (review.final_evaluation) {
      researchNote(reviewPanel, "Independent DEVELOPMENT comparison runs on: " + review.final_evaluation.profile + " · Backend: " + review.final_evaluation.backend + " · " + review.final_evaluation.basis);
    }
    if (review.execution.assurance) {
      researchNote(reviewPanel, "This research lane establishes: " + review.execution.assurance.established.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ". It does not establish: " + review.execution.assurance.not_established.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ".");
    }
    if (review.readiness) {
      // Distinct states, never one green badge.
      const states = Object.entries(review.readiness).filter(([name]) => name !== "basis");
      researchNote(reviewPanel, "Readiness · " + states.map(([name, value]) => name.replaceAll("_", " ") + ": " + value).join(" · "));
      researchNote(reviewPanel, review.readiness.basis);
    }
    researchNote(reviewPanel, "Dependencies installed: " + review.execution.installed_dependencies + " · Device visibility: " + review.execution.device_visibility + " · Retained execution evidence: " + review.execution.runtime_evidence + " · Admission: " + review.execution.admission_readiness);
    researchNote(reviewPanel, "Admission: " + review.admission.gate.replaceAll("_", " ").toLowerCase() + " · " + review.admission.basis);
    researchNote(reviewPanel, review.resources.basis);
    const details = document.createElement("details");
    const label = document.createElement("summary"); label.textContent = "Exact configured identities, capabilities and resource limits";
    const data = document.createElement("pre"); data.textContent = JSON.stringify(review, null, 2);
    data.style.whiteSpace = "pre-wrap"; data.style.overflowWrap = "anywhere";
    details.append(label, data); reviewPanel.append(details);
  }
  function renderWizardReview() {
    const grid = $("wizard-review");
    grid.replaceChildren();
    const missingList = $("wizard-missing");
    missingList.replaceChildren();
    if (!caps) return;
    const row = (label, value) => grid.append(el("dt", label), el("dd", value));
    const entry = challengeEntry(wizard.challenge);
    const agent = agentEntry(wizard.agentChoice);
    const provider = selectedProvider();
    const compute = computeChoice();
    const budget = composition.budget || {};
    row("Identity", caps.profile.configured ? "Runner profile " + caps.profile.profile_id + " · registered hotkey read from it at launch" : "No runner profile");
    row("Network", research.preflight.review?.admission?.gate ? words(research.preflight.review.admission.gate).toLowerCase() + " · see Wallet & Identity for the network and netuid" : "Subnet registration, read at launch · see Wallet & Identity");
    row("Challenge", entry ? entry.title + " · " + entry.challenge_id + " · version " + entry.version + (entry.description?.contract_digest ? " · contract " + entry.description.contract_digest : "") : "Not chosen");
    row("Agent", agent ? agent.label + " (launch agent: " + agent.launch_agent + ")" : "Not chosen");
    row("Model", agent && !agent.uses_model ? "None: this agent calls no model" : provider && wizard.model ? provider.provider + " · " + wizard.model + " · credential " + (provider.credential.configured ? "configured" : "not configured") + ". " + caps.model.selection : "Not chosen");
    row("Compute", compute ? compute.label + " · " + compute.lane + " lane · " + compute.availability : "Unavailable");
    row("Tools", entry ? Object.keys(entry.tools?.workflow || {}).join(", ") || "none listed" : "Choose a Challenge");
    const limits = [];
    limits.push("elapsed: " + ("elapsed_seconds" in budget ? budget.elapsed_seconds + " s" : "no limit"));
    limits.push("final reserve: " + (budget.final_reserve ? "on" : "off"));
    for (const name of caps.budget.ceilings) limits.push(words(name) + ": " + (budget.ceilings && name in budget.ceilings ? budget.ceilings[name] : "no limit"));
    row("Your limits", limits.join(" · "));
    row("Unset limits", "An unset limit means no limit. Carbon sets none for you.");
    const problems = [];
    for (const [name, label] of STEPS.slice(0, 5)) { const problem = stepProblem(name); if (problem) problems.push({ok: false, text: label + ": " + problem}); }
    if (!research.preflight.available) problems.push({ok: false, text: "Research launch: " + words(research.preflight.reason || research.preflight.status)});
    problems.push({ok: null, text: "Subnet registration is read at launch, before anything is recorded.", href: "#wallet"});
    renderChecklist(missingList, problems);
  }
  function buildCeilings() {
    const box = $("budget-ceilings");
    const vocabulary = caps?.budget || launchOptions?.budget;
    if (!vocabulary || box.dataset.built) return;
    for (const name of vocabulary.ceilings) {
      const wrap = document.createElement("div");
      const label = document.createElement("label"); label.htmlFor = "ceiling-" + name; label.textContent = words(name);
      const input = document.createElement("input"); input.id = "ceiling-" + name; input.type = "number"; input.min = "0"; input.step = "1"; input.placeholder = "No limit"; input.dataset.ceiling = name;
      input.addEventListener("input", readAdvanced);
      wrap.append(label, input); box.append(wrap);
    }
    box.dataset.built = "1";
    writeAdvanced();
  }
  // Advanced inputs write into the composition; a blank field removes its key.
  function readAdvanced() {
    const budget = {};
    const whole = text => (text.trim() === "" ? undefined : Number(text));
    const elapsed = whole($("budget-elapsed").value);
    if (elapsed !== undefined) budget.elapsed_seconds = elapsed;
    if ($("budget-final-reserve").checked) budget.final_reserve = true;
    const ceilings = {};
    for (const input of document.querySelectorAll("[data-ceiling]")) {
      const cap = whole(input.value);
      if (cap !== undefined) ceilings[input.dataset.ceiling] = cap;
    }
    if (Object.keys(ceilings).length) budget.ceilings = ceilings;
    composition = {...composition, budget};
    saveWizard();
    render();
  }
  function writeAdvanced() {
    const budget = composition.budget || {};
    $("budget-elapsed").value = budget.elapsed_seconds ?? "";
    $("budget-final-reserve").checked = budget.final_reserve === true;
    for (const input of document.querySelectorAll("[data-ceiling]")) input.value = budget.ceilings?.[input.dataset.ceiling] ?? "";
  }
  function renderLaunchComposition() {
    buildCeilings();
    $("path-quick").setAttribute("aria-pressed", String(launchPath === "quick"));
    $("path-advanced").setAttribute("aria-pressed", String(launchPath === "advanced"));
    $("launch-advanced").hidden = launchPath !== "advanced";
    const availability = $("launch-availability");
    const chosen = wizard.challenge ? wizard.challenge.id : "";
    if (launchOptions && availability.dataset.built !== chosen) {
      availability.replaceChildren();
      const families = {};
      for (const family of familiesFor(chosen)) (families[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      for (const [verdict, names] of Object.entries(families)) researchNote(availability, "Model families · " + words(verdict) + ": " + names.join(", "));
      for (const [lane, state] of Object.entries(launchOptions.research_lanes)) researchNote(availability, "Research lane " + lane + " · " + state.availability + (state.reason ? ": " + words(state.reason) : ""));
      availability.dataset.built = chosen;
    }
    const problem = compositionProblem(composition);
    $("composition-summary").textContent = describeComposition(composition) + (problem ? " · cannot launch: " + problem : "");
    renderTemplates();
    return problem;
  }
  function readTemplates() {
    try { const value = JSON.parse(localStorage.getItem(templateKey) || "{}"); return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
    catch (_) { return null; }
  }
  function renderTemplates() {
    const templates = readTemplates();
    const pick = $("template-pick");
    const disabled = templates === null || !connected;
    for (const id of ["template-name", "template-save", "template-pick", "template-load", "template-delete"]) $(id).disabled = disabled;
    if (templates === null) { $("template-note").textContent = "Templates are unavailable: this browser refused its storage."; return; }
    const names = Object.keys(templates).sort();
    if (pick.dataset.names !== names.join("\n")) {
      pick.replaceChildren(...names.map(name => { const option = document.createElement("option"); option.value = name; option.textContent = name; return option; }));
      pick.dataset.names = names.join("\n");
    }
    $("template-load").disabled = disabled || !names.length;
    $("template-delete").disabled = disabled || !names.length;
  }
  // A template is a launch composition and nothing else: closed against the
  // launch operation's own fields, and checked against what is available now,
  // not when it was saved.
  function templateProblem(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return "it is not a launch composition";
    const fields = new Set([...(launchShape?.required || []), ...(launchShape?.optional || [])]);
    for (const key of Object.keys(value)) if (!["agent", "budget"].includes(key) || !fields.has(key)) return "it sets " + key + ", which a template cannot carry";
    return compositionProblem({agent: value.agent, budget: value.budget || {}});
  }
  $("path-quick").addEventListener("click", () => { launchPath = "quick"; saveWizard(); render(); });
  $("path-advanced").addEventListener("click", () => { launchPath = "advanced"; writeAdvanced(); saveWizard(); render(); });
  $("budget-elapsed").addEventListener("input", readAdvanced);
  $("budget-final-reserve").addEventListener("change", readAdvanced);
  $("template-save").addEventListener("click", () => {
    const name = $("template-name").value.trim();
    if (!name) { message("Name the template first.", true); return; }
    const problem = compositionProblem(composition);
    if (problem) { message("Not saved: " + problem + ".", true); return; }
    const templates = readTemplates();
    if (templates === null) { message("Not saved: this browser refused its storage.", true); return; }
    templates[name] = {agent: composition.agent, ...(Object.keys(composition.budget).length ? {budget: composition.budget} : {})};
    try { localStorage.setItem(templateKey, JSON.stringify(templates)); }
    catch (_) { message("Not saved: this browser refused its storage.", true); return; }
    $("template-name").value = "";
    message("Template “" + name + "” saved.");
    render();
  });
  $("template-load").addEventListener("click", async () => {
    const name = $("template-pick").value;
    const value = (readTemplates() || {})[name];
    // Availability is read again now: the moment of choosing is this one.
    try { launchOptions = await api("/api/v1/operations/options", {}); } catch (_) { /* keep the last read */ }
    const problem = templateProblem(value);
    if (problem) { message("Template “" + name + "” not loaded: " + problem + ".", true); render(); return; }
    composition = {agent: value.agent, budget: value.budget || {}};
    // A template carries the launch agent; "none" is the manual choice.
    wizard.agentChoice = value.agent === "autonomous" ? "autonomous" : "manual";
    launchPath = Object.keys(composition.budget).length ? "advanced" : "quick";
    writeAdvanced(); saveWizard();
    message("Template “" + name + "” loaded. " + describeComposition(composition) + ".");
    render();
  });
  $("template-delete").addEventListener("click", () => {
    const name = $("template-pick").value;
    const templates = readTemplates();
    if (!templates || !(name in templates)) return;
    delete templates[name];
    try { localStorage.setItem(templateKey, JSON.stringify(templates)); } catch (_) { message("Not deleted: this browser refused its storage.", true); return; }
    message("Template “" + name + "” deleted.");
    render();
  });
  async function operate(name, body, done) {
    if (!connected || busy) return;
    // One idempotency key per action, kept until answered: a retry of the
    // same request (a lost response, a reload) replays it, never repeats it.
    const operationKey = "carbon.launchpad.pending-operation.v1";
    let held = null;
    try { held = JSON.parse(sessionStorage.getItem(operationKey) || "null"); } catch (_) { held = null; }
    const action = held && held.name === name && JSON.stringify(held.body) === JSON.stringify(body) ? held : {name, body, key: crypto.randomUUID()};
    try { sessionStorage.setItem(operationKey, JSON.stringify(action)); } catch (_) { /* the key still covers this request */ }
    busy = true; render();
    try {
      await api("/api/v1/operations/" + name, {...body, idempotency_key: action.key}, undefined, 20000);
      try { sessionStorage.removeItem(operationKey); } catch (_) { /* nothing held */ }
      message(done);
    } catch (error) { message("Not done: " + error.message.replaceAll("_", " "), true); }
    finally { busy = false; await refresh(); render(); }
  }
  async function researchAction(id, action) {
    if (!connected || busy) return;
    busy = true; render();
    try {
      if (action === "export") download(await api("/api/v1/research/" + id), "carbon-research-" + id + ".json");
      else await api("/api/v1/research/" + id + "/" + action, {});
      message("Research request acknowledged. Check observed state and cleanup in the campaign.");
    } catch (error) { message("Research request unresolved: " + error.message, true); }
    finally { busy = false; await refresh(); render(); }
  }
  $("research-launch").addEventListener("click", async () => {
    if (!connected || busy || storageError || !research.preflight.available) return;
    if (!pendingResearch) {
      const problem = stepProblem("review");
      if (problem) { message("Not launched: " + problem, true); return; }
      const entry = challengeEntry(wizard.challenge);
      // The Challenge is always sent, exactly: there is no default Challenge.
      pendingResearch = {key: crypto.randomUUID(), body: {profile: research.preflight.profile, agent: composition.agent, challenge: entry.challenge_id, challenge_version: entry.version}};
      if (Object.keys(composition.budget).length) pendingResearch.body.budget = composition.budget;
      // A feedback mode only when the Challenge offers it and it is not FULL.
      if (wizard.feedbackMode && wizard.feedbackMode !== "FULL" && (entry.setup_offers?.feedback_modes || []).includes(wizard.feedbackMode)) pendingResearch.body.feedback_mode = wizard.feedbackMode;
      // The chosen provider and model, when the agent calls one and the launch
      // carries them; the key file stays in the runner profile.
      const provider = selectedProvider();
      if (agentEntry(wizard.agentChoice)?.uses_model && caps.model.launch_field && provider?.availability === "available" && wizard.model) {
        pendingResearch.body.model_provider = provider.id;
        pendingResearch.body.model = wizard.model;
      }
      if (research.preflight.review_digest) pendingResearch.body.review_digest = research.preflight.review_digest;
      try { sessionStorage.setItem(researchKey, JSON.stringify(pendingResearch)); }
      catch (_) { storageError = true; render(); return; }
    }
    busy = true; render();
    try {
      const run = await api("/api/v1/research", pendingResearch.body, pendingResearch.key);
      sessionStorage.removeItem(researchKey); pendingResearch = null;
      message("Research launch recorded. Runtime preflight and actual outcome appear in the campaign.");
      wizard.step = "challenge"; saveWizard();
      if (run && run.id) location.hash = "#campaigns/" + encodeURIComponent(run.id) + "/overview";
    } catch (error) { message("Research launch not confirmed: " + error.message + ". Retry retains the same request.", true); }
    finally { busy = false; await refresh(); render(); }
  });
  buildNavigation();
  show();
  setInterval(refresh, 1500);
})();
