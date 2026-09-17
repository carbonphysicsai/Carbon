import test from "node:test";
import assert from "node:assert/strict";
import cases from "../eval/cases.public.json" with { type: "json" };

test("frozen live-evaluation inputs retain the supplied cases and explicit topic switch", () => {
  assert.equal(cases.single_turn_cases.length, 40);
  assert.equal(cases.conversation_cases.length, 6);
  const switchCase = cases.conversation_cases.find((item) => item.id === "THREAD-06");
  assert.deepEqual(switchCase.questions, [
    "Who chooses the training cases?",
    "What can the miner change?",
    "Can they bring their own data?",
    "Okay, where do the reference answers come from?",
  ]);
  assert.match(switchCase.review_expectation, /topic switch/i);
});
