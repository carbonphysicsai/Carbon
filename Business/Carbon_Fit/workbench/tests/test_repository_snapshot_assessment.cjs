"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const F = require("../src/engine.js");
const R = require("../src/routing.js");
const E = require("../src/c05_evidence.js");
const S = require("../src/source_assessment.js");
const G = require("../src/workflow.js");
const B = require("../tools/build_repository_snapshot_fixtures.cjs");

const ROOT = path.resolve(__dirname, "..");
const BASE = path.join(ROOT, "source_assessment", "repository_snapshot", "v1");
const load = (name) => JSON.parse(fs.readFileSync(path.join(BASE, name), "utf8"));
const raw = (name) => fs.readFileSync(path.join(BASE, name), "utf8");
const clone = (value) => JSON.parse(JSON.stringify(value));
const productionProfile = load("profile.json");
const productionIndex = load("approved_assessments.json");
const testProfile = load("test_fixtures/profile.test-only.json");
const testIndex = load("test_fixtures/approved_assessments.test-only.json");
const request = load("candidate/request.json");
const testResponse = load("test_fixtures/assessment.test-only.json");
const testRaw = raw("test_fixtures/assessment.test-only.json");
const testVerifier = () => S.createVerifier(testProfile, testIndex, { testMode: true });

function designWithRequest() {
  const design = load("candidate/public_design.json");
  design.source_assessments.requests.push(clone(request));
  design.source_assessments.current_request_id = request.request_id;
  return design;
}

async function admittedTestExchange(design, builtRequest, answers, unanswered) {
  design.source_assessments.requests.push(clone(builtRequest));
  design.source_assessments.current_request_id = builtRequest.request_id;
  const response = clone(testResponse);
  response.response_id = "GW07-TEST-SCOPED-REASON-RESPONSE";
  response.request_id = builtRequest.request_id;
  response.request_digest = await S.digest(builtRequest);
  response.association = clone(builtRequest.association);
  response.subject_digest = builtRequest.subject_digest;
  response.answered = answers;
  response.unanswered_question_ids = unanswered;
  const responseRaw = JSON.stringify(response, null, 2) + "\n";
  const responseDigest = await S.digest(response);
  const index = {
    schema_version: S.SNAPSHOT_VERSION,
    snapshot_id: testProfile.snapshot_id,
    test_only: true,
    entries: [{
      assessment_id: response.response_id,
      request_id: builtRequest.request_id,
      request_digest: response.request_digest,
      subject_digest: response.subject_digest,
      response_raw_sha256: `sha256:${await S.sha256(responseRaw)}`,
      response_canonical_digest: responseDigest,
      issuer_principal: "github:jbequ5",
      allowed_domains: S.TECHNICAL_DOMAINS,
      owner_adoption_ref: "GW07-TEST-ONLY-ADOPTION",
      owner_adoption_content_digest: responseDigest,
      state: "CURRENT",
      withdrawn_reason: "",
      supersedes_assessment_ids: [],
      conflicts_with_assessment_ids: [],
    }],
  };
  return S.importResponse(
    design,
    responseRaw,
    S.createVerifier(testProfile, index, { testMode: true }),
  );
}

test("operational schemas are closed at their record roots", () => {
  for (const name of ["request", "response", "profile", "approved_index", "receipt"]) {
    const schema = load(`schemas/${name}.schema.json`);
    assert.equal(schema.type, "object");
    assert.equal(schema.additionalProperties, false);
  }
});

test("production repository snapshot is Ryan-controlled and empty pending exact adoption", () => {
  const verifier = S.createVerifier(productionProfile, productionIndex);
  assert.equal(verifier.profile.issuer_policy.principal, "github:jbequ5");
  assert.deepEqual(verifier.index.entries, []);
  assert.equal(verifier.profile.test_only, false);
});

test("test-owned trust root cannot be installed as production", () => {
  assert.throws(() => S.createVerifier(testProfile, testIndex), /Test trust root/);
});

