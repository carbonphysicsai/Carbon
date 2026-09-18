const STATE_KEY = "ask-carbon-provider-budget:v2";
export const OWNER_MONTHLY_LIMIT_MICRO_USD = 50_000_000;

const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});
const monthOf = (milliseconds) => new Date(milliseconds).toISOString().slice(0, 7);
const dayOf = (milliseconds) => new Date(milliseconds).toISOString().slice(0, 10);
const hourOf = (milliseconds) => new Date(milliseconds).toISOString().slice(0, 13);
const integer = (value, { min = 0 } = {}) => Number.isSafeInteger(value) && value >= min;
const text = (value, max = 200) => typeof value === "string" && value.length > 0 && value.length <= max;

const emptyState = () => ({
  schema_version: 3,
  policy: null,
  environment_policies: {},
  scope_policies: {},
  attempts: {},
  days: {},
  environment_days: {},
  clients: {},
  pilot_sessions: {},
});

const sweep = (state, now) => {
  for (const attempt of Object.values(state.attempts)) {
    if (attempt.expires_at_ms > now) continue;
    if (attempt.state === "prepared") {
      attempt.state = "released_pre_dispatch";
      attempt.terminal_at_ms = now;
      attempt.terminal_reason = "prepared_lease_expired";
    } else if (attempt.state === "dispatch_authorized") {
      attempt.state = "unresolved";
      attempt.terminal_at_ms = now;
      attempt.terminal_reason = "dispatch_lease_expired";
    }
  }
};

const exposureFor = (attempt) => {
  if (["prepared", "dispatch_authorized", "unresolved"].includes(attempt.state)) return attempt.reserved_cost_micro_usd;
  if (["settled", "settled_overrun"].includes(attempt.state)) return attempt.actual_cost_micro_usd;
  return 0;
};

const summarize = (state) => {
  const months = {};
  const scopes = {};
  let activeAttempts = 0;
  for (const attempt of Object.values(state.attempts)) {
    const month = months[attempt.admission_period] ??= {
      prepared_micro_usd: 0,
      dispatch_authorized_micro_usd: 0,
      unresolved_micro_usd: 0,
      settled_micro_usd: 0,
      overrun_micro_usd: 0,
      exposure_micro_usd: 0,
    };
    const scopeKey = `${attempt.admission_period}:${attempt.scope_id}`;
    const scope = scopes[scopeKey] ??= { exposure_micro_usd: 0, limit_micro_usd: attempt.scope_limit_micro_usd };
    const exposure = exposureFor(attempt);
    month.exposure_micro_usd += exposure;
    scope.exposure_micro_usd += exposure;
    if (attempt.state === "prepared") month.prepared_micro_usd += attempt.reserved_cost_micro_usd;
    if (attempt.state === "dispatch_authorized") month.dispatch_authorized_micro_usd += attempt.reserved_cost_micro_usd;
    if (attempt.state === "unresolved") month.unresolved_micro_usd += attempt.reserved_cost_micro_usd;
    if (["settled", "settled_overrun"].includes(attempt.state)) month.settled_micro_usd += attempt.actual_cost_micro_usd;
    if (attempt.state === "settled_overrun") month.overrun_micro_usd += attempt.actual_cost_micro_usd - attempt.reserved_cost_micro_usd;
    if (["prepared", "dispatch_authorized"].includes(attempt.state)) activeAttempts += 1;
  }
  return { months, scopes, active_attempts: activeAttempts };
};

