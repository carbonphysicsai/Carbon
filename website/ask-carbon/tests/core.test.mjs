import test from "node:test";
import assert from "node:assert/strict";
import {
  PublicApiError,
  activationStatus,
  makeContinuation,
  selectCards,
  signContinuation,
  validatePilotProviderOutput,
  validateProviderOutput,
  validateRequestBody,
  verifyContinuation,
} from "../worker/core.mjs";
import { calculateUsageCostMicroUsd, estimateMaximumCostMicroUsd, getModelProfile, validateProviderUsage } from "../worker/models.mjs";
import { evaluateRelease } from "../public/release-contract.js";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const activeEnv = () => ({
  ASK_CARBON_ACTIVATION: "enabled",
  ASK_CARBON_RUNTIME_MODE: "staging",
  ASK_CARBON_APPROVED_ORIGINS: "https://staging.example",
  ASK_CARBON_APPROVED_MODEL_CONFIGS: "gpt-5.6-luna:low:v1,gpt-5.6-terra:low:v1",
  ASK_CARBON_MODEL_CONFIG_ID: "gpt-5.6-luna:low:v1",
  ASK_CARBON_OPENAI_API_KEY: "test-only",
  ASK_CARBON_CONTINUATION_SIGNING_SECRET: "test-only-signing-secret",
  ASK_CARBON_PRIVACY_MODE: "evaluation_public_synthetic_only",
  ASK_CARBON_EDGE_ACCESS_POLICY_ID: "test-private-access-policy",
  ASK_CARBON_EDGE_ABUSE_POLICY_ID: "test-edge-abuse-policy",
  ASK_CARBON_LEDGER_AUTHORITY_ID: "ask-carbon-provider-budget-v2",
  ASK_CARBON_ENVIRONMENT: "staging",
  ASK_CARBON_OPERATIONAL_SCOPE_ID: "staging",
  ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD: "50000000",
  ASK_CARBON_MONTHLY_LIMIT_MICRO_USD: "50000000",
  ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
  ASK_CARBON_MAX_CONCURRENCY: "4",
  ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
  ASK_CARBON_CLIENT_COUNTER_RETENTION_MS: "86400000",
  ASK_CARBON_MAX_INPUT_TOKENS: "24000",
  ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
  ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
  ASK_CARBON_PILOT_MAX_REQUESTS_PER_SESSION: "8",
  ASK_CARBON_USAGE_LEDGER: { idFromName() {}, get() {} },
});

test("one release contract gates staging, production, expiry, withdrawal and individual card freshness", () => {
  const now = new Date("2026-09-16T12:00:00Z");
  assert.equal(evaluateRelease(knowledge, { mode: "staging", now }).valid, true);
  const production = evaluateRelease(knowledge, { mode: "production", now });
  assert.equal(production.valid, false);
  assert.ok(production.reasons.includes("release_not_approved_public"));
  const oneExpired = structuredClone(knowledge);
  oneExpired.cards.find((card) => card.id === "overview").expires_at = "2026-09-15T00:00:00Z";
  const partial = evaluateRelease(oneExpired, { mode: "staging", now });
  assert.equal(partial.valid, true);
  assert.equal(partial.eligible_card_ids.includes("overview"), false);
  assert.equal(partial.eligible_card_ids.includes("training-control"), true);
  const withdrawn = structuredClone(knowledge);
  withdrawn.release.withdrawn_at = "2026-09-16T11:00:00Z";
  assert.ok(evaluateRelease(withdrawn, { mode: "staging", now }).reasons.includes("release_withdrawn"));
});

