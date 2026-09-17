import { performance } from "node:perf_hooks";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { findSavedAnswer } from "../public/ask-carbon.js";
import { evaluateRelease } from "../public/release-contract.js";
import { loadPilotSuite, planPilotSuite, runPilotLive, runPilotMock } from "./pilot-design-runner.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const argument = (name, fallback = null) => {
  const prefixed = process.argv.find((value) => value.startsWith(`--${name}=`));
  if (prefixed) return prefixed.slice(name.length + 3);
  const position = process.argv.indexOf(`--${name}`);
  return position >= 0 ? process.argv[position + 1] : fallback;
};
const provider = argument("provider", "contract");
const suiteName = argument("suite", "general-qa");
const split = argument("split", "all");
const delayMs = Number.parseInt(argument("delay-ms", process.env.ASK_CARBON_EVAL_DELAY_MS ?? "3200"), 10);
if (!Number.isSafeInteger(delayMs) || delayMs < 0) throw new Error("--delay-ms must be a non-negative integer.");
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

const accessHeaders = () => process.env.CF_ACCESS_CLIENT_ID && process.env.CF_ACCESS_CLIENT_SECRET ? {
  "CF-Access-Client-Id": process.env.CF_ACCESS_CLIENT_ID,
  "CF-Access-Client-Secret": process.env.CF_ACCESS_CLIENT_SECRET,
} : {};
const stagingAuthHeaders = () => process.env.ASK_CARBON_STAGING_BASIC_USER && process.env.ASK_CARBON_STAGING_BASIC_PASSWORD ? {
  authorization: `Basic ${Buffer.from(`${process.env.ASK_CARBON_STAGING_BASIC_USER}:${process.env.ASK_CARBON_STAGING_BASIC_PASSWORD}`).toString("base64")}`,
} : {};

