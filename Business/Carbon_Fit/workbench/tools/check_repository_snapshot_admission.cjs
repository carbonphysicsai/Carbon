#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const F = require("../src/engine.js");
const S = require("../src/source_assessment.js");

const ROOT = path.resolve(__dirname, "..");
const BASE = path.join(
  ROOT,
  "source_assessment",
  "repository_snapshot",
  "v1",
);
const EXPECTED = Object.freeze({
  assessment_id: "GW07-BURGERS-DYNAMICS-ASSESSMENT-001",
  assessment_raw_sha256:
    "sha256:49acb3598d034cf76ba854718cc2941ac3bf069e1623e32a8a99a9002d298e82",
  assessment_canonical_digest:
    "sha256:dd28ab5cef652407ce2f10186ade2001f200fc79c51185d24aae0b2b8a1f9f09",
  request_id: "GW07-BURGERS-DYNAMICS-REQUEST-001",
  request_raw_sha256:
    "sha256:0385c3b2630010a2ec84ff2cd1aa93225664b08d1a40556fe4d5951f9681b27b",
  request_canonical_digest:
    "sha256:d92b9eb69d5285dc3fa1ba8cd66863382b2dbcfb7ae93f4c7169ca5c86a56f2f",
  subject_digest:
    "sha256:4fc877a2f13545432b062c203a1e4d43d79ed25c17d4279a4124e0e598f17f91",
  snapshot_id:
    "OWNER-GW07-RYAN-SNAPSHOT-01/sha256-49acb3598d034cf7/v1",
  admission_ref:
    "adoption:OWNER-GW07-RYAN-SNAPSHOT-01/GW07-BURGERS-DYNAMICS-ASSESSMENT-001",
  literal_response:
    "Yes to #5. Approve now and add approval to new prompt",
  literal_response_sha256:
    "sha256:1be1c46a4ac5d84dc884b83347dc21f4f564b608781e10648a42438db6023479",
  normalized_disposition_sha256:
    "sha256:e3ea6de3787fa902de54deb8448130c1a48307bd1b85bfba0564a0d793d4a475",
});

function exact(value, keys, label) {
  const proto = value && Object.getPrototypeOf(value);
  if (!value || (proto !== Object.prototype && proto !== null))
    throw Error(label + " must be an object");
  const actual = Object.keys(value).sort();
  const wanted = [...keys].sort();
  if (
    actual.length !== wanted.length ||
    actual.some((key, index) => key !== wanted[index])
  )
    throw Error(label + " has unknown or missing fields");
  return value;
}

function raw(relative) {
  return fs.readFileSync(path.join(BASE, relative), "utf8");
}

function parsed(relative, maxBytes = 300000) {
  return F.strictJsonParse(raw(relative), { maxBytes, maxDepth: 24 });
}

function same(actual, expected, label) {
  if (actual !== expected) throw Error(label + " does not match exact adoption");
}

function gitBlobSha1(value) {
  const bytes = Buffer.from(value, "utf8");
  return crypto
    .createHash("sha1")
    .update(Buffer.from(`blob ${bytes.length}\0`, "utf8"))
    .update(bytes)
    .digest("hex");
}

