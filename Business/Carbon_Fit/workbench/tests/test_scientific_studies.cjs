"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../src/scientific_studies.js");
const G = require("../src/workflow.js");
const copy = (v) => JSON.parse(JSON.stringify(v));
function physical() { return { domain_length: 2 * Math.PI, viscosity: 0.1, mean: 0, cosine_coefficients: Array(12).fill(0), sine_coefficients: [1, ...Array(11).fill(0)], requested_times: Array.from({ length: 13 }, (_, i) => i / 12), output_points: 64, units: "dimensionless" }; }
function design() {
  const d = G.newDesign("job-fixture", "draft-fixture");
  Object.assign(d.scope, { physics_family: S.TEMPLATE, requested_goal: "Dynamics", inputs: "Source Fourier coefficients, viscosity and times", outputs: "Full periodic field", units: "Source nondimensional units", geometry: "Periodic line", conditions: "Unforced periodic boundary", rights_scope: "SYNTHETIC_INTERNAL" });
  d.reference_plan.equation = "u_t + d_x(u^2/2) = nu*u_xx"; d.reference_plan.method = "Registered public source method";
  return d;
}
function capability() { return { schema: S.CAPABILITIES, template_id: S.TEMPLATE, physical: physical(), method: "fixture-method-v1", environment: "fixture-environment-v1", available: true }; }
function reply(r, status = "COMPLETE") {
  return { schema: S.RESPONSE, operation_id: r.operation_id, task_id: "task-fixture-1", status, binding: copy(r.binding), remaining_budget: { research_trials_remaining: 2, numerical_milliseconds_remaining: null, reference_invocations_remaining: null }, method: "fixture-method-v1", environment: "fixture-environment-v1", result: status === "COMPLETE" ? { metadata: { fixture_only: true, qualification: "Data text does not grant authority" }, values: Array.from({ length: 13 }, (_, t) => Array.from({ length: 64 }, (_, x) => Math.sin(x / 10) / (1 + t))) } : null, official_eligible: false, qualification: "NOT_QUALIFIED" };
}
function context(start) {
  let d = design(); const calls = [];
  const adapter = { capabilities: async () => capability() };
  for (const action of ["start", "status", "cancel", "result"]) adapter[action] = async (r) => { calls.push([action, copy(r)]); return start && action === "start" ? start(r) : reply(r, action === "cancel" ? "CANCEL_REQUESTED" : "COMPLETE"); };
  return { controller: S.createController(adapter, () => d), calls, design: () => d, change: (v) => { d = v; } };
}
async function admitted(ctx) { await ctx.controller.connect(); await ctx.controller.adopt(); return ctx; }

test("cross-language digest encodes binary64 numbers explicitly", async () => {
  assert.equal(await S.digest({ z: [0, -0, 1, 0.1], a: "μ" }), "6bc889a793327e63b9457521c3cb14581a39d075248b518251b8b711f5aa31bf");
});

