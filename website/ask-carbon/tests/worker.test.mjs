import test from "node:test";
import assert from "node:assert/strict";
import worker, { AskCarbonUsageLedger, createWorker } from "../worker/index.mjs";
import { answerSchema, pilotAnswerSchema, validatePilotProviderOutput } from "../worker/core.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };
import { readFileSync } from "node:fs";
import { calculateUsageCostMicroUsd, estimateMaximumCostMicroUsd, getModelProfile, validateProviderUsage } from "../worker/models.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async transaction(callback) { return callback(this); }
}

const makeRuntime = (overrides = {}) => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  const env = {
    ASK_CARBON_ACTIVATION: "enabled",
    ASK_CARBON_RUNTIME_MODE: "staging",
    ASK_CARBON_APPROVED_ORIGINS: "https://staging.example",
    ASK_CARBON_APPROVED_MODEL_CONFIGS: "gpt-5.6-luna:low:v1,gpt-5.6-terra:low:v1",
    ASK_CARBON_MODEL_CONFIG_ID: "gpt-5.6-luna:low:v1",
    ASK_CARBON_OPENAI_API_KEY: "test-provider-key",
    ASK_CARBON_CONTINUATION_SIGNING_SECRET: "test-signing-secret",
    ASK_CARBON_OPERATOR_READ_SECRET: "test-operator-secret",
    ASK_CARBON_EVALUATION_ACCESS_SECRET: "test-only-evaluation-access-secret-32-bytes",
    ASK_CARBON_PRIVACY_MODE: "evaluation_public_synthetic_only",
    ASK_CARBON_EDGE_ACCESS_POLICY_ID: "test-private-access-policy",
    ASK_CARBON_STAGING_ACCESS_MODE: "cloudflare_access",
    ASK_CARBON_EDGE_ABUSE_POLICY_ID: "test-edge-abuse-policy",
    ASK_CARBON_LEDGER_AUTHORITY_ID: "ask-carbon-provider-budget-v2",
    ASK_CARBON_ENVIRONMENT: "staging",
    ASK_CARBON_OPERATIONAL_SCOPE_ID: "staging",
    ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD: "50000000",
    ASK_CARBON_MONTHLY_LIMIT_MICRO_USD: "50000000",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_PERIOD: "2026-09",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_SCOPE_ID: "bakeoff",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_EXPOSURE_MICRO_USD: "80831",
    ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
    ASK_CARBON_MAX_CONCURRENCY: "4",
    ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
    ASK_CARBON_CLIENT_COUNTER_RETENTION_MS: "86400000",
    ASK_CARBON_MAX_INPUT_TOKENS: "24000",
    ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
    ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
    ASK_CARBON_PILOT_MAX_REQUESTS_PER_SESSION: "8",
    ASK_CARBON_STAGING_OPERATOR_SECRET: "test-staging-operator-secret",
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "global", get: () => ({ fetch: (url, options) => ledger.fetch(new Request(url, options)) }) },
    ASK_CARBON_EDGE_RATE_LIMITER: { limit: async () => ({ success: true }) },
    ...overrides,
  };
  return { env, ledger };
};

const ask = (workerRef, env, question, continuation = null, extra = {}) => workerRef.fetch(new Request("https://staging.example/api/ask-carbon", {
  method: "POST",
  headers: { origin: "https://staging.example", "content-type": "application/json", "cf-connecting-ip": "192.0.2.1", ...extra.headers },
  body: extra.body ?? JSON.stringify({ question, ...(continuation ? { continuation } : {}) }),
}), env);

const validProviderBody = (overrides = {}) => ({
  id: "resp-test-1",
  model: "gpt-5.6-luna",
  status: "completed",
  output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({
    status: "supported",
    card_ids: ["overview"],
    follow_up: "What is a Challenge?"
  }) }] }],
  usage: {
    input_tokens: 100,
    input_tokens_details: { cached_tokens: 0 },
    output_tokens: 50,
    output_tokens_details: { reasoning_tokens: 10 },
    total_tokens: 150,
  },
  ...overrides,
});

const withProvider = async (implementation, callback) => {
  const original = globalThis.fetch;
  globalThis.fetch = implementation;
  try { return await callback(); } finally { globalThis.fetch = original; }
};

test("health fails closed without exposing secret values and homepage routing stays untouched", async () => {
  const response = await worker.fetch(new Request("https://staging.example/api/ask-carbon/health"), { ASK_CARBON_ACTIVATION: "disabled" });
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.active, false);
  assert.equal(JSON.stringify(body).includes("test-provider-key"), false);
  assert.equal((await worker.fetch(new Request("https://staging.example/"), {})).status, 404);
  const assetResponse = await worker.fetch(new Request("https://staging.example/"), {
    ASSETS: { fetch: async () => new Response("staging homepage", { status: 200, headers: { "content-type": "text/html" } }) },
  });
  assert.equal(await assetResponse.text(), "staging homepage");
  assert.equal(assetResponse.headers.get("content-type"), "text/html");
  assert.match(assetResponse.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.equal(assetResponse.headers.get("x-frame-options"), "DENY");
  assert.equal(assetResponse.headers.get("cache-control"), "private, no-store");
});

