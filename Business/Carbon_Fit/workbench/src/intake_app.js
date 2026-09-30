(function () {
  "use strict";
  const I = CarbonClientIntake;
  const $ = (id) => document.getElementById(id);
  const NOTICE_VERSION = "carbon.ask-guidance.notice.v2-2026-09-26";
  const quantityLabels = {
    preparation_time: "One-time preparation / training / reference generation",
    prediction_latency: "Recurring prediction latency",
    reference_query_time: "Reference-query time",
    workload_frequency: "Workload frequency",
    desired_accuracy: "Requested accuracy (unreviewed intent)",
  };
  const pilotLabels = {
    candidate_inputs: "candidate inputs",
    candidate_outputs: "candidate outputs",
    operating_envelope: "operating envelope",
    evaluation_questions: "evaluation questions and observables",
    requested_targets: "requested targets",
    missing_evidence: "missing evidence",
    implementation_work: "implementation work",
    bounded_first_pilot: "bounded first pilot",
    next_discussion: "next discussion",
  };
  const guidanceBoundaryHtml = $("guidance-boundary").innerHTML;
  const pilot = Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""]));
  const provenance = new Map();
  const acceptedSuggestions = [];
  const undoStack = [];
  let unresolvedAssumptions = [];
  let pendingProposals = [];
  let conversation = [];
  let guidanceEnabled = false;
  let guidanceAvailable = false;
  let consentedAt = null;
  let clearedLocally = false;
  // The consent record of a restored package whose accepted suggestions came
  // from guidance in an earlier session. Kept so a re-export does not claim
  // those suggestions arrived without guidance.
  let priorGuidance = null;
  let sessionId = "pilot-" + crypto.randomUUID();
  const textValue = (field) => document.querySelector(`[data-text="${field}"]`).value;
  // The system builder (GOAL-WORKBENCH-16). It edits the same draft, and its
  // evidence plan reads the brief's own words.
  const builder = CarbonSystemBuilder.create({
    engine: CarbonWorkbench,
    atlas: JSON.parse($("research-leads").textContent),
    root: $("system-panel"),
    words: () => ({ intended_decision: textValue("intended_decision"), requested_result: textValue("requested_result"), current_baseline: textValue("current_baseline") }),
    onChange: () => renderBrief(),
    status: (message) => { $("intake-status").textContent = message; },
  });

  $("quantity-fields").innerHTML = I.QUANTITY_FIELDS.map(
    (field) => `<div class="quantity-row" data-quantity-row="${field}"><label>${quantityLabels[field]}<select data-quantity-state="${field}"><option value="UNKNOWN">Unknown</option><option value="POINT">Point estimate</option><option value="RANGE">Supplied range</option></select></label><label data-quantity-unit-wrap="${field}" hidden>Unit<input data-quantity-unit="${field}" disabled></label><div class="quantity-values"><label class="point" data-quantity-point-wrap="${field}" hidden>Value<input type="number" step="any" data-quantity-value="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Minimum<input type="number" step="any" data-quantity-min="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Maximum<input type="number" step="any" data-quantity-max="${field}" disabled></label></div></div>`,
  ).join("");

  const answer = (value) => value.trim() ? { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" } : { state: "UNKNOWN", value: "", origin: "USER_ENTERED_LOCAL" };
  const numberOrNull = (input) => input.value === "" ? null : Number(input.value);

  function currentDraft() {
    const draft = I.newDraft($("draft-id").value, $("revision-id").value, builder.system());
    document.querySelectorAll("[data-text]").forEach((node) => { draft.answers[node.dataset.text] = answer(node.value); });
    I.QUANTITY_FIELDS.forEach((field) => {
      const state = document.querySelector(`[data-quantity-state="${field}"]`).value;
      draft.quantities[field] = {
        state,
        value: state === "POINT" ? numberOrNull(document.querySelector(`[data-quantity-value="${field}"]`)) : null,
        minimum: state === "RANGE" ? numberOrNull(document.querySelector(`[data-quantity-min="${field}"]`)) : null,
        maximum: state === "RANGE" ? numberOrNull(document.querySelector(`[data-quantity-max="${field}"]`)) : null,
        unit: state === "UNKNOWN" ? "" : document.querySelector(`[data-quantity-unit="${field}"]`).value,
        note: "",
        origin: "USER_ENTERED_LOCAL",
      };
    });
    const predecessorRevision = $("predecessor-revision").value.trim();
    const predecessorDigest = $("predecessor-digest").value.trim();
    if (predecessorRevision || predecessorDigest) draft.predecessor = { draft_id: draft.draft_id, revision_id: predecessorRevision, canonical_digest: predecessorDigest };
    draft.summary = I.summaryFor(draft);
    return I.validateDraft(draft);
  }

  // The proposed Challenge (GOAL-WORKBENCH-16 slice 2) follows the draft.
  const P = CarbonChallengeProposal;
  const FAMILIES = JSON.parse($("challenge-families").textContent);
  let proposalFamily = null;
  let lastProposal = null;
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const STATUS_TEXT = {
    INSIDE_TESTED_RANGE: "inside the tested range",
    OUTSIDE_TESTED_RANGE: "outside the tested range",
    PROPOSED_FROM_TESTED_DESIGN: "proposed from the tested design",
    SUPPLIED_RANGE_MISSING: "range needed",
    UNITS_TO_CONFIRM: "units to confirm",
    SUPPLIED_NO_TESTED_RANGE: "supplied; no tested range yet",
    NEEDED_NO_TESTED_RANGE: "needed; no tested range yet",
  };
  const table = (columns, rows) => `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th scope="col">${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  function renderProposal(draft) {
    let proposal;
    try { proposal = P.propose(draft, FAMILIES, proposalFamily); } catch (error) { proposalFamily = null; proposal = P.propose(draft, FAMILIES); }
    lastProposal = proposal;
    // The client can always choose; the first option follows the best match.
    const best = proposal.matches[0];
    $("proposal-family").innerHTML = `<option value=""${proposalFamily ? "" : " selected"}>Best match${best ? ": " + esc(best.title) : " (none yet)"}</option>` +
      FAMILIES.families.map((f) => {
        const m = proposal.matches.find((x) => x.family_id === f.id);
        return `<option value="${esc(f.id)}"${proposalFamily === f.id ? " selected" : ""}>${esc(f.title)}${m ? "" : " (not matched)"}${f.evidence ? "" : " · no evidence yet"}</option>`;
      }).join("");
    const view = $("proposal-view");
    if (proposal.kind === P.KIND.NONE) {
      view.innerHTML = `<div class="boundary"><strong>No launch-portfolio family matches this brief yet.</strong> Describe the system and what you need to predict, in the form or in Your system, and the proposal will follow. A problem outside Carbon's current families is still welcome: Carbon would scope it from the start, and a new family needs its own reference, measurements and exam-design study.</div><p class="field-note">Families Carbon has records for: ${esc(FAMILIES.families.map((f) => f.title).join(", "))}.</p>`;
      return;
    }
    const f = proposal.family;
    const matchedOn = proposal.matched ? [...proposal.matched.keywords, ...proposal.matched.physics.map((x) => x + " physics")].join(", ") : "";
    let html = `<article class="plan-route"><p class="eyebrow">${proposal.kind === P.KIND.EVIDENCE ? "Evidence-backed family" : "Scoped family, no evidence yet"}</p><h3>${esc(f.title)}</h3><p>${esc(f.engineering_decision)}</p><p class="field-note">${matchedOn ? "Matched on your words: " + esc(matchedOn) + ". " : "Chosen by you. "}Status ${esc(f.status)}; training budget study ${esc(f.training_budget_study)}. A suggestion for Carbon review, not an assessment of fit.</p></article>`;
    html += `<div class="boundary"><strong>Where the evidence applies.</strong> ${esc(f.reference_applicability)}</div>`;
    html += `<h3>Conditions</h3><p class="field-note">Each condition the family varies, against your inputs. Where you gave none, Carbon proposes the range it tested; confirm or change it.</p>`;
    html += `<ul class="condition-list">${proposal.conditions.map((c) => `<li class="condition ${c.status.toLowerCase()}"><div><strong>${esc(c.variable)}</strong> <span class="field-note">(${esc(c.unit)})</span> <span class="chip">${esc(STATUS_TEXT[c.status] || c.status)}</span></div><p>${esc(c.description)}</p><p>${esc(c.note)}</p>${c.client_inputs.length ? `<p class="field-note">Your input: ${esc(c.client_inputs.join(", "))}</p>` : ""}</li>`).join("")}</ul>`;
    if (proposal.extra_client_inputs.length) html += `<p class="field-note">Inputs you gave that this family's design does not vary: ${esc(proposal.extra_client_inputs.join(", "))}. They would need a new design study.</p>`;
    html += `<h3>What the model would predict</h3>${table(["Output", "Unit", "What it is", "Your matching output"], proposal.outputs.map((o) => [o.output, o.unit, o.description, o.client_outputs.join(", ") || "—"]))}`;
    if (proposal.kind === P.KIND.EVIDENCE) {
      const outside = proposal.conditions.some((c) => c.status === "OUTSIDE_TESTED_RANGE");
      html += `<h3>Proposed exam settings, and why</h3><p class="field-note">From ${esc(proposal.evidence.title)}: ${esc(proposal.evidence.summary)}</p>`;
      if (outside) html += `<div class="boundary"><strong>Part of your brief is outside the tested range.</strong> These settings were measured on Carbon's tested design; they are a starting point, and your range would need its own study before they could be relied on.</div>`;
      html += proposal.settings.map((st) => `<details class="method setting"><summary><span>${esc(st.label)}</span> <strong>${esc(st.value)}</strong></summary><p>${esc(st.why)}</p>${table(st.table.columns, st.table.rows)}${st.supporting_table ? table(st.supporting_table.columns, st.supporting_table.rows) : ""}<p class="field-note">Source: ${esc(proposal.evidence.source.path)} (section: ${esc(st.section)})${st.limit ? ` Limit <code>${esc(st.limit.name)}</code>: proposed ${esc(st.limit.proposed)} ${esc(st.limit.unit)}; approved: ${st.limit.approved === null ? "not yet" : esc(st.limit.approved)}.` : "."}</p></details>`).join("");
      html += `<h3>Limits of this evidence</h3><ul>${proposal.evidence.limits_of_evidence.map((l) => `<li>${esc(l.replace(/^\d+\.\s*/, "").replaceAll("**", ""))}…</li>`).join("")}</ul>`;
    } else {
      const unknown = proposal.costs.filter((c) => c.basis === "unknown").map((c) => c.item);
      html += `<h3>No exam-design evidence yet</h3><p>Carbon has scoped this family but has not run its exam-design campaign, so no exam setting is proposed. The first step on record:</p><p class="clarification">${esc(f.next_experiment)}</p>${unknown.length ? `<p class="field-note">Cost items not yet measured: ${esc(unknown.join(", "))}. No figure is shown until it is measured.</p>` : ""}`;
    }
    html += `<details class="method"><summary>Open items Carbon still has to resolve (${f.unresolved.length})</summary><ul>${f.unresolved.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></details>`;
    view.innerHTML = html;
  }

  function guidanceContext() {
    return I.guidanceContextFrom(currentDraft(), pilot, unresolvedAssumptions);
  }

  function renderBrief() {
    try {
      const draft = currentDraft();
      $("summary-text").textContent = draft.summary.text;
      $("next-clarification").textContent = pilot.next_discussion || draft.summary.next_clarification;
      $("pilot-text").textContent = pilot.bounded_first_pilot || "Not yet proposed.";
      const list = $("assumption-list");
      list.replaceChildren();
      const missingPilotFields = I.PILOT_FIELDS.filter((field) => !pilot[field].trim()).map((field) => `Unresolved field: ${pilotLabels[field] || field.replaceAll("_", " ")}.`);
      const visibleUnknowns = [...new Set([...unresolvedAssumptions, ...missingPilotFields])];
      for (const text of visibleUnknowns.length ? visibleUnknowns : ["No unresolved pilot fields are currently recorded."]) {
        const item = document.createElement("li"); item.textContent = text; list.append(item);
      }
      $("brief-mode").textContent = acceptedSuggestions.length ? `${acceptedSuggestions.length} accepted suggestion${acceptedSuggestions.length === 1 ? "" : "s"}` : "client draft";
      $("context-preview").textContent = JSON.stringify(guidanceContext(), null, 2);
      renderProposal(draft);
      $("intake-status").textContent = "Ready for local review. Nothing has been submitted.";
    } catch (error) { $("intake-status").textContent = error.message; }
  }

  const MODES = ["guided", "form", "system", "proposal"];
  function setMode(mode, focusPanel = true) {
    for (const name of MODES) {
      const selected = name === mode;
      $(name + "-panel").hidden = !selected;
      $("show-" + name).setAttribute("aria-selected", String(selected));
      $("show-" + name).tabIndex = selected ? 0 : -1;
    }
    if (!focusPanel) return;
    if (mode === "form") document.querySelector("[data-text='intended_decision']").focus();
    if (mode === "system") $("system-panel").querySelector("[data-step]").focus();
    if (mode === "proposal") $("proposal-panel").querySelector("h2").focus();
  }

  function addMessage(role, text) {
    conversation.push({ turn_id: `turn-${String(conversation.length + 1).padStart(3, "0")}`, role, text });
    const article = document.createElement("article"); article.className = `message ${role === "CLIENT" ? "client" : "assistant"}`;
    const strong = document.createElement("strong"); strong.textContent = role === "CLIENT" ? "You" : "Carbon";
    const p = document.createElement("p"); p.textContent = text; article.append(strong, p); $("conversation").append(article); article.scrollIntoView({ block: "nearest" });
  }

  function valueFor(field) {
    if (field.startsWith("pilot.")) return pilot[field.slice(6)];
    return document.querySelector(`[data-text="${field}"]`)?.value ?? "";
  }
  function setValue(field, value, dispatch = true) {
    if (field.startsWith("pilot.")) {
      const name = field.slice(6); pilot[name] = value;
      const node = document.querySelector(`[data-pilot="${name}"]`); if (node) node.value = value;
    } else {
      const node = document.querySelector(`[data-text="${field}"]`); if (!node) throw Error("Unsupported suggestion field"); node.value = value;
    }
    if (dispatch) renderBrief();
  }

  function renderProposals() {
    const root = $("proposal-list"); root.replaceChildren();
    for (const proposal of pendingProposals) {
      const card = document.createElement("article"); card.className = "proposal";
      const title = document.createElement("strong"); title.textContent = `Proposed change · ${proposal.field.replaceAll("_", " ")}`;
      const value = document.createElement("p"); value.textContent = proposal.value;
      const why = document.createElement("p"); why.className = "field-note"; why.textContent = proposal.rationale;
      const actions = document.createElement("div"); actions.className = "actions";
      const accept = document.createElement("button"); accept.type = "button"; accept.textContent = "Accept change";
      const reject = document.createElement("button"); reject.type = "button"; reject.className = "quiet"; reject.textContent = "Reject";
      accept.onclick = () => {
        const previous = valueFor(proposal.field);
        undoStack.push({ proposal, previous }); setValue(proposal.field, proposal.value);
        acceptedSuggestions.push({ suggestion_id: proposal.suggestion_id, field: proposal.field, proposed_value: proposal.value, rationale: proposal.rationale, accepted_at: new Date().toISOString() });
        provenance.set(proposal.field, { origin: "AI_SUGGESTED_CLIENT_ACCEPTED", suggestion_id: proposal.suggestion_id });
        pendingProposals = pendingProposals.filter((item) => item.suggestion_id !== proposal.suggestion_id); renderProposals(); $("undo-suggestion").disabled = false;
      };
      reject.onclick = () => { pendingProposals = pendingProposals.filter((item) => item.suggestion_id !== proposal.suggestion_id); renderProposals(); };
      actions.append(accept, reject); card.append(title, value, why, actions); root.append(card);
    }
  }

  function turnPairs() {
    const pairs = [];
    for (let index = 0; index < conversation.length - 1; index += 1) if (conversation[index].role === "CLIENT" && conversation[index + 1].role === "ASSISTANT") pairs.push({ question: conversation[index].text, answer: conversation[index + 1].text });
    return pairs.slice(-10);
  }

  async function enableGuidance() {
    guidanceEnabled = true; consentedAt = new Date().toISOString();
    $("enable-guidance").disabled = true; $("guidance-status").textContent = "Checking whether guided AI is available…";
    try {
      const base = document.body.dataset.apiUrl;
      const response = await fetch(base + "/health", { credentials: "same-origin", cache: "no-store" });
      const status = await response.json();
      guidanceAvailable = response.ok && status.active;
    } catch { guidanceAvailable = false; }
    $("guidance-input").disabled = !guidanceAvailable; $("send-guidance").disabled = !guidanceAvailable;
    $("guidance-boundary").innerHTML = guidanceAvailable ? "<strong>AI guidance enabled.</strong> Proposed changes require your acceptance. The form remains available." : "<strong>AI guidance is unavailable in this preview.</strong> Your draft is preserved; continue with the form.";
    $("guidance-status").textContent = guidanceAvailable ? "AI guidance is ready. No draft field changes without your acceptance." : "No provider request was completed. Continue through the form and export the same brief.";
    if (!guidanceAvailable) setMode("form");
    renderBrief();
  }

  async function sendGuidance(event) {
    event.preventDefault();
    const question = $("guidance-input").value.trim(); if (!question || !guidanceAvailable) return;
    addMessage("CLIENT", question); $("guidance-input").value = ""; $("guidance-input").disabled = true; $("send-guidance").disabled = true; $("guidance-status").textContent = "Preparing one bounded next step…";
    try {
      const response = await fetch(document.body.dataset.apiUrl, { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ mode: "PILOT_DESIGN", session_id: sessionId, question, turns: turnPairs(), draft_context: guidanceContext() }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 429 || ["usage_limit", "edge_rate_limit"].includes(body.error?.code)) {
          throw Error("AI guidance is unavailable because a shared usage limit has been reached. Your draft is preserved; continue with form-only drafting.");
        }
        throw Error(body.error?.message || "AI guidance is temporarily unavailable. Your draft is preserved; continue with form-only drafting.");
      }
      addMessage("ASSISTANT", [body.message, body.next_question].filter(Boolean).join("\n\n"));
      pendingProposals = body.proposals || []; unresolvedAssumptions = [...new Set([...unresolvedAssumptions, ...(body.unresolved_assumptions || [])])]; renderProposals(); renderBrief();
      $("guidance-status").textContent = "Review each proposed change. Rejecting a suggestion leaves the brief unchanged.";
    } catch (error) { $("guidance-status").textContent = `${error.message} Your draft is preserved; continue through the form.`; }
    finally { $("guidance-input").disabled = false; $("send-guidance").disabled = false; $("guidance-input").focus(); }
  }

  function reviewedPackage() {
    const draft = currentDraft();
    const allFields = [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((field) => "pilot." + field)];
    const fieldProvenance = allFields.map((field) => {
      const recorded = provenance.get(field);
      const hasValue = field.startsWith("pilot.") ? Boolean(pilot[field.slice(6)]) : field in draft.answers ? draft.answers[field].state === "VALUE" : draft.quantities[field].state !== "UNKNOWN";
      return { field, origin: recorded?.origin || (hasValue ? "CLIENT_TYPED" : "UNKNOWN"), suggestion_id: recorded?.suggestion_id || null };
    });
    const includeConversation = $("include-conversation").checked;
    return I.validateReviewedPackage({
      schema_version: I.REVIEW_VERSION_V2, brief: draft,
      pilot: { label: "Draft pilot for Carbon review", ...pilot },
      field_provenance: fieldProvenance, accepted_suggestions: acceptedSuggestions,
      unresolved_assumptions: unresolvedAssumptions,
      ai_guidance: !guidanceEnabled && priorGuidance && acceptedSuggestions.length
        ? { ...priorGuidance, cleared_locally: priorGuidance.cleared_locally || clearedLocally }
        : { enabled: guidanceEnabled, provider: guidanceEnabled ? "CHUTES_API" : null, guidance_version: I.GUIDANCE_VERSION, notice_version: guidanceEnabled ? NOTICE_VERSION : null, consented_at: guidanceEnabled ? consentedAt : null, cleared_locally: clearedLocally },
      sharing: { include_conversation: includeConversation, conversation: includeConversation ? conversation : [] },
      contact: { name: $("contact-name").value, email: $("contact-email").value, organization: $("contact-organization").value },
      local_scope: I.REVIEW_SCOPE,
    });
  }

  document.querySelectorAll("[data-text]").forEach((node) => node.addEventListener("input", () => { provenance.set(node.dataset.text, { origin: "CLIENT_TYPED", suggestion_id: null }); builder.refresh(); renderBrief(); }));
  document.querySelectorAll("[data-pilot]").forEach((node) => node.addEventListener("input", () => { pilot[node.dataset.pilot] = node.value; provenance.set("pilot." + node.dataset.pilot, { origin: "CLIENT_TYPED", suggestion_id: null }); renderBrief(); }));
  document.querySelectorAll("#form-panel input,#form-panel select,.brief-panel input").forEach((node) => node.addEventListener("input", renderBrief));
  document.querySelectorAll("[data-quantity-state]").forEach((node) => node.addEventListener("change", () => {
    const field = node.dataset.quantityState, point = node.value === "POINT", range = node.value === "RANGE";
    document.querySelector(`[data-quantity-unit-wrap="${field}"]`).hidden = node.value === "UNKNOWN";
    document.querySelector(`[data-quantity-point-wrap="${field}"]`).hidden = !point;
    document.querySelectorAll(`[data-quantity-range-wrap="${field}"]`).forEach((element) => { element.hidden = !range; });
    document.querySelector(`[data-quantity-unit="${field}"]`).disabled = node.value === "UNKNOWN";
    document.querySelector(`[data-quantity-value="${field}"]`).disabled = !point;
    document.querySelector(`[data-quantity-min="${field}"]`).disabled = !range;
    document.querySelector(`[data-quantity-max="${field}"]`).disabled = !range;
    provenance.set(field, { origin: node.value === "UNKNOWN" ? "UNKNOWN" : "CLIENT_TYPED", suggestion_id: null }); renderBrief();
  }));
  for (const name of MODES) $("show-" + name).onclick = () => setMode(name);
  for (const name of MODES) $("show-" + name).addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = MODES.indexOf(name);
    const next = event.key === "Home" ? 0 : event.key === "End" ? MODES.length - 1 : (index + (event.key === "ArrowLeft" ? -1 : 1) + MODES.length) % MODES.length;
    setMode(MODES[next], false); $("show-" + MODES[next]).focus();
  });
  $("system-panel").querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
    if (!builder.isBlank() && !confirm("Replace the system you have built with this example? Download first if you want to keep it.")) return;
    builder.example(button.dataset.example);
    $("intake-status").textContent = "Example loaded into the system builder. Your brief's words are unchanged; edit the starting assumptions to fit your problem.";
  }));
  $("proposal-family").onchange = () => { proposalFamily = $("proposal-family").value || null; renderBrief(); };
  $("export-proposal").onclick = () => {
    if (!lastProposal) return;
    download(P.markdown(lastProposal), `${lastProposal.draft.draft_id}_${lastProposal.draft.revision_id}.proposed-challenge.md`, "text/markdown");
    $("intake-status").textContent = "Proposal downloaded locally. Nothing was transmitted to Carbon.";
  };
  $("system-clear").onclick = () => {
    if (!builder.isBlank() && !confirm("Clear the system builder? Your brief's words are unchanged.")) return;
    builder.reset();
  };
  $("show-consent").onclick = () => { $("consent-panel").hidden = false; renderBrief(); };
  $("consent-check").onchange = () => { $("enable-guidance").disabled = !$("consent-check").checked; };
  $("enable-guidance").onclick = enableGuidance; $("guidance-form").onsubmit = sendGuidance;
  $("clear-conversation").onclick = () => { conversation = []; pendingProposals = []; clearedLocally = true; $("conversation").innerHTML = '<article class="message assistant"><strong>Carbon</strong><p>Conversation cleared on this device. This does not delete provider records. Your accepted brief changes remain.</p></article>'; renderProposals(); renderBrief(); };
  $("undo-suggestion").onclick = () => { const item = undoStack.pop(); if (!item) return; setValue(item.proposal.field, item.previous); const index = acceptedSuggestions.findIndex((entry) => entry.suggestion_id === item.proposal.suggestion_id); if (index >= 0) acceptedSuggestions.splice(index, 1); provenance.set(item.proposal.field, { origin: item.previous ? "CLIENT_TYPED" : "UNKNOWN", suggestion_id: null }); $("undo-suggestion").disabled = !undoStack.length; renderBrief(); };
  $("reset-draft").onclick = () => {
    if (!confirm("Reset this local draft and conversation? Download first if you want to keep a copy.")) return;
    document.querySelectorAll("[data-text],[data-pilot]").forEach((node) => { node.value = ""; });
    for (const field of I.PILOT_FIELDS) pilot[field] = "";
    for (const field of I.QUANTITY_FIELDS) {
      const select = document.querySelector(`[data-quantity-state="${field}"]`); select.value = "UNKNOWN"; select.dispatchEvent(new Event("change"));
      for (const selector of [`[data-quantity-unit="${field}"]`, `[data-quantity-value="${field}"]`, `[data-quantity-min="${field}"]`, `[data-quantity-max="${field}"]`]) document.querySelector(selector).value = "";
    }
    $("draft-id").value = "local-inquiry-001"; $("revision-id").value = "rev-001"; $("predecessor-revision").value = ""; $("predecessor-digest").value = "";
    $("contact-name").value = ""; $("contact-email").value = ""; $("contact-organization").value = ""; $("include-conversation").checked = false;
    acceptedSuggestions.length = 0; undoStack.length = 0; provenance.clear(); unresolvedAssumptions = []; pendingProposals = []; conversation = []; priorGuidance = null; proposalFamily = null;
    guidanceEnabled = false; guidanceAvailable = false; consentedAt = null; clearedLocally = true; sessionId = "pilot-" + crypto.randomUUID();
    $("consent-check").checked = false; $("enable-guidance").disabled = true; $("consent-panel").hidden = true; $("guidance-input").value = ""; $("guidance-input").disabled = true; $("send-guidance").disabled = true; $("undo-suggestion").disabled = true;
    $("guidance-boundary").innerHTML = guidanceBoundaryHtml;
    builder.reset();
    $("conversation").innerHTML = '<article class="message assistant"><strong>Carbon</strong><p>What engineering decision depends on the prediction or comparison you want to make?</p></article>';
    $("guidance-status").textContent = "Draft reset locally. This does not delete provider records. Continue with the form or review AI data use again.";
    renderProposals(); renderBrief(); setMode("guided"); $("show-guided").focus();
  };
  // "Continue a saved draft". Opens, on this device only, a reviewed package
  // or brief this page downloaded (either version), or a draft saved from the
  // earlier /workbench/ page. A package is restored as it was recorded,
  // including its provenance and accepted suggestions; nothing is inferred.
  function hasWork() {
    const typed = [...document.querySelectorAll("[data-text],[data-pilot]")].some((node) => node.value.trim());
    return typed || !builder.isBlank() || acceptedSuggestions.length > 0;
  }
  function setQuantity(field, value) {
    const select = document.querySelector(`[data-quantity-state="${field}"]`);
    select.value = value.state; select.dispatchEvent(new Event("change"));
    document.querySelector(`[data-quantity-unit="${field}"]`).value = value.unit;
    document.querySelector(`[data-quantity-value="${field}"]`).value = value.value ?? "";
    document.querySelector(`[data-quantity-min="${field}"]`).value = value.minimum ?? "";
    document.querySelector(`[data-quantity-max="${field}"]`).value = value.maximum ?? "";
  }
  function restoreBrief(draft) {
    $("draft-id").value = draft.draft_id; $("revision-id").value = draft.revision_id;
    $("predecessor-revision").value = draft.predecessor?.revision_id || "";
    $("predecessor-digest").value = draft.predecessor?.canonical_digest || "";
    for (const field of I.TEXT_FIELDS) document.querySelector(`[data-text="${field}"]`).value = draft.answers[field].value;
    for (const field of I.QUANTITY_FIELDS) setQuantity(field, draft.quantities[field]);
    if (draft.system) builder.load(draft.system); else builder.reset();
  }
  function restorePackage(reviewed) {
    restoreBrief(reviewed.brief);
    for (const field of I.PILOT_FIELDS) setValue("pilot." + field, reviewed.pilot[field], false);
    provenance.clear();
    for (const item of reviewed.field_provenance) if (item.origin !== "UNKNOWN") provenance.set(item.field, { origin: item.origin, suggestion_id: item.suggestion_id });
    acceptedSuggestions.length = 0; acceptedSuggestions.push(...reviewed.accepted_suggestions);
    unresolvedAssumptions = [...reviewed.unresolved_assumptions];
    priorGuidance = reviewed.ai_guidance.enabled ? { ...reviewed.ai_guidance } : null;
    clearedLocally = reviewed.ai_guidance.cleared_locally;
    $("contact-name").value = reviewed.contact.name; $("contact-email").value = reviewed.contact.email; $("contact-organization").value = reviewed.contact.organization;
  }
  function restoreWorkbench(text) {
    const saved = CarbonSystemBuilder.readWorkbenchDraft(CarbonWorkbench, text);
    const words = builder.load(saved.problem);
    for (const [field, value] of Object.entries(words)) {
      if (!value.trim()) continue;
      document.querySelector(`[data-text="${field}"]`).value = value.slice(0, 8000);
      provenance.set(field, { origin: "CLIENT_TYPED", suggestion_id: null });
    }
    if (saved.email) $("contact-email").value = saved.email;
  }
  $("resume-draft").onclick = () => $("resume-file").click();
  $("resume-file").onchange = async (event) => {
    const file = event.target.files[0]; event.target.value = "";
    if (!file) return;
    try {
      if (file.size > 2000000) throw Error("The file is larger than a saved draft can be.");
      const text = await file.text();
      let parsed;
      try { parsed = JSON.parse(text); } catch { throw Error("Choose a draft file saved from this page or from Carbon's Workbench."); }
      if (hasWork() && !confirm("Replace the current draft with the saved one? Download the current draft first if you want to keep it.")) return;
      const own = parsed && (I.REVIEW_VERSIONS.includes(parsed.schema_version) || I.DRAFT_VERSIONS.includes(parsed.schema_version));
      if (own && I.REVIEW_VERSIONS.includes(parsed.schema_version)) restorePackage(I.validateReviewedPackage(parsed));
      else {
        // A brief or a Workbench draft carries no pilot outline, contact or
        // provenance, so those start empty rather than keeping the old draft's.
        for (const field of I.PILOT_FIELDS) setValue("pilot." + field, "", false);
        provenance.clear(); acceptedSuggestions.length = 0; unresolvedAssumptions = []; priorGuidance = null; clearedLocally = false;
        if (own) restoreBrief(I.validateDraft(parsed));
        else { restoreBrief(I.newDraft()); restoreWorkbench(text); }
      }
      // A conversation belongs to the draft it was held about, so it never
      // travels into a different one. A package's conversation is not replayed.
      conversation = [];
      $("conversation").innerHTML = '<article class="message assistant"><strong>Carbon</strong><p>Saved draft opened. What would you like to refine?</p></article>';
      $("include-conversation").checked = false;
      undoStack.length = 0; pendingProposals = []; renderProposals(); $("undo-suggestion").disabled = true;
      builder.refresh(); renderBrief();
      $("intake-status").textContent = own
        ? "Saved draft restored on this device. Nothing was sent. Change the revision ID before sending an updated version."
        : "Workbench draft opened. Its words are in the form and its structure is in Your system. Review both; nothing was sent.";
    } catch (error) { $("intake-status").textContent = "Could not open that file: " + error.message; }
  };
  function download(text, name, type) { const blob = new Blob([text], { type }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = name; link.click(); URL.revokeObjectURL(link.href); }
  const packageText = (reviewed) => JSON.stringify(reviewed, null, 2) + "\n";
  const packageName = (reviewed) => `${reviewed.brief.draft_id}_${reviewed.brief.revision_id}`;
  $("export-intake").onclick = () => { try { const reviewed = reviewedPackage(); download(packageText(reviewed), packageName(reviewed) + ".carbon-intake.json", "application/json"); $("intake-status").textContent = "Reviewed brief downloaded locally. Nothing was transmitted to Carbon."; } catch (error) { $("intake-status").textContent = "Export blocked: " + error.message; } };
  // E6: the encrypted download seals the same bytes the reviewed download saves.
  // The button stays disabled unless the key embedded in this page verifies, and
  // the fingerprint shown is recomputed from that key.
  let intakeRecipient = null;
  $("export-sealed").onclick = async () => {
    if (!intakeRecipient) return;
    try {
      const reviewed = reviewedPackage();
      const sealed = await CarbonIntakeSeal.seal(packageText(reviewed), intakeRecipient);
      download(JSON.stringify(sealed, null, 2) + "\n", packageName(reviewed) + ".carbon-sealed", "application/octet-stream");
      $("intake-status").textContent = "Encrypted draft downloaded locally. Nothing was transmitted to Carbon.";
    } catch (error) { $("intake-status").textContent = "Encrypted export blocked: " + error.message; }
  };
  Promise.resolve().then(() => CarbonIntakeSeal.recipient(JSON.parse($("intake-public-key").textContent))).then(
    (built) => { intakeRecipient = built; $("intake-fingerprint").textContent = built.fingerprint; $("export-sealed").disabled = false; },
    () => { $("intake-fingerprint").textContent = "unavailable. The intake key in this page did not verify, so encrypted download is off."; },
  );
  renderBrief();
})();
