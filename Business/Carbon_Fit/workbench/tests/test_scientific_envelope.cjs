"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../src/scientific_studies.js"), G = require("../src/workflow.js");
const copy = (v) => JSON.parse(JSON.stringify(v));
const pin = (x) => "sha256:" + x.repeat(64);
function setup() {
  const physical = { domain_length: 2 * Math.PI, viscosity: 0.2, mean: 0, cosine_coefficients: [0.2, ...Array(11).fill(0)], sine_coefficients: Array(12).fill(0), requested_times: Array.from({length: 13}, (_, i) => i), output_points: 64, units: "dimensionless" };
  const cap = { schema: S.ENVELOPE_CAPABILITIES, template_id: S.TEMPLATE, physical, method: "fixture-method", environment: "fixture-environment", available: true, envelope: { scope_digest: pin("a"), case_digests: [pin("b"), pin("c")], physical: [physical, { ...copy(physical), mean: 0.1 }] } };
  const design = G.newDesign("job-fixture", "draft-fixture");
  Object.assign(design.scope, { physics_family: S.TEMPLATE, requested_goal: "Dynamics", inputs: "public source", outputs: "periodic field", units: "dimensionless", geometry: "periodic line", conditions: "periodic", rights_scope: "SYNTHETIC_INTERNAL" });
  design.reference_plan.equation = "u_t + (u²/2)_x = nu u_xx";
  const calls = [];
  function reply(r, partial = false) {
    const children = cap.envelope.case_digests.map((case_digest, index) => ({ operation_id: "child-" + index, case_digest, state: partial && index ? "HELD" : "SUCCEEDED", reservation: { numerical_milliseconds: 720000 }, actual: partial && index ? null : { numerical_milliseconds: 10 }, result: partial && index ? null : { metadata: { case_digest, scope_digest: r.envelope_scope_digest, times: cap.envelope.physical[index].requested_times }, values: Array.from({ length: 13 }, () => Array(64).fill(index)) } }));
    return { schema: S.ENVELOPE_RESPONSE, operation_id: r.operation_id, task_id: "task-envelope", status: partial ? "RUNNING" : "COMPLETE", binding: copy(r.binding), remaining_budget: { research_trials_remaining: 1, numerical_milliseconds_remaining: 1000, reference_invocations_remaining: null }, method: cap.method, environment: cap.environment, result: { metadata: { parent: "task-envelope", scope_digest: r.envelope_scope_digest, official_eligible: false, scientifically_qualified: false, training_support_eligible: false }, children }, official_eligible: false, qualification: "NOT_QUALIFIED" };
  }
  const adapter = { capabilities: async () => copy(cap) };
  for (const name of ["start", "status", "result", "cancel"]) adapter[name] = async (r) => { calls.push(copy(r)); return reply(r); };
  return { cap, design, calls, reply, controller: S.createController(adapter, () => design) };
}

test("v2 two-case grant must be closed and baseline/source order exact", () => {
  const {cap} = setup(); assert.deepEqual(S.capabilities(cap), cap);
  for (const invalid of [{...cap, envelope: {...cap.envelope, case_digests: [pin("b"), pin("b")]}}, {...cap, envelope: {...cap.envelope, physical: cap.envelope.physical.slice(1)}}]) assert.throws(() => S.capabilities(invalid));
});

test("envelope action retains exact retry identity and preserves v1 selection", async () => {
  const c = setup(); await c.controller.connect(); await c.controller.adopt();
  const v1 = c.controller.snapshot().run.request;
  await c.controller.adopt("OPERATING_ENVELOPE"); await c.controller.start(); await c.controller.status();
  const saved = c.controller.save(); assert.equal(saved.request.schema, S.ENVELOPE_REQUEST);
  assert.deepEqual(c.calls[0], c.calls[1]); assert.notEqual(saved.request.operation_id, v1.operation_id);
  await c.controller.adopt(); assert.deepEqual(c.controller.snapshot().run.request, v1);
  await c.controller.adopt("OPERATING_ENVELOPE"); assert.deepEqual(c.controller.save(), saved);
});

test("partial completed child is readable while held child is never called complete", async () => {
  const c = setup(), request = await S.prepare(c.design, c.cap.physical, c.cap.envelope.scope_digest);
  const partial = c.reply(request, true); assert.equal(S.response(partial, request).result.children[1].state, "HELD");
  assert.throws(() => S.response({...partial, status: "COMPLETE"}, request));
  const forged = copy(partial); forged.result.children[1].result = forged.result.children[0].result;
  assert.throws(() => S.response(forged, request));
});

test("saved envelope reopens unverified without dispatch, then rereads same operation", async () => {
  const c = setup(); await c.controller.connect(); await c.controller.adopt("OPERATING_ENVELOPE"); await c.controller.start();
  const saved = c.controller.save(), other = setup();
  await other.controller.reopen(saved); assert.equal(other.calls.length, 0); assert.equal(other.controller.snapshot().run.origin, "SAVED_UNVERIFIED");
  await other.controller.connect(); await other.controller.status(); assert.deepEqual(other.calls[0], saved.request);
});

test("physical edits invalidate two-case association while display edits preserve it", async () => {
  const c = setup(); await c.controller.connect(); await c.controller.adopt("OPERATING_ENVELOPE");
  c.design.alternative_label = "display only"; assert.equal((await c.controller.refresh()).run.association, "CURRENT");
  c.design.scope.conditions += " changed"; assert.equal((await c.controller.refresh()).run.association, "STALE");
  await assert.rejects(c.controller.start(), /stale/); assert.equal(c.calls.length, 0);
});
