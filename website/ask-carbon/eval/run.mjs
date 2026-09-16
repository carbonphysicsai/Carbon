import { performance } from "node:perf_hooks";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { findSavedAnswer } from "../public/ask-carbon.js";
import { evaluateRelease } from "../public/release-contract.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const argument = (name, fallback = null) => {
  const prefixed = process.argv.find((value) => value.startsWith(`--${name}=`));
  if (prefixed) return prefixed.slice(name.length + 3);
  const position = process.argv.indexOf(`--${name}`);
  return position >= 0 ? process.argv[position + 1] : fallback;
};
const provider = argument("provider", "contract");
const split = argument("split", "all");
const percentile = (values, fraction) => values.length ? values.slice().sort((a, b) => a - b)[Math.min(values.length - 1, Math.ceil(values.length * fraction) - 1)] : null;
const selectCases = (suite) => ({
  singles: suite.single_turn_cases.filter((item) => split === "all" || item.split === split),
  conversations: suite.conversation_cases.filter((item) => split === "all" || item.split === split),
});

const runContract = (knowledge, suite) => {
  const release = evaluateRelease(knowledge, { mode: "staging", now: new Date("2026-09-16T12:00:00Z") });
  if (!release.valid) throw new Error(`Staging release invalid: ${release.reasons.join(",")}`);
  const selected = selectCases(suite);
  const singles = selected.singles.map((item) => {
    const started = performance.now();
    const card = findSavedAnswer(knowledge, item.question, { eligibleCardIds: release.eligible_card_ids });
    return { id: item.id, split: item.split, retrieved_card_id: card?.id ?? null, disposition: card ? "saved_explanation_match" : "no_relevant_saved_explanation", latency_ms: Math.round((performance.now() - started) * 1000) / 1000 };
  });
  const conversations = selected.conversations.map((item) => {
    let priorCardIds = [];
    const turns = item.questions.map((question) => {
      const card = findSavedAnswer(knowledge, question, { eligibleCardIds: release.eligible_card_ids, priorCardIds });
      if (card) priorCardIds = [card.id];
      return { retrieved_card_id: card?.id ?? null, disposition: card ? "saved_explanation_match" : "no_relevant_saved_explanation" };
    });
    return { id: item.id, split: item.split, turns };
  });
  return {
    provider: "deterministic_saved_retrieval_contract",
    live_model_calls: 0,
    quality_evidence: false,
    warning: "Retrieval matches and latency are contract smoke checks, not factuality, support or usefulness scores.",
    counts: { supplied_single_turn: suite.single_turn_cases.length, supplied_conversations: suite.conversation_cases.length, executed_single_turn: singles.length, executed_conversations: conversations.length },
    singles,
    conversations,
  };
};

const postQuestion = async ({ endpoint, origin, question, continuation }) => {
  const started = performance.now();
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json", origin },
    body: JSON.stringify({ question, ...(continuation ? { continuation } : {}) }),
  });
  const body = await response.json().catch(() => null);
  return { http_status: response.status, body, latency_ms: Math.round((performance.now() - started) * 1000) / 1000 };
};

const runLive = async (suite) => {
  const endpoint = argument("endpoint", process.env.ASK_CARBON_EVAL_ENDPOINT);
  const origin = argument("origin", process.env.ASK_CARBON_EVAL_ORIGIN);
  if (!endpoint || !origin) throw new Error("Live evaluation requires --endpoint and --origin for a private staging Worker using the shared ledger. Direct provider evaluation is forbidden.");
  const healthUrl = new URL("./health", endpoint.endsWith("/") ? endpoint : `${endpoint}/`).href;
  const healthResponse = await fetch(healthUrl, { headers: { origin } });
  const health = await healthResponse.json().catch(() => null);
  if (!healthResponse.ok || !health?.active) throw new Error("The staging Worker health gate is not active; no live evaluation was attempted.");
  const selected = selectCases(suite);
  const singles = [];
  for (const item of selected.singles) {
    const result = await postQuestion({ endpoint, origin, question: item.question });
    singles.push({ id: item.id, split: item.split, review_expectation: item.review_expectation, ...result, body: result.body ? { ...result.body, continuation: result.body.continuation ? "REDACTED_OPAQUE_STATE" : undefined } : null });
  }
  const conversations = [];
  for (const item of selected.conversations) {
    let continuation = null;
    const turns = [];
    for (const question of item.questions) {
      const result = await postQuestion({ endpoint, origin, question, continuation });
      continuation = result.body?.continuation ?? null;
      turns.push({ http_status: result.http_status, latency_ms: result.latency_ms, status: result.body?.status ?? null, source_count: result.body?.sources?.length ?? 0, request_id: result.body?.request_id ?? null });
    }
    conversations.push({ id: item.id, split: item.split, review_expectation: item.review_expectation, turns });
  }
  const allLatencies = [...singles.map((item) => item.latency_ms), ...conversations.flatMap((item) => item.turns.map((turn) => turn.latency_ms))];
  return {
    provider: "bounded_staging_worker",
    model_config_id: health.model_config_id,
    quality_evidence: "PENDING_HUMAN_RUBRIC_SCORING",
    provider_attempts: allLatencies.length,
    latency_ms: { sample_count: allLatencies.length, median: percentile(allLatencies, 0.5), p95: percentile(allLatencies, 0.95), maximum: allLatencies.length ? Math.max(...allLatencies) : null },
    note: "Read exact usage and micro-USD settlement from the shared Durable Object snapshot; this client does not infer cost from response text.",
    singles,
    conversations,
  };
};

const main = async () => {
  const suite = JSON.parse(await readFile(resolve(HERE, "cases.public.json"), "utf8"));
  if (suite.single_turn_cases.length !== 40 || suite.conversation_cases.length !== 5) throw new Error("Supplied evaluation coverage changed unexpectedly.");
  const knowledge = JSON.parse(await readFile(resolve(HERE, "../knowledge/public-knowledge.v1.json"), "utf8"));
  const result = provider === "contract" ? runContract(knowledge, suite) : provider === "live" ? await runLive(suite) : null;
  if (!result) throw new Error("Provider must be contract or live.");
  process.stdout.write(`${JSON.stringify({ suite_status: suite.status, source_artifact_sha256: suite.source_artifact_sha256, split, ...result }, null, 2)}\n`);
};

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
