#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const F = require("../src/engine.js");
const R = require("../src/routing.js");
const E = require("../src/c05_evidence.js");
const S = require("../src/source_assessment.js");
const G = require("../src/workflow.js");

const ROOT = path.resolve(__dirname, "..");
const BASE = path.join(ROOT, "source_assessment", "repository_snapshot", "v1");
const CANDIDATE = path.join(BASE, "candidate");
const TEST = path.join(BASE, "test_fixtures");
const read = (name) => JSON.parse(fs.readFileSync(path.join(ROOT, name), "utf8"));
const clone = (value) => JSON.parse(JSON.stringify(value));
const write = (name, value) => {
  fs.mkdirSync(path.dirname(name), { recursive: true });
  fs.writeFileSync(name, JSON.stringify(value, null, 2) + "\n");
};
const writeText = (name, value) => {
  fs.mkdirSync(path.dirname(name), { recursive: true });
  fs.writeFileSync(name, value);
};

async function publicDesign() {
  const job = G.newJob("job-001", "Public Burgers Dynamics source assessment");
  job.accountable_owner = "Ryan / github:jbequ5";
  job.lead = "Engineering";
  const d = job.designs[0];
  Object.assign(d.scope, {
    physics_family: "periodic_viscous_burgers_1d_v1",
    requested_goal: "Dynamics",
    intended_use: "Public synthetic periodic viscous Burgers Dynamics technical assessment only",
    inputs: "Finite Fourier initial field, positive viscosity, requested times, and declared periodic domain length",
    outputs: "Complete field evolution with compression, dissipation, and half-time diagnostics",
    units: "Source-defined nondimensional Burgers variables and declared characteristic scales",
    geometry: "One-dimensional periodic domain",
    conditions: "Periodic boundary; unforced; finite Fourier initial condition; positive viscosity",
    regime: "Exact retained C05-PUBLIC-EVAL2-PERTURBED fixed-case context",
    exclusions: "No population adequacy, qualification, rights, protected use, customer result, score, or launch",
    query_workload: "One retained public fixed-case result; no fresh execution",
    turnaround: "No service claim",
    failure_consequences: "Unresolved",
    data_access: "Public repository artifacts only",
    rights_scope: "UNRESOLVED",
    commercial_context: "Public synthetic demonstration",
    disclosure_scope: "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
    deployment_environment: "Not assessed",
  });
  d.requirements = [G.requirement("REQ-DYNAMICS", "Predict complete field evolution without allowing a favorable average to offset mandatory physical failure.", "Public synthetic GOAL-WORKBENCH-07 fixture", "Test exact technical expressibility only")];
  const trace = G.trace("TRACE-DYNAMICS", "REQ-DYNAMICS");
  Object.assign(trace, { observable: "field, compression, dissipation, half-time", requested_output: "complete periodic trajectory", measurement_definition: "source-owned C-05 public DEVELOPMENT result", numerical_method: "source-owned C-AUTH1/C-05 definitions", role: "MANDATORY", normalization: "source record", floor: "unresolved", aggregation: "not qualified", uncertainty: "null/unresolved", population_ref: "fixed public case only", stratum_ref: "EVAL cell 2", finite_case_coverage: "one case", reference_requirement: "retained identity only", authoring_binding: "carbon.goal-authoring-proposal/1" });
  d.traces = [trace];
  const cases = G.caseFamily("BURGERS-12-CELL", "EVAL");
  Object.assign(cases, { requirement_ids: ["REQ-DYNAMICS"], target_population: "source-defined public DEVELOPMENT cells", target_mass: "unresolved", sampling_frequency: "one retained fixed case in this assessment", analysis_weight: "none", independent_physical_cases: "one retained case", reconstruction_replicas: "one test-created perturbed candidate", generator_ref: "goal_burgers_12cell_v1", rationale: "Preserve the exact C-05 fixture association", support_status: "SOURCE_SUPPORTED" });
  d.cases = [cases];
  d.authoring.template_id = "periodic_viscous_burgers_1d_v1";
  d.authoring.requested_goal = "Dynamics";
  d.authoring.compatibility = "EXACT_SUPPORTED";
  d.authoring.request_id = "GW06-C-AUTH1-PUBLIC-REQUEST";
  d.authoring.result_ref = "source_assessment/v1/fixtures/public_design_snapshot.json";
  R.selectRoute(d, "ADAPT_SUPPORTED_CHALLENGE", { rationale: "Reuse the exact public Burgers/Dynamics source profile.", source_or_capability_ref: "periodic_viscous_burgers_1d_v1 / Dynamics", route_basis: "C-AUTH1 authoring and exact retained C-05 context", unresolved_conditions: ["scientific applicability", "qualified uncertainty", "rights", "customer suitability"], next_decision: "Ryan may adopt only the exact technical statement; all other obligations remain.", selected_by_assertion: "GOAL-WORKBENCH-07 public fixture builder", status_provenance: "LOCAL_MANUAL_ASSERTION" });
  E.installFixtureIndex(read("data/c05_fixture_index_v2.json"));
  const bundleRaw = fs.readFileSync(path.join(ROOT, "data", "c05_public_development_evidence_v1.json"), "utf8");
  await E.importBundle(d, G.diagnosticRequest(d, "diagnostic-job-001-design-1-r1"), bundleRaw, S.sha256);
  d.status = "SEALED";
  G.validateDesign(d, d.job_id);
  return d;
}