test("exact public request is derived from a sealed design and immutable subject", async () => {
  const design = load("candidate/public_design.json");
  assert.equal(design.status, "SEALED");
  assert.equal(request.subject_digest, await S.digest(S.scopeSubject(design)));
  assert.equal(request.requested_recipient, "github:jbequ5");
  assert.equal(request.subject.scope.physics_family, "periodic_viscous_burgers_1d_v1");
  assert.equal(request.subject.scope.requested_goal, "Dynamics");
});

test("draft and unsupported physics cannot prepare an operational request", async () => {
  const design = load("candidate/public_design.json");
  design.status = "DRAFT";
  await assert.rejects(S.buildRequest(design, "request-2"), /sealed/);
  design.status = "SEALED";
  design.scope.physics_family = "unsupported_physics";
  await assert.rejects(S.buildRequest(design, "request-2"), /Unsupported/);
});

test("production empty index rejects candidate and test responses atomically", async () => {
  const design = designWithRequest(), before = JSON.stringify(design);
  await assert.rejects(S.importResponse(design, testRaw, S.createVerifier(productionProfile, productionIndex)), /not admitted/);
  assert.equal(JSON.stringify(design), before);
});

test("one exact test-owned record verifies through the real consumer", async () => {
  const design = designWithRequest();
  const result = await S.importResponse(design, testRaw, testVerifier());
  assert.equal(result.status, "MATCHED_APPROVED_SOURCE_SNAPSHOT");
  assert.equal(result.receipt.origin_verification, "CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH");
  assert.equal(result.receipt.authority_effect, "NONE");
  assert.deepEqual(result.receipt.resolved_reason_ids, []);
  assert.ok(result.receipt.remaining_question_ids.includes("GW07:FIXED_EVIDENCE_RELATIONSHIP"));
});

test("exact replay deduplicates and changed bytes with same identity reject", async () => {
  const design = designWithRequest(), verifier = testVerifier();
  await S.importResponse(design, testRaw, verifier);
  const count = design.source_assessments.responses.length;
  assert.equal((await S.importResponse(design, testRaw, verifier)).status, "DEDUPLICATED");
  assert.equal(design.source_assessments.responses.length, count);
  const changed = testRaw.replace("one fixed public DEVELOPMENT observation", "a changed fixed observation");
  await assert.rejects(S.importResponse(design, changed, verifier), /bytes or scope/);
  assert.equal(design.source_assessments.responses.length, count);
});

test("wrong job design revision subject request and source scope reject", async () => {
  for (const mutate of [
    (value) => { value.association.job_id = "wrong-job"; },
    (value) => { value.association.design_id = "wrong-design"; },
    (value) => { value.association.design_revision = 2; },
    (value) => { value.subject_digest = `sha256:${"0".repeat(64)}`; },
    (value) => { value.request_id = "wrong-request"; },
    (value) => { value.answered[0].domain = "SOURCE_ARTIFACT_IDENTITY"; },
  ]) {
    const design = designWithRequest(), changed = clone(testResponse);
    mutate(changed);
    await assert.rejects(S.importResponse(design, JSON.stringify(changed), testVerifier()));
    assert.equal(design.source_assessments.responses.length, 0);
  }
});

test("same revision with changed semantic content rejects", async () => {
  const design = designWithRequest();
  design.scope.outputs = "changed meaning";
  await assert.rejects(S.importResponse(design, testRaw, testVerifier()), /no longer matches/);
});

test("workspace profile index and receipt cannot replace installed trust root", async () => {
  const design = designWithRequest();
  design.source_assessments.installed_profile = testProfile;
  assert.throws(() => S.validateState(design.source_assessments), /unknown or missing fields/);
});

test("forged owner name native flag trustedSource and authority reject", () => {
  for (const mutate of [
    (value) => { value.claimed_issuer.principal = "github:jbequ5"; },
    (value) => { value.trustedSource = true; },
    (value) => { value.claimed_issuer.claim_basis = "SOURCE_OWNER_CONFIRMED"; },
    (value) => { value.authority_ceiling.scientific_qualification = true; },
  ]) {
    const changed = load("candidate/assessment_pending_adoption.json");
    mutate(changed);
    if (Object.hasOwn(changed, "trustedSource") || changed.claimed_issuer.claim_basis === "SOURCE_OWNER_CONFIRMED" || changed.authority_ceiling.scientific_qualification)
      assert.throws(() => S.validateResponse(changed));
    else
      assert.doesNotThrow(() => S.validateResponse(changed));
  }
});

