#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const WB = path.resolve(__dirname, "..");
const ROOT = path.resolve(WB, "../../..");
const PACKAGE = path.join(WB, "source_assessment", "v1");
const FIXTURES = path.join(PACKAGE, "fixtures");

function sorted(value) {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sorted(value[key])]));
  }
  return value;
}

function canonical(value) {
  return `${JSON.stringify(sorted(value))}\n`;
}

function digestBytes(bytes) {
  return `sha256:${crypto.createHash("sha256").update(bytes).digest("hex")}`;
}

function digestValue(value) {
  return digestBytes(Buffer.from(canonical(value), "utf8"));
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function artifact(id, relativePath, factScope) {
  const absolute = path.join(ROOT, relativePath);
  return {
    artifact_id: id,
    path: relativePath,
    sha256: digestBytes(fs.readFileSync(absolute)),
    fact_scope: factScope,
  };
}

function ceiling() {
  return {
    origin_authenticated: false,
    source_owner_accepted: false,
    scientifically_qualified: false,
    rights_authorized: false,
    execution_established_by_response: false,
    score_eligible: false,
    protected_use_authorized: false,
    launch_authorized: false,
  };
}

function writeJson(relative, value) {
  const target = path.join(PACKAGE, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", flag: "w" });
}

function main() {
  const resultPath = path.join(PACKAGE, "source", "authoring_bridge_output", "workbench-authoring-result.json");
  const proposalPath = path.join(PACKAGE, "source", "authoring_bridge_output", "native-output", "proposal.json");
  const c05Path = path.join(WB, "data", "c05_public_development_evidence_v1.json");
  const c05IndexPath = path.join(WB, "data", "c05_fixture_index_v2.json");
  const authoringResult = readJson(resultPath);
  const proposal = readJson(proposalPath);
  const c05 = readJson(c05Path);
  const c05Request = JSON.parse(c05.measurement_request_json);
  const c05Result = JSON.parse(c05.measurement_result_json);

  if (authoringResult.semantic_receipt.status !== "INTENT_PRESERVED") throw new Error("Authoring intent was not preserved");
  if (authoringResult.semantic_receipt.emitted.active_goal !== "Dynamics") throw new Error("Expected Dynamics authoring result");
  if (proposal.challenge.primary_goal !== "Dynamics") throw new Error("Expected Dynamics proposal");
  if (c05.source.fixture_id !== "C05-PUBLIC-EVAL2-PERTURBED") throw new Error("Unexpected C-05 fixture");

  const snapshot = {
    schema_version: "carbon.goal-workbench.source-assessment-design-snapshot.v1",
    job_id: "job-001",
    design_id: "job-001-design-1",
    design_revision: 1,
    design_status: "SEALED",
    planning_route: "ADAPT_SUPPORTED_CHALLENGE",
    intended_use: "Public synthetic periodic viscous Burgers Dynamics contract demonstration only",
    template_id: "periodic_viscous_burgers_1d_v1",
    challenge: { id: "burgers-dynamics-v1", version: "1.0", active_goal: "Dynamics" },
    input_contract: "Finite Fourier initial field, positive viscosity, requested times, and declared periodic domain length",
    output_contract: "Complete field evolution with compression, dissipation, and half-time diagnostics",
    units: "Source-defined nondimensional Burgers variables and declared characteristic scales",
    requirements: [{ requirement_id: "REQ-DYNAMICS", role: "MANDATORY", state: "PROPOSED_UNQUALIFIED" }],
    traces: [{ trace_id: "TRACE-DYNAMICS", requirement_id: "REQ-DYNAMICS", case_family_id: "BURGERS-12-CELL" }],
    evidence_bindings: [{
      evidence_binding_id: "C05-PUBLIC-EVAL2-PERTURBED",
      evidence_kind: "FIXED_CASE_RESULT",
      source_ref: "Business/Carbon_Fit/workbench/data/c05_public_development_evidence_v1.json",
      source_digest: digestBytes(fs.readFileSync(c05Path)),
      originating_design_id: "job-001-design-1",
      originating_design_revision: 1,
      inherited: false,
      applicability: "UNRESOLVED",
      rights_status: "UNRESOLVED",
    }],
    unresolved_reason_ids: [
      "gw06:intended-use:suitability-unresolved",
      "gw06:rights:use-unresolved",
      "gw06:scientific:applicability-unresolved",
    ],
    authority_ceiling: ceiling(),
  };
  writeJson("fixtures/public_design_snapshot.json", snapshot);
  const snapshotRaw = fs.readFileSync(path.join(FIXTURES, "public_design_snapshot.json"));

  const request = {
    schema_version: "carbon.goal-workbench.source-assessment-request.v1",
    contract_version: "1.0",
    source_profile_version: "burgers-dynamics-public.v1",
    request_id: "GW06-BURGERS-DYNAMICS-PUBLIC-REQUEST-001",
    handoff_identity: {
      schema_version: "carbon.goal-workbench.handoff.v1",
      request_id: "GW06-BURGERS-DYNAMICS-PUBLIC-REQUEST-001",
      status: "EXPORTED_CONTRACT_FIXTURE_NOT_DISPATCHED",
    },
    association: {
      job_id: snapshot.job_id,
      design_id: snapshot.design_id,
      design_revision: snapshot.design_revision,
      design_status: snapshot.design_status,
      design_snapshot_ref: "fixtures/public_design_snapshot.json",
      design_snapshot_digest: digestValue(snapshot),
      design_snapshot_artifact_digest: digestBytes(snapshotRaw),
      planning_route: snapshot.planning_route,
    },
    question: {
      question_id: "GW06-BURGERS-DYNAMICS-CAPABILITY-AND-CONTEXT",
      response_type: "CAPABILITY_DECLARATION_WITH_UNRESOLVED_APPLICABILITY",
      text: "Can the accepted public Burgers authoring path express this exact Dynamics design, and what exact retained C-05 development context is associated with it?",
      intended_use_question: "What scientific applicability, intended-use suitability, and rights questions remain unanswered for any later use?",
    },
    scope: {
      requirement_ids: ["REQ-DYNAMICS"],
      trace_ids: ["TRACE-DYNAMICS"],
      case_family_ids: ["BURGERS-12-CELL"],
      evidence_bindings: snapshot.evidence_bindings.map(({ applicability, rights_status, ...binding }) => binding),
      dependency_domains: ["AUTHORING", "INPUT_CONTRACT", "OUTPUT_CONTRACT", "PHYSICS_SCOPE", "REFERENCE", "UNITS_SCALING"],
      unresolved_reason_ids: snapshot.unresolved_reason_ids,
    },
    source_target: {
      recipient_domain: "WAVE-C/C-AUTH1",
      requested_response_type: "DECLARATION_AND_SCOPED_ASSESSMENT",
      implementation_ref: "carbon/authoring/goals.py",
      schema_refs: ["carbon.goal-authoring-proposal/1", "carbon.c05.burgers-measurement-result.v1"],
      artifact_ids: ["authoring_result", "native_proposal", "c05_public_bundle", "c05_fixture_index"],
    },
    permitted_scope: { information: "PUBLIC_SYNTHETIC_ONLY", use: "DETACHED_CONTRACT_CONFORMANCE_ONLY", rights: "NO_RIGHTS_GRANTED" },
    expected_result: {
      allowed_kinds: ["DECLARATION", "SCOPED_ASSESSMENT", "PARTIAL_RESPONSE", "UNSUPPORTED_SCOPE", "NAMED_BLOCKER"],
      named_blocker: "Source-owner semantic, issuer-scope, trust-anchor, or fixture mapping decision is absent",
      restart_event: "The WAVE-C/C-AUTH1 source contract owner answers the three acceptance questions for this exact contract/profile version",
    },
    authority: "REQUEST_ONLY_NO_EXECUTION_APPROVAL_QUALIFICATION_RIGHTS_OR_LAUNCH",
  };
  writeJson("fixtures/request.json", request);
  const requestDigest = digestValue(request);

  const responseContent = {
    source_snapshot: {
      authoring_result: digestBytes(fs.readFileSync(resultPath)),
      native_proposal: digestBytes(fs.readFileSync(proposalPath)),
      c05_public_bundle: digestBytes(fs.readFileSync(c05Path)),
      c05_fixture_index: digestBytes(fs.readFileSync(c05IndexPath)),
    },
    capability_declaration: {
      status: "SUPPORTED_EXACT_PUBLIC_DYNAMICS_TECHNICAL_DECLARATION",
      template_id: "periodic_viscous_burgers_1d_v1",
      active_goal: "Dynamics",
      technical_scope: "The accepted local authoring bridge emitted an intent-preserved DEVELOPMENT proposal for the exact public synthetic periodic viscous Burgers Dynamics request.",
      field_coverage: ["physical_law", "active_goal", "measurement_bindings", "sampling", "references", "query_contract"],
      source_artifact_ids: ["authoring_result", "native_proposal"],
    },
    evidence_relationship: {
      status: "RETAINED_PUBLIC_DEVELOPMENT_CONTEXT",
      fixture_id: c05.source.fixture_id,
      evidence_kind: "FIXED_CASE_RESULT",
      case_scope: "ONE_EXACT_PUBLIC_EVAL_CASE_NOT_A_CAMPAIGN",
      request_digest: c05.source.request_digest,
      result_digest: c05.source.result_digest,
      measurement_ids: c05Result.measurements.map((item) => item.measurement_id),
      physics_ids: c05Result.physics.map((item) => item.physics_id),
      source_artifact_id: "c05_public_bundle",
      execution_relationship: "HISTORICAL_CONTEXT_NOT_FRESH_EXECUTION",
    },
    applicability_assessment: {
      status: "UNRESOLVED_TEST_AUTHORED_PREVIEW",
      assumptions: ["PUBLIC_SYNTHETIC_SCOPE_ONLY"],
      exclusions: ["NO_CUSTOMER_USE", "NO_PROTECTED_USE", "NO_POPULATION_ADEQUACY_CLAIM"],
      limitations: ["TEST_PRODUCER_IS_NOT_SOURCE_OWNER", "C05_UNCERTAINTY_AND_LIMITS_REMAIN_UNKNOWN", "ONE_FIXED_CASE_IS_NOT_A_CAMPAIGN"],
      answered_question_ids: ["GW06:TECHNICAL_EXPRESSIBILITY"],
      partial_question_ids: ["GW06:RETAINED_C05_CONTEXT"],
      unsupported_question_ids: [],
      unanswered_question_ids: ["GW06:SCIENTIFIC_APPLICABILITY", "GW06:INTENDED_USE_SUITABILITY", "GW06:RIGHTS"],
      reason_ids_addressed: [],
      reason_ids_remaining: request.scope.unresolved_reason_ids,
      supporting_evidence_refs: ["authoring_result", "native_proposal", "c05_public_bundle", "c05_fixture_index"],
      supersedes_response_id: null,
      next_decision: "The WAVE-C/C-AUTH1 source contract owner accepts, changes, or rejects the field semantics, issuer/scope verification, and public fixture mapping.",
      restart_event: request.expected_result.restart_event,
    },
  };
  const response = {
    schema_version: "carbon.goal-workbench.source-assessment-response.v1",
    contract_version: "1.0",
    source_profile_version: "burgers-dynamics-public.v1",
    response_id: "GW06-BURGERS-DYNAMICS-PUBLIC-RESPONSE-001",
    request_id: request.request_id,
    request_digest: requestDigest,
    association: {
      job_id: snapshot.job_id,
      design_id: snapshot.design_id,
      design_revision: snapshot.design_revision,
      design_snapshot_digest: request.association.design_snapshot_digest,
    },
    claimed_issuer: {
      issuer_id: "GOAL_WORKBENCH_06_TEST_PRODUCER",
      issuer_role: "CONFORMANCE_FIXTURE_PRODUCER",
      claim_basis: "TEST_AUTHORED_NOT_SOURCE_OWNER",
    },
    result_kind: "PARTIAL_RESPONSE",
    content: responseContent,
    content_digest: digestValue(responseContent),
    authority_ceiling: ceiling(),
  };
  writeJson("fixtures/response.json", response);

  const profile = {
    schema: "carbon.goal-workbench.source-assessment-profile.v1",
    contract_version: "1.0",
    profile_id: "BURGERS_DYNAMICS_PUBLIC_CAUTH1_C05_V1",
    source_profile_version: "burgers-dynamics-public.v1",
    consumer_owner: { domain: "SYSTEM/BUSINESS-AUTHORITY", role: "WORKBENCH_CONSUMER" },
    source_contract_owner: { domain: "WAVE-C/C-AUTH1", role: "SCIENTIFIC_INTEGRATION", decision_inbox: "https://github.com/carbonphysicsai/Carbon/issues/42", acceptance_status: "PENDING_SOURCE_OWNER_DECISION" },
    canonicalization: { envelope: "UTF8_SORTED_KEYS_MINIFIED_JSON_LF_V1", artifact: "EXACT_RETAINED_BYTES_SHA256" },
    source_artifacts: [
      artifact("authoring_result", "Business/Carbon_Fit/workbench/source_assessment/v1/source/authoring_bridge_output/workbench-authoring-result.json", ["bridge semantic receipt", "Dynamics activation", "unqualified status"]),
      artifact("native_proposal", "Business/Carbon_Fit/workbench/source_assessment/v1/source/authoring_bridge_output/native-output/proposal.json", ["source proposal bytes", "public Dynamics goal", "DEVELOPMENT boundaries"]),
      artifact("c05_public_bundle", "Business/Carbon_Fit/workbench/data/c05_public_development_evidence_v1.json", ["one exact fixed public EVAL case", "four measurements", "six physics diagnostics", "unknown limits and uncertainty"]),
      artifact("c05_fixture_index", "Business/Carbon_Fit/workbench/data/c05_fixture_index_v2.json", ["pinned C-05 fixture association and identities"]),
    ],
    origin_routes: [
      { input: "User-imported JSON with a claimed owner name", establishes: "A statement attributed by the submitter", must_not_follow: "Authenticated source ownership or approval" },
      { input: "A file matching a pinned public fixture", establishes: "Correspondence with those exact pinned fixture bytes", must_not_follow: "Live execution, independent review, or human acceptance" },
      { input: "An artifact from the accepted local authoring bridge", establishes: "The bridge's existing verified artifact and semantic facts", must_not_follow: "A new source-owner assessment or qualification" },
      { input: "A GitHub link or comment locator", establishes: "A locator and reported status", must_not_follow: "Verified authority or permission to fetch or transmit" },
      { input: "A future accepted authenticated assessment", establishes: "Only the statement and scope its issuer is authorized to make", must_not_follow: "Global design qualification or unrelated rights" },
    ],
    future_authenticated_route: {
      status: "NOT_IMPLEMENTED",
      verifier_owner: "OWNER_ACCEPTED_INPUT_REQUIRED",
      issuer_scope_mapping: "OWNER_ACCEPTED_INPUT_REQUIRED",
      trust_anchor: "OWNER_ACCEPTED_INPUT_REQUIRED",
      failure_behavior: "REJECT_WITHOUT_PARTIAL_RECEIPT_OR_WORKSPACE_MUTATION",
      missing_inputs: ["accepted verifier owner", "accepted issuer-to-scope mapping", "accepted trust anchor", "accepted public response fixture"],
    },
    authority_ceiling: ceiling(),
  };
  writeJson("fixtures/profile.json", profile);

  const provenance = {
    schema_version: "carbon.goal-workbench.source-assessment-field-provenance.v1",
    entries: [
      { path: "request.*", source_kind: "TEST_AUTHORED_REQUEST_FIELD", source_ref: "GOAL-WORKBENCH-06 ticket", meaning: "A bounded request, not an owner decision" },
      { path: "response.claimed_issuer", source_kind: "TEST_AUTHORED_EXPECTED_RESPONSE", source_ref: "fixtures/response.json", meaning: "Conformance producer claim, not source-owner identity" },
      { path: "response.content.capability_declaration", source_kind: "EXISTING_BRIDGE_DERIVED_FACT", source_ref: "authoring_result", meaning: "Intent-preserved public Dynamics authoring fact" },
      { path: "response.content.evidence_relationship", source_kind: "COPIED_SOURCE_FACT", source_ref: "c05_public_bundle", meaning: "Exact historical fixed-case C-05 context" },
      { path: "response.content.applicability_assessment", source_kind: "TEST_AUTHORED_EXPECTED_RESPONSE", source_ref: "fixtures/response.json", meaning: "Unresolved preview; no owner-supplied assessment is available" },
      { path: "response.authority_ceiling", source_kind: "CONTRACT_INVARIANT", source_ref: "schemas/response.schema.json", meaning: "All authority effects remain false" },
    ],
  };
  writeJson("fixtures/field_provenance.json", provenance);

  const vectors = {
    schema_version: "carbon.goal-workbench.source-assessment-vectors.v1",
    base_request: "request.json",
    base_response: "response.json",
    cases: [
      ["positive-supported-dynamics", "ACCEPT_NON_AUTHORITATIVE_PREVIEW"],
      ["front-resolution-intent-mismatch", "REJECT_INTENT_MISMATCH"],
      ["unsupported-physics", "ACCEPT_EXPLICIT_UNSUPPORTED_ONLY"],
      ["unsupported-rights", "ACCEPT_EXPLICIT_UNSUPPORTED_ONLY"],
      ["wrong-job-design-request", "REJECT_ASSOCIATION"],
      ["same-revision-different-content", "REJECT_SNAPSHOT"],
      ["wrong-case-query-source-version", "REJECT_SOURCE_SCOPE"],
      ["inherited-as-fresh-execution", "REJECT_EXECUTION_LAUNDERING"],
      ["exact-response-replay", "IDEMPOTENT"],
      ["same-response-id-different-bytes", "REJECT_IDENTITY_CONFLICT"],
      ["partial-answer", "RETAIN_UNRESOLVED"],
      ["conflicting-assessments", "RECONCILIATION_REQUIRED"],
      ["older-revision", "REJECT_STALE"],
      ["forged-native-provenance", "REJECT_UNKNOWN_AUTHORITY_FIELD"],
      ["hash-without-origin-route", "NO_AUTHENTICATION"],
      ["confirmation-as-qualification", "REJECT_AUTHORITY_ESCALATION"],
      ["rights-prohibition-plus-technical-confirmation", "RETAIN_PROHIBITION"],
      ["hostile-json-and-display-text", "REJECT_OR_ESCAPE"],
    ].map(([vector_id, expected]) => ({ vector_id, expected })),
  };
  writeJson("fixtures/vectors.json", vectors);

  const manifestFiles = [
    "schemas/request.schema.json", "schemas/response.schema.json", "schemas/profile.schema.json", "schemas/receipt.schema.json",
    "source/authoring_request.json", "source/authoring_bridge_output/native-input.json",
    "source/authoring_bridge_output/native-output/proposal.json", "source/authoring_bridge_output/workbench-authoring-result.json",
    "fixtures/public_design_snapshot.json", "fixtures/request.json", "fixtures/response.json", "fixtures/profile.json", "fixtures/field_provenance.json", "fixtures/vectors.json",
  ];
  const manifest = {
    schema_version: "carbon.goal-workbench.source-assessment-manifest.v1",
    contract_version: "1.0",
    profile_id: profile.profile_id,
    canonicalization: profile.canonicalization,
    files: manifestFiles.map((relative) => ({ path: relative, bytes: fs.statSync(path.join(PACKAGE, relative)).size, sha256: digestBytes(fs.readFileSync(path.join(PACKAGE, relative))) })),
    production_application_changed: false,
    source_owner_acceptance: "PENDING_SOURCE_OWNER_DECISION",
    production_consumer: "NOT_IMPLEMENTED",
    authority_ceiling: ceiling(),
  };
  writeJson("manifest.json", manifest);
  process.stdout.write(`wrote ${manifest.files.length} contract files; request ${requestDigest}\n`);
}

if (require.main === module) main();
module.exports = { canonical, digestBytes, digestValue, sorted };
