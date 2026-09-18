"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
require("../src/engine.js");
const G = require("../src/workflow.js");
const T = require("../src/team_review.js");
const S = require("../src/scientific_studies.js");

function job() {
  const value = G.newJob("team-job-001", "Synthetic thermal inquiry");
  value.assignment.client_words = "We want to predict cold-plate temperatures faster.";
  value.assignment.intended_decision = "Choose a cold-plate design without waiting for every full simulation.";
  value.assignment.credible_baseline = "Current finite-volume simulation; timing unknown.";
  value.designs[0].scope.conditions = "Load and flow ranges are not yet agreed.";
  value.designs[0].scope.outputs = "Temperature field, hotspots and design ranking.";
  return value;
}

test("new jobs enter a truthful unassigned intake queue", () => {
  const value = job();
  const row = T.queueProjection(value, value.designs[0]);
  assert.equal(row.queue_state, "NEW");
  assert.equal(row.assigned_reviewer, "");
  assert.match(row.missing_information.join(" "), /reference evidence/);
  assert.equal(value.designs[0].route_plan.route, "UNASSESSED");
});

test("correction preserves original statement and manual provenance", () => {
  const value = job(), original = value.assignment.client_words;
  G.addReviewCorrection(value.team_review, {
    correction_id: "correction-001",
    field: "assignment.client_words",
    original,
    corrected: "We want faster cold-plate temperature predictions.",
    reason: "Transcription punctuation only.",
    recorded_by: "synthetic-reviewer",
  });
  assert.equal(value.assignment.client_words, original);
  assert.equal(value.team_review.original_statement_corrections[0].original, original);
  assert.equal(value.team_review.provenance, "LOCAL_MANUAL_ASSERTION");
});

test("client and internal outputs derive from the same exact design", () => {
  const value = job(), design = value.designs[0];
  design.assessment.intended_engineering_decision = value.assignment.intended_decision;
  design.assessment.operating_envelope = "Proposed load and flow range; bounds unresolved.";
  design.assessment.smallest_useful_pilot = "Compare hotspots and rankings on an agreed synthetic subset.";
  design.assessment.measurement_requirements = "Hotspot error and ranking agreement; limits unresolved.";
  design.assessment.open_questions = ["Which reference runs can be used?"];
  const client = G.clientPilotBrief(value, design);
  const internal = G.internalExecutionBrief(value, design);
  assert.equal(client.design_id, internal.design_id);
  assert.equal(client.design_revision, internal.design_revision);
  assert.match(client.authority, /not feasibility/);
  assert.match(internal.authority, /runs no solver/);
  assert.equal(client.internal_notes, undefined);
  assert.equal(internal.assessment.smallest_useful_pilot, client.proposed_scope);
});

test("accepted core check is exact-scope, non-qualifying, and stale after a physical edit", async () => {
  const value = G.newJob("science-job-001", "Public Burgers definition");
  const design = value.designs[0];
  Object.assign(design.scope, {
    physics_family: S.TEMPLATE,
    requested_goal: "Dynamics",
    inputs: "Source Fourier coefficients, viscosity and requested times",
    outputs: "Full periodic field",
    units: "Source nondimensional units",
    geometry: "Periodic line",
    conditions: "Unforced periodic boundary",
    regime: "Public synthetic TRAIN source case",
    exclusions: "No private or protected cases",
    query_workload: "One local structural review",
    rights_scope: "SYNTHETIC_INTERNAL",
  });
  design.reference_plan.equation = "u_t + d_x(u^2/2) = nu*u_xx";
  design.reference_plan.method = "Registered public source method";
  const first = await G.recordPhysicalDefinitionCheck(design, S);
  const again = await G.recordPhysicalDefinitionCheck(design, S);
  assert.equal(first.availability, "RETURNED");
  assert.equal(first.result.status, "INPUTS_UNRESOLVED");
  assert.match(first.result.issues.join(" "), /Adopt the private service/);
  assert.equal(first.result.qualification, "NOT_QUALIFIED");
  assert.equal(first.result.authority_effect, "NONE");
  assert.equal(first.check_id, again.check_id);
  assert.equal(first.exact_design_binding, design.design_id + "@1");
  G.applyChange(design, "commercial_context", "Editorial note", "display only");
  assert.equal(design.assessment.scientific_task_dependencies[0].availability, "RETURNED");
  G.applyChange(design, "conditions", "Changed physical condition", "material");
  assert.equal(design.assessment.scientific_task_dependencies[0].availability, "STALE");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
});

