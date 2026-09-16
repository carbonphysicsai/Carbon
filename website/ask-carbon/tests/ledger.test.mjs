import test from "node:test";
import assert from "node:assert/strict";
import { AskCarbonUsageLedger } from "../worker/ledger.mjs";

class MemoryStorage {
  constructor(values) { this.values = values ?? new Map(); }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async transaction(callback) { return callback(this); }
}

class SerializedStorage extends MemoryStorage {
  constructor(values) { super(values); this.tail = Promise.resolve(); }
  transaction(callback) {
    const run = this.tail.then(() => callback(this));
    this.tail = run.catch(() => {});
    return run;
  }
}

const post = (path, value) => new Request(`https://ledger.test${path}`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(value),
});
const JAN = Date.parse("2026-01-31T23:59:59Z");
const MONTHLY_LIMIT = 50_000_000;
const admission = (overrides = {}) => ({
  attempt_id: "attempt-1", client_id: "client-1", environment: "staging", scope_id: "staging",
  now_ms: JAN, lease_ttl_ms: 30_000, monthly_limit_micro_usd: MONTHLY_LIMIT,
  scope_limit_micro_usd: MONTHLY_LIMIT, daily_request_limit: 100, concurrency_limit: 2,
  client_requests_per_hour: 12, client_counter_retention_ms: 86_400_000,
  reserved_cost_micro_usd: 2_000, model_config_id: "gpt-5.6-luna:low:v1",
  pricing_id: "openai-standard-2026-09-16:gpt-5.6-luna", ...overrides,
});
const body = async (ledger, path, value) => {
  const response = await ledger.fetch(post(path, value));
  return { status: response.status, value: await response.json() };
};
const prepare = (ledger, value = admission()) => body(ledger, "/prepare", value);
const authorize = (ledger, attemptId, nowMs = JAN) => body(ledger, "/authorize-dispatch", { attempt_id: attemptId, now_ms: nowMs });
const settle = (ledger, attemptId, cost, settlementId = `settlement-${attemptId}`, nowMs = JAN) => body(ledger, "/settle", {
  attempt_id: attemptId, now_ms: nowMs, actual_cost_micro_usd: cost,
  settlement_id: settlementId, provider_response_id: `response-${attemptId}`,
});
const snapshot = (ledger, nowMs = JAN) => body(ledger, "/snapshot", { now_ms: nowMs });

test("crash after dispatch retains conservative monthly exposure across expiry and restart", async () => {
  const storage = new MemoryStorage();
  const first = new AskCarbonUsageLedger({ storage });
  const admittedAt = Date.parse("2026-01-15T12:00:00Z");
  assert.equal((await prepare(first, admission({ now_ms: admittedAt, reserved_cost_micro_usd: 30_000_000 }))).status, 200);
  assert.equal((await authorize(first, "attempt-1", admittedAt)).status, 200);
  const restarted = new AskCarbonUsageLedger({ storage });
  const later = admittedAt + 30_001;
  const denied = await prepare(restarted, admission({ attempt_id: "attempt-2", client_id: "client-2", now_ms: later, reserved_cost_micro_usd: 21_000_000 }));
  assert.equal(denied.status, 429);
  assert.equal(denied.value.reason, "monthly_cost_limit");
  const state = await snapshot(restarted, later);
  assert.equal(state.value.months["2026-01"].unresolved_micro_usd, 30_000_000);
  assert.equal(state.value.active_attempts, 0);
});

test("prepared expiry releases cost while retaining request and abuse accounting", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger, admission({ lease_ttl_ms: 1, reserved_cost_micro_usd: 49_000_000 }));
  const later = JAN + 2;
  assert.equal((await prepare(ledger, admission({ attempt_id: "attempt-2", now_ms: later, reserved_cost_micro_usd: 49_000_000 }))).status, 200);
  const state = await snapshot(ledger, later);
  assert.equal(state.value.days["2026-01-31"].requests, 2);
  assert.equal(state.value.attempts["attempt-1"].state, "released_pre_dispatch");
});

test("confirmed pre-dispatch failure releases cost but duplicate IDs never overwrite attempts", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger);
  assert.equal((await body(ledger, "/release-pre-dispatch", { attempt_id: "attempt-1", now_ms: JAN, reason: "context_too_large" })).status, 200);
  const duplicate = await prepare(ledger, admission({ reserved_cost_micro_usd: 1 }));
  assert.equal(duplicate.status, 409);
  assert.equal(duplicate.value.reason, "duplicate_attempt_id");
  const state = await snapshot(ledger);
  assert.equal(state.value.months["2026-01"].exposure_micro_usd, 0);
  assert.equal(state.value.attempts["attempt-1"].reserved_cost_micro_usd, 2_000);
});

test("global concurrency does not reset at UTC day or month rollover", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger, admission({ concurrency_limit: 1 }));
  await authorize(ledger, "attempt-1");
  const denied = await prepare(ledger, admission({ attempt_id: "attempt-2", client_id: "client-2", now_ms: JAN + 1_000, concurrency_limit: 1 }));
  assert.equal(new Date(JAN + 1_000).toISOString(), "2026-02-01T00:00:00.000Z");
  assert.equal(denied.status, 429);
  assert.equal(denied.value.reason, "global_concurrency_limit");
});

