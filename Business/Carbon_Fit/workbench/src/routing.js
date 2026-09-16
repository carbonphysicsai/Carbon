/* Pure GOAL-WORKBENCH-05A routing, cumulative applicability, and owner-console engine. */
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
    "UNRESOLVED_IMPACT",
  ];
  const SCIENTIFIC_APPLICABILITY = [
    "UNASSESSED",
    "CARRIED_FORWARD_UNCHANGED_SCOPE",
    "REVIEW_REQUIRED",
    "NOT_APPLICABLE",
    "SOURCE_OWNER_CONFIRMED",
  ];
  const SCOPE_RELATIONSHIPS = ["UNASSESSED", "UNCHANGED", "CHANGED", "UNKNOWN"];
  const RIGHTS_STATUS = [
    "UNRESOLVED",
    "UNCHANGED_SOURCE_SCOPE",
    "REVIEW_REQUIRED",
    "PROHIBITED",
    "SOURCE_AUTHORIZED",
  ];
  const ORIGIN_VERIFICATION = [
    "UNVERIFIED_CLAIM",
    "EXTERNAL_LOCATOR_ONLY",
    "PINNED_C05_FIXTURE_VERIFIED",
    "WORKBENCH_DERIVED_LINEAGE",
  ];
  const EXTERNAL_RECORD_STATES = [
    "PREPARED",
    "EXPORTED_OWNER_REQUEST",
    "SENT",
    "ACKNOWLEDGED",
    "EXECUTION_REPORTED_ACTIVE",
    "EXECUTED",
    "RETURNED",
    "FAILED",
    "OWNER_DECISION",
    "BLOCKED",
  ];

  /* Every supported editable/importable semantic path has an explicit mapping. */
  const FIELD_DOMAINS = Object.freeze({
    commercial_context: ["COMMERCIAL_CONTEXT"],
    commercial_note: ["COMMERCIAL_CONTEXT"],
    intended_use: ["INTENDED_USE", "DEPLOYMENT"],
    physics_family: [
      "PHYSICS_SCOPE",
      "GENERATOR",
      "MEASUREMENT_SCORE",
      "REFERENCE",
      "CPES_DISCLOSURE",
      "AUTHORING",
    ],
    requested_goal: [
      "PHYSICS_SCOPE",
      "OUTPUT_CONTRACT",
      "MEASUREMENT_SCORE",
      "AUTHORING",
    ],
    inputs: ["INPUT_CONTRACT", "GENERATOR", "REFERENCE", "AUTHORING"],
    outputs: ["OUTPUT_CONTRACT", "MEASUREMENT_SCORE", "REFERENCE", "AUTHORING"],
    units: [
      "UNITS_SCALING",
      "OUTPUT_CONTRACT",
      "MEASUREMENT_SCORE",
      "REFERENCE",
    ],
    geometry: [
      "PHYSICS_SCOPE",
      "INPUT_CONTRACT",
      "GENERATOR",
      "REFERENCE",
      "AUTHORING",
    ],
    conditions: [
      "PHYSICS_SCOPE",
      "INPUT_CONTRACT",
      "GENERATOR",
      "REFERENCE",
      "AUTHORING",
    ],
    regime: ["POPULATION_CASES", "GENERATOR", "REFERENCE", "MEASUREMENT_SCORE"],
    exclusions: ["INTENDED_USE", "POPULATION_CASES", "RIGHTS", "DEPLOYMENT"],
    query_workload: [
      "INPUT_CONTRACT",
      "OUTPUT_CONTRACT",
      "MEASUREMENT_SCORE",
      "REFERENCE",
      "DEPLOYMENT",
    ],
    turnaround: ["COMMERCIAL_CONTEXT", "DEPLOYMENT"],
    failure_consequences: ["INTENDED_USE", "MEASUREMENT_SCORE", "DEPLOYMENT"],
    data_access: ["INPUT_CONTRACT", "CPES_DISCLOSURE", "RIGHTS", "DEPLOYMENT"],
    rights_scope: ["RIGHTS"],
    disclosure_scope: ["CPES_DISCLOSURE", "RIGHTS"],
    disclosure: ["CPES_DISCLOSURE", "RIGHTS"],
    deployment_environment: ["DEPLOYMENT"],
    requirements: [
      "INTENDED_USE",
      "OUTPUT_CONTRACT",
      "MEASUREMENT_SCORE",
      "POPULATION_CASES",
      "REFERENCE",
      "AUTHORING",
    ],
    traces: [
      "OUTPUT_CONTRACT",
      "UNITS_SCALING",
      "MEASUREMENT_SCORE",
      "REFERENCE",
      "AUTHORING",
    ],
    cases: ["POPULATION_CASES", "GENERATOR", "REFERENCE"],
    population: [
      "POPULATION_CASES",
      "GENERATOR",
      "MEASUREMENT_SCORE",
      "REFERENCE",
    ],
    generator: ["GENERATOR", "POPULATION_CASES", "REFERENCE"],
    score: ["MEASUREMENT_SCORE", "REFERENCE"],
    score_plan: ["MEASUREMENT_SCORE", "REFERENCE"],
    measurement: [
      "MEASUREMENT_SCORE",
      "OUTPUT_CONTRACT",
      "UNITS_SCALING",
      "REFERENCE",
    ],
    reference: ["REFERENCE", "MEASUREMENT_SCORE"],
    reference_plan: ["REFERENCE", "MEASUREMENT_SCORE"],
    reconstruction: ["RECONSTRUCTION", "MEASUREMENT_SCORE", "REFERENCE"],
    authoring: [
      "AUTHORING",
      "PHYSICS_SCOPE",
      "INPUT_CONTRACT",
      "OUTPUT_CONTRACT",
    ],
  });

  const C05_DOMAINS = [
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
  const MINIMUM_DEPENDENCIES = Object.freeze({
    MEASUREMENT_IMPLEMENTATION: [
      "OUTPUT_CONTRACT",
      "UNITS_SCALING",
      "MEASUREMENT_SCORE",
    ],
    TEMPLATE: [
      "PHYSICS_SCOPE",
      "INPUT_CONTRACT",
      "OUTPUT_CONTRACT",
      "AUTHORING",
    ],
    PRIOR_DECISION: ["INTENDED_USE"],
    FIXED_CASE_RESULT: [
      "INTENDED_USE",
      "PHYSICS_SCOPE",
      "INPUT_CONTRACT",
      "OUTPUT_CONTRACT",
      "UNITS_SCALING",
      "MEASUREMENT_SCORE",
      "REFERENCE",
      "RECONSTRUCTION",
      "CPES_DISCLOSURE",
      "RIGHTS",
      "DEPLOYMENT",
      "AUTHORING",
    ],
    RESEARCH_REFERENCE: ["PHYSICS_SCOPE", "REFERENCE"],
    DEPLOYMENT_EVIDENCE: ["INTENDED_USE", "RIGHTS", "DEPLOYMENT"],
    MANUAL_RESEARCH_NOTE: [],
  });

  const clone = (value) => JSON.parse(JSON.stringify(value));
  function exact(value, keys, label) {
    const proto = value && Object.getPrototypeOf(value);
    if (!value || (proto !== Object.prototype && proto !== null))
      throw Error(label + " must be an object");
    const actual = Object.keys(value).sort(),
      expected = [...keys].sort();
    if (
      actual.length !== expected.length ||
      actual.some((key, index) => key !== expected[index])
    )
      throw Error(label + " has unsupported or missing fields");
    return value;
  }
  function text(value, label, max = 8_000, required = false) {
    if (typeof value !== "string" || value.length > max || (required && !value))
      throw Error("Invalid " + label);
    return value;
  }
  function ident(value, label) {
    if (
      typeof value !== "string" ||
      !/^([A-Za-z0-9][A-Za-z0-9._:-]{0,191})$/.test(value)
    )
      throw Error("Invalid " + label);
    return value;
  }
  function integer(value, label, min = 0) {
    if (!Number.isSafeInteger(value) || value < min)
      throw Error("Invalid " + label);
    return value;
  }
  function list(value, label, max = 128) {
    if (!Array.isArray(value) || value.length > max)
      throw Error("Invalid " + label);
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
      current_action_ref: "",
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
    ])
      text(plan[key], "route " + key);
    strings(plan.unresolved_conditions, "unresolved conditions", null, 64);
    enumValue(plan.status_provenance, PROVENANCE, "route provenance");
    if (
      plan.route === "UNASSESSED" &&
      plan.status_provenance !== "WORKBENCH_DERIVED"
    )
      throw Error("Unassessed route provenance must be workbench-derived");
    if (
      plan.route !== "UNASSESSED" &&
      plan.status_provenance !== "LOCAL_MANUAL_ASSERTION"
    )
      throw Error(
        "Route selection is a local assertion; native provenance is unavailable",
      );
    if (plan.route !== "UNASSESSED" && !plan.rationale)
      throw Error("Selected route requires rationale");
    if (
      plan.route === "USE_EXISTING_CAPABILITY" &&
      !plan.source_or_capability_ref
    )
      throw Error("Existing-capability route requires a capability reference");
    if (plan.route === "ADAPT_SUPPORTED_CHALLENGE") {
      if (!plan.source_or_capability_ref)
        throw Error("Adapt route requires a source Challenge reference");
      if (
        design.scope.physics_family &&
        design.scope.physics_family !== "periodic_viscous_burgers_1d_v1"
      )
        throw Error(
          "Adapt route cannot coerce unsupported physics into the Burgers authoring path",
        );
    }
    if (
      plan.route === "DEVELOP_NEW_CAPABILITY" &&
      (!plan.bounded_question || !plan.stop_condition || !plan.restart_event)
    )
      throw Error(
        "Develop route requires a bounded question, stop condition, and restart event",
      );
    return clone(plan);
  }
  function validateExternalRecord(record) {
    exact(
      record,
      ["record_id", "source_ref", "status", "provenance", "note"],
      "external record",
    );
    ident(record.record_id, "external record ID");
    text(record.source_ref, "external source reference", 1_000, true);
    enumValue(record.status, EXTERNAL_RECORD_STATES, "external record status");
    if (record.provenance !== "EXTERNAL_LINKED_RECORD")
      throw Error("External record provenance must remain linked");
    text(record.note, "external record note", 2_000);
    return clone(record);
  }
  function validateCoordination(value, revision) {
    exact(value, Object.keys(newCoordination()), "coordination");
    enumValue(value.customer_outcome, CUSTOMER_OUTCOMES, "customer outcome");
    enumValue(
      value.customer_outcome_provenance,
      PROVENANCE,
      "customer outcome provenance",
    );
    if (
      !["WORKBENCH_DERIVED", "LOCAL_MANUAL_ASSERTION"].includes(
        value.customer_outcome_provenance,
      )
    )
      throw Error("Customer outcome cannot claim native or external authority");
    for (const key of [
      "decision_needed",
      "blocker",
      "blocker_owner",
      "restart_event",
      "current_action_ref",
    ])
      text(value[key], "coordination " + key);
    list(value.external_records, "external records", 64).forEach(
      validateExternalRecord,
    );
    if (
      !Number.isSafeInteger(value.last_relevant_design_revision) ||
      value.last_relevant_design_revision < 1 ||
      value.last_relevant_design_revision > revision
    )
      throw Error("Invalid last relevant design revision");
    return clone(value);
  }

  const bindingKeys = [
    "evidence_binding_id",
    "evidence_kind",
    "source_ref",
    "source_digest_or_identity",
    "design_id",
    "design_revision",
    "originating_design_id",
    "originating_design_revision",
    "originating_binding_id",
    "trace_ids",
    "case_family_ids",
    "dependency_domains",
    "scope_relationship",
    "scientific_applicability",
    "scientific_review_reasons",
    "use_or_rights_status",
    "rights_review_reasons",
    "assessment_basis",
    "rationale",
    "invalidated_by",
    "source_claimed_provenance",
    "origin_verification",
    "status_provenance",
  ];
  const reasonKeys = [
    "reason_id",
    "domain",
    "field",
    "originating_design_id",
    "originating_revision",
    "basis",
  ];
  function validateReason(reason, label) {
    exact(reason, reasonKeys, label);
    ident(reason.reason_id, label + " ID");
    enumValue(reason.domain, DEPENDENCY_DOMAINS, label + " domain");
    text(reason.field, label + " field", 500, true);
    ident(reason.originating_design_id, label + " design ID");
    integer(reason.originating_revision, label + " revision", 1);
    text(reason.basis, label + " basis", 1_000, true);
    return clone(reason);
  }
  function validateEvidenceBindingBase(binding, design) {
    exact(binding, bindingKeys, "evidence binding");
    ident(binding.evidence_binding_id, "evidence binding ID");
    enumValue(
      binding.evidence_kind,
      Object.keys(MINIMUM_DEPENDENCIES),
      "evidence kind",
    );
    text(binding.source_ref, "evidence source reference", 1_000, true);
    text(binding.source_digest_or_identity, "evidence identity", 300, true);
    if (
      binding.design_id !== design.design_id ||
      binding.design_revision !== design.revision
    )
      throw Error(
        "Evidence binding is not scoped to the exact design revision",
      );
    ident(binding.originating_design_id, "originating design ID");
    integer(
      binding.originating_design_revision,
      "originating design revision",
      1,
    );
    ident(binding.originating_binding_id, "originating binding ID");
    strings(binding.trace_ids, "evidence trace IDs", null, 256);
    strings(binding.case_family_ids, "evidence case-family IDs", null, 128);
    if (
      binding.trace_ids.some(
        (id) => !design.traces.some((trace) => trace.trace_id === id),
      ) ||
      binding.case_family_ids.some(
        (id) => !design.cases.some((item) => item.case_family_id === id),
      )
    )
      throw Error(
        "Evidence binding references an unknown trace or case family",
      );
    const domains = strings(
      binding.dependency_domains,
      "dependency domains",
      DEPENDENCY_DOMAINS,
      32,
    );
    if (new Set(domains).size !== domains.length)
      throw Error("Duplicate evidence dependency domain");
    if (binding.evidence_kind === "MANUAL_RESEARCH_NOTE" && !domains.length)
      throw Error(
        "Manual research note must declare at least one asserted dependency",
      );
    for (const required of MINIMUM_DEPENDENCIES[binding.evidence_kind])
      if (!domains.includes(required))
        throw Error(
          "Evidence binding omits source-required dependency domain " +
            required,
        );
    enumValue(
      binding.scope_relationship,
      SCOPE_RELATIONSHIPS,
      "scope relationship",
    );
    enumValue(
      binding.scientific_applicability,
      SCIENTIFIC_APPLICABILITY,
      "scientific applicability",
    );
    const scientificReasons = list(
      binding.scientific_review_reasons,
      "scientific review reasons",
      128,
    ).map((item) => validateReason(item, "scientific review reason"));
    const rightsReasons = list(
      binding.rights_review_reasons,
      "rights review reasons",
      128,
    ).map((item) => validateReason(item, "rights review reason"));
    if (
      new Set(scientificReasons.map((item) => item.reason_id)).size !==
        scientificReasons.length ||
      new Set(rightsReasons.map((item) => item.reason_id)).size !==
        rightsReasons.length
    )
      throw Error("Duplicate review reason");
    enumValue(binding.use_or_rights_status, RIGHTS_STATUS, "rights status");
    if (
      scientificReasons.length &&
      binding.scientific_applicability !== "REVIEW_REQUIRED"
    )
      throw Error("Outstanding scientific reasons require review");
    if (
      rightsReasons.length &&
      !["REVIEW_REQUIRED", "PROHIBITED"].includes(binding.use_or_rights_status)
    )
      throw Error(
        "Outstanding rights reasons require review or preserve prohibition",
      );
    for (const key of ["assessment_basis", "rationale"])
      text(binding[key], "evidence " + key, 2_000, true);
    strings(binding.invalidated_by, "evidence invalidations", null, 64);
    enumValue(
      binding.source_claimed_provenance,
      PROVENANCE,
      "source claimed provenance",
    );
    enumValue(
      binding.origin_verification,
      ORIGIN_VERIFICATION,
      "origin verification",
    );
    enumValue(binding.status_provenance, PROVENANCE, "evidence provenance");
    if (
      binding.scientific_applicability === "CARRIED_FORWARD_UNCHANGED_SCOPE" ||
      binding.use_or_rights_status === "UNCHANGED_SOURCE_SCOPE"
    )
      throw Error("Legacy carry labels require v0.5 reconciliation");
    return clone(binding);
  }
  function validateEvidenceBinding(binding, design) {
    const checked = validateEvidenceBindingBase(binding, design);
    if (
      checked.scientific_applicability === "SOURCE_OWNER_CONFIRMED" ||
      checked.use_or_rights_status === "SOURCE_AUTHORIZED"
    )
      throw Error(
        "Source-owner confirmation requires a future eligible source interface",
      );
    if (
      checked.status_provenance === "NATIVE_IMPORTED_RESULT" ||
      checked.origin_verification === "PINNED_C05_FIXTURE_VERIFIED"
    )
      throw Error("Native provenance requires the exact C-05 reader path");
    if (
      !["LOCAL_MANUAL_ASSERTION", "EXTERNAL_LINKED_RECORD"].includes(
        checked.status_provenance,
      )
    )
      throw Error(
        "Generic evidence entry must remain manual or externally linked",
      );
    return checked;
  }
  function c05Binding(record, design) {
    const id = "c05-" + record.source.result_digest.slice(7, 31);
    return {
      evidence_binding_id: id,
      evidence_kind: "FIXED_CASE_RESULT",
      source_ref:
        record.source.repository +
        "@" +
        record.source.source_revision +
        ":" +
        record.source.implementation,
      source_digest_or_identity: record.source.result_digest,
      design_id: design.design_id,
      design_revision: design.revision,
      originating_design_id: design.design_id,
      originating_design_revision: design.revision,
      originating_binding_id: id,
      trace_ids: clone(record.requirement_trace_ids),
      case_family_ids: clone(record.case_family_ids),
      dependency_domains: clone(C05_DOMAINS),
      scope_relationship: "UNASSESSED",
      scientific_applicability: "UNASSESSED",
      scientific_review_reasons: [],
      use_or_rights_status: "UNRESOLVED",
      rights_review_reasons: [],
      assessment_basis:
        "Exact source-owned C-05 request/result bytes bound by the accepted reader.",
      rationale:
        "Public DEVELOPMENT fixed-case evidence; scientific limits and uncertainty remain unresolved.",
      invalidated_by: [],
      source_claimed_provenance: "NATIVE_IMPORTED_RESULT",
      origin_verification: "PINNED_C05_FIXTURE_VERIFIED",
      status_provenance: "NATIVE_IMPORTED_RESULT",
    };
  }
  function sameC05Core(binding, canonical) {
    const keys = [
      "evidence_kind",
      "source_ref",
      "source_digest_or_identity",
      "design_id",
      "design_revision",
      "trace_ids",
      "case_family_ids",
      "dependency_domains",
    ];
    return keys.every(
      (key) => JSON.stringify(binding[key]) === JSON.stringify(canonical[key]),
    );
  }
  function validateStoredEvidenceBinding(
    binding,
    design,
    verifiedC05Records = [],
  ) {
    const checked = validateEvidenceBindingBase(binding, design);
    if (
      checked.origin_verification === "PINNED_C05_FIXTURE_VERIFIED" ||
      checked.status_provenance === "NATIVE_IMPORTED_RESULT"
    ) {
      if (
        !verifiedC05Records.some((record) =>
          sameC05Core(checked, c05Binding(record, design)),
        )
      )
        throw Error(
          "Native evidence provenance lacks an exact verified C-05 source record",
        );
    }
    if (
      checked.scientific_applicability === "SOURCE_OWNER_CONFIRMED" ||
      checked.use_or_rights_status === "SOURCE_AUTHORIZED"
    )
      throw Error("Source-owner authority interface is not implemented");
    return checked;
  }
  function selectRoute(design, route, values = {}) {
    if (design.status !== "DRAFT")
      throw Error("Sealed design route requires a new revision");
    const allowed = Object.keys(newRoutePlan()).filter(
      (key) => key !== "route",
    );
    if (Object.keys(values).some((key) => !allowed.includes(key)))
      throw Error("Unsupported route-plan field");
    const next = {
      ...newRoutePlan(),
      ...clone(design.route_plan),
      ...clone(values),
      route,
    };
    if (route === "UNASSESSED") Object.assign(next, newRoutePlan());
    else next.status_provenance = "LOCAL_MANUAL_ASSERTION";
    validateRoutePlan(next, design);
    design.route_plan = next;
    return clone(next);
  }
  function addEvidenceBinding(design, binding) {
    if (design.status !== "DRAFT") throw Error("Sealed design is immutable");
    const checked = validateEvidenceBinding(binding, design),
      prior = design.evidence_bindings.find(
        (item) => item.evidence_binding_id === checked.evidence_binding_id,
      );
    if (prior) {
      if (JSON.stringify(prior) === JSON.stringify(checked))
        return { disposition: "DEDUPLICATED", binding: clone(prior) };
      throw Error("Conflicting evidence binding identity");
    }
    design.evidence_bindings.push(checked);
    return { disposition: "ADDED", binding: clone(checked) };
  }
  function bindC05Record(design, record) {
    if (!Array.isArray(design.evidence_bindings)) return null;
    const verifier = root.CarbonC05Evidence;
    if (
      !verifier ||
      typeof verifier.isVerifiedRecord !== "function" ||
      !verifier.isVerifiedRecord(record)
    )
      throw Error(
        "Native C-05 binding requires the exact verified reader path",
      );
    const checked = validateEvidenceBindingBase(
        c05Binding(record, design),
        design,
      ),
      prior = design.evidence_bindings.find(
        (item) => item.evidence_binding_id === checked.evidence_binding_id,
      );
    if (prior) {
      if (JSON.stringify(prior) === JSON.stringify(checked))
        return { disposition: "DEDUPLICATED", binding: clone(prior) };
      throw Error("Conflicting evidence binding identity");
    }
    design.evidence_bindings.push(checked);
    return { disposition: "ADDED", binding: clone(checked) };
  }
  function changedDomains(field) {
    if (!Object.hasOwn(FIELD_DOMAINS, field))
      throw Error("Unsupported or unmapped change field: " + field);
    return clone(FIELD_DOMAINS[field]);
  }
  function reasonFor(design, field, domain, kind) {
    return {
      reason_id: ["review", kind, design.revision, field, domain].join(":"),
      domain,
      field,
      originating_design_id: design.design_id,
      originating_revision: design.revision,
      basis:
        "The " +
        field +
        " mutation affects the binding's declared " +
        domain +
        " dependency.",
    };
  }
  function addReason(target, reason) {
    if (!target.some((item) => item.reason_id === reason.reason_id))
      target.push(reason);
  }
  function applyImpactToBinding(binding, domains, field, design) {
    const intersection = binding.dependency_domains.filter((domain) =>
      domains.includes(domain),
    );
    const useDomains = [
      "RIGHTS",
      "DEPLOYMENT",
      "INTENDED_USE",
      "COMMERCIAL_CONTEXT",
      "CPES_DISCLOSURE",
    ];
    const scientific = intersection.filter(
        (domain) => !useDomains.includes(domain),
      ),
      rights = intersection.filter((domain) => useDomains.includes(domain));
    if (scientific.length) {
      binding.scope_relationship = "CHANGED";
      binding.scientific_applicability = "REVIEW_REQUIRED";
      for (const domain of scientific)
        addReason(
          binding.scientific_review_reasons,
          reasonFor(design, field, domain, "SCI"),
        );
      if (!binding.invalidated_by.includes(field))
        binding.invalidated_by.push(field);
    } else if (binding.scope_relationship === "UNASSESSED")
      binding.scope_relationship = "UNCHANGED";
    if (rights.length) {
      for (const domain of rights)
        addReason(
          binding.rights_review_reasons,
          reasonFor(design, field, domain, "RIGHTS"),
        );
      if (binding.use_or_rights_status !== "PROHIBITED")
        binding.use_or_rights_status = "REVIEW_REQUIRED";
      if (!binding.invalidated_by.includes(field))
        binding.invalidated_by.push(field);
    }
    if (binding.scientific_review_reasons.length)
      binding.scientific_applicability = "REVIEW_REQUIRED";
    if (
      binding.rights_review_reasons.length &&
      binding.use_or_rights_status !== "PROHIBITED"
    )
      binding.use_or_rights_status = "REVIEW_REQUIRED";
    const debts =
      binding.scientific_review_reasons.length +
      binding.rights_review_reasons.length;
    binding.assessment_basis = debts
      ? "Cumulative review obligations retained from exact recorded mutations."
      : "No declared dependency was affected by this mutation; the prior assessment remains unchanged.";
    binding.rationale = debts
      ? domains.includes("POPULATION_CASES") &&
        binding.evidence_kind === "FIXED_CASE_RESULT"
        ? "The exact fixed-case observation remains historical; it cannot support the changed population claim without review."
        : "Source evidence remains retained while all outstanding scoped obligations remain visible."
      : "Unchanged relationship recorded without changing scientific or rights assessment.";
    return binding;
  }
  function applyChangeImpact(design, field) {
    const domains = changedDomains(field);
    for (const binding of design.evidence_bindings)
      applyImpactToBinding(binding, domains, field, design);
    return domains;
  }
  function carryEvidenceBindings(parent, child) {
    const source = clone(parent.evidence_bindings || []);
    for (const record of parent.measurement_evidence || []) {
      const candidate = c05Binding(record, parent);
      if (
        !source.some(
          (item) =>
            item.source_digest_or_identity ===
            candidate.source_digest_or_identity,
        )
      )
        source.push(candidate);
    }
    return source.map((binding, index) => ({
      ...binding,
      evidence_binding_id:
        "carry-" +
        child.revision +
        "-" +
        (index + 1) +
        "-" +
        binding.evidence_binding_id,
      design_id: child.design_id,
      design_revision: child.revision,
      scope_relationship: ["CHANGED", "UNKNOWN"].includes(
        binding.scope_relationship,
      )
        ? binding.scope_relationship
        : "UNCHANGED",
      assessment_basis:
        "Parent evidence and cumulative obligations retained on the child revision.",
      rationale:
        "No new material delta has yet been recorded; inherited assessments, restrictions, and review reasons remain unchanged.",
      origin_verification: "WORKBENCH_DERIVED_LINEAGE",
      status_provenance: "WORKBENCH_DERIVED",
    }));
  }
  function linkExternalRecord(design, record) {
    if (design.status !== "DRAFT") throw Error("Sealed design is immutable");
    const checked = validateExternalRecord(record),
      prior = design.coordination.external_records.find(
        (item) => item.record_id === checked.record_id,
      );
    if (prior) {
      if (JSON.stringify(prior) === JSON.stringify(checked))
        return { disposition: "DEDUPLICATED", record: clone(prior) };
      throw Error("Conflicting external record identity");
    }
    design.coordination.external_records.push(checked);
    if (!design.coordination.current_action_ref && design.handoffs.length === 0)
      design.coordination.current_action_ref = checked.record_id;
    return { disposition: "LINKED", record: clone(checked) };
  }

  function actionRecords(design) {
    return [
      ...design.handoffs.map((item) => ({
        id: item.request_id,
        kind: "HANDOFF",
        status: item.status,
        provenance:
          item.route === "VERIFIED_CONNECTOR"
            ? "NATIVE_IMPORTED_RESULT"
            : "LOCAL_MANUAL_ASSERTION",
      })),
      ...design.coordination.external_records.map((item) => ({
        id: item.record_id,
        kind: "EXTERNAL",
        status: item.status,
        provenance: "EXTERNAL_LINKED_RECORD",
      })),
    ];
  }
  function actionResolution(design) {
    const records = actionRecords(design),
      currentRef = design.coordination.current_action_ref;
    let current = null;
    if (currentRef) {
      current = records.find((item) => item.id === currentRef);
      if (!current)
        return {
          kind: "RECONCILE",
          record: null,
          records,
          returned: [],
          reason: "The explicit current-action reference does not resolve.",
        };
    } else if (records.length === 1) current = records[0];
    else if (records.length > 1)
      return {
        kind: "RECONCILE",
        record: null,
        records,
        returned: records.filter((item) =>
          ["RETURNED", "EXECUTED", "FAILED", "OWNER_DECISION"].includes(
            item.status,
          ),
        ),
        reason:
          "Multiple action records have no explicit current-action relationship.",
      };
    if (!current)
      return design.coordination.blocker
        ? { kind: "MANUAL_BLOCKER", record: null, records, returned: [] }
        : { kind: "NONE", record: null, records, returned: [] };
    if (current.status === "EXECUTION_REPORTED_ACTIVE")
      return { kind: "ACTIVE", record: current, records, returned: [] };
    if (
      [
        "EXPORTED",
        "EXPORTED_OWNER_REQUEST",
        "SENT",
        "ACKNOWLEDGED",
        "BLOCKED",
      ].includes(current.status)
    )
      return { kind: "WAITING", record: current, records, returned: [] };
    if (current.status === "PREPARED")
      return { kind: "PREPARED", record: current, records, returned: [] };
    return { kind: "RETURNED", record: current, records, returned: [current] };
  }
  function routeAction(job, design) {
    const plan = design.route_plan;
    if (plan.route === "UNASSESSED")
      return {
        action: "CHOOSE_PLANNING_ROUTE",
        why: "No exact-revision planning route has been selected.",
        missing_conditions: ["route"],
      };
    if (!job.accountable_owner)
      return {
        action: "NAME_ACCOUNTABLE_OWNER",
        why: "The lead cannot also stand in for business/technical disposition ownership.",
        missing_conditions: ["accountable_owner"],
      };
    if (plan.route === "USE_EXISTING_CAPABILITY") {
      if (plan.unresolved_conditions.length)
        return {
          action: "REVIEW_INTENDED_USE_APPLICABILITY",
          why: "The referenced capability is not automatically qualified for this use.",
          missing_conditions: clone(plan.unresolved_conditions),
        };
      if (design.scope.rights_scope === "UNRESOLVED")
        return {
          action: "RESOLVE_RIGHTS",
          why: "Scientific relevance and use authorization are separate.",
          missing_conditions: ["rights/use status"],
        };
      return {
        action: "REQUEST_DEPLOYMENT_OR_OWNER_DISPOSITION",
        why: "Capability and scope are bound; customer/deployment applicability remains unresolved.",
        missing_conditions: [plan.next_decision || "owner disposition"],
      };
    }
    if (plan.route === "ADAPT_SUPPORTED_CHALLENGE") {
      const affected = design.evidence_bindings.filter(
        (item) =>
          item.scientific_review_reasons.length ||
          item.rights_review_reasons.length,
      );
      if (!plan.route_basis)
        return {
          action: "DESCRIBE_SUPPORTED_CHALLENGE_DELTA",
          why: "Selective reuse requires an exact delta from the source Challenge.",
          missing_conditions: ["route_basis"],
        };
      if (affected.length)
        return {
          action: "REVIEW_AFFECTED_EVIDENCE_BINDINGS",
          why: "Cumulative obligations remain for bindings whose dependencies changed.",
          missing_conditions: affected.map((item) => item.evidence_binding_id),
        };
      if (design.authoring.compatibility !== "EXACT_SUPPORTED")
        return {
          action: "RUN_NATIVE_AUTHORING_SEMANTIC_COMPARISON",
          why: "The supported adapter must preserve the exact intended semantics.",
          missing_conditions: ["intent-preserving authoring receipt"],
        };
      return {
        action: "REQUEST_MISSING_OWNER_DECISION",
        why: "Structural adaptation is assembled without creating qualification.",
        missing_conditions: [plan.next_decision || "source-owner decision"],
      };
    }
    if (!job.lead)
      return {
        action: "ASSIGN_FEASIBILITY_LEAD",
        why: "One named lead is required for the bounded feasibility question.",
        missing_conditions: ["lead"],
      };
    if (!plan.bounded_question || !plan.stop_condition || !plan.restart_event)
      return {
        action: "DEFINE_BOUNDED_FEASIBILITY_QUESTION",
        why: "Unsupported physics must not open a full qualification program by default.",
        missing_conditions: [
          "bounded_question",
          "stop_condition",
          "restart_event",
        ],
      };
    if (!design.handoffs.length)
      return {
        action: "ISSUE_ONE_BOUNDED_HANDOFF",
        why: "The feasibility question is frozen and ready for one lead.",
        missing_conditions: ["one exported handoff"],
      };
    return {
      action: "REVIEW_FEASIBILITY_RETURN",
      why: "A returned bounded finding may support revise, reroute, park, or continue.",
      missing_conditions: [plan.next_decision || "owner disposition"],
    };
  }
  function nextAction(job, design) {
    const assessment = design.source_assessments,
      assessmentRequest = assessment?.requests?.find(
        (item) => item.request_id === assessment.current_request_id,
      ),
      assessmentReceipt = assessment?.receipts?.find(
        (item) => item.request_id === assessment.current_request_id,
      );
    if (assessmentReceipt)
      return {
        action: "REVIEW_SCOPED_SOURCE_ASSESSMENT",
        why:
          "A repository-snapshot-matched technical answer is retained; remaining scientific, rights, and customer-use obligations stay separate. Open response questions: " +
          (assessmentReceipt.remaining_question_ids.join(", ") || "none") +
          ".",
        missing_conditions: [
          ...assessmentReceipt.remaining_question_ids.map(
            (item) => "question:" + item,
          ),
          ...assessmentReceipt.remaining_reason_ids.map(
            (item) => "review_reason:" + item,
          ),
        ],
      };
    if (assessmentRequest)
      return {
        action: "WAIT_FOR_EXACT_RYAN_ADOPTION",
        why: "The exact request is prepared locally, but no source assessment is admitted by the installed repository snapshot.",
        missing_conditions: [
          "Ryan adoption of exact assessment bytes",
          "Engineering admission in a later accepted repository snapshot",
        ],
      };
    const resolved = actionResolution(design);
    if (resolved.kind === "RECONCILE")
      return {
        action: "RECONCILE_ACTION_STATE",
        why: resolved.reason,
        missing_conditions: resolved.records.map(
          (item) => item.kind + ":" + item.id + ":" + item.status,
        ),
      };
    if (resolved.kind === "ACTIVE")
      return {
        action: "MONITOR_REPORTED_ACTIVE_WORK",
        why: "Execution is explicitly reported active for the named request; this is not scientific acceptance.",
        missing_conditions: [resolved.record.id + " return or failure"],
      };
    if (resolved.kind === "WAITING")
      return {
        action: "WAIT_FOR_RESTART_EVENT",
        why: "The named request is waiting; export, send, acknowledgment, or block does not establish execution or approval.",
        missing_conditions: [
          design.coordination.restart_event ||
            design.route_plan.restart_event ||
            "named owner response",
        ],
      };
    if (resolved.kind === "PREPARED")
      return {
        action: "EXPORT_PREPARED_REQUEST",
        why: "The request is prepared locally and has not been delivered.",
        missing_conditions: [resolved.record.id + " export/delivery"],
      };
    if (resolved.kind === "RETURNED")
      return {
        action: "REVIEW_RETURNED_EVIDENCE",
        why: "Returned or failed work is historical evidence and now needs an explicit interpretation or owner disposition.",
        missing_conditions: [
          design.coordination.decision_needed ||
            design.route_plan.next_decision ||
            "owner interpretation",
        ],
      };
    if (resolved.kind === "MANUAL_BLOCKER") {
      const scoped = routeAction(job, design);
      return {
        action: scoped.action,
        why:
          scoped.why +
          " A local blocker is recorded for this scoped action; it is not native execution evidence.",
        missing_conditions: [
          ...scoped.missing_conditions,
          design.coordination.restart_event ||
            "reconcile blocker with a named action",
        ],
      };
    }
    return routeAction(job, design);
  }
  function evidenceAxis(design) {
    const currentNative = design.measurement_evidence.some(
      (item) =>
        item.binding_status === "CURRENT_DESIGN_REVISION" &&
        item.evidence_state === "SOURCE_MEASUREMENT_EVIDENCE_BOUND",
    );
    const resolvedTechnicalReasons = new Set(
        (design.source_assessments?.dispositions || [])
          .filter((item) => item.effect === "TECHNICAL_REASON_RESOLVED")
          .map((item) => item.reason_id),
      ),
      review = design.evidence_bindings.filter((item) => {
        const unresolvedScientific = item.scientific_review_reasons.filter(
          (reason) => !resolvedTechnicalReasons.has(reason.reason_id),
        );
        return (
          unresolvedScientific.length ||
          item.rights_review_reasons.length ||
          (item.scientific_applicability === "REVIEW_REQUIRED" &&
            item.scientific_review_reasons.length === 0)
        );
      }),
      sourceConfirmed = design.evidence_bindings.some(
        (item) => item.scientific_applicability === "SOURCE_OWNER_CONFIRMED",
      ),
      facts = [];
    if (design.source_assessments?.receipts?.length)
      facts.push("REPOSITORY_SNAPSHOT_TECHNICAL_ASSESSMENT_RETAINED");
    if (resolvedTechnicalReasons.size)
      facts.push("SCOPED_TECHNICAL_REASON_DISPOSITION_RETAINED");
    if (currentNative) facts.push("EXACT_C05_SOURCE_RESULT_RETAINED");
    if (review.length) facts.push("OUTSTANDING_SCOPED_REVIEW");
    if (sourceConfirmed) facts.push("APPLICABILITY_CONFIRMED_NOT_QUALIFIED");
    if (review.length)
      return {
        state: "UNDER_REVIEW",
        provenance: "WORKBENCH_DERIVED",
        source: "cumulative change-impact obligations",
        facts,
        outstanding_binding_ids: review.map((item) => item.evidence_binding_id),
      };
    if (currentNative)
      return {
        state: "SOURCE_EXECUTED_UNRESOLVED",
        provenance: "NATIVE_IMPORTED_RESULT",
        source: "C-05 exact retained source result",
        facts,
        outstanding_binding_ids: [],
      };
    if (
      design.evidence_bindings.length ||
      design.requirements.length ||
      design.traces.length
    )
      return {
        state: "STRUCTURAL_ONLY",
        provenance: "WORKBENCH_DERIVED",
        source: sourceConfirmed
          ? "scoped applicability does not establish qualification"
          : "local design structure",
        facts,
        outstanding_binding_ids: [],
      };
    return {
      state: "MISSING",
      provenance: "WORKBENCH_DERIVED",
      source: "no evidence bound",
      facts,
      outstanding_binding_ids: [],
    };
  }
  function workflowAxis(job, design) {
    if (design.coordination.customer_outcome === "CLOSED")
      return {
        state: "CLOSED",
        provenance: design.coordination.customer_outcome_provenance,
        source: "customer outcome",
      };
    if (design.coordination.customer_outcome === "PARKED")
      return {
        state: "PARKED",
        provenance: design.coordination.customer_outcome_provenance,
        source: "customer outcome",
      };
    const resolved = actionResolution(design),
      action = nextAction(job, design);
    if (action.action === "WAIT_FOR_EXACT_RYAN_ADOPTION")
      return {
        state: "WAITING_ON_DEPENDENCY",
        provenance: "WORKBENCH_DERIVED",
        source: design.source_assessments.current_request_id,
      };
    if (action.action === "REVIEW_SCOPED_SOURCE_ASSESSMENT")
      return {
        state: "NEEDS_OWNER_DECISION",
        provenance: "NATIVE_IMPORTED_RESULT",
        source: design.source_assessments.current_request_id,
      };
    if (resolved.kind === "ACTIVE")
      return {
        state: "ACTIVE_REPORTED",
        provenance: resolved.record.provenance,
        source: resolved.record.id + " explicitly reports active execution",
      };
    if (resolved.kind === "WAITING")
      return {
        state: "WAITING_ON_DEPENDENCY",
        provenance: resolved.record.provenance,
        source: resolved.record.id + " is " + resolved.record.status,
      };
    if (["RETURNED", "RECONCILE"].includes(resolved.kind))
      return {
        state: "NEEDS_OWNER_DECISION",
        provenance: resolved.record?.provenance || "WORKBENCH_DERIVED",
        source: action.action,
      };
    if (resolved.kind === "MANUAL_BLOCKER")
      return {
        state: "WAITING_ON_DEPENDENCY",
        provenance: "LOCAL_MANUAL_ASSERTION",
        source: action.action,
      };
    if (
      ["CHOOSE_PLANNING_ROUTE", "NAME_ACCOUNTABLE_OWNER"].includes(
        action.action,
      )
    )
      return {
        state: "NEEDS_OWNER_DECISION",
        provenance: "WORKBENCH_DERIVED",
        source: action.action,
      };
    if (planIsEmpty(design.route_plan))
      return {
        state: "NOT_STARTED",
        provenance: "WORKBENCH_DERIVED",
        source: "empty route plan",
      };
    return {
      state: "READY_FOR_ACTION",
      provenance: "WORKBENCH_DERIVED",
      source: action.action,
    };
  }
  function planIsEmpty(plan) {
    return plan.route === "UNASSESSED" && !plan.rationale && !plan.route_basis;
  }
  function attentionBucket(workflow) {
    if (workflow === "NEEDS_OWNER_DECISION") return "NEEDS_DECISION";
    if (["READY_FOR_ACTION", "NOT_STARTED"].includes(workflow))
      return "READY_FOR_ACTION";
    if (["ACTIVE_REPORTED", "ACTIVE_NATIVE_EVIDENCE"].includes(workflow))
      return "ACTIVE";
    if (workflow === "WAITING_ON_DEPENDENCY") return "WAITING";
    return "CLOSED_OR_PARKED";
  }
  function ownerSummary(job, design) {
    const workflow = workflowAxis(job, design),
      evidence = evidenceAxis(design),
      action = nextAction(job, design),
      resolved = actionResolution(design);
    return {
      job_id: job.job_id,
      client_job: job.title,
      design_id: design.design_id,
      design_revision: design.revision,
      route: design.route_plan.route,
      accountable_owner: job.accountable_owner,
      lead: job.lead,
      current_action: action.action,
      current_action_ref:
        design.source_assessments?.current_request_id ||
        resolved.record?.id || "UNLINKED_OR_RECONCILIATION_REQUIRED",
      action_reason: action.why,
      missing_conditions: action.missing_conditions,
      workflow_state: workflow.state,
      workflow_provenance: workflow.provenance,
      workflow_source: workflow.source,
      evidence_state: evidence.state,
      evidence_provenance: evidence.provenance,
      evidence_source: evidence.source,
      evidence_facts: evidence.facts,
      outstanding_evidence_bindings: evidence.outstanding_binding_ids,
      customer_outcome: design.coordination.customer_outcome,
      customer_outcome_provenance:
        design.coordination.customer_outcome_provenance,
      open_request_or_handoff: design.source_assessments?.current_request_id
        ? design.source_assessments.receipts.some(
            (item) =>
              item.request_id === design.source_assessments.current_request_id,
          )
          ? "SOURCE_ASSESSMENT_RETURNED"
          : "PREPARED_AWAITING_EXACT_OWNER_ADOPTION"
        : resolved.record
        ? resolved.record.status
        : resolved.kind === "RECONCILE"
          ? "RECONCILIATION_REQUIRED"
          : "NONE",
      evidence_received: design.source_assessments?.receipts?.some(
        (item) => item.request_id === design.source_assessments.current_request_id,
      )
        ? "YES_SCOPED_SOURCE_ASSESSMENT"
        : design.measurement_evidence.some(
        (item) => item.binding_status === "CURRENT_DESIGN_REVISION",
      )
        ? "YES_SCOPED_UNRESOLVED"
        : "NO_CURRENT_NATIVE_RESULT",
      decision_needed:
        design.coordination.decision_needed || design.route_plan.next_decision,
      blocker: design.coordination.blocker,
      blocker_owner: design.coordination.blocker_owner,
      restart_event:
        design.coordination.restart_event || design.route_plan.restart_event,
      last_relevant_design_revision:
        design.coordination.last_relevant_design_revision,
      attention_bucket: attentionBucket(workflow.state),
      qualification_effect: "NONE_NO_QUALIFICATION_READER_IMPLEMENTED",
    };
  }
  function ownerConsole(workspace) {
    const rows = workspace.jobs.map((job) => {
      const selected = job.designs.find(
        (design) => design.design_id === job.working_design_id,
      );
      if (selected) return ownerSummary(job, selected);
      return {
        job_id: job.job_id,
        client_job: job.title,
        design_id: "UNSELECTED",
        design_revision: 0,
        route: "UNASSESSED",
        accountable_owner: job.accountable_owner,
        lead: job.lead,
        current_action: "SELECT_WORKING_DESIGN",
        current_action_ref: "UNLINKED_OR_RECONCILIATION_REQUIRED",
        action_reason:
          "Multiple historical alternatives exist without an explicit working-design selection.",
        missing_conditions: ["working_design_id"],
        workflow_state: "NEEDS_OWNER_DECISION",
        workflow_provenance: "WORKBENCH_DERIVED",
        workflow_source: "SELECT_WORKING_DESIGN",
        evidence_state: "MISSING",
        evidence_provenance: "WORKBENCH_DERIVED",
        evidence_source: "no design selected for projection",
        evidence_facts: [],
        outstanding_evidence_bindings: [],
        customer_outcome: "OPEN",
        customer_outcome_provenance: "WORKBENCH_DERIVED",
        open_request_or_handoff: "RECONCILIATION_REQUIRED",
        evidence_received: "UNKNOWN_UNTIL_WORKING_DESIGN_SELECTED",
        decision_needed: "Select the exact design revision to summarize.",
        blocker: "Working design is not explicit.",
        blocker_owner: job.accountable_owner,
        restart_event: "Owner selects one exact design revision.",
        last_relevant_design_revision: 0,
        attention_bucket: "NEEDS_DECISION",
        qualification_effect: "NONE_NO_QUALIFICATION_READER_IMPLEMENTED",
      };
    });
    const counts = Object.fromEntries(
      ATTENTION_BUCKETS.map((bucket) => [
        bucket,
        rows.filter((row) => row.attention_bucket === bucket).length,
      ]),
    );
    return {
      rows,
      counts,
      authority:
        "Attention grouping only; no priority score, percent complete, qualification, approval, or launch authority.",
    };
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
    SCOPE_RELATIONSHIPS,
    RIGHTS_STATUS,
    ORIGIN_VERIFICATION,
    EXTERNAL_RECORD_STATES,
    FIELD_DOMAINS,
    C05_DOMAINS,
    MINIMUM_DEPENDENCIES,
    newRoutePlan,
    newCoordination,
    validateRoutePlan,
    validateCoordination,
    validateEvidenceBinding,
    validateStoredEvidenceBinding,
    validateExternalRecord,
    selectRoute,
    addEvidenceBinding,
    c05Binding,
    bindC05Record,
    changedDomains,
    applyChangeImpact,
    carryEvidenceBindings,
    linkExternalRecord,
    actionResolution,
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
