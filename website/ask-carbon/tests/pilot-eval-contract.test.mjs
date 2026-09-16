import test from "node:test";
import assert from "node:assert/strict";
import cases from "../eval/pilot-design.cases.public.json" with { type: "json" };

test("pilot-design authored evaluation contract covers the owner-requested risks", () => {
  assert.equal(cases.status, "AUTHOR_CREATED_CONTRACT_CASES_NOT_LIVE_MODEL_EVALUATION");
  const ids = new Set(cases.cases.map((item) => item.id));
  for (const id of ["existing-model-evaluation", "thermal-fluid-cold-plate", "unfamiliar-coupled-physics", "sparse-information", "contradiction-and-correction", "unrealistic-performance", "absent-reference-data", "unsupported-guarantee", "prompt-injection-cross-client"]) assert.ok(ids.has(id), id);
  for (const item of cases.cases) {
    assert.ok(item.scenario.length > 20);
    assert.ok(item.required_behavior.length >= 3);
    assert.ok(item.forbidden_behavior.length >= 3);
  }
});