test("staging basic authentication protects assets, health and answer routes before processing", async () => {
  const runtime = makeRuntime({
    ASK_CARBON_STAGING_ACCESS_MODE: "http_basic_v1",
    ASK_CARBON_STAGING_AUTH_USER: "owner-review",
    ASK_CARBON_STAGING_AUTH_PASSWORD: "correct horse battery staple",
    ASSETS: { fetch: async () => new Response("private staging") },
  });
  const workerRef = createWorker(knowledge);
  const unauthenticated = await workerRef.fetch(new Request("https://staging.example/"), runtime.env);
  assert.equal(unauthenticated.status, 401);
  assert.match(unauthenticated.headers.get("www-authenticate"), /Ask Carbon private staging/);
  const wrong = await workerRef.fetch(new Request("https://staging.example/", { headers: { authorization: `Basic ${btoa("owner-review:wrong")}` } }), runtime.env);
  assert.equal(wrong.status, 401);
  const authenticated = await workerRef.fetch(new Request("https://staging.example/", { headers: { authorization: `Basic ${btoa("owner-review:correct horse battery staple")}` } }), runtime.env);
  assert.equal(authenticated.status, 200);
  assert.equal(await authenticated.text(), "private staging");

  const encodedCredential = btoa("token-review:token-secret");
  const tokenRuntime = makeRuntime({
    ASK_CARBON_STAGING_ACCESS_MODE: "http_basic_v1",
    ASK_CARBON_STAGING_BASIC_AUTH: encodedCredential,
    ASSETS: { fetch: async () => new Response("private token staging") },
  });
  const tokenAuthenticated = await workerRef.fetch(new Request("https://staging.example/", {
    headers: { authorization: `Basic ${encodedCredential}` },
  }), tokenRuntime.env);
  assert.equal(tokenAuthenticated.status, 200);
  assert.equal(await tokenAuthenticated.text(), "private token staging");
});

test("staging evaluation access is secret-bound, evaluation-only and does not weaken browser Basic authentication", async () => {
  const runtime = makeRuntime({
    ASK_CARBON_EVALUATION_TELEMETRY: "enabled",
    ASK_CARBON_STAGING_ACCESS_MODE: "http_basic_v1",
    ASK_CARBON_STAGING_BASIC_AUTH: btoa("owner-review:browser-secret"),
  });
  const workerRef = createWorker(knowledge);
  const wrong = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/health", {
    headers: { "x-ask-carbon-evaluation-access": "wrong" },
  }), runtime.env);
  assert.equal(wrong.status, 401);
  const accepted = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/health", {
    headers: { "x-ask-carbon-evaluation-access": runtime.env.ASK_CARBON_EVALUATION_ACCESS_SECRET },
  }), runtime.env);
  assert.equal(accepted.status, 200);
  const assetStillPrivate = await workerRef.fetch(new Request("https://staging.example/", {
    headers: { "x-ask-carbon-evaluation-access": runtime.env.ASK_CARBON_EVALUATION_ACCESS_SECRET },
  }), runtime.env);
  assert.equal(assetStillPrivate.status, 401);
  const production = makeRuntime({
    ASK_CARBON_RUNTIME_MODE: "production",
    ASK_CARBON_EVALUATION_TELEMETRY: undefined,
    ASK_CARBON_STAGING_ACCESS_MODE: "cloudflare_access",
  });
  const productionResponse = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/health", {
    headers: { "x-ask-carbon-evaluation-access": production.env.ASK_CARBON_EVALUATION_ACCESS_SECRET },
  }), production.env);
  assert.notEqual(productionResponse.status, 200);
});

