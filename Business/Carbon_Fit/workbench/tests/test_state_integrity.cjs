"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const F = require("../src/engine.js");
const R = require("../src/routing.js");
const E = require("../src/c05_evidence.js");
const G = require("../src/workflow.js");
const index = JSON.parse(
  fs.readFileSync(path.join(ROOT, "data/c05_fixture_index_v2.json")),
);
const fixture = fs.readFileSync(
  path.join(ROOT, "data/c05_public_development_evidence_v1.json"),
  "utf8",
);
const atlas = JSON.parse(fs.readFileSync(path.join(ROOT, "data/atlas.json")));
const ids = atlas.opportunities.map((item) => item.id);
const clone = (value) => JSON.parse(JSON.stringify(value));
const sha = async (raw) =>
  crypto.createHash("sha256").update(raw).digest("hex");
E.installFixtureIndex(index);

function component() {
  return {
    schema_version: F.WORKSPACE_VERSION,
    application_version: F.APP_VERSION,
    source_sha256: atlas.source.sha256,
    evidence_catalog: [],
    drafts: [],
    shortlist: [],
    migration_receipts: [],
  };
}
function reader(raw) {
  return F.readWorkspace(raw, ids, atlas.source.sha256);
}
function context() {
  const w = G.newWorkspace(component()),
    j = G.newJob("job-001", "State integrity journey"),
    d = j.designs[0];
  w.jobs.push(j);
  Object.assign(d.scope, {
    physics_family: "periodic_viscous_burgers_1d_v1",
    requested_goal: "Dynamics",
    intended_use: "Bounded public DEVELOPMENT comparison",
    inputs: "initial field, viscosity and times",
    outputs: "complete field evolution",
    units: "source nondimensional units",
    geometry: "one-dimensional periodic domain",
    conditions: "periodic and unforced",
    regime: "source public cell",
    exclusions: "no protected use",
    query_workload: "fixed public request",
    turnaround: "unknown",
    failure_consequences: "development-only finding",
    data_access: "public fixture",
    rights_scope: "SYNTHETIC_INTERNAL",
  });
  d.requirements = [
    G.requirement(
      "REQ-DYNAMICS",
      "Predict complete field evolution.",
      "public fixture",
      "Inform bounded design",
    ),
  ];
  const t = G.trace("TRACE-DYNAMICS", "REQ-DYNAMICS");
  Object.assign(t, {
    measurement_definition: "source C-05 measurement",
    authoring_binding: "carbon.goal-authoring-proposal/1",
    role: "MANDATORY",
    floor: "source-owned DEVELOPMENT normalization only",
  });
  d.traces = [t];
  const c = G.caseFamily("BURGERS-12-CELL", "EVAL");
  Object.assign(c, {
    requirement_ids: ["REQ-DYNAMICS"],
    generator_ref: "goal_burgers_12cell_v1",
    support_status: "SOURCE_SUPPORTED",
  });
  d.cases = [c];
  j.accountable_owner = "Synthetic owner";
  j.lead = "S1";
  G.selectRoute(d, "ADAPT_SUPPORTED_CHALLENGE", {
    rationale: "Exact supported public adaptation.",
    source_or_capability_ref: "periodic_viscous_burgers_1d_v1 / Dynamics",
    route_basis: "Exact source template with bounded delta review.",
    unresolved_conditions: [],
    next_decision: "Scientific owner interpretation.",
    selected_by_assertion: "Local test",
    status_provenance: "LOCAL_MANUAL_ASSERTION",
  });
  return { w, j, d };
}
function binding(d, overrides = {}) {
  return {
    evidence_binding_id: "evidence-1",
    evidence_kind: "FIXED_CASE_RESULT",
    source_ref: "public:result",
    source_digest_or_identity: "sha256:" + "a".repeat(64),
    design_id: d.design_id,
    design_revision: d.revision,
    originating_design_id: d.design_id,
    originating_design_revision: d.revision,
    originating_binding_id: "evidence-1",
    trace_ids: ["TRACE-DYNAMICS"],
    case_family_ids: ["BURGERS-12-CELL"],
    dependency_domains: [...R.C05_DOMAINS],
    scope_relationship: "UNASSESSED",
    scientific_applicability: "UNASSESSED",
    scientific_review_reasons: [],
    use_or_rights_status: "UNRESOLVED",
    rights_review_reasons: [],
    assessment_basis: "Manual fixed-case claim.",
    rationale: "Historical DEVELOPMENT evidence only.",
    invalidated_by: [],
    source_claimed_provenance: "LOCAL_MANUAL_ASSERTION",
    origin_verification: "UNVERIFIED_CLAIM",
    status_provenance: "LOCAL_MANUAL_ASSERTION",
    ...overrides,
  };
}
async function withC05() {
  const x = context(),
    request = G.diagnosticRequest(x.d, "diagnostic-job-001-design-1-r1");
  const imported = await E.importBundle(x.d, request, fixture, sha);
  return { ...x, request, record: imported.record };
}
function response(d, h, kind = "RESULT", status = "RETURNED") {
  return {
    schema_version: G.RESPONSE_VERSION,
    response_id: "response-" + h.request_id,
    request_id: h.request_id,
    base_revision: d.revision,
    job_id: d.job_id,
    design_id: d.design_id,
    design_revision: d.revision,
    kind,
    route: "MANUAL",
    source_owner: "Synthetic source owner",
    status,
    output_reference: "public:result",
    input_digest: "sha256:" + "b".repeat(64),
    authority_class: "UNVERIFIED_ASSERTION",
    verification_reference: "none",
    limitations: "Manual assertion only.",
    note: "Returned for owner interpretation.",
    content_sha256: "c".repeat(64),
  };
}