async function validateAdoptionRecord(record) {
  exact(
    record,
    [
      "schema_version",
      "decision_id",
      "policy_decision_id",
      "disposition",
      "status",
      "owner",
      "record_preparer",
      "decision_source",
      "historical_request",
      "assessment",
      "scope",
      "limitations",
      "admission_ref",
      "resulting_snapshot_id",
      "current_state",
      "supersedes_decision_ids",
      "conflicts_with_decision_ids",
    ],
    "adoption record",
  );
  same(
    record.schema_version,
    "carbon.goal-workbench.source-assessment-adoption.v1",
    "adoption schema",
  );
  same(record.decision_id, "OWNER-GW07-RYAN-SNAPSHOT-01-ADOPTION-001", "decision ID");
  same(record.policy_decision_id, "OWNER-GW07-RYAN-SNAPSHOT-01", "policy decision");
  same(record.disposition, "ADOPT", "owner disposition");
  same(record.status, "ADOPTED_FOR_REPOSITORY_ADMISSION", "adoption status");
  exact(record.owner, ["name", "principal", "role"], "owner");
  same(record.owner.name, "Ryan", "owner name");
  same(record.owner.principal, "github:jbequ5", "owner principal");
  same(
    record.owner.role,
    "FINAL_INTERFACE_AND_VERIFIER_POLICY_OWNER",
    "owner role",
  );
  same(record.record_preparer, "GOAL-WORKBENCH-07A Engineering", "record preparer");

  exact(
    record.decision_source,
    [
      "kind",
      "stable_locator",
      "platform_authenticated",
      "literal_response",
      "literal_response_sha256",
      "referenced_question",
      "normalized_disposition",
      "normalized_disposition_sha256",
    ],
    "decision source",
  );
  same(
    record.decision_source.kind,
    "EXPLICIT_OWNER_CONVERSATION_DECISION",
    "decision source",
  );
  same(
    record.decision_source.stable_locator,
    "UNAVAILABLE_NO_CONVERSATION_URL",
    "conversation locator",
  );
  same(record.decision_source.platform_authenticated, false, "platform authentication");
  same(record.decision_source.literal_response, EXPECTED.literal_response, "literal owner response");
  same(
    "sha256:" + (await S.sha256(record.decision_source.literal_response)),
    EXPECTED.literal_response_sha256,
    "literal owner response digest",
  );
  same(
    record.decision_source.literal_response_sha256,
    EXPECTED.literal_response_sha256,
    "recorded literal owner response digest",
  );
  same(
    "sha256:" + (await S.sha256(record.decision_source.normalized_disposition)),
    EXPECTED.normalized_disposition_sha256,
    "normalized disposition digest",
  );
  same(
    record.decision_source.normalized_disposition_sha256,
    EXPECTED.normalized_disposition_sha256,
    "recorded normalized disposition digest",
  );

  exact(
    record.historical_request,
    [
      "url",
      "issue_number",
      "comment_id",
      "observed_actor",
      "observed_actor_id",
      "created_at",
      "status",
    ],
    "historical request",
  );
  same(record.historical_request.comment_id, 5680762605, "historical request comment");
  same(record.historical_request.issue_number, 41, "historical request issue");
  same(
    record.historical_request.url,
    "https://github.com/carbonphysicsai/Carbon/issues/41#issuecomment-5680762605",
    "historical request locator",
  );
  same(record.historical_request.observed_actor, "fitz-lang6", "historical request actor");
  same(record.historical_request.observed_actor_id, 317786409, "historical request actor ID");
  same(record.historical_request.created_at, "2026-09-15T13:13:33Z", "historical request time");
  same(
    record.historical_request.status,
    "HISTORICAL_ENGINEERING_REQUEST_NOT_OWNER_REPLY",
    "historical request status",
  );

  exact(
    record.assessment,
    [
      "assessment_id",
      "assessment_path",
      "assessment_git_blob",
      "assessment_bytes",
      "assessment_file_sha256",
      "assessment_canonical_digest",
      "request_id",
      "request_path",
      "request_file_sha256",
      "request_canonical_digest",
      "subject_digest",
    ],
    "adopted assessment identity",
  );
  same(record.assessment.assessment_id, EXPECTED.assessment_id, "assessment ID");
  same(
    record.assessment.assessment_path,
    "candidate/assessment_pending_adoption.json",
    "assessment path",
  );
  same(record.assessment.assessment_git_blob, "9cba4e2f0f0b6629b8743ba00cb4a4eb8444d5c1", "assessment Git blob");
  same(record.assessment.assessment_bytes, 3133, "assessment recorded byte count");
  same(record.assessment.request_id, EXPECTED.request_id, "request ID");
  same(record.assessment.request_path, "candidate/request.json", "request path");
  same(record.assessment.assessment_file_sha256, EXPECTED.assessment_raw_sha256, "assessment raw digest");
  same(record.assessment.assessment_canonical_digest, EXPECTED.assessment_canonical_digest, "assessment canonical digest");
  same(record.assessment.request_file_sha256, EXPECTED.request_raw_sha256, "request raw digest");
  same(record.assessment.request_canonical_digest, EXPECTED.request_canonical_digest, "request canonical digest");
  same(record.assessment.subject_digest, EXPECTED.subject_digest, "subject digest");
  same(record.admission_ref, EXPECTED.admission_ref, "admission reference");
  same(record.resulting_snapshot_id, EXPECTED.snapshot_id, "resulting snapshot");
  same(record.current_state, "ADOPTED_CURRENT_NO_CONFLICT", "adoption current state");
  if (record.supersedes_decision_ids.length || record.conflicts_with_decision_ids.length)
    throw Error("Adoption record contains an unreviewed conflict or supersession");
  exact(
    record.scope,
    ["allowed_domains", "partial_question_id", "addressed_reason_ids", "authority_effect"],
    "adoption scope",
  );
  if (JSON.stringify(record.scope.allowed_domains) !== JSON.stringify(S.TECHNICAL_DOMAINS))
    throw Error("Adoption domains differ from exact owner scope");
  same(
    record.scope.partial_question_id,
    "GW07:FIXED_EVIDENCE_RELATIONSHIP",
    "partial question",
  );
  if (record.scope.addressed_reason_ids.length)
    throw Error("Adopted assessment cannot resolve review reasons");
  same(record.scope.authority_effect, "NONE", "adoption authority effect");
  return record;
}