test("evaluation ledger readout is staging-only, separately authorized and aggregate-only", async () => {
  const runtime = makeRuntime({
    ASK_CARBON_EVALUATION_TELEMETRY: "enabled",
    ASK_CARBON_STAGING_ACCESS_MODE: "http_basic_v1",
    ASK_CARBON_STAGING_AUTH_USER: "owner-review",
    ASK_CARBON_STAGING_AUTH_PASSWORD: "test-review-password",
  });
  const workerRef = createWorker(knowledge);
  const basic = `Basic ${btoa("owner-review:test-review-password")}`;
  const unauthorized = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/internal/ledger", {
    headers: { authorization: basic },
  }), runtime.env);
  assert.equal(unauthorized.status, 403);
  const authorized = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/internal/ledger", {
    headers: { authorization: basic, "x-ask-carbon-operator-secret": "test-operator-secret" },
  }), runtime.env);
  assert.equal(authorized.status, 200);
  const summary = await authorized.json();
  assert.equal(summary.total_attempts, 0);
  assert.deepEqual(summary.attempt_state_counts, {});
  assert.equal("attempts" in summary, false);
  assert.equal("clients" in summary, false);
  assert.equal("pilot_sessions" in summary, false);
  const production = makeRuntime({
    ASK_CARBON_RUNTIME_MODE: "production",
    ASK_CARBON_EVALUATION_TELEMETRY: "enabled",
    ASK_CARBON_STAGING_ACCESS_MODE: "cloudflare_access",
  });
  const denied = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/internal/ledger", {
    headers: { "x-ask-carbon-operator-secret": "test-operator-secret" },
  }), production.env);
  assert.equal(denied.status, 403);
});

test("staging ledger snapshot requires the separate operator secret and returns no prompt text", async () => {
  const runtime = makeRuntime();
  const workerRef = createWorker(knowledge);
  const denied = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/staging/budget-snapshot", {
    method: "POST",
    headers: { "x-ask-carbon-staging-operator": "wrong" },
  }), runtime.env);
  assert.equal(denied.status, 403);
  assert.equal((await denied.json()).error.code, "staging_operator_required");
  const accepted = await workerRef.fetch(new Request("https://staging.example/api/ask-carbon/staging/budget-snapshot", {
    method: "POST",
    headers: { "x-ask-carbon-staging-operator": "test-staging-operator-secret" },
  }), runtime.env);
  assert.equal(accepted.status, 200);
  const body = await accepted.json();
  assert.equal(body.schema_version, 3);
  assert.equal(JSON.stringify(body).includes("question"), false);
  assert.equal(JSON.stringify(body).includes("test-staging-operator-secret"), false);
});

test("active path uses the exact compatible schema, settles trustworthy usage and returns server-owned citations", async () => {
  const runtime = makeRuntime({ ASK_CARBON_EVALUATION_TELEMETRY: "enabled" });
  let providerRequest;
  await withProvider(async (url, options) => {
    providerRequest = { url, options, body: JSON.parse(options.body) };
    return new Response(JSON.stringify(validProviderBody()), { status: 200, headers: { "content-type": "application/json" } });
  }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.status, "supported");
    assert.equal(body.sources[0].url.includes("/blob/405a820b"), true);
    assert.ok(body.maturity_note.includes("BOUNDED"));
    assert.equal(typeof body.continuation, "string");
    assert.equal(body.evaluation.provider_model, "gpt-5.6-luna");
    assert.equal(body.evaluation.usage.input_tokens, 100);
    assert.equal(body.evaluation.actual_cost_micro_usd, 80);
    assert.equal(body.evaluation.reserved_cost_micro_usd, 5_640);
    assert.ok(Number.isSafeInteger(body.evaluation.worker_elapsed_ms));
  });
  assert.equal(providerRequest.url, "https://api.openai.com/v1/responses");
  assert.equal(providerRequest.body.model, "gpt-5.6-luna");
  assert.deepEqual(providerRequest.body.reasoning, { effort: "low" });
  assert.equal(providerRequest.body.text.verbosity, "low");
  assert.equal(providerRequest.body.text.format.type, "json_schema");
  assert.equal(providerRequest.body.text.format.strict, true);
  assert.equal(providerRequest.body.text.format.name, "ask_carbon_answer_selection");
  assert.ok(providerRequest.body.text.format.schema.properties.card_ids.items.enum.includes("overview"));
  assert.ok(providerRequest.body.text.format.schema.properties.follow_up.enum.includes("What is a Challenge?"));
  assert.equal(providerRequest.body.store, false);
  assert.equal("tools" in providerRequest.body, false);
  assert.equal(providerRequest.body.instructions.includes("Signed"), false);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  assert.equal(Object.values(state.attempts)[0].state, "settled");
  assert.equal(state.months[new Date().toISOString().slice(0, 7)].settled_micro_usd, 80);
});

test("provider selection and follow-up enums exclude stale release material", async () => {
  const runtime = makeRuntime();
  const staleKnowledge = structuredClone(knowledge);
  staleKnowledge.cards.find((card) => card.id === "challenge").expires_at = "2026-09-16T00:00:00Z";
  let providerRequest;
  await withProvider(async (_url, options) => {
    providerRequest = JSON.parse(options.body);
    return new Response(JSON.stringify(validProviderBody({
      output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({
        status: "supported",
        card_ids: ["overview"],
        follow_up: null,
      }) }] }],
    })), { status: 200 });
  }, async () => {
    const response = await ask(createWorker(staleKnowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 200);
  });
  assert.equal(providerRequest.text.format.schema.properties.card_ids.items.enum.includes("challenge"), false);
  assert.equal(providerRequest.text.format.schema.properties.follow_up.enum.includes("What is a Challenge?"), false);
});

