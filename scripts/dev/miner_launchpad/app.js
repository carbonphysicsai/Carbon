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
  // An unavailable thing, shown as such: its reason and what to do next.
  function unavailableNote(parent, item) {
    researchNote(parent, "Unavailable: " + words(item.reason) + (item.next_action ? " · Next: " + item.next_action : ""), "reason");
  }
  function card(parent, title, tag) {
    const box = el("div", undefined, "integration card");
    const head = el("div", undefined, "card-head");
    head.append(el("h3", title));
    if (tag) head.append(el("span", tag, "small-tag"));
    box.append(head); parent.append(box);
    return box;
  }
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
      const error = new Error(result.error || "request_failed");
      error.status = response.status;
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
    $("settings-recheck").disabled = !connected || busy;
    // Connected: the token form steps aside; interrupted or new, it returns.
    $("connect-panel").hidden = connected;
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

  $("onboarding-status").addEventListener("click", () => onboardingCall("status"));
  $("onboarding-prepare").addEventListener("click", () => onboardingCall("prepare"));
  $("onboarding-confirm").addEventListener("click", () => onboardingCall("confirm"));

  // ---- Capabilities: read on connect and on request, never assumed. ----
  async function readCapabilities() {
    const value = await api("/api/v1/control-center/capabilities", undefined, undefined, 20000);
    if (value.schema !== CAPS_SCHEMA) throw new Error("unsupported_controller_version");
    caps = value;
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
    // Where the miner may run their own research. Rendered beside the exam
    // environment on purpose: they choose the first and are told the second.
    const panel = $("exam-environment");
    if (!choices.length) return;
    const heading = document.createElement("h3");
    heading.textContent = "Your research compute";
    panel.append(heading);
    for (const choice of choices.filter(entry => entry.selectable !== false)) {
      const box = document.createElement("div"); box.className = "integration";
      const title = document.createElement("strong");
      title.textContent = choice.id.replaceAll("-", " ");
      const summary = document.createElement("p"); summary.textContent = choice.summary;
      box.append(title, summary);
      if (choice.requires?.length) {
        researchNote(box, "Needs: " + choice.requires.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      }
      if (choice.not_required?.length) {
        researchNote(box, "Not needed: " + choice.not_required.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      }
      panel.append(box);
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
    researchNote(panel, "Backend profile: " + contract.backend_profile.profile_id + " · " + contract.backend_profile.backend + " · " + contract.backend_profile.scope);
    // Declared is not qualified, and the page says which this is.
    researchNote(panel, "Qualification: declared, not qualified · Backend support " + contract.qualification.backend_support + " · " + contract.qualification.basis);
    researchNote(panel, "You submit: " + contract.submission.accepted.replaceAll("_", " ").toLowerCase() + ". Not accepted: " + contract.submission.not_accepted.map(value => value.replaceAll("_", " ").toLowerCase()).join("; ") + ".");
    researchNote(panel, "Your research hardware is not constrained by this contract and does not have to match it. No provider is prescribed, for you or for a validator.");
    for (const limitation of contract.known_limitations || []) {
      researchNote(panel, "Disclosed limitation · " + limitation.statement + " " + limitation.consequence);
    }
    const details = document.createElement("details");
    const label = document.createElement("summary");
    label.textContent = "Pinned versions, resource envelope and containment";
    const data = document.createElement("pre"); data.textContent = JSON.stringify(contract, null, 2);
    data.style.whiteSpace = "pre-wrap"; data.style.overflowWrap = "anywhere";
    details.append(label, data); panel.append(details);
  }

  // ---- Overview. ----
  function prerequisites() {
    // What a launch needs, each read from the controller - never assumed met.
    if (!caps) return [];
    const items = [];
    items.push(caps.profile.configured
      ? {ok: true, text: "Runner profile configured: " + caps.profile.profile_id}
      : {ok: false, text: "Runner profile: " + words(caps.profile.reason), next: caps.profile.next_action});
    items.push({ok: null, text: "Subnet registration: read at launch, before anything is recorded.", next: "Check your hotkey under Wallet & Identity.", href: "#wallet"});
    const selectable = caps.challenges.filter(entry => entry.selectable);
    items.push(selectable.length
      ? {ok: true, text: "Challenges you can launch: " + selectable.map(entry => entry.title).join(", ")}
      : {ok: false, text: "No Challenge can be launched here yet.", next: (caps.challenges.find(entry => entry.implemented) || {}).next_action, href: "#challenges"});
    const agents = caps.agents.choices.filter(choice => choice.availability === "available");
    items.push(agents.length
      ? {ok: true, text: "Agents available: " + agents.map(choice => choice.label).join(", ")}
      : {ok: false, text: "No agent can launch yet.", next: caps.agents.choices[0]?.next_action, href: "#agents"});
    const provider = caps.model.providers.find(item => item.availability === "available");
    items.push(provider
      ? {ok: true, text: "Model credential configured for " + provider.provider}
      : {ok: false, text: "No model provider credential configured (only Carbon's autonomous agent needs one).", next: caps.model.providers[0]?.next_action, href: "#agents"});
    const compute = computeChoice();
    items.push(compute && compute.availability === "available"
      ? {ok: true, text: "Compute: " + compute.label}
      : {ok: false, text: "Compute unavailable: " + words(compute?.reason), next: compute?.next_action, href: "#compute"});
    return items;
  }
  function renderChecklist(list, items) {
    list.replaceChildren();
    for (const item of items) {
      const entry = el("li", undefined, item.ok === true ? "ok" : item.ok === false ? "missing" : "pending");
      entry.append(el("span", item.ok === true ? "Ready" : item.ok === false ? "Missing" : "At launch", "state"), el("span", item.text));
      if (item.next) entry.append(el("span", "Next: " + item.next, "next"));
      if (item.href) { const link = el("a", "Open", "inline-link"); link.href = item.href; entry.append(link); }
      list.append(entry);
    }
  }
  function renderOverview() {
    const list = $("overview-prerequisites");
    if (!connected || !caps) { list.replaceChildren(el("li", "Connect to read what this controller can do.", "hint")); }
    else renderChecklist(list, prerequisites());
    const active = $("overview-active");
    active.replaceChildren();
    if (!connected) { researchNote(active, "Connect to see your campaigns.", "hint"); return; }
    const live = research.runs.filter(run => !TERMINAL.includes(run.state));
    if (!research.runs.length) {
      const empty = el("div", undefined, "empty");
      empty.append(el("h3", "No campaign yet."), el("p", "Start one with New campaign: choose a Challenge, who researches it, and your limits or none."));
      active.append(empty);
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
  function renderCatalogs() {
    const views = ["challenge-catalog", "agent-catalog", "compute-catalog", "connection-catalog", "wallet-profile"];
    if (!connected || !caps) {
      for (const id of views) $(id).replaceChildren(el("p", id === "wallet-profile" ? "" : "Connect to read this controller's capabilities.", "hint"));
      return;
    }
    renderChallengeCatalog();
    renderAgentCatalog();
    renderComputeCatalog();
    renderConnections();
    renderWallet();
  }
  function challengeStatus(entry) {
    return entry.status + (entry.selectable ? " · launchable" : "");
  }
  function renderChallengeCatalog() {
    const target = $("challenge-catalog");
    if (target.contains(document.activeElement) && document.activeElement.tagName === "SUMMARY") return;
    const open = new Set([...target.querySelectorAll("details[open]")].map(node => node.dataset.key));
    target.replaceChildren();
    for (const entry of caps.challenges) {
      const box = card(target, entry.title, challengeStatus(entry));
      researchNote(box, entry.challenge_id + (entry.version ? " · version " + entry.version : "") + " · " + words(entry.portfolio) + (entry.tracking ? " · " + entry.tracking : ""), "hint");
      if (!entry.selectable) unavailableNote(box, entry);
      if (entry.implemented) {
        researchNote(box, "This host: " + (entry.usable_here ? "shows every requirement of " + entry.profile : "has not shown " + entry.missing_here.map(words).join(", ") + " (the launch still reads your profile's runtime)"), "hint");
        const details = document.createElement("details"); details.dataset.key = entry.challenge_id;
        details.open = open.has(entry.challenge_id);
        details.append(el("summary", "Description"));
        renderDescription(details, entry);
        box.append(details);
        const choose = el("button", "Use for a new campaign"); choose.type = "button";
        choose.disabled = !entry.selectable;
        choose.addEventListener("click", () => { selectChallenge(entry); location.hash = "#launch"; });
        box.append(choose);
      }
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
    parent.append(grid);
  }
  function renderAgentCatalog() {
    const target = $("agent-catalog");
    target.replaceChildren();
    for (const choice of caps.agents.choices) {
      const box = card(target, choice.label, choice.availability);
      researchNote(box, choice.summary);
      if (choice.command) researchNote(box, "Command: " + choice.command, "code");
      if (choice.availability !== "available") unavailableNote(box, choice);
    }
    for (const provider of caps.model.providers) {
      const box = card(target, "Model provider · " + provider.provider, provider.availability);
      researchNote(box, "Models: " + provider.models.map(model => model.id).join(", ") + " · used by Carbon's autonomous agent only");
      researchNote(box, "Credential: " + provider.credential.reference + " · " + (provider.credential.configured === null ? provider.credential.basis : provider.credential.configured ? "configured" : "not configured") + " · held by " + provider.credential.held_by);
      if (provider.availability !== "available") unavailableNote(box, provider);
    }
    for (const item of [...caps.agents.unavailable, ...caps.model.unavailable]) unavailableNote(card(target, item.id, "unavailable"), item);
  }
  function renderComputeCatalog() {
    const target = $("compute-catalog");
    target.replaceChildren();
    for (const choice of caps.compute.choices) {
      const box = card(target, choice.label, choice.availability);
      researchNote(box, "Lanes: " + Object.entries(choice.lanes).map(([lane, state]) => lane + " " + state.availability + (state.reason ? " (" + words(state.reason) + ")" : "")).join(" · "));
      researchNote(box, caps.compute.selection, "hint");
      if (choice.availability !== "available") unavailableNote(box, choice);
    }
    for (const item of caps.compute.unavailable) unavailableNote(card(target, item.id, "unavailable"), item);
  }
  function renderConnections() {
    const target = $("connection-catalog");
    target.replaceChildren();
    const mcp = agentEntry("external_mcp");
    if (mcp) {
      const box = card(target, "Your own MCP client · stdio", mcp.availability);
      researchNote(box, "Run on this machine with your runner profile. Every operation - launch, observe, practice, freeze, submit, halt, resume - is the same one this page calls, over the same records. Nothing is issued by Carbon.");
      researchNote(box, mcp.command, "code");
      if (mcp.availability !== "available") unavailableNote(box, mcp);
    }
    for (const item of caps.connections) unavailableNote(card(target, item.id, "unavailable"), item);
  }
  function renderWallet() {
    const target = $("wallet-profile");
    target.replaceChildren();
    const box = card(target, "Research identity", caps.profile.configured ? "configured" : "not configured");
    if (caps.profile.configured) researchNote(box, "Runner profile " + caps.profile.profile_id + ". Your registered miner is read from it at launch; signing stays in your own wallet.");
    else unavailableNote(box, caps.profile);
    for (const item of caps.wallet) {
      const entry = card(target, item.id, "your wallet");
      researchNote(entry, words(item.reason) + " · " + item.next_action);
    }
  }

  // ---- Campaigns: list, deep-linked detail and tabs. ----
  function renderCampaigns() {
    const list = $("research-runs");
    const current = route();
    const detail = $("campaign-detail");
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
      button.disabled = !connected || busy || (action === "resume" && !research.preflight.available) || (action !== "export" && ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE"].includes(run.state));
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
    const scores = (run.experiments || []).map((experiment, index) => "#" + (index + 1) + ": " + (experiment.diagnostics?.descriptive_score ?? "unavailable"));
    researchNote(panel, scores.length ? "Descriptive practice scores (not accepted improvements): " + scores.join(" · ") : "No practice score yet.");
  }
  function tabJournal(panel, run) {
    const hypotheses = run.hypotheses || [];
    const decisions = run.decisions || [];
    for (const item of hypotheses) researchNote(panel, "Hypothesis " + (item.sequence ?? "") + ": " + (item.hypothesis || JSON.stringify(item)));
    for (const item of decisions) researchNote(panel, "Decision " + (item.sequence ?? "") + ": " + JSON.stringify(item));
    for (const item of run.capability_requests || []) researchNote(panel, "Capability request (grants nothing): " + JSON.stringify(item));
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
  function tabSubmission(panel, run) {
    if (run.selects === "miner") renderJourneySubmission(panel, run);
    else if (run.selects === "agent") researchNote(panel, "Carbon's agent freezes and submits in this campaign.", "hint");
    for (const result of run.final_results || []) {
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
    details.open = expandedResearch.has(run.id);
    details.addEventListener("toggle", () => { if (details.isConnected) { if (details.open) expandedResearch.add(run.id); else expandedResearch.delete(run.id); } });
    const record = document.createElement("pre"); record.style.whiteSpace = "pre-wrap"; record.style.overflowWrap = "anywhere";
    record.textContent = JSON.stringify({challenge: run.challenge, runtime_revision: run.runtime_revision, agent_policy: run.agent_policy, research_guidance: run.research_guidance, effective_research_inputs: run.effective_research_inputs, hypothesis: run.current_hypothesis, hypotheses: run.hypotheses, decisions: run.decisions, outcomes: run.epoch_outcomes, usage: run.usage, experiments: run.experiments, operations: run.operations, freezes: run.candidate_freezes, development: run.final_results, capability_requests: run.capability_requests}, null, 2);
    details.append(summary, record); panel.append(details);
  }
  function renderPractice(parent, experiment, index) {
    const section = document.createElement("section"); section.className = "practice-result";
    const heading = document.createElement("h4"); heading.textContent = "Practice experiment " + (index + 1); section.append(heading);
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
      for (const family of launchOptions.families) (byVerdict[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
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
      const box = card(target, choice.label, choice.availability);
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
    if (launchOptions && !availability.dataset.built) {
      const families = {};
      for (const family of launchOptions.families) (families[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      for (const [verdict, names] of Object.entries(families)) researchNote(availability, "Model families · " + words(verdict) + ": " + names.join(", "));
      for (const [lane, state] of Object.entries(launchOptions.research_lanes)) researchNote(availability, "Research lane " + lane + " · " + state.availability + (state.reason ? ": " + words(state.reason) : ""));
      availability.dataset.built = "1";
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
    busy = true; render();
    try {
      await api("/api/v1/operations/" + name, body, undefined, 20000);
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
