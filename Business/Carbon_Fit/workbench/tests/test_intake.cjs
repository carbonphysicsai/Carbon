"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const F = require("../src/engine.js");
const I = require("../src/intake.js");
const G = require("../src/workflow.js");
const ROOT = path.resolve(__dirname, "..");
const ATLAS = JSON.parse(fs.readFileSync(path.join(ROOT, "data/atlas.json")));
const IDS = ATLAS.opportunities.map((item) => item.id);
const reader = (raw) => F.readWorkspace(raw, IDS, ATLAS.source.sha256);
const component = () => ({ schema_version: F.WORKSPACE_VERSION, application_version: F.APP_VERSION, source_sha256: ATLAS.source.sha256, evidence_catalog: [], drafts: [], shortlist: [], migration_receipts: [] });
const fixtureRaw = (name) => fs.readFileSync(path.join(ROOT, "intake/fixtures", name), "utf8");
const inspect = (raw) => I.inspect(raw, F.strictJsonParse);
const reviewed = (brief) => ({
  schema_version: I.REVIEW_VERSION,
  brief,
  pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])) },
  field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((field) => `pilot.${field}`)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
  accepted_suggestions: [],
  unresolved_assumptions: ["Reference adequacy is unknown."],
  ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
  sharing: { include_conversation: false, conversation: [] },
  contact: { name: "", email: "", organization: "" },
  local_scope: I.REVIEW_SCOPE,
});

test("closed local draft preserves unknowns and deterministic summary", () => {
  const draft = I.newDraft("draft-a", "rev-001");
  draft.summary = I.summaryFor(draft);
  const validated = I.validateDraft(draft);
  assert.equal(validated.summary.unknown_fields.length, 14);
  assert.match(validated.summary.text, /Requested accuracy: unknown/);
  assert.match(validated.summary.next_clarification, /intended decision/);
});

test("authority-bearing or unknown fields reject", () => {
  const draft = I.newDraft("draft-a", "rev-001");
  draft.summary = I.summaryFor(draft);
  draft.qualified = true;
  assert.throws(() => I.validateDraft(draft), /unsupported or missing fields/);
});

test("point range and missing values never collapse to zero", () => {
  const draft = I.newDraft("draft-a", "rev-001");
  draft.quantities.prediction_latency = { state: "POINT", value: 2, minimum: null, maximum: null, unit: "seconds/query", note: "reported", origin: "USER_ENTERED_LOCAL" };
  draft.quantities.reference_query_time = { state: "RANGE", value: null, minimum: 10, maximum: 20, unit: "minutes/query", note: "reported", origin: "USER_ENTERED_LOCAL" };
  draft.summary = I.summaryFor(draft);
  assert.match(I.validateDraft(draft).summary.text, /Prediction latency: 2 seconds\/query/i);
  assert.match(draft.summary.text, /Reference-query time: 10–20 minutes\/query/);
  assert.match(draft.summary.text, /Preparation time: unknown/);
});

test("client-computed summary mismatch rejects", () => {
  const draft = I.newDraft("draft-a", "rev-001");
  draft.summary = I.summaryFor(draft);
  draft.summary.text = "qualified fit";
  assert.throws(() => I.validateDraft(draft), /does not match/);
});

test("reviewed pilot package preserves the canonical v1 brief and explicit unknowns", async () => {
  const brief = JSON.parse(fixtureRaw("existing_method_v1.json"));
  const value = reviewed(brief);
  value.pilot.bounded_first_pilot = "Compare the reported baseline across an agreed public operating range.";
  value.field_provenance.find((item) => item.field === "pilot.bounded_first_pilot").origin = "CLIENT_TYPED";
  const inspection = await inspect(JSON.stringify(value));
  assert.equal(inspection.transport_kind, "REVIEWED_PACKAGE");
  assert.equal(inspection.draft.draft_id, brief.draft_id);
  assert.equal(inspection.review_package.pilot.label, "Draft pilot for Carbon review");
  assert.deepEqual(inspection.review_package.unresolved_assumptions, ["Reference adequacy is unknown."]);
});

test("reviewed package rejects authority injection and conversation sharing without opt-in", () => {
  const brief = JSON.parse(fixtureRaw("existing_method_v1.json"));
  const authority = reviewed(brief);
  authority.approved = true;
  assert.throws(() => I.validateReviewedPackage(authority), /unsupported or missing fields/);
  const history = reviewed(brief);
  history.sharing.conversation.push({ turn_id: "turn-001", role: "CLIENT", text: "private draft" });
  assert.throws(() => I.validateReviewedPackage(history), /explicit inclusion/);
});