test("multiple environments coordinate one shared monthly and evaluation sub-budget", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger, admission({ environment: "evaluation", scope_id: "bakeoff", scope_limit_micro_usd: 5_000_000, reserved_cost_micro_usd: 3_000_000 }));
  await authorize(ledger, "attempt-1");
  await settle(ledger, "attempt-1", 3_000_000);
  const evaluationDenied = await prepare(ledger, admission({ attempt_id: "attempt-2", client_id: "client-2", environment: "evaluation", scope_id: "bakeoff", scope_limit_micro_usd: 5_000_000, reserved_cost_micro_usd: 2_000_001 }));
  assert.equal(evaluationDenied.value.reason, "scope_cost_limit");
  const stagingAllowed = await prepare(ledger, admission({ attempt_id: "attempt-3", client_id: "client-3", environment: "staging", scope_id: "staging", reserved_cost_micro_usd: 47_000_000 }));
  assert.equal(stagingAllowed.status, 200);
  const monthlyDenied = await prepare(ledger, admission({ attempt_id: "attempt-4", client_id: "client-4", environment: "production", scope_id: "production", reserved_cost_micro_usd: 1 }));
  assert.equal(monthlyDenied.value.reason, "monthly_cost_limit");
});

test("a durable scope cap cannot be raised by a later environment or restart", async () => {
  const storage = new MemoryStorage();
  const first = new AskCarbonUsageLedger({ storage });
  await prepare(first, admission({ environment: "evaluation", scope_id: "bakeoff", scope_limit_micro_usd: 5_000_000 }));
  const restarted = new AskCarbonUsageLedger({ storage });
  const raised = await prepare(restarted, admission({ attempt_id: "attempt-2", client_id: "client-2", environment: "staging", scope_id: "bakeoff", scope_limit_micro_usd: 50_000_000 }));
  assert.equal(raised.status, 409);
  assert.equal(raised.value.reason, "scope_policy_mismatch");
  const state = await snapshot(restarted);
  assert.equal(state.value.scope_policies.bakeoff.limit_micro_usd, 5_000_000);
});

test("exact monthly boundary is admitted and one micro-dollar over is rejected", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  assert.equal((await prepare(ledger, admission({ reserved_cost_micro_usd: MONTHLY_LIMIT }))).status, 200);
  assert.equal((await authorize(ledger, "attempt-1")).status, 200);
  const denied = await prepare(ledger, admission({ attempt_id: "attempt-2", client_id: "client-2", reserved_cost_micro_usd: 1 }));
  assert.equal(denied.status, 429);
  assert.equal(denied.value.reason, "monthly_cost_limit");
});

test("concurrent admissions serialize at the exact monthly boundary", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new SerializedStorage() });
  const results = await Promise.all(Array.from({ length: 11 }, (_, index) => prepare(ledger, admission({
    attempt_id: `concurrent-${index}`,
    client_id: `concurrent-client-${index}`,
    reserved_cost_micro_usd: 5_000_000,
    concurrency_limit: 100,
    client_requests_per_hour: 100,
  }))));
  assert.equal(results.filter((result) => result.status === 200).length, 10);
  assert.equal(results.filter((result) => result.value.reason === "monthly_cost_limit").length, 1);
  const state = await snapshot(ledger);
  assert.equal(state.value.months["2026-01"].exposure_micro_usd, MONTHLY_LIMIT);
});

test("late settlement replaces unresolved charge idempotently without double refund", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger, admission({ lease_ttl_ms: 1, reserved_cost_micro_usd: 5_000 }));
  await authorize(ledger, "attempt-1");
  await snapshot(ledger, JAN + 2);
  assert.equal((await settle(ledger, "attempt-1", 777, "stable-settlement", JAN + 3)).status, 200);
  const repeated = await settle(ledger, "attempt-1", 777, "stable-settlement", JAN + 4);
  assert.equal(repeated.status, 200);
  assert.equal(repeated.value.idempotent, true);
  assert.equal((await settle(ledger, "attempt-1", 778, "other-settlement", JAN + 5)).status, 409);
  const state = await snapshot(ledger, JAN + 6);
  assert.equal(state.value.months["2026-01"].settled_micro_usd, 777);
  assert.equal(state.value.months["2026-01"].unresolved_micro_usd, 0);
});

test("negative cost is rejected and over-reservation settlement is charged and flagged", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  await prepare(ledger);
  await authorize(ledger, "attempt-1");
  assert.equal((await settle(ledger, "attempt-1", -1)).status, 400);
  const overrun = await settle(ledger, "attempt-1", 2_001);
  assert.equal(overrun.status, 409);
  assert.equal(overrun.value.reason, "reservation_overrun_recorded");
  const state = await snapshot(ledger);
  assert.equal(state.value.months["2026-01"].settled_micro_usd, 2_001);
  assert.equal(state.value.attempts["attempt-1"].state, "settled_overrun");
});

test("generated event sequences never admit exposure above the owner ceiling", async () => {
  for (let seed = 1; seed <= 20; seed += 1) {
    const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
    let random = seed;
    const next = () => ((random = (random * 48_271) % 2_147_483_647) / 2_147_483_647);
    for (let index = 0; index < 80; index += 1) {
      const attemptId = `s${seed}-${index}`;
      const cost = 1 + Math.floor(next() * 2_000_000);
      const now = Date.parse("2026-04-01T00:00:00Z") + index * 1_000;
      const admitted = await prepare(ledger, admission({ attempt_id: attemptId, client_id: `client-${index % 7}`, now_ms: now, reserved_cost_micro_usd: cost, concurrency_limit: 100, client_requests_per_hour: 100 }));
      if (admitted.status === 200) {
        if (next() < 0.2) await body(ledger, "/release-pre-dispatch", { attempt_id: attemptId, now_ms: now, reason: "generated_pre_dispatch" });
        else {
          await authorize(ledger, attemptId, now);
          if (next() < 0.7) await settle(ledger, attemptId, Math.floor(cost * next()), `settle-${attemptId}`, now);
        }
      }
      const state = await snapshot(ledger, now);
      for (const month of Object.values(state.value.months)) assert.ok(month.exposure_micro_usd <= MONTHLY_LIMIT || month.overrun_micro_usd > 0);
    }
  }
});
