import test from "node:test";
import assert from "node:assert/strict";
import worker, { AskCarbonUsageLedger, createWorker } from "../worker/index.mjs";
import { answerSchema, pilotAnswerSchema, validatePilotProviderOutput } from "../worker/core.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

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
    answer: "Carbon discovers and independently tests methods for constructing fast physical models.",
    claims: [{ text: "Carbon discovers and independently tests methods for constructing fast physical models.", evidence_ids: ["overview-purpose"] }],
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
  assert.equal(body.schema_version, 2);
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
  assert.ok(providerRequest.body.text.format.schema.properties.claims.items.properties.evidence_ids.items.enum.includes("overview-purpose"));
  assert.equal(providerRequest.body.store, false);
  assert.equal("tools" in providerRequest.body, false);
  assert.equal(providerRequest.body.instructions.includes("Signed"), false);
  const snapshot = await runtime.ledger.fetch(new Request("https://ledger.test/snapshot", { method: "POST", body: JSON.stringify({ now_ms: Date.now() }) }));
  const state = await snapshot.json();
  assert.equal(Object.values(state.attempts)[0].state, "settled");
  assert.equal(state.months[new Date().toISOString().slice(0, 7)].settled_micro_usd, 80);
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
    requests.push(JSON.parse(options.body));
    const first = requests.length === 1;
    return new Response(JSON.stringify(validProviderBody({
      id: `resp-${requests.length}`,
      output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify(first ? {
        status: "supported",
        answer: "The validator supplies training randomness. Miners cannot provide official seeds.",
        claims: [
          { text: "The validator supplies training randomness.", evidence_ids: ["training-randomness"] },
          { text: "Miners cannot provide official seeds.", evidence_ids: ["training-randomness"] }
        ],
        follow_up: "What training choices are permitted?"
      } : {
        status: "supported",
        answer: "Only registered schedules, curricula and approved augmentations can modify training conditions.",
        claims: [{ text: "Only registered schedules, curricula and approved augmentations can modify training conditions.", evidence_ids: ["training-bounds"] }],
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
