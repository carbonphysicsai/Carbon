/* Pure GOAL-WORKBENCH-05 routing, applicability, and owner-console engine. */
(function (root) {
  "use strict";

  const ROUTES = [
    "UNASSESSED",
    "USE_EXISTING_CAPABILITY",
    "ADAPT_SUPPORTED_CHALLENGE",
    "DEVELOP_NEW_CAPABILITY",
  ];
  const PROVENANCE = [
    "WORKBENCH_DERIVED",
    "LOCAL_MANUAL_ASSERTION",
    "NATIVE_IMPORTED_RESULT",
    "EXTERNAL_LINKED_RECORD",
  ];
  const WORKFLOW_STATES = [
    "NOT_STARTED",
    "READY_FOR_ACTION",
    "ACTIVE_REPORTED",
    "ACTIVE_NATIVE_EVIDENCE",
    "WAITING_ON_DEPENDENCY",
    "NEEDS_OWNER_DECISION",
    "PARKED",
    "CLOSED",
  ];
  const EVIDENCE_STATES = [
    "MISSING",
    "STRUCTURAL_ONLY",
    "SOURCE_EXECUTED_UNRESOLVED",
    "UNDER_REVIEW",
    "QUALIFICATION_CANDIDATE",
    "QUALIFIED_SCOPED",
    "NOT_APPLICABLE",
  ];
  const CUSTOMER_OUTCOMES = [
    "OPEN",
    "FEASIBILITY_FINDING",
    "SCOPE_REVISION_NEEDED",
    "BASELINE_RETAINED",
    "CANDIDATE_READY_FOR_FURTHER_TEST",
    "DELIVERY_QUALIFICATION_REQUIRED",
    "PARKED",
    "CLOSED",
  ];
  const ATTENTION_BUCKETS = [
    "NEEDS_DECISION",
    "READY_FOR_ACTION",
    "ACTIVE",
    "WAITING",
    "CLOSED_OR_PARKED",
  ];
  const DEPENDENCY_DOMAINS = [
    "COMMERCIAL_CONTEXT",
    "INTENDED_USE",
    "PHYSICS_SCOPE",
    "INPUT_CONTRACT",
    "OUTPUT_CONTRACT",
    "UNITS_SCALING",
    "POPULATION_CASES",
    "GENERATOR",
    "MEASUREMENT_SCORE",
    "REFERENCE",
    "RECONSTRUCTION",
    "CPES_DISCLOSURE",
    "RIGHTS",
    "DEPLOYMENT",
    "AUTHORING",
  ];
  const SCIENTIFIC_APPLICABILITY = [
    "UNASSESSED",
    "CARRIED_FORWARD_UNCHANGED_SCOPE",
    "REVIEW_REQUIRED",
    "NOT_APPLICABLE",
    "SOURCE_OWNER_CONFIRMED",
  ];
  const RIGHTS_STATUS = [
    "UNRESOLVED",
    "UNCHANGED_SOURCE_SCOPE",
    "REVIEW_REQUIRED",
    "PROHIBITED",
    "SOURCE_AUTHORIZED",
  ];
  const EXTERNAL_RECORD_STATES = [
    "PREPARED",
    "EXPORTED_OWNER_REQUEST",
    "SENT",
    "ACKNOWLEDGED",
    "EXECUTED",
    "OWNER_DECISION",
    "BLOCKED",
  ];

  const FIELD_DOMAINS = Object.freeze({
    commercial_context: ["COMMERCIAL_CONTEXT"],
    intended_use: ["INTENDED_USE", "DEPLOYMENT"],
    physics_family: [
      "PHYSICS_SCOPE",
      "GENERATOR",
      "MEASUREMENT_SCORE",
      "REFERENCE",
      "CPES_DISCLOSURE",
      "AUTHORING",
    ],
    requested_goal: ["PHYSICS_SCOPE", "OUTPUT_CONTRACT", "MEASUREMENT_SCORE", "AUTHORING"],
    inputs: ["INPUT_CONTRACT", "GENERATOR", "REFERENCE", "AUTHORING"],
    outputs: ["OUTPUT_CONTRACT", "MEASUREMENT_SCORE", "REFERENCE", "AUTHORING"],
    units: ["UNITS_SCALING", "OUTPUT_CONTRACT", "MEASUREMENT_SCORE", "REFERENCE"],
    geometry: ["PHYSICS_SCOPE", "INPUT_CONTRACT", "GENERATOR", "REFERENCE", "AUTHORING"],
    conditions: ["PHYSICS_SCOPE", "INPUT_CONTRACT", "GENERATOR", "REFERENCE", "AUTHORING"],
    regime: ["POPULATION_CASES", "GENERATOR", "REFERENCE", "MEASUREMENT_SCORE"],
    population: ["POPULATION_CASES", "GENERATOR", "MEASUREMENT_SCORE", "REFERENCE"],
    score: ["MEASUREMENT_SCORE", "REFERENCE"],
    reference: ["REFERENCE", "MEASUREMENT_SCORE"],
    disclosure_scope: ["CPES_DISCLOSURE", "RIGHTS"],
    rights_scope: ["RIGHTS"],
    deployment_environment: ["DEPLOYMENT"],
  });

  const C05_DOMAINS = [
    "PHYSICS_SCOPE",
    "INPUT_CONTRACT",
    "OUTPUT_CONTRACT",
    "UNITS_SCALING",
    "POPULATION_CASES",
    "GENERATOR",
    "MEASUREMENT_SCORE",
    "REFERENCE",
    "RECONSTRUCTION",
    "AUTHORING",
  ];

  const clone = (value) => JSON.parse(JSON.stringify(value));
  function exact(value, keys, label) {
    const proto = value && Object.getPrototypeOf(value);
    if (!value || (proto !== Object.prototype && proto !== null)) throw Error(label + " must be an object");
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
      throw Error(label + " has unsupported or missing fields");
    }
    return value;
  }
  function text(value, label, max = 8_000, required = false) {
    if (typeof value !== "string" || value.length > max || (required && !value)) throw Error("Invalid " + label);
    return value;
  }
  function ident(value, label) {
    if (typeof value !== "string" || !/^([A-Za-z0-9][A-Za-z0-9._:-]{0,191})$/.test(value)) {
      throw Error("Invalid " + label);
    }
    return value;
  }
  function list(value, label, max = 128) {
    if (!Array.isArray(value) || value.length > max) throw Error("Invalid " + label);
    return value;
  }
  function enumValue(value, allowed, label) {
    if (!allowed.includes(value)) throw Error("Invalid " + label);
    return value;
  }
  function strings(value, label, allowed = null, max = 128) {
    return list(value, label, max).map((item) => {
      text(item, label + " item", 1_000, true);
      if (allowed) enumValue(item, allowed, label + " item");
      return item;
    });
  }

  function newRoutePlan() {
    return {
      route: "UNASSESSED",
      rationale: "",
      source_or_capability_ref: "",
      route_basis: "",
      unresolved_conditions: [],
      next_decision: "",
      bounded_question: "",
      stop_condition: "",
      restart_event: "",
      selected_by_assertion: "",
      status_provenance: "WORKBENCH_DERIVED",
    };
  }

  function newCoordination(revision = 1) {
    return {
      customer_outcome: "OPEN",
      customer_outcome_provenance: "WORKBENCH_DERIVED",
      decision_needed: "",
      blocker: "",
      blocker_owner: "",
      restart_event: "",
      external_records: [],
      last_relevant_design_revision: revision,
    };
  }

  function validateRoutePlan(plan, design) {
    exact(plan, Object.keys(newRoutePlan()), "route plan");
    enumValue(plan.route, ROUTES, "planning route");
    for (const key of [
      "rationale",
      "source_or_capability_ref",
      "route_basis",
      "next_decision",
      "bounded_question",
      "stop_condition",
      "restart_event",
      "selected_by_assertion",
    ]) text(plan[key], "route " + key);
    strings(plan.unresolved_conditions, "unresolved conditions", null, 64);
    enumValue(plan.status_provenance, PROVENANCE, "route provenance");
    if (plan.route !== "UNASSESSED" && !plan.rationale) throw Error("Selected route requires rationale");
    if (plan.route === "USE_EXISTING_CAPABILITY" && !plan.source_or_capability_ref) {
      throw Error("Existing-capability route requires a capability reference");
    }
    if (plan.route === "ADAPT_SUPPORTED_CHALLENGE") {
      if (!plan.source_or_capability_ref) throw Error("Adapt route requires a source Challenge reference");
      if (design.scope.physics_family && design.scope.physics_family !== "periodic_viscous_burgers_1d_v1") {
        throw Error("Adapt route cannot coerce unsupported physics into the Burgers authoring path");
      }
    }
    if (plan.route === "DEVELOP_NEW_CAPABILITY" &&
      (!plan.bounded_question || !plan.stop_condition || !plan.restart_event)) {
      throw Error("Develop route requires a bounded question, stop condition, and restart event");
    }
    return clone(plan);
  }

  function validateExternalRecord(record) {
    exact(record, ["record_id", "source_ref", "status", "provenance", "note"], "external record");
    ident(record.record_id, "external record ID");
    text(record.source_ref, "external source reference", 1_000, true);
    enumValue(record.status, EXTERNAL_RECORD_STATES, "external record status");
    if (record.provenance !== "EXTERNAL_LINKED_RECORD") throw Error("External record provenance must remain linked");
    text(record.note, "external record note", 2_000);
    return clone(record);
  }

  function validateCoordination(value, revision) {
    exact(value, Object.keys(newCoordination()), "coordination");
    enumValue(value.customer_outcome, CUSTOMER_OUTCOMES, "customer outcome");
    enumValue(value.customer_outcome_provenance, PROVENANCE, "customer outcome provenance");
    for (const key of ["decision_needed", "blocker", "blocker_owner", "restart_event"]) {
      text(value[key], "coordination " + key);
    }
    list(value.external_records, "external records", 64).forEach(validateExternalRecord);
    if (!Number.isSafeInteger(value.last_relevant_design_revision) || value.last_relevant_design_revision < 1 ||
      value.last_relevant_design_revision > revision) throw Error("Invalid last relevant design revision");
    return clone(value);
  }

  function validateEvidenceBinding(binding, design, { trustedSource = false } = {}) {
    const keys = [
      "evidence_binding_id",
      "evidence_kind",
      "source_ref",
      "source_digest_or_identity",
      "design_id",
      "design_revision",
      "trace_ids",
      "case_family_ids",
      "dependency_domains",
      "scientific_applicability",
      "use_or_rights_status",
      "assessment_basis",
      "rationale",
      "invalidated_by",
      "status_provenance",
    ];
    exact(binding, keys, "evidence binding");
    ident(binding.evidence_binding_id, "evidence binding ID");
    enumValue(binding.evidence_kind, [
      "MEASUREMENT_IMPLEMENTATION",
      "TEMPLATE",
      "PRIOR_DECISION",
      "FIXED_CASE_RESULT",
      "RESEARCH_REFERENCE",
      "DEPLOYMENT_EVIDENCE",
    ], "evidence kind");
    text(binding.source_ref, "evidence source reference", 1_000, true);
    text(binding.source_digest_or_identity, "evidence identity", 300, true);
    if (binding.design_id !== design.design_id || binding.design_revision !== design.revision) {
      throw Error("Evidence binding is not scoped to the exact design revision");
    }
    strings(binding.trace_ids, "evidence trace IDs", null, 256);
    strings(binding.case_family_ids, "evidence case-family IDs", null, 128);
    if (binding.trace_ids.some((id) => !design.traces.some((trace) => trace.trace_id === id)) ||
      binding.case_family_ids.some((id) => !design.cases.some((item) => item.case_family_id === id))) {
      throw Error("Evidence binding references an unknown trace or case family");
    }
    const domains = strings(binding.dependency_domains, "dependency domains", DEPENDENCY_DOMAINS, 32);
    if (new Set(domains).size !== domains.length) throw Error("Duplicate evidence dependency domain");
    enumValue(binding.scientific_applicability, SCIENTIFIC_APPLICABILITY, "scientific applicability");
    enumValue(binding.use_or_rights_status, RIGHTS_STATUS, "rights status");
    enumValue(binding.status_provenance, PROVENANCE, "evidence provenance");
    for (const key of ["assessment_basis", "rationale"]) text(binding[key], "evidence " + key, 2_000, true);
    strings(binding.invalidated_by, "evidence invalidations", null, 64);
    if (!trustedSource && binding.scientific_applicability === "SOURCE_OWNER_CONFIRMED") {
      throw Error("Source-owner confirmation requires a trusted source interface");
    }
    if (!trustedSource && binding.use_or_rights_status === "SOURCE_AUTHORIZED") {
      throw Error("Source authorization requires a trusted source interface");
    }
    return clone(binding);
  }

  function selectRoute(design, route, values = {}) {
    if (design.status !== "DRAFT") throw Error("Sealed design route requires a new revision");
    const allowed = Object.keys(newRoutePlan()).filter((key) => key !== "route");
    if (Object.keys(values).some((key) => !allowed.includes(key))) throw Error("Unsupported route-plan field");
    const next = { ...newRoutePlan(), ...clone(design.route_plan), ...clone(values), route };
    if (route === "UNASSESSED") Object.assign(next, newRoutePlan());
    else if (!Object.hasOwn(values, "status_provenance")) next.status_provenance = "LOCAL_MANUAL_ASSERTION";
    validateRoutePlan(next, design);
    design.route_plan = next;
    return clone(next);
  }

  function addEvidenceBinding(design, binding, options = {}) {
    if (design.status !== "DRAFT") throw Error("Sealed design is immutable");
    const checked = validateEvidenceBinding(binding, design, options);
    const prior = design.evidence_bindings.find((item) => item.evidence_binding_id === checked.evidence_binding_id);
    if (prior) {
      if (JSON.stringify(prior) === JSON.stringify(checked)) return { disposition: "DEDUPLICATED", binding: clone(prior) };
      throw Error("Conflicting evidence binding identity");
    }
    design.evidence_bindings.push(checked);
    return { disposition: "ADDED", binding: clone(checked) };
  }

  function c05Binding(record, design) {
    return {
      evidence_binding_id: "c05-" + record.source.result_digest.slice(7, 31),
      evidence_kind: "FIXED_CASE_RESULT",
      source_ref: record.source.repository + "@" + record.source.source_revision + ":" + record.source.implementation,
      source_digest_or_identity: record.source.result_digest,
      design_id: design.design_id,
      design_revision: design.revision,
      trace_ids: clone(record.requirement_trace_ids),
      case_family_ids: clone(record.case_family_ids),
      dependency_domains: clone(C05_DOMAINS),
      scientific_applicability: "UNASSESSED",
      use_or_rights_status: "UNRESOLVED",
      assessment_basis: "Exact source-owned C-05 request/result bytes bound by the accepted reader.",
      rationale: "Public DEVELOPMENT fixed-case evidence; scientific limits and uncertainty remain unresolved.",
      invalidated_by: [],
      status_provenance: "NATIVE_IMPORTED_RESULT",
    };
  }

  function bindC05Record(design, record) {
    if (!Array.isArray(design.evidence_bindings)) return null;
    return addEvidenceBinding(design, c05Binding(record, design));
  }

  function changedDomains(field) {
    return clone(FIELD_DOMAINS[field] || []);
  }

  function applyImpactToBinding(binding, domains, field) {
    const intersection = binding.dependency_domains.filter((domain) => domains.includes(domain));
    const onlyUse = intersection.every((domain) => ["RIGHTS", "DEPLOYMENT", "INTENDED_USE", "COMMERCIAL_CONTEXT", "CPES_DISCLOSURE"].includes(domain));
    if (intersection.length && !onlyUse) {
      binding.scientific_applicability = "REVIEW_REQUIRED";
      if (!binding.invalidated_by.includes(field)) binding.invalidated_by.push(field);
      binding.assessment_basis = "Material dependency changed: " + intersection.join(", ") + ".";
      binding.rationale = domains.includes("POPULATION_CASES") && binding.evidence_kind === "FIXED_CASE_RESULT"
        ? "The exact fixed-case observation remains historical; it cannot support the changed population claim without review."
        : "The source evidence remains retained, but its affected claim requires re-review.";
    } else if (binding.scientific_applicability !== "NOT_APPLICABLE") {
      binding.scientific_applicability = "CARRIED_FORWARD_UNCHANGED_SCOPE";
      binding.assessment_basis = "No declared scientific dependency changed for this evidence.";
      binding.rationale = "Carried forward without creating a new qualification decision.";
    }
    if (domains.some((domain) => ["RIGHTS", "INTENDED_USE", "DEPLOYMENT", "CPES_DISCLOSURE"].includes(domain))) {
      binding.use_or_rights_status = "REVIEW_REQUIRED";
    } else if (binding.use_or_rights_status !== "PROHIBITED") {
      binding.use_or_rights_status = "UNCHANGED_SOURCE_SCOPE";
    }
    return binding;
  }

  function applyChangeImpact(design, field) {
    const domains = changedDomains(field);
    for (const binding of design.evidence_bindings) applyImpactToBinding(binding, domains, field);
    return domains;
  }

  function carryEvidenceBindings(parent, child) {
    const source = clone(parent.evidence_bindings || []);
    for (const record of parent.measurement_evidence || []) {
      const candidate = c05Binding(record, parent);
      if (!source.some((item) => item.source_digest_or_identity === candidate.source_digest_or_identity)) source.push(candidate);
    }
    return source.map((binding, index) => ({
      ...binding,
      evidence_binding_id: "carry-" + child.revision + "-" + (index + 1) + "-" + binding.evidence_binding_id,
      design_id: child.design_id,
      design_revision: child.revision,
      scientific_applicability: binding.scientific_applicability === "NOT_APPLICABLE"
        ? "NOT_APPLICABLE"
        : "CARRIED_FORWARD_UNCHANGED_SCOPE",
      use_or_rights_status: binding.use_or_rights_status === "PROHIBITED"
        ? "PROHIBITED"
        : "UNCHANGED_SOURCE_SCOPE",
      assessment_basis: "Parent design evidence retained for explicit change-impact review.",
      rationale: "No affected dependency has yet been recorded on this child revision; carry-forward is not qualification.",
      invalidated_by: [],
      status_provenance: "WORKBENCH_DERIVED",
    }));
  }

  function linkExternalRecord(design, record) {
    if (design.status !== "DRAFT") throw Error("Sealed design is immutable");
    const checked = validateExternalRecord(record);
    const prior = design.coordination.external_records.find((item) => item.record_id === checked.record_id);
    if (prior) {
      if (JSON.stringify(prior) === JSON.stringify(checked)) return { disposition: "DEDUPLICATED", record: clone(prior) };
      throw Error("Conflicting external record identity");
    }
    design.coordination.external_records.push(checked);
    return { disposition: "LINKED", record: clone(checked) };
  }

  function nextAction(job, design) {
    const plan = design.route_plan;
    if (plan.route === "UNASSESSED") {
      return { action: "CHOOSE_PLANNING_ROUTE", why: "No exact-revision planning route has been selected.", missing_conditions: ["route"] };
    }
    if (!job.accountable_owner) {
      return { action: "NAME_ACCOUNTABLE_OWNER", why: "The lead cannot also stand in for business/technical disposition ownership.", missing_conditions: ["accountable_owner"] };
    }
    const waiting = [...design.handoffs, ...design.coordination.external_records].find((item) =>
      ["EXPORTED", "EXPORTED_OWNER_REQUEST", "SENT", "BLOCKED"].includes(item.status));
    if (waiting) {
      return { action: "WAIT_FOR_RESTART_EVENT", why: "One bounded request is already waiting; export does not mean approved or executed.", missing_conditions: [design.coordination.restart_event || plan.restart_event || "named owner response"] };
    }
    if (plan.route === "USE_EXISTING_CAPABILITY") {
      if (plan.unresolved_conditions.length) return { action: "REVIEW_INTENDED_USE_APPLICABILITY", why: "The referenced capability is not automatically qualified for this use.", missing_conditions: clone(plan.unresolved_conditions) };
      if (design.scope.rights_scope === "UNRESOLVED") return { action: "RESOLVE_RIGHTS", why: "Scientific relevance and use authorization are separate.", missing_conditions: ["rights/use status"] };
      return { action: "REQUEST_DEPLOYMENT_OR_OWNER_DISPOSITION", why: "Capability and scope are bound; the next missing decision is customer/deployment applicability.", missing_conditions: [plan.next_decision || "owner disposition"] };
    }
    if (plan.route === "ADAPT_SUPPORTED_CHALLENGE") {
      const affected = design.evidence_bindings.filter((item) => item.scientific_applicability === "REVIEW_REQUIRED");
      if (!plan.route_basis) return { action: "DESCRIBE_SUPPORTED_CHALLENGE_DELTA", why: "Selective reuse requires an exact delta from the source Challenge.", missing_conditions: ["route_basis"] };
      if (affected.length) return { action: "REVIEW_AFFECTED_EVIDENCE_BINDINGS", why: "Only evidence whose declared dependencies changed needs re-review.", missing_conditions: affected.map((item) => item.evidence_binding_id) };
      if (design.authoring.compatibility !== "EXACT_SUPPORTED") return { action: "RUN_NATIVE_AUTHORING_SEMANTIC_COMPARISON", why: "The supported adapter must preserve the exact intended semantics.", missing_conditions: ["intent-preserving authoring receipt"] };
      return { action: "REQUEST_MISSING_OWNER_DECISION", why: "Structural adaptation is assembled without creating qualification.", missing_conditions: [plan.next_decision || "source-owner decision"] };
    }
    if (!job.lead) return { action: "ASSIGN_FEASIBILITY_LEAD", why: "One named lead is required for the bounded feasibility question.", missing_conditions: ["lead"] };
    if (!plan.bounded_question || !plan.stop_condition || !plan.restart_event) {
      return { action: "DEFINE_BOUNDED_FEASIBILITY_QUESTION", why: "Unsupported physics must not open a full qualification program by default.", missing_conditions: ["bounded_question", "stop_condition", "restart_event"] };
    }
    if (!design.handoffs.length) return { action: "ISSUE_ONE_BOUNDED_HANDOFF", why: "The feasibility question is frozen and ready for one lead.", missing_conditions: ["one exported handoff"] };
    return { action: "REVIEW_FEASIBILITY_RETURN", why: "A returned bounded finding may support revise, reroute, park, or continue.", missing_conditions: [plan.next_decision || "owner disposition"] };
  }

  function evidenceAxis(design) {
    const currentNative = design.measurement_evidence.some((item) => item.binding_status === "CURRENT_DESIGN_REVISION" && item.evidence_state === "SOURCE_MEASUREMENT_EVIDENCE_BOUND");
    if (currentNative) return { state: "SOURCE_EXECUTED_UNRESOLVED", provenance: "NATIVE_IMPORTED_RESULT", source: "C-05 exact retained source result" };
    if (design.evidence_bindings.some((item) => item.scientific_applicability === "REVIEW_REQUIRED")) return { state: "UNDER_REVIEW", provenance: "WORKBENCH_DERIVED", source: "change-impact rule" };
    if (design.evidence_bindings.some((item) => item.scientific_applicability === "SOURCE_OWNER_CONFIRMED")) return { state: "QUALIFIED_SCOPED", provenance: "NATIVE_IMPORTED_RESULT", source: "eligible source-owned authority interface" };
    if (design.evidence_bindings.length || design.requirements.length || design.traces.length) return { state: "STRUCTURAL_ONLY", provenance: "WORKBENCH_DERIVED", source: "local design structure" };
    return { state: "MISSING", provenance: "WORKBENCH_DERIVED", source: "no evidence bound" };
  }

  function workflowAxis(job, design) {
    const records = design.coordination.external_records;
    const handoffs = design.handoffs;
    const native = design.measurement_evidence.some((item) => item.binding_status === "CURRENT_DESIGN_REVISION");
    if (design.coordination.customer_outcome === "CLOSED") return { state: "CLOSED", provenance: design.coordination.customer_outcome_provenance, source: "customer outcome" };
    if (design.coordination.customer_outcome === "PARKED") return { state: "PARKED", provenance: design.coordination.customer_outcome_provenance, source: "customer outcome" };
    if (records.some((item) => ["EXPORTED_OWNER_REQUEST", "SENT", "BLOCKED"].includes(item.status)) || handoffs.some((item) => ["EXPORTED", "BLOCKED"].includes(item.status))) {
      return { state: "WAITING_ON_DEPENDENCY", provenance: records.length ? "EXTERNAL_LINKED_RECORD" : "WORKBENCH_DERIVED", source: "bounded request awaiting restart event" };
    }
    if (records.some((item) => item.status === "ACKNOWLEDGED") || handoffs.some((item) => item.status === "ACKNOWLEDGED")) return { state: "ACTIVE_REPORTED", provenance: records.length ? "EXTERNAL_LINKED_RECORD" : "LOCAL_MANUAL_ASSERTION", source: "acknowledgment only; execution not established" };
    if (native) return { state: "ACTIVE_NATIVE_EVIDENCE", provenance: "NATIVE_IMPORTED_RESULT", source: "exact native result bytes" };
    if (records.some((item) => ["EXECUTED", "OWNER_DECISION"].includes(item.status)) || handoffs.some((item) => item.status === "RETURNED")) return { state: "NEEDS_OWNER_DECISION", provenance: records.length ? "EXTERNAL_LINKED_RECORD" : "LOCAL_MANUAL_ASSERTION", source: "returned result remains unqualified" };
    const action = nextAction(job, design);
    if (action.action === "CHOOSE_PLANNING_ROUTE" || action.action === "NAME_ACCOUNTABLE_OWNER") return { state: "NEEDS_OWNER_DECISION", provenance: "WORKBENCH_DERIVED", source: action.action };
    if (planIsEmpty(design.route_plan)) return { state: "NOT_STARTED", provenance: "WORKBENCH_DERIVED", source: "empty route plan" };
    return { state: "READY_FOR_ACTION", provenance: "WORKBENCH_DERIVED", source: action.action };
  }

  function planIsEmpty(plan) {
    return plan.route === "UNASSESSED" && !plan.rationale && !plan.route_basis;
  }

  function attentionBucket(workflow) {
    if (workflow === "NEEDS_OWNER_DECISION") return "NEEDS_DECISION";
    if (["READY_FOR_ACTION", "NOT_STARTED"].includes(workflow)) return "READY_FOR_ACTION";
    if (["ACTIVE_REPORTED", "ACTIVE_NATIVE_EVIDENCE"].includes(workflow)) return "ACTIVE";
    if (workflow === "WAITING_ON_DEPENDENCY") return "WAITING";
    return "CLOSED_OR_PARKED";
  }

  function ownerSummary(job, design) {
    const workflow = workflowAxis(job, design);
    const evidence = evidenceAxis(design);
    const action = nextAction(job, design);
    return {
      job_id: job.job_id,
      client_job: job.title,
      design_id: design.design_id,
      design_revision: design.revision,
      route: design.route_plan.route,
      accountable_owner: job.accountable_owner,
      lead: job.lead,
      current_action: action.action,
      action_reason: action.why,
      missing_conditions: action.missing_conditions,
      workflow_state: workflow.state,
      workflow_provenance: workflow.provenance,
      workflow_source: workflow.source,
      evidence_state: evidence.state,
      evidence_provenance: evidence.provenance,
      evidence_source: evidence.source,
      customer_outcome: design.coordination.customer_outcome,
      customer_outcome_provenance: design.coordination.customer_outcome_provenance,
      open_request_or_handoff: design.handoffs.at(-1)?.status || design.coordination.external_records.at(-1)?.status || "NONE",
      evidence_received: evidence.state === "SOURCE_EXECUTED_UNRESOLVED" ? "YES_SCOPED_UNRESOLVED" : "NO_NATIVE_RESULT",
      decision_needed: design.coordination.decision_needed || design.route_plan.next_decision,
      blocker: design.coordination.blocker,
      blocker_owner: design.coordination.blocker_owner,
      restart_event: design.coordination.restart_event || design.route_plan.restart_event,
      last_relevant_design_revision: design.coordination.last_relevant_design_revision,
      attention_bucket: attentionBucket(workflow.state),
      qualification_effect: "NONE_UNLESS_ELIGIBLE_SOURCE_OWNER_RECORD_EXISTS",
    };
  }

  function ownerConsole(workspace) {
    const rows = workspace.jobs.map((job) => ownerSummary(job, job.designs.at(-1)));
    const counts = Object.fromEntries(ATTENTION_BUCKETS.map((bucket) => [bucket, rows.filter((row) => row.attention_bucket === bucket).length]));
    return { rows, counts, authority: "Attention grouping only; no priority score, percent complete, qualification, approval, or launch authority." };
  }

  const api = {
    ROUTES,
    PROVENANCE,
    WORKFLOW_STATES,
    EVIDENCE_STATES,
    CUSTOMER_OUTCOMES,
    ATTENTION_BUCKETS,
    DEPENDENCY_DOMAINS,
    SCIENTIFIC_APPLICABILITY,
    RIGHTS_STATUS,
    EXTERNAL_RECORD_STATES,
    FIELD_DOMAINS,
    C05_DOMAINS,
    newRoutePlan,
    newCoordination,
    validateRoutePlan,
    validateCoordination,
    validateEvidenceBinding,
    validateExternalRecord,
    selectRoute,
    addEvidenceBinding,
    c05Binding,
    bindC05Record,
    changedDomains,
    applyChangeImpact,
    carryEvidenceBindings,
    linkExternalRecord,
    nextAction,
    evidenceAxis,
    workflowAxis,
    attentionBucket,
    ownerSummary,
    ownerConsole,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonGoalRouting = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