test("no-evidence is distinct, cites nothing and makes no provider call", async () => {
  const runtime = makeRuntime();
  let calls = 0;
  await withProvider(async () => { calls += 1; throw new Error("must not dispatch"); }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "zxqv pluviophile unrelated");
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.status, "insufficient_evidence");
    assert.deepEqual(body.sources, []);
  });
  assert.equal(calls, 0);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.values((await snapshot.json()).attempts)[0].state, "released_pre_dispatch");
});

test("public boundary answers are specific, cite nothing and release before provider dispatch", async () => {
  const runtime = makeRuntime();
  let calls = 0;
  await withProvider(async () => { calls += 1; throw new Error("must not dispatch"); }, async () => {
    const privacy = await ask(createWorker(knowledge), runtime.env, "Do you retain absolutely nothing when I ask a question?");
    const privacyBody = await privacy.json();
    assert.equal(privacyBody.status, "service_information");
    assert.match(privacyBody.answer, /Chutes/);
    assert.doesNotMatch(privacyBody.answer, /OpenAI|Zero Data Retention|30 days/);
    assert.deepEqual(privacyBody.sources, []);
    const execution = await ask(createWorker(knowledge), runtime.env, "Deploy my miner now.");
    const executionBody = await execution.json();
    assert.equal(executionBody.status, "out_of_scope");
    assert.match(executionBody.answer, /cannot deploy or run a miner/);
  });
  assert.equal(calls, 0);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.deepEqual(Object.values((await snapshot.json()).attempts).map((attempt) => attempt.state), ["released_pre_dispatch", "released_pre_dispatch"]);
});

test("edge rate limiting rejects before request parsing or provider reservation", async () => {
  const runtime = makeRuntime({ ASK_CARBON_EDGE_RATE_LIMITER: { limit: async () => ({ success: false }) } });
  let calls = 0;
  await withProvider(async () => { calls += 1; throw new Error("must not dispatch"); }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 429);
    assert.equal((await response.json()).error.code, "edge_rate_limit");
  });
  assert.equal(calls, 0);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.keys((await snapshot.json()).attempts).length, 0);
});

test("follow-up continuation re-retrieves evidence and never sends visitor-authored history", async () => {
  const runtime = makeRuntime();
  const requests = [];
  await withProvider(async (url, options) => {
    const requestBody = JSON.parse(options.body);
    requests.push(requestBody);
    const selectedCard = requestBody.text.format.schema.properties.card_ids.items.enum[0];
    return new Response(JSON.stringify(validProviderBody({
      id: `resp-${requests.length}`,
      output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({
        status: "supported",
        card_ids: [selectedCard],
        follow_up: null
      }) }] }]
    })), { status: 200 });
  }, async () => {
    const firstResponse = await ask(createWorker(knowledge), runtime.env, "Who chooses the training cases?");
    const first = await firstResponse.json();
    const secondResponse = await ask(createWorker(knowledge), runtime.env, "And who selects them?", first.continuation);
    assert.equal((await secondResponse.json()).status, "supported");
  });
  assert.equal(requests.length, 2);
  assert.equal(requests[1].input[0].content[0].text, "And who selects them?");
  assert.equal(JSON.stringify(requests[1]).includes("Miners cannot provide official seeds"), false);
});

test("missing or negative usage after possible dispatch retains conservative unresolved exposure", async () => {
  for (const usage of [undefined, { input_tokens: 1, output_tokens: -1, total_tokens: 0 }]) {
    const runtime = makeRuntime();
    await withProvider(async () => {
      const body = validProviderBody();
      body.usage = usage;
      return new Response(JSON.stringify(body), { status: 200 });
    }, async () => {
      const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
      assert.equal(response.status, 502);
      assert.equal((await response.json()).error.code, "untrusted_provider_usage");
    });
    const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
    const state = await snapshot.json();
    assert.equal(Object.values(state.attempts)[0].state, "unresolved");
    assert.equal(state.months[new Date().toISOString().slice(0, 7)].unresolved_micro_usd, 5_640);
  }
});

test("rejected or invalid output with trustworthy billed usage is settled before typed failure", async () => {
  const runtime = makeRuntime();
  await withProvider(async () => new Response(JSON.stringify(validProviderBody({ status: "incomplete", output: [] })), { status: 200 }), async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error.code, "provider_incomplete");
  });
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.values((await snapshot.json()).attempts)[0].state, "settled");
});

