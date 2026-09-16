import test from "node:test";
import assert from "node:assert/strict";
import { createThreadGuard, findSavedAnswer } from "../public/ask-carbon.js";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

test("saved-answer retrieval uses exact starters and preserves an explicit unknown", () => {
  assert.equal(findSavedAnswer(knowledge, "How does Carbon work?").id, "how-carbon-works");
  assert.equal(findSavedAnswer(knowledge, "Which aerospace customer bought Carbon last week?").id, "commercial-stage");
  assert.equal(findSavedAnswer(knowledge, "zxqv unlisted subject").id, "unknown-answer");
});

test("new chat aborts an in-flight request and invalidates stale results", () => {
  const guard = createThreadGuard();
  const first = guard.begin();
  assert.equal(first.isCurrent(), true);
  guard.reset();
  assert.equal(first.signal.aborted, true);
  assert.equal(first.isCurrent(), false);
  const second = guard.begin();
  assert.equal(second.isCurrent(), true);
});
