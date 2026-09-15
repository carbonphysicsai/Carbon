#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const WB = path.resolve(__dirname, "..");
const ROOT = path.resolve(WB, "../../..");
const F = require(path.join(WB, "src", "engine.js"));
const E = require(path.join(WB, "src", "c05_evidence.js"));
const G = require(path.join(WB, "src", "workflow.js"));
const B = require("./build_source_assessment_fixtures.cjs");

const CEILING_KEYS = [
  "origin_authenticated", "source_owner_accepted", "scientifically_qualified", "rights_authorized",
  "execution_established_by_response", "score_eligible", "protected_use_authorized", "launch_authorized",
];

function fail(code, detail = "") {
  throw new Error(`${code}${detail ? `: ${detail}` : ""}`);
}

function exact(value, keys, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("INVALID_OBJECT", label);
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) fail("UNKNOWN_OR_MISSING_FIELD", `${label} expected ${expected.join(",")}; got ${actual.join(",")}`);
}

function same(a, b, code) {
  if (JSON.stringify(a) !== JSON.stringify(b)) fail(code);
}

function readBounded(file, maxBytes = 1_000_000) {
  const bytes = fs.readFileSync(file);
  if (bytes.length > maxBytes) fail("INPUT_TOO_LARGE", path.basename(file));
  let raw;
  try {
    raw = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (_error) {
    fail("MALFORMED_UTF8", path.basename(file));
  }
  return { raw, bytes, value: F.strictJsonParse(raw, { maxBytes, maxDepth: 24 }) };
}

function sha(bytes) {
  return `sha256:${crypto.createHash("sha256").update(bytes).digest("hex")}`;
}

function validateCeiling(value) {
  exact(value, CEILING_KEYS, "authority_ceiling");
  for (const key of CEILING_KEYS) if (value[key] !== false) fail("AUTHORITY_ESCALATION", key);
}

function validateProfile(profile) {
  exact(profile, ["schema", "contract_version", "profile_id", "source_profile_version", "consumer_owner", "source_contract_owner", "canonicalization", "source_artifacts", "origin_routes", "future_authenticated_route", "authority_ceiling"], "profile");
  if (profile.schema !== "carbon.goal-workbench.source-assessment-profile.v1" || profile.contract_version !== "1.0" || profile.profile_id !== "BURGERS_DYNAMICS_PUBLIC_CAUTH1_C05_V1" || profile.source_profile_version !== "burgers-dynamics-public.v1") fail("UNSUPPORTED_PROFILE");
  same(profile.consumer_owner, { domain: "SYSTEM/BUSINESS-AUTHORITY", role: "WORKBENCH_CONSUMER" }, "WRONG_CONSUMER_OWNER");
  if (profile.source_contract_owner.domain !== "WAVE-C/C-AUTH1" || profile.source_contract_owner.acceptance_status !== "PENDING_SOURCE_OWNER_DECISION") fail("SOURCE_OWNER_ACCEPTANCE_MISSTATED");
  same(profile.canonicalization, { envelope: "UTF8_SORTED_KEYS_MINIFIED_JSON_LF_V1", artifact: "EXACT_RETAINED_BYTES_SHA256" }, "CANONICALIZATION_MISMATCH");
  if (!Array.isArray(profile.source_artifacts) || profile.source_artifacts.length !== 4) fail("SOURCE_ARTIFACT_SET_MISMATCH");
  const ids = profile.source_artifacts.map((a) => a.artifact_id);
  same(ids, ["authoring_result", "native_proposal", "c05_public_bundle", "c05_fixture_index"], "SOURCE_ARTIFACT_ORDER_OR_ID_MISMATCH");
  if (profile.future_authenticated_route.status !== "NOT_IMPLEMENTED") fail("UNSUPPORTED_ORIGIN_ROUTE_ENABLED");
  validateCeiling(profile.authority_ceiling);
}

function validateRequest(request) {
  exact(request, ["schema_version", "contract_version", "source_profile_version", "request_id", "handoff_identity", "association", "question", "scope", "source_target", "permitted_scope", "expected_result", "authority"], "request");
  if (request.schema_version !== "carbon.goal-workbench.source-assessment-request.v1" || request.contract_version !== "1.0" || request.source_profile_version !== "burgers-dynamics-public.v1") fail("UNSUPPORTED_REQUEST_VERSION");
  if (request.request_id !== "GW06-BURGERS-DYNAMICS-PUBLIC-REQUEST-001") fail("WRONG_REQUEST_ID");
  exact(request.handoff_identity, ["schema_version", "request_id", "status"], "handoff_identity");
  if (request.handoff_identity.request_id !== request.request_id || request.handoff_identity.status !== "EXPORTED_CONTRACT_FIXTURE_NOT_DISPATCHED") fail("HANDOFF_IDENTITY_MISMATCH");
  exact(request.association, ["job_id", "design_id", "design_revision", "design_status", "design_snapshot_ref", "design_snapshot_digest", "design_snapshot_artifact_digest", "planning_route"], "request.association");
  if (request.association.job_id !== "job-001" || request.association.design_id !== "job-001-design-1" || request.association.design_revision !== 1 || request.association.design_status !== "SEALED" || request.association.planning_route !== "ADAPT_SUPPORTED_CHALLENGE") fail("REQUEST_ASSOCIATION_MISMATCH");
  exact(request.question, ["question_id", "response_type", "text", "intended_use_question"], "request.question");
  exact(request.scope, ["requirement_ids", "trace_ids", "case_family_ids", "evidence_bindings", "dependency_domains", "unresolved_reason_ids"], "request.scope");
  exact(request.source_target, ["recipient_domain", "requested_response_type", "implementation_ref", "schema_refs", "artifact_ids"], "request.source_target");
  exact(request.permitted_scope, ["information", "use", "rights"], "request.permitted_scope");
  exact(request.expected_result, ["allowed_kinds", "named_blocker", "restart_event"], "request.expected_result");
  if (request.question.question_id !== "GW06-BURGERS-DYNAMICS-CAPABILITY-AND-CONTEXT") fail("QUESTION_SCOPE_MISMATCH");
  if (request.source_target.recipient_domain !== "WAVE-C/C-AUTH1" || request.source_target.implementation_ref !== "carbon/authoring/goals.py") fail("SOURCE_TARGET_MISMATCH");
  if (request.permitted_scope.information !== "PUBLIC_SYNTHETIC_ONLY" || request.permitted_scope.use !== "DETACHED_CONTRACT_CONFORMANCE_ONLY" || request.permitted_scope.rights !== "NO_RIGHTS_GRANTED") fail("PERMITTED_SCOPE_MISMATCH");
  if (request.authority !== "REQUEST_ONLY_NO_EXECUTION_APPROVAL_QUALIFICATION_RIGHTS_OR_LAUNCH") fail("REQUEST_AUTHORITY_ESCALATION");
  const binding = request.scope.evidence_bindings?.[0];
  if (!binding || request.scope.evidence_bindings.length !== 1 || binding.evidence_binding_id !== "C05-PUBLIC-EVAL2-PERTURBED" || binding.inherited !== false) fail("EVIDENCE_BINDING_MISMATCH");
  exact(binding, ["evidence_binding_id", "evidence_kind", "source_ref", "source_digest", "originating_design_id", "originating_design_revision", "inherited"], "request.scope.evidence_binding");
  const requiredDomains = ["AUTHORING", "INPUT_CONTRACT", "OUTPUT_CONTRACT", "PHYSICS_SCOPE", "REFERENCE", "UNITS_SCALING"];
  for (const domain of requiredDomains) if (!request.scope.dependency_domains.includes(domain)) fail("MISSING_SOURCE_DEPENDENCY_DOMAIN", domain);
}

function validateResponse(response, request) {
  exact(response, ["schema_version", "contract_version", "source_profile_version", "response_id", "request_id", "request_digest", "association", "claimed_issuer", "result_kind", "content", "content_digest", "authority_ceiling"], "response");
  if (response.schema_version !== "carbon.goal-workbench.source-assessment-response.v1" || response.contract_version !== "1.0" || response.source_profile_version !== request.source_profile_version) fail("UNSUPPORTED_RESPONSE_VERSION");
  if (response.request_id !== request.request_id || response.request_digest !== B.digestValue(request)) fail("RESPONSE_REQUEST_MISMATCH");
  exact(response.association, ["job_id", "design_id", "design_revision", "design_snapshot_digest"], "response.association");
  if (response.association.job_id !== request.association.job_id || response.association.design_id !== request.association.design_id || response.association.design_revision !== request.association.design_revision || response.association.design_snapshot_digest !== request.association.design_snapshot_digest) fail("RESPONSE_ASSOCIATION_MISMATCH");
  exact(response.claimed_issuer, ["issuer_id", "issuer_role", "claim_basis"], "claimed_issuer");
  if (response.claimed_issuer.issuer_id !== "GOAL_WORKBENCH_06_TEST_PRODUCER" || response.claimed_issuer.claim_basis !== "TEST_AUTHORED_NOT_SOURCE_OWNER") fail("FORGED_SOURCE_OWNER_OR_PROVENANCE");
  if (response.result_kind !== "PARTIAL_RESPONSE") fail("RESULT_KIND_MISMATCH");
  exact(response.content, ["source_snapshot", "capability_declaration", "evidence_relationship", "applicability_assessment"], "response.content");
  exact(response.content.capability_declaration, ["status", "template_id", "active_goal", "technical_scope", "field_coverage", "source_artifact_ids"], "capability_declaration");
  exact(response.content.evidence_relationship, ["status", "fixture_id", "evidence_kind", "case_scope", "request_digest", "result_digest", "measurement_ids", "physics_ids", "source_artifact_id", "execution_relationship"], "evidence_relationship");
  exact(response.content.applicability_assessment, ["status", "assumptions", "exclusions", "limitations", "answered_question_ids", "partial_question_ids", "unsupported_question_ids", "unanswered_question_ids", "reason_ids_addressed", "reason_ids_remaining", "supporting_evidence_refs", "supersedes_response_id", "next_decision", "restart_event"], "applicability_assessment");
  if (response.content_digest !== B.digestValue(response.content)) fail("RESPONSE_CONTENT_DIGEST_MISMATCH");
  const capability = response.content.capability_declaration;
  if (capability.status !== "SUPPORTED_EXACT_PUBLIC_DYNAMICS_TECHNICAL_DECLARATION" || capability.template_id !== "periodic_viscous_burgers_1d_v1" || capability.active_goal !== "Dynamics") fail("INTENT_MISMATCH");
  const evidence = response.content.evidence_relationship;
  if (evidence.fixture_id !== "C05-PUBLIC-EVAL2-PERTURBED" || evidence.case_scope !== "ONE_EXACT_PUBLIC_EVAL_CASE_NOT_A_CAMPAIGN" || evidence.execution_relationship !== "HISTORICAL_CONTEXT_NOT_FRESH_EXECUTION") fail("SOURCE_SCOPE_OR_EXECUTION_LAUNDERING");
  if (evidence.request_digest !== "sha256:cbd8f66c1c501325cb74c4c95c197b0a957a58334bb37a4853e9524c2a78a857" || evidence.result_digest !== "sha256:92aee39eb3f293f1d18cbc40837837a715492314a2565a14cc0b6aba636be8d1") fail("SOURCE_SCOPE_OR_EXECUTION_LAUNDERING");
  const assessment = response.content.applicability_assessment;
  if (assessment.status !== "UNRESOLVED_TEST_AUTHORED_PREVIEW" || assessment.reason_ids_addressed.length !== 0) fail("UNSUPPORTED_APPLICABILITY_RESOLUTION");
  same(assessment.reason_ids_remaining, request.scope.unresolved_reason_ids, "REVIEW_REASON_LOSS");
  if (assessment.supersedes_response_id !== null) fail("UNSUPPORTED_SUPERSESSION");
  validateCeiling(response.authority_ceiling);
}

function resolveArtifact(relative) {
  if (typeof relative !== "string" || path.isAbsolute(relative)) fail("UNSAFE_ARTIFACT_PATH");
  const absolute = path.resolve(ROOT, relative);
  if (!absolute.startsWith(`${ROOT}${path.sep}`)) fail("UNSAFE_ARTIFACT_PATH");
  return absolute;
}

async function validateC05(raw) {
  const index = JSON.parse(fs.readFileSync(path.join(WB, "data", "c05_fixture_index_v2.json"), "utf8"));
  E.installFixtureIndex(index);
  const job = G.newJob("job-001", "GOAL-WORKBENCH-06 detached conformance");
  const design = job.designs[0];
  design.scope.physics_family = "periodic_viscous_burgers_1d_v1";
  design.requirements = [G.requirement("REQ-DYNAMICS", "Predict complete field evolution.", "public fixture", "Inform bounded design")];
  const trace = G.trace("TRACE-DYNAMICS", "REQ-DYNAMICS");
  Object.assign(trace, { measurement_definition: "source C-05 measurement", authoring_binding: "carbon.goal-authoring-proposal/1", role: "MANDATORY", floor: "source-owned DEVELOPMENT normalization only" });
  design.traces = [trace];
  const caseFamily = G.caseFamily("BURGERS-12-CELL", "EVAL");
  Object.assign(caseFamily, { requirement_ids: ["REQ-DYNAMICS"], generator_ref: "goal_burgers_12cell_v1", support_status: "SOURCE_SUPPORTED" });
  design.cases = [caseFamily];
  const request = G.diagnosticRequest(design, "diagnostic-job-001-design-1-r1");
  const result = await E.importBundle(design, request, raw, async (value) => crypto.createHash("sha256").update(value).digest("hex"));
  if (result.record.measurements.length !== 4 || result.record.physics.length !== 6 || !result.record.measurements.every((m) => m.uncertainty === null && m.scientific_limit === null && m.decision === "UNRESOLVED_NO_QUALIFIED_LIMIT")) fail("C05_SCOPE_OR_UNKNOWN_STATE_MISMATCH");
  return result.record;
}

async function validateSources(profile, request, response) {
  const byId = {};
  for (const item of profile.source_artifacts) {
    exact(item, ["artifact_id", "path", "sha256", "fact_scope"], `artifact.${item.artifact_id}`);
    const file = resolveArtifact(item.path);
    const bytes = fs.readFileSync(file);
    if (sha(bytes) !== item.sha256) fail("SOURCE_ARTIFACT_DIGEST_MISMATCH", item.artifact_id);
    if (response.content.source_snapshot[item.artifact_id] !== item.sha256) fail("RESPONSE_SOURCE_SNAPSHOT_MISMATCH", item.artifact_id);
    byId[item.artifact_id] = { file, bytes };
  }
  const authoring = F.strictJsonParse(new TextDecoder("utf-8", { fatal: true }).decode(byId.authoring_result.bytes), { maxBytes: 200000, maxDepth: 24 });
  const proposal = F.strictJsonParse(new TextDecoder("utf-8", { fatal: true }).decode(byId.native_proposal.bytes), { maxBytes: 200000, maxDepth: 24 });
  if (authoring.semantic_receipt.status !== "INTENT_PRESERVED" || authoring.semantic_receipt.emitted.active_goal !== "Dynamics" || authoring.semantic_receipt.qualification !== "NOT_QUALIFIED" || authoring.semantic_receipt.launch !== "NOT_LAUNCHED") fail("AUTHORING_SOURCE_FACT_MISMATCH");
  if (proposal.challenge.primary_goal !== "Dynamics" || proposal.status !== "DEVELOPMENT_PROPOSAL" || proposal.capabilities.scientifically_qualified !== false) fail("PROPOSAL_SOURCE_FACT_MISMATCH");
  const c05 = await validateC05(byId.c05_public_bundle.bytes.toString("utf8"));
  if (c05.source.request_digest !== response.content.evidence_relationship.request_digest || c05.source.result_digest !== response.content.evidence_relationship.result_digest) fail("C05_IDENTITY_MISMATCH");
  if (request.scope.evidence_bindings[0].source_digest !== profile.source_artifacts.find((a) => a.artifact_id === "c05_public_bundle").sha256) fail("C05_BINDING_ARTIFACT_MISMATCH");
}

function validateSnapshot(request, snapshotInput) {
  const snapshot = snapshotInput.value;
  if (snapshot.job_id !== request.association.job_id || snapshot.design_id !== request.association.design_id || snapshot.design_revision !== request.association.design_revision || snapshot.design_status !== "SEALED") fail("DESIGN_SNAPSHOT_ASSOCIATION_MISMATCH");
  if (B.digestValue(snapshot) !== request.association.design_snapshot_digest || sha(snapshotInput.bytes) !== request.association.design_snapshot_artifact_digest) fail("DESIGN_SNAPSHOT_DIGEST_MISMATCH");
}

function receiptFor(profile, request, response, inputs) {
  const assessment = response.content.applicability_assessment;
  return {
    schema: "carbon.goal-workbench.source-assessment-validation-receipt.v1",
    contract_version: "1.0",
    profile_id: profile.profile_id,
    request_id: request.request_id,
    response_id: response.response_id,
    input_digests: {
      profile_artifact: sha(inputs.profile.bytes), request_artifact: sha(inputs.request.bytes), response_artifact: sha(inputs.response.bytes),
      request_canonical: B.digestValue(request), response_content_canonical: B.digestValue(response.content), design_snapshot_artifact: sha(inputs.snapshot.bytes), design_snapshot_canonical: B.digestValue(inputs.snapshot.value),
    },
    association: { status: "EXACT", job_id: request.association.job_id, design_id: request.association.design_id, design_revision: request.association.design_revision, design_snapshot_digest: request.association.design_snapshot_digest },
    origin_verification: {
      status: "FIXTURE_BYTES_MATCH_TEST_PRODUCER_NOT_SOURCE_OWNER",
      claimed_issuer: response.claimed_issuer.issuer_id,
      established: ["exact contract-fixture bytes", "exact accepted local authoring-bridge artifact bytes", "exact pinned C-05 fixture bytes and association"],
      not_established: ["live operator identity", "source-owner acceptance", "independent review", "scientific qualification", "rights authorization"],
    },
    interpretation: {
      status: "VALID_NON_AUTHORITATIVE_PREVIEW",
      answered: assessment.answered_question_ids,
      partial: assessment.partial_question_ids,
      unsupported: assessment.unsupported_question_ids,
      stale: [], contradictory: [], unresolved: assessment.unanswered_question_ids,
      qualification_effect: "NONE", workspace_effect: "NONE_DETACHED_PREVIEW",
    },
    review_obligations: { addressed_reason_ids: assessment.reason_ids_addressed, remaining_reason_ids: assessment.reason_ids_remaining, prohibitions_retained: ["NO_RIGHTS_GRANTED"], supersession: "NONE" },
    authority_ceiling: { ...response.authority_ceiling },
    execution: { mode: "DETACHED_DRY_RUN", solver_runs: 0, training_runs: 0, network_requests: 0, account_actions: 0 },
  };
}

function escapeMarkdown(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function previewFor(request, response, receipt) {
  const a = response.content.applicability_assessment;
  return `# GOAL-WORKBENCH-06 detached interpretation preview\n\n` +
    `- Question: ${escapeMarkdown(request.question.text)}\n` +
    `- Source scope: ${escapeMarkdown(response.content.capability_declaration.technical_scope)}\n` +
    `- Evidence: ${escapeMarkdown(response.content.evidence_relationship.fixture_id)}; ${escapeMarkdown(response.content.evidence_relationship.case_scope)}; ${escapeMarkdown(response.content.evidence_relationship.execution_relationship)}.\n` +
    `- Claimed issuer: ${escapeMarkdown(response.claimed_issuer.issuer_id)} (${escapeMarkdown(response.claimed_issuer.claim_basis)}).\n` +
    `- Origin verification: ${receipt.origin_verification.status}. This does not authenticate a live source owner.\n` +
    `- Answered: ${a.answered_question_ids.map(escapeMarkdown).join(", ")}.\n` +
    `- Partial: ${a.partial_question_ids.map(escapeMarkdown).join(", ")}.\n` +
    `- Unresolved: ${a.unanswered_question_ids.map(escapeMarkdown).join(", ")}.\n` +
    `- Review reasons remaining: ${a.reason_ids_remaining.map(escapeMarkdown).join(", ")}.\n` +
    `- Next action: ${escapeMarkdown(a.next_decision)}\n` +
    `- Restart event: ${escapeMarkdown(a.restart_event)}\n\n` +
    `This detached preview does not update the Workbench and creates no scientific qualification, rights grant, execution claim, score eligibility, protected-use authority, or launch authority.\n`;
}

async function validateObjects(profile, request, response, snapshotInput) {
  validateProfile(profile);
  validateRequest(request);
  validateResponse(response, request);
  validateSnapshot(request, snapshotInput);
  await validateSources(profile, request, response);
  return true;
}

function reconcileResponses(responses) {
  const seen = new Map();
  for (const response of responses) {
    const key = response.response_id;
    const digest = B.digestValue(response);
    if (seen.has(key) && seen.get(key) !== digest) fail("CONFLICTING_RESPONSE_IDENTITY");
    seen.set(key, digest);
  }
  const byRequest = new Map();
  for (const response of responses) {
    const prior = byRequest.get(response.request_id);
    if (prior && prior.content_digest !== response.content_digest && response.content.applicability_assessment.supersedes_response_id !== prior.response_id) fail("RECONCILIATION_REQUIRED");
    byRequest.set(response.request_id, response);
  }
  return { disposition: "CONSISTENT", unique_responses: seen.size };
}

function interpretCandidate(request, response) {
  validateCeiling(response.authority_ceiling);
  if (response.request_id !== request.request_id || response.request_digest !== B.digestValue(request)) fail("RESPONSE_REQUEST_MISMATCH");
  if (response.association.job_id !== request.association.job_id || response.association.design_id !== request.association.design_id || response.association.design_revision !== request.association.design_revision || response.association.design_snapshot_digest !== request.association.design_snapshot_digest) fail("RESPONSE_ASSOCIATION_MISMATCH");
  if (response.content_digest !== B.digestValue(response.content)) fail("RESPONSE_CONTENT_DIGEST_MISMATCH");
  const assessment = response.content.applicability_assessment;
  for (const reason of assessment.reason_ids_addressed) if (!request.scope.unresolved_reason_ids.includes(reason)) fail("OUT_OF_SCOPE_REASON_RESOLUTION", reason);
  const remaining = [...new Set([...request.scope.unresolved_reason_ids.filter((id) => !assessment.reason_ids_addressed.includes(id)), ...assessment.reason_ids_remaining])].sort();
  if (response.result_kind === "UNSUPPORTED_SCOPE" || response.result_kind === "NAMED_BLOCKER") {
    if (assessment.reason_ids_addressed.length) fail("UNSUPPORTED_RESPONSE_CANNOT_RESOLVE_REASONS");
    return { status: response.result_kind, remaining_reason_ids: remaining, qualification_effect: "NONE", rights_effect: "NONE" };
  }
  return { status: response.result_kind, remaining_reason_ids: remaining, qualification_effect: "NONE", rights_effect: "NONE" };
}

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 2) {
    if (!argv[i].startsWith("--") || argv[i + 1] === undefined) fail("USAGE");
    out[argv[i].slice(2)] = argv[i + 1];
  }
  for (const key of ["profile", "request", "response", "output-dir"]) if (!out[key]) fail("USAGE", `missing --${key}`);
  return out;
}