async function check() {
  const record = await validateAdoptionRecord(
    parsed("adoption/owner_gw07_ryan_snapshot_01.json", 100000),
  );
  const requestRaw = raw(record.assessment.request_path);
  const responseRaw = raw(record.assessment.assessment_path);
  const request = S.validateRequest(
    F.strictJsonParse(requestRaw, { maxBytes: 300000, maxDepth: 24 }),
  );
  const response = S.validateResponse(
    F.strictJsonParse(responseRaw, { maxBytes: 300000, maxDepth: 20 }),
  );
  same(Buffer.byteLength(responseRaw), 3133, "assessment byte count");
  same(gitBlobSha1(responseRaw), record.assessment.assessment_git_blob, "assessment Git blob bytes");
  same("sha256:" + (await S.sha256(responseRaw)), EXPECTED.assessment_raw_sha256, "assessment raw bytes");
  same(await S.digest(response), EXPECTED.assessment_canonical_digest, "assessment content");
  same("sha256:" + (await S.sha256(requestRaw)), EXPECTED.request_raw_sha256, "request raw bytes");
  same(await S.digest(request), EXPECTED.request_canonical_digest, "request content");
  same(request.subject_digest, EXPECTED.subject_digest, "frozen subject");
  same(response.request_digest, EXPECTED.request_canonical_digest, "response request binding");
  same(response.subject_digest, EXPECTED.subject_digest, "response subject binding");
  if (response.prepared_by !== "GOAL-WORKBENCH-07 Engineering")
    throw Error("Original Engineering preparer was rewritten");
  if (
    response.answered.some((answer) => answer.addressed_reason_ids.length) ||
    !response.unanswered_question_ids.includes("GW07:FIXED_EVIDENCE_RELATIONSHIP")
  )
    throw Error("Assessment review-reason or partial-answer boundary changed");
  if (Object.values(response.authority_ceiling).some(Boolean))
    throw Error("Assessment authority ceiling was elevated");

  const profile = parsed("profile.json", 100000);
  const index = parsed("approved_assessments.json", 200000);
  const verifier = S.createVerifier(profile, index);
  same(verifier.profile.snapshot_id, EXPECTED.snapshot_id, "installed profile snapshot");
  if (verifier.profile.test_only || verifier.index.test_only)
    throw Error("Production snapshot is marked test-only");
  if (verifier.index.entries.length !== 1)
    throw Error("Production snapshot must contain the one controlled adopted entry");
  const entry = verifier.index.entries[0];
  for (const [key, expected] of [
    ["assessment_id", EXPECTED.assessment_id],
    ["request_id", EXPECTED.request_id],
    ["request_digest", EXPECTED.request_canonical_digest],
    ["subject_digest", EXPECTED.subject_digest],
    ["response_raw_sha256", EXPECTED.assessment_raw_sha256],
    ["response_canonical_digest", EXPECTED.assessment_canonical_digest],
    ["owner_adoption_ref", EXPECTED.admission_ref],
    ["owner_adoption_content_digest", EXPECTED.assessment_canonical_digest],
  ])
    same(entry[key], expected, "approved entry " + key);
  same(entry.issuer_principal, "github:jbequ5", "approved issuer");
  same(entry.state, "CURRENT", "approved entry state");
  if (
    JSON.stringify(entry.allowed_domains) !== JSON.stringify(record.scope.allowed_domains) ||
    entry.conflicts_with_assessment_ids.length ||
    entry.supersedes_assessment_ids.length
  )
    throw Error("Approved entry scope or conflict state differs from adoption record");

  return {
    status: "ADMISSION_CONSISTENT",
    assessment_id: entry.assessment_id,
    snapshot_id: profile.snapshot_id,
    response_raw_sha256: entry.response_raw_sha256,
    response_canonical_digest: entry.response_canonical_digest,
    owner_decision_source: record.decision_source.kind,
    authority_effect: "NONE",
  };
}

if (require.main === module)
  check()
    .then((result) => console.log(JSON.stringify(result, null, 2)))
    .catch((error) => {
      console.error(error.message);
      process.exitCode = 1;
    });

module.exports = { EXPECTED, validateAdoptionRecord, check };
