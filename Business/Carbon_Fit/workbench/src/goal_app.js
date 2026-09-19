(function () {
  "use strict";
  const G = CarbonGoalWorkflow,
    F = CarbonFit,
    E = CarbonC05Evidence,
    S = CarbonSourceAssessment,
    I = CarbonClientIntake,
    H = CarbonWorkbenchHost,
    $ = (id) => document.getElementById(id),
    esc = (x) =>
      String(x ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
          })[c],
      );
  E.installFixtureIndex(
    F.strictJsonParse(
      document.getElementById("c05-fixture-index").textContent,
      { maxBytes: 100000, maxDepth: 8 },
    ),
  );
  S.installRepositorySnapshot(
    F.strictJsonParse(
      document.getElementById("source-assessment-profile").textContent,
      { maxBytes: 100000, maxDepth: 12 },
    ),
    F.strictJsonParse(
      document.getElementById("source-assessment-index").textContent,
      { maxBytes: 200000, maxDepth: 12 },
    ),
  );
  let W = G.newWorkspace(H.componentWorkspace()),
    jobId = null,
    designId = null,
    lastAuthoringRequest = null,
    pendingIntake = null;
  const option = (v, label, sel) =>
    `<option value="${esc(v)}" ${v === sel ? "selected" : ""}>${esc(label ?? v)}</option>`;
  const job = () => W.jobs.find((x) => x.job_id === jobId) || null,
    design = () => job()?.designs.find((x) => x.design_id === designId) || null;
  const safeName = (x) =>
    String(x || "record")
      .replace(/[^A-Za-z0-9._-]/g, "_")
      .slice(0, 100);
  function workspace() {
    W.opportunity_workspace = H.componentWorkspace();
    return W;
  }
  function download(name, value, type = "application/json") {
    H.download(
      name,
      typeof value === "string" ? value : JSON.stringify(value, null, 2) + "\n",
      type,
    );
  }
  function notify(x) {
    H.notify(x);
  }
  const scientificStudies = CarbonScientificStudyUI.create({ getDesign: design, notify, download });
  function intakePreviewView() {
    if (!pendingIntake)
      return `<section class="panel"><div class="eyebrow">Local intake bridge</div><h3>Preview before creating a job</h3><p>Import a closed local intake draft. Nothing is transmitted, and the file cannot carry approvals, native receipts, trusted evidence, or a route.</p><button data-import-intake>Import intake draft</button></section>`;
    const preview = pendingIntake.preview,
      draft = pendingIntake.inspection.draft,
      canCommit = ["CREATE_NEW_JOB", "ADD_REVISION_FOR_REVIEW", "EXACT_REPLAY"].includes(preview.action);
    const reviewed = pendingIntake.inspection.review_package;
    const guided = reviewed ? `<div class="notice"><strong>Reviewed pilot package.</strong> ${reviewed.accepted_suggestions.length} accepted AI suggestion(s); ${reviewed.unresolved_assumptions.length} unresolved assumption(s); conversation ${reviewed.sharing.include_conversation ? "included by client choice" : "not included"}.<br><strong>${esc(reviewed.pilot.label)}:</strong> ${esc(reviewed.pilot.bounded_first_pilot || "not yet supplied")}</div>` : "";
    return `<section class="panel"><div class="eyebrow">Local intake bridge · ${esc(preview.action)}</div><h3>${esc(draft.draft_id)} / ${esc(draft.revision_id)}</h3><p>${esc(preview.message)}</p><div class="badges"><span class="badge neutral">route UNASSESSED</span><span class="badge neutral">origin LOCAL ASSERTION</span><span class="badge neutral">science / rights unresolved</span></div>${guided}<pre>${esc(draft.summary.text)}</pre><p><strong>Unknowns:</strong> ${esc(draft.summary.unknown_fields.join(", ") || "none declared")}<br><strong>Source digest:</strong> ${esc(pendingIntake.inspection.raw_sha256)}<br><strong>Canonical digest:</strong> ${esc(pendingIntake.inspection.canonical_digest)}</p><div class="actions"><button data-import-intake>Choose another draft</button><button id="commit-intake-draft" ${canCommit ? "" : "disabled"}>${preview.action === "ADD_REVISION_FOR_REVIEW" ? "Add revised intake for review" : preview.action === "EXACT_REPLAY" ? "Confirm existing link" : "Create job"}</button><button id="clear-intake-preview">Clear preview</button></div><small>The raw statement remains separate from operator interpretation. A revised intake never rewrites a sealed design. Accepted assistant suggestions remain attributed client-reviewed input, not Carbon evidence.</small></section>`;
  }
  function teamReviewView(j, d) {
    const review = j.team_review,
      assessment = d.assessment,
      taskRows = assessment.scientific_task_dependencies
        .map(
          (item) => `<tr><td>${esc(item.task_kind)}${item.task_kind === "PHYSICAL_DEFINITION_CHECK" ? `<br><button id="run-physical-definition-check" ${d.status === "DRAFT" ? "" : "disabled"}>Run structural check</button>` : ""}</td><td>${esc(item.availability)}${item.result ? `<br><small>${esc(item.result.status)} · ${esc(item.result.provenance)}</small>` : ""}</td><td>${esc(item.note)}${item.check_id ? `<br><small>${esc(item.check_id)} · ${esc(item.scope_digest)} · ${esc(item.exact_design_binding)}</small>` : ""}</td></tr>`,
        )
        .join("");
    return `<section class="panel" id="team-review-panel"><div class="eyebrow">Private team review · exact design revision</div><h3>Intake queue and feasibility assessment</h3><div class="badges"><span class="badge neutral">${esc(review.queue_state)}</span><span class="badge neutral">reviewer ${esc(review.assigned_reviewer || "unassigned")}</span><span class="badge neutral">science / rights unresolved</span></div><div class="form-grid"><label>Queue state<select id="team-queue-state">${G.QUEUE_STATES.map((x) => option(x, x, review.queue_state)).join("")}</select></label><label>Assigned reviewer<input id="team-reviewer" value="${esc(review.assigned_reviewer)}" placeholder="Named team reviewer"></label><label>Current action<textarea id="team-current-action">${esc(review.current_action)}</textarea></label><label>Restart event<textarea id="team-restart-event">${esc(review.next_restart_event)}</textarea></label><label>Correction field<input id="team-correction-field" placeholder="assignment.client_words"></label><label>Corrected transcription<input id="team-correction-value"></label><label>Correction reason<input id="team-correction-reason"></label><label>Assessment note<textarea id="team-note"></textarea></label><label>Outstanding client/science question<textarea id="team-question"></textarea></label></div><div class="actions"><button id="save-team-review">Save queue state</button><button id="add-team-correction">Record correction without overwriting original</button><button id="add-team-note">Add assessment note</button><button id="add-team-question">Add outstanding question</button></div>${review.original_statement_corrections.length ? `<details><summary>Preserved corrections (${review.original_statement_corrections.length})</summary><ul>${review.original_statement_corrections.map((item) => `<li>${esc(item.field)}: <del>${esc(item.original)}</del> → ${esc(item.corrected)} · ${esc(item.reason)}</li>`).join("")}</ul></details>` : ""}${review.assessment_notes.length ? `<details><summary>Internal notes (${review.assessment_notes.length})</summary><ul>${review.assessment_notes.map((item) => `<li>${esc(item.text)} · ${esc(item.recorded_by)}</li>`).join("")}</ul></details>` : ""}<h3 class="section-title">Traceable assessment</h3><p class="muted">Empty fields remain unknown. Entries are human planning assertions until their native source supplies stronger evidence.</p><div class="form-grid"><label>Engineering decision<textarea data-assessment="intended_engineering_decision">${esc(assessment.intended_engineering_decision)}</textarea></label>${G.ASSESSMENT_FIELDS.map((field) => `<label>${esc(field.replaceAll("_", " "))}<textarea data-assessment="${esc(field)}">${esc(assessment[field])}</textarea></label>`).join("")}</div><details><summary>Shared core task dependencies</summary><div class="scroll"><table><thead><tr><th>Requested check</th><th>Availability</th><th>Boundary</th></tr></thead><tbody>${taskRows}</tbody></table></div><small>Issue #209 owns execution. These rows are dependency facts, not GPU/TPU/Julia execution claims.</small></details><div class="actions"><button id="export-pilot-brief">Export client pilot brief</button><button id="export-execution-brief">Export internal execution brief</button></div></section>`;
  }
  let pendingAdaptJourney = false;
  document.addEventListener(
    "click",
    (e) => {
      if (e.target?.id === "journey-adapt") pendingAdaptJourney = true;
    },
    true,
  );
  document.addEventListener("click", (e) => {
    if (e.target?.id === "import-c05-evidence") $("c05-evidence-file").click();
    if (e.target?.id === "burgers-demo" && pendingAdaptJourney) {
      pendingAdaptJourney = false;
      const j = job(),
        d = design();
      if (!d || d.status !== "DRAFT") return;
      j.accountable_owner = "Synthetic Carbon owner";
      j.lead = "S1";
      G.selectRoute(d, "ADAPT_SUPPORTED_CHALLENGE", {
        rationale:
          "The exact public Burgers Dynamics template supports delta review.",
        source_or_capability_ref: "periodic_viscous_burgers_1d_v1 / Dynamics",
        route_basis:
          "Native authoring semantics and design-scoped C-05 evidence remain bounded to the source template.",
        unresolved_conditions: [
          "scientific limits and uncertainty remain unresolved",
        ],
        next_decision:
          "Request only the affected scientific or protection decision.",
        selected_by_assertion: "Synthetic journey fixture",
        status_provenance: "LOCAL_MANUAL_ASSERTION",
      });
      render();
    }
  });
  function evidenceView(d) {
    return `<section class="panel"><div class="eyebrow">C-05 source evidence</div><h3>Read-only public DEVELOPMENT measurement</h3><p><button id="import-c05-evidence">Import exact C-05 result bundle</button> The adapter verifies registered bytes, provenance, design revision, traces and cases. It never computes a score or pass/fail.</p>${d.measurement_evidence.length ? d.measurement_evidence.map((r) => `<article class="result-card"><strong>${esc(r.evidence_state)}</strong><p>${esc(r.source_disposition)} · ${esc(r.binding_status)} · ${esc(r.trace_state)}</p>${r.measurements.length ? `<div class="scroll"><table><thead><tr><th>Measurement</th><th>Candidate</th><th>Reference</th><th>Raw error</th><th>Normalized error</th><th>Limit / uncertainty</th></tr></thead><tbody>${r.measurements.map((x) => `<tr><td>${esc(x.measurement_id)}</td><td>${esc(x.candidate_value)}</td><td>${esc(x.reference_value)}</td><td>${esc(x.raw_absolute_error)}</td><td>${esc(x.normalized_error)}</td><td>not supplied / unresolved</td></tr>`).join("")}</tbody></table></div><div class="scroll"><table><thead><tr><th>Physics check</th><th>Raw defect</th><th>Normalized defect</th><th>Limit / uncertainty</th></tr></thead><tbody>${r.physics.map((x) => `<tr><td>${esc(x.physics_id)}</td><td>${esc(x.raw_defect)}</td><td>${esc(x.normalized_defect)}</td><td>not supplied / unresolved</td></tr>`).join("")}</tbody></table></div>` : `<p>No observations imported. The source returned typed disposition ${esc(r.source_disposition)}.</p>`}<small>Source ${esc(r.source.source_revision)} · request ${esc(r.source.request_digest)} · result ${esc(r.source.result_digest)}. Not qualified, score eligible, approved, or launch authorized.</small></article>`).join("") : '<p class="empty">No source measurement evidence is bound to this design revision.</p>'}</section>`;
  }
  function routeView(j, d) {
    const p = d.route_plan,
      c = d.coordination,
      n = G.nextRouteAction(j, d);
    return `<section class="panel"><div class="eyebrow">Three-route planning</div><h3>Smallest defensible path</h3><div class="form-grid"><label>Route<select id="route-choice">${G.ROUTES.map((x) => option(x, x, p.route)).join("")}</select></label><label>Accountable owner<input data-job="accountable_owner" value="${esc(j.accountable_owner)}" placeholder="Human disposition owner"></label><label>Commercial/editorial context<textarea data-scope="commercial_context">${esc(d.scope.commercial_context)}</textarea></label><label>Disclosure/publication scope<textarea data-scope="disclosure_scope">${esc(d.scope.disclosure_scope)}</textarea></label><label>Deployment environment<textarea data-scope="deployment_environment">${esc(d.scope.deployment_environment)}</textarea></label><label>Rationale<textarea id="route-rationale">${esc(p.rationale)}</textarea></label><label>Source capability / Challenge ref<textarea id="route-source">${esc(p.source_or_capability_ref)}</textarea></label><label>Exact route basis / delta<textarea id="route-basis">${esc(p.route_basis)}</textarea></label><label>Unresolved conditions (one per line)<textarea id="route-conditions">${esc(p.unresolved_conditions.join("\n"))}</textarea></label><label>One bounded feasibility question<textarea id="route-question">${esc(p.bounded_question)}</textarea></label><label>Stop condition<textarea id="route-stop">${esc(p.stop_condition)}</textarea></label><label>Restart event<textarea id="route-restart">${esc(p.restart_event)}</textarea></label><label>Next owner decision<textarea id="route-decision">${esc(p.next_decision)}</textarea></label></div><div class="actions"><button id="save-route">Save exact-revision route</button><button id="journey-existing">Journey A · existing</button><button id="journey-adapt">Journey B · adapt</button><button id="journey-develop">Journey C · develop</button></div><div class="result"><strong>${esc(n.action)}</strong><p>${esc(n.why)}</p><small>Missing: ${esc(n.missing_conditions.join(", ") || "none")}. No fit percentage or hidden priority score is used.</small></div><h3 class="section-title">Owner disposition</h3><div class="form-grid"><label>Customer outcome<select data-customer-outcome>${G.CUSTOMER_OUTCOMES.map((x) => option(x, x, c.customer_outcome)).join("")}</select></label><label>Decision needed<input data-coordination="decision_needed" value="${esc(c.decision_needed)}"></label><label>Blocker<input data-coordination="blocker" value="${esc(c.blocker)}"></label><label>Blocker owner<input data-coordination="blocker_owner" value="${esc(c.blocker_owner)}"></label><label>Restart event<input data-coordination="restart_event" value="${esc(c.restart_event)}"></label></div><button id="link-owner-request">Link #42 EXPORTED_OWNER_REQUEST negative control</button></section>`;
  }
  function applicabilityView(d) {
    const latest = d.change_log.at(-1);
    return `<section class="panel"><div class="eyebrow">Evidence applicability / change impact</div><h3>Selective carry-forward, never automatic qualification</h3>${latest ? `<p><strong>Last change:</strong> ${esc(latest.field)} · ${esc(latest.domains.join(", ") || "impact unresolved")}</p>` : '<p class="muted">No material change recorded for this revision.</p>'}${d.evidence_bindings.length ? `<div class="scroll"><table><thead><tr><th>Evidence / origin</th><th>Scope dependencies</th><th>Assessment / relationship</th><th>Rights/use</th><th>Outstanding reasons / provenance</th></tr></thead><tbody>${d.evidence_bindings.map((x) => `<tr><td>${esc(x.evidence_kind)}<br><small>${esc(x.source_digest_or_identity)}<br>claimed ${esc(x.source_claimed_provenance)} · checked ${esc(x.origin_verification)}</small></td><td>${esc(x.dependency_domains.join(", "))}</td><td>${esc(x.scientific_applicability)}<br><small>${esc(x.scope_relationship)}</small></td><td>${esc(x.use_or_rights_status)}</td><td>${esc([...x.scientific_review_reasons, ...x.rights_review_reasons].map((r) => r.field + ":" + r.domain).join(", ") || "none")}<br><small>${esc(x.status_provenance)} · origin ${esc(x.originating_design_id)} r${esc(x.originating_design_revision)}</small></td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No applicability binding. Migration and source links do not infer applicability.</p>'}<small>Unchanged scope is a relationship, not a favorable assessment. Reference-answer reuse is excluded.</small></section>`;
  }
  function sourceAssessmentView(d) {
    const p = S.project(d),
      request = d.source_assessments.requests.find(
        (item) => item.request_id === d.source_assessments.current_request_id,
      ),
      receipt = d.source_assessments.receipts.find(
        (item) => item.request_id === d.source_assessments.current_request_id,
      ),
      stored = d.source_assessments.responses.find(
        (item) => item.received_for_request_id === d.source_assessments.current_request_id,
      ),
      answerState = (questionId) => {
        if (!receipt || !stored) return "UNANSWERED";
        const answer = stored.response.answered.find(
          (item) => item.question_id === questionId,
        );
        if (!answer) return "UNANSWERED";
        return answer.status === "ANSWERED"
          ? "ANSWERED_TECHNICAL"
          : answer.status === "PARTIAL"
            ? "PARTIAL_STILL_OPEN"
            : answer.status;
      };
    return `<section class="panel"><div class="eyebrow">Ryan-controlled source assessment</div><h3>Repository-pinned, read-only technical assessment</h3><div class="badges"><span class="badge neutral">${esc(p.request_status)}</span><span class="badge neutral">${esc(p.assessment_status)}</span><span class="badge neutral">qualification effect NONE</span><span class="badge neutral">rights effect NONE</span></div><p><strong>Installed profile:</strong> ${esc(p.profile_id)}<br><strong>Snapshot:</strong> ${esc(p.snapshot_id)} · as of ${esc(p.snapshot_as_of)}</p>${request ? `<p><strong>Frozen request:</strong> ${esc(request.request_id)}<br><small>${esc(request.subject_digest)}</small></p>${receipt && stored ? `<p><strong>Assessment:</strong> ${esc(stored.response.response_id)}<br><strong>Prepared by:</strong> ${esc(stored.response.prepared_by)} · <strong>admitted owner:</strong> github:jbequ5<br><small>${esc(receipt.origin_verification)} · resolves ${esc(receipt.resolved_reason_ids.length)} review reasons</small></p>` : ""}<div class="scroll"><table><thead><tr><th>Question</th><th>State</th></tr></thead><tbody>${request.questions.map((q) => `<tr><td>${esc(q.question_id)}<br><small>${esc(q.text)}</small></td><td>${esc(answerState(q.question_id))}</td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No exact assessment request prepared for this design.</p>'}<p><strong>Next action:</strong> ${esc(p.next_action)}</p><div class="actions"><button id="prepare-source-assessment">Freeze & prepare request</button><button id="export-source-assessment" ${request ? "" : "disabled"}>Export exact request</button><button id="import-source-assessment">Import source assessment</button></div><small>The browser sends nothing. A matching repository snapshot establishes only admitted byte-and-scope correspondence. It does not authenticate a live operator, prove fresh execution, qualify science, grant rights, or authorize launch. Offline use cannot detect a later withdrawal until a newer accepted build is installed.</small></section>`;
  }
  function renderOwnerConsole() {
    const root = $("owner-console-view"),
      view = G.ownerConsole(W),
      queue = G.teamQueue(W);
    root.innerHTML = `<div class="eyebrow">GOAL-WORKBENCH-10 · private team workflow</div><h2>Owner Console</h2><section class="panel"><h3>Intake queue</h3><p class="muted">Engineering objective, source brief, missing information, reviewer and next action remain distinct from evidence maturity and customer outcome.</p>${queue.length ? `<div class="scroll"><table><thead><tr><th>Inquiry</th><th>Objective / current workflow</th><th>Conditions / outputs</th><th>Reference / missing</th><th>Reviewer / state</th><th>Next action</th></tr></thead><tbody>${queue.map((item) => `<tr><td><button data-console-job="${esc(item.job_id)}">${esc(item.title)}</button></td><td>${esc(item.objective)}<br><small>${esc(item.current_workflow)}</small></td><td>${esc(item.operating_conditions)}<br><small>${esc(item.requested_outputs)}</small></td><td>${esc(item.reference_evidence)}<br><small>${esc(item.missing_information.join("; ") || "none recorded")}</small></td><td>${esc(item.assigned_reviewer || "unassigned")}<br><small>${esc(item.queue_state)} · ${esc(item.provenance)}</small></td><td>${esc(item.next_action)}</td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No reviewed brief is queued.</p>'}</section><div class="stats">${G.ATTENTION_BUCKETS.map((x) => `<div class="stat"><strong>${view.counts[x]}</strong><span>${esc(x.replaceAll("_", " "))}</span></div>`).join("")}</div><p class="muted">Workflow progress, evidence maturity, and customer outcome are separate. A finished observation is not an active worker; an unchanged relationship is not a resolved assessment.</p>${view.rows.length ? `<div class="scroll"><table><thead><tr><th>Job / working revision</th><th>Route / people</th><th>Three status axes</th><th>One next action</th><th>Blocker / restart</th><th>Provenance</th></tr></thead><tbody>${view.rows.map((x) => `<tr><td><button data-console-job="${esc(x.job_id)}">${esc(x.client_job)}</button><br><small>${esc(x.design_id)} r${x.design_revision}</small></td><td>${esc(x.route)}<br><small>Owner ${esc(x.accountable_owner || "unassigned")} · lead ${esc(x.lead || "unassigned")}</small></td><td>${esc(x.workflow_state)}<br>${esc(x.evidence_state)}<br>${esc(x.customer_outcome)}<br><small>${esc(x.evidence_facts.join("; ") || "no evidence facts")} · ${esc(x.open_request_or_handoff)} · ${esc(x.evidence_received)}</small></td><td><strong>${esc(x.current_action)}</strong><br><small>${esc(x.current_action_ref)} · ${esc(x.action_reason)}</small></td><td>${esc(x.blocker || "none")}<br><small>${esc(x.restart_event || "none")}</small></td><td>${esc(x.workflow_provenance)}<br>${esc(x.evidence_provenance)}<br>${esc(x.customer_outcome_provenance)}</td></tr>`).join("")}</tbody></table></div>` : '<section class="panel empty"><h3>No client job yet</h3><p>Create a job in Client jobs. No route will be inferred.</p></section>'}<p class="source-note">${esc(view.authority)}</p>`;
    document.querySelectorAll("[data-console-job]").forEach(
      (button) =>
        (button.onclick = () => {
          jobId = button.dataset.consoleJob;
          const selectedJob = W.jobs.find((x) => x.job_id === jobId);
          designId =
            selectedJob.working_design_id || selectedJob.designs[0].design_id;
          selectedJob.working_design_id = designId;
          document.querySelector('[data-tab="jobs"]').click();
        }),
    );
  }
  function saveRoute() {
    const d = design();
    try {
      G.selectRoute(d, $("route-choice").value, {
        rationale: $("route-rationale").value,
        source_or_capability_ref: $("route-source").value,
        route_basis: $("route-basis").value,
        unresolved_conditions: $("route-conditions")
          .value.split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
        next_decision: $("route-decision").value,
        bounded_question: $("route-question").value,
        stop_condition: $("route-stop").value,
        restart_event: $("route-restart").value,
        selected_by_assertion: "Local workbench editor",
        status_provenance: "LOCAL_MANUAL_ASSERTION",
      });
      render();
      notify(
        "Route saved for this exact draft revision; no authority was granted.",
      );
    } catch (error) {
      notify(error.message);
    }
  }
  function loadRouteJourney(kind) {
    const j = job(),
      d = design();
    if (d.status !== "DRAFT") return notify("Create a revision first.");
    j.accountable_owner = "Synthetic Carbon owner";
    if (kind === "existing") {
      j.lead = "S1";
      Object.assign(d.scope, {
        physics_family: "existing_external_capability_v1",
        intended_use: "Synthetic bounded customer decision",
        outputs: "Declared bounded output",
        units: "declared units",
        rights_scope: "UNRESOLVED",
        deployment_environment: "Customer deployment environment unresolved",
      });
      G.selectRoute(d, "USE_EXISTING_CAPABILITY", {
        rationale:
          "A referenced existing capability may avoid unnecessary Challenge authoring.",
        source_or_capability_ref: "public:synth-existing-capability-v1",
        route_basis:
          "Compare intended use, output, units, envelope, rights and deployment assumptions.",
        unresolved_conditions: [
          "intended-use verification",
          "deployment evidence",
        ],
        next_decision: "Retain baseline or require delivery qualification.",
        selected_by_assertion: "Synthetic journey fixture",
        status_provenance: "LOCAL_MANUAL_ASSERTION",
      });
      d.coordination.decision_needed =
        "Intended-use and deployment applicability";
      d.coordination.blocker = "Deployment evidence unavailable";
      d.coordination.blocker_owner = "Product owner";
      d.coordination.restart_event =
        "Exact deployment evidence or owner baseline decision";
    }
    if (kind === "adapt") {
      $("burgers-demo").click();
      return;
    }
    if (kind === "develop") {
      j.lead = "R1";
      Object.assign(d.scope, {
        physics_family: "synthetic_unsupported_multiphysics_v1",
        requested_goal: "Unsupported coupled-physics feasibility",
        intended_use:
          "Determine whether one bounded supported representation exists.",
        rights_scope: "SYNTHETIC_INTERNAL",
      });
      G.selectRoute(d, "DEVELOP_NEW_CAPABILITY", {
        rationale:
          "The requested physics and output semantics are unsupported.",
        route_basis:
          "No supported authoring adapter matches the intended physics.",
        bounded_question:
          "Can the existing source contracts represent one synthetic coupled observable without changing its physics?",
        stop_condition:
          "Stop after one source-owner compatibility finding or precise unsupported result.",
        restart_event:
          "Source owner returns the bounded compatibility finding.",
        next_decision:
          "Revise, reroute, park, or authorize a separately scoped follow-up.",
        selected_by_assertion: "Synthetic journey fixture",
        status_provenance: "LOCAL_MANUAL_ASSERTION",
      });
      d.coordination.blocker = "Bounded feasibility response absent";
      d.coordination.blocker_owner = "R1";
      d.coordination.restart_event = d.route_plan.restart_event;
    }
    render();
  }
  function createJob() {
    const n = W.jobs.length + 1,
      id = "job-" + String(n).padStart(3, "0");
    const j = G.newJob(id, "Untitled client job " + n);
    W.jobs.push(j);
    jobId = id;
    designId = j.designs[0].design_id;
    W.selected_job_id = jobId;
    W.selected_design_id = designId;
    render();
  }
  function bindIntakePreview() {
    document.querySelectorAll("[data-import-intake]").forEach(
      (button) => (button.onclick = () => $("intake-draft-file").click()),
    );
    const clear = $("clear-intake-preview");
    if (clear)
      clear.onclick = () => {
        pendingIntake = null;
        render();
      };
    const commit = $("commit-intake-draft");
    if (commit)
      commit.onclick = () => {
        try {
          const result = G.commitIntakeImport(
            W,
            pendingIntake.inspection,
            pendingIntake.preview,
          );
          const selected = W.jobs.find((item) => item.job_id === result.job_id);
          jobId = result.job_id;
          designId = selected.working_design_id || selected.designs[0].design_id;
          W.selected_job_id = jobId;
          W.selected_design_id = designId;
          pendingIntake = null;
          render();
          notify(
            result.changed
              ? "Local intake linked. Route, science, rights, execution and launch remain unassessed."
              : "Exact replay recognized; no duplicate job or requirement was created.",
          );
        } catch (error) {
          notify("Intake commit rejected: " + error.message);
        }
      };
  }
  function bind() {
    const j = job(),
      d = design();
    document.querySelectorAll("[data-assignment]").forEach(
      (e) =>
        (e.oninput = () => {
          j.assignment[e.dataset.assignment] = e.value;
        }),
    );
    document.querySelectorAll("[data-job]").forEach(
      (e) =>
        (e.oninput = () => {
          j[e.dataset.job] = e.value;
        }),
    );
    document.querySelectorAll("[data-scope]").forEach((e) =>
      e.addEventListener(e.tagName === "SELECT" ? "change" : "input", () => {
        if (d.status !== "DRAFT")
          return notify("Sealed design is immutable; create a revision.");
        G.applyChange(
          d,
          e.dataset.scope,
          e.value,
          "Edited in the local workbench",
        );
        renderSummary();
      }),
    );
    document.querySelectorAll("[data-score]").forEach(
      (e) =>
        (e.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.score_plan[e.dataset.score] = e.value;
          G.recordImpact(
            d,
            "score",
            "Score plan changed in the local workbench",
          );
          renderSummary();
        }),
    );
    document.querySelectorAll("[data-reference]").forEach(
      (e) =>
        (e.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.reference_plan[e.dataset.reference] = e.value;
          G.recordImpact(
            d,
            "reference",
            "Reference plan changed in the local workbench",
          );
          renderSummary();
        }),
    );
    document.querySelectorAll("[data-econ]").forEach((e) =>
      e.addEventListener(e.tagName === "SELECT" ? "change" : "input", () => {
        if (d.status !== "DRAFT")
          return notify("Sealed design is immutable; create a revision.");
        d.cpes.economics[e.dataset.econ] = e.value;
        renderSummary();
      }),
    );
    document.querySelectorAll("[data-control]").forEach(
      (e) =>
        (e.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.cpes.protection.controls[e.dataset.control].state = e.value;
          renderSummary();
        }),
    );
    document.querySelectorAll("[data-blocker]").forEach(
      (e) =>
        (e.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.cpes.protection.blockers[e.dataset.blocker].applicability = e.value;
          renderSummary();
        }),
    );
  }
  function bindV05() {
    const d = design();
    if (!d) return;
    $("save-route").onclick = saveRoute;
    $("journey-existing").onclick = () => loadRouteJourney("existing");
    $("journey-adapt").onclick = () => loadRouteJourney("adapt");
    $("journey-develop").onclick = () => loadRouteJourney("develop");
    document.querySelectorAll("[data-coordination]").forEach(
      (e) =>
        (e.oninput = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.coordination[e.dataset.coordination] = e.value;
          d.coordination.last_relevant_design_revision = d.revision;
          renderOwnerConsole();
        }),
    );
    document.querySelectorAll("[data-customer-outcome]").forEach(
      (e) =>
        (e.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.coordination.customer_outcome = e.value;
          d.coordination.customer_outcome_provenance = "LOCAL_MANUAL_ASSERTION";
          renderOwnerConsole();
        }),
    );
    $("link-owner-request").onclick = () => {
      try {
        G.linkExternalRecord(d, {
          record_id: "D-QUAL-PREP-01-FOLLOWUP-01",
          source_ref:
            "https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5670993432",
          status: "EXPORTED_OWNER_REQUEST",
          provenance: "EXTERNAL_LINKED_RECORD",
          note: "Routed only; not acknowledged, approved, selected, funded, or executed.",
        });
        d.coordination.blocker = "Scientific-owner decision pending";
        d.coordination.blocker_owner = "D-QUAL scientific owner";
        d.coordination.restart_event =
          "Issue #42 records acknowledgment and an authorized next state";
        render();
        notify(
          "External owner request linked as waiting; no approval or execution was inferred.",
        );
      } catch (error) {
        notify(error.message);
      }
    };
  }
  function bindTeamReview() {
    const j = job(), d = design();
    if (!j || !d || !$("team-review-panel")) return;
    document.querySelectorAll("[data-assessment]").forEach(
      (element) =>
        (element.onchange = () => {
          if (d.status !== "DRAFT")
            return notify("Sealed design is immutable; create a revision.");
          d.assessment[element.dataset.assessment] = element.value;
          renderOwnerConsole();
        }),
    );
    $("save-team-review").onclick = () => {
      j.team_review.queue_state = $("team-queue-state").value;
      j.team_review.assigned_reviewer = $("team-reviewer").value;
      j.team_review.current_action = $("team-current-action").value;
      j.team_review.next_restart_event = $("team-restart-event").value;
      j.team_review.provenance = "LOCAL_MANUAL_ASSERTION";
      G.validateJob(j);
      render();
      notify("Team review state saved as a local manual assertion.");
    };
    $("add-team-correction").onclick = () => {
      try {
        const field = $("team-correction-field").value,
          key = field.startsWith("assignment.") ? field.slice(11) : field,
          original = Object.hasOwn(j.assignment, key)
            ? j.assignment[key]
            : "Original value retained in source intake bytes";
        G.addReviewCorrection(j.team_review, {
          correction_id:
            "correction-" + String(j.team_review.original_statement_corrections.length + 1),
          field,
          original,
          corrected: $("team-correction-value").value,
          reason: $("team-correction-reason").value,
          recorded_by: j.team_review.assigned_reviewer || "unassigned local reviewer",
        });
        render();
        notify("Correction recorded beside the unchanged original statement.");
      } catch (error) {
        notify(error.message);
      }
    };
    $("add-team-note").onclick = () => {
      try {
        G.addAssessmentNote(j.team_review, {
          record_id: "note-" + String(j.team_review.assessment_notes.length + 1),
          text: $("team-note").value,
          recorded_by: j.team_review.assigned_reviewer || "unassigned local reviewer",
        });
        render();
      } catch (error) {
        notify(error.message);
      }
    };
    $("add-team-question").onclick = () => {
      try {
        G.addOutstandingQuestion(j.team_review, {
          record_id: "question-" + String(j.team_review.outstanding_questions.length + 1),
          text: $("team-question").value,
          recorded_by: j.team_review.assigned_reviewer || "unassigned local reviewer",
        });
        render();
      } catch (error) {
        notify(error.message);
      }
    };
    $("export-pilot-brief").onclick = () =>
      download(safeName(j.job_id) + "_client_pilot_brief.json", G.clientPilotBrief(j, d));
    $("export-execution-brief").onclick = () =>
      download(safeName(j.job_id) + "_internal_execution_brief.json", G.internalExecutionBrief(j, d));
    $("run-physical-definition-check").onclick = async () => {
      try {
        await G.recordPhysicalDefinitionCheck(d, CarbonScientificStudies);
        render();
        notify(
          "C-CORE-04 structural check recorded for this exact draft. No solver ran and no qualification was created.",
        );
      } catch (error) {
        notify("Physical-definition check rejected: " + error.message);
      }
    };
  }
  function renderEconomics() {
    const d = design(),
      el = $("goal-economics-result");
    if (!d || !el) return;
    const econ = d.cpes.economics,
      r = G.economics(d);
    el.className = "result " + (r.status === "INVALID" ? "invalid" : "");
    el.innerHTML = `<strong>${esc(r.relation.toUpperCase())}</strong><p>${esc(r.message)}</p>${r.status === "CALCULATED_CONDITIONAL" ? `<p>A=${esc(r.a_reference_control_work)}, B=${esc(r.b_reference_control_work)}, saving=${esc(r.net_saving_per_group)} ${esc(r.unit)}.</p>` : ""}<p>Completed comparisons: ${esc(econ.completed_comparisons || "unknown")} of ${esc(econ.offered_requests || "unknown")} offered; unresolved/censored ${esc(econ.unresolved_or_censored || "unknown")}.</p><small>Upfront burden is reported separately and cannot change recurring capacity or mandatory gates. Invalidated bindings: ${esc(d.cpes.invalidated_by.join("; ") || "none recorded")}</small>`;
  }
  function renderSummary() {
    const d = design();
    if (!d) return;
    const c = G.coverage(d),
      e = G.economics(d),
      a = G.compatibility(d),
      l = G.launchCandidate(d, job()?.native_task_id || "");
    $("goal-summary").innerHTML =
      `<div class="decision-grid"><div><span>Client/design</span><strong>${esc(d.decision.client_interpretation)}</strong><small>${esc(c.status)} · missing case coverage ${esc(c.missing_case_requirements.join(", ") || "none")}</small></div><div><span>Native authoring</span><strong>${esc(d.authoring.semantic_receipt?.status || a.status)}</strong><small>${esc(a.reason)}${a.gaps?.length ? " Gaps: " + esc(a.gaps.join("; ")) : ""}</small></div><div><span>CPES baseline</span><strong>Variant A · DEVELOPMENT</strong><small>${esc(e.message)}</small></div></div><p><strong>Launch:</strong> ${esc(l.status)} · ${l.remaining_decisions.length} remaining decision(s). A complete local record cannot grant qualification or launch.</p>${evidenceView(d)}${sourceAssessmentView(d)}`;
    renderEconomics();
  }
  function render() {
    renderOwnerConsole();
    const root = $("jobs-view");
    if (!W.jobs.length) {
      root.innerHTML = `<div class="eyebrow">GOAL-WORKBENCH-08 · local intake</div><h2>Client jobs & Challenge designs</h2><div class="notice"><strong>One record, no forced Atlas match.</strong> Start from the decision the client needs. Nothing is sent, scored, qualified, registered, or launched.</div>${intakePreviewView()}<section class="panel empty"><h3>No client job yet</h3><p>Create an empty direct record, import a local intake draft, or import a prior complete session. Migration never chooses a route or resolves review debt.</p><button class="primary" id="new-job">Create direct client job</button><button id="import-goal-empty">Import complete session</button></section>`;
      $("new-job").onclick = createJob;
      $("import-goal-empty").onclick = () => $("goal-workspace-file").click();
      bindIntakePreview();
      return;
    }
    const j = job() || W.jobs[0];
    jobId = j.job_id;
    const d =
      design() ||
      j.designs.find((x) => x.design_id === j.working_design_id) ||
      j.designs[0];
    designId = d.design_id;
    W.selected_job_id = jobId;
    W.selected_design_id = designId;
    const reqOptions = d.requirements
      .map((x) =>
        option(
          x.requirement_id,
          x.requirement_id + " · " + x.original_words.slice(0, 70),
        ),
      )
      .join("");
    const econ = d.cpes.economics,
      econResult = G.economics(d),
      cov = G.coverage(d),
      launch = G.launchCandidate(d, j.native_task_id);
    root.innerHTML = `<div class="eyebrow">GOAL-WORKBENCH-10 · physical-definition integration</div><div class="panel-heading"><div><h2>Client jobs & Challenge designs</h2><p class="muted">The Atlas is optional context. Earlier intake revisions, sealed designs, and source evidence remain immutable.</p></div><div class="actions"><button id="new-job">New job</button><button data-import-intake>Import intake draft</button><button id="export-goal">Export complete session</button><button id="import-goal">Import session</button></div></div>${pendingIntake ? intakePreviewView() : ""}<div class="job-layout"><aside class="list" aria-label="Client jobs">${W.jobs.map((x) => `<button class="op-item ${x.job_id === jobId ? "selected" : ""}" data-job-select="${esc(x.job_id)}"><span>${esc(x.title)}</span><small>${esc(x.job_id)} · ${x.designs.length} design revision(s) · ${x.intake_records.length} intake revision(s) · ${esc(x.team_review.queue_state)} · working ${esc(x.working_design_id || "unselected")}</small></button>`).join("")}</aside><div><section class="panel result-card"><div class="panel-heading"><div><div class="eyebrow">Decision snapshot</div><h3>${esc(j.title)} · ${esc(d.design_id)} r${d.revision}</h3></div><span class="badge ${d.status === "DRAFT" ? "hyp" : "neutral"}">${esc(d.status)} · ${j.working_design_id === d.design_id ? "WORKING DESIGN" : "HISTORICAL VIEW"}</span></div><div id="goal-summary" aria-live="polite"></div>${j.intake_records.length ? `<details><summary>Source intake lineage (${j.intake_records.length})</summary><ul>${j.intake_records.map((record) => `<li>${esc(record.draft_id)} / ${esc(record.revision_id)} · ${esc(record.canonical_digest)} · local assertion</li>`).join("")}</ul></details>` : ""}</section>
 <section class="panel"><div class="panel-heading"><div><div class="eyebrow">Assignment</div><h3>Intended decision before score</h3></div><label>Design revision<select id="design-select">${j.designs.map((x) => option(x.design_id, x.alternative_label + " · r" + x.revision + " · " + x.status, designId)).join("")}</select></label></div><div class="form-grid"><label>Job title<input data-job="title" value="${esc(j.title)}"></label><label>Lead<input data-job="lead" value="${esc(j.lead)}" placeholder="Owner-named lead"></label><label class="span-all">Client's original words<textarea data-assignment="client_words">${esc(j.assignment.client_words)}</textarea></label><label>Source reference<input data-assignment="client_source" value="${esc(j.assignment.client_source)}"></label><label>Intended decision<textarea data-assignment="intended_decision">${esc(j.assignment.intended_decision)}</textarea></label><label>Credible deployed baseline<textarea data-assignment="credible_baseline">${esc(j.assignment.credible_baseline)}</textarea></label><label>Context / native task link notes<textarea data-assignment="context">${esc(j.assignment.context)}</textarea></label><label>Allowances and stop limits<textarea data-assignment="allowances">${esc(j.assignment.allowances)}</textarea></label><label>Rights summary<textarea data-assignment="rights_summary">${esc(j.assignment.rights_summary)}</textarea></label><label>Next owner decision<textarea data-assignment="next_owner_decision">${esc(j.assignment.next_owner_decision)}</textarea></label><label>Native task ID, if it exists<input data-job="native_task_id" value="${esc(j.native_task_id)}"></label></div><div class="actions"><button id="link-atlas">Link current Atlas opportunity</button><button id="burgers-demo">Load public Burgers demonstration</button><button id="new-alternative">New alternative</button><button id="revise-design">Seal & revise</button></div><small>Current optional source link: ${esc(j.source_opportunity_id || "none")}. Linking does not make an Atlas hypothesis measured or authoritative.</small></section>${teamReviewView(j, d)}${routeView(j, d)}${applicabilityView(d)}
 <section class="panel"><div class="eyebrow">Preparation</div><h3>Design scope</h3><div class="form-grid"><label>Physics/template family<input data-scope="physics_family" value="${esc(d.scope.physics_family)}" placeholder="e.g. periodic_viscous_burgers_1d_v1"></label><label>Requested active goal<input data-scope="requested_goal" value="${esc(d.scope.requested_goal)}"></label><label>Intended use<textarea data-scope="intended_use">${esc(d.scope.intended_use)}</textarea></label><label>Required causal inputs<textarea data-scope="inputs">${esc(d.scope.inputs)}</textarea></label><label>Requested outputs<textarea data-scope="outputs">${esc(d.scope.outputs)}</textarea></label><label>Units / scaling<textarea data-scope="units">${esc(d.scope.units)}</textarea></label><label>Geometry<textarea data-scope="geometry">${esc(d.scope.geometry)}</textarea></label><label>Initial / boundary / forcing conditions<textarea data-scope="conditions">${esc(d.scope.conditions)}</textarea></label><label>Intended regime<textarea data-scope="regime">${esc(d.scope.regime)}</textarea></label><label>Query workload<textarea data-scope="query_workload">${esc(d.scope.query_workload)}</textarea></label><label>Required turnaround<textarea data-scope="turnaround">${esc(d.scope.turnaround)}</textarea></label><label>Failure consequences<textarea data-scope="failure_consequences">${esc(d.scope.failure_consequences)}</textarea></label><label>Data/reference access<textarea data-scope="data_access">${esc(d.scope.data_access)}</textarea></label><label>Rights scope<select data-scope="rights_scope">${["UNRESOLVED", "SYNTHETIC_INTERNAL", "CLIENT_RESTRICTED", "THIRD_PARTY_UNRESOLVED"].map((x) => option(x, x, d.scope.rights_scope)).join("")}</select></label><label>Explicit exclusions<textarea data-scope="exclusions">${esc(d.scope.exclusions)}</textarea></label></div></section>
 <section class="panel"><h3>Requirement → score → case → reference trace</h3><p class="muted">Importance labels do not generate weights. Every material requirement needs a semantic binding, agreed exclusion, or visible gap.</p><div class="form-grid"><label>Requirement ID<input id="req-id" placeholder="REQ-1"></label><label>Source reference<input id="req-source"></label><label>Requirement role<select id="req-kind">${["MATERIAL", "PREFERENCE", "CONSTRAINT", "EXCLUSION"].map((x) => option(x, x)).join("")}</select></label><label>Agreement status<select id="req-agreement">${["CLIENT_ASSERTION", "ANALYST_PROPOSAL", "CLIENT_CONFIRMED", "SCOPED_EXCLUSION"].map((x) => option(x, x)).join("")}</select></label><label class="span-all">Original words<textarea id="req-words"></textarea></label><label class="span-all">Decision consequence<textarea id="req-consequence"></textarea></label></div><button id="add-requirement">Add requirement</button>${d.requirements.length ? `<div class="scroll"><table><thead><tr><th>ID / role</th><th>Original words</th><th>Consequence</th><th>Agreement</th></tr></thead><tbody>${d.requirements.map((x) => `<tr><td>${esc(x.requirement_id)} · ${esc(x.kind)}</td><td>${esc(x.original_words)}</td><td>${esc(x.decision_consequence)}</td><td>${esc(x.agreement_status)}</td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No requirement trace yet.</p>'}<details open><summary>Add measurement/score binding</summary><div class="form-grid"><label>Requirement<select id="trace-req"><option value="">Choose</option>${reqOptions}</select></label><label>Role<select id="trace-role">${G.ROLES.map((x) => option(x, x)).join("")}</select></label><label>Observable<input id="trace-observable"></label><label>Requested output<input id="trace-output"></label><label>Measurement definition<textarea id="trace-measure"></textarea></label><label>Numerical method<textarea id="trace-method"></textarea></label><label>Normalization / floor<input id="trace-floor" placeholder="Keep unresolved if not owner-supplied"></label><label>Authoring binding<input id="trace-binding" placeholder="Exact native ID or named gap"></label></div><button id="add-trace">Add trace binding</button></details>${d.traces.length ? `<div class="scroll"><table><thead><tr><th>Requirement</th><th>Observable/output</th><th>Role</th><th>Binding/gap</th></tr></thead><tbody>${d.traces.map((x) => `<tr><td>${esc(x.requirement_id)}</td><td>${esc(x.observable)} → ${esc(x.requested_output)}</td><td>${esc(x.role)}</td><td>${esc(x.authoring_binding || x.gap || "gap")}</td></tr>`).join("")}</tbody></table></div>` : ""}<details><summary>Add target-population / case-family proposal</summary><div class="form-grid"><label>Case family ID<input id="case-id" placeholder="CASE-1"></label><label>Evidence role<select id="case-role">${G.CASE_ROLES.map((x) => option(x, x)).join("")}</select></label><label>Requirements (comma-separated IDs)<input id="case-requirements"></label><label>Support status<select id="case-support">${["UNASSESSED", "PROPOSED", "SOURCE_SUPPORTED", "GAP"].map((x) => option(x, x)).join("")}</select></label><label>Target population<textarea id="case-population"></textarea></label><label>Target mass / importance<textarea id="case-mass"></textarea></label><label>Sampling frequency<textarea id="case-frequency"></textarea></label><label>Analysis weight<textarea id="case-weight"></textarea></label><label>Independent physical cases<input id="case-physical-count"></label><label>Reconstruction replicas<input id="case-replicas"></label><label>Generator/source contract<input id="case-generator"></label><label>Why this family exists<textarea id="case-rationale"></textarea></label></div><button id="add-case">Add case family</button></details>${d.cases.length ? `<div class="scroll"><table><thead><tr><th>Case / role</th><th>Population and sample</th><th>Requirements</th><th>Generator / support</th></tr></thead><tbody>${d.cases.map((x) => `<tr><td>${esc(x.case_family_id)} · ${esc(x.role)}</td><td>${esc(x.target_population || "unresolved")} · sample ${esc(x.sampling_frequency || "unresolved")} · weight ${esc(x.analysis_weight || "unresolved")}</td><td>${esc(x.requirement_ids.join(", ") || "none")}</td><td>${esc(x.generator_ref || "gap")} · ${esc(x.support_status)}</td></tr>`).join("")}</tbody></table></div>` : ""}<p><strong>Trace diagnostic:</strong> ${esc(cov.status)}. Missing requirements: ${esc(cov.missing_requirements.join(", ") || "none")}. Unresolved floors: ${esc(cov.unresolved_floors.join(", ") || "none")}. Population/sampling questions: ${esc(cov.population_sampling_weighting_questions.join(", ") || "none")}.</p><div class="form-grid"><label>Mandatory physical admissibility<textarea data-score="mandatory_gate_summary">${esc(d.score_plan.mandatory_gate_summary)}</textarea></label><label>Soft scientific estimand<textarea data-score="soft_estimand">${esc(d.score_plan.soft_estimand)}</textarea></label><label>Training objective — separate<textarea data-score="training_objective">${esc(d.score_plan.training_objective)}</textarea></label><label>Miner reward accounting — separate<textarea data-score="reward_accounting">${esc(d.score_plan.reward_accounting)}</textarea></label><label>Deployed-system acceptance<textarea data-score="deployment_acceptance">${esc(d.score_plan.deployment_acceptance)}</textarea></label><label>Unresolved trade-offs<textarea data-score="unresolved_tradeoffs">${esc(d.score_plan.unresolved_tradeoffs)}</textarea></label></div><details><summary>Reference role and evidence envelope</summary><div class="form-grid"><label>Equation / physical law<textarea data-reference="equation">${esc(d.reference_plan.equation)}</textarea></label><label>Reference role<input data-reference="role" value="${esc(d.reference_plan.role)}"></label><label>Method<textarea data-reference="method">${esc(d.reference_plan.method)}</textarea></label><label>Configuration<textarea data-reference="configuration">${esc(d.reference_plan.configuration)}</textarea></label><label>Convergence evidence<textarea data-reference="convergence_evidence">${esc(d.reference_plan.convergence_evidence)}</textarea></label><label>Uncertainty evidence<textarea data-reference="uncertainty_evidence">${esc(d.reference_plan.uncertainty_evidence)}</textarea></label><label>Applicable envelope<textarea data-reference="applicable_envelope">${esc(d.reference_plan.applicable_envelope)}</textarea></label><label>Failures retained<textarea data-reference="failures">${esc(d.reference_plan.failures)}</textarea></label><label>Cost scope<textarea data-reference="cost_scope">${esc(d.reference_plan.cost_scope)}</textarea></label><label>Correlation / independence limits<textarea data-reference="independence_limitations">${esc(d.reference_plan.independence_limitations)}</textarea></label></div></details><details><summary>Prospective behavior checks</summary><div class="card-grid">${G.DIAGNOSTIC_EXAMPLES.map(
   (x) => {
     const r = G.prospectivePreferenceDiagnostic(x);
     return `<article class="card"><strong>${esc(x.replaceAll("_", " "))}</strong><p>${esc(r.expected_relation)}</p><small>${esc(r.numerical_execution)} · ${esc(r.limitation)}</small></article>`;
   },
 ).join(
   "",
 )}</div><p><button id="download-diagnostic">Export source-owner diagnostic request</button> This download does not execute the official scorer.</p></details></section>
 <section class="panel"><div class="eyebrow">Same proposed exam</div><h3>CPES protection & conditional reference economics</h3><div class="baseline-strip"><strong>Retain Variant A in DEVELOPMENT</strong><span>B is non-activating conditional research; C is sensitivity only. Repeated precise hidden-bank feedback is a vulnerable control.</span></div><details><summary>P1–P8 design-bound controls</summary><p class="muted">A complete packet can still be blocked. These planning states do not qualify a control.</p><div class="form-grid">${G.CONTROLS.map((id) => `<label>${id} review state<select data-control="${id}">${["UNASSESSED", "ASSEMBLED_FOR_REVIEW", "BLOCKED"].map((x) => option(x, x, d.cpes.protection.controls[id].state)).join("")}</select></label>`).join("")}</div></details><p><strong>Five unresolved claims:</strong> ${G.BLOCKERS.join(", ")}. Applicability is scope-specific and user notes cannot clear authority.</p><div class="form-grid">${G.BLOCKERS.map((id) => `<label>${id} applicability<select data-blocker="${id}">${["UNKNOWN", "APPLICABLE", "NOT_APPLICABLE_USER_ASSERTION"].map((x) => option(x, x, d.cpes.protection.blockers[id].applicability)).join("")}</select></label>`).join("")}</div><h3 class="section-title">Fixed homogeneous group scenario</h3><div class="form-grid"><label>Reference work R<input data-econ="reference_work" value="${esc(econ.reference_work)}"></label><label>R status<select data-econ="reference_status">${F.QUANTITY_STATUS.map((x) => option(x, x, econ.reference_status)).join("")}</select></label><label>B overhead H<input data-econ="group_overhead" value="${esc(econ.group_overhead)}"></label><label>H status<select data-econ="overhead_status">${F.QUANTITY_STATUS.map((x) => option(x, x, econ.overhead_status)).join("")}</select></label><label>Compatible group size b<input data-econ="group_size" value="${esc(econ.group_size)}"></label><label>b status<select data-econ="group_size_status">${F.QUANTITY_STATUS.map((x) => option(x, x, econ.group_size_status)).join("")}</select></label><label>Matched unit<select data-econ="unit">${F.ECON_UNITS.map((x) => option(x, x || "unknown", econ.unit)).join("")}</select></label><label>Scope<input data-econ="unit_scope" value="${esc(econ.unit_scope)}"></label><label>Compatible dispatch demand<select data-econ="compatible_demand_status">${F.QUANTITY_STATUS.map((x) => option(x, x, econ.compatible_demand_status)).join("")}</select></label><label>Compatible-demand source<input data-econ="compatible_demand_source" value="${esc(econ.compatible_demand_source)}"></label><label>Evidence field-dependence<select data-econ="field_dependent">${["UNKNOWN", "YES", "NO"].map((x) => option(x, x, econ.field_dependent)).join("")}</select></label><label>Completed comparisons<input data-econ="completed_comparisons" value="${esc(econ.completed_comparisons)}"></label><label>Offered requests<input data-econ="offered_requests" value="${esc(econ.offered_requests)}"></label><label>Unresolved / censored work<input data-econ="unresolved_or_censored" value="${esc(econ.unresolved_or_censored)}"></label><label>Upfront implementation / qualification cost<input data-econ="upfront_cost" value="${esc(econ.upfront_cost)}"></label><label>Upfront duration<input data-econ="upfront_duration" value="${esc(econ.upfront_duration)}"></label><label>Upfront risk<input data-econ="upfront_risk" value="${esc(econ.upfront_risk)}"></label></div><div id="goal-economics-result"></div></section>
 <section class="panel"><div class="eyebrow">Native authoring</div><h3>Compile with intent comparison, or request the missing capability</h3><p>${esc(G.compatibility(d).reason)}</p><div class="actions"><button id="prepare-authoring">Prepare authoring request</button><button id="download-authoring" ${lastAuthoringRequest ? "" : "disabled"}>Download request</button><button id="import-authoring">Import native result</button></div><pre id="authoring-preview">${esc(JSON.stringify(d.authoring.semantic_receipt || d.authoring.extension_request || { status: "NOT_PREPARED" }, null, 2))}</pre><small>Engineering command: <code>python3 tools/authoring_bridge.py REQUEST.json OUTPUT_DIRECTORY</code>. The fixed bridge invokes the installed source-owned CLI; the browser never executes Python or a solver.</small></section>
 <section class="panel"><div class="eyebrow">Execution / Decision</div><h3>Bidirectional handoff</h3><div class="form-grid"><label>Recipient<select id="handoff-recipient">${["S1", "R1", "OWNER_DECISION", "EXECUTOR", "LAUNCH_OWNER", "N1"].map((x) => option(x, x)).join("")}</select></label><label>One question<input id="handoff-question" value="What exact observation or owner decision changes the next scoped decision?"></label><label>Required output<textarea id="handoff-output">Return a response bound to this job, design revision, request ID, source owner, limitations, and artifact digest.</textarea></label><label>Stop condition<textarea id="handoff-stop">Stop after one response or a precise blocker; reopen only on the named dependency event.</textarea></label></div><div class="actions"><button id="prepare-handoff">Prepare request</button><button id="import-response">Import response</button></div>${d.handoffs.length ? `<div class="scroll"><table><thead><tr><th>Request</th><th>Recipient</th><th>Route/status</th><th>Question</th><th>Action</th></tr></thead><tbody>${d.handoffs.map((x) => `<tr><td>${esc(x.request_id)}</td><td>${esc(x.recipient)}</td><td>${esc(x.route)} / ${esc(x.status)}</td><td>${esc(x.question)}</td><td><button data-export-handoff="${esc(x.request_id)}">Export</button></td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No handoff prepared.</p>'}<h3 class="section-title">Launch-candidate projection</h3><p><strong>${esc(launch.status)}</strong> · native interface ${esc(launch.native_launch_interface)}.</p><ul>${launch.remaining_decisions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><div class="actions"><button id="export-client">Client summary</button><button id="export-engineering">Engineering packet</button><button id="export-n1">N1 account view</button><button id="export-launch">Launch-candidate manifest</button><button disabled>Send / launch unavailable</button></div><details><summary>C-PILOT-01 operating projection</summary><pre>${esc(JSON.stringify(G.cPilotProjection(), null, 2))}</pre></details></section></div></div>`;
    document.querySelectorAll("[data-job-select]").forEach(
      (e) =>
        (e.onclick = () => {
          jobId = e.dataset.jobSelect;
          const selectedJob = W.jobs.find((x) => x.job_id === jobId);
          designId =
            selectedJob.working_design_id || selectedJob.designs[0].design_id;
          selectedJob.working_design_id = designId;
          lastAuthoringRequest = null;
          render();
        }),
    );
    $("design-select").onchange = (e) => {
      designId = e.target.value;
      j.working_design_id = designId;
      lastAuthoringRequest = null;
      render();
    };
    $("new-job").onclick = createJob;
    $("export-goal").onclick = () =>
      download("Carbon_Goal_Workbench_v0.10_PHYSICAL_CHECK.json", workspace());
    $("import-goal").onclick = () => $("goal-workspace-file").click();
    bindIntakePreview();
    $("link-atlas").onclick = () => {
      j.source_opportunity_id = H.selectedOpportunity();
      notify("Linked optional source opportunity as context only.");
      render();
    };
    $("new-alternative").onclick = () => {
      const n = j.designs.length + 1,
        nd = G.newDesign(
          j.job_id,
          j.job_id + "-design-" + n,
          1,
          null,
          "Alternative " + n,
        );
      j.designs.push(nd);
      designId = nd.design_id;
      j.working_design_id = designId;
      lastAuthoringRequest = null;
      render();
    };
    $("revise-design").onclick = () => {
      try {
        const nd = G.reviseDesign(
          j,
          d.design_id,
          d.design_id + "-r" + (d.revision + 1),
        );
        designId = nd.design_id;
        lastAuthoringRequest = null;
        render();
      } catch (e) {
        notify(e.message);
      }
    };
    $("burgers-demo").onclick = () => {
      if (d.status !== "DRAFT") return notify("Create a revision first.");
      const hadEvidence =
        d.evidence_bindings.length > 0 || d.measurement_evidence.length > 0;
      d.scope.physics_family = "periodic_viscous_burgers_1d_v1";
      d.scope.requested_goal = "Dynamics";
      d.scope.intended_use =
        "Use the source-owned public DEVELOPMENT Burgers benchmark to test an exact goal-to-Challenge handoff without customer, production, or qualification claims.";
      d.scope.inputs =
        "Finite Fourier initial field, positive viscosity, requested times, and declared periodic domain length";
      d.scope.outputs =
        "Complete field evolution with compression, dissipation and half-time diagnostics";
      d.scope.units =
        "Source-defined nondimensional Burgers variables and declared characteristic scales";
      d.scope.geometry = "One-dimensional periodic domain";
      d.scope.conditions =
        "Periodic boundary; unforced; finite Fourier initial condition; positive viscosity";
      d.scope.regime = "Twelve source-defined public DEVELOPMENT cells";
      d.scope.query_workload =
        "Source-defined TRAIN/EVAL/STRESS finite campaign only";
      d.scope.turnaround = "No customer service limit established";
      d.scope.exclusions =
        "No industrial/customer validation; no protected evaluation; no launch";
      d.scope.rights_scope = "SYNTHETIC_INTERNAL";
      d.authoring.template_id = "periodic_viscous_burgers_1d_v1";
      d.authoring.requested_goal = "Dynamics";
      d.requirements = [
        G.requirement(
          "REQ-DYNAMICS",
          "Predict complete field evolution; mandatory physical failures cannot be offset by favorable average error.",
          "Synthetic public demonstration",
          "Decide whether the source-owned Dynamics template preserves this bounded intent",
          "MATERIAL",
        ),
      ];
      const t = G.trace("TRACE-DYNAMICS", "REQ-DYNAMICS");
      Object.assign(t, {
        observable:
          "field, maximum compression, peak dissipation, energy half-time",
        requested_output: "complete periodic trajectory",
        measurement_definition: "source-owned Burgers measurement proposal",
        numerical_method: "source-owned C-AUTH1/C-05 definitions",
        role: "MANDATORY",
        normalization: "source-owned exact template values",
        floor: "source-owned fixed DEVELOPMENT floors",
        aggregation: "source-owned proposal; no customer-approved trade-off",
        uncertainty: "C-05 scientific limits and uncertainty remain unresolved",
        population_ref: "goal_burgers_12cell_v1",
        stratum_ref: "12 public DEVELOPMENT cells",
        finite_case_coverage: "TRAIN/EVAL/STRESS roles remain disjoint",
        reference_requirement:
          "primary plus independent development witness, not qualified",
        authoring_binding: "carbon.goal-authoring-proposal/1",
      });
      d.traces = [t];
      const c = G.caseFamily("BURGERS-12-CELL", "EVAL");
      Object.assign(c, {
        requirement_ids: ["REQ-DYNAMICS"],
        target_population:
          "source-defined synthetic periodic Burgers population",
        target_mass: "1/12 per cell",
        sampling_frequency: "4 parents per EVAL cell",
        analysis_weight: "population mass distinct from sampling frequency",
        independent_physical_cases: "48 EVAL parents in fixed template",
        reconstruction_replicas: "separate from physical case count",
        generator_ref: "goal_burgers_12cell_v1",
        rationale: "Covers declared amplitude, shape and viscosity cells",
        support_status: "SOURCE_SUPPORTED",
      });
      d.cases = [c];
      Object.assign(d.score_plan, {
        mandatory_gate_summary:
          "Source mandatory physics gates precede quality ranking",
        soft_estimand:
          "Source population-weighted mean and worst-cell CVaR DEVELOPMENT proposal",
        training_objective:
          "Candidate training remains separate from official measurement and score",
        reward_accounting: "SEPARATE_UNRESOLVED",
        deployment_acceptance:
          "No customer deployment acceptance is established",
        unresolved_tradeoffs:
          "Qualified limits, floors and customer trade-offs remain HUMAN_INPUT",
      });
      Object.assign(d.reference_plan, {
        equation: "Periodic unforced viscous Burgers equation from C-AUTH1",
        role: "Candidate primary plus independent DEVELOPMENT witness",
        method: "Source-owned C-04 reference interfaces",
        configuration: "Exact registered DEVELOPMENT template only",
        convergence_evidence:
          "Unqualified development evidence; see native source",
        uncertainty_evidence: "Qualified limits remain HUMAN_INPUT",
        applicable_envelope: "Synthetic periodic Burgers development cells",
        failures:
          "Failed reference cases remain separate from candidate failure",
        cost_scope:
          "Reference work not measured by this demo; R=40 below is user-assumed synthetic work",
        independence_limitations:
          "Shared assumptions and correlations remain explicit",
      });
      Object.assign(d.cpes.economics, {
        reference_work: "40",
        reference_status: "user_assumed",
        group_overhead: "4",
        overhead_status: "user_assumed",
        group_size: "3",
        group_size_status: "user_assumed",
        unit: "synthetic work units",
        unit_scope: "one unchanged adequate reference pack",
        compatible_demand_status: "unknown",
        field_dependent: "UNKNOWN",
        completed_comparisons: "3",
        offered_requests: "3",
        unresolved_or_censored: "0",
      });
      if (hadEvidence)
        for (const field of [
          "physics_family",
          "requested_goal",
          "intended_use",
          "inputs",
          "outputs",
          "units",
          "geometry",
          "conditions",
          "regime",
          "query_workload",
          "turnaround",
          "exclusions",
          "rights_scope",
          "requirements",
          "traces",
          "cases",
          "score",
          "reference",
        ])
          G.recordImpact(
            d,
            field,
            "Public Burgers demonstration replaced this design field",
          );
      render();
    };
    $("add-requirement").onclick = () => {
      try {
        if (d.status !== "DRAFT")
          throw Error("Sealed design is immutable; create a revision.");
        const r = G.requirement(
          $("req-id").value,
          $("req-words").value,
          $("req-source").value,
          $("req-consequence").value,
          $("req-kind").value,
        );
        r.agreement_status = $("req-agreement").value;
        d.requirements.push(r);
        G.recordImpact(d, "requirements", "Requirement added");
        render();
      } catch (e) {
        notify(e.message);
      }
    };
    $("add-trace").onclick = () => {
      try {
        if (d.status !== "DRAFT")
          throw Error("Sealed design is immutable; create a revision.");
        const t = G.trace(
          "TRACE-" + (d.traces.length + 1),
          $("trace-req").value,
        );
        Object.assign(t, {
          observable: $("trace-observable").value,
          requested_output: $("trace-output").value,
          measurement_definition: $("trace-measure").value,
          numerical_method: $("trace-method").value,
          role: $("trace-role").value,
          floor: $("trace-floor").value,
          authoring_binding: $("trace-binding").value,
          gap: $("trace-binding").value ? "" : "Authoring binding unresolved",
        });
        d.traces.push(t);
        G.recordImpact(d, "traces", "Requirement trace added");
        render();
      } catch (e) {
        notify(e.message);
      }
    };
    $("add-case").onclick = () => {
      try {
        if (d.status !== "DRAFT")
          throw Error("Sealed design is immutable; create a revision.");
        const c = G.caseFamily($("case-id").value, $("case-role").value);
        Object.assign(c, {
          requirement_ids: $("case-requirements")
            .value.split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          target_population: $("case-population").value,
          target_mass: $("case-mass").value,
          sampling_frequency: $("case-frequency").value,
          analysis_weight: $("case-weight").value,
          independent_physical_cases: $("case-physical-count").value,
          reconstruction_replicas: $("case-replicas").value,
          generator_ref: $("case-generator").value,
          rationale: $("case-rationale").value,
          support_status: $("case-support").value,
        });
        G.validateDesign({ ...d, cases: [...d.cases, c] }, d.job_id);
        d.cases.push(c);
        G.recordImpact(
          d,
          "population",
          "Case-family proposal added or changed",
        );
        render();
      } catch (e) {
        notify(e.message);
      }
    };
    $("download-diagnostic").onclick = () =>
      download(
        "diagnostic-" + d.design_id + "-r" + d.revision + ".json",
        G.diagnosticRequest(d, "diagnostic-" + d.design_id + "-r" + d.revision),
      );
    $("prepare-authoring").onclick = () => {
      try {
        lastAuthoringRequest = G.authoringRequest(
          d,
          "author-" + d.design_id + "-r" + d.revision,
        );
        $("authoring-preview").textContent = JSON.stringify(
          lastAuthoringRequest.route === "LOCAL_FIXED_CLI"
            ? lastAuthoringRequest
            : d.authoring.extension_request,
          null,
          2,
        );
        $("download-authoring").disabled = false;
        notify(
          lastAuthoringRequest.route === "LOCAL_FIXED_CLI"
            ? "Bounded local CLI request prepared."
            : "Source-owner extension request prepared; client intent preserved.",
        );
      } catch (e) {
        notify(e.message);
      }
    };
    $("download-authoring").onclick = () => {
      if (lastAuthoringRequest)
        download(
          lastAuthoringRequest.request_id + ".json",
          lastAuthoringRequest,
        );
    };
    $("import-authoring").onclick = () => $("authoring-result-file").click();
    $("prepare-handoff").onclick = () => {
      try {
        const id = "handoff-" + d.design_id + "-" + (d.handoffs.length + 1),
          h = G.handoff(d, {
            request_id: id,
            recipient: $("handoff-recipient").value,
            lead: j.lead,
            question: $("handoff-question").value,
            required_output: $("handoff-output").value,
            permitted_data: "Public-safe high-level planning record only",
            rights: j.assignment.rights_summary,
            required_authority: "Source owner must retain its native authority",
            allowance: j.assignment.allowances,
            stop_condition: $("handoff-stop").value,
            input_refs: [
              d.authoring.result_ref ||
                d.authoring.request_id ||
                "design:" + d.design_id + "@" + d.revision,
            ],
            dependency_owner: $("handoff-recipient").value,
            restart_event: "Named source-owner response for this request",
            native_task_id: j.native_task_id,
            route: "MANUAL",
          });
        notify("Manual request prepared; it has not been sent or executed.");
        render();
      } catch (e) {
        notify(e.message);
      }
    };
    document.querySelectorAll("[data-export-handoff]").forEach(
      (e) =>
        (e.onclick = () => {
          const h = d.handoffs.find(
            (x) => x.request_id === e.dataset.exportHandoff,
          );
          G.markExported(d, h.request_id);
          download(h.request_id + ".json", h);
          render();
        }),
    );
    $("import-response").onclick = () => $("handoff-response-file").click();

    $("export-client").onclick = () =>
      download(safeName(j.job_id) + "_client.json", G.clientProjection(j, d));
    $("export-engineering").onclick = () =>
      download(
        safeName(j.job_id) + "_engineering.json",
        G.engineeringProjection(j, d),
      );
    $("export-n1").onclick = () =>
      download(safeName(j.job_id) + "_n1.json", G.n1Projection(j, d));
    $("export-launch").onclick = () =>
      download(
        safeName(d.design_id) + "_launch_candidate.json",
        G.launchCandidate(d, j.native_task_id),
      );
    bind();
    renderSummary();
  }
  function bindSourceAssessment() {
    const d = design(), prepareButton = $("prepare-source-assessment");
    if (!d || !prepareButton) return;
    prepareButton.onclick = async () => {
      const beforeStatus = d.status;
      try {
        if (d.status === "DRAFT") d.status = "SEALED";
        const request = await S.prepare(
          d,
          "assessment-" + d.design_id + "-r" + d.revision,
        );
        G.validateDesign(d, d.job_id);
        render();
        notify(
          "Exact source-assessment request prepared locally. Nothing was sent or adopted.",
        );
        return request;
      } catch (error) {
        d.status = beforeStatus;
        notify("Source-assessment request rejected: " + error.message);
      }
    };
    $("export-source-assessment").onclick = () => {
      const request = d.source_assessments.requests.find(
        (item) => item.request_id === d.source_assessments.current_request_id,
      );
      if (!request) return notify("Prepare the exact request first.");
      download(safeName(request.request_id) + ".json", request);
      notify("Request exported locally; it was not transmitted.");
    };
    $("import-source-assessment").onclick = () =>
      $("source-assessment-file").click();
  }
  const renderSummaryV04 = renderSummary;
  renderSummary = () => {
    renderSummaryV04();
    bindSourceAssessment();
    bindV05();
    bindTeamReview();
    renderOwnerConsole();
    scientificStudies.mount($("jobs-view"));
  };
  async function digest(raw) {
    if (!crypto?.subtle) return "UNAVAILABLE";
    const b = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(raw),
    );
    return [...new Uint8Array(b)]
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
  }
  $("intake-draft-file").onchange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const before = JSON.stringify(W);
    try {
      if (file.size > 120000) throw Error("Intake draft exceeds 120 KB");
      const raw = new TextDecoder("utf-8", { fatal: true }).decode(
        await file.arrayBuffer(),
      );
      const inspection = await I.inspect(raw, F.strictJsonParse);
      pendingIntake = {
        inspection,
        preview: G.previewIntakeImport(W, inspection),
      };
      render();
      notify("Intake preview prepared. Review it before changing the workspace.");
    } catch (error) {
      if (JSON.stringify(W) !== before)
        throw Error("Atomic intake preview invariant failed");
      notify("Intake preview rejected: " + error.message);
    } finally {
      event.target.value = "";
    }
  };
  $("goal-workspace-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      if (f.size > 2000000) throw Error("Session exceeds 2 MB");
      const raw = await f.text(),
        status =
          (await digest(raw)) === "UNAVAILABLE"
            ? "UNAVAILABLE"
            : "VERIFIED_WEB_CRYPTO",
        next = G.readWorkspace(
          raw,
          (x) =>
            F.readWorkspace(
              x,
              H.atlas().opportunities.map((o) => o.id),
              H.atlas().source.sha256,
            ),
          status,
        );
      for (const importedJob of next.jobs)
        for (const importedDesign of importedJob.designs)
          await S.revalidateState(importedDesign);
      await G.revalidateIntakeRecords(next);
      await G.revalidatePhysicalDefinitionChecks(
        next,
        CarbonScientificStudies,
      );
      G.validateWorkspace(next, (x) =>
        F.readWorkspace(
          x,
          H.atlas().opportunities.map((o) => o.id),
          H.atlas().source.sha256,
        ),
      );
      if (
        (W.jobs.length || H.componentWorkspace().drafts.length) &&
        !confirm("Replace the current in-memory session?")
      )
        return;
      W = next;
      H.installWorkspace(W.opportunity_workspace);
      jobId = W.selected_job_id || W.jobs[0]?.job_id || null;
      const selectedJob = W.jobs.find((x) => x.job_id === jobId);
      designId =
        W.selected_design_id ||
        selectedJob?.working_design_id ||
        selectedJob?.designs[0]?.design_id ||
        null;
      render();
      notify(
        next.migration_receipts.length
          ? "Imported with migration receipt; no authority was promoted."
          : "Imported v0.10 session; intake lineage, physical-definition observations, and privileged derived metadata revalidated.",
      );
    } catch (err) {
      notify("Import rejected: " + err.message);
    } finally {
      e.target.value = "";
    }
  };
  $("c05-evidence-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      if (f.size > 900000) throw Error("C-05 bundle exceeds 900 KB");
      const raw = await f.text();
      if ((await digest(raw)) === "UNAVAILABLE")
        throw Error(
          "Web Crypto is required for exact source digest verification",
        );
      const d = design(),
        request = G.diagnosticRequest(
          d,
          "diagnostic-" + d.design_id + "-r" + d.revision,
        ),
        result = await E.importBundle(d, request, raw, digest);
      G.validateDesign(d, d.job_id);
      render();
      notify(
        result.disposition === "DEDUPLICATED"
          ? "Exact C-05 evidence replay deduplicated."
          : "Source measurement evidence bound; scientific decision remains unresolved.",
      );
    } catch (err) {
      notify(
        err.message.startsWith("SOURCE_MEASUREMENT_EVIDENCE_REJECTED")
          ? err.message
          : "SOURCE_MEASUREMENT_EVIDENCE_REJECTED: " + err.message,
      );
    } finally {
      e.target.value = "";
    }
  };
  $("source-assessment-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const d = design(), before = JSON.stringify(d);
    try {
      if (f.size > 300000) throw Error("Assessment response exceeds 300 KB");
      const result = await S.importResponse(d, await f.text());
      G.validateDesign(d, d.job_id);
      render();
      notify(
        result.status === "DEDUPLICATED"
          ? "Exact admitted assessment replay deduplicated."
          : "Assessment matched the installed repository snapshot; authority effect remains none.",
      );
    } catch (err) {
      Object.assign(d, JSON.parse(before));
      notify("Source-assessment import rejected: " + err.message);
    } finally {
      e.target.value = "";
    }
  };
  $("authoring-result-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      if (f.size > 1500000) throw Error("Authoring result exceeds 1.5 MB");
      if (!lastAuthoringRequest)
        throw Error("Prepare the exact originating request first");
      const value = F.strictJsonParse(await f.text(), {
        maxBytes: 1500000,
        maxDepth: 24,
      });
      G.importAuthoringResult(design(), lastAuthoringRequest, value);
      render();
      notify(
        "Native result bound to this exact design; semantic status recomputed.",
      );
    } catch (err) {
      notify("Authoring result rejected: " + err.message);
    } finally {
      e.target.value = "";
    }
  };
  $("handoff-response-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      if (f.size > 100000) throw Error("Response exceeds 100 KB");
      const value = F.strictJsonParse(await f.text(), {
        maxBytes: 100000,
        maxDepth: 12,
      });
      G.importResponse(design(), value, { trusted: false });
      render();
      notify(
        "Response imported as a scoped assertion; no authority was inferred.",
      );
    } catch (err) {
      notify("Response rejected: " + err.message);
    } finally {
      e.target.value = "";
    }
  };
  document.querySelector('[data-tab="jobs"]').onclick = () => {
    document.querySelectorAll("nav [data-tab]").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === "jobs");
      b.setAttribute(
        "aria-current",
        b.dataset.tab === "jobs" ? "page" : "false",
      );
    });
    document
      .querySelectorAll(".view")
      .forEach((v) => (v.hidden = v.id !== "jobs-view"));
    render();
  };
  document.querySelector('[data-tab="owner-console"]').onclick = () => {
    document.querySelectorAll("nav [data-tab]").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === "owner-console");
      b.setAttribute(
        "aria-current",
        b.dataset.tab === "owner-console" ? "page" : "false",
      );
    });
    document
      .querySelectorAll(".view")
      .forEach((v) => (v.hidden = v.id !== "owner-console-view"));
    renderOwnerConsole();
  };
  render();
  document.querySelector('[data-tab="owner-console"]').click();
})();
