import { performance } from "node:perf_hooks";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { findSavedAnswer } from "../public/ask-carbon.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const providerArgument = process.argv.find((argument) => argument.startsWith("--provider="))?.split("=")[1] ??
  (process.argv[process.argv.indexOf("--provider") + 1] || "mock");

const normalize = (value) => value.toLowerCase();

const runMock = (knowledge, evaluationCase) => {
  const card = findSavedAnswer(knowledge, evaluationCase.question);
  return { answer: card.answer, source_ids: card.source_ids, follow_ups: card.follow_ups, maturity_note: null };
};

const score = (evaluationCase, result) => {
  const answer = normalize(result.answer);
  const support = evaluationCase.required_terms.every((term) => answer.includes(normalize(term)));
  const citationRelevance = evaluationCase.required_source_ids.every((id) => result.source_ids.includes(id));
  const maturityAccuracy = evaluationCase.forbidden_terms.every((term) => !answer.includes(normalize(term)));
  const usefulness = result.answer.length >= 80 && result.follow_ups.length > 0;
  return { support, citation_relevance: citationRelevance, maturity_accuracy: maturityAccuracy, usefulness };
};

const main = async () => {
  if (providerArgument !== "mock") {
    throw new Error("Live evaluation is disabled until an owner-approved model, credential, price acceptance and supplied live cases are available.");
  }
  const knowledge = JSON.parse(await readFile(resolve(HERE, "../knowledge/public-knowledge.v1.json"), "utf8"));
  const suite = JSON.parse(await readFile(resolve(HERE, "cases.public.json"), "utf8"));
  const results = [];
  for (const evaluationCase of suite.cases) {
    const started = performance.now();
    const output = runMock(knowledge, evaluationCase);
    results.push({ id: evaluationCase.id, ...score(evaluationCase, output), latency_ms: Math.round((performance.now() - started) * 1000) / 1000, cost_usd: 0 });
  }
  const metrics = ["support", "citation_relevance", "maturity_accuracy", "usefulness"];
  const summary = Object.fromEntries(metrics.map((metric) => [metric, results.filter((result) => result[metric]).length / results.length]));
  process.stdout.write(`${JSON.stringify({ provider: "mock_saved_explanations", live_model_calls: 0, suite_status: suite.status, cases: results, summary }, null, 2)}\n`);
};

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
