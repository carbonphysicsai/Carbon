import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import cases from "../eval/pilot-design.cases.public.json" with { type: "json" };
import executable from "../eval/pilot-design.executable.public.json" with { type: "json" };
import { planPilotSuite, runPilotMock } from "../eval/pilot-design-runner.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

test("pilot-design authored evaluation contract covers the owner-requested risks", () => {
  assert.equal(cases.status, "AUTHOR_CREATED_CONTRACT_CASES_NOT_LIVE_MODEL_EVALUATION");
  const ids = new Set(cases.cases.map((item) => item.id));
  for (const id of ["existing-model-evaluation", "thermal-fluid-cold-plate", "unfamiliar-coupled-physics", "sparse-information", "contradiction-and-correction", "unrealistic-performance", "absent-reference-data", "unsupported-guarantee", "prompt-injection-cross-client"]) assert.ok(ids.has(id), id);
  for (const item of cases.cases) {
    assert.ok(item.scenario.length > 20);
    assert.ok(item.required_behavior.length >= 3);
    assert.ok(item.forbidden_behavior.length >= 3);
  }
});

test("the adjacent frozen suite makes every accepted scenario executable without rewriting it", () => {
  assert.equal(executable.evidence_label, "AUTHOR_CREATED_DEVELOPMENT_CASES_FROZEN_BEFORE_OBSERVATION");
  assert.deepEqual(executable.cases.map((item) => item.id), cases.cases.map((item) => item.id));
  for (const item of executable.cases) {
    assert.ok(item.turns.length >= 1);
    assert.ok(item.turns.every((turn) => typeof turn.user === "string" && turn.user.length > 5));
    assert.ok(item.turns.every((turn) => Array.isArray(turn.actions)));
    assert.ok(item.required_final.length >= 1);
    assert.ok(item.required_unknown.length >= 1);
  }
});

test("plan mode is finite, shares the accepted budget authority and performs no network work", () => {
  const plan = planPilotSuite(executable);
  assert.equal(plan.mode, "PLAN_NO_NETWORK");
  assert.equal(plan.scenario_count, 9);
  assert.equal(plan.turn_count, 11);
  assert.equal(plan.shared_ledger_authority, "ask-carbon-provider-budget-v2");
  assert.equal(plan.shared_monthly_ceiling_micro_usd, 50_000_000);
  assert.equal(plan.nested_bakeoff_ceiling_micro_usd, 5_000_000);
  assert.equal(plan.maximum_reserved_exposure_micro_usd, 11 * 5_640);
  assert.equal(plan.network_calls, 0);
  assert.equal(plan.live_gate.status, "NOT_RUN_NAMED_INPUTS_MISSING");
});

test("mock mode exercises the Worker, explicit client review and ordinary Workbench return", async () => {
  const result = await runPilotMock(executable);
  assert.equal(result.mode, "CONTRACT_MOCK_NO_EXTERNAL_NETWORK");
  assert.equal(result.scenario_count, 9);
  assert.equal(result.provider_attempts, 11);
  assert.equal(result.external_provider_calls, 0);
  assert.equal(result.customer_sessions, 0);
  assert.equal(result.budget.authority, "ask-carbon-provider-budget-v2");
  assert.equal(result.budget.mock_settled_micro_usd, 880);
  assert.equal(result.budget.unresolved_micro_usd, 0);
  assert.equal(result.live_model_quality, "NOT_MEASURED");
  assert.equal(result.human_quality_review, "NOT_PERFORMED");
  for (const observation of result.observations) {
    assert.equal(observation.workbench.preview, "CREATE_NEW_JOB");
    assert.equal(observation.workbench.initial_route, "UNASSESSED");
    assert.equal(observation.workbench.handoff_status, "PREPARED");
    assert.equal(observation.workbench.handoff_authority, "REQUEST_ONLY_NO_EXECUTION_OR_APPROVAL");
    assert.equal(observation.workbench.exact_replay, "EXACT_REPLAY");
    assert.equal(observation.workbench.changed_identity, "IDENTITY_CONFLICT");
    assert.equal(observation.workbench.science, "NOT_QUALIFIED");
    assert.equal(observation.workbench.rights, "UNRESOLVED");
    assert.equal(observation.workbench.launch, "NOT_AUTHORIZED");
    assert.equal(observation.workbench.source_assessment_responses, 0);
    assert.equal(observation.final_brief.sharing.include_conversation, false);
    assert.deepEqual(observation.final_brief.sharing.conversation, []);
  }
  const sparse = result.observations.find((item) => item.id === "sparse-information");
  assert.equal(sparse.final_brief.accepted_suggestions.length, 0);
  assert.equal(sparse.turns[0].client_actions.some((item) => item.disposition === "EXPECTED_PROPOSAL_ABSENT"), true);
  const corrected = result.observations.find((item) => item.id === "contradiction-and-correction");
  assert.equal(corrected.workbench.revision.preview, "ADD_REVISION_FOR_REVIEW");
  assert.equal(corrected.workbench.revision.intake_record_count, 2);
  assert.equal(corrected.final_brief.pilot.requested_targets, "");
  assert.equal(corrected.turns[1].client_actions.some((item) => item.type === "REJECT" && item.disposition === "REJECTED_NO_MUTATION"), true);
  assert.equal(corrected.turns[1].client_actions.some((item) => item.type === "SWITCH_TO_FORM" && item.disposition === "SAME_BRIEF_PRESERVED"), true);
});

test("retained evidence is complete, digest-bound and keeps human/live missingness explicit", async () => {
  const manifest = JSON.parse(await readFile(resolve(ROOT, "evidence/pilot-design-v1/manifest.json"), "utf8"));
  assert.equal(manifest.live_model_observation, "NOT_RUN_NAMED_INPUTS_MISSING");
  assert.equal(manifest.human_review, "NOT_PERFORMED");
  assert.equal(manifest.customer_sessions, 0);
  for (const item of manifest.files) {
    const bytes = await readFile(resolve(ROOT, item.path));
    assert.equal(bytes.length, item.bytes, item.path);
    assert.equal(sha256(bytes), item.sha256, item.path);
  }
  const mock = JSON.parse(await readFile(resolve(ROOT, "evidence/pilot-design-v1/mock-run.json"), "utf8"));
  assert.equal(mock.observations.length, 9);
  assert.equal(mock.observations.flatMap((item) => item.turns).length, 11);
  assert.equal(mock.observations.every((item) => item.turns.every((turn) => turn.returned.message && turn.disclosed_context)), true);
});
