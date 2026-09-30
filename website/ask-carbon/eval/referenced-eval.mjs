// Model selection for REFERENCED_ANSWER_V1.
//
// Runs the Worker's own retrieval, prompt, schema and quote check against the
// question set in referenced.cases.json, with one model, and grades each answer
// mechanically. The corpus is read from a git revision of this repository, so a
// run is reproducible and names exactly what the model was given.
//
//   node eval/referenced-eval.mjs --provider mock
//   node eval/referenced-eval.mjs --model <id> --api-key-file <path> \
//     [--base-url https://llm.chutes.ai/v1] [--revision origin/main] --output <file>
//
// The API key is read from --api-key-file at the moment of each request and is
// never stored, logged or written; the output is checked for it before exit.

import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { detectOutOfScope, needsTopicContext } from "../worker/core.mjs";
import { PROVIDERS } from "../worker/providers.mjs";
import {
  CORPUS_PATHS,
  MIN_OUTPUT_TOKENS,
  REFERENCED_ANSWER_CONTRACT,
  referencedInstructions,
  referencedSchema,
  retrieve,
  smallTalkAnswer,
  splitPassages,
  verifyReferencedAnswer,
} from "../worker/referenced.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../../..");
export const CASES_PATH = resolve(HERE, "referenced.cases.json");

// The bar a model must clear before it is proposed for the live Worker. These
// are product-quality thresholds for a public explainer, set by engineering and
// open to the owner's change; they are not scientific acceptance values.
export const PASS_BAR = Object.freeze({
  answer_case_pass_rate: 0.9,
  no_reference_case_pass_rate: 1,
  global_must_not_hits: 0,
  citation_verification_rate: 0.8,
});

export const readCorpusAtRevision = (revision = "HEAD", paths = CORPUS_PATHS, root = REPO_ROOT) => {
  const sha = execFileSync("git", ["-C", root, "rev-parse", `${revision}^{commit}`], { encoding: "utf8" }).trim();
  const unreadable = [];
  const passages = paths.flatMap((path) => {
    try {
      return splitPassages(path, execFileSync("git", ["-C", root, "show", `${sha}:${path}`], { encoding: "utf8", maxBuffer: 16 * 1024 * 1024 }));
    } catch {
      unreadable.push(path);
      return [];
    }
  });
  return { revision: sha, passages, unreadable_paths: unreadable };
};

const patternsMatch = (patterns, text) => patterns.some((pattern) => new RegExp(pattern, "i").test(text));

export const gradeCase = (testCase, result, globalMustNot = []) => {
  const declined = result.status === "no_reference" || result.status === "out_of_scope";
  const answered = result.status === "supported";
  const text = answered ? result.answer : "";
  const failures = [];
  const forbidden = [...globalMustNot, ...(testCase.must_not ?? [])].filter((pattern) => answered && new RegExp(pattern, "i").test(text));
  if (forbidden.length) failures.push(...forbidden.map((pattern) => `must_not:${pattern}`));
  if (testCase.expect === "no_reference" && !declined) failures.push("expected_no_reference");
  if (testCase.expect === "conversation" && result.status !== "conversation") failures.push("expected_conversation");
  if (testCase.expect === "answer") {
    if (!answered) failures.push("expected_answer");
    else for (const group of testCase.must_include ?? []) if (!patternsMatch(group, text)) failures.push(`missing_one_of:${group.join("|")}`);
  }
  if (testCase.expect === "either" && answered) {
    for (const group of testCase.must_include ?? []) if (!patternsMatch(group, text)) failures.push(`missing_one_of:${group.join("|")}`);
  }
  if (result.status === "error") failures.push(`error:${result.error}`);
  return {
    pass: failures.length === 0,
    failures,
    global_must_not_hits: globalMustNot.filter((pattern) => answered && new RegExp(pattern, "i").test(text)).length,
  };
};

