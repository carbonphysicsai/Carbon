"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const WB = path.resolve(__dirname, "..");
const PACKAGE = path.join(WB, "source_assessment", "v1");
const F = require("../src/engine.js");
const B = require("../tools/build_source_assessment_fixtures.cjs");
const C = require("../tools/source_assessment_conformance.cjs");
const G = require("../src/workflow.js");

const load = (relative) => JSON.parse(fs.readFileSync(path.join(PACKAGE, relative), "utf8"));
const clone = (value) => JSON.parse(JSON.stringify(value));
const profile = load("fixtures/profile.json");
const request = load("fixtures/request.json");
const response = load("fixtures/response.json");
const snapshotFile = path.join(PACKAGE, "fixtures", "public_design_snapshot.json");
const snapshot = { value: load("fixtures/public_design_snapshot.json"), bytes: fs.readFileSync(snapshotFile) };
const redigest = (value) => { value.content_digest = B.digestValue(value.content); return value; };
const newOut = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gw06-test-")), "output");

test("all four normative schemas are valid JSON and closed at the root", () => {
  for (const name of ["request", "response", "profile", "receipt"]) {
    const schema = load(`schemas/${name}.schema.json`);
    assert.equal(schema.type, "object");
    assert.equal(schema.additionalProperties, false);
  }
});

test("positive example validates exact source bytes through the detached path", async () => {
  assert.equal(await C.validateObjects(profile, request, response, snapshot), true);
});

test("source-derived declaration remains technical and unqualified", () => {
  assert.equal(response.content.capability_declaration.active_goal, "Dynamics");
  assert.equal(response.content.applicability_assessment.status, "UNRESOLVED_TEST_AUTHORED_PREVIEW");
  assert.ok(Object.values(response.authority_ceiling).every((value) => value === false));
});

test("field provenance identifies test-authored and source-derived facts", () => {
  const entries = load("fixtures/field_provenance.json").entries;
  assert.ok(entries.some((entry) => entry.source_kind === "EXISTING_BRIDGE_DERIVED_FACT"));
  assert.ok(entries.some((entry) => entry.source_kind === "COPIED_SOURCE_FACT"));
  assert.ok(entries.some((entry) => entry.source_kind === "TEST_AUTHORED_EXPECTED_RESPONSE"));
  assert.equal(entries.some((entry) => entry.source_kind === "OWNER_SUPPLIED_ASSESSMENT"), false);
});

test("Front Resolution cannot be presented as the Dynamics declaration", () => {
  const changed = redigest(clone(response));
  changed.content.capability_declaration.active_goal = "Front Resolution";
  changed.content_digest = B.digestValue(changed.content);
  assert.throws(() => C.validateResponse(changed, request), /INTENT_MISMATCH/);
});

test("unsupported physics remains an explicit unsupported result with all reasons", () => {
  const changed = clone(response);
  changed.result_kind = "UNSUPPORTED_SCOPE";
  changed.content.capability_declaration.status = "UNSUPPORTED_REQUESTED_SCOPE";
  changed.content.capability_declaration.technical_scope = "Unsupported physics; no Burgers coercion.";
  changed.content.applicability_assessment.status = "UNSUPPORTED";
  changed.content.applicability_assessment.unsupported_question_ids = ["GW06:TECHNICAL_EXPRESSIBILITY"];
  changed.content.applicability_assessment.answered_question_ids = [];
  redigest(changed);
  const interpretation = C.interpretCandidate(request, changed);
  assert.equal(interpretation.status, "UNSUPPORTED_SCOPE");
  assert.deepEqual(interpretation.remaining_reason_ids, [...request.scope.unresolved_reason_ids].sort());
});

test("unsupported rights cannot resolve the rights reason", () => {
  const changed = clone(response);
  changed.result_kind = "NAMED_BLOCKER";
  changed.content.applicability_assessment.status = "BLOCKED";
  changed.content.applicability_assessment.unsupported_question_ids = ["GW06:RIGHTS"];
  redigest(changed);
  assert.ok(C.interpretCandidate(request, changed).remaining_reason_ids.includes("gw06:rights:use-unresolved"));
});

test("wrong job, design, request, or older revision rejects exact association", () => {
  for (const mutate of [
    (x) => { x.association.job_id = "other"; },
    (x) => { x.association.design_id = "other"; },
    (x) => { x.request_id = "other"; },
    (x) => { x.association.design_revision = 0; },
  ]) {
    const changed = clone(response); mutate(changed);
    assert.throws(() => C.interpretCandidate(request, changed), /RESPONSE_(REQUEST|ASSOCIATION)_MISMATCH/);
  }
});