test("F1 material review survives a later editorial edit and export/import", () => {
  const { w, d } = context();
  G.addEvidenceBinding(d, binding(d));
  G.applyChange(d, "regime", "changed population");
  G.applyChange(d, "commercial_context", "copy edit");
  assert.equal(
    d.evidence_bindings[0].scientific_applicability,
    "REVIEW_REQUIRED",
  );
  assert.equal(d.evidence_bindings[0].scope_relationship, "CHANGED");
  assert.ok(
    d.evidence_bindings[0].scientific_review_reasons.some(
      (x) => x.field === "regime",
    ),
  );
  const reopened = G.readWorkspace(JSON.stringify(w), reader),
    restored = reopened.jobs[0].designs[0].evidence_bindings[0];
  assert.equal(restored.scientific_applicability, "REVIEW_REQUIRED");
  assert.ok(restored.invalidated_by.includes("regime"));
});

test("independent editorial and material edit order yields the same review obligations", () => {
  const first = context().d,
    second = context().d;
  G.addEvidenceBinding(first, binding(first));
  G.addEvidenceBinding(second, binding(second));
  G.applyChange(first, "regime", "changed population");
  G.applyChange(first, "commercial_context", "copy");
  G.applyChange(second, "commercial_context", "copy");
  G.applyChange(second, "regime", "changed population");
  const reasons = (d) =>
    d.evidence_bindings[0].scientific_review_reasons
      .map((x) => x.field + ":" + x.domain)
      .sort();
  assert.deepEqual(reasons(first), reasons(second));
});

test("F2 scientific and rights obligations survive child and grandchild revisions", () => {
  const { j, d } = context();
  G.addEvidenceBinding(d, binding(d));
  G.applyChange(d, "regime", "changed");
  G.applyChange(d, "rights_scope", "changed");
  const parent = clone(d);
  const child = G.reviseDesign(j, d.design_id, "job-001-design-1-r2"),
    grandchild = G.reviseDesign(j, child.design_id, "job-001-design-1-r3");
  for (const current of [child, grandchild]) {
    const b = current.evidence_bindings[0];
    assert.equal(b.scientific_applicability, "REVIEW_REQUIRED");
    assert.equal(b.use_or_rights_status, "REVIEW_REQUIRED");
    assert.ok(b.invalidated_by.includes("regime"));
    assert.equal(b.originating_design_id, d.design_id);
  }
  assert.deepEqual({ ...d, status: "DRAFT" }, parent);
});

test("F3 prohibition survives rights proposal editorial edit and save/reload", () => {
  const { w, d } = context();
  G.addEvidenceBinding(d, binding(d, { use_or_rights_status: "PROHIBITED" }));
  G.applyChange(d, "rights_scope", "proposed wider rights");
  G.applyChange(d, "commercial_context", "copy edit");
  const reopened = G.readWorkspace(JSON.stringify(w), reader),
    b = reopened.jobs[0].designs[0].evidence_bindings[0];
  assert.equal(b.use_or_rights_status, "PROHIBITED");
  assert.ok(b.rights_review_reasons.some((x) => x.field === "rights_scope"));
});

