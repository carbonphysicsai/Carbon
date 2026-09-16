#!/usr/bin/env node
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const root = path.resolve(__dirname, "..");
const output = path.join(root, "intake", "fixtures");

function answer(value) {
  return value
    ? { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" }
    : { state: "UNKNOWN", value: "", origin: "USER_ENTERED_LOCAL" };
}
function point(value, unit, note = "") {
  return { state: "POINT", value, minimum: null, maximum: null, unit, note, origin: "USER_ENTERED_LOCAL" };
}
function range(minimum, maximum, unit, note = "") {
  return { state: "RANGE", value: null, minimum, maximum, unit, note, origin: "USER_ENTERED_LOCAL" };
}
function finish(draft) {
  draft.summary = I.summaryFor(draft);
  return I.validateDraft(draft);
}
function existing() {
  const d = I.newDraft("synthetic-existing-method", "rev-001");
  Object.assign(d.answers, {
    intended_decision: answer("Decide whether the existing numerical workflow can return useful answers sooner without changing the engineering decision."),
    requested_result: answer("Compare turnaround and output compatibility for the current method."),
    current_baseline: answer("A user-reported numerical method."),
    baseline_limitation: answer("Turnaround is reported as inconvenient; accuracy and financial impact are unknown."),
    changing_conditions: answer("Operating conditions vary between runs; the exact envelope is unknown."),
    consequential_error: answer("A misleading output could cause the wrong design comparison."),
    comparison_evidence: answer("The current method may provide comparison outputs; availability and permission are unverified."),
  });
  d.quantities.workload_frequency = range(1, 5, "queries/week", "Synthetic product-flow fixture");
  return finish(d);
}
function burgers() {
  const d = I.newDraft("synthetic-burgers-inquiry", "rev-001");
  Object.assign(d.answers, {
    intended_decision: answer("Explore whether a public periodic viscous Burgers-like task is close to a supported Carbon template."),
    requested_result: answer("Predict a time-dependent field and compare compression behavior."),
    current_baseline: answer("Synthetic finite-difference baseline."),
    baseline_limitation: answer("The example is for workflow testing and has no customer or qualification claim."),
    changing_conditions: answer("Viscosity and initial conditions vary in a synthetic periodic domain."),
    exclusions: answer("No protected cases, customer data, production tolerance, or launch."),
    consequential_error: answer("Missing a compression feature would invalidate the intended comparison."),
    comparison_evidence: answer("A public development example exists, but this fresh inquiry has its own identity."),
    access_limitations: answer("Synthetic public-development context only."),
  });
  d.quantities.prediction_latency = point(2, "seconds/query", "Requested scenario, not measured");
  d.quantities.desired_accuracy = point(5, "percent", "Requested intent, not accepted tolerance");
  return finish(d);
}
function unsupported() {
  const d = I.newDraft("synthetic-unsupported-physics", "rev-001");
  Object.assign(d.answers, {
    intended_decision: answer("Determine whether one bounded feasibility question can be stated for an unsupported coupled-physics need."),
    requested_result: answer("Compare a coupled thermal-structural observable."),
    current_baseline: answer("Unknown."),
    changing_conditions: answer("A synthetic operating condition changes between runs."),
    exclusions: answer("No full research program and no solver execution."),
    consequential_error: answer("An unsupported representation could lead to a false feasibility conclusion."),
    access_limitations: answer("Synthetic high-level inputs only; rights remain unresolved."),
  });
  return finish(d);
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const fixtures = [
    ["existing_method_v1.json", existing()],
    ["fresh_burgers_v1.json", burgers()],
    ["unsupported_physics_v1.json", unsupported()],
  ];
  const manifest = { schema_version: "carbon.client-intake.fixture-manifest.v1", fixtures: [] };
  for (const [name, draft] of fixtures) {
    const raw = JSON.stringify(draft, null, 2) + "\n";
    fs.writeFileSync(path.join(output, name), raw);
    const inspection = await I.inspect(raw, JSON.parse);
    manifest.fixtures.push({ name, draft_id: draft.draft_id, revision_id: draft.revision_id, raw_sha256: inspection.raw_sha256, canonical_digest: inspection.canonical_digest });
  }
  const base = manifest.fixtures.find((item) => item.name === "unsupported_physics_v1.json");
  const revised = unsupported();
  revised.revision_id = "rev-002";
  revised.predecessor = { draft_id: revised.draft_id, revision_id: base.revision_id, canonical_digest: base.canonical_digest };
  revised.answers.requested_result = answer("Compare a revised coupled thermal-structural output under a changed operating condition.");
  revised.summary = I.summaryFor(revised);
  const revisedRaw = JSON.stringify(revised, null, 2) + "\n";
  fs.writeFileSync(path.join(output, "unsupported_physics_revision_v2.json"), revisedRaw);
  const revisedInspection = await I.inspect(revisedRaw, JSON.parse);
  manifest.fixtures.push({ name: "unsupported_physics_revision_v2.json", draft_id: revised.draft_id, revision_id: revised.revision_id, raw_sha256: revisedInspection.raw_sha256, canonical_digest: revisedInspection.canonical_digest });
  fs.writeFileSync(path.join(output, "fixture_manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
}
main().catch((error) => { console.error(error); process.exit(1); });
