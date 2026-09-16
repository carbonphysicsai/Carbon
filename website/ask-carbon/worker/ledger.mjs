const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});

const utcDay = (milliseconds) => new Date(milliseconds).toISOString().slice(0, 10);
const utcHour = (milliseconds) => new Date(milliseconds).toISOString().slice(0, 13);

export class AskCarbonUsageLedger {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    const input = await request.json().catch(() => null);
    if (!input || typeof input !== "object") return json({ error: "invalid_request" }, 400);
    if (url.pathname === "/reserve") return this.reserve(input);
    if (url.pathname === "/settle") return this.settle(input);
    if (url.pathname === "/snapshot") return this.snapshot(input);
    return json({ error: "not_found" }, 404);
  }

  async reserve(input) {
    const now = Number(input.now_ms);
    const leaseTtlMs = Number(input.lease_ttl_ms);
    const requestLimit = Number(input.request_limit);
    const costLimit = Number(input.cost_limit_micro_usd);
    const concurrencyLimit = Number(input.concurrency_limit);
    const clientRequestsPerHour = Number(input.client_requests_per_hour);
    const reservedCost = Number(input.reserved_cost_micro_usd);
    if (![now, leaseTtlMs, requestLimit, costLimit, concurrencyLimit, clientRequestsPerHour, reservedCost].every(Number.isSafeInteger) ||
        now <= 0 || leaseTtlMs <= 0 || requestLimit <= 0 || costLimit <= 0 || concurrencyLimit <= 0 || clientRequestsPerHour <= 0 || reservedCost <= 0 ||
        typeof input.lease_id !== "string" || !input.lease_id || typeof input.client_id !== "string" || !input.client_id) {
      return json({ allowed: false, reason: "invalid_reservation" }, 400);
    }
    return this.state.storage.transaction(async (transaction) => {
      const key = `day:${utcDay(now)}`;
      const current = (await transaction.get(key)) ?? { requests: 0, settled_micro_usd: 0, leases: {}, clients: {} };
      current.clients ??= {};
      for (const [leaseId, lease] of Object.entries(current.leases)) {
        if (lease.expires_at_ms <= now) delete current.leases[leaseId];
      }
      const activeLeases = Object.values(current.leases);
      const reserved = activeLeases.reduce((total, lease) => total + lease.reserved_micro_usd, 0);
      const clientWindow = activeLeases.filter((lease) => lease.client_id === input.client_id).length;
      const hour = utcHour(now);
      const clientRate = current.clients[input.client_id]?.hour === hour ? current.clients[input.client_id].requests : 0;
      let reason = null;
      if (current.requests >= requestLimit) reason = "daily_request_limit";
      else if (activeLeases.length >= concurrencyLimit) reason = "global_concurrency_limit";
      else if (clientWindow >= 2) reason = "client_concurrency_limit";
      else if (clientRate >= clientRequestsPerHour) reason = "client_hourly_limit";
      else if (current.settled_micro_usd + reserved + reservedCost > costLimit) reason = "daily_cost_limit";
      if (reason) {
        await transaction.put(key, current);
        return json({ allowed: false, reason }, 429);
      }
      current.requests += 1;
      current.clients[input.client_id] = { hour, requests: clientRate + 1 };
      current.leases[input.lease_id] = {
        client_id: input.client_id,
        reserved_micro_usd: reservedCost,
        expires_at_ms: now + leaseTtlMs,
      };
      await transaction.put(key, current);
      return json({ allowed: true, lease_id: input.lease_id, expires_at_ms: now + leaseTtlMs });
    });
  }

  async settle(input) {
    const now = Number(input.now_ms);
    const actualCost = Number(input.actual_cost_micro_usd);
    if (!Number.isSafeInteger(now) || now <= 0 || !Number.isSafeInteger(actualCost) || actualCost < 0 || typeof input.lease_id !== "string") {
      return json({ settled: false, reason: "invalid_settlement" }, 400);
    }
    return this.state.storage.transaction(async (transaction) => {
      const key = `day:${utcDay(now)}`;
      const current = (await transaction.get(key)) ?? { requests: 0, settled_micro_usd: 0, leases: {}, clients: {} };
      const lease = current.leases[input.lease_id];
      if (!lease) return json({ settled: false, reason: "lease_not_found" }, 409);
      delete current.leases[input.lease_id];
      current.settled_micro_usd += actualCost;
      await transaction.put(key, current);
      return json({ settled: true, actual_cost_micro_usd: actualCost });
    });
  }

  async snapshot(input) {
    const now = Number(input.now_ms);
    if (!Number.isSafeInteger(now) || now <= 0) return json({ error: "invalid_snapshot" }, 400);
    const key = `day:${utcDay(now)}`;
    const current = (await this.state.storage.get(key)) ?? { requests: 0, settled_micro_usd: 0, leases: {}, clients: {} };
    for (const [leaseId, lease] of Object.entries(current.leases)) {
      if (lease.expires_at_ms <= now) delete current.leases[leaseId];
    }
    return json({ ...current, active_leases: Object.keys(current.leases).length });
  }
}