test("F4 exclusions workload requirements and unsupported fields never receive favorable omission", () => {
  for (const [field, value] of [
    ["exclusions", "changed exclusions"],
    ["query_workload", "changed workload"],
  ]) {
    const { d } = context();
    G.addEvidenceBinding(d, binding(d));
    G.applyChange(d, field, value);
    assert.ok(
      d.evidence_bindings[0].scientific_review_reasons.length +
        d.evidence_bindings[0].rights_review_reasons.length >
        0,
    );
  }
  const { d } = context();
  G.addEvidenceBinding(d, binding(d));
  d.requirements.push(
    G.requirement("REQ-2", "New requirement", "test", "changes claim"),
  );
  G.recordImpact(d, "requirements", "added");
  assert.equal(
    d.evidence_bindings[0].scientific_applicability,
    "REVIEW_REQUIRED",
  );
  assert.throws(
    () => G.recordImpact(d, "unmapped_semantic_field", "changed"),
    /Unsupported or unmapped/,
  );
});

test("native evidence cannot omit minimum dependencies or forge provenance", () => {
  const { d } = context();
  assert.throws(
    () => G.addEvidenceBinding(d, binding(d, { dependency_domains: [] })),
    /source-required dependency/,
  );
  assert.throws(
    () =>
      G.addEvidenceBinding(
        d,
        binding(d, {
          status_provenance: "NATIVE_IMPORTED_RESULT",
          source_claimed_provenance: "NATIVE_IMPORTED_RESULT",
        }),
      ),
    /exact C-05 reader/,
  );
});

test("F5 actual C-05 result plus returned handoff is evidence received, not active work", async () => {
  const { j, d } = await withC05();
  const h = G.handoff(d, {
    request_id: "handoff-1",
    recipient: "OWNER_DECISION",
    lead: j.lead,
    question: "Interpret exact result?",
    required_output: "Scoped disposition",
  });
  G.importResponse(d, response(d, h));
  const row = G.ownerSummary(j, d);
  assert.equal(row.workflow_state, "NEEDS_OWNER_DECISION");
  assert.equal(row.attention_bucket, "NEEDS_DECISION");
  assert.equal(row.evidence_received, "YES_SCOPED_UNRESOLVED");
  assert.notEqual(row.workflow_state, "ACTIVE_NATIVE_EVIDENCE");
});

test("current result and unrelated open record require explicit action reconciliation", async () => {
  const { j, d } = await withC05();
  const h = G.handoff(d, {
    request_id: "handoff-returned",
    recipient: "OWNER_DECISION",
    lead: j.lead,
    question: "Interpret?",
    required_output: "Disposition",
  });
  G.importResponse(d, response(d, h));
  G.linkExternalRecord(d, {
    record_id: "unrelated-request",
    source_ref: "issue:42",
    status: "EXPORTED_OWNER_REQUEST",
    provenance: "EXTERNAL_LINKED_RECORD",
    note: "Separate request",
  });
  d.coordination.current_action_ref = "";
  const row = G.ownerSummary(j, d);
  assert.equal(row.current_action, "RECONCILE_ACTION_STATE");
  assert.equal(row.open_request_or_handoff, "RECONCILIATION_REQUIRED");
});

test("explicit current action controls status instead of array order", () => {
  const { j, d } = context();
  G.linkExternalRecord(d, {
    record_id: "old-return",
    source_ref: "public:old",
    status: "RETURNED",
    provenance: "EXTERNAL_LINKED_RECORD",
    note: "Historical",
  });
  G.linkExternalRecord(d, {
    record_id: "current-wait",
    source_ref: "public:current",
    status: "ACKNOWLEDGED",
    provenance: "EXTERNAL_LINKED_RECORD",
    note: "Not execution",
  });
  d.coordination.current_action_ref = "current-wait";
  const row = G.ownerSummary(j, d);
  assert.equal(row.workflow_state, "WAITING_ON_DEPENDENCY");
  assert.equal(row.current_action_ref, "current-wait");
  assert.equal(row.open_request_or_handoff, "ACKNOWLEDGED");
});