test("settlement failure stops the answer and leaves possible provider work conservatively exposed", async () => {
  const runtime = makeRuntime();
  runtime.env.ASK_CARBON_USAGE_LEDGER = {
    idFromName: () => "global",
    get: () => ({
      fetch: (url, options) => new URL(url).pathname === "/settle"
        ? new Response(JSON.stringify({ settled: false, reason: "simulated_storage_failure" }), { status: 503, headers: { "content-type": "application/json" } })
        : runtime.ledger.fetch(new Request(url, options)),
    }),
  };
  await withProvider(async () => new Response(JSON.stringify(validProviderBody()), { status: 200 }), async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.code, "accounting_settlement_failed");
  });
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.values((await snapshot.json()).attempts)[0].state, "dispatch_authorized");
});

test("model mismatch is detected and conservatively unresolved", async () => {
  const runtime = makeRuntime();
  await withProvider(async () => new Response(JSON.stringify(validProviderBody({ model: "unexpected-model" })), { status: 200 }), async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error.code, "provider_model_mismatch");
  });
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.values((await snapshot.json()).attempts)[0].state, "unresolved");
});

test("provider HTTP failure is not mislabeled as a model mismatch and remains conservatively unresolved", async () => {
  const runtime = makeRuntime();
  await withProvider(async () => new Response(JSON.stringify({
    error: { type: "invalid_request_error", code: "invalid_request", param: "text.format" },
  }), { status: 400, headers: { "content-type": "application/json" } }), async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 502);
    const body = await response.json();
    assert.equal(body.error.code, "provider_error");
    assert.match(body.request_id, /^[0-9a-f-]{36}$/);
  });
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  assert.equal(Object.values(state.attempts)[0].state, "unresolved");
  assert.equal(Object.values(state.attempts)[0].terminal_reason, "provider_http_400");
});

test("provider-facing strict schemas omit unsupported uniqueness keywords while runtime validation rejects duplicates", () => {
  assert.equal(JSON.stringify(answerSchema).includes('"uniqueItems"'), false);
  assert.equal(JSON.stringify(pilotAnswerSchema).includes('"uniqueItems"'), false);
  assert.throws(() => validatePilotProviderOutput({
    message: "Bounded guidance.",
    next_question: null,
    proposals: [],
    unresolved_assumptions: [],
    source_ids: ["source-a", "source-a"],
    maturity_note: null,
  }, new Set(["source-a"])), /unapproved source/);
});

test("streaming request limit rejects chunked oversized bodies before full buffering", async () => {
  const runtime = makeRuntime();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(8_000));
      controller.enqueue(new Uint8Array(8_000));
      controller.close();
    }
  });
  const request = new Request("https://staging.example/api/ask-carbon", {
    method: "POST",
    headers: { origin: "https://staging.example", "content-type": "application/json" },
    body: stream,
    duplex: "half",
  });
  const response = await createWorker(knowledge).fetch(request, runtime.env);
  assert.equal(response.status, 413);
  assert.equal((await response.json()).error.code, "request_too_large");
});

test("provider response stream is bounded and possible work remains unresolved", async () => {
  const runtime = makeRuntime();
  await withProvider(async () => new Response("x".repeat(96_001), { status: 200 }), async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error.code, "provider_response_too_large");
  });
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  assert.equal(Object.values((await snapshot.json()).attempts)[0].state, "unresolved");
});

test("pre-dispatch context failure releases provider cost with no dispatch", async () => {
  const runtime = makeRuntime({ ASK_CARBON_MAX_INPUT_TOKENS: "10" });
  let calls = 0;
  await withProvider(async () => { calls += 1; throw new Error("must not dispatch"); }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error.code, "context_too_large");
  });
  assert.equal(calls, 0);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  assert.equal(Object.values(state.attempts)[0].state, "released_pre_dispatch");
  assert.equal(state.months[new Date().toISOString().slice(0, 7)].exposure_micro_usd, 0);
});