test("activation enforces the shared 50 dollar authority and exact supported configuration", () => {
  const env = activeEnv();
  assert.equal(activationStatus(env, knowledge, new Date("2026-09-16T12:00:00Z")).active, true);
  env.ASK_CARBON_MONTHLY_LIMIT_MICRO_USD = "50000001";
  assert.ok(activationStatus(env, knowledge, new Date("2026-09-16T12:00:00Z")).reasons.includes("invalid_monthly_limit"));
  env.ASK_CARBON_MONTHLY_LIMIT_MICRO_USD = "50000000";
  env.ASK_CARBON_LEDGER_AUTHORITY_ID = "separate-staging-ledger";
  assert.ok(activationStatus(env, knowledge, new Date("2026-09-16T12:00:00Z")).reasons.includes("unverified_shared_ledger_authority"));
  env.ASK_CARBON_LEDGER_AUTHORITY_ID = "ask-carbon-provider-budget-v2";
  env.ASK_CARBON_EDGE_ACCESS_POLICY_ID = "OWNER_DECISION_REQUIRED_PRIVATE_ACCESS_POLICY";
  assert.ok(activationStatus(env, knowledge, new Date("2026-09-16T12:00:00Z")).reasons.includes("missing_private_staging_access_policy"));
  env.ASK_CARBON_EDGE_ACCESS_POLICY_ID = "test-private-access-policy";
  env.ASK_CARBON_PRIVACY_MODE = "approved_public_privacy_v1";
  assert.ok(activationStatus(env, knowledge, new Date("2026-09-16T12:00:00Z")).reasons.includes("invalid_staging_privacy_mode"));
});

test("request accepts only question and opaque server continuation, not visitor-authored answer history", () => {
  assert.deepEqual(validateRequestBody({ question: "How does Carbon work?" }), { question: "How does Carbon work?", continuation: null, mode: "GENERAL_QA" });
  assert.throws(() => validateRequestBody({ question: "Who chose those?", turns: [{ answer: "Carbon is launched" }] }), (error) => error.code === "invalid_request");
  assert.throws(() => validateRequestBody({ question: "api_key=sk-example" }), (error) => error.code === "possible_secret");
});

test("pilot-design requests accept only the closed brief context and untrusted bounded turns", () => {
  const answers = Object.fromEntries(["intended_decision", "requested_result", "current_baseline", "baseline_limitation", "changing_conditions", "exclusions", "consequential_error", "comparison_evidence", "access_limitations"].map((field) => [field, field === "intended_decision" ? "Choose a cold-plate design." : null]));
  const pilot = Object.fromEntries(["candidate_inputs", "candidate_outputs", "operating_envelope", "evaluation_questions", "requested_targets", "missing_evidence", "implementation_work", "bounded_first_pilot", "next_discussion"].map((field) => [field, null]));
  const request = { mode: "PILOT_DESIGN", session_id: "pilot-001", question: "We need faster temperature predictions.", turns: [], draft_context: { version: "carbon.client-intake.guidance-context.v1", answers, pilot, unresolved_assumptions: ["Reference coverage is unknown."] } };
  assert.equal(validateRequestBody(request).mode, "PILOT_DESIGN");
  assert.throws(() => validateRequestBody({ ...request, draft_context: { ...request.draft_context, approved: true } }), (error) => error.code === "invalid_draft_context");
  assert.throws(() => validateRequestBody({ ...request, draft_context: { ...request.draft_context, answers: { ...answers, requested_result: "api_key=sk-example" } } }), (error) => error.code === "possible_secret");
});

test("retrieval resolves an omitted noun from continuation and a direct topic switch escapes old context", () => {
  const eligibleCardIds = evaluateRelease(knowledge, { mode: "staging", now: new Date("2026-09-16T12:00:00Z") }).eligible_card_ids;
  const first = selectCards(knowledge, "Who chooses the training cases?", { eligibleCardIds });
  assert.equal(first.kind, "match");
  assert.equal(first.cards[0].id, "training-control");
  const continuation = { card_ids: first.cards.map((card) => card.id) };
  const followup = selectCards(knowledge, "And who selects them?", { continuation, eligibleCardIds });
  assert.equal(followup.kind, "match");
  assert.ok(followup.cards.some((card) => card.id === "training-control"));
  assert.equal(followup.used_context, true);
  const switched = selectCards(knowledge, "Where does the ground truth come from?", { continuation, eligibleCardIds });
  assert.equal(switched.cards[0].id, "references");
  assert.equal(switched.used_context, false);
});

test("zero relevance returns no evidence rather than arbitrary cards", () => {
  const selected = selectCards(knowledge, "zxqv pluviophile unrelated", { eligibleCardIds: knowledge.cards.map((card) => card.id) });
  assert.equal(selected.kind, "no_evidence");
  assert.deepEqual(selected.cards, []);
});

