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
  async function api(path, body, key) {
    const headers = {Authorization: "Bearer " + token};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (key) headers["Idempotency-Key"] = key;
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(5000), cache: "no-store", redirect: "error"
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
    $("research-preflight").textContent = connected ? research.preflight.status.replaceAll("_", " ") + (research.preflight.reason ? " · " + research.preflight.reason : "") + (research.preflight.available && research.preflight.ceilings ? " · Approved envelope: " + JSON.stringify(research.preflight.ceilings) + " · Expires: " + new Date(research.preflight.expires_unix * 1000).toLocaleString() : "") : "Reconnect to reconcile research state. Controls are disabled.";
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
      researchNote(reviewPanel, "Grant: " + review.grant.status + (review.grant.expired ? " · EXPIRED" : " · Before configured expiry") + " · " + new Date(review.grant.expires_unix * 1000).toLocaleString());
      researchNote(reviewPanel, review.resources.basis);
      const details = document.createElement("details");
      const label = document.createElement("summary"); label.textContent = "Exact configured identities, capabilities and resource limits";
      const data = document.createElement("pre"); data.textContent = JSON.stringify(review, null, 2);
      data.style.whiteSpace = "pre-wrap"; data.style.overflowWrap = "anywhere";
      details.append(label, data); reviewPanel.append(details);
    }
    $("research-launch").disabled = !connected || busy || storageError || !research.preflight.available;
    $("research-launch").textContent = pendingResearch ? "Retry same research launch" : "Launch approved research";
    const container = $("research-runs"); container.replaceChildren();
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
      for (const outcome of run.epoch_outcomes || []) researchNote(card, "Agent epoch " + outcome.epoch + ": " + outcome.status + " · " + (outcome.reason || "No reason reported") + " · Agent-reported decision, not independent science.");
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
      pendingResearch = {key: crypto.randomUUID(), body: {profile: research.preflight.profile}};
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
  setInterval(refresh, 1500);
})();