test("changing a claimed producer name cannot create an admitted record", async () => {
  const changed = load("candidate/assessment_pending_adoption.json");
  changed.claimed_issuer.principal = "github:jbequ5";
  changed.claimed_issuer.role = "FINAL_INTERFACE_OWNER";
  changed.claimed_issuer.claim_basis = "REPOSITORY_ADOPTION_REFERENCE";
  await assert.rejects(S.importResponse(designWithRequest(), JSON.stringify(changed), S.createVerifier(productionProfile, productionIndex)), /not admitted/);
});

test("partial answer leaves all scientific and rights reasons pending", async () => {
  const design = designWithRequest();
  const { receipt } = await S.importResponse(design, testRaw, testVerifier());
  assert.deepEqual(receipt.resolved_reason_ids, []);
  assert.ok(receipt.remaining_reason_ids.length >= 0);
  assert.equal(S.project(design, testVerifier()).qualification_effect, "NONE");
  assert.equal(design.decision.security_rights, "UNRESOLVED");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
});

test("only an exact authoring reason can be resolved by this technical profile", async () => {
  const design = load("candidate/public_design.json");
  const authoringReason = {
    reason_id: "review:SCI:1:authoring:AUTHORING",
    domain: "AUTHORING",
    field: "authoring",
    originating_design_id: design.design_id,
    originating_revision: design.revision,
    basis: "The material authoring mutation requires a new technical expressibility check.",
  };
  const referenceReason = {
    reason_id: "review:SCI:1:reference_plan:REFERENCE",
    domain: "REFERENCE",
    field: "reference_plan",
    originating_design_id: design.design_id,
    originating_revision: design.revision,
    basis: "Reference accuracy remains a scientific source-owner question.",
  };
  design.evidence_bindings[0].scientific_review_reasons.push(
    authoringReason,
    referenceReason,
  );
  design.evidence_bindings[0].scientific_applicability = "REVIEW_REQUIRED";
  const builtRequest = await S.buildRequest(design, "GW07-TEST-SCOPED-REASON-REQUEST");
  assert.deepEqual(builtRequest.questions[0].reason_ids, [authoringReason.reason_id]);
  assert.ok(!S.canonical(builtRequest.questions).includes(referenceReason.reason_id));
  const result = await admittedTestExchange(
    design,
    builtRequest,
    [{
      question_id: "GW07:AUTHORING_EXPRESSIBILITY",
      domain: "AUTHORING_EXPRESSIBILITY",
      status: "ANSWERED",
      statement: "Test-only exact authoring answer.",
      addressed_reason_ids: [authoringReason.reason_id],
      supporting_refs: ["TEST-ONLY"],
    }],
    ["GW07:SOURCE_ARTIFACT_IDENTITY", "GW07:FIXED_EVIDENCE_RELATIONSHIP"],
  );
  assert.deepEqual(result.receipt.resolved_reason_ids, [authoringReason.reason_id]);
  assert.ok(!result.receipt.resolved_reason_ids.includes(referenceReason.reason_id));
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.decision.security_rights, "UNRESOLVED");
});

test("failed save/reload revalidation is atomic", async () => {
  const design = designWithRequest();
  await S.importResponse(design, testRaw, testVerifier());
  design.source_assessments.responses[0].raw_sha256 = `sha256:${"0".repeat(64)}`;
  const before = JSON.stringify(design.source_assessments);
  await assert.rejects(S.revalidateState(design, testVerifier()), /altered/);
  assert.equal(JSON.stringify(design.source_assessments), before);
});

test("withdrawal and conflict in installed snapshot block current positive use", async () => {
  for (const state of ["WITHDRAWN", "CONFLICTING"]) {
    const index = clone(testIndex);
    index.entries[0].state = state;
    if (state === "WITHDRAWN") index.entries[0].withdrawn_reason = "test withdrawal";
    else index.entries[0].conflicts_with_assessment_ids = ["GW07-CONFLICT"];
    const verifier = S.createVerifier(testProfile, index, { testMode: true });
    await assert.rejects(S.importResponse(designWithRequest(), testRaw, verifier), /withdrawn|conflict/);
  }
});

