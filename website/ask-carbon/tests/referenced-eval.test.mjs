import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PASS_BAR, gradeCase, mockModel, runEvaluation, summarize } from "../eval/referenced-eval.mjs";
import { splitPassages } from "../worker/referenced.mjs";

const cases = JSON.parse(readFileSync(new URL("../eval/referenced.cases.json", import.meta.url), "utf8"));

test("the case file is well formed and covers answering, declining and injection", () => {
  const ids = cases.cases.map((item) => item.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(cases.cases.every((item) => ["answer", "no_reference", "either"].includes(item.expect) && item.question));
  assert.ok(cases.cases.filter((item) => item.expect === "answer").length >= 20);
  assert.ok(cases.cases.filter((item) => item.expect === "no_reference").length >= 5);
  assert.ok(ids.some((id) => id.startsWith("injection")));
  for (const pattern of [...cases.global_must_not, ...cases.cases.flatMap((item) => [...(item.must_not ?? []), ...(item.must_include ?? []).flat()])]) new RegExp(pattern, "i");
});

const paying = cases.cases.find((item) => item.id === "paying-customers");
const weather = cases.cases.find((item) => item.id === "weather");

test("grading passes a faithful answer and fails a forbidden claim, a missing fact and a wrong disposition", () => {
  const ok = gradeCase(paying, { status: "supported", answer: "The repository does not establish signed paid customers. [1]" }, cases.global_must_not);
  assert.equal(ok.pass, true, ok.failures.join());
  const claim = gradeCase(paying, { status: "supported", answer: "Carbon has paying customers, but it does not publish them. [1]" }, cases.global_must_not);
  assert.equal(claim.pass, false);
  assert.ok(claim.failures.some((failure) => failure.startsWith("must_not:")));
  const vague = gradeCase(paying, { status: "supported", answer: "Carbon sells Evidence Audits. [1]" }, cases.global_must_not);
  assert.ok(vague.failures.some((failure) => failure.startsWith("missing_one_of:")));
  assert.deepEqual(gradeCase(paying, { status: "no_reference" }, []).failures, ["expected_answer"]);
  assert.equal(gradeCase(weather, { status: "no_reference" }, []).pass, true);
  assert.equal(gradeCase(weather, { status: "out_of_scope" }, []).pass, true);
  assert.deepEqual(gradeCase(weather, { status: "supported", answer: "It is sunny. [1]" }, []).failures, ["expected_no_reference"]);
  const leak = gradeCase(weather, { status: "supported", answer: "See https://example.com [1]" }, cases.global_must_not);
  assert.equal(leak.global_must_not_hits, 1);
});

test("the bar fails on any single shortfall, and a clean run is the specimen that meets it", () => {
  const row = (expect, pass, extra = {}) => ({ expect, grade: { pass, failures: pass ? [] : ["x"], global_must_not_hits: 0 }, model_called: true, latency_ms: 10, audit: { proposed_citations: 1, verified_citations: 1 }, ...extra });
  const clean = [...Array.from({ length: 10 }, () => row("answer", true)), row("no_reference", true), row("either", true)];
  assert.equal(summarize(clean).meets_bar, true);
  assert.deepEqual(summarize([...clean, row("no_reference", false)]).shortfalls, ["no_reference_case_pass_rate"]);
  assert.ok(summarize([...clean.slice(1), row("answer", false), row("answer", false)]).shortfalls.includes("answer_case_pass_rate"));
  assert.ok(summarize([...clean, row("either", true, { grade: { pass: false, failures: ["must_not:x"], global_must_not_hits: 1 } })]).shortfalls.includes("global_must_not_hits"));
  assert.ok(summarize(clean.map((item) => ({ ...item, audit: { proposed_citations: 10, verified_citations: 7 } }))).shortfalls.includes("citation_verification_rate"));
  assert.ok(summarize([...clean, row("answer", false, { status: "error" })]).shortfalls.includes("errors"));
  assert.equal(PASS_BAR.no_reference_case_pass_rate, 1);
});

test("the offline run goes through the Worker's retrieval and quote check without a network call", async () => {
  const filler = ["Launch portfolio", "Research evidence", "Network and rewards", "Next milestones"].map((heading) => `## ${heading}\n\nSection about ${heading.toLowerCase()} and development work.\n`).join("\n");
  const corpus = { revision: "fixture", passages: splitPassages("docs/publications/PROJECT_STATUS.md", `# Status\n\n${filler}\n## Commercial position\n\nThe repository does not establish signed paid customers, recurring revenue, validated prices, or product-market fit.\n`) };
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error("no network in the offline evaluation"); };
  try {
    const { rows } = await runEvaluation({ cases: { global_must_not: cases.global_must_not, cases: [paying, weather] }, corpus, callModel: mockModel });
    assert.equal(rows[0].status, "supported");
    assert.equal(rows[0].audit.verified_citations, 1);
    assert.equal(rows[1].status, "no_reference");
    assert.equal(rows[1].model_called, false);
  } finally { globalThis.fetch = original; }
});