test("same revision with different design content rejects snapshot identity", () => {
  const changed = clone(snapshot.value);
  changed.intended_use = "changed after sealing";
  assert.throws(() => C.validateSnapshot(request, { value: changed, bytes: Buffer.from(`${JSON.stringify(changed, null, 2)}\n`) }), /DESIGN_SNAPSHOT_DIGEST_MISMATCH/);
});

test("wrong case, query digest, source version, or artifact bytes rejects", async () => {
  for (const mutate of [
    (x) => { x.content.evidence_relationship.fixture_id = "OTHER-CASE"; },
    (x) => { x.content.evidence_relationship.request_digest = `sha256:${"0".repeat(64)}`; },
    (x) => { x.source_profile_version = "burgers-dynamics-public.v2"; },
  ]) {
    const changed = clone(response); mutate(changed); redigest(changed);
    assert.throws(() => C.validateResponse(changed, request));
  }
  const changedProfile = clone(profile);
  changedProfile.source_artifacts[0].sha256 = `sha256:${"0".repeat(64)}`;
  await assert.rejects(C.validateSources(changedProfile, request, response), /SOURCE_ARTIFACT_DIGEST_MISMATCH/);
});

test("inherited evidence cannot be relabeled as fresh execution", () => {
  const changed = clone(response);
  changed.content.evidence_relationship.execution_relationship = "FRESH_EXECUTION";
  redigest(changed);
  assert.throws(() => C.validateResponse(changed, request), /SOURCE_SCOPE_OR_EXECUTION_LAUNDERING/);
});

test("exact replay is deterministic and same identity with changed bytes conflicts", async () => {
  const out1 = newOut();
  const out2 = newOut();
  const args = (out) => ["node", "tool", "--profile", path.join(PACKAGE, "fixtures/profile.json"), "--request", path.join(PACKAGE, "fixtures/request.json"), "--response", path.join(PACKAGE, "fixtures/response.json"), "--output-dir", out];
  await C.run(args(out1));
  await C.run(args(out2));
  assert.equal(fs.readFileSync(path.join(out1, "validation_receipt.json"), "utf8"), fs.readFileSync(path.join(out2, "validation_receipt.json"), "utf8"));
  assert.equal(fs.readFileSync(path.join(out1, "interpretation_preview.md"), "utf8"), fs.readFileSync(path.join(out2, "interpretation_preview.md"), "utf8"));
  assert.deepEqual(C.reconcileResponses([response, clone(response)]), { disposition: "CONSISTENT", unique_responses: 1 });
  const conflict = clone(response); conflict.content.applicability_assessment.limitations.push("different bytes"); redigest(conflict);
  assert.throws(() => C.reconcileResponses([response, conflict]), /CONFLICTING_RESPONSE_IDENTITY/);
});

test("partial answer preserves unresolved questions and cumulative reasons", () => {
  const interpretation = C.interpretCandidate(request, response);
  assert.deepEqual(interpretation.remaining_reason_ids, [...request.scope.unresolved_reason_ids].sort());
  assert.equal(interpretation.qualification_effect, "NONE");
  assert.equal(interpretation.rights_effect, "NONE");
});

test("conflicting assessments require explicit exact-scope supersession", () => {
  const conflict = clone(response);
  conflict.response_id = "GW06-BURGERS-DYNAMICS-PUBLIC-RESPONSE-002";
  conflict.content.applicability_assessment.limitations.push("conflicting interpretation");
  redigest(conflict);
  assert.throws(() => C.reconcileResponses([response, conflict]), /RECONCILIATION_REQUIRED/);
});

test("forged provenance, trustedSource, and qualification fields reject", () => {
  for (const mutate of [
    (x) => { x.claimed_issuer.claim_basis = "SOURCE_OWNER_CONFIRMED"; },
    (x) => { x.trustedSource = true; },
    (x) => { x.authority_ceiling.scientifically_qualified = true; },
  ]) {
    const changed = clone(response); mutate(changed);
    assert.throws(() => C.validateResponse(changed, request), /FORGED_SOURCE_OWNER_OR_PROVENANCE|UNKNOWN_OR_MISSING_FIELD|AUTHORITY_ESCALATION/);
  }
});