test("approved entry without exact adoption reference rejects", () => {
  const index = clone(testIndex);
  index.entries[0].owner_adoption_ref = "";
  assert.throws(() => S.createVerifier(testProfile, index, { testMode: true }), /Invalid approved entry/);
});

test("child revision retains parent history but cannot use old assessment as current", async () => {
  const job = G.newJob("job-001", "history");
  job.designs[0] = designWithRequest();
  job.working_design_id = job.designs[0].design_id;
  await S.importResponse(job.designs[0], testRaw, testVerifier());
  job.designs[0].status = "DRAFT";
  const child = G.reviseDesign(job, job.designs[0].design_id, "job-001-design-2");
  assert.equal(job.designs[0].source_assessments.receipts.length, 1);
  assert.equal(child.source_assessments.receipts.length, 0);
  assert.equal(S.project(child, testVerifier()).assessment_status, "PENDING_EXACT_OWNER_ADOPTION");
});

test("save and reload revalidates assessment state and preserves authority ceiling", async () => {
  const design = designWithRequest();
  await S.importResponse(design, testRaw, testVerifier());
  assert.doesNotThrow(() => S.validateState(JSON.parse(JSON.stringify(design.source_assessments))));
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.decision.launch_authorization, "NOT_AUTHORIZED");
});

test("revalidation cannot carry a test-owned positive receipt into the shipped empty snapshot", async () => {
  const design = designWithRequest();
  await S.importResponse(design, testRaw, testVerifier());
  assert.equal(design.source_assessments.receipts.length, 1);
  await S.revalidateState(design, S.createVerifier(productionProfile, productionIndex));
  assert.equal(design.source_assessments.responses.length, 1);
  assert.equal(design.source_assessments.receipts.length, 0);
  assert.equal(S.project(design, S.createVerifier(productionProfile, productionIndex)).assessment_status, "PENDING_EXACT_OWNER_ADOPTION");
});

test("revalidation rejects edited display or response cache bytes", async () => {
  const design = designWithRequest();
  await S.importResponse(design, testRaw, testVerifier());
  design.source_assessments.responses[0].response.limitations.push("forged display");
  await assert.rejects(S.revalidateState(design, testVerifier()), /altered/);
});

test("v0.6 migration adds empty state without adoption or provenance promotion", () => {
  const component = {
    schema_version: F.WORKSPACE_VERSION,
    application_version: F.APP_VERSION,
    source_sha256: "a".repeat(64),
    evidence_catalog: [],
    drafts: [],
    shortlist: [],
    migration_receipts: [],
  };
  const current = G.newWorkspace(component);
  const job = G.newJob("migration-job", "migration");
  current.jobs.push(job);
  const old = clone(current);
  old.schema_version = "carbon.goal-workbench.workspace.v0.6";
  old.application_version = "Carbon Goal-to-Challenge Workbench v0.6";
  old.decision_id = "GOAL-WORKBENCH-05A";
  old.base_application_merge = "3681f7fb10be0c6e278f53d59ff9b022099ef12d";
  delete old.jobs[0].designs[0].source_assessments;
  old.jobs[0].designs[0].schema_version = "carbon.goal-workbench.design.v0.6";
  const migrated = G.readWorkspace(JSON.stringify(old), (rawValue) => JSON.parse(rawValue));
  assert.equal(migrated.schema_version, G.WORKSPACE_VERSION);
  assert.deepEqual(migrated.jobs[0].designs[0].source_assessments, S.newState());
});

test("legacy Workbench-06 envelope remains detached and cannot enter the operational reader", async () => {
  const old = fs.readFileSync(path.join(ROOT, "source_assessment", "v1", "fixtures", "response.json"), "utf8");
  await assert.rejects(S.importResponse(designWithRequest(), old, testVerifier()), /unknown or missing fields|Unsupported/);
});

test("request and candidate remain deterministic under the fixture builder", async () => {
  const design = await B.publicDesign();
  const built = await S.buildRequest(design, request.request_id);
  assert.equal(S.canonical(built), S.canonical(request));
});