test("F6 route outcome and generic evidence native-origin claims are rejected on import", () => {
  for (const mutate of [
    (d) => (d.route_plan.status_provenance = "NATIVE_IMPORTED_RESULT"),
    (d) =>
      (d.coordination.customer_outcome_provenance = "NATIVE_IMPORTED_RESULT"),
  ]) {
    const { w, d } = context();
    mutate(d);
    assert.throws(
      () => G.readWorkspace(JSON.stringify(w), reader),
      /provenance|native/i,
    );
  }
  const { w, d } = context();
  d.evidence_bindings.push(
    binding(d, {
      status_provenance: "NATIVE_IMPORTED_RESULT",
      source_claimed_provenance: "NATIVE_IMPORTED_RESULT",
    }),
  );
  assert.throws(
    () => G.readWorkspace(JSON.stringify(w), reader),
    /verified C-05/,
  );
});

test("genuine exact C-05 survives workspace validation and reimport with source association", async () => {
  const { w, d } = await withC05();
  const reopened = G.readWorkspace(JSON.stringify(w), reader),
    restored = reopened.jobs[0].designs[0];
  assert.equal(
    restored.measurement_evidence[0].source.result_digest,
    d.measurement_evidence[0].source.result_digest,
  );
  assert.equal(
    restored.evidence_bindings[0].origin_verification,
    "PINNED_C05_FIXTURE_VERIFIED",
  );
});

test("saved C-05 observations cannot be edited and reimported as verified native evidence", async () => {
  const { w, d } = await withC05();
  d.measurement_evidence[0].measurements[0].candidate_value += 1;
  assert.throws(
    () => G.readWorkspace(JSON.stringify(w), reader),
    /saved fixture projection bytes/,
  );
});

test("F7 scoped applicability confirmation cannot project qualification", () => {
  const { d } = context();
  d.evidence_bindings.push(
    binding(d, {
      scientific_applicability: "SOURCE_OWNER_CONFIRMED",
      source_claimed_provenance: "NATIVE_IMPORTED_RESULT",
      status_provenance: "NATIVE_IMPORTED_RESULT",
    }),
  );
  const axis = R.evidenceAxis(d);
  assert.notEqual(axis.state, "QUALIFIED_SCOPED");
  assert.ok(axis.facts.includes("APPLICABILITY_CONFIRMED_NOT_QUALIFIED"));
  assert.equal(d.decision.scientific_qualification, "NOT_QUALIFIED");
});

test("v0.5 contradictory carry-forward migrates to explicit review with correction receipt", () => {
  const { w, d } = context();
  G.addEvidenceBinding(d, binding(d));
  G.applyChange(d, "regime", "changed");
  const old = clone(w);
  old.schema_version = "carbon.goal-workbench.workspace.v0.5";
  old.application_version = "Carbon Goal-to-Challenge Workbench v0.5";
  old.decision_id = "GOAL-WORKBENCH-05";
  old.base_application_merge = "e576fbdc711c9194dbcc7d90405480e90577407e";
  delete old.jobs[0].working_design_id;
  const od = old.jobs[0].designs[0];
  od.schema_version = "carbon.goal-workbench.design.v0.5";
  delete od.coordination.current_action_ref;
  const b = od.evidence_bindings[0];
  for (const key of [
    "originating_design_id",
    "originating_design_revision",
    "originating_binding_id",
    "scope_relationship",
    "scientific_review_reasons",
    "rights_review_reasons",
    "source_claimed_provenance",
    "origin_verification",
  ])
    delete b[key];
  b.scientific_applicability = "CARRIED_FORWARD_UNCHANGED_SCOPE";
  b.use_or_rights_status = "UNCHANGED_SOURCE_SCOPE";
  const migrated = G.readWorkspace(
      JSON.stringify(old),
      reader,
      "VERIFIED_WEB_CRYPTO",
    ),
    restored = migrated.jobs[0].designs[0].evidence_bindings[0];
  assert.equal(restored.scientific_applicability, "REVIEW_REQUIRED");
  assert.ok(restored.scientific_review_reasons.length);
  assert.match(
    migrated.migration_receipts.at(-1).semantic_changes.join(" "),
    /Reconciled v0.5/,
  );
});

test("working design is explicit and no newest alternative is silently approved", () => {
  const { w, j } = context(),
    second = G.newDesign(
      j.job_id,
      "job-001-design-2",
      1,
      null,
      "Alternative 2",
    );
  j.designs.push(second);
  j.working_design_id = null;
  const row = G.ownerConsole(w).rows[0];
  assert.equal(row.design_id, "UNSELECTED");
  assert.equal(row.current_action, "SELECT_WORKING_DESIGN");
});