test("pilot-design mode shares the repaired adapter, ledger and bounded output path", async () => {
  const runtime = makeRuntime();
  const answers = Object.fromEntries(["intended_decision", "requested_result", "current_baseline", "baseline_limitation", "changing_conditions", "exclusions", "consequential_error", "comparison_evidence", "access_limitations"].map((field) => [field, field === "intended_decision" ? "Choose a cold-plate design." : null]));
  const pilot = Object.fromEntries(["candidate_inputs", "candidate_outputs", "operating_envelope", "evaluation_questions", "requested_targets", "missing_evidence", "implementation_work", "bounded_first_pilot", "next_discussion"].map((field) => [field, null]));
  let providerRequest;
  await withProvider(async (_url, options) => {
    providerRequest = JSON.parse(options.body);
    return new Response(JSON.stringify(validProviderBody({
      output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify({
        message: "A bounded comparison can be drafted without promising execution.",
        next_question: "Which operating conditions vary?",
        proposals: [{ suggestion_id: "pilot-thermal-001", field: "pilot.evaluation_questions", value: "Compare hotspot location and design ranking.", rationale: "These observables connect the prediction to the design decision." }],
        unresolved_assumptions: ["Reference coverage and access remain unknown."],
        source_ids: ["constitution-405a820b"],
        maturity_note: "Draft pilot for Carbon review.",
      }) }] }],
    })), { status: 200 });
  }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "unused", null, { body: JSON.stringify({
      mode: "PILOT_DESIGN",
      session_id: "pilot-session-1",
      question: "What is Carbon?",
      turns: [],
      draft_context: { version: "carbon.client-intake.guidance-context.v1", answers, pilot, unresolved_assumptions: [] },
    }) });
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.mode, "PILOT_DESIGN");
    assert.equal(body.proposals[0].field, "pilot.evaluation_questions");
    assert.equal(body.next_question, "Which operating conditions vary?");
  });
  assert.equal(providerRequest.store, false);
  assert.equal(providerRequest.text.format.name, "carbon_pilot_guidance");
  assert.equal(providerRequest.text.format.schema.properties.source_ids.items.enum.includes("constitution-405a820b"), true);
  assert.equal("tools" in providerRequest, false);
  assert.equal(providerRequest.instructions.includes("Signed bounded-context token"), false);
  assert.equal(providerRequest.input[0].content[0].text.includes("draft_context"), true);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  const attempt = Object.values(state.attempts)[0];
  assert.equal(attempt.mode, "PILOT_DESIGN");
  assert.equal(attempt.state, "settled");
});

// Chutes chat/completions adapter. The fixture is constructed from the
// OpenAI-compatible shape, not recorded (see its provenance block): no live
// completion was requested for this candidate.
const chutesFixture = JSON.parse(readFileSync(new URL("./fixtures/chutes-chat-completion.v1.json", import.meta.url), "utf8"));
const chutesBody = (mutate = () => {}) => { const body = structuredClone(chutesFixture.response); mutate(body); return body; };
const chutesRuntime = (overrides = {}) => makeRuntime({
  ASK_CARBON_APPROVED_MODEL_CONFIGS: "gemma-4-31b-turbo-tee:v1",
  ASK_CARBON_MODEL_CONFIG_ID: "gemma-4-31b-turbo-tee:v1",
  ASK_CARBON_OPENAI_API_KEY: undefined,
  ASK_CARBON_CHUTES_API_KEY: "test-chutes-key",
  ...overrides,
});
const attemptState = async (runtime) => {
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  return { attempt: Object.values(state.attempts)[0], month: state.months[new Date().toISOString().slice(0, 7)] };
};
const askChutes = async (runtime, body, status = 200) => withProvider(
  async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  async () => ask(createWorker(knowledge), runtime.env, "What is Carbon?"),
);

test("fixture provenance says constructed, so nobody mistakes it for a recorded provider response", () => {
  assert.equal(chutesFixture.provenance.kind, "CONSTRUCTED_NOT_RECORDED");
  assert.equal(chutesFixture.response.model, getModelProfile("gemma-4-31b-turbo-tee:v1").request_model);
});

test("Chutes profile carries the live-read prices and limits and settles through the shared cost rule", () => {
  const profile = getModelProfile("gemma-4-31b-turbo-tee:v1");
  assert.equal(profile.provider, "chutes_chat_completions");
  assert.equal(profile.request_model, "google/gemma-4-31B-turbo-TEE");
  assert.equal(profile.input_price_micro_usd_per_million, 120_000);
  assert.equal(profile.cached_input_price_micro_usd_per_million, 12_000);
  assert.equal(profile.output_price_micro_usd_per_million, 370_000);
  assert.equal(profile.context_window_tokens, 131_072);
  assert.equal(profile.model_max_output_tokens, 65_536);
  assert.equal(profile.confidential_compute, true);
  // 1834 * 0.12 + 41 * 0.37 = 235.25 micro-USD, rounded up.
  assert.equal(calculateUsageCostMicroUsd(profile, validateProviderUsage(chutesFixture.response, profile)), 236);
  assert.equal(estimateMaximumCostMicroUsd(profile, { maxInputTokens: 24_000, maxOutputTokens: 700 }), 3_139);
});

