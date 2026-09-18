(function (root) {
  "use strict";

  const QUEUE_STATES = [
    "NEW",
    "READY_FOR_REVIEW",
    "UNDER_REVIEW",
    "NEEDS_CLIENT_CLARIFICATION",
    "READY_FOR_ROUTE",
    "PILOT_BRIEF_READY",
    "HANDOFF_READY",
    "PARKED",
    "CLOSED",
  ];
  const ASSESSMENT_FIELDS = [
    "physical_problem",
    "domain_and_units",
    "operating_envelope",
    "requested_observables",
    "performance_requests",
    "mandatory_physics",
    "optional_objectives",
    "diagnostics",
    "available_data",
    "data_rights_and_provenance",
    "generator_requirements",
    "sampling_requirements",
    "reference_candidates",
    "reference_gaps",
    "measurement_requirements",
    "uncertainty_requirements",
    "acceptance_rule_requirements",
    "implementation_work",
    "dependencies",
    "smallest_useful_pilot",
    "stop_conditions",
  ];
  const clone = (value) => JSON.parse(JSON.stringify(value));

  function text(value, label, maximum = 8000) {
    if (typeof value !== "string" || value.length > maximum)
      throw Error("Invalid " + label);
    return value;
  }
  function exact(value, keys, label) {
    const prototype = value && Object.getPrototypeOf(value);
    if (!value || (prototype !== Object.prototype && prototype !== null))
      throw Error(label + " must be an object");
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    if (
      actual.length !== expected.length ||
      actual.some((key, index) => key !== expected[index])
    )
      throw Error(label + " has unsupported or missing fields");
    return value;
  }
  function identifier(value, label) {
    if (
      typeof value !== "string" ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)
    )
      throw Error("Invalid " + label);
    return value;
  }
  function list(value, label, maximum = 128) {
    if (!Array.isArray(value) || value.length > maximum)
      throw Error("Invalid " + label);
    return value;
  }

  function newTeamReview() {
    return {
      schema_version: "carbon.goal-workbench.team-review.v1",
      queue_state: "NEW",
      assigned_reviewer: "",
      original_statement_corrections: [],
      assessment_notes: [],
      outstanding_questions: [],
      service_receipts: [],
      current_action: "Review the imported brief and assign one reviewer.",
      next_restart_event: "A reviewer is assigned or a client clarification arrives.",
      provenance: "WORKBENCH_DERIVED",
    };
  }

  function newAssessment() {
    const result = {
      schema_version: "carbon.goal-workbench.team-assessment.v1",
      intended_engineering_decision: "",
    };
    for (const field of ASSESSMENT_FIELDS) result[field] = "";
    result.resource_scenarios = [];
    result.work_packages = [];
    result.open_questions = [];
    result.scientific_task_dependencies = [
      {
        task_kind: "PHYSICAL_DEFINITION_CHECK",
        availability: "CORE_INTERFACE_PENDING",
        exact_design_binding: "",
        note: "Issue #209 C-CORE-02 is accepted; use it only through the pending C-CORE-04 Workbench adapter. No local runner is implied.",
      },
      {
        task_kind: "OPERATING_ENVELOPE_EXPLORATION",
        availability: "CORE_INTERFACE_PENDING",
        exact_design_binding: "",
        note: "Synthetic contract placeholder only until the C-CORE-04 Workbench adapter is accepted.",
      },
      {
        task_kind: "REFERENCE_FEASIBILITY_AND_COST",
        availability: "CORE_INTERFACE_PENDING",
        exact_design_binding: "",
        note: "No reference execution, cost result, or scientific conclusion is claimed.",
      },
    ];
    return result;
  }

  function validateTeamReview(value) {
    exact(
      value,
      [
        "schema_version",
        "queue_state",
        "assigned_reviewer",
        "original_statement_corrections",
        "assessment_notes",
        "outstanding_questions",
        "service_receipts",
        "current_action",
        "next_restart_event",
        "provenance",
      ],
      "team review",
    );
    if (value.schema_version !== "carbon.goal-workbench.team-review.v1")
      throw Error("Unsupported team-review version");
    if (!QUEUE_STATES.includes(value.queue_state))
      throw Error("Invalid intake queue state");
    text(value.assigned_reviewer, "assigned reviewer", 300);
    list(value.original_statement_corrections, "corrections", 128).forEach(
      (item) => {
        exact(
          item,
          ["correction_id", "field", "original", "corrected", "reason", "recorded_by"],
          "correction",
        );
        identifier(item.correction_id, "correction ID");
        text(item.field, "correction field", 300);
        text(item.original, "original statement");
        text(item.corrected, "corrected statement");
        text(item.reason, "correction reason", 1000);
        text(item.recorded_by, "correction recorder", 300);
      },
    );
    for (const [key, maximum] of [
      ["assessment_notes", 256],
      ["outstanding_questions", 128],
    ])
      list(value[key], key, maximum).forEach((item) => {
        exact(item, ["record_id", "text", "recorded_by", "provenance"], key.slice(0, -1));
        identifier(item.record_id, key + " record ID");
        text(item.text, key + " text");
        text(item.recorded_by, key + " recorder", 300);
        if (item.provenance !== "LOCAL_MANUAL_ASSERTION")
          throw Error("Manual review records cannot claim native provenance");
      });
    list(value.service_receipts, "service receipts", 64).forEach((item) => {
      exact(
        item,
        ["receipt_id", "inquiry_id", "revision", "raw_sha256", "status", "observed_by"],
        "service receipt",
      );
      identifier(item.receipt_id, "receipt ID");
      identifier(item.inquiry_id, "inquiry ID");
      if (!Number.isSafeInteger(item.revision) || item.revision < 1)
        throw Error("Invalid receipt revision");
      if (!/^sha256:[0-9a-f]{64}$/.test(item.raw_sha256))
        throw Error("Invalid receipt digest");
      if (item.status !== "PERSISTED_PRIVATE_SYNTHETIC")
        throw Error("Unsupported service receipt status");
      text(item.observed_by, "receipt observer", 300);
    });
    text(value.current_action, "current action", 2000);
    text(value.next_restart_event, "restart event", 2000);
    if (!["WORKBENCH_DERIVED", "LOCAL_MANUAL_ASSERTION", "IMPORTED_PRIVATE_RECEIPT"].includes(value.provenance))
      throw Error("Invalid team-review provenance");
    return clone(value);
  }

  function validateAssessment(value, design) {
    exact(
      value,
      [
        "schema_version",
        "intended_engineering_decision",
        ...ASSESSMENT_FIELDS,
        "resource_scenarios",
        "work_packages",
        "open_questions",
        "scientific_task_dependencies",
      ],
      "team assessment",
    );
    if (value.schema_version !== "carbon.goal-workbench.team-assessment.v1")
      throw Error("Unsupported team-assessment version");
    text(value.intended_engineering_decision, "assessment intended decision");
    for (const field of ASSESSMENT_FIELDS)
      text(value[field], "assessment " + field);
    list(value.resource_scenarios, "resource scenarios", 32).forEach((item) => {
      exact(item, ["scenario_id", "description", "assumptions", "cost", "duration", "status"], "resource scenario");
      identifier(item.scenario_id, "resource scenario ID");
      for (const key of ["description", "assumptions", "cost", "duration"])
        text(item[key], "resource scenario " + key, 2000);
      if (item.status !== "ASSUMPTION_ONLY") throw Error("Resource scenario cannot claim measured status");
    });
    list(value.work_packages, "work packages", 64).forEach((item) => {
      exact(item, ["work_package_id", "title", "owner", "required_output", "stop_condition", "dependency"], "work package");
      identifier(item.work_package_id, "work package ID");
      for (const key of ["title", "owner", "required_output", "stop_condition", "dependency"])
        text(item[key], "work package " + key, 2000);
    });
    list(value.open_questions, "assessment open questions", 128).forEach((item) => text(item, "assessment open question", 2000));
    list(value.scientific_task_dependencies, "scientific task dependencies", 16).forEach((item) => {
      exact(item, ["task_kind", "availability", "exact_design_binding", "note"], "scientific task dependency");
      if (!["PHYSICAL_DEFINITION_CHECK", "OPERATING_ENVELOPE_EXPLORATION", "REFERENCE_FEASIBILITY_AND_COST"].includes(item.task_kind))
        throw Error("Unknown scientific task kind");
      if (!["CORE_INTERFACE_PENDING", "AVAILABLE_NOT_REQUESTED", "REQUEST_PREPARED", "RETURNED", "FAILED", "CANCELLED", "STALE"].includes(item.availability))
        throw Error("Invalid scientific task availability");
      text(item.exact_design_binding, "scientific task binding", 300);
      text(item.note, "scientific task note", 2000);
      if (item.exact_design_binding && item.exact_design_binding !== design.design_id + "@" + design.revision)
        throw Error("Scientific task binding is stale or for another design");
    });
    return clone(value);
  }

  function addCorrection(review, input) {
    validateTeamReview(review);
    const record = {
      correction_id: identifier(input.correction_id, "correction ID"),
      field: text(input.field, "correction field", 300),
      original: text(input.original, "original statement"),
      corrected: text(input.corrected, "corrected statement"),
      reason: text(input.reason || "", "correction reason", 1000),
      recorded_by: text(input.recorded_by, "correction recorder", 300),
    };
    if (review.original_statement_corrections.some((item) => item.correction_id === record.correction_id))
      throw Error("Duplicate correction identity");
    review.original_statement_corrections.push(record);
    review.provenance = "LOCAL_MANUAL_ASSERTION";
    return record;
  }

  function addManualRecord(review, collection, input) {
    if (!["assessment_notes", "outstanding_questions"].includes(collection))
      throw Error("Unsupported review collection");
    const record = {
      record_id: identifier(input.record_id, "review record ID"),
      text: text(input.text, "review record text"),
      recorded_by: text(input.recorded_by, "review record author", 300),
      provenance: "LOCAL_MANUAL_ASSERTION",
    };
    if (review[collection].some((item) => item.record_id === record.record_id))
      throw Error("Duplicate review record identity");
    review[collection].push(record);
    review.provenance = "LOCAL_MANUAL_ASSERTION";
    return record;
  }

  function queueProjection(job, design) {
    const brief = job.assignment || {};
    const missing = [];
    for (const [label, value] of [
      ["engineering decision", brief.intended_decision],
      ["current model or baseline", brief.credible_baseline],
      ["operating conditions", design.scope.conditions],
      ["requested outputs", design.scope.outputs],
      ["reference evidence", design.reference_plan.method],
    ]) if (!value) missing.push(label);
    for (const item of job.team_review.outstanding_questions)
      if (!missing.includes(item.text)) missing.push(item.text);
    return {
      job_id: job.job_id,
      title: job.title,
      objective: brief.intended_decision || brief.client_words || "unknown",
      current_workflow: brief.credible_baseline || "unknown",
      operating_conditions: design.scope.conditions || "unknown",
      requested_outputs: design.scope.outputs || "unknown",
      reference_evidence: design.reference_plan.method || "unknown",
      missing_information: missing,
      assigned_reviewer: job.team_review.assigned_reviewer,
      queue_state: job.team_review.queue_state,
      next_action: job.team_review.current_action,
      provenance: job.team_review.provenance,
    };
  }

  function clientPilotBrief(job, design) {
    return {
      schema_version: "carbon.goal-workbench.client-pilot-brief.v1",
      label: "Draft pilot for Carbon review",
      job_id: job.job_id,
      design_id: design.design_id,
      design_revision: design.revision,
      problem_to_investigate: design.assessment.intended_engineering_decision || job.assignment.intended_decision,
      proposed_scope: design.assessment.smallest_useful_pilot || design.scope.intended_use,
      operating_conditions: design.assessment.operating_envelope || design.scope.conditions,
      requested_outputs: design.assessment.requested_observables || design.scope.outputs,
      evidence_carbon_could_provide: design.assessment.measurement_requirements,
      client_inputs_needed: design.assessment.available_data,
      assumptions_and_exclusions: [design.scope.exclusions, design.assessment.open_questions.join("; ")].filter(Boolean).join("; "),
      open_questions: clone(design.assessment.open_questions),
      next_discussion: design.route_plan.next_decision || job.assignment.next_owner_decision,
      authority: "Draft scope only. Client review confirms the brief, not feasibility, scientific adequacy, price, speedup, execution, rights, qualification, or launch.",
    };
  }

  function internalExecutionBrief(job, design) {
    return {
      schema_version: "carbon.goal-workbench.internal-execution-brief.v1",
      job_id: job.job_id,
      design_id: design.design_id,
      design_revision: design.revision,
      route: design.route_plan.route,
      physical_definition: clone(design.scope),
      assessment: clone(design.assessment),
      requirement_ids: design.requirements.map((item) => item.requirement_id),
      case_family_ids: design.cases.map((item) => item.case_family_id),
      reference_plan: clone(design.reference_plan),
      evidence_binding_ids: design.evidence_bindings.map((item) => item.evidence_binding_id),
      handoff_bindings: design.handoffs.map((item) => ({ request_id: item.request_id, status: item.status })),
      unresolved_decisions: [
        ...design.assessment.open_questions,
        ...design.evidence_bindings.flatMap((item) => [
          ...item.scientific_review_reasons.map((reason) => reason.reason_id),
          ...item.rights_review_reasons.map((reason) => reason.reason_id),
        ]),
      ],
      authority: "Internal preparation only. Shared core tasks remain unavailable unless their accepted interface and grant are present. No execution or scientific authority is created.",
    };
  }

  const api = {
    QUEUE_STATES,
    ASSESSMENT_FIELDS,
    newTeamReview,
    newAssessment,
    validateTeamReview,
    validateAssessment,
    addCorrection,
    addManualRecord,
    queueProjection,
    clientPilotBrief,
    internalExecutionBrief,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonTeamReview = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