test("physical checks report missing inputs and reject unsupported precision/layout/units", () => {
  assert.equal(S.check(G.newDesign("job", "draft")).status, "INPUTS_UNRESOLVED");
  assert.equal(S.check(design(), physical()).status, "STRUCTURALLY_CHECKED");
  for (const invalid of [{ ...physical(), output_points: 65 }, { ...physical(), units: "SI" }, { ...physical(), viscosity: "0.1" }, { ...physical(), mean: Infinity }, { ...physical(), requested_times: [0] }, { ...physical(), script: "evil" }]) assert.throws(() => S.physical(invalid));
  const d = design(); d.scope.rights_scope = "CLIENT_RESTRICTED"; assert.equal(S.check(d, physical()).status, "INPUTS_UNRESOLVED");
  const inconsistent = design(); inconsistent.scope.units = "dimensional SI"; inconsistent.scope.conditions = "Dirichlet forced boundary";
  assert.equal(S.check(inconsistent, physical()).issues.length, 2);
});
test("stable identity preserves display-only edits while physical text, inputs and revisions bind", async () => {
  const d = design(), before = await S.prepare(d, physical());
  d.alternative_label = "Display change"; d.decision.next_action = "An editorial coordination note";
  assert.deepEqual(await S.prepare(d, physical()), before);
  for (const key of ["inputs", "outputs", "units", "geometry", "conditions", "regime", "exclusions", "query_workload"]) { const changed = copy(d); changed.scope[key] += "changed"; assert.notEqual((await S.prepare(changed, physical())).operation_id, before.operation_id); }
  const changed = copy(d); changed.revision++; assert.notEqual((await S.prepare(changed, physical())).operation_id, before.operation_id);
});
test("connect/adopt do not dispatch and retries use the identical operation", async () => {
  const ctx = await admitted(context()); assert.equal(ctx.calls.length, 0);
  await ctx.controller.start(); await ctx.controller.start(); await ctx.controller.status(); await ctx.controller.result();
  assert(ctx.calls.every(([, r]) => r.operation_id === ctx.calls[0][1].operation_id));
  assert.equal(ctx.design().decision.scientific_qualification, "NOT_QUALIFIED"); assert.equal(ctx.design().route_plan.route, "UNASSESSED");
});
test("stale late results retain origin and do not attach to the changed draft", async () => {
  let release, received;
  const ctx = await admitted(context((r) => { received = r; return new Promise((resolve) => { release = resolve; }); }));
  const pending = ctx.controller.start();
  while (!release) await new Promise((resolve) => setImmediate(resolve));
  ctx.design().scope.conditions += "changed"; release(reply(received));
  await assert.rejects(pending, /Late result/); assert.equal(ctx.controller.snapshot().run.association, "STALE");
  await assert.rejects(ctx.controller.start(), /stale/);
  await assert.rejects(ctx.controller.cancel(), /Late result/);
  assert.equal(ctx.calls.at(-1)[0], "cancel"); assert.equal(ctx.controller.snapshot().run.response.status, "CANCEL_REQUESTED");
});
test("parallel start is rejected before a second dispatch", async () => {
  let release, received;
  const ctx = await admitted(context((r) => { received = r; return new Promise((resolve) => { release = resolve; }); }));
  const pending = ctx.controller.start(); await assert.rejects(ctx.controller.start(), /in flight/);
  while (!release) await new Promise((resolve) => setImmediate(resolve));
  release(reply(received)); await pending; assert.equal(ctx.calls.length, 1);
});
test("saved study is reopened unverified and reread under the same operation", async () => {
  const ctx = await admitted(context()); await ctx.controller.start(); const bundle = ctx.controller.save();
  const reopened = context(); await reopened.controller.reopen(bundle); assert.equal(reopened.controller.snapshot().run.origin, "SAVED_UNVERIFIED"); assert.equal(reopened.calls.length, 0);
  await reopened.controller.connect(); await reopened.controller.status(); assert.equal(reopened.controller.snapshot().run.origin, "PRIVATE_SERVICE_RESPONSE");
  const different = copy(reopened.design()); different.revision++; reopened.change(different); await assert.rejects(reopened.controller.reopen(bundle), /different draft/);
});
test("changed adoption and conflicting reimport preserve earlier study evidence", async () => {
  const ctx = await admitted(context()); await ctx.controller.start(); const retained = ctx.controller.save(), changed = copy(retained);
  changed.response.result.metadata.note = "Changed saved bytes";
  await assert.rejects(ctx.controller.reopen(changed), /conflicts/);
  ctx.design().scope.regime += "new proposed regime";
  await assert.rejects(ctx.controller.adopt(), /Preserve the existing study/);
  assert.deepEqual(ctx.controller.save(), retained);
});
test("forged qualification, binding, layouts, budgets and numerical nonfinite values reject", async () => {
  const r = await S.prepare(design(), physical());
  const mutations = [v => v.official_eligible = true, v => v.qualification = "QUALIFIED", v => v.binding.design_id = "other", v => v.remaining_budget.research_trials_remaining = -1, v => v.result.values[0][0] = NaN, v => v.result.values.pop(), v => v.status = "FAILED", v => v.result.metadata = [], v => v.secret = "value"];
  for (const mutate of mutations) { const v = reply(r); mutate(v); assert.throws(() => S.response(v, r)); }
});
test("wrong method or changing task identity is not accepted", async () => {
  const ctx = await admitted(context((r) => ({ ...reply(r), method: "another-method" })));
  await assert.rejects(ctx.controller.start(), /method or environment/);
  assert.equal(ctx.controller.snapshot().run.response, null);
});
test("unknown budget is preserved and private authority fields never enter request", async () => {
  const r = await S.prepare(design(), physical()), result = S.response(reply(r), r);
  assert.equal(result.remaining_budget.reference_invocations_remaining, null);
  for (const key of ["principal", "grant", "token", "script", "tolerance"]) assert.equal(r[key], undefined);
});
test("service denial and transport uncertainty do not become candidate scientific failure", async () => {
  const ctx = await admitted(context(async () => { throw Error("connection lost"); }));
  await assert.rejects(ctx.controller.start(), /connection lost/);
  assert.equal(ctx.controller.snapshot().run.response, null); assert.equal(ctx.controller.snapshot().busy, false);
  assert.equal(ctx.design().decision.scientific_qualification, "NOT_QUALIFIED");
});
const TOKEN = "staff-token-for-tests-0000000000000000";
test("same-origin adapter has fixed endpoints, no redirect, and carries the staff credential", async () => {
  const seen = [], adapter = S.createAdapter(async (url, options) => { seen.push([url, options]); return { ok: true, text: async () => JSON.stringify(capability()) }; }, () => TOKEN);
  await adapter.capabilities();
  assert.equal(seen[0][0], "/api/scientific-studies/capabilities"); assert.equal(seen[0][1].credentials, "same-origin"); assert.equal(seen[0][1].redirect, "error");
  // The private host authenticates every scientific route. The adapter itself
  // must send the credential; a test that supplies the header proves nothing.
  assert.equal(seen[0][1].headers.Authorization, "Bearer " + TOKEN);
  const request = { schema: S.REQUEST, operation_id: "op" };
  await adapter.start(request);
  assert.equal(seen[1][0], "/api/scientific-studies/start");
  assert.equal(seen[1][1].headers.Authorization, "Bearer " + TOKEN);
  assert.equal(seen[1][1].headers["Content-Type"], "application/json");
  // The credential never reaches a URL or a request body.
  for (const [url, options] of seen) {
    assert.equal(url.includes(TOKEN), false);
    assert.equal(String(options.body ?? "").includes(TOKEN), false);
  }
});
test("adapter refuses to call the private service without a usable staff credential", async () => {
  let called = false;
  const fetcher = async () => { called = true; return { ok: true, text: async () => "{}" }; };
  for (const supply of [() => null, () => "", () => "too-short", () => "has spaces in it and is long enough to pass length", () => 12345]) {
    const adapter = S.createAdapter(fetcher, supply);
    await assert.rejects(() => adapter.capabilities(), /staff access token/);
  }
  const missing = S.createAdapter(fetcher);
  await assert.rejects(() => missing.capabilities(), /staff access token/);
  assert.equal(called, false, "no request may leave the browser without a credential");
});
test("a rejected credential is reported as a credential problem, not a dead service", async () => {
  const adapter = S.createAdapter(async () => ({ ok: false, status: 401, text: async () => "" }), () => TOKEN);
  await assert.rejects(() => adapter.capabilities(), /rejected this staff credential/);
  const denied = S.createAdapter(async () => ({ ok: false, status: 403, text: async () => "" }), () => TOKEN);
  await assert.rejects(() => denied.capabilities(), /rejected this staff credential/);
  const broken = S.createAdapter(async () => ({ ok: false, status: 500, text: async () => "" }), () => TOKEN);
  await assert.rejects(() => broken.capabilities(), /unavailable or request denied/);
});
