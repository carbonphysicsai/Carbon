import test from "node:test";
import assert from "node:assert/strict";
import { AskCarbonUsageLedger } from "../worker/ledger.mjs";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async transaction(callback) { return callback(this); }
}

const request = (path, body) => new Request(`https://ledger.test${path}`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

const reservation = (overrides = {}) => ({
  lease_id: "lease-1",
  client_id: "client-1",
  now_ms: Date.parse("2026-09-16T12:00:00Z"),
  lease_ttl_ms: 30_000,
  request_limit: 10,
  cost_limit_micro_usd: 10_000,
  monthly_cost_limit_micro_usd: 50_000_000,
  concurrency_limit: 2,
  client_requests_per_hour: 12,
  pilot_requests_per_session: 8,
  session_id: "session-1",
  mode: "GENERAL_QA",
  reserved_cost_micro_usd: 2_000,
  ...overrides,
});

test("ledger enforces global concurrency atomically", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  assert.equal((await ledger.fetch(request("/reserve", reservation()))).status, 200);
  assert.equal((await ledger.fetch(request("/reserve", reservation({ lease_id: "lease-2", client_id: "client-2" })))).status, 200);
  const rejected = await ledger.fetch(request("/reserve", reservation({ lease_id: "lease-3", client_id: "client-3" })));
  assert.equal(rejected.status, 429);
  assert.equal((await rejected.json()).reason, "global_concurrency_limit");
});

test("expired leases recover capacity across object restarts", async () => {
  const storage = new MemoryStorage();
  const first = new AskCarbonUsageLedger({ storage });
  await first.fetch(request("/reserve", reservation({ lease_ttl_ms: 1 })));
  const restarted = new AskCarbonUsageLedger({ storage });
  const recovered = await restarted.fetch(request("/reserve", reservation({ lease_id: "lease-2", now_ms: reservation().now_ms + 2, concurrency_limit: 1 })));
  assert.equal(recovered.status, 200);
});

test("settlement replaces reservation with actual cost and survives restart", async () => {
  const storage = new MemoryStorage();
  const first = new AskCarbonUsageLedger({ storage });
  await first.fetch(request("/reserve", reservation()));
  const settled = await first.fetch(request("/settle", { lease_id: "lease-1", actual_cost_micro_usd: 777, now_ms: reservation().now_ms }));
  assert.equal(settled.status, 200);
  const restarted = new AskCarbonUsageLedger({ storage });
  const snapshot = await restarted.fetch(request("/snapshot", { now_ms: reservation().now_ms }));
  const body = await snapshot.json();
  assert.equal(body.requests, 1);
  assert.equal(body.settled_micro_usd, 777);
  assert.equal(body.active_leases, 0);
});

test("ledger rejects a reservation that would exceed the cost ceiling", async () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  const response = await ledger.fetch(request("/reserve", reservation({ reserved_cost_micro_usd: 10_001 })));
  assert.equal(response.status, 429);
  assert.equal((await response.json()).reason, "daily_cost_limit");
});

test("ledger enforces a per-client hourly abuse ceiling in addition to global limits", async () => {
  const storage = new MemoryStorage();
  const ledger = new AskCarbonUsageLedger({ storage });
  await ledger.fetch(request("/reserve", reservation({ lease_id: "lease-1", client_requests_per_hour: 1 })));
  await ledger.fetch(request("/settle", { lease_id: "lease-1", actual_cost_micro_usd: 10, now_ms: reservation().now_ms }));
  const rejected = await ledger.fetch(request("/reserve", reservation({ lease_id: "lease-2", client_requests_per_hour: 1 })));
  assert.equal(rejected.status, 429);
  assert.equal((await rejected.json()).reason, "client_hourly_limit");
});

test("general Q&A and pilot guidance share one monthly spending ceiling", async () => {
  const storage = new MemoryStorage();
  const ledger = new AskCarbonUsageLedger({ storage });
  await ledger.fetch(request("/reserve", reservation({ lease_id: "general-1", mode: "GENERAL_QA", reserved_cost_micro_usd: 600, monthly_cost_limit_micro_usd: 1_000 })));
  await ledger.fetch(request("/settle", { lease_id: "general-1", actual_cost_micro_usd: 600, now_ms: reservation().now_ms }));
  const rejected = await ledger.fetch(request("/reserve", reservation({ lease_id: "pilot-1", mode: "PILOT_DESIGN", session_id: "pilot-session", reserved_cost_micro_usd: 401, monthly_cost_limit_micro_usd: 1_000 })));
  assert.equal(rejected.status, 429);
  assert.equal((await rejected.json()).reason, "monthly_cost_limit");
});

test("pilot guidance has a bounded per-session request count without a second budget", async () => {
  const storage = new MemoryStorage();
  const ledger = new AskCarbonUsageLedger({ storage });
  const first = reservation({ lease_id: "pilot-1", mode: "PILOT_DESIGN", pilot_requests_per_session: 1 });
  assert.equal((await ledger.fetch(request("/reserve", first))).status, 200);
  await ledger.fetch(request("/settle", { lease_id: "pilot-1", actual_cost_micro_usd: 10, now_ms: first.now_ms }));
  const rejected = await ledger.fetch(request("/reserve", reservation({ lease_id: "pilot-2", mode: "PILOT_DESIGN", pilot_requests_per_session: 1 })));
  assert.equal(rejected.status, 429);
  assert.equal((await rejected.json()).reason, "pilot_session_limit");
});