test("reviewed package requires complete provenance and exact accepted-suggestion linkage", () => {
  const brief = JSON.parse(fixtureRaw("existing_method_v1.json"));
  const incomplete = reviewed(brief);
  incomplete.field_provenance.pop();
  assert.throws(() => I.validateReviewedPackage(incomplete), /cover every reviewable field/);

  const mismatch = reviewed(brief);
  mismatch.pilot.evaluation_questions = "Compare hotspot location.";
  mismatch.accepted_suggestions.push({ suggestion_id: "suggestion-001", field: "pilot.evaluation_questions", proposed_value: mismatch.pilot.evaluation_questions, rationale: "Proposed evaluation focus.", accepted_at: "2026-09-16T12:01:00.000Z" });
  assert.throws(() => I.validateReviewedPackage(mismatch), /does not match field provenance/);

  const stale = reviewed(brief);
  const provenance = stale.field_provenance.find((item) => item.field === "pilot.evaluation_questions");
  provenance.origin = "AI_SUGGESTED_CLIENT_ACCEPTED";
  provenance.suggestion_id = "suggestion-001";
  stale.pilot.evaluation_questions = "Current accepted wording.";
  stale.accepted_suggestions.push({ suggestion_id: "suggestion-001", field: "pilot.evaluation_questions", proposed_value: "Different wording.", rationale: "Proposed evaluation focus.", accepted_at: "2026-09-16T12:01:00.000Z" });
  assert.throws(() => I.validateReviewedPackage(stale), /does not match the current field value/);
});

test("accepted AI suggestion is separately attributed and remains unqualified client input", async () => {
  const brief = JSON.parse(fixtureRaw("fresh_burgers_v1.json"));
  const value = reviewed(brief);
  value.ai_guidance = { enabled: true, provider: "OPENAI_API", guidance_version: I.GUIDANCE_VERSION, notice_version: "carbon.ask-guidance.notice.v1-2026-09-16", consented_at: "2026-09-16T12:00:00.000Z", cleared_locally: false };
  value.pilot.evaluation_questions = "Compare hotspot location and design ranking.";
  const provenance = value.field_provenance.find((item) => item.field === "pilot.evaluation_questions");
  provenance.origin = "AI_SUGGESTED_CLIENT_ACCEPTED";
  provenance.suggestion_id = "suggestion-001";
  value.accepted_suggestions.push({ suggestion_id: "suggestion-001", field: "pilot.evaluation_questions", proposed_value: value.pilot.evaluation_questions, rationale: "This makes the proposed comparison inspectable.", accepted_at: "2026-09-16T12:01:00.000Z" });
  const inspection = await inspect(JSON.stringify(value));
  const workspace = G.newWorkspace(component());
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const design = workspace.jobs[0].designs[0];
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.decision.security_rights, "UNRESOLVED");
  assert.equal(design.route_plan.route, "UNASSESSED");
  assert.equal(workspace.jobs[0].intake_records[0].raw_json.includes("AI_SUGGESTED_CLIENT_ACCEPTED"), true);
});

test("new intake previews before creating an unassessed source-linked job", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("existing_method_v1.json"));
  const preview = G.previewIntakeImport(workspace, inspection);
  assert.equal(preview.action, "CREATE_NEW_JOB");
  assert.equal(workspace.jobs.length, 0);
  const result = G.commitIntakeImport(workspace, inspection, preview);
  assert.equal(result.changed, true);
  const job = workspace.jobs[0], design = job.designs[0];
  assert.equal(job.created_from, "ASSISTED_INTAKE");
  assert.equal(design.route_plan.route, "UNASSESSED");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.decision.security_rights, "UNRESOLVED");
  assert.match(design.requirements[0].source_reference, /^intake:sha256:/);
  assert.equal(job.intake_records.length, 1);
});

test("exact replay deduplicates job requirements and lineage", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("existing_method_v1.json"));
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const counts = [workspace.jobs.length, workspace.jobs[0].designs[0].requirements.length, workspace.jobs[0].intake_records.length];
  const preview = G.previewIntakeImport(workspace, inspection);
  assert.equal(preview.action, "EXACT_REPLAY");
  assert.equal(G.commitIntakeImport(workspace, inspection, preview).changed, false);
  assert.deepEqual([workspace.jobs.length, workspace.jobs[0].designs[0].requirements.length, workspace.jobs[0].intake_records.length], counts);
});

test("same claimed identity with changed bytes conflicts atomically", async () => {
  const workspace = G.newWorkspace(component());
  const raw = fixtureRaw("existing_method_v1.json"), inspection = await inspect(raw);
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const changed = JSON.parse(raw);
  changed.answers.requested_result.value += " changed";
  changed.summary = I.summaryFor(changed);
  const changedInspection = await inspect(JSON.stringify(changed));
  const before = JSON.stringify(workspace), preview = G.previewIntakeImport(workspace, changedInspection);
  assert.equal(preview.action, "IDENTITY_CONFLICT");
  assert.throws(() => G.commitIntakeImport(workspace, changedInspection, preview), /different bytes/);
  assert.equal(JSON.stringify(workspace), before);
});

