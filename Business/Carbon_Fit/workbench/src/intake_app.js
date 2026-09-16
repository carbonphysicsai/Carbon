(function () {
  "use strict";
  const I = CarbonClientIntake;
  const $ = (id) => document.getElementById(id);
  const NOTICE_VERSION = "carbon.ask-guidance.notice.v1-2026-09-16";
  const quantityLabels = {
    preparation_time: "One-time preparation / training / reference generation",
    prediction_latency: "Recurring prediction latency",
    reference_query_time: "Reference-query time",
    workload_frequency: "Workload frequency",
    desired_accuracy: "Requested accuracy (unreviewed intent)",
  };
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
  const sessionId = "pilot-" + crypto.randomUUID();

  $("quantity-fields").innerHTML = I.QUANTITY_FIELDS.map(
    (field) => `<div class="quantity-row" data-quantity-row="${field}"><label>${quantityLabels[field]}<select data-quantity-state="${field}"><option value="UNKNOWN">Unknown</option><option value="POINT">Point estimate</option><option value="RANGE">Supplied range</option></select></label><label data-quantity-unit-wrap="${field}" hidden>Unit<input data-quantity-unit="${field}" disabled></label><div class="quantity-values"><label class="point" data-quantity-point-wrap="${field}" hidden>Value<input type="number" step="any" data-quantity-value="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Minimum<input type="number" step="any" data-quantity-min="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Maximum<input type="number" step="any" data-quantity-max="${field}" disabled></label></div></div>`,
  ).join("");

  const answer = (value) => value.trim() ? { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" } : { state: "UNKNOWN", value: "", origin: "USER_ENTERED_LOCAL" };
  const numberOrNull = (input) => input.value === "" ? null : Number(input.value);

  function currentDraft() {
    const draft = I.newDraft($("draft-id").value, $("revision-id").value);
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

  function guidanceContext() {
    const draft = currentDraft();
    return {
      version: "carbon.client-intake.guidance-context.v1",
      answers: Object.fromEntries(I.TEXT_FIELDS.map((field) => [field, draft.answers[field].state === "VALUE" ? draft.answers[field].value : null])),
      pilot: Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, pilot[field] || null])),
      unresolved_assumptions: [...unresolvedAssumptions],
    };
  }

  function renderBrief() {
    try {
      const draft = currentDraft();
      $("summary-text").textContent = draft.summary.text;
      $("next-clarification").textContent = pilot.next_discussion || draft.summary.next_clarification;
      $("pilot-text").textContent = pilot.bounded_first_pilot || "Not yet proposed.";
      const list = $("assumption-list");
      list.replaceChildren();
      for (const text of unresolvedAssumptions.length ? unresolvedAssumptions : ["Complete or skip fields; unknowns remain visible."]) {
        const item = document.createElement("li"); item.textContent = text; list.append(item);
      }
      $("brief-mode").textContent = acceptedSuggestions.length ? `${acceptedSuggestions.length} accepted suggestion${acceptedSuggestions.length === 1 ? "" : "s"}` : "client draft";
      $("context-preview").textContent = JSON.stringify(guidanceContext(), null, 2);
      $("intake-status").textContent = "Ready for local review. Nothing has been submitted.";
    } catch (error) { $("intake-status").textContent = error.message; }
  }

  function setMode(mode) {
    const guided = mode === "guided";
    $("guided-panel").hidden = !guided; $("form-panel").hidden = guided;
    $("show-guided").setAttribute("aria-selected", String(guided));
    $("show-form").setAttribute("aria-selected", String(!guided));
    if (!guided) document.querySelector("[data-text='intended_decision']").focus();
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
      const body = await response.json().catch(() => ({})); if (!response.ok) throw Error(body.error?.message || "Guidance is temporarily unavailable.");
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
      schema_version: I.REVIEW_VERSION, brief: draft,
      pilot: { label: "Draft pilot for Carbon review", ...pilot },
      field_provenance: fieldProvenance, accepted_suggestions: acceptedSuggestions,
      unresolved_assumptions: unresolvedAssumptions,
      ai_guidance: { enabled: guidanceEnabled, provider: guidanceEnabled ? "OPENAI_API" : null, guidance_version: I.GUIDANCE_VERSION, notice_version: guidanceEnabled ? NOTICE_VERSION : null, consented_at: guidanceEnabled ? consentedAt : null, cleared_locally: clearedLocally },
      sharing: { include_conversation: includeConversation, conversation: includeConversation ? conversation : [] },
      contact: { name: $("contact-name").value, email: $("contact-email").value, organization: $("contact-organization").value },
      local_scope: I.REVIEW_SCOPE,
    });
  }

  document.querySelectorAll("[data-text]").forEach((node) => node.addEventListener("input", () => { provenance.set(node.dataset.text, { origin: "CLIENT_TYPED", suggestion_id: null }); renderBrief(); }));
  document.querySelectorAll("[data-pilot]").forEach((node) => node.addEventListener("input", () => { pilot[node.dataset.pilot] = node.value; provenance.set("pilot." + node.dataset.pilot, { origin: "CLIENT_TYPED", suggestion_id: null }); renderBrief(); }));
  document.querySelectorAll("input,select").forEach((node) => node.addEventListener("input", renderBrief));
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
  $("show-guided").onclick = () => setMode("guided"); $("show-form").onclick = () => setMode("form");
  $("show-consent").onclick = () => { $("consent-panel").hidden = false; renderBrief(); };
  $("consent-check").onchange = () => { $("enable-guidance").disabled = !$("consent-check").checked; };
  $("enable-guidance").onclick = enableGuidance; $("guidance-form").onsubmit = sendGuidance;
  $("clear-conversation").onclick = () => { conversation = []; pendingProposals = []; clearedLocally = true; $("conversation").innerHTML = '<article class="message assistant"><strong>Carbon</strong><p>Conversation cleared on this device. This does not delete provider records. Your accepted brief changes remain.</p></article>'; renderProposals(); renderBrief(); };
  $("undo-suggestion").onclick = () => { const item = undoStack.pop(); if (!item) return; setValue(item.proposal.field, item.previous); const index = acceptedSuggestions.findIndex((entry) => entry.suggestion_id === item.proposal.suggestion_id); if (index >= 0) acceptedSuggestions.splice(index, 1); provenance.set(item.proposal.field, { origin: item.previous ? "CLIENT_TYPED" : "UNKNOWN", suggestion_id: null }); $("undo-suggestion").disabled = !undoStack.length; renderBrief(); };
  $("export-intake").onclick = () => { try { const reviewed = reviewedPackage(); const blob = new Blob([JSON.stringify(reviewed, null, 2) + "\n"], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${reviewed.brief.draft_id}_${reviewed.brief.revision_id}.carbon-intake.json`; link.click(); URL.revokeObjectURL(link.href); $("intake-status").textContent = "Reviewed brief downloaded locally. Nothing was transmitted to Carbon."; } catch (error) { $("intake-status").textContent = "Export blocked: " + error.message; } };
  renderBrief();
})();