async function responseFor(request, claimedPrincipal) {
  return {
    schema_version: S.RESPONSE_VERSION,
    profile_id: S.PROFILE_ID,
    response_id: "GW07-BURGERS-DYNAMICS-ASSESSMENT-001",
    request_id: request.request_id,
    request_digest: await S.digest(request),
    association: request.association,
    subject_digest: request.subject_digest,
    prepared_by: "GOAL-WORKBENCH-07 Engineering",
    claimed_issuer: { principal: claimedPrincipal, role: claimedPrincipal === "github:jbequ5" ? "FINAL_INTERFACE_OWNER" : "ENGINEERING_PREPARER", claim_basis: "PRODUCER_CLAIM_UNVERIFIED" },
    result_kind: "PARTIAL_RESPONSE",
    answered: [
      { question_id: "GW07:AUTHORING_EXPRESSIBILITY", domain: "AUTHORING_EXPRESSIBILITY", status: "ANSWERED", statement: "The named accepted authoring path expresses Dynamics for the exact public synthetic periodic Burgers scope recorded by this request.", addressed_reason_ids: [], supporting_refs: ["source_assessment/v1/fixtures/public_design_snapshot.json", "carbon/authoring/goals.py"] },
      { question_id: "GW07:SOURCE_ARTIFACT_IDENTITY", domain: "SOURCE_ARTIFACT_IDENTITY", status: "ANSWERED", statement: "The request cites the exact retained C05-PUBLIC-EVAL2-PERTURBED source identities without creating a fresh execution.", addressed_reason_ids: [], supporting_refs: ["data/c05_public_development_evidence_v1.json", "data/c05_fixture_index_v2.json"] },
      { question_id: "GW07:FIXED_EVIDENCE_RELATIONSHIP", domain: "FIXED_EVIDENCE_RELATIONSHIP", status: "PARTIAL", statement: "The retained C-05 record supplies one fixed public DEVELOPMENT observation only; population adequacy, scientific applicability, limits, uncertainty, rights, and customer suitability remain unresolved.", addressed_reason_ids: [], supporting_refs: ["data/c05_public_development_evidence_v1.json"] },
    ],
    unanswered_question_ids: ["GW07:FIXED_EVIDENCE_RELATIONSHIP"],
    source_basis: ["C-AUTH1 public Burgers/Dynamics authoring contract", "C05-PUBLIC-EVAL2-PERTURBED retained public DEVELOPMENT bytes"],
    limitations: ["Prepared by Engineering; pending exact Ryan adoption.", "Ryan is not claimed to have run the compiler, solver, or measurement.", "No scientific qualification, rights grant, fresh execution, population claim, protected use, score, or launch follows."],
    supersedes_response_ids: [],
    next_action: "Ryan adopts, changes, or rejects these exact bytes; Engineering may admit only an exact adoption in a later accepted snapshot.",
    authority_ceiling: { ...S.AUTHORITY_CEILING },
  };
}