test("saved structural observations revalidate and tampered projections reject", async () => {
  const value = job(), design = value.designs[0];
  await G.recordPhysicalDefinitionCheck(design, S);
  const workspace = G.newWorkspace({ schema_version: "carbon.fit.workspace.v0.2", application_version: "Carbon Fit Workbench v0.2", source_sha256: "a".repeat(64), evidence_catalog: [], drafts: [], shortlist: [], migration_receipts: [] });
  workspace.jobs.push(value);
  await G.revalidatePhysicalDefinitionChecks(workspace, S);
  design.assessment.scientific_task_dependencies[0].result.status = "STRUCTURALLY_CHECKED";
  await assert.rejects(
    G.revalidatePhysicalDefinitionChecks(workspace, S),
    /failed deterministic revalidation/,
  );
});

test("revision preserves assessment content but resets shared task observations", async () => {
  const value = job(), design = value.designs[0];
  design.assessment.reference_gaps = "No usable independent reference identified.";
  await G.recordPhysicalDefinitionCheck(design, S);
  const next = G.reviseDesign(value, design.design_id, "team-job-001-design-2");
  assert.equal(next.assessment.reference_gaps, design.assessment.reference_gaps);
  assert.equal(next.assessment.scientific_task_dependencies[0].availability, "AVAILABLE_NOT_REQUESTED");
  assert.equal(next.assessment.scientific_task_dependencies[0].result, null);
  assert.equal(next.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.status, "SEALED");
});

test("assessment cannot claim an unrelated scientific task binding or measured cost", () => {
  const value = job(), design = value.designs[0];
  design.assessment.scientific_task_dependencies[0].exact_design_binding = "other@1";
  assert.throws(() => T.validateAssessment(design.assessment, design), /stale or for another design/);
  design.assessment.scientific_task_dependencies[0].exact_design_binding = "";
  design.assessment.resource_scenarios.push({
    scenario_id: "scenario-001",
    description: "Synthetic bounded feasibility",
    assumptions: "No runtime estimate supplied",
    cost: "unknown",
    duration: "unknown",
    status: "MEASURED",
  });
  assert.throws(() => T.validateAssessment(design.assessment, design), /cannot claim measured/);
});

test("v0.9 workspace migration preserves review text without promoting placeholder task state", () => {
  const workspace = G.newWorkspace({ component: "synthetic" });
  const value = job();
  value.team_review.assigned_reviewer = "Synthetic reviewer";
  value.designs[0].assessment.reference_gaps = "Reference adequacy remains unknown.";
  const old = value.designs[0].assessment;
  old.schema_version = "carbon.goal-workbench.team-assessment.v1";
  old.scientific_task_dependencies = old.scientific_task_dependencies.map((item) => ({
    task_kind: item.task_kind,
    availability: "CORE_INTERFACE_PENDING",
    exact_design_binding: "",
    note: "Historical v0.9 placeholder.",
  }));
  value.designs[0].schema_version = "carbon.goal-workbench.design.v0.9";
  workspace.jobs.push(value);
  workspace.schema_version = "carbon.goal-workbench.workspace.v0.9";
  workspace.application_version = "Carbon Goal-to-Challenge Workbench v0.9";
  workspace.decision_id = "GOAL-WORKBENCH-09";
  workspace.base_application_merge = "4afb80566fc695a873d7154c203787991bb64267";
  const migrated = G.readWorkspace(JSON.stringify(workspace), JSON.parse, "VERIFIED_WEB_CRYPTO");
  const assessment = migrated.jobs[0].designs[0].assessment;
  assert.equal(migrated.schema_version, "carbon.goal-workbench.workspace.v0.10");
  assert.equal(migrated.jobs[0].team_review.assigned_reviewer, "Synthetic reviewer");
  assert.equal(assessment.reference_gaps, "Reference adequacy remains unknown.");
  assert.deepEqual(
    assessment.scientific_task_dependencies.map((item) => item.availability),
    ["AVAILABLE_NOT_REQUESTED", "CORE_INTERFACE_PENDING", "AVAILABLE_NOT_REQUESTED"],
  );
  assert.equal(assessment.scientific_task_dependencies[0].result, null);
});

test("private team notes never enter the client pilot brief", () => {
  const value = job(), design = value.designs[0];
  G.addAssessmentNote(value.team_review, {
    record_id: "note-001",
    text: "private-team-sentinel",
    recorded_by: "synthetic-reviewer",
  });
  const client = JSON.stringify(G.clientPilotBrief(value, design));
  const internal = JSON.stringify(G.engineeringProjection(value, design));
  assert.equal(client.includes("private-team-sentinel"), false);
  assert.equal(internal.includes("private-team-sentinel"), true);
});
