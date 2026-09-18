"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
require("../src/engine.js");
const G = require("../src/workflow.js");
const T = require("../src/team_review.js");

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
  assert.match(internal.authority, /No execution/);
  assert.equal(client.internal_notes, undefined);
  assert.equal(internal.assessment.smallest_useful_pilot, client.proposed_scope);
});

test("revision preserves assessment content but resets shared task execution claims", () => {
  const value = job(), design = value.designs[0];
  design.assessment.reference_gaps = "No usable independent reference identified.";
  design.assessment.scientific_task_dependencies[0] = {
    task_kind: "PHYSICAL_DEFINITION_CHECK",
    availability: "RETURNED",
    exact_design_binding: design.design_id + "@" + design.revision,
    note: "Synthetic returned fixture, not scientific evidence.",
  };
  const next = G.reviseDesign(value, design.design_id, "team-job-001-design-2");
  assert.equal(next.assessment.reference_gaps, design.assessment.reference_gaps);
  assert.equal(next.assessment.scientific_task_dependencies[0].availability, "CORE_INTERFACE_PENDING");
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