async function run(argv = process.argv) {
  const args = parseArgs(argv);
  const output = path.resolve(args["output-dir"]);
  if (fs.existsSync(output)) fail("OUTPUT_DIRECTORY_ALREADY_EXISTS");
  const inputs = {
    profile: readBounded(path.resolve(args.profile)), request: readBounded(path.resolve(args.request)), response: readBounded(path.resolve(args.response)),
  };
  const snapshotPath = resolveArtifact(path.posix.join("Business/Carbon_Fit/workbench/source_assessment/v1", inputs.request.value.association.design_snapshot_ref));
  inputs.snapshot = readBounded(snapshotPath);
  await validateObjects(inputs.profile.value, inputs.request.value, inputs.response.value, inputs.snapshot);
  const receipt = receiptFor(inputs.profile.value, inputs.request.value, inputs.response.value, inputs);
  const preview = previewFor(inputs.request.value, inputs.response.value, receipt);
  const receiptRaw = `${JSON.stringify(receipt, null, 2)}\n`;
  const manifest = {
    schema_version: "carbon.goal-workbench.source-assessment-output-manifest.v1",
    files: [
      { path: "validation_receipt.json", bytes: Buffer.byteLength(receiptRaw), sha256: sha(Buffer.from(receiptRaw)) },
      { path: "interpretation_preview.md", bytes: Buffer.byteLength(preview), sha256: sha(Buffer.from(preview)) },
    ],
    atomic_validation_completed_before_write: true,
  };
  fs.mkdirSync(output);
  fs.writeFileSync(path.join(output, "validation_receipt.json"), receiptRaw, "utf8");
  fs.writeFileSync(path.join(output, "interpretation_preview.md"), preview, "utf8");
  fs.writeFileSync(path.join(output, "output_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({ disposition: "VALID_NON_AUTHORITATIVE_PREVIEW", output_directory: output, request_id: receipt.request_id, response_id: receipt.response_id })}\n`);
  return { receipt, preview, manifest };
}

if (require.main === module) run().catch((error) => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
module.exports = { exact, readBounded, validateCeiling, validateProfile, validateRequest, validateResponse, validateSnapshot, validateSources, validateObjects, interpretCandidate, reconcileResponses, receiptFor, previewFor, run };