test("valid successor attaches for review without overwriting design", async () => {
  const workspace = G.newWorkspace(component());
  const first = await inspect(fixtureRaw("unsupported_physics_v1.json"));
  G.commitIntakeImport(workspace, first, G.previewIntakeImport(workspace, first));
  const designBefore = JSON.stringify(workspace.jobs[0].designs[0]);
  const second = await inspect(fixtureRaw("unsupported_physics_revision_v2.json"));
  const preview = G.previewIntakeImport(workspace, second);
  assert.equal(preview.action, "ADD_REVISION_FOR_REVIEW");
  G.commitIntakeImport(workspace, second, preview);
  assert.equal(workspace.jobs[0].intake_records.length, 2);
  assert.equal(JSON.stringify(workspace.jobs[0].designs[0]), designBefore);
});

test("missing or wrong predecessor requires explicit reconciliation", async () => {
  const workspace = G.newWorkspace(component());
  const successor = await inspect(fixtureRaw("unsupported_physics_revision_v2.json"));
  assert.equal(G.previewIntakeImport(workspace, successor).action, "RECONCILIATION_REQUIRED");
  const before = JSON.stringify(workspace);
  assert.throws(() => G.commitIntakeImport(workspace, successor, G.previewIntakeImport(workspace, successor)), /predecessor/);
  assert.equal(JSON.stringify(workspace), before);
});

test("fresh Burgers-like inquiry cannot inherit admitted 07A assessment", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("fresh_burgers_v1.json"));
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const design = workspace.jobs[0].designs[0];
  assert.equal(design.source_assessments.requests.length, 0);
  assert.equal(design.source_assessments.receipts.length, 0);
  assert.equal(design.evidence_bindings.length, 0);
  assert.equal(design.route_plan.route, "UNASSESSED");
});

test("save reload preserves lineage and deduplication", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("existing_method_v1.json"));
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const saved = G.readWorkspace(JSON.stringify(workspace), reader, "VERIFIED_WEB_CRYPTO");
  await G.revalidateIntakeRecords(saved);
  assert.equal(saved.jobs[0].intake_records[0].canonical_digest, inspection.canonical_digest);
  assert.equal(G.previewIntakeImport(saved, inspection).action, "EXACT_REPLAY");
});

test("workspace-supplied intake digests are caches and fail exact revalidation", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("existing_method_v1.json"));
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  workspace.jobs[0].intake_records[0].raw_sha256 = "sha256:" + "0".repeat(64);
  const parsed = G.readWorkspace(JSON.stringify(workspace), reader, "VERIFIED_WEB_CRYPTO");
  const before = JSON.stringify(parsed);
  await assert.rejects(() => G.revalidateIntakeRecords(parsed), /failed revalidation/);
  assert.equal(JSON.stringify(parsed), before);
});

test("successor cannot cross-link a different draft identity", async () => {
  const draft = JSON.parse(fixtureRaw("unsupported_physics_revision_v2.json"));
  draft.predecessor.draft_id = "different-inquiry";
  await assert.rejects(() => inspect(JSON.stringify(draft)), /retain its draft identity/);
});

test("malformed duplicate and cross-format inputs reject before mutation", async () => {
  const workspace = G.newWorkspace(component()), before = JSON.stringify(workspace);
  await assert.rejects(() => inspect('{"schema_version":"carbon.client-intake.draft.v1","schema_version":"forged"}'), /Duplicate|unsupported/i);
  await assert.rejects(() => inspect(JSON.stringify({ schema_version: "carbon.source-assessment.response.v1" })), /unsupported|missing/i);
  assert.equal(JSON.stringify(workspace), before);
});

test("malicious text remains inert source content", async () => {
  const raw = fixtureRaw("existing_method_v1.json");
  const value = JSON.parse(raw);
  value.answers.intended_decision.value = '<img src=x onerror="globalThis.pwned=true">';
  value.summary = I.summaryFor(value);
  const inspection = await inspect(JSON.stringify(value));
  assert.match(inspection.draft.summary.text, /onerror/);
  assert.equal(globalThis.pwned, undefined);
});

test("existing-capability handoff reuses intake decision without execution authority", async () => {
  const workspace = G.newWorkspace(component());
  const inspection = await inspect(fixtureRaw("existing_method_v1.json"));
  G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
  const job = workspace.jobs[0], design = job.designs[0];
  G.selectRoute(design, "USE_EXISTING_CAPABILITY", { rationale: "Compare the current method before authoring.", source_or_capability_ref: "reported-current-method", route_basis: "Client assertion only", unresolved_conditions: ["output compatibility"], next_decision: "Clarify baseline applicability", selected_by_assertion: "Operator", status_provenance: "LOCAL_MANUAL_ASSERTION" });
  const handoff = G.handoff(design, { request_id: "handoff-intake-1", recipient: "S1", lead: "S1", question: job.assignment.intended_decision, required_output: "Return one bounded applicability finding", route: "MANUAL", input_refs: [job.intake_records[0].canonical_digest], stop_condition: "Stop after one finding", restart_event: "Finding returned" });
  assert.equal(handoff.status, "PREPARED");
  assert.equal(design.authoring.request_id, "");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
});