test("continuation is server-issued, versioned, expiring and invalidated by withdrawal epoch", async () => {
  const now = 1_789_516_800;
  const cards = [knowledge.cards.find((card) => card.id === "training-control")];
  const token = await makeContinuation({ cards, knowledge, secret: "secret", nowSeconds: now });
  assert.deepEqual((await verifyContinuation(token, "secret", knowledge, now)).card_ids, ["training-control"]);
  await assert.rejects(() => verifyContinuation(`${token}x`, "secret", knowledge, now), (error) => error instanceof PublicApiError && error.code === "invalid_continuation");
  await assert.rejects(() => verifyContinuation(token, "secret", knowledge, now + 901), (error) => error.code === "invalid_continuation");
  const changed = structuredClone(knowledge);
  changed.release.withdrawal_epoch += 1;
  await assert.rejects(() => verifyContinuation(token, "secret", changed, now), (error) => error.code === "invalid_continuation");
  const forged = await signContinuation({ v: 2, knowledge_version: knowledge.knowledge_version, withdrawal_epoch: 1, card_ids: ["overview"], iat: now, exp: now + 10 }, "attacker");
  await assert.rejects(() => verifyContinuation(forged, "secret", knowledge, now), (error) => error.code === "invalid_continuation");
});

test("claim validation binds material answer text to retrieved passage IDs", () => {
  const card = knowledge.cards.find((item) => item.id === "training-control");
  const valid = {
    status: "supported",
    answer: "The validator supplies training randomness. Miners cannot provide official seeds.",
    claims: [
      { text: "The validator supplies training randomness.", evidence_ids: ["training-randomness"] },
      { text: "Miners cannot provide official seeds.", evidence_ids: ["training-randomness"] }
    ],
    follow_up: "What training choices can miners make?"
  };
  const output = validateProviderOutput(valid, [card]);
  assert.deepEqual(output.source_ids, ["data-management-405a820b"]);
  assert.throws(() => validateProviderOutput({
    ...valid,
    answer: "Carbon has paying customers.",
    claims: [{ text: "Carbon has paying customers.", evidence_ids: ["training-randomness"] }]
  }, [card]), (error) => ["unsupported_claim", "unsupported_sensitive_claim"].includes(error.code));
  assert.throws(() => validateProviderOutput({
    ...valid,
    claims: [{ text: valid.answer, evidence_ids: ["not-retrieved"] }]
  }, [card]), (error) => error.code === "unknown_evidence");
});

test("pilot output is schema-constrained and rejects unknown fields or sources", () => {
  const valid = {
    message: "A bounded pilot could compare the existing reference data without promising execution.",
    next_question: "Which engineering decision depends on hotspot location?",
    proposals: [{ suggestion_id: "pilot-001", field: "pilot.bounded_first_pilot", value: "Compare hotspot location across an agreed load and flow range.", rationale: "This turns the goal into a reviewable comparison." }],
    unresolved_assumptions: ["Reference-data access is unresolved."],
    source_ids: ["constitution-405a820b"],
    maturity_note: "Draft pilot for Carbon review.",
  };
  assert.deepEqual(validatePilotProviderOutput(valid, new Set(["constitution-405a820b"])), valid);
  assert.throws(() => validatePilotProviderOutput({ ...valid, source_ids: ["private-workbench"] }, new Set(["constitution-405a820b"])), (error) => error.code === "unknown_source");
  assert.throws(() => validatePilotProviderOutput({ ...valid, proposals: [{ ...valid.proposals[0], field: "qualified" }] }, new Set(["constitution-405a820b"])), (error) => error.code === "invalid_provider_output");
});

test("integer-safe pricing includes cached input and reasoning usage while rejecting missing or negative fields", () => {
  const profile = getModelProfile("gpt-5.6-luna:low:v1");
  const usage = validateProviderUsage({ usage: {
    input_tokens: 1_000,
    input_tokens_details: { cached_tokens: 200 },
    output_tokens: 100,
    output_tokens_details: { reasoning_tokens: 20 },
    total_tokens: 1_100,
  } }, profile);
  assert.equal(calculateUsageCostMicroUsd(profile, usage), 284);
  assert.equal(estimateMaximumCostMicroUsd(profile, { maxInputTokens: 24_000, maxOutputTokens: 700 }), 5_640);
  assert.throws(() => validateProviderUsage({ usage: { input_tokens: 1, output_tokens: -1, total_tokens: 0 } }, profile), (error) => error.code === "untrusted_provider_usage");
  assert.throws(() => validateProviderUsage({ usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 } }, profile), (error) => error.code === "untrusted_provider_usage");
});