test("Chutes activation requires the Chutes secret and an OpenAI key does not satisfy it", async () => {
  const health = async (env) => (await createWorker(knowledge).fetch(new Request("https://staging.example/api/ask-carbon/health"), env)).json();
  const withOpenAiOnly = await health(chutesRuntime({ ASK_CARBON_CHUTES_API_KEY: undefined, ASK_CARBON_OPENAI_API_KEY: "test-provider-key" }).env);
  assert.equal(withOpenAiOnly.active, false);
  assert.ok(withOpenAiOnly.reasons.includes("missing_ask_carbon_chutes_api_key"));
  assert.equal(withOpenAiOnly.reasons.includes("missing_ask_carbon_openai_api_key"), false);
  // Specimen: the same check passes with the Chutes secret present.
  const withChutes = await health(chutesRuntime().env);
  assert.deepEqual(withChutes.reasons, []);
  assert.equal(withChutes.active, true);
  // And the reverse: an OpenAI configuration still demands its own key.
  const lunaWithoutKey = await health(makeRuntime({ ASK_CARBON_OPENAI_API_KEY: undefined, ASK_CARBON_CHUTES_API_KEY: "test-chutes-key" }).env);
  assert.ok(lunaWithoutKey.reasons.includes("missing_ask_carbon_openai_api_key"));
  assert.equal(JSON.stringify(withOpenAiOnly).includes("test-provider-key"), false);
});

test("Chutes request is chat/completions with the strict selection schema, its own key and no OpenAI-only fields", async () => {
  const runtime = chutesRuntime({ ASK_CARBON_EVALUATION_TELEMETRY: "enabled" });
  let providerRequest;
  await withProvider(async (url, options) => {
    providerRequest = { url, headers: options.headers, body: JSON.parse(options.body) };
    return new Response(JSON.stringify(chutesBody()), { status: 200, headers: { "content-type": "application/json" } });
  }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "What is Carbon?");
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.status, "supported");
    assert.equal(body.model_config_id, "gemma-4-31b-turbo-tee:v1");
    assert.equal(body.evaluation.provider_model, "google/gemma-4-31B-turbo-TEE");
    assert.equal(body.evaluation.usage.input_tokens, 1834);
    assert.equal(body.evaluation.actual_cost_micro_usd, 236);
    assert.equal(body.evaluation.reserved_cost_micro_usd, 3_139);
    assert.equal(body.follow_up, "What is a Challenge?");
    assert.equal(body.sources[0].url.includes("/blob/405a820b"), true);
  });
  assert.equal(providerRequest.url, "https://llm.chutes.ai/v1/chat/completions");
  assert.equal(providerRequest.headers.authorization, "Bearer test-chutes-key");
  const sent = providerRequest.body;
  assert.equal(sent.model, "google/gemma-4-31B-turbo-TEE");
  assert.equal(sent.stream, false);
  assert.equal(sent.temperature, 0);
  assert.equal(sent.max_tokens, 700);
  assert.deepEqual(sent.messages.map((message) => message.role), ["system", "user"]);
  assert.equal(sent.messages[1].content, "What is Carbon?");
  assert.equal(sent.messages[0].content.includes("Select the smallest set of retrieved card IDs"), true);
  assert.equal(sent.response_format.type, "json_schema");
  assert.equal(sent.response_format.json_schema.strict, true);
  assert.equal(sent.response_format.json_schema.name, "ask_carbon_answer_selection");
  assert.ok(sent.response_format.json_schema.schema.properties.card_ids.items.enum.includes("overview"));
  for (const field of ["store", "reasoning", "text", "input", "instructions", "max_output_tokens", "tools"]) assert.equal(field in sent, false, field);
  const { attempt, month } = await attemptState(runtime);
  assert.equal(attempt.state, "settled");
  assert.equal(attempt.model_config_id, "gemma-4-31b-turbo-tee:v1");
  assert.equal(month.settled_micro_usd, 236);
});

test("Chutes non-stop completions settle billed usage and then fail typed", async () => {
  const cases = [
    [(body) => { body.choices[0].finish_reason = "length"; }, "provider_incomplete"],
    [(body) => { body.choices[0].message.refusal = "I can't help with that."; }, "provider_refused"],
    [(body) => { body.choices[0].finish_reason = "content_filter"; }, "provider_refused"],
    [(body) => { body.choices.push(structuredClone(body.choices[0])); }, "provider_refused"],
    [(body) => { body.choices = []; }, "provider_refused"],
    [(body) => { body.choices[0].message.content = `<think>reasoning</think>${body.choices[0].message.content}`; }, "invalid_provider_output"],
    [(body) => { body.choices[0].message.content = JSON.stringify({ status: "supported", card_ids: ["not-retrieved"], follow_up: null }); }, "unknown_evidence"],
  ];
  for (const [mutate, code] of cases) {
    const runtime = chutesRuntime();
    const response = await askChutes(runtime, chutesBody(mutate));
    assert.equal(response.status, 502, code);
    assert.equal((await response.json()).error.code, code);
    assert.equal((await attemptState(runtime)).attempt.state, "settled", code);
  }
});