function publicExampleWorkspace(design, request) {
  const atlas = read("data/atlas.json");
  const component = {
    schema_version: F.WORKSPACE_VERSION,
    application_version: F.APP_VERSION,
    source_sha256: atlas.source.sha256,
    evidence_catalog: [],
    drafts: [],
    shortlist: [],
    migration_receipts: [],
  };
  const workspace = G.newWorkspace(component);
  const job = G.newJob(
    design.job_id,
    "Public Burgers Dynamics source assessment",
  );
  job.accountable_owner = "Ryan / github:jbequ5";
  job.lead = "Engineering";
  job.designs = [clone(design)];
  job.working_design_id = design.design_id;
  job.designs[0].source_assessments.requests.push(clone(request));
  job.designs[0].source_assessments.current_request_id = request.request_id;
  workspace.jobs = [job];
  workspace.selected_job_id = job.job_id;
  workspace.selected_design_id = design.design_id;
  G.validateWorkspace(workspace, (rawValue) =>
    F.readWorkspace(
      rawValue,
      atlas.opportunities.map((item) => item.id),
      atlas.source.sha256,
    ),
  );
  return workspace;
}

async function main() {
  const protectedProductionRecords = [
    "profile.json",
    "approved_assessments.json",
    "adoption/owner_gw07_ryan_snapshot_01.json",
  ].map((name) => [name, fs.readFileSync(path.join(BASE, name), "utf8")]);
  const design = await publicDesign();
  const request = await S.buildRequest(design, "GW07-BURGERS-DYNAMICS-REQUEST-001");
  const exampleWorkspace = publicExampleWorkspace(design, request);
  const candidate = await responseFor(request, "github:jbequ5");
  const testResponse = await responseFor(request, "github:jbequ5");
  testResponse.claimed_issuer.claim_basis = "REPOSITORY_ADOPTION_REFERENCE";
  const testRaw = JSON.stringify(testResponse, null, 2) + "\n";
  const profile = read("source_assessment/repository_snapshot/v1/profile.json");
  profile.snapshot_id = "TEST-ONLY-GW07-SNAPSHOT-01";
  profile.test_only = true;
  const canonicalDigest = await S.digest(testResponse);
  const testIndex = {
    schema_version: S.SNAPSHOT_VERSION,
    snapshot_id: profile.snapshot_id,
    test_only: true,
    entries: [{
      assessment_id: testResponse.response_id,
      request_id: request.request_id,
      request_digest: testResponse.request_digest,
      subject_digest: request.subject_digest,
      response_raw_sha256: "sha256:" + await S.sha256(testRaw),
      response_canonical_digest: canonicalDigest,
      issuer_principal: "github:jbequ5",
      allowed_domains: [...S.TECHNICAL_DOMAINS],
      owner_adoption_ref: "test-only:synthetic-owner-adoption/GW07-001",
      owner_adoption_content_digest: canonicalDigest,
      state: "CURRENT",
      withdrawn_reason: "",
      supersedes_assessment_ids: [],
      conflicts_with_assessment_ids: [],
    }],
  };
  // These are the exact historical Workbench-07A bytes adopted by Ryan. The
  // maintained Workbench can advance without rewriting that frozen subject.
  const historicalDesign = clone(design);
  historicalDesign.schema_version = "carbon.goal-workbench.design.v0.8";
  delete historicalDesign.assessment;
  const historicalWorkspace = clone(exampleWorkspace);
  historicalWorkspace.schema_version = "carbon.goal-workbench.workspace.v0.8";
  historicalWorkspace.application_version = "Carbon Goal-to-Challenge Workbench v0.8";
  historicalWorkspace.decision_id = "GOAL-WORKBENCH-08";
  historicalWorkspace.base_application_merge = "94762b6a8932ac6834c731a416c3a45c4cbf6170";
  for (const historicalJob of historicalWorkspace.jobs) {
    delete historicalJob.team_review;
    for (const historical of historicalJob.designs) {
      historical.schema_version = "carbon.goal-workbench.design.v0.8";
      delete historical.assessment;
    }
  }
  write(path.join(CANDIDATE, "public_design.json"), historicalDesign);
  write(path.join(CANDIDATE, "request.json"), request);
  write(path.join(CANDIDATE, "assessment_pending_adoption.json"), candidate);
  write(path.join(CANDIDATE, "public_example_workspace.json"), historicalWorkspace);
  write(path.join(TEST, "profile.test-only.json"), profile);
  write(path.join(TEST, "approved_assessments.test-only.json"), testIndex);
  write(path.join(TEST, "assessment.test-only.json"), testResponse);
  const requestRaw = fs.readFileSync(path.join(CANDIDATE, "request.json"), "utf8");
  const candidateRaw = fs.readFileSync(path.join(CANDIDATE, "assessment_pending_adoption.json"), "utf8");
  const candidateDigest = await S.digest(candidate);
  writeText(path.join(CANDIDATE, "RYAN_ADOPTION_PACKET.md"), `# OWNER-GW07-RYAN-SNAPSHOT-01 — exact assessment adoption packet

Status: \`PENDING_EXACT_OWNER_ADOPTION\`

Accountable owner: Ryan, Carbon creator, GitHub \`@jbequ5\`

Actual preparer: GOAL-WORKBENCH-07 Engineering

Operational profile: \`${S.PROFILE_ID}\`

## Exact content proposed for adoption

- Request ID: \`${request.request_id}\`
- Assessment ID: \`${candidate.response_id}\`
- Frozen subject digest: \`${request.subject_digest}\`
- Request canonical digest: \`${await S.digest(request)}\`
- Request file SHA-256: \`${await S.sha256(requestRaw)}\`
- Assessment file SHA-256: \`${await S.sha256(candidateRaw)}\`
- Assessment canonical digest: \`${candidateDigest}\`

The exact human-readable statement is:

> For the exact frozen public synthetic Burgers/Dynamics request, the named accepted authoring path expresses Dynamics within that source-defined scope. The request cites the retained \`C05-PUBLIC-EVAL2-PERTURBED\` identities as one historical fixed-case DEVELOPMENT observation, not a fresh execution or population result. Scientific applicability, qualified limits and uncertainty, rights, protected use, customer suitability, scoring, and launch remain unresolved or outside this assessment.

Answered technical questions: \`GW07:AUTHORING_EXPRESSIBILITY\` and \`GW07:SOURCE_ARTIFACT_IDENTITY\`.

Partially answered and still open: \`GW07:FIXED_EVIDENCE_RELATIONSHIP\`.

## Ryan disposition

Ryan may adopt the exact content by replying in the accepted owner channel with:

\`\`\`text
ADOPT OWNER-GW07-RYAN-SNAPSHOT-01
assessment_id: ${candidate.response_id}
assessment_file_sha256: ${await S.sha256(candidateRaw)}
assessment_canonical_digest: ${candidateDigest}
scope: AUTHORING_EXPRESSIBILITY,SOURCE_ARTIFACT_IDENTITY,FIXED_EVIDENCE_RELATIONSHIP
\`\`\`

Or Ryan may name the exact field/statement to change, or reject the candidate. An agent-authored comment, ordinary PR merge, matching hash, silence, or broad interface-policy acceptance is not this adoption.

After exact adoption, Engineering may add only this assessment and its adoption locator/digest to a new repository snapshot, run the same build-time and browser validation, and deliver that snapshot normally. The assessment does not need to be rewritten and the broad policy questions do not need to be reopened.

No source assessment is presently admitted by the shipped production index.
`);
  const manifest = { schema_version: "carbon.goal-workbench.source-assessment-fixture-manifest.v1", generated_by: "tools/build_repository_snapshot_fixtures.cjs", production_index_state: "ADMITTED_PRODUCTION_SNAPSHOT_PROTECTED; HISTORICAL_EMPTY_FIXTURES_RETAINED", files: {} };
  for (const file of ["public_design.json", "request.json", "assessment_pending_adoption.json", "public_example_workspace.json", "RYAN_ADOPTION_PACKET.md"]) {
    const raw = fs.readFileSync(path.join(CANDIDATE, file), "utf8");
    manifest.files["candidate/" + file] = { bytes: Buffer.byteLength(raw), sha256: await S.sha256(raw) };
  }
  for (const file of ["profile.test-only.json", "approved_assessments.test-only.json", "assessment.test-only.json", "profile.empty-historical.json", "approved_assessments.empty-historical.json"]) {
    const raw = fs.readFileSync(path.join(TEST, file), "utf8");
    manifest.files["test_fixtures/" + file] = { bytes: Buffer.byteLength(raw), sha256: await S.sha256(raw) };
  }
  write(path.join(BASE, "fixture_manifest.json"), manifest);
  for (const [name, before] of protectedProductionRecords) {
    const after = fs.readFileSync(path.join(BASE, name), "utf8");
    if (after !== before)
      throw Error("Fixture regeneration modified protected production record: " + name);
  }
}

if (require.main === module) main().catch((error) => { console.error(error); process.exitCode = 1; });
module.exports = { publicDesign, responseFor, publicExampleWorkspace, main };