test("correct hashes do not authenticate a live operator or source owner", () => {
  const receipt = C.receiptFor(profile, request, response, {
    profile: { bytes: fs.readFileSync(path.join(PACKAGE, "fixtures/profile.json")) },
    request: { bytes: fs.readFileSync(path.join(PACKAGE, "fixtures/request.json")) },
    response: { bytes: fs.readFileSync(path.join(PACKAGE, "fixtures/response.json")) },
    snapshot,
  });
  assert.equal(receipt.origin_verification.status, "FIXTURE_BYTES_MATCH_TEST_PRODUCER_NOT_SOURCE_OWNER");
  assert.ok(receipt.origin_verification.not_established.includes("source-owner acceptance"));
  assert.equal(receipt.authority_ceiling.origin_authenticated, false);
});

test("technical declaration cannot remove scientific or rights prohibition", () => {
  const interpretation = C.interpretCandidate(request, response);
  assert.ok(interpretation.remaining_reason_ids.includes("gw06:scientific:applicability-unresolved"));
  assert.ok(interpretation.remaining_reason_ids.includes("gw06:rights:use-unresolved"));
});

test("strict parser rejects duplicate keys, dangerous keys, unsafe numbers, and depth", () => {
  assert.throws(() => F.strictJsonParse('{"a":1,"a":2}'), /duplicate object member/);
  assert.throws(() => F.strictJsonParse('{"__proto__":{}}'), /forbidden object member/i);
  assert.throws(() => F.strictJsonParse('{"n":9007199254740992}'), /safe integer/i);
  let deep = "0"; for (let i = 0; i < 30; i += 1) deep = `{"x":${deep}}`;
  assert.throws(() => F.strictJsonParse(deep, { maxDepth: 12 }), /nesting limit/);
});

test("malicious display text is escaped in the preview", () => {
  const changed = clone(response);
  changed.content.applicability_assessment.next_decision = '<img src=x onerror="alert(1)">';
  redigest(changed);
  const receipt = { origin_verification: { status: "UNAUTHENTICATED" } };
  const preview = C.previewFor(request, changed, receipt);
  assert.equal(preview.includes("<img"), false);
  assert.ok(preview.includes("&lt;img"));
});

test("current v0.6 response import rejects the candidate format without mutation", () => {
  const job = G.newJob("job-001", "consumer rejection");
  const design = job.designs[0];
  const before = JSON.stringify(design);
  assert.throws(() => G.importResponse(design, response));
  assert.equal(JSON.stringify(design), before);
});

test("current standalone ships only the operational v2 consumer and preserves v1 as detached history", () => {
  const file = path.join(WB, "Carbon_Opportunity_Workbench.html");
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.includes(Buffer.from("carbon.goal-workbench.source-assessment-response.v2")), true);
  assert.equal(bytes.includes(Buffer.from("OWNER-GW07-RYAN-SNAPSHOT-01/empty-production-index/v1")), true);
  assert.equal(bytes.includes(Buffer.from("GW06-BURGERS-DYNAMICS-PUBLIC-RESPONSE-001")), false);
});

test("validation failure creates no output directory", async () => {
  const badDir = fs.mkdtempSync(path.join(os.tmpdir(), "gw06-bad-"));
  const badResponsePath = path.join(badDir, "bad.json");
  fs.writeFileSync(badResponsePath, '{"schema_version":"x","schema_version":"y"}', "utf8");
  const output = path.join(badDir, "output");
  await assert.rejects(C.run(["node", "tool", "--profile", path.join(PACKAGE, "fixtures/profile.json"), "--request", path.join(PACKAGE, "fixtures/request.json"), "--response", badResponsePath, "--output-dir", output]));
  assert.equal(fs.existsSync(output), false);
});

test("manifest accounts for exact bytes and excludes self-reference", () => {
  const manifest = load("manifest.json");
  assert.equal(manifest.files.some((item) => item.path === "manifest.json"), false);
  for (const item of manifest.files) {
    const bytes = fs.readFileSync(path.join(PACKAGE, item.path));
    assert.equal(item.bytes, bytes.length);
    assert.equal(item.sha256, `sha256:${crypto.createHash("sha256").update(bytes).digest("hex")}`);
  }
});

test("vector inventory covers the required conformance boundaries", () => {
  const ids = new Set(load("fixtures/vectors.json").cases.map((item) => item.vector_id));
  for (const id of ["front-resolution-intent-mismatch", "unsupported-physics", "unsupported-rights", "wrong-job-design-request", "same-revision-different-content", "inherited-as-fresh-execution", "exact-response-replay", "conflicting-assessments", "confirmation-as-qualification", "rights-prohibition-plus-technical-confirmation", "hostile-json-and-display-text"]) assert.ok(ids.has(id), id);
});