const load = async (storage) => {
  const state = (await storage.get(STATE_KEY)) ?? emptyState();
  if ((state.schema_version ?? 2) < 3) {
    const legacyPilotSessions = state.pilot_sessions ?? {};
    state.environment_policies = {};
    state.environment_days = {};
    state.clients = {};
    state.pilot_sessions = Object.fromEntries(Object.entries(legacyPilotSessions)
      .map(([key, value]) => [`legacy:${key}`, value]));
    for (const attempt of Object.values(state.attempts ?? {})) {
      const environment = attempt.environment;
      if (!text(environment, 40) || !integer(attempt.admitted_at_ms, { min: 1 })) continue;
      const day = dayOf(attempt.admitted_at_ms);
      const environmentDays = state.environment_days[environment] ??= {};
      const dayState = environmentDays[day] ??= { requests: 0 };
      dayState.requests += 1;
      const hour = hourOf(attempt.admitted_at_ms);
      const clientKey = `${environment}:${attempt.client_id}`;
      const clientState = state.clients[clientKey];
      if (!clientState || clientState.hour !== hour) {
        if (!clientState || clientState.hour < hour) {
          state.clients[clientKey] = { hour, requests: 1, last_seen_ms: attempt.admitted_at_ms };
        }
      } else {
        clientState.requests += 1;
        clientState.last_seen_ms = Math.max(clientState.last_seen_ms, attempt.admitted_at_ms);
      }
      if (attempt.mode === "PILOT_DESIGN" && text(attempt.session_id)) {
        const sessionKey = `${environment}:${monthOf(attempt.admitted_at_ms)}:${attempt.session_id}`;
        const session = state.pilot_sessions[sessionKey] ??= { requests: 0, last_seen_ms: attempt.admitted_at_ms };
        session.requests += 1;
        session.last_seen_ms = Math.max(session.last_seen_ms, attempt.admitted_at_ms);
      }
    }
    if (state.policy) {
      delete state.policy.daily_request_limit;
      delete state.policy.client_requests_per_hour;
      delete state.policy.pilot_requests_per_session;
      delete state.policy.client_counter_retention_ms;
    }
    state.schema_version = 3;
  }
  state.environment_policies ??= {};
  state.environment_days ??= {};
  state.scope_policies ??= {};
  state.pilot_sessions ??= {};
  return state;
};