test("Chutes responses with untrusted identity or usage stay conservatively unresolved", async () => {
  const cases = [
    [(body) => { body.model = "google/gemma-4-31b-turbo-tee"; }, "provider_model_mismatch"],
    [(body) => { delete body.model; }, "provider_model_mismatch"],
    [(body) => { delete body.usage; }, "untrusted_provider_usage"],
    [(body) => { body.usage.total_tokens += 1; }, "untrusted_provider_usage"],
    [(body) => { body.usage.prompt_tokens_details.cached_tokens = body.usage.prompt_tokens + 1; }, "untrusted_provider_usage"],
    [(body) => { body.usage.completion_tokens_details = { reasoning_tokens: body.usage.completion_tokens + 1 }; }, "untrusted_provider_usage"],
  ];
  for (const [mutate, code] of cases) {
    const runtime = chutesRuntime();
    const response = await askChutes(runtime, chutesBody(mutate));
    assert.equal(response.status, 502, code);
    assert.equal((await response.json()).error.code, code);
    const { attempt, month } = await attemptState(runtime);
    assert.equal(attempt.state, "unresolved", code);
    assert.equal(month.unresolved_micro_usd, 3_139, code);
  }
});

test("a response in the other provider's shape is never read under the wrong rules", async () => {
  // An OpenAI Responses body with the Chutes model id has no prompt/completion counts.
  const runtime = chutesRuntime();
  const response = await askChutes(runtime, validProviderBody({ model: "google/gemma-4-31B-turbo-TEE" }));
  assert.equal((await response.json()).error.code, "untrusted_provider_usage");
  assert.equal((await attemptState(runtime)).attempt.state, "unresolved");
  // Specimen: the Luna profile does read that same shape once its own model id is present.
  const luna = makeRuntime();
  assert.equal((await askChutes(luna, validProviderBody())).status, 200);
  // And the Luna profile refuses a chat/completions body.
  const lunaGivenChutes = makeRuntime();
  const refused = await askChutes(lunaGivenChutes, chutesBody((body) => { body.model = "gpt-5.6-luna"; }));
  assert.equal((await refused.json()).error.code, "untrusted_provider_usage");
});

test("Chutes reasoning tokens are billed inside completion tokens, never on top", async () => {
  const profile = getModelProfile("gemma-4-31b-turbo-tee:v1");
  const usage = validateProviderUsage(chutesBody((body) => { body.usage.completion_tokens_details = { reasoning_tokens: 30 }; }), profile);
  assert.equal(usage.reasoning_tokens, 30);
  assert.equal(usage.output_tokens, 41);
  assert.equal(calculateUsageCostMicroUsd(profile, usage), 236);
});

test("Chutes provider HTTP failure is unresolved and not a model mismatch", async () => {
  const runtime = chutesRuntime();
  const response = await askChutes(runtime, { detail: "rate limited" }, 429);
  assert.equal((await response.json()).error.code, "provider_error");
  const { attempt } = await attemptState(runtime);
  assert.equal(attempt.state, "unresolved");
  assert.equal(attempt.terminal_reason, "provider_http_429");
});

test("pilot-design mode uses the same Chutes adapter with its own schema", async () => {
  const runtime = chutesRuntime();
  const answers = Object.fromEntries(["intended_decision", "requested_result", "current_baseline", "baseline_limitation", "changing_conditions", "exclusions", "consequential_error", "comparison_evidence", "access_limitations"].map((field) => [field, field === "intended_decision" ? "Choose a cold-plate design." : null]));
  const pilot = Object.fromEntries(["candidate_inputs", "candidate_outputs", "operating_envelope", "evaluation_questions", "requested_targets", "missing_evidence", "implementation_work", "bounded_first_pilot", "next_discussion"].map((field) => [field, null]));
  let sent;
  await withProvider(async (_url, options) => {
    sent = JSON.parse(options.body);
    return new Response(JSON.stringify(chutesBody((body) => {
      body.choices[0].message.content = JSON.stringify({
        message: "A bounded comparison can be drafted without promising execution.",
        next_question: null,
        proposals: [],
        unresolved_assumptions: [],
        source_ids: ["constitution-405a820b"],
        maturity_note: "Draft pilot for Carbon review.",
      });
    })), { status: 200 });
  }, async () => {
    const response = await ask(createWorker(knowledge), runtime.env, "unused", null, { body: JSON.stringify({
      mode: "PILOT_DESIGN",
      session_id: "pilot-session-1",
      question: "What is Carbon?",
      turns: [],
      draft_context: { version: "carbon.client-intake.guidance-context.v1", answers, pilot, unresolved_assumptions: [] },
    }) });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).mode, "PILOT_DESIGN");
  });
  assert.equal(sent.response_format.json_schema.name, "carbon_pilot_guidance");
  assert.equal(sent.messages[1].content.includes("draft_context"), true);
  assert.equal("store" in sent, false);
});