export const summarize = (rows) => {
  const byExpect = (expect) => rows.filter((row) => row.expect === expect);
  const rate = (items) => items.length ? items.filter((row) => row.grade.pass).length / items.length : 1;
  const proposed = rows.reduce((sum, row) => sum + (row.audit?.proposed_citations ?? 0), 0);
  const verified = rows.reduce((sum, row) => sum + (row.audit?.verified_citations ?? 0), 0);
  const latencies = rows.filter((row) => row.model_called).map((row) => row.latency_ms).sort((a, b) => a - b);
  const summary = {
    cases: rows.length,
    passed: rows.filter((row) => row.grade.pass).length,
    answer_case_pass_rate: rate(byExpect("answer")),
    no_reference_case_pass_rate: rate(byExpect("no_reference")),
    either_case_pass_rate: rate(byExpect("either")),
    conversation_case_pass_rate: rate(byExpect("conversation")),
    global_must_not_hits: rows.reduce((sum, row) => sum + row.grade.global_must_not_hits, 0),
    citation_verification_rate: proposed ? verified / proposed : null,
    errors: rows.filter((row) => row.status === "error").length,
    model_calls: latencies.length,
    latency_ms_median: latencies.length ? latencies[Math.floor((latencies.length - 1) / 2)] : null,
    latency_ms_p95: latencies.length ? latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * 0.95) - 1)] : null,
    input_tokens: rows.reduce((sum, row) => sum + (row.usage?.input_tokens ?? 0), 0),
    output_tokens: rows.reduce((sum, row) => sum + (row.usage?.output_tokens ?? 0), 0),
  };
  const shortfalls = [];
  if (summary.answer_case_pass_rate < PASS_BAR.answer_case_pass_rate) shortfalls.push("answer_case_pass_rate");
  if (summary.no_reference_case_pass_rate < PASS_BAR.no_reference_case_pass_rate) shortfalls.push("no_reference_case_pass_rate");
  if (summary.either_case_pass_rate < 1) shortfalls.push("either_case_pass_rate");
  if (summary.conversation_case_pass_rate < 1) shortfalls.push("conversation_case_pass_rate");
  if (summary.global_must_not_hits > PASS_BAR.global_must_not_hits) shortfalls.push("global_must_not_hits");
  if (summary.citation_verification_rate !== null && summary.citation_verification_rate < PASS_BAR.citation_verification_rate) shortfalls.push("citation_verification_rate");
  if (summary.errors) shortfalls.push("errors");
  return { ...summary, meets_bar: shortfalls.length === 0, shortfalls };
};

// One turn, exactly as the Worker would handle it: small talk, boundary check,
// retrieval, then one model call whose facts are kept only where their quotes
// verify. `prior` is the previous turn, as the signed continuation carries it.
export const runTurn = async (question, corpus, callModel, prior = null) => {
  const started = performance.now();
  const greeting = smallTalkAnswer(question);
  if (greeting) return { status: "conversation", answer: greeting, model_called: false, latency_ms: 0, retrieved: [] };
  const boundary = detectOutOfScope(question);
  if (boundary) return { status: "out_of_scope", answer: null, model_called: false, latency_ms: 0, retrieved: [] };
  const query = prior && needsTopicContext(question) ? `${prior.question} ${question}` : question;
  const passages = retrieve(corpus.passages, query);
  if (!passages.length) return { status: "no_reference", answer: null, model_called: false, latency_ms: 0, retrieved: [] };
  const retrieved = passages.map((passage) => `${passage.path}#L${passage.start_line}-L${passage.end_line}`);
  try {
    const { parsed, usage } = await callModel({
      instructions: referencedInstructions(passages, prior ? { priorQuestion: prior.question, priorAnswer: prior.answer } : {}),
      userText: question,
      schema: referencedSchema(passages.length),
      passages,
    });
    const verified = verifyReferencedAnswer(parsed, passages);
    return {
      status: verified.status,
      answer: verified.status === "supported" ? verified.answer : null,
      references: verified.references.map((reference) => ({ document: retrieved[reference.passage_index], quote: reference.quote })),
      audit: verified.audit,
      usage,
      model_called: true,
      latency_ms: Math.round(performance.now() - started),
      retrieved,
    };
  } catch (error) {
    return { status: "error", error: String(error?.code ?? error?.message ?? error).slice(0, 200), model_called: true, latency_ms: Math.round(performance.now() - started), retrieved };
  }
};

export const runCase = async (testCase, corpus, callModel) => {
  const questions = testCase.turns ?? [testCase.question];
  const base = { id: testCase.id, question: questions.join(" / "), expect: testCase.expect };
  let prior = null;
  const earlier = [];
  let result;
  for (const question of questions) {
    result = await runTurn(question, corpus, callModel, prior);
    if (question !== questions.at(-1)) earlier.push({ question, status: result.status, answer: result.answer });
    prior = { question, answer: result.status === "supported" ? result.answer : null };
  }
  return { ...base, ...result, ...(earlier.length ? { earlier_turns: earlier } : {}) };
};

export const runEvaluation = async ({ cases, corpus, callModel, delayMs = 0, onRow = () => {} }) => {
  const rows = [];
  for (const testCase of cases.cases) {
    const result = await runCase(testCase, corpus, callModel);
    result.grade = gradeCase(testCase, result, cases.global_must_not ?? []);
    rows.push(result);
    onRow(result);
    if (delayMs && result.model_called) await delay(delayMs);
  }
  return { rows, summary: summarize(rows) };
};

