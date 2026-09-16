import test from "node:test";
import assert from "node:assert/strict";
import worker, { createWorker } from "../worker/index.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const disabledEnv = {
  ASK_CARBON_ACTIVATION: "disabled",
  ASK_CARBON_APPROVED_ORIGINS: "https://carbonphysics.ai",
};

test("health route exposes fail-closed activation without secrets", async () => {
  const response = await worker.fetch(new Request("https://carbonphysics.ai/api/ask-carbon/health"), disabledEnv);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.active, false);
  assert.ok(body.reasons.includes("activation_disabled"));
  assert.equal(JSON.stringify(body).includes("api_key"), true);
  assert.equal(JSON.stringify(body).includes("test-only"), false);
});

test("origin checks are required but do not activate the service", async () => {
  const response = await worker.fetch(new Request("https://carbonphysics.ai/api/ask-carbon", {
    method: "POST",
    headers: { origin: "https://carbonphysics.ai", "content-type": "application/json" },
    body: JSON.stringify({ question: "How does Carbon work?" }),
  }), disabledEnv);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error.code, "not_active");
});

test("unknown ask-carbon subroutes and methods do not alter homepage routing", async () => {
  assert.equal((await worker.fetch(new Request("https://carbonphysics.ai/api/ask-carbon/admin"), disabledEnv)).status, 404);
  assert.equal((await worker.fetch(new Request("https://carbonphysics.ai/"), disabledEnv)).status, 404);
});

test("active flow maps source IDs server-side and settles measured usage", async () => {
  const calls = [];
  const ledger = {
    async fetch(url, options) {
      const body = JSON.parse(options.body);
      calls.push({ url, body });
      if (url.endsWith("/reserve")) return new Response(JSON.stringify({ allowed: true, lease_id: body.lease_id }), { status: 200 });
      return new Response(JSON.stringify({ settled: true }), { status: 200 });
    },
  };
  const env = {
    ASK_CARBON_ACTIVATION: "enabled",
    ASK_CARBON_APPROVED_ORIGINS: "https://carbonphysics.ai",
    ASK_CARBON_APPROVED_MODELS: "approved-test-model",
    ASK_CARBON_MODEL: "approved-test-model",
    ASK_CARBON_OPENAI_API_KEY: "test-provider-key",
    ASK_CARBON_CONTEXT_SIGNING_SECRET: "test-signing-secret",
    ASK_CARBON_INPUT_USD_PER_MILLION: "1",
    ASK_CARBON_OUTPUT_USD_PER_MILLION: "2",
    ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
    ASK_CARBON_DAILY_COST_MICRO_USD_LIMIT: "100000",
    ASK_CARBON_MAX_CONCURRENCY: "4",
    ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
    ASK_CARBON_MAX_INPUT_TOKENS: "24000",
    ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
    ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "global", get: () => ledger },
  };
  const released = { ...knowledge, release_status: "APPROVED_PUBLIC", source_release_date: "2026-09-16", expires_at: "2099-01-01T00:00:00Z" };
  const activeWorker = createWorker(released);
  const originalFetch = globalThis.fetch;
  let providerRequest;
  globalThis.fetch = async (url, options) => {
    providerRequest = { url, options, body: JSON.parse(options.body) };
    return new Response(JSON.stringify({
      status: "completed",
      output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({
        answer: "Carbon defines a bounded Challenge; miners propose strategies and validators independently reconstruct selected candidates.",
        source_ids: ["public-homepage-2026-09-16"],
        follow_ups: ["What do miners submit?"],
        maturity_note: "This describes the proposed public design, not a completed scientific pilot."
      }) }] }],
      usage: { input_tokens: 100, output_tokens: 50 },
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const response = await activeWorker.fetch(new Request("https://carbonphysics.ai/api/ask-carbon", {
      method: "POST",
      headers: { origin: "https://carbonphysics.ai", "content-type": "application/json", "cf-connecting-ip": "192.0.2.1" },
      body: JSON.stringify({ question: "How does Carbon work?", turns: [] }),
    }), env);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.sources[0].url, "https://carbonphysics.ai/");
    assert.equal(providerRequest.url, "https://api.openai.com/v1/responses");
    assert.equal(providerRequest.options.headers.authorization, "Bearer test-provider-key");
    assert.equal("tools" in providerRequest.body, false);
    assert.equal(providerRequest.body.store, false);
    assert.equal(calls[0].url.endsWith("/reserve"), true);
    assert.equal(calls[1].url.endsWith("/settle"), true);
    assert.equal(calls[1].body.actual_cost_micro_usd, 200);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("provider failure settles the conservative reserved maximum", async () => {
  const calls = [];
  const ledger = {
    async fetch(url, options) {
      const body = JSON.parse(options.body);
      calls.push({ url, body });
      return new Response(JSON.stringify(url.endsWith("/reserve") ? { allowed: true, lease_id: body.lease_id } : { settled: true }), { status: 200 });
    },
  };
  const env = {
    ASK_CARBON_ACTIVATION: "enabled",
    ASK_CARBON_APPROVED_ORIGINS: "https://carbonphysics.ai",
    ASK_CARBON_APPROVED_MODELS: "approved-test-model",
    ASK_CARBON_MODEL: "approved-test-model",
    ASK_CARBON_OPENAI_API_KEY: "test-provider-key",
    ASK_CARBON_CONTEXT_SIGNING_SECRET: "test-signing-secret",
    ASK_CARBON_INPUT_USD_PER_MILLION: "1",
    ASK_CARBON_OUTPUT_USD_PER_MILLION: "2",
    ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
    ASK_CARBON_DAILY_COST_MICRO_USD_LIMIT: "100000",
    ASK_CARBON_MAX_CONCURRENCY: "4",
    ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
    ASK_CARBON_MAX_INPUT_TOKENS: "24000",
    ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
    ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "global", get: () => ledger },
  };
  const released = { ...knowledge, release_status: "APPROVED_PUBLIC", source_release_date: "2026-09-16", expires_at: "2099-01-01T00:00:00Z" };
  const activeWorker = createWorker(released);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { message: "simulated" } }), { status: 500 });
  try {
    const response = await activeWorker.fetch(new Request("https://carbonphysics.ai/api/ask-carbon", {
      method: "POST",
      headers: { origin: "https://carbonphysics.ai", "content-type": "application/json" },
      body: JSON.stringify({ question: "How does Carbon work?" }),
    }), env);
    assert.equal(response.status, 502);
    assert.equal(calls[1].body.actual_cost_micro_usd, 25_400);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