export class AskCarbonUsageLedger {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    const input = await request.json().catch(() => null);
    if (!input || typeof input !== "object" || Array.isArray(input)) return json({ error: "invalid_request" }, 400);
    const path = new URL(request.url).pathname;
    if (path === "/prepare") return this.prepare(input);
    if (path === "/authorize-dispatch") return this.authorizeDispatch(input);
    if (path === "/release-pre-dispatch") return this.releasePreDispatch(input);
    if (path === "/mark-unresolved") return this.markUnresolved(input);
    if (path === "/settle") return this.settle(input);
    if (path === "/snapshot") return this.snapshot(input);
    return json({ error: "not_found" }, 404);
  }

  async prepare(input) {
    const requiredIntegers = [
      input.now_ms, input.lease_ttl_ms, input.monthly_limit_micro_usd,
      input.scope_limit_micro_usd, input.daily_request_limit, input.concurrency_limit,
      input.client_requests_per_hour, input.client_counter_retention_ms,
      input.pilot_requests_per_session, input.reserved_cost_micro_usd,
      input.legacy_closed_authority_exposure_micro_usd,
    ];
    if (!requiredIntegers.every((value) => integer(value, { min: 1 })) ||
        input.monthly_limit_micro_usd !== OWNER_MONTHLY_LIMIT_MICRO_USD ||
        input.scope_limit_micro_usd > OWNER_MONTHLY_LIMIT_MICRO_USD ||
        input.legacy_closed_authority_exposure_micro_usd > OWNER_MONTHLY_LIMIT_MICRO_USD ||
        !/^\d{4}-\d{2}$/.test(input.legacy_closed_authority_period ?? "") ||
        !text(input.legacy_closed_authority_scope_id, 100) ||
        !text(input.attempt_id) || !text(input.client_id) || !text(input.session_id) ||
        !["GENERAL_QA", "PILOT_DESIGN"].includes(input.mode) || !text(input.environment, 40) ||
        !text(input.scope_id, 100) || !text(input.model_config_id) || !text(input.pricing_id)) {
      return json({ allowed: false, reason: "invalid_admission" }, 400);
    }
    return this.state.storage.transaction(async (transaction) => {
      const state = await load(transaction);
      sweep(state, input.now_ms);
      if (state.attempts[input.attempt_id]) {
        await transaction.put(STATE_KEY, state);
        return json({ allowed: false, reason: "duplicate_attempt_id" }, 409);
      }
      if (state.policy && state.policy.legacy_closed_authority_period === undefined) {
        state.policy.legacy_closed_authority_period = input.legacy_closed_authority_period;
        state.policy.legacy_closed_authority_scope_id = input.legacy_closed_authority_scope_id;
        state.policy.legacy_closed_authority_exposure_micro_usd = input.legacy_closed_authority_exposure_micro_usd;
      }
      if (state.policy && (
        state.policy.concurrency_limit !== input.concurrency_limit ||
        state.policy.legacy_closed_authority_period !== input.legacy_closed_authority_period ||
        state.policy.legacy_closed_authority_scope_id !== input.legacy_closed_authority_scope_id ||
        state.policy.legacy_closed_authority_exposure_micro_usd !== input.legacy_closed_authority_exposure_micro_usd
      )) {
        return json({ allowed: false, reason: "ledger_policy_mismatch" }, 409);
      }
      state.policy ??= {
        monthly_limit_micro_usd: OWNER_MONTHLY_LIMIT_MICRO_USD,
        concurrency_limit: input.concurrency_limit,
        legacy_closed_authority_period: input.legacy_closed_authority_period,
        legacy_closed_authority_scope_id: input.legacy_closed_authority_scope_id,
        legacy_closed_authority_exposure_micro_usd: input.legacy_closed_authority_exposure_micro_usd,
      };
      const existingEnvironmentPolicy = state.environment_policies[input.environment];
      const requestedEnvironmentPolicy = {
        daily_request_limit: input.daily_request_limit,
        client_requests_per_hour: input.client_requests_per_hour,
        pilot_requests_per_session: input.pilot_requests_per_session,
        client_counter_retention_ms: input.client_counter_retention_ms,
      };
      if (existingEnvironmentPolicy && Object.entries(requestedEnvironmentPolicy)
        .some(([key, value]) => existingEnvironmentPolicy[key] !== value)) {
        return json({ allowed: false, reason: "environment_policy_mismatch" }, 409);
      }
      state.environment_policies[input.environment] ??= {
        ...requestedEnvironmentPolicy,
        created_at_ms: input.now_ms,
      };
      const environmentPolicy = state.environment_policies[input.environment];
      const existingScopePolicy = state.scope_policies[input.scope_id];
      if (existingScopePolicy && existingScopePolicy.limit_micro_usd !== input.scope_limit_micro_usd) {
        return json({ allowed: false, reason: "scope_policy_mismatch" }, 409);
      }
      state.scope_policies[input.scope_id] ??= {
        limit_micro_usd: input.scope_limit_micro_usd,
        first_environment: input.environment,
        created_at_ms: input.now_ms,
      };
      const cutoff = input.now_ms - environmentPolicy.client_counter_retention_ms;
      for (const [clientId, counter] of Object.entries(state.clients)) {
        if (counter.last_seen_ms < cutoff) delete state.clients[clientId];
      }
      const day = dayOf(input.now_ms);
      const dayState = state.days[day] ??= { requests: 0 };
      const environmentDays = state.environment_days[input.environment] ??= {};
      const environmentDayState = environmentDays[day] ??= { requests: 0 };
      const clientHour = hourOf(input.now_ms);
      const clientKey = `${input.environment}:${input.client_id}`;
      const clientState = state.clients[clientKey];
      const clientRequests = clientState?.hour === clientHour ? clientState.requests : 0;
      const summary = summarize(state);
      const period = monthOf(input.now_ms);
      const pilotSessionKey = `${input.environment}:${period}:${input.session_id}`;
      const legacyPilotSessionKey = `legacy:${period}:${input.session_id}`;
      const currentPilotSessionRequests = state.pilot_sessions[pilotSessionKey]?.requests ?? 0;
      const pilotSessionRequests = currentPilotSessionRequests +
        (state.pilot_sessions[legacyPilotSessionKey]?.requests ?? 0);
      const monthExposure = summary.months[period]?.exposure_micro_usd ?? 0;
      const scopeKey = `${period}:${input.scope_id}`;
      const scopeExposure = summary.scopes[scopeKey]?.exposure_micro_usd ?? 0;
      const legacyExposure = period === state.policy.legacy_closed_authority_period
        ? state.policy.legacy_closed_authority_exposure_micro_usd
        : 0;
      const legacyScopeExposure = legacyExposure && input.scope_id === state.policy.legacy_closed_authority_scope_id
        ? legacyExposure
        : 0;
      const clientActive = Object.values(state.attempts).filter((attempt) =>
        attempt.client_id === input.client_id && ["prepared", "dispatch_authorized"].includes(attempt.state)).length;
      let reason = null;
      if (environmentDayState.requests >= environmentPolicy.daily_request_limit) reason = "daily_request_limit";
      else if (summary.active_attempts >= state.policy.concurrency_limit) reason = "global_concurrency_limit";
      else if (clientActive >= 2) reason = "client_concurrency_limit";
      else if (clientRequests >= environmentPolicy.client_requests_per_hour) reason = "client_hourly_limit";
      else if (input.mode === "PILOT_DESIGN" && pilotSessionRequests >= environmentPolicy.pilot_requests_per_session) reason = "pilot_session_limit";
      else if (monthExposure + legacyExposure + input.reserved_cost_micro_usd > OWNER_MONTHLY_LIMIT_MICRO_USD) reason = "monthly_cost_limit";
      else if (scopeExposure + legacyScopeExposure + input.reserved_cost_micro_usd > (existingScopePolicy?.limit_micro_usd ?? state.scope_policies[input.scope_id].limit_micro_usd)) reason = "scope_cost_limit";
      if (reason) {
        await transaction.put(STATE_KEY, state);
        return json({ allowed: false, reason }, 429);
      }
      dayState.requests += 1;
      environmentDayState.requests += 1;
      state.clients[clientKey] = { hour: clientHour, requests: clientRequests + 1, last_seen_ms: input.now_ms };
      if (input.mode === "PILOT_DESIGN") state.pilot_sessions[pilotSessionKey] = { requests: currentPilotSessionRequests + 1, last_seen_ms: input.now_ms };
      state.attempts[input.attempt_id] = {
        attempt_id: input.attempt_id,
        client_id: input.client_id,
        session_id: input.session_id,
        mode: input.mode,
        environment: input.environment,
        scope_id: input.scope_id,
        admission_period: period,
        admitted_at_ms: input.now_ms,
        expires_at_ms: input.now_ms + input.lease_ttl_ms,
        reserved_cost_micro_usd: input.reserved_cost_micro_usd,
        scope_limit_micro_usd: input.scope_limit_micro_usd,
        model_config_id: input.model_config_id,
        pricing_id: input.pricing_id,
        state: "prepared",
      };
      await transaction.put(STATE_KEY, state);
      return json({
        allowed: true,
        attempt_id: input.attempt_id,
        admission_period: period,
        expires_at_ms: input.now_ms + input.lease_ttl_ms,
        monthly_remaining_micro_usd: OWNER_MONTHLY_LIMIT_MICRO_USD - monthExposure - legacyExposure - input.reserved_cost_micro_usd,
      });
    });
  }

  async transition(input, transition) {
    if (!integer(input.now_ms, { min: 1 }) || !text(input.attempt_id)) return json({ ok: false, reason: "invalid_transition" }, 400);
    return this.state.storage.transaction(async (transaction) => {
      const state = await load(transaction);
      sweep(state, input.now_ms);
      const attempt = state.attempts[input.attempt_id];
      const result = transition(attempt, state);
      await transaction.put(STATE_KEY, state);
      return json(result.body, result.status);
    });
  }

  authorizeDispatch(input) {
    return this.transition(input, (attempt) => {
      if (!attempt) return { status: 409, body: { authorized: false, reason: "attempt_not_found" } };
      if (attempt.state === "dispatch_authorized") return { status: 200, body: { authorized: true, idempotent: true } };
      if (attempt.state !== "prepared") return { status: 409, body: { authorized: false, reason: "attempt_not_prepared" } };
      attempt.state = "dispatch_authorized";
      attempt.dispatch_authorized_at_ms = input.now_ms;
      return { status: 200, body: { authorized: true, attempt_id: attempt.attempt_id, admission_period: attempt.admission_period } };
    });
  }

  releasePreDispatch(input) {
    if (!text(input.reason, 100)) return Promise.resolve(json({ released: false, reason: "invalid_release" }, 400));
    return this.transition(input, (attempt) => {
      if (!attempt) return { status: 409, body: { released: false, reason: "attempt_not_found" } };
      if (attempt.state === "released_pre_dispatch") return { status: 200, body: { released: true, idempotent: true } };
      if (attempt.state !== "prepared") return { status: 409, body: { released: false, reason: "dispatch_may_have_occurred" } };
      attempt.state = "released_pre_dispatch";
      attempt.terminal_at_ms = input.now_ms;
      attempt.terminal_reason = input.reason;
      return { status: 200, body: { released: true } };
    });
  }

  markUnresolved(input) {
    if (!text(input.reason, 100)) return Promise.resolve(json({ marked: false, reason: "invalid_unresolved" }, 400));
    return this.transition(input, (attempt) => {
      if (!attempt) return { status: 409, body: { marked: false, reason: "attempt_not_found" } };
      if (attempt.state === "unresolved") return { status: 200, body: { marked: true, idempotent: true } };
      if (attempt.state !== "dispatch_authorized") return { status: 409, body: { marked: false, reason: "dispatch_not_authorized" } };
      attempt.state = "unresolved";
      attempt.terminal_at_ms = input.now_ms;
      attempt.terminal_reason = input.reason;
      return { status: 200, body: { marked: true, conservative_charge_micro_usd: attempt.reserved_cost_micro_usd } };
    });
  }

  async settle(input) {
    if (!integer(input.now_ms, { min: 1 }) || !integer(input.actual_cost_micro_usd) ||
        !text(input.attempt_id) || !text(input.settlement_id) || !text(input.provider_response_id)) {
      return json({ settled: false, reason: "invalid_settlement" }, 400);
    }
    return this.state.storage.transaction(async (transaction) => {
      const state = await load(transaction);
      sweep(state, input.now_ms);
      const attempt = state.attempts[input.attempt_id];
      if (!attempt) return json({ settled: false, reason: "attempt_not_found" }, 409);
      if (["settled", "settled_overrun"].includes(attempt.state)) {
        const same = attempt.settlement_id === input.settlement_id &&
          attempt.provider_response_id === input.provider_response_id &&
          attempt.actual_cost_micro_usd === input.actual_cost_micro_usd;
        return json(same ? { settled: true, idempotent: true, actual_cost_micro_usd: attempt.actual_cost_micro_usd } :
          { settled: false, reason: "conflicting_settlement" }, same ? 200 : 409);
      }
      if (!["dispatch_authorized", "unresolved"].includes(attempt.state)) {
        return json({ settled: false, reason: "dispatch_not_authorized" }, 409);
      }
      attempt.actual_cost_micro_usd = input.actual_cost_micro_usd;
      attempt.settlement_id = input.settlement_id;
      attempt.provider_response_id = input.provider_response_id;
      attempt.terminal_at_ms = input.now_ms;
      const overrun = input.actual_cost_micro_usd > attempt.reserved_cost_micro_usd;
      attempt.state = overrun ? "settled_overrun" : "settled";
      attempt.terminal_reason = overrun ? "reservation_overrun" : "provider_usage_settled";
      await transaction.put(STATE_KEY, state);
      return json(overrun ? {
        settled: false,
        reason: "reservation_overrun_recorded",
        actual_cost_micro_usd: input.actual_cost_micro_usd,
      } : { settled: true, actual_cost_micro_usd: input.actual_cost_micro_usd }, overrun ? 409 : 200);
    });
  }

  async snapshot(input) {
    if (!integer(input.now_ms, { min: 1 })) return json({ error: "invalid_snapshot" }, 400);
    return this.state.storage.transaction(async (transaction) => {
      const state = await load(transaction);
      sweep(state, input.now_ms);
      await transaction.put(STATE_KEY, state);
      return json({
        schema_version: state.schema_version,
        policy: state.policy,
        environment_policies: state.environment_policies,
        attempts: state.attempts,
        days: state.days,
        environment_days: state.environment_days,
        clients: state.clients,
        pilot_sessions: state.pilot_sessions,
        scope_policies: state.scope_policies,
        ...summarize(state),
      });
    });
  }
}