// Offline stand-in: quotes the opening of the first retrieved passage. It
// exercises the harness and the quote check, not answer quality.
export const mockModel = async ({ passages }) => {
  const text = passages[0].text.replace(/^#+\s.*\n/, "").replace(/\s+/g, " ").trim();
  const quote = text.slice(0, 120);
  return {
    parsed: quote.length >= 20
      ? { status: "answered", sentences: [{ kind: "fact", text: `We describe it this way: ${quote}`, citations: [{ passage: "P1", quote }] }] }
      : { status: "no_reference", sentences: [] },
    usage: { input_tokens: 0, output_tokens: 0 },
  };
};

// OpenAI-compatible chat/completions with strict JSON-schema output, the same
// wire format the Worker's Chutes adapter sends.
// A rate limit or a transport failure says nothing about the model's answer,
// so it is retried with backoff (5 s, 15 s, 45 s) before counting as an error.
// A timeout is not retried: it is the latency a visitor would see.
export const RETRY_DELAYS_MS = Object.freeze([5_000, 15_000, 45_000]);
export const chatCompletionsModel = ({ baseUrl, model, apiKeyFile, maxOutputTokens, timeoutMs = 60_000, retryDelaysMs = RETRY_DELAYS_MS }) => async ({ instructions, userText, schema }) => {
  const adapter = PROVIDERS.chutes_chat_completions;
  const body = adapter.buildBody({ request_model: model, temperature: 0 }, {
    instructions, userText, schemaName: "ask_carbon_referenced_answer", schema, maxOutputTokens,
  });
  let response;
  let retries = 0;
  for (let attempt = 0; ; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      response = await fetch(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
        method: "POST",
        headers: { authorization: `Bearer ${(await readFile(apiKeyFile, "utf8")).trim()}`, "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (error) {
      clearTimeout(timer);
      if (error?.name === "AbortError") throw Object.assign(new Error("provider_timeout"), { code: "provider_timeout" });
      if (attempt >= retryDelaysMs.length) throw Object.assign(new Error("provider_transport"), { code: "provider_transport" });
      retries += 1;
      await delay(retryDelaysMs[attempt]);
      continue;
    }
    clearTimeout(timer);
    if ((response.status === 429 || response.status >= 500) && attempt < retryDelaysMs.length) {
      retries += 1;
      await delay(retryDelaysMs[attempt]);
      continue;
    }
    break;
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload) throw Object.assign(new Error(`provider_http_${response.status}`), { code: `provider_http_${response.status}` });
  const outcome = adapter.normalizeOutcome(payload);
  if (outcome.completion !== "completed") throw Object.assign(new Error(`provider_${outcome.completion}`), { code: `provider_${outcome.completion}` });
  let parsed;
  try { parsed = JSON.parse(outcome.text); } catch { throw Object.assign(new Error("invalid_json"), { code: "invalid_json" }); }
  return {
    parsed,
    usage: { input_tokens: payload.usage?.prompt_tokens ?? null, output_tokens: payload.usage?.completion_tokens ?? null, response_model: payload.model ?? null, retries },
  };
};

const argument = (name, fallback = null) => {
  const prefixed = process.argv.find((value) => value.startsWith(`--${name}=`));
  if (prefixed) return prefixed.slice(name.length + 3);
  const position = process.argv.indexOf(`--${name}`);
  return position >= 0 ? process.argv[position + 1] : fallback;
};

const main = async () => {
  const provider = argument("provider", "live");
  const cases = JSON.parse(await readFile(argument("cases", CASES_PATH), "utf8"));
  const corpus = readCorpusAtRevision(argument("revision", "HEAD"));
  const maxOutputTokens = Number.parseInt(argument("max-output-tokens", String(MIN_OUTPUT_TOKENS)), 10);
  let callModel;
  let model;
  const apiKeyFile = argument("api-key-file");
  if (provider === "mock") {
    callModel = mockModel;
    model = "mock";
  } else {
    model = argument("model");
    if (!model || !apiKeyFile) throw new Error("A live run needs --model and --api-key-file.");
    callModel = chatCompletionsModel({ baseUrl: argument("base-url", "https://llm.chutes.ai/v1"), model, apiKeyFile, maxOutputTokens });
  }
  const { rows, summary } = await runEvaluation({
    cases,
    corpus,
    callModel,
    delayMs: Number.parseInt(argument("delay-ms", "0"), 10),
    onRow: (row) => process.stderr.write(`${row.grade.pass ? "PASS" : "FAIL"} ${row.id} ${row.status}${row.grade.failures.length ? ` ${row.grade.failures.join(",")}` : ""}\n`),
  });
  const result = {
    schema: "ask-carbon.referenced-eval-result.v1",
    answer_contract: REFERENCED_ANSWER_CONTRACT,
    model,
    base_url: provider === "mock" ? null : argument("base-url", "https://llm.chutes.ai/v1"),
    documentation_revision: corpus.revision,
    unreadable_paths: corpus.unreadable_paths,
    max_output_tokens: maxOutputTokens,
    pass_bar: PASS_BAR,
    summary,
    rows,
  };
  const serialized = `${JSON.stringify(result, null, 2)}\n`;
  // Specimen check: the credential itself is the thing that must be absent.
  if (apiKeyFile) {
    const secret = (await readFile(apiKeyFile, "utf8")).trim();
    if (secret && serialized.includes(secret)) throw new Error("Refusing to write evaluation output that contains the API key.");
  }
  const outputPath = argument("output");
  if (outputPath) await writeFile(resolve(outputPath), serialized, { encoding: "utf8", flag: "wx" });
  process.stdout.write(`${JSON.stringify({ model, documentation_revision: corpus.revision, ...summary }, null, 2)}\n`);
  if (!summary.meets_bar) process.exitCode = 1;
};

if (process.argv[1] === fileURLToPath(import.meta.url)) main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 2;
});