const readLedger = async (endpoint) => {
  const secret = process.env.ASK_CARBON_OPERATOR_READ_SECRET;
  if (!secret) throw new Error("Live evaluation requires ASK_CARBON_OPERATOR_READ_SECRET for aggregate Durable Object reconciliation.");
  const ledgerUrl = new URL("./internal/ledger", endpoint.endsWith("/") ? endpoint : `${endpoint}/`).href;
  const response = await fetch(ledgerUrl, {
    headers: { ...accessHeaders(), ...stagingAuthHeaders(), "x-ask-carbon-operator-secret": secret },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error("The staging Worker ledger readout is unavailable; no live evaluation was attempted.");
  return body;
};

const postQuestion = async ({ endpoint, origin, question, continuation }) => {
  const started = performance.now();
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json", origin, ...accessHeaders(), ...stagingAuthHeaders() },
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
  const healthResponse = await fetch(healthUrl, { headers: { origin, ...accessHeaders(), ...stagingAuthHeaders() } });
  const health = await healthResponse.json().catch(() => null);
  if (!healthResponse.ok || !health?.active) throw new Error("The staging Worker health gate is not active; no live evaluation was attempted.");
  const ledgerBefore = await readLedger(endpoint);
  const selected = selectCases(suite);
  let requestCount = 0;
  const pacedQuestion = async (value) => {
    if (requestCount > 0 && delayMs > 0) await delay(delayMs);
    requestCount += 1;
    return postQuestion(value);
  };
  const singles = [];
  for (const item of selected.singles) {
    const result = await pacedQuestion({ endpoint, origin, question: item.question });
    singles.push({ id: item.id, split: item.split, review_expectation: item.review_expectation, ...result, body: result.body ? { ...result.body, continuation: result.body.continuation ? "REDACTED_OPAQUE_STATE" : undefined } : null });
  }
  const conversations = [];
  for (const item of selected.conversations) {
    let continuation = null;
    const turns = [];
    for (const question of item.questions) {
      const result = await pacedQuestion({ endpoint, origin, question, continuation });
      continuation = result.body?.continuation ?? null;
      turns.push({
        question,
        http_status: result.http_status,
        latency_ms: result.latency_ms,
        status: result.body?.status ?? null,
        error: result.body?.error ?? null,
        answer: result.body?.answer ?? null,
        follow_up: result.body?.follow_up ?? null,
        maturity_note: result.body?.maturity_note ?? null,
        sources: result.body?.sources ?? [],
        source_count: result.body?.sources?.length ?? 0,
        request_id: result.body?.request_id ?? null,
        evaluation: result.body?.evaluation ?? null,
      });
    }
    conversations.push({ id: item.id, split: item.split, review_expectation: item.review_expectation, turns });
  }
  const allLatencies = [...singles.map((item) => item.latency_ms), ...conversations.flatMap((item) => item.turns.map((turn) => turn.latency_ms))];
  const allTelemetry = [
    ...singles.map((item) => item.body?.evaluation),
    ...conversations.flatMap((item) => item.turns.map((turn) => turn.evaluation)),
  ].filter(Boolean);
  const exactCostMicroUsd = allTelemetry.reduce((total, item) => total + item.actual_cost_micro_usd, 0);
  const inputTokens = allTelemetry.reduce((total, item) => total + item.usage.input_tokens, 0);
  const cachedInputTokens = allTelemetry.reduce((total, item) => total + item.usage.cached_input_tokens, 0);
  const outputTokens = allTelemetry.reduce((total, item) => total + item.usage.output_tokens, 0);
  const ledgerAfter = await readLedger(endpoint);
  return {
    provider: "bounded_staging_worker",
    model_config_id: health.model_config_id,
    quality_evidence: "PENDING_HUMAN_RUBRIC_SCORING",
    provider_attempts: allLatencies.length,
    pacing_delay_ms: delayMs,
    latency_ms: { sample_count: allLatencies.length, median: percentile(allLatencies, 0.5), p95: percentile(allLatencies, 0.95), maximum: allLatencies.length ? Math.max(...allLatencies) : null },
    completed_telemetry: {
      sample_count: allTelemetry.length,
      input_tokens: inputTokens,
      cached_input_tokens: cachedInputTokens,
      output_tokens: outputTokens,
      exact_cost_micro_usd: exactCostMicroUsd,
    },
    uncertain_exposure_requires_ledger_snapshot: allTelemetry.length !== allLatencies.length,
    ledger_before: ledgerBefore,
    ledger_after: ledgerAfter,
    note: "Completed response usage is provider-reported and settled by the Worker. Any failed or ambiguous attempt requires the shared Durable Object snapshot; the evaluator never infers missing usage as zero.",
    singles,
    conversations,
  };
};

const main = async () => {
  if (suiteName === "pilot-design") {
    const pilotSuite = await loadPilotSuite();
    const result = provider === "plan"
      ? planPilotSuite(pilotSuite)
      : provider === "mock"
        ? await runPilotMock(pilotSuite)
        : provider === "live"
          ? await runPilotLive(pilotSuite, {
            endpoint: argument("endpoint", process.env.ASK_CARBON_EVAL_ENDPOINT),
            origin: argument("origin", process.env.ASK_CARBON_EVAL_ORIGIN),
            accessClientId: process.env.ASK_CARBON_ACCESS_CLIENT_ID,
            accessClientSecret: process.env.ASK_CARBON_ACCESS_CLIENT_SECRET,
            basicAuth: process.env.ASK_CARBON_STAGING_BASIC_AUTH,
            operatorSecret: process.env.ASK_CARBON_STAGING_OPERATOR_SECRET,
            runId: argument("run-id", null),
          })
          : null;
    if (!result) throw new Error("Pilot-design provider must be plan, mock or live.");
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  if (suiteName !== "general-qa") throw new Error("Suite must be general-qa or pilot-design.");
  const suite = JSON.parse(await readFile(resolve(HERE, "cases.public.json"), "utf8"));
  if (suite.single_turn_cases.length !== 40 || suite.conversation_cases.length !== 6) throw new Error("Frozen evaluation coverage changed unexpectedly.");
  const knowledge = JSON.parse(await readFile(resolve(HERE, "../knowledge/public-knowledge.v1.json"), "utf8"));
  const result = provider === "contract" ? runContract(knowledge, suite) : provider === "live" ? await runLive(suite) : null;
  if (!result) throw new Error("Provider must be contract or live.");
  process.stdout.write(`${JSON.stringify({ suite_status: suite.status, source_artifact_sha256: suite.source_artifact_sha256, split, ...result }, null, 2)}\n`);
};

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
