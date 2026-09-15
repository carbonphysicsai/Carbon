(function (root) {
  "use strict";

  const F = root.CarbonFit ||
    (typeof require !== "undefined" ? require("./engine.js") : null);
  const PROFILE_ID = "burgers-dynamics-public.repository-snapshot.v1";
  const REQUEST_VERSION = "carbon.goal-workbench.source-assessment-request.v2";
  const RESPONSE_VERSION = "carbon.goal-workbench.source-assessment-response.v2";
  const RECEIPT_VERSION = "carbon.goal-workbench.source-assessment-receipt.v1";
  const STATE_VERSION = "carbon.goal-workbench.source-assessment-state.v1";
  const SNAPSHOT_VERSION = "carbon.goal-workbench.approved-assessment-snapshot.v1";
  const SUBJECT_VERSION = "carbon.goal-workbench.assessment-subject.v1";
  const PROFILE_VERSION = "carbon.goal-workbench.repository-snapshot-profile.v1";
  const TECHNICAL_DOMAINS = [
    "AUTHORING_EXPRESSIBILITY",
    "SOURCE_ARTIFACT_IDENTITY",
    "FIXED_EVIDENCE_RELATIONSHIP",
  ];
  const RESOLVABLE_REASON_DOMAINS = Object.freeze({
    AUTHORING_EXPRESSIBILITY: Object.freeze(["AUTHORING"]),
    SOURCE_ARTIFACT_IDENTITY: Object.freeze([]),
    FIXED_EVIDENCE_RELATIONSHIP: Object.freeze([]),
  });
  const AUTHORITY_CEILING = {
    scientific_qualification: false,
    rights_authorization: false,
    fresh_execution: false,
    score_eligibility: false,
    protected_reuse: false,
    launch_authorization: false,
  };
  const clone = (value) => JSON.parse(JSON.stringify(value));
  function exact(value, keys, label) {
    const proto = value && Object.getPrototypeOf(value);
    if (!value || (proto !== Object.prototype && proto !== null))
      throw Error(label + " must be a plain object");
    const got = Object.keys(value).sort(), expected = [...keys].sort();
    if (got.length !== expected.length || got.some((key, index) => key !== expected[index]))
      throw Error(label + " has unknown or missing fields");
    return value;
  }
  function text(value, label, max = 8000, empty = false) {
    if (typeof value !== "string" || value.length > max || (!empty && !value))
      throw Error("Invalid " + label);
    return value;
  }
  function id(value, label) {
    if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$/.test(value))
      throw Error("Invalid " + label);
    return value;
  }
  function list(value, label, max = 128) {
    if (!Array.isArray(value) || value.length > max) throw Error("Invalid " + label);
    return value;
  }
  function enumValue(value, values, label) {
    if (!values.includes(value)) throw Error("Invalid " + label);
    return value;
  }
  function sorted(value) {
    if (Array.isArray(value)) return value.map(sorted);
    if (
      value &&
      (Object.getPrototypeOf(value) === Object.prototype ||
        Object.getPrototypeOf(value) === null)
    ) {
      const out = {};
      for (const key of Object.keys(value).sort()) out[key] = sorted(value[key]);
      return out;
    }
    return value;
  }
  const canonical = (value) => JSON.stringify(sorted(value));
  const hex = (bytes) => [...new Uint8Array(bytes)].map((x) => x.toString(16).padStart(2, "0")).join("");
  async function sha256(raw) {
    if (typeof raw !== "string") throw Error("Hash input must be text");
    if (root.crypto?.subtle)
      return hex(await root.crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw)));
    if (typeof require !== "undefined")
      return require("node:crypto").createHash("sha256").update(raw, "utf8").digest("hex");
    throw Error("SHA-256 unavailable");
  }
  async function digest(value) { return "sha256:" + await sha256(canonical(value)); }

  function newState() {
    return { schema_version: STATE_VERSION, current_request_id: null, requests: [], responses: [], receipts: [], dispositions: [] };
  }
  function compactAuthoring(authoring) {
    const receipt = authoring.semantic_receipt;
    return {
      template_id: authoring.template_id,
      requested_goal: authoring.requested_goal,
      compatibility: authoring.compatibility,
      request_id: authoring.request_id,
      result_ref: authoring.result_ref,
      semantic_receipt: receipt ? {
        schema_version: receipt.schema_version,
        request_id: receipt.request_id,
        job_id: receipt.job_id,
        design_id: receipt.design_id,
        design_revision: receipt.design_revision,
        input_digest: receipt.input_digest,
        proposal_digest: receipt.proposal_digest,
        status: receipt.status,
        qualification: receipt.qualification,
        launch: receipt.launch,
      } : null,
      extension_request: clone(authoring.extension_request),
    };
  }
  function scopeSubject(design) {
    return {
      schema_version: SUBJECT_VERSION,
      job_id: design.job_id,
      design_id: design.design_id,
      design_revision: design.revision,
      route: design.route_plan.route,
      scope: clone(design.scope),
      requirements: clone(design.requirements),
      traces: clone(design.traces),
      cases: clone(design.cases),
      authoring: compactAuthoring(design.authoring),
      reference_plan: clone(design.reference_plan),
      evidence_bindings: design.evidence_bindings.map((binding) => ({
        evidence_binding_id: binding.evidence_binding_id,
        source_digest_or_identity: binding.source_digest_or_identity,
        originating_design_id: binding.originating_design_id,
        originating_design_revision: binding.originating_design_revision,
        trace_ids: clone(binding.trace_ids),
        case_family_ids: clone(binding.case_family_ids),
        dependency_domains: clone(binding.dependency_domains),
        scientific_applicability: binding.scientific_applicability,
        scientific_review_reasons: clone(binding.scientific_review_reasons),
        use_or_rights_status: binding.use_or_rights_status,
        rights_review_reasons: clone(binding.rights_review_reasons),
      })),
    };
  }
  function supportedSubject(subject) {
    return subject.scope.physics_family === "periodic_viscous_burgers_1d_v1" &&
      subject.scope.requested_goal === "Dynamics" &&
      subject.authoring.template_id === "periodic_viscous_burgers_1d_v1" &&
      subject.authoring.requested_goal === "Dynamics";
  }
  async function buildRequest(design, requestId) {
    if (design.status !== "SEALED") throw Error("Assessment subject must be sealed");
    const subject = scopeSubject(design);
    if (!supportedSubject(subject)) throw Error("Unsupported source-assessment profile scope");
    const authoringReasons = [...new Set(design.evidence_bindings.flatMap((binding) =>
      binding.scientific_review_reasons
        .filter((reason) => reason.domain === "AUTHORING")
        .map((reason) => reason.reason_id)))].sort();
    const questions = [
      { question_id: "GW07:AUTHORING_EXPRESSIBILITY", domain: "AUTHORING_EXPRESSIBILITY", text: "Does the named authoring artifact express the exact requested Dynamics task?", reason_ids: authoringReasons },
      { question_id: "GW07:SOURCE_ARTIFACT_IDENTITY", domain: "SOURCE_ARTIFACT_IDENTITY", text: "Do the named accepted authoring and retained C-05 identities match the recorded source artifacts?", reason_ids: [] },
      { question_id: "GW07:FIXED_EVIDENCE_RELATIONSHIP", domain: "FIXED_EVIDENCE_RELATIONSHIP", text: "What exact fixed-case technical relationship can the retained C-05 record support?", reason_ids: [] },
    ];
    return validateRequest({
      schema_version: REQUEST_VERSION,
      profile_id: PROFILE_ID,
      request_id: id(requestId, "request ID"),
      association: { job_id: design.job_id, design_id: design.design_id, design_revision: design.revision },
      subject,
      subject_digest: await digest(subject),
      source: {
        implementation_id: "periodic_viscous_burgers_1d_v1/Dynamics",
        authoring_result_ref: design.authoring.result_ref || "UNAVAILABLE",
        evidence_identity_refs: design.evidence_bindings.map((item) => item.source_digest_or_identity),
      },
      questions,
      permitted_information_scope: "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
      requested_recipient: "github:jbequ5",
      expected_result_or_restart: "Exact Ryan adoption or a named unsupported scope/blocker; no scientific or rights authority.",
      authority_ceiling: clone(AUTHORITY_CEILING),
    });
  }
  function validateAuthority(value, label) {
    exact(value, Object.keys(AUTHORITY_CEILING), label);
    for (const [key, expected] of Object.entries(AUTHORITY_CEILING))
      if (value[key] !== expected) throw Error("Authority escalation rejected");
  }
  function validateAssociation(value, label) {
    exact(value, ["job_id", "design_id", "design_revision"], label);
    id(value.job_id, label + " job"); id(value.design_id, label + " design");
    if (!Number.isSafeInteger(value.design_revision) || value.design_revision < 1) throw Error("Invalid design revision");
  }
  function validateQuestion(value) {
    exact(value, ["question_id", "domain", "text", "reason_ids"], "assessment question");
    id(value.question_id, "question ID"); enumValue(value.domain, TECHNICAL_DOMAINS, "question domain");
    text(value.text, "question text"); list(value.reason_ids, "question reasons").forEach((reason) => id(reason, "reason ID"));
    return clone(value);
  }
  function validateReason(value, label) {
    exact(value, ["reason_id", "domain", "field", "originating_design_id", "originating_revision", "basis"], label);
    id(value.reason_id, label + " ID"); text(value.domain, label + " domain"); text(value.field, label + " field", 500, true);
    id(value.originating_design_id, label + " originating design");
    if (!Number.isSafeInteger(value.originating_revision) || value.originating_revision < 1) throw Error("Invalid " + label + " revision");
    text(value.basis, label + " basis", 2000, true);
  }
  function validateSubject(value) {
    exact(value, ["schema_version", "job_id", "design_id", "design_revision", "route", "scope", "requirements", "traces", "cases", "authoring", "reference_plan", "evidence_bindings"], "assessment subject");
    if (value.schema_version !== SUBJECT_VERSION) throw Error("Unsupported subject version");
    id(value.job_id, "subject job"); id(value.design_id, "subject design");
    if (!Number.isSafeInteger(value.design_revision) || value.design_revision < 1) throw Error("Invalid subject revision");
    text(value.route, "subject route");
    const scopeKeys = ["physics_family", "requested_goal", "intended_use", "inputs", "outputs", "units", "geometry", "conditions", "regime", "exclusions", "query_workload", "turnaround", "failure_consequences", "data_access", "rights_scope", "commercial_context", "disclosure_scope", "deployment_environment"];
    exact(value.scope, scopeKeys, "subject scope"); Object.values(value.scope).forEach((item) => text(item, "subject scope value", 8000, true));
    const requirementKeys = ["requirement_id", "original_words", "source_reference", "decision_consequence", "kind", "agreement_status"];
    list(value.requirements, "subject requirements").forEach((item) => { exact(item, requirementKeys, "subject requirement"); id(item.requirement_id, "subject requirement ID"); for (const [key, entry] of Object.entries(item)) if (key !== "requirement_id") text(entry, "subject requirement " + key, 8000, true); });
    const traceKeys = ["trace_id", "requirement_id", "observable", "requested_output", "measurement_definition", "numerical_method", "role", "normalization", "floor", "aggregation", "uncertainty", "population_ref", "stratum_ref", "finite_case_coverage", "reference_requirement", "authoring_binding", "gap"];
    list(value.traces, "subject traces", 256).forEach((item) => { exact(item, traceKeys, "subject trace"); id(item.trace_id, "subject trace ID"); id(item.requirement_id, "subject trace requirement"); for (const [key, entry] of Object.entries(item)) if (!['trace_id', 'requirement_id'].includes(key)) text(entry, "subject trace " + key, 8000, true); });
    const caseKeys = ["case_family_id", "role", "requirement_ids", "target_population", "target_mass", "sampling_frequency", "analysis_weight", "independent_physical_cases", "reconstruction_replicas", "generator_ref", "rationale", "support_status"];
    list(value.cases, "subject cases").forEach((item) => { exact(item, caseKeys, "subject case"); id(item.case_family_id, "subject case ID"); list(item.requirement_ids, "subject case requirements").forEach((entry) => id(entry, "subject case requirement")); for (const [key, entry] of Object.entries(item)) if (!['case_family_id', 'requirement_ids'].includes(key)) text(entry, "subject case " + key, 8000, true); });
    exact(value.authoring, ["template_id", "requested_goal", "compatibility", "request_id", "result_ref", "semantic_receipt", "extension_request"], "subject authoring");
    for (const key of ["template_id", "requested_goal", "compatibility", "request_id", "result_ref"]) text(value.authoring[key], "subject authoring " + key, 1000, true);
    if (value.authoring.semantic_receipt !== null) {
      const receipt = value.authoring.semantic_receipt;
      exact(receipt, ["schema_version", "request_id", "job_id", "design_id", "design_revision", "input_digest", "proposal_digest", "status", "qualification", "launch"], "subject semantic receipt");
      for (const key of ["schema_version", "request_id", "job_id", "design_id", "input_digest", "proposal_digest", "status", "qualification", "launch"]) text(receipt[key], "subject semantic receipt " + key, 1000);
      if (!Number.isSafeInteger(receipt.design_revision) || receipt.design_revision < 1) throw Error("Invalid subject semantic receipt revision");
    }
    if (value.authoring.extension_request !== null) {
      exact(value.authoring.extension_request, ["schema_version", "request_id", "job_id", "design_id", "design_revision", "missing_capability", "client_rationale", "compatible_existing_components", "proposed_tests", "unresolved_scientific_choices", "owner_interface"], "subject extension request");
    }
    const referenceKeys = ["equation", "role", "method", "configuration", "convergence_evidence", "uncertainty_evidence", "applicable_envelope", "failures", "cost_scope", "independence_limitations"];
    exact(value.reference_plan, referenceKeys, "subject reference plan"); Object.values(value.reference_plan).forEach((item) => text(item, "subject reference value", 8000, true));
    list(value.evidence_bindings, "subject evidence bindings").forEach((binding) => {
      exact(binding, ["evidence_binding_id", "source_digest_or_identity", "originating_design_id", "originating_design_revision", "trace_ids", "case_family_ids", "dependency_domains", "scientific_applicability", "scientific_review_reasons", "use_or_rights_status", "rights_review_reasons"], "subject evidence binding");
      id(binding.evidence_binding_id, "subject binding ID"); text(binding.source_digest_or_identity, "subject evidence identity", 1000, true); id(binding.originating_design_id, "subject originating design");
      if (!Number.isSafeInteger(binding.originating_design_revision) || binding.originating_design_revision < 1) throw Error("Invalid subject originating revision");
      for (const key of ["trace_ids", "case_family_ids", "dependency_domains"]) list(binding[key], "subject binding " + key).forEach((item) => text(item, "subject binding value"));
      text(binding.scientific_applicability, "subject scientific applicability"); text(binding.use_or_rights_status, "subject rights status");
      list(binding.scientific_review_reasons, "subject scientific reasons").forEach((reason) => validateReason(reason, "subject scientific reason"));
      list(binding.rights_review_reasons, "subject rights reasons").forEach((reason) => validateReason(reason, "subject rights reason"));
    });
    return value;
  }
  function validateRequest(value) {
    exact(value, ["schema_version", "profile_id", "request_id", "association", "subject", "subject_digest", "source", "questions", "permitted_information_scope", "requested_recipient", "expected_result_or_restart", "authority_ceiling"], "source-assessment request");
    if (value.schema_version !== REQUEST_VERSION || value.profile_id !== PROFILE_ID) throw Error("Unsupported request profile/version");
    id(value.request_id, "request ID"); validateAssociation(value.association, "request association");
    validateSubject(value.subject);
    if (value.subject.job_id !== value.association.job_id || value.subject.design_id !== value.association.design_id || value.subject.design_revision !== value.association.design_revision) throw Error("Request subject association mismatch");
    if (!/^sha256:[a-f0-9]{64}$/.test(value.subject_digest)) throw Error("Invalid subject digest");
    exact(value.source, ["implementation_id", "authoring_result_ref", "evidence_identity_refs"], "request source");
    text(value.source.implementation_id, "source implementation"); text(value.source.authoring_result_ref, "authoring result ref");
    list(value.source.evidence_identity_refs, "evidence identity refs").forEach((item) => text(item, "evidence identity"));
    const questions = list(value.questions, "questions", 16).map(validateQuestion);
    if (!questions.length || new Set(questions.map((item) => item.question_id)).size !== questions.length) throw Error("Missing or duplicate questions");
    const knownScientificReasons = new Set(value.subject.evidence_bindings.flatMap((binding) => binding.scientific_review_reasons.map((reason) => reason.reason_id)));
    for (const question of questions) for (const reason of question.reason_ids) if (!knownScientificReasons.has(reason)) throw Error("Question references an unknown or rights-only reason");
    text(value.permitted_information_scope, "information scope"); id(value.requested_recipient, "requested recipient");
    text(value.expected_result_or_restart, "expected result"); validateAuthority(value.authority_ceiling, "request authority ceiling");
    return clone(value);
  }
  function validateResponse(value) {
    exact(value, ["schema_version", "profile_id", "response_id", "request_id", "request_digest", "association", "subject_digest", "prepared_by", "claimed_issuer", "result_kind", "answered", "unanswered_question_ids", "source_basis", "limitations", "supersedes_response_ids", "next_action", "authority_ceiling"], "source-assessment response");
    if (value.schema_version !== RESPONSE_VERSION || value.profile_id !== PROFILE_ID) throw Error("Unsupported response profile/version");
    id(value.response_id, "response ID"); id(value.request_id, "request ID");
    if (!/^sha256:[a-f0-9]{64}$/.test(value.request_digest) || !/^sha256:[a-f0-9]{64}$/.test(value.subject_digest)) throw Error("Invalid response digest");
    validateAssociation(value.association, "response association");
    text(value.prepared_by, "response preparer");
    exact(value.claimed_issuer, ["principal", "role", "claim_basis"], "claimed issuer");
    id(value.claimed_issuer.principal, "claimed issuer principal"); text(value.claimed_issuer.role, "claimed issuer role");
    enumValue(value.claimed_issuer.claim_basis, ["PRODUCER_CLAIM_UNVERIFIED", "REPOSITORY_ADOPTION_REFERENCE"], "issuer claim basis");
    enumValue(value.result_kind, ["SCOPED_ASSESSMENT", "PARTIAL_RESPONSE", "UNSUPPORTED_SCOPE", "NAMED_BLOCKER", "CORRECTION"], "result kind");
    const answers = list(value.answered, "answers", 16);
    answers.forEach((answer) => {
      exact(answer, ["question_id", "domain", "status", "statement", "addressed_reason_ids", "supporting_refs"], "answer");
      id(answer.question_id, "answer question"); enumValue(answer.domain, TECHNICAL_DOMAINS, "answer domain");
      enumValue(answer.status, ["ANSWERED", "PARTIAL", "UNSUPPORTED", "BLOCKED"], "answer status"); text(answer.statement, "answer statement");
      list(answer.addressed_reason_ids, "addressed reasons").forEach((item) => id(item, "addressed reason"));
      list(answer.supporting_refs, "supporting refs").forEach((item) => text(item, "supporting ref"));
    });
    const unanswered = list(value.unanswered_question_ids, "unanswered questions", 16);
    unanswered.forEach((item) => id(item, "unanswered question"));
    if (new Set(answers.map((answer) => answer.question_id)).size !== answers.length || new Set(unanswered).size !== unanswered.length) throw Error("Duplicate response question identity");
    if (answers.some((answer) => answer.status === "ANSWERED" && unanswered.includes(answer.question_id))) throw Error("Fully answered question cannot also be unanswered");
    list(value.source_basis, "source basis", 32).forEach((item) => text(item, "source basis"));
    list(value.limitations, "limitations", 32).forEach((item) => text(item, "limitation"));
    list(value.supersedes_response_ids, "supersession IDs", 16).forEach((item) => id(item, "superseded response"));
    text(value.next_action, "next action"); validateAuthority(value.authority_ceiling, "response authority ceiling");
    return clone(value);
  }
  function validateProfile(value, testMode = false) {
    exact(value, ["schema_version", "profile_id", "policy_decision_id", "verifier_implementation_id", "issuer_policy", "supported_scope", "trust_assumptions", "snapshot_id", "snapshot_as_of", "test_only"], "installed source-assessment profile");
    if (value.schema_version !== PROFILE_VERSION || value.profile_id !== PROFILE_ID) throw Error("Unsupported installed profile");
    id(value.policy_decision_id, "policy decision"); id(value.verifier_implementation_id, "verifier implementation");
    exact(value.issuer_policy, ["principal", "role", "allowed_domains", "adoption_required"], "issuer policy");
    if (value.issuer_policy.principal !== "github:jbequ5" || value.issuer_policy.role !== "FINAL_INTERFACE_OWNER" || value.issuer_policy.adoption_required !== true) throw Error("Unsupported issuer policy");
    list(value.issuer_policy.allowed_domains, "allowed domains").forEach((item) => enumValue(item, TECHNICAL_DOMAINS, "allowed domain"));
    exact(value.supported_scope, ["physics_family", "goal", "information_scope"], "supported scope");
    if (value.supported_scope.physics_family !== "periodic_viscous_burgers_1d_v1" || value.supported_scope.goal !== "Dynamics" || value.supported_scope.information_scope !== "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY") throw Error("Unsupported profile scope");
    list(value.trust_assumptions, "trust assumptions", 16).forEach((item) => text(item, "trust assumption"));
    id(value.snapshot_id, "snapshot ID"); text(value.snapshot_as_of, "snapshot as-of");
    if (typeof value.test_only !== "boolean" || (value.test_only && !testMode)) throw Error("Test trust root cannot be installed in production");
    return clone(value);
  }
  function validateIndex(value, profile, testMode = false) {
    exact(value, ["schema_version", "snapshot_id", "test_only", "entries"], "approved assessment index");
    if (value.schema_version !== SNAPSHOT_VERSION || value.snapshot_id !== profile.snapshot_id || typeof value.test_only !== "boolean" || value.test_only !== profile.test_only) throw Error("Installed snapshot mismatch");
    if (value.test_only && !testMode) throw Error("Test approved index cannot ship");
    list(value.entries, "approved entries", 128).forEach((entry) => {
      exact(entry, ["assessment_id", "request_id", "request_digest", "subject_digest", "response_raw_sha256", "response_canonical_digest", "issuer_principal", "allowed_domains", "owner_adoption_ref", "owner_adoption_content_digest", "state", "withdrawn_reason", "supersedes_assessment_ids", "conflicts_with_assessment_ids"], "approved entry");
      ["assessment_id", "request_id", "issuer_principal", "owner_adoption_ref"].forEach((key) => id(entry[key], "approved entry " + key));
      for (const key of ["request_digest", "subject_digest", "response_raw_sha256", "response_canonical_digest", "owner_adoption_content_digest"])
        if (!/^sha256:[a-f0-9]{64}$/.test(entry[key])) throw Error("Invalid approved entry digest");
      if (entry.issuer_principal !== profile.issuer_policy.principal) throw Error("Approved issuer outside profile");
      list(entry.allowed_domains, "entry domains").forEach((item) => enumValue(item, profile.issuer_policy.allowed_domains, "entry domain"));
      enumValue(entry.state, ["CURRENT", "WITHDRAWN", "SUPERSEDED", "CONFLICTING"], "entry state");
      text(entry.withdrawn_reason, "withdrawn reason", 2000, true);
      list(entry.supersedes_assessment_ids, "supersedes").forEach((item) => id(item, "superseded assessment"));
      list(entry.conflicts_with_assessment_ids, "conflicts").forEach((item) => id(item, "conflicting assessment"));
    });
    if (new Set(value.entries.map((entry) => entry.assessment_id)).size !== value.entries.length) throw Error("Duplicate approved assessment ID");
    return clone(value);
  }
  function validateState(value) {
    exact(value, ["schema_version", "current_request_id", "requests", "responses", "receipts", "dispositions"], "source-assessment state");
    if (value.schema_version !== STATE_VERSION) throw Error("Unsupported source-assessment state");
    if (value.current_request_id !== null) id(value.current_request_id, "current assessment request");
    const requests = list(value.requests, "assessment requests", 32).map(validateRequest);
    const responses = list(value.responses, "assessment responses", 64);
    responses.forEach((item) => {
      exact(item, ["response", "raw", "raw_sha256", "canonical_digest", "received_for_request_id"], "stored assessment response");
      validateResponse(item.response); text(item.raw, "raw response", 300000);
      if (!/^sha256:[a-f0-9]{64}$/.test(item.raw_sha256) || !/^sha256:[a-f0-9]{64}$/.test(item.canonical_digest)) throw Error("Invalid stored response digest");
      id(item.received_for_request_id, "received request");
    });
    const receipts = list(value.receipts, "assessment receipts", 64);
    receipts.forEach((item) => {
      exact(item, ["schema_version", "receipt_id", "request_id", "response_id", "profile_id", "snapshot_id", "snapshot_as_of", "status", "answered_question_ids", "remaining_question_ids", "resolved_reason_ids", "remaining_reason_ids", "origin_verification", "authority_effect"], "assessment receipt");
      if (item.schema_version !== RECEIPT_VERSION) throw Error("Unsupported assessment receipt");
      ["receipt_id", "request_id", "response_id", "profile_id", "snapshot_id"].forEach((key) => id(item[key], "receipt " + key));
      text(item.snapshot_as_of, "receipt as-of"); enumValue(item.status, ["MATCHED_APPROVED_SOURCE_SNAPSHOT", "HISTORICAL_WITHDRAWN", "HISTORICAL_SUPERSEDED"], "receipt status");
      for (const key of ["answered_question_ids", "remaining_question_ids", "resolved_reason_ids", "remaining_reason_ids"])
        list(item[key], "receipt " + key).forEach((entry) => id(entry, key));
      if (item.origin_verification !== "CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH" || item.authority_effect !== "NONE") throw Error("Invalid receipt authority");
    });
    const dispositions = list(value.dispositions, "assessment dispositions", 128);
    dispositions.forEach((item) => {
      exact(item, ["disposition_id", "receipt_id", "reason_id", "effect", "basis"], "assessment disposition");
      ["disposition_id", "receipt_id", "reason_id"].forEach((key) => id(item[key], "disposition " + key));
      enumValue(item.effect, ["TECHNICAL_REASON_RESOLVED", "RETAINED_UNRESOLVED"], "disposition effect"); text(item.basis, "disposition basis");
    });
    if (new Set(requests.map((item) => item.request_id)).size !== requests.length) throw Error("Duplicate assessment request ID");
    if (new Set(responses.map((item) => item.response.response_id)).size !== responses.length) throw Error("Duplicate assessment response ID");
    if (new Set(receipts.map((item) => item.receipt_id)).size !== receipts.length) throw Error("Duplicate assessment receipt ID");
    if (new Set(dispositions.map((item) => item.disposition_id)).size !== dispositions.length) throw Error("Duplicate assessment disposition ID");
    for (const stored of responses) if (!requests.some((request) => request.request_id === stored.received_for_request_id)) throw Error("Stored assessment response references missing request");
    for (const receipt of receipts) if (!responses.some((stored) => stored.response.response_id === receipt.response_id && stored.received_for_request_id === receipt.request_id)) throw Error("Assessment receipt references missing response");
    for (const disposition of dispositions) if (!receipts.some((receipt) => receipt.receipt_id === disposition.receipt_id)) throw Error("Assessment disposition references missing receipt");
    if (value.current_request_id !== null && !requests.some((request) => request.request_id === value.current_request_id)) throw Error("Current assessment request is missing");
    return clone(value);
  }
  function createVerifier(profileValue, indexValue, options = {}) {
    const testMode = options.testMode === true;
    const profile = validateProfile(clone(profileValue), testMode), index = validateIndex(clone(indexValue), profile, testMode);
    return Object.freeze({ profile: Object.freeze(profile), index: Object.freeze(index), testMode });
  }
  let installedVerifier = null;
  function installRepositorySnapshot(profile, index) {
    if (installedVerifier) throw Error("Installed trust root is immutable");
    installedVerifier = createVerifier(profile, index, { testMode: false });
    return installedVerifier;
  }
  function repositorySnapshot() {
    if (!installedVerifier) throw Error("Repository snapshot is not installed");
    return installedVerifier;
  }
  async function prepare(design, requestId) {
    const request = await buildRequest(design, requestId);
    if (request.subject_digest !== await digest(request.subject)) throw Error("Assessment subject digest failure");
    const prior = design.source_assessments.requests.find((item) => item.request_id === request.request_id);
    if (prior && canonical(prior) !== canonical(request)) throw Error("Assessment request identity conflict");
    if (!prior) design.source_assessments.requests.push(request);
    design.source_assessments.current_request_id = request.request_id;
    return clone(request);
  }
  async function verifyResponse(design, raw, verifier = repositorySnapshot()) {
    if (typeof raw !== "string" || raw.length > 300000) throw Error("Assessment response exceeds parser bound");
    const parsed = validateResponse(F.strictJsonParse(raw, { maxBytes: 300000, maxDepth: 20 }));
    const request = design.source_assessments.requests.find((item) => item.request_id === parsed.request_id);
    if (!request || design.source_assessments.current_request_id !== request.request_id) throw Error("No matching current local assessment request");
    if (request.subject_digest !== await digest(scopeSubject(design)) || canonical(request.subject) !== canonical(scopeSubject(design))) throw Error("Current design no longer matches frozen assessment subject");
    if (parsed.subject_digest !== request.subject_digest || canonical(parsed.association) !== canonical(request.association)) throw Error("Response subject association mismatch");
    const requestDigest = await digest(request), rawHash = "sha256:" + await sha256(raw), canonicalDigest = await digest(parsed);
    if (parsed.request_digest !== requestDigest) throw Error("Response request digest mismatch");
    const entry = verifier.index.entries.find((item) => item.assessment_id === parsed.response_id);
    if (!entry) throw Error("Assessment is not admitted by the installed snapshot");
    if (entry.request_id !== request.request_id || entry.request_digest !== requestDigest || entry.subject_digest !== request.subject_digest || entry.response_raw_sha256 !== rawHash || entry.response_canonical_digest !== canonicalDigest) throw Error("Assessment bytes or scope do not match approved entry");
    if (!entry.owner_adoption_ref || entry.issuer_principal !== parsed.claimed_issuer.principal || entry.owner_adoption_content_digest !== canonicalDigest) throw Error("Exact owner adoption is missing or mismatched");
    if (entry.state === "WITHDRAWN") throw Error("Assessment withdrawn by installed snapshot");
    if (entry.state === "CONFLICTING" || entry.conflicts_with_assessment_ids.length) throw Error("Assessment conflict requires explicit disposition");
    const questionMap = new Map(request.questions.map((item) => [item.question_id, item]));
    const answered = [], resolved = [];
    for (const answer of parsed.answered) {
      const question = questionMap.get(answer.question_id);
      if (!question || answer.domain !== question.domain || !entry.allowed_domains.includes(answer.domain)) throw Error("Answer outside approved request/domain scope");
      if (answer.status === "ANSWERED") answered.push(answer.question_id);
      for (const reason of answer.addressed_reason_ids) {
        if (!question.reason_ids.includes(reason)) throw Error("Answer addresses unknown reason");
        const recordedReason = design.evidence_bindings
          .flatMap((binding) => binding.scientific_review_reasons)
          .find((item) => item.reason_id === reason);
        if (
          recordedReason &&
          RESOLVABLE_REASON_DOMAINS[answer.domain].includes(recordedReason.domain)
        ) resolved.push(reason);
      }
    }
    const allQuestionIds = request.questions.map((item) => item.question_id);
    const remainingQuestions = allQuestionIds.filter((item) => !answered.includes(item));
    const allReasons = [...new Set(request.questions.flatMap((item) => item.reason_ids))];
    const currentUse = entry.state === "CURRENT";
    const receipt = {
      schema_version: RECEIPT_VERSION,
      receipt_id: "receipt:" + parsed.response_id,
      request_id: request.request_id,
      response_id: parsed.response_id,
      profile_id: verifier.profile.profile_id,
      snapshot_id: verifier.profile.snapshot_id,
      snapshot_as_of: verifier.profile.snapshot_as_of,
      status: entry.state === "SUPERSEDED" ? "HISTORICAL_SUPERSEDED" : "MATCHED_APPROVED_SOURCE_SNAPSHOT",
      answered_question_ids: [...new Set(answered)].sort(),
      remaining_question_ids: remainingQuestions.sort(),
      resolved_reason_ids: currentUse ? [...new Set(resolved)].sort() : [],
      remaining_reason_ids: currentUse ? allReasons.filter((item) => !resolved.includes(item)).sort() : allReasons.sort(),
      origin_verification: "CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH",
      authority_effect: "NONE",
    };
    return { response: parsed, raw, raw_sha256: rawHash, canonical_digest: canonicalDigest, received_for_request_id: request.request_id, receipt };
  }
  async function importResponse(design, raw, verifier = repositorySnapshot()) {
    const before = canonical(design.source_assessments), checked = await verifyResponse(design, raw, verifier);
    const prior = design.source_assessments.responses.find((item) => item.response.response_id === checked.response.response_id);
    if (prior) {
      if (prior.raw_sha256 !== checked.raw_sha256) throw Error("Assessment identity conflict");
      return { status: "DEDUPLICATED", receipt: clone(design.source_assessments.receipts.find((item) => item.response_id === checked.response.response_id)) };
    }
    try {
      design.source_assessments.responses.push({ response: checked.response, raw: checked.raw, raw_sha256: checked.raw_sha256, canonical_digest: checked.canonical_digest, received_for_request_id: checked.received_for_request_id });
      design.source_assessments.receipts.push(checked.receipt);
      for (const reasonId of checked.receipt.resolved_reason_ids)
        design.source_assessments.dispositions.push({ disposition_id: "disposition:" + checked.response.response_id + ":" + reasonId, receipt_id: checked.receipt.receipt_id, reason_id: reasonId, effect: "TECHNICAL_REASON_RESOLVED", basis: "Exact admitted response under installed repository snapshot; qualification and rights effect remain none." });
      validateState(design.source_assessments);
      return { status: checked.receipt.status, receipt: clone(checked.receipt) };
    } catch (error) {
      design.source_assessments = JSON.parse(before);
      throw error;
    }
  }
  async function revalidateState(design, verifier = repositorySnapshot()) {
    const working = clone(design), state = working.source_assessments;
    validateState(state);
    const originalCurrent = state.current_request_id,
      freshReceipts = [], freshDispositions = [];
    for (const stored of state.responses) {
      const parsed = validateResponse(F.strictJsonParse(stored.raw, { maxBytes: 300000, maxDepth: 20 })),
        rawHash = "sha256:" + await sha256(stored.raw),
        canonicalDigest = await digest(parsed);
      if (canonical(parsed) !== canonical(stored.response) || rawHash !== stored.raw_sha256 || canonicalDigest !== stored.canonical_digest)
        throw Error("Stored assessment bytes or derived digests were altered");
      state.current_request_id = stored.received_for_request_id;
      try {
        const checked = await verifyResponse(working, stored.raw, verifier);
        freshReceipts.push(checked.receipt);
        for (const reasonId of checked.receipt.resolved_reason_ids)
          freshDispositions.push({ disposition_id: "disposition:" + checked.response.response_id + ":" + reasonId, receipt_id: checked.receipt.receipt_id, reason_id: reasonId, effect: "TECHNICAL_REASON_RESOLVED", basis: "Revalidated against the currently installed repository snapshot; qualification and rights effect remain none." });
      } catch (error) {
        if (!/not admitted|withdrawn|conflict|superseded/i.test(error.message)) throw error;
      }
    }
    state.current_request_id = originalCurrent;
    state.receipts = freshReceipts;
    state.dispositions = freshDispositions;
    validateState(state);
    design.source_assessments = state;
    return project(design, verifier);
  }
  function project(design, verifier = repositorySnapshot()) {
    const state = design.source_assessments, request = state.requests.find((item) => item.request_id === state.current_request_id) || null;
    const receipts = state.receipts.filter((item) => item.request_id === state.current_request_id);
    const current = receipts.at(-1) || null;
    const stored = state.responses.filter((item) => item.received_for_request_id === state.current_request_id).at(-1) || null;
    const installedEntry = stored ? verifier.index.entries.find((item) => item.assessment_id === stored.response.response_id) || null : null;
    const historicalStatus = !current && installedEntry?.state === "WITHDRAWN"
      ? "HISTORICAL_WITHDRAWN"
      : !current && installedEntry?.state === "CONFLICTING"
        ? "CONFLICTING_INSTALLED_SNAPSHOT"
        : null;
    const assessmentStatus = current?.status || historicalStatus || "PENDING_EXACT_OWNER_ADOPTION";
    const usableCurrentAnswer = assessmentStatus === "MATCHED_APPROVED_SOURCE_SNAPSHOT";
    return {
      profile_id: verifier.profile.profile_id,
      snapshot_id: verifier.profile.snapshot_id,
      snapshot_as_of: verifier.profile.snapshot_as_of,
      request_status: request ? "PREPARED_LOCAL_NOT_TRANSMITTED" : "NOT_PREPARED",
      request_id: request?.request_id || "",
      subject_digest: request?.subject_digest || "",
      assessment_status: assessmentStatus,
      origin_verification: current?.origin_verification || (historicalStatus ? "CURRENT_USE_REJECTED_BY_INSTALLED_SNAPSHOT" : "NOT_ESTABLISHED"),
      answered_question_ids: current?.answered_question_ids || [],
      remaining_question_ids: current?.remaining_question_ids || request?.questions.map((item) => item.question_id) || [],
      remaining_reason_ids: current?.remaining_reason_ids || request?.questions.flatMap((item) => item.reason_ids) || [],
      next_action: usableCurrentAnswer
        ? "REVIEW_SCOPED_TECHNICAL_ANSWER_AND_REMAINING_OBLIGATIONS"
        : historicalStatus || assessmentStatus === "HISTORICAL_SUPERSEDED"
          ? "RECONCILE_INSTALLED_SNAPSHOT_HISTORY_WITH_OWNER"
          : "RYAN_ADOPT_EXACT_PREPARED_ASSESSMENT_FOR_A_FUTURE_SNAPSHOT",
      qualification_effect: "NONE",
      rights_effect: "NONE",
      launch_effect: "NONE",
    };
  }
  const api = { PROFILE_ID, REQUEST_VERSION, RESPONSE_VERSION, RECEIPT_VERSION, STATE_VERSION, SNAPSHOT_VERSION, SUBJECT_VERSION, PROFILE_VERSION, TECHNICAL_DOMAINS, RESOLVABLE_REASON_DOMAINS, AUTHORITY_CEILING, canonical, sha256, digest, newState, scopeSubject, supportedSubject, buildRequest, validateRequest, validateResponse, validateProfile, validateIndex, validateState, createVerifier, installRepositorySnapshot, repositorySnapshot, prepare, verifyResponse, importResponse, revalidateState, project };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonSourceAssessment = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
