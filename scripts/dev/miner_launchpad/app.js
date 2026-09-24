"use strict";
(() => {
  let token = "";
  let selected = "";
  let runs = [];
  let pending = null;
  let busy = false;
  let polling = false;
  let connected = false;
  let developmentSources = [];
  let research = {preflight: {available: false}, runs: []};
  let pendingResearch = null;
  const expandedResearch = new Set();
  // What a person has typed into a campaign's journey, kept across refreshes.
  const journeyDrafts = {};
  // Every launch-time choice with its true availability, from the options
  // operation - the same one an MCP client reads. Never a static list.
  let launchOptions = null;
  // The one launch composition. The quick and advanced paths edit this same
  // object, templates save and load it, and the launch body is built from it;
  // there is no second copy to disagree with. `agent` stays null until the
  // person or a template chooses, so a default is never mistaken for a choice.
  let composition = {agent: null, budget: {}};
  let launchPath = "quick";
  let launchShape = null;
  const templateKey = "carbon.launchpad.launch-templates.v1";
  const STARTER_RECIPE = JSON.stringify({schema_version: "1.0", challenge_id: "burgers-dynamics-v1", backbone: "fno", parameters: {steps: 64}}, null, 2);
  const researchKey = "carbon.launchpad.pending-research.v1";
  const pendingKey = "carbon.launchpad.pending.v1";
  let storageError = false;
  try { pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null"); pendingResearch = JSON.parse(sessionStorage.getItem(researchKey) || "null"); }
  catch (_) { storageError = true; }
  const $ = id => document.getElementById(id);
  const message = (text, error = false) => {
    $("message").textContent = text;
    $("message").className = error ? "message error" : "message";
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
      const error = new Error(result.error || "request_failed");
      error.status = response.status;
      throw error;
    }
    return result;
  }
  function render() {
    renderResearch();
    renderOnboarding();
    const sources = $("development-sources");
    sources.replaceChildren();
    if (!connected || !developmentSources.length) {
      const note = document.createElement("p"); note.className = "hint";
      note.textContent = connected ? "No historical DEVELOPMENT source is attached. Current research campaigns are shown separately below." : "Reconnect to verify current source state.";
      sources.append(note);
    }
    if (connected) for (const source of developmentSources) {
      const card = document.createElement("div"); card.className = "integration";
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
          const blob = new Blob([JSON.stringify(fresh, null, 2)], {type: "application/json"});
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a"); anchor.href = url;
          anchor.download = "carbon-development-" + source.id + ".json";
          anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) { message("Receipt export unavailable: " + error.message, true); }
        finally { busy = false; await refresh(); render(); }
      });
      card.append(title, note, button); sources.append(card);
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
        ["Network", value.network + " \u00b7 netuid " + value.netuid],
        ["Mechanism", value.mechanism],
        ["Recycle amount", value.cost && value.cost.value === "NOT_READ"
          ? "Not read by Carbon \u2014 your wallet shows it at signing"
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
    } catch (error) {
      showOnboarding([onboardingLine("Could not read the registration requirements: " + error.message, "error")]);
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

  async function refresh() {
    if (!token || polling) return;
    polling = true;
    try {
      await onboardingRequirements();
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
      render();
      $("connection-state").textContent = "Connected";
    } catch (error) {
      connected = false;
      render();
      $("connection-state").textContent = "Connection interrupted";
      message("Controller connection interrupted. Runs may still be active. Reconnect before issuing another command.", true);
    } finally { polling = false; }
  }
  $("connect-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || polling) return;
    connected = false;
    render();
    token = $("token").value.trim();
    try {
      const catalog = await api("/api/v1/capabilities");
      if (catalog.schema !== "carbon.launchpad.rehearsal.v1" || catalog.mode !== "REHEARSAL") {
        throw new Error("unsupported_controller_version");
      }
      $("token").value = "";
      $("integrations").replaceChildren();
      for (const item of catalog.unavailable) {
        const card = document.createElement("div"); card.className = "integration";
        const title = document.createElement("strong"); title.textContent = item.id;
        const reason = document.createElement("p"); reason.textContent = item.reason.replaceAll("_", " ");
        card.append(title, reason); $("integrations").append(card);
      }
      // Order matters: renderExamEnvironment clears the panel before filling
      // it, so the compute choices are appended after it rather than before.
      await renderExamEnvironment();
      renderComputeChoices(catalog.research_compute || []);
      message("Connected. Records persist on this machine. Research dispatch requires the separate approved profile shown below.");
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
    const blob = new Blob([JSON.stringify(run, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = "carbon-rehearsal-" + run.id + ".json";
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
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
      const card = document.createElement("div"); card.className = "integration";
      const title = document.createElement("strong");
      title.textContent = choice.id.replaceAll("-", " ");
      const summary = document.createElement("p"); summary.textContent = choice.summary;
      card.append(title, summary);
      if (choice.requires?.length) {
        researchNote(card, "Needs: " + choice.requires.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      }
      if (choice.not_required?.length) {
        researchNote(card, "Not needed: " + choice.not_required.map(value => value.replaceAll("_", " ").toLowerCase()).join("; "));
      }
      panel.append(card);
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

  function researchNote(parent, text, className = "") {
    const note = document.createElement("p"); note.textContent = text; note.className = className; parent.append(note);
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
      researchNote(section, "Training data loss · " + points.length + " recorded samples, joined for readability. First: " + first.data_loss + "; last: " + last.data_loss + ". Full projected samples remain in the record below.");
    } else researchNote(section, "Training curve unavailable; no measurements inferred.");
    parent.append(section);
  }
  function renderResearch() {
    const guidance = research.preflight.research_guidance;
    $("research-guidance-review").hidden = !connected || !guidance;
    $("research-guidance").value = connected && guidance ? guidance.text : "";
    $("research-runtime").textContent = connected && guidance ? "Configured runtime: " + research.preflight.runtime_revision + " · Task identity (frozen on launch): " + guidance.digest : "";
    $("research-preflight").textContent = connected ? research.preflight.status.replaceAll("_", " ") + (research.preflight.reason ? " · " + research.preflight.reason : "") + (research.preflight.available ? " · Admission: your subnet registration, read at launch · Budget: yours to set, or none" : "") : "Reconnect to reconcile research state. Controls are disabled.";
    const reviewPanel = $("research-review"); reviewPanel.replaceChildren();
    const review = connected && research.preflight.review;
    if (review) {
      researchNote(reviewPanel, "Experiment pause: " + review.experiment_pause);
      if (review.blockers?.length) researchNote(reviewPanel, "Launch unavailable: " + review.blockers.map(value => value.replaceAll("_", " ")).join("; "));
      researchNote(reviewPanel, "Challenge: " + review.challenge + " · " + review.reconstruction);
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
      researchNote(reviewPanel, "Model capabilities: " + review.capabilities.backbones.join(", ") + " · " + review.capabilities.selection);
      researchNote(reviewPanel, "Training: " + review.capabilities.training);
      researchNote(reviewPanel, "Admission: " + review.admission.gate.replaceAll("_", " ").toLowerCase() + " · " + review.admission.basis);
      researchNote(reviewPanel, review.resources.basis);
      const details = document.createElement("details");
      const label = document.createElement("summary"); label.textContent = "Exact configured identities, capabilities and resource limits";
      const data = document.createElement("pre"); data.textContent = JSON.stringify(review, null, 2);
      data.style.whiteSpace = "pre-wrap"; data.style.overflowWrap = "anywhere";
      details.append(label, data); reviewPanel.append(details);
    }
    const blocked = renderLaunchComposition();
    $("research-launch").disabled = !connected || busy || storageError || !research.preflight.available || Boolean(blocked);
    $("research-launch").textContent = pendingResearch ? "Retry same research launch" : "Launch research";
    const container = $("research-runs");
    // Never rebuild under a person's cursor: the journey is typed into.
    const active = document.activeElement;
    if (active && container.contains(active) && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)) return;
    container.replaceChildren();
    for (const run of research.runs) {
      const card = document.createElement("div"); card.className = "integration";
      const title = document.createElement("h3"); title.textContent = run.id.slice(0, 10) + " · " + run.state;
      const description = document.createElement("p"); description.textContent = (run.agent || "Awaiting runtime") + " / " + (run.reasoning || "unavailable") + " / " + (run.compute || "unavailable") + " · Attempts: " + (run.attempted_experiments ?? 0) + " · Completed practice: " + (run.completed_experiments ?? 0);
      card.append(title, description);
      if (run.research_guidance) {
        const task = document.createElement("p"); task.className = "frozen-guidance";
        task.textContent = "Frozen research task: " + run.research_guidance.text;
        card.append(task);
        researchNote(card, "Task identity: " + run.research_guidance.digest);
      }
      if (run.current_hypothesis) researchNote(card, "Research hypothesis: " + (run.current_hypothesis.hypothesis || "unavailable"));
      const current = (run.operations || []).filter(op => op.state === "RESERVED");
      researchNote(card, current.length ? "Active reserved operations: " + current.map(op => op.phase + " / " + op.id).join(", ") : "No active reserved operation reported.");
      const held = (run.operations || []).filter(op => op.state === "HELD");
      if (held.length) researchNote(card, "Held capacity, never dispatched: " + held.map(op => op.phase + " / " + op.id).join(", "));
      if (run.usage) {
        const usage = document.createElement("div"); usage.className = "research-usage";
        for (const kind of ["available", "reserved", "reported", "uncertain"]) {
          const amount = run.usage[kind]?.provider_nanodollars;
          researchNote(usage, kind + ": " + (Number.isFinite(amount) ? "$" + (amount / 1e9).toFixed(8) : "unavailable"));
        }
        card.append(usage);
        researchNote(card, run.usage.cost_basis || "Cost basis unavailable.");
      }
      for (const outcome of run.epoch_outcomes || []) researchNote(card, (outcome.selected_by === "miner" ? "Your" : "Agent") + " epoch " + outcome.epoch + ": " + outcome.status + " · " + (outcome.reason || "No reason reported") + " · " + (outcome.selected_by === "miner" ? "Your" : "Agent-reported") + " decision, not independent science.");
      if (run.selects === "miner") renderJourney(card, run);
      for (const result of run.final_results || []) {
        const verified = result.status === "VERIFIED_SOURCE" && result.result;
        researchNote(card, "DEVELOPMENT evaluation: " + (verified ? (result.result.disposition || "disposition unavailable") + " · Accepted DEVELOPMENT improvement: " + (typeof result.result.accepted_development_improvement === "boolean" ? String(result.result.accepted_development_improvement) : "unavailable") : "Readback unavailable; no disposition inferred."), "development-result");
      }
      if (!(run.final_results || []).length) researchNote(card, "DEVELOPMENT evaluation: no independent result available.", "development-result");
      (run.experiments || []).forEach((experiment, index) => renderPractice(card, experiment, index));
      const controls = document.createElement("div"); controls.className = "controls";
      for (const action of ["pause", "resume", "stop", "reconcile", "export"]) {
        const button = document.createElement("button"); button.type = "button"; button.textContent = action;
        button.disabled = !connected || busy || (action === "resume" && !research.preflight.available) || (action !== "export" && ["COMPLETED", "STOPPED", "READBACK_UNAVAILABLE"].includes(run.state));
        button.addEventListener("click", () => researchAction(run.id, action)); controls.append(button);
      }
      const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Research, usage, candidate and independent result";
      details.open = expandedResearch.has(run.id);
      details.addEventListener("toggle", () => { if (details.isConnected) { if (details.open) expandedResearch.add(run.id); else expandedResearch.delete(run.id); } });
      const record = document.createElement("pre"); record.style.whiteSpace = "pre-wrap"; record.style.overflowWrap = "anywhere";
      record.textContent = JSON.stringify({runtime_revision: run.runtime_revision, agent_policy: run.agent_policy, research_guidance: run.research_guidance, effective_research_inputs: run.effective_research_inputs, hypothesis: run.current_hypothesis, hypotheses: run.hypotheses, decisions: run.decisions, outcomes: run.epoch_outcomes, usage: run.usage, experiments: run.experiments, operations: run.operations, freezes: run.candidate_freezes, development: run.final_results, capability_requests: run.capability_requests}, null, 2);
      details.append(summary, record); card.append(controls, details); container.append(card);
    }
  }
  function draft(id, field, fallback) {
    const key = id + ":" + field;
    return key in journeyDrafts ? journeyDrafts[key] : fallback;
  }
  function journeyField(parent, id, field, labelText, element, fallback) {
    const label = document.createElement("label"); label.textContent = labelText;
    element.id = "journey-" + field + "-" + id; label.htmlFor = element.id;
    element.value = draft(id, field, fallback);
    element.addEventListener("input", () => { journeyDrafts[id + ":" + field] = element.value; });
    parent.append(label, element);
    return element;
  }
  function renderJourney(card, run) {
    // A person's own journey, with no agent: practice, freeze, submit. Each
    // step is an operation from the same table the agent and MCP clients use.
    const box = document.createElement("div"); box.className = "journey"; box.id = "journey-" + run.id;
    const heading = document.createElement("h4"); heading.textContent = "Your research · no agent";
    box.append(heading);
    researchNote(box, "1 · Practice a recipe. 2 · Freeze one you practiced. 3 · Submit it for the independent DEVELOPMENT comparison with the control. Nothing reaches the chain.");
    const recipe = journeyField(box, run.id, "recipe", "Recipe to practice (JSON)", document.createElement("textarea"), STARTER_RECIPE);
    recipe.rows = 6; recipe.className = "research-guidance";
    const hypothesis = journeyField(box, run.id, "hypothesis", "What this trial tests", document.createElement("input"), "");
    const practiced = [];
    for (const experiment of run.experiments || []) {
      if (!experiment.recipe) continue;
      const text = JSON.stringify(experiment.recipe);
      if (!practiced.includes(text)) practiced.push(text);
    }
    const choose = document.createElement("select");
    for (const text of practiced) { const option = document.createElement("option"); option.value = text; option.textContent = text; choose.append(option); }
    const reason = document.createElement("input");
    const journey = run.journey || {};
    const frozen = journey.frozen_awaiting_submission === true;
    const exhausted = journey.final_exams_remaining === 0;
    // One operation at a time: the campaign is READY again only once the last
    // one has fully settled, and until then another would answer busy.
    const ready = run.state === "READY";
    if (!ready) researchNote(box, "Working: " + String(run.state).replaceAll("_", " ").toLowerCase() + ". The next step opens when the campaign is ready.");
    researchNote(box, "Final exams remaining: " + (journey.final_exams_remaining ?? "unavailable") + " · Submitted epochs: " + ((journey.submitted_epochs || []).join(", ") || "none") + (frozen ? " · A frozen candidate is waiting for submission." : ""));
    const buttons = document.createElement("div"); buttons.className = "controls";
    const practice = document.createElement("button"); practice.type = "button"; practice.id = "journey-practice-" + run.id; practice.textContent = "Run practice trial";
    practice.disabled = !connected || busy || !ready || exhausted;
    practice.addEventListener("click", () => {
      let strategy;
      try { strategy = JSON.parse(recipe.value); } catch (_) { message("The recipe is not valid JSON.", true); return; }
      operate("practice", {campaign: run.id, strategy, hypothesis: hypothesis.value || "practice"}, "Practice trial started. Its result appears below when training finishes.");
    });
    buttons.append(practice); box.append(buttons);
    journeyField(box, run.id, "candidate", "Practiced recipe to freeze", choose, practiced[0] || "");
    journeyField(box, run.id, "reason", "Why this candidate", reason, "");
    if (!practiced.length) researchNote(box, "No practiced recipe yet: a candidate must have a practice result before it can be frozen.");
    if (launchOptions) {
      // Each family's true availability now, by its registry verdict.
      const byVerdict = {};
      for (const family of launchOptions.families) (byVerdict[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      const labels = {supported: "Families you can freeze and submit now", not_yet_rebuildable: "Not yet rebuildable (research only)", needs_owner_decision: "Waiting on an owner decision", excluded: "Excluded"};
      for (const [verdict, label] of Object.entries(labels)) if (byVerdict[verdict]) researchNote(box, label + ": " + byVerdict[verdict].join(", "));
    }
    const second = document.createElement("div"); second.className = "controls";
    const freeze = document.createElement("button"); freeze.type = "button"; freeze.id = "journey-freeze-" + run.id; freeze.textContent = "Freeze candidate";
    freeze.disabled = !connected || busy || !ready || !practiced.length || frozen || exhausted;
    freeze.addEventListener("click", () => operate("freeze_candidate", {campaign: run.id, strategy: JSON.parse(choose.value), reason: reason.value || "practiced"}, "Candidate frozen for this epoch."));
    const submit = document.createElement("button"); submit.type = "button"; submit.id = "journey-submit-" + run.id; submit.textContent = "Submit frozen candidate";
    submit.disabled = !connected || busy || !ready || !frozen;
    submit.addEventListener("click", () => operate("submit", {campaign: run.id}, "Submitted for the DEVELOPMENT comparison. The independent result appears below."));
    second.append(freeze, submit); box.append(second);
    card.append(box);
  }
  const AGENT_LABELS = {autonomous: "Carbon's agent researches, freezes and submits", none: "I do it myself \u2014 no agent"};
  function words(value) { return String(value).replaceAll("_", " "); }
  // Why this composition cannot launch right now, or null. Availability is
  // the options operation's, read from the host - never assumed.
  function compositionProblem(value) {
    if (!launchOptions) return "launch options have not been read yet";
    const agent = launchOptions.agents.find(option => option.value === value.agent);
    if (!agent) return "choose who selects and submits";
    if (agent.availability !== "available") return "the " + value.agent + " agent is unavailable: " + words(agent.reason);
    const budget = value.budget || {};
    const vocabulary = launchOptions.budget || {keys: [], ceilings: []};
    for (const key of Object.keys(budget)) if (!vocabulary.keys.includes(key)) return "a budget cannot set " + key;
    if ("elapsed_seconds" in budget && !(Number.isInteger(budget.elapsed_seconds) && budget.elapsed_seconds >= 1)) return "the elapsed limit must be a whole number of seconds, at least 1";
    if ("final_reserve" in budget && typeof budget.final_reserve !== "boolean") return "the final reserve is on or off";
    for (const [name, cap] of Object.entries(budget.ceilings || {})) {
      if (!vocabulary.ceilings.includes(name)) return "no resource is called " + name;
      if (!(Number.isInteger(cap) && cap >= 0)) return "the " + words(name) + " ceiling must be a whole number, 0 or more";
    }
    return null;
  }
  function describeComposition(value) {
    const budget = value.budget || {};
    const parts = [];
    if ("elapsed_seconds" in budget) parts.push(budget.elapsed_seconds + " s elapsed");
    if (budget.final_reserve) parts.push("final phase held back");
    for (const [name, cap] of Object.entries(budget.ceilings || {})) parts.push(words(name) + " \u2264 " + cap);
    return "Launches with " + (value.agent ? AGENT_LABELS[value.agent] || value.agent : "no choice yet") + " \u00b7 budget: " + (parts.length ? parts.join(", ") : "none, no cap");
  }
  function buildCeilings() {
    const box = $("budget-ceilings");
    if (!launchOptions?.budget || box.dataset.built) return;
    for (const name of launchOptions.budget.ceilings) {
      const wrap = document.createElement("div");
      const label = document.createElement("label"); label.htmlFor = "ceiling-" + name; label.textContent = words(name);
      const input = document.createElement("input"); input.id = "ceiling-" + name; input.type = "number"; input.min = "0"; input.step = "1"; input.placeholder = "No cap"; input.dataset.ceiling = name;
      input.addEventListener("input", readAdvanced);
      wrap.append(label, input); box.append(wrap);
    }
    box.dataset.built = "1";
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
    if (composition.agent === null && launchOptions) {
      // First read: offer the agent where it can run, and never select one
      // that cannot.
      const agent = launchOptions.agents.find(option => option.value === "autonomous");
      composition = {...composition, agent: agent?.availability === "available" ? "autonomous" : "none"};
    }
    for (const radio of document.querySelectorAll("input[name=research-agent]")) {
      const option = launchOptions?.agents.find(item => item.value === radio.value);
      const unavailable = option && option.availability !== "available";
      radio.disabled = Boolean(unavailable);
      radio.checked = radio.value === composition.agent;
      radio.parentElement.lastChild.textContent = " " + AGENT_LABELS[radio.value] + (unavailable ? " \u00b7 unavailable: " + words(option.reason) : "");
    }
    $("path-quick").setAttribute("aria-pressed", String(launchPath === "quick"));
    $("path-advanced").setAttribute("aria-pressed", String(launchPath === "advanced"));
    $("launch-advanced").hidden = launchPath !== "advanced";
    const availability = $("launch-availability");
    if (launchOptions && !availability.dataset.built) {
      const families = {};
      for (const family of launchOptions.families) (families[family.verdict] ||= []).push(family.selector || family.id.split(".")[1]);
      for (const [verdict, names] of Object.entries(families)) researchNote(availability, "Model families \u00b7 " + words(verdict) + ": " + names.join(", "));
      for (const [lane, state] of Object.entries(launchOptions.research_lanes)) researchNote(availability, "Research lane " + lane + " \u00b7 " + state.availability + (state.reason ? ": " + words(state.reason) : ""));
      availability.dataset.built = "1";
    }
    const problem = compositionProblem(composition);
    $("composition-summary").textContent = describeComposition(composition) + (problem ? " \u00b7 cannot launch: " + problem : "");
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
  $("path-quick").addEventListener("click", () => { launchPath = "quick"; render(); });
  $("path-advanced").addEventListener("click", () => { launchPath = "advanced"; writeAdvanced(); render(); });
  for (const radio of document.querySelectorAll("input[name=research-agent]")) radio.addEventListener("change", () => { composition = {...composition, agent: radio.value}; render(); });
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
    message("Template \u201c" + name + "\u201d saved.");
    render();
  });
  $("template-load").addEventListener("click", async () => {
    const name = $("template-pick").value;
    const value = (readTemplates() || {})[name];
    // Availability is read again now: the moment of choosing is this one.
    try { launchOptions = await api("/api/v1/operations/options", {}); } catch (_) { /* keep the last read */ }
    const problem = templateProblem(value);
    if (problem) { message("Template \u201c" + name + "\u201d not loaded: " + problem + ".", true); render(); return; }
    composition = {agent: value.agent, budget: value.budget || {}};
    writeAdvanced();
    message("Template \u201c" + name + "\u201d loaded. " + describeComposition(composition) + ".");
    render();
  });
  $("template-delete").addEventListener("click", () => {
    const name = $("template-pick").value;
    const templates = readTemplates();
    if (!templates || !(name in templates)) return;
    delete templates[name];
    try { localStorage.setItem(templateKey, JSON.stringify(templates)); } catch (_) { message("Not deleted: this browser refused its storage.", true); return; }
    message("Template \u201c" + name + "\u201d deleted.");
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
      if (action === "export") {
        const fresh = await api("/api/v1/research/" + id);
        const url = URL.createObjectURL(new Blob([JSON.stringify(fresh, null, 2)], {type: "application/json"}));
        const link = document.createElement("a"); link.href = url; link.download = "carbon-research-" + id + ".json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else await api("/api/v1/research/" + id + "/" + action, {});
      message("Research request acknowledged. Check observed state and cleanup below.");
    } catch (error) { message("Research request unresolved: " + error.message, true); }
    finally { busy = false; await refresh(); render(); }
  }
  $("research-launch").addEventListener("click", async () => {
    if (!connected || busy || storageError || !research.preflight.available) return;
    if (!pendingResearch) {
      const problem = compositionProblem(composition);
      if (problem) { message("Not launched: " + problem + ".", true); return; }
      pendingResearch = {key: crypto.randomUUID(), body: {profile: research.preflight.profile, agent: composition.agent}};
      if (Object.keys(composition.budget).length) pendingResearch.body.budget = composition.budget;
      if (research.preflight.review_digest) pendingResearch.body.review_digest = research.preflight.review_digest;
      try { sessionStorage.setItem(researchKey, JSON.stringify(pendingResearch)); }
      catch (_) { storageError = true; render(); return; }
    }
    busy = true; render();
    try {
      await api("/api/v1/research", pendingResearch.body, pendingResearch.key);
      sessionStorage.removeItem(researchKey); pendingResearch = null;
      message("Research launch recorded. Runtime preflight and actual outcome appear below.");
    } catch (error) { message("Research launch not confirmed: " + error.message + ". Retry retains the same request.", true); }
    finally { busy = false; await refresh(); render(); }
  });
  // The navigation is built from the page's own sections: a section marked
  // data-nav is listed, and nothing else can be, so the two cannot drift.
  function buildNavigation() {
    const nav = $("tool-nav");
    const list = document.createElement("ul");
    const links = new Map();
    for (const section of document.querySelectorAll("[data-nav]")) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = "#" + section.id; link.textContent = section.dataset.nav;
      item.append(link); list.append(item); links.set(section, link);
    }
    nav.replaceChildren(list);
    if (!("IntersectionObserver" in window)) return;
    const seen = new Set();
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) entry.isIntersecting ? seen.add(entry.target) : seen.delete(entry.target);
      const current = [...links.keys()].find(section => seen.has(section));
      for (const [section, link] of links) {
        if (section === current) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      }
    }, {rootMargin: "0px 0px -60% 0px"});
    for (const section of links.keys()) observer.observe(section);
  }
  buildNavigation();
  setInterval(refresh, 1500);
})();
