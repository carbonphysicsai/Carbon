import test from "node:test";
import assert from "node:assert/strict";
import {
  PublicApiError,
  activationStatus,
  calculateCostMicroUsd,
  makeBoundedContext,
  selectCards,
  signBoundedContext,
  validateProviderOutput,
  validateRequestBody,
  verifyBoundedContext,
} from "../worker/core.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const activeEnv = () => ({
  ASK_CARBON_ACTIVATION: "enabled",
  ASK_CARBON_APPROVED_ORIGINS: "https://carbonphysics.ai",
  ASK_CARBON_APPROVED_MODELS: "owner-approved-model",
  ASK_CARBON_MODEL: "owner-approved-model",
  ASK_CARBON_OPENAI_API_KEY: "test-only",
  ASK_CARBON_CONTEXT_SIGNING_SECRET: "test-only-signing-secret",
  ASK_CARBON_INPUT_USD_PER_MILLION: "1.25",
  ASK_CARBON_OUTPUT_USD_PER_MILLION: "5",
  ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
  ASK_CARBON_DAILY_COST_MICRO_USD_LIMIT: "100000",
  ASK_CARBON_MAX_CONCURRENCY: "4",
  ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
  ASK_CARBON_MAX_INPUT_TOKENS: "24000",
  ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
  ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
  ASK_CARBON_USAGE_LEDGER: { idFromName() {}, get() {} },
});

const releasedKnowledge = () => ({
  ...knowledge,
  release_status: "APPROVED_PUBLIC",
  source_release_date: "2026-09-16",
  expires_at: "2026-10-16T00:00:00Z",
});

test("activation fails closed for the draft manifest", () => {
  const result = activationStatus(activeEnv(), knowledge, new Date("2026-09-16T00:00:00Z"));
  assert.equal(result.active, false);
  assert.ok(result.reasons.includes("knowledge_not_approved"));
  assert.ok(result.reasons.includes("missing_source_release_date"));
});

test("activation requires every operational gate", () => {
  const env = activeEnv();
  const result = activationStatus(env, releasedKnowledge(), new Date("2026-09-16T00:00:00Z"));
  assert.equal(result.active, true);
  delete env.ASK_CARBON_CONTEXT_SIGNING_SECRET;
  assert.equal(activationStatus(env, releasedKnowledge(), new Date("2026-09-16T00:00:00Z")).active, false);
});

test("activation rejects expired knowledge and an unapproved model", () => {
  const env = activeEnv();
  env.ASK_CARBON_MODEL = "other-model";
  const released = { ...releasedKnowledge(), expires_at: "2026-09-15T23:59:59Z" };
  const result = activationStatus(env, released, new Date("2026-09-16T00:00:00Z"));
  assert.ok(result.reasons.includes("knowledge_expired_or_invalid"));
  assert.ok(result.reasons.includes("model_not_approved"));
});

test("request validation bounds context and detects pasted secrets", () => {
  assert.deepEqual(validateRequestBody({ question: "How does Carbon work?", turns: [] }), { question: "How does Carbon work?", turns: [] });
  assert.throws(() => validateRequestBody({ question: "api_key=sk-example" }), (error) => error instanceof PublicApiError && error.code === "possible_secret");
  assert.throws(() => validateRequestBody({ question: "Hello", extra: true }), (error) => error.code === "invalid_request");
});

test("bounded context signatures verify and reject tampering or expiry", async () => {
  const nowSeconds = 1_789_516_800;
  const cards = selectCards(knowledge, "Who establishes the reference answers?");
  const bounded = await makeBoundedContext({ question: "Who establishes the reference answers?", turns: [], cards, knowledge, requestId: "request-1", secret: "secret", nowSeconds });
  assert.equal((await verifyBoundedContext(bounded.token, "secret", nowSeconds)).request_id, "request-1");
  await assert.rejects(() => verifyBoundedContext(`${bounded.token}x`, "secret", nowSeconds), (error) => error.code === "invalid_context_signature");
  await assert.rejects(() => verifyBoundedContext(bounded.token, "secret", nowSeconds + 181), (error) => error.code === "expired_context");
  const independentlySigned = await signBoundedContext({ iat: nowSeconds, exp: nowSeconds + 1 }, "secret");
  assert.equal((await verifyBoundedContext(independentlySigned, "secret", nowSeconds)).iat, nowSeconds);
});

test("provider output rejects model-selected unknown sources and extra fields", () => {
  const allowed = new Set(["constitution-main"]);
  const valid = { answer: "The public sources do not establish that.", source_ids: ["constitution-main"], follow_ups: [], maturity_note: null };
  assert.deepEqual(validateProviderOutput(valid, allowed), valid);
  assert.throws(() => validateProviderOutput({ ...valid, source_ids: ["https://evil.example"] }, allowed), (error) => error.code === "unknown_source");
  assert.throws(() => validateProviderOutput({ ...valid, url: "https://evil.example" }, allowed), (error) => error.code === "invalid_provider_output");
});

test("cost arithmetic uses token prices in dollars per million", () => {
  assert.equal(calculateCostMicroUsd({ inputTokens: 1000, outputTokens: 200, inputUsdPerMillion: 1.25, outputUsdPerMillion: 5 }), 2250);
});
