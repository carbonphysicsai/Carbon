import test from "node:test";
import assert from "node:assert/strict";
import { AskCarbonUsageLedger, createWorker } from "../worker/index.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };
import {
  CORPUS_PATHS,
  MAX_PASSAGE_CHARS,
  NO_REFERENCE_ANSWER,
  loadCorpus,
  normalizeForQuote,
  referencedSchema,
  resetCorpusMemo,
  retrieve,
  smallTalkAnswer,
  splitPassages,
  verifyReferencedAnswer,
} from "../worker/referenced.mjs";

const SHA = "0123456789abcdef0123456789abcdef01234567";
const STATUS_DOC = [
  "# Carbon project status",
  "",
  "**Reviewed: 28 September 2026.** This guide summarizes the code and evidence on `main`.",
  "",
  "## Launch portfolio",
  "",
  "The owner selected battery, AI-chip cold plates, electric motors, and silicon photonics. Selection is not launch approval.",
  "",
  "## Commercial position",
  "",
  "The repository does not establish signed paid customers, recurring revenue, validated prices, or product-market fit.",
].join("\n");
const README_DOC = "# Carbon\n\nCarbon is an incentivized experimental system for discovering methods for constructing fast physical models.\n";

// A corpus server standing in for GitHub: the commit id, then raw files at it.
const corpusServer = (files = { "docs/publications/PROJECT_STATUS.md": STATUS_DOC, "README.md": README_DOC }, calls = []) => async (url, ttl, headers = {}) => {
  calls.push({ url, ttl, headers });
  if (url.endsWith("/commits/main")) return SHA;
  const path = url.split(`/${SHA}/`)[1];
  if (path in files) return files[path];
  throw new Error("404");
};

test("passages follow Markdown sections and keep 1-based line ranges", () => {
  const passages = splitPassages("docs/publications/PROJECT_STATUS.md", STATUS_DOC);
  assert.deepEqual(passages.map((passage) => passage.heading), ["Carbon project status", "Launch portfolio", "Commercial position"]);
  const launch = passages[1];
  assert.equal(launch.start_line, 5);
  assert.equal(STATUS_DOC.split("\n")[launch.start_line - 1], "## Launch portfolio");
  assert.ok(launch.text.includes("silicon photonics"));
  const long = splitPassages("x.md", `# Long\n\n${Array.from({ length: 40 }, (_, index) => `Paragraph ${index} ${"word ".repeat(20)}\n`).join("\n")}`);
  assert.ok(long.length > 1);
  assert.ok(long.every((passage) => passage.text.length <= MAX_PASSAGE_CHARS + 200));
  // A heading inside a code fence is text, not a section.
  assert.equal(splitPassages("y.md", "# A\n\n```\n# not a heading\n```\n").length, 1);
});

test("retrieval ranks the relevant section first and finds nothing for an empty query", () => {
  const passages = splitPassages("docs/publications/PROJECT_STATUS.md", STATUS_DOC);
  assert.equal(retrieve(passages, "Does Carbon have paying customers or revenue?")[0].heading, "Commercial position");
  assert.equal(retrieve(passages, "Which launch challenges were selected?")[0].heading, "Launch portfolio");
  assert.deepEqual(retrieve(passages, "what is the"), []);
  assert.deepEqual(retrieve(passages, "zebra xylophone"), []);
});

test("the corpus is read at the current commit, cached by it, and a missing file is reported not fatal", async () => {
  resetCorpusMemo();
  const calls = [];
  const corpus = await loadCorpus(corpusServer(undefined, calls));
  assert.equal(corpus.revision, SHA);
  assert.equal(calls[0].headers.accept, "application/vnd.github.sha");
  const raw = calls.filter((call) => call.url.startsWith("https://raw.githubusercontent.com/"));
  assert.equal(raw.length, CORPUS_PATHS.length);
  assert.ok(raw.every((call) => call.url.includes(`/${SHA}/`) && call.ttl === 86_400));
  assert.ok(corpus.unreadable_paths.includes("SPEC.md"));
  assert.ok(corpus.passages.some((passage) => passage.path === "README.md"));
  resetCorpusMemo();
  await assert.rejects(loadCorpus(corpusServer({})), (error) => error.code === "reference_unavailable");
});

const passages = splitPassages("docs/publications/PROJECT_STATUS.md", STATUS_DOC);
const commercial = passages.findIndex((passage) => passage.heading === "Commercial position");
const label = `P${commercial + 1}`;

test("a fact reaches the visitor only with a quote found in the passage it cites", () => {
  const kept = verifyReferencedAnswer({ status: "answered", sentences: [
    { kind: "fact", text: "Carbon has not established paying customers.", citations: [{ passage: label, quote: "does not establish signed paid customers, recurring revenue" }] },
    { kind: "fact", text: "It has ten enterprise contracts.", citations: [{ passage: label, quote: "ten signed enterprise contracts are in place" }] },
  ] }, passages);
  assert.equal(kept.status, "supported");
  assert.equal(kept.answer, "Carbon has not established paying customers.");
  assert.equal(kept.references.length, 1);
  assert.equal(kept.audit.kept_sentences, 1);
  assert.equal(kept.audit.rejected[0].reason, "quote_not_found");
  assert.equal(kept.audit.rejected[1].reason, "fact_without_verified_quote");
});

test("the right quote cited to the wrong passage is rejected, and the same quote on its own passage is the specimen that passes", () => {
  const wrong = commercial === 0 ? "P2" : "P1";
  const sentence = (passage) => ({ status: "answered", sentences: [{ kind: "fact", text: "No paying customers are established.", citations: [{ passage, quote: "does not establish signed paid customers" }] }] });
  assert.equal(verifyReferencedAnswer(sentence(wrong), passages).status, "no_reference");
  assert.equal(verifyReferencedAnswer(sentence(label), passages).status, "supported");
});

test("Markdown, quote style, whitespace and a slip of a word do not change a quote; meaning does", () => {
  const launch = passages.findIndex((passage) => passage.heading === "Launch portfolio");
  const cite = (quote) => verifyReferencedAnswer({ status: "answered", sentences: [{ kind: "fact", text: "Battery is in the launch portfolio.", citations: [{ passage: `P${launch + 1}`, quote }] }] }, passages).status;
  assert.equal(normalizeForQuote("**Reviewed:  28 September**"), "reviewed: 28 september");
  assert.equal(cite("The owner selected battery,   AI-chip cold plates"), "supported");
  assert.equal(cite("The owner approved battery, AI-chip cold plates"), "no_reference");
  assert.equal(cite("Selection is not launch approval"), "supported");
  assert.equal(cite("Selection is launch approval"), "no_reference");
  // One dropped word in ten is a copying slip, not a different statement.
  assert.equal(cite("The owner selected battery, AI-chip cold plates, electric motors, and photonics"), "supported");
  // Specimen pairs: fuzziness never drops or adds a negation.
  assert.equal(cite("electric motors, and silicon photonics. Selection is not launch approval"), "supported");
  assert.equal(cite("electric motors, and silicon photonics. Selection is launch approval"), "no_reference");
  // Words scattered across the passage are not a quote.
  assert.equal(cite("owner battery motors photonics selection approval"), "no_reference");
});

test("no sentences, a no_reference status, a URL or a short quote all end as no reference", () => {
  const status = (value) => verifyReferencedAnswer(value, passages);
  assert.equal(status({ status: "no_reference", sentences: [] }).answer, NO_REFERENCE_ANSWER);
  assert.equal(status({ status: "answered", sentences: [] }).status, "no_reference");
  assert.equal(status({ status: "answered", sentences: [{ kind: "fact", text: "See https://example.com for customers.", citations: [{ passage: label, quote: "does not establish signed paid customers" }] }] }).status, "no_reference");
  assert.equal(status({ status: "answered", sentences: [{ kind: "fact", text: "No customers.", citations: [{ passage: label, quote: "customers" }] }] }).status, "no_reference");
  assert.throws(() => verifyReferencedAnswer({ status: "maybe", sentences: [] }, passages), (error) => error.code === "invalid_provider_output");
});

test("the schema only offers the retrieved passage labels", () => {
  const schema = referencedSchema(3);
  assert.deepEqual(schema.properties.sentences.items.properties.citations.items.properties.passage.enum, ["P1", "P2", "P3"]);
});

// Worker integration: the referenced contract is opt-in configuration.
class MemoryStorage {
  constructor() { this.values = new Map(); }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async transaction(callback) { return callback(this); }
}
const runtime = (overrides = {}) => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  return { ledger, env: {
    ASK_CARBON_ACTIVATION: "enabled",
    ASK_CARBON_RUNTIME_MODE: "staging",
    ASK_CARBON_APPROVED_ORIGINS: "https://staging.example",
    ASK_CARBON_APPROVED_MODEL_CONFIGS: "gemma-4-31b-turbo-tee:v1",
    ASK_CARBON_MODEL_CONFIG_ID: "gemma-4-31b-turbo-tee:v1",
    ASK_CARBON_CHUTES_API_KEY: "test-chutes-key",
    ASK_CARBON_CONTINUATION_SIGNING_SECRET: "test-signing-secret",
    ASK_CARBON_OPERATOR_READ_SECRET: "test-operator-secret",
    ASK_CARBON_EVALUATION_ACCESS_SECRET: "test-only-evaluation-access-secret-32-bytes",
    ASK_CARBON_PRIVACY_MODE: "evaluation_public_synthetic_only",
    ASK_CARBON_EDGE_ACCESS_POLICY_ID: "test-private-access-policy",
    ASK_CARBON_STAGING_ACCESS_MODE: "cloudflare_access",
    ASK_CARBON_EDGE_ABUSE_POLICY_ID: "test-edge-abuse-policy",
    ASK_CARBON_LEDGER_AUTHORITY_ID: "ask-carbon-provider-budget-v2",
    ASK_CARBON_ENVIRONMENT: "staging",
    ASK_CARBON_OPERATIONAL_SCOPE_ID: "staging",
    ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD: "50000000",
    ASK_CARBON_MONTHLY_LIMIT_MICRO_USD: "50000000",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_PERIOD: "2026-09",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_SCOPE_ID: "bakeoff",
    ASK_CARBON_LEGACY_CLOSED_AUTHORITY_EXPOSURE_MICRO_USD: "80831",
    ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
    ASK_CARBON_MAX_CONCURRENCY: "4",
    ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "12",
    ASK_CARBON_CLIENT_COUNTER_RETENTION_MS: "86400000",
    ASK_CARBON_MAX_INPUT_TOKENS: "24000",
    ASK_CARBON_MAX_OUTPUT_TOKENS: "1600",
    ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
    ASK_CARBON_PILOT_MAX_REQUESTS_PER_SESSION: "8",
    ASK_CARBON_QA_CONTRACT: "REFERENCED_ANSWER_V1",
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "global", get: () => ({ fetch: (url, options) => ledger.fetch(new Request(url, options)) }) },
    ASK_CARBON_EDGE_RATE_LIMITER: { limit: async () => ({ success: true }) },
    ...overrides,
  } };
};
const ask = (workerRef, env, question, continuation = null) => workerRef.fetch(new Request("https://staging.example/api/ask-carbon", {
  method: "POST",
  headers: { origin: "https://staging.example", "content-type": "application/json", "cf-connecting-ip": "192.0.2.1" },
  body: JSON.stringify({ question, ...(continuation ? { continuation } : {}) }),
}), env);
const chat = (answer) => ({
  id: "chatcmpl-referenced-test",
  model: "google/gemma-4-31B-turbo-TEE",
  choices: [{ index: 0, finish_reason: "stop", message: { role: "assistant", content: JSON.stringify(answer) } }],
  usage: { prompt_tokens: 2000, completion_tokens: 120, total_tokens: 2120 },
});
const withProvider = async (answer, body) => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), body: JSON.parse(options.body) });
    const sent = JSON.parse(options.body);
    return new Response(JSON.stringify(chat(typeof answer === "function" ? answer(sent) : answer)), { status: 200, headers: { "content-type": "application/json" } });
  };
  try { return { result: await body(), requests }; } finally { globalThis.fetch = original; }
};

test("the worker answers from the current documents with checked quotes and GitHub references", async () => {
  resetCorpusMemo();
  const { env } = runtime();
  const worker = createWorker(knowledge, corpusServer());
  // The fake model cites whichever retrieved passage holds the quote, as a
  // faithful model would; the label depends on retrieval order.
  const labelFor = (sent, quote) => {
    const passages = JSON.parse(sent.messages[0].content.split("Passages: ")[1]);
    return passages.find((passage) => passage.text.includes(quote)).id;
  };
  const quote = "does not establish signed paid customers";
  const { result, requests } = await withProvider((sent) => ({
    status: "answered",
    sentences: [{ kind: "fact", text: "Carbon's repository does not establish paying customers.", citations: [{ passage: labelFor(sent, quote), quote }] }],
  }), async () => {
    const response = await ask(worker, env, "Does Carbon have paying customers?");
    return { status: response.status, body: await response.json() };
  });
  assert.equal(result.status, 200);
  const body = result.body;
  assert.equal(body.status, "supported");
  assert.equal(body.answer_contract, "REFERENCED_ANSWER_V1");
  assert.equal(body.documentation_revision, SHA);
  assert.equal(body.answer, "Carbon's repository does not establish paying customers.");
  assert.equal(body.sources.length, 1);
  assert.match(body.sources[0].url, new RegExp(`^https://github.com/carbonphysicsai/Carbon/blob/${SHA}/docs/publications/PROJECT_STATUS.md#L\\d+-L\\d+$`));
  assert.equal(body.sources[0].note, "“does not establish signed paid customers”");
  assert.ok(body.continuation);
  assert.equal(requests.length, 1);
  const sent = requests[0].body;
  assert.equal(sent.response_format.json_schema.name, "ask_carbon_referenced_answer");
  assert.ok(sent.messages[0].content.includes("Commercial position"));
  assert.equal(sent.messages[1].content, "Does Carbon have paying customers?");
});

test("an invented quote reaches the visitor as no reference, not as an answer", async () => {
  resetCorpusMemo();
  const { env } = runtime();
  const { result } = await withProvider({ status: "answered", sentences: [{ kind: "fact", text: "Carbon has three paying customers.", citations: [{ passage: "P1", quote: "Carbon has three paying enterprise customers" }] }] },
    async () => (await ask(createWorker(knowledge, corpusServer()), env, "Does Carbon have paying customers?")).json());
  assert.equal(result.status, "no_reference");
  assert.equal(result.answer, NO_REFERENCE_ANSWER);
  assert.deepEqual(result.sources, []);
});

test("a question the documents cannot match makes no provider call", async () => {
  resetCorpusMemo();
  const { env } = runtime();
  const { result, requests } = await withProvider({ status: "no_reference", sentences: [] },
    async () => (await ask(createWorker(knowledge, corpusServer()), env, "zebra xylophone quartz")).json());
  assert.equal(result.status, "no_reference");
  assert.equal(requests.length, 0);
});

test("health names the Q&A contract and refuses an unknown one or too small an output budget", async () => {
  const health = async (env) => (await createWorker(knowledge, corpusServer()).fetch(new Request("https://staging.example/api/ask-carbon/health"), env)).json();
  const referenced = await health(runtime().env);
  assert.equal(referenced.qa_contract, "REFERENCED_ANSWER_V1");
  assert.deepEqual(referenced.reasons, []);
  const unset = await health(runtime({ ASK_CARBON_QA_CONTRACT: undefined, ASK_CARBON_MAX_OUTPUT_TOKENS: "700" }).env);
  assert.equal(unset.qa_contract, "REVIEWED_CARD_SELECTION");
  assert.deepEqual(unset.reasons, []);
  assert.ok((await health(runtime({ ASK_CARBON_QA_CONTRACT: "FREEFORM" }).env)).reasons.includes("unsupported_qa_contract"));
  assert.ok((await health(runtime({ ASK_CARBON_MAX_OUTPUT_TOKENS: "700" }).env)).reasons.includes("referenced_output_tokens_too_low"));
});

test("conversational sentences carry no claims, and pleasantries alone are not an answer", () => {
  const fact = { kind: "fact", text: "We haven't established paying customers yet.", citations: [{ passage: label, quote: "does not establish signed paid customers" }] };
  const talk = (text) => ({ kind: "conversation", text, citations: [] });
  const kept = verifyReferencedAnswer({ status: "answered", sentences: [talk("Good question."), fact, talk("Happy to go deeper on how we'd run an Evidence Audit if that's useful.")] }, passages);
  assert.equal(kept.status, "supported");
  assert.equal(kept.answer, "Good question. We haven't established paying customers yet. Happy to go deeper on how we'd run an Evidence Audit if that's useful.");
  assert.equal(kept.audit.kept_conversation, 2);
  // A claim dressed as conversation is dropped: numbers and state words.
  for (const smuggled of ["We have 12 pilots running.", "We're already live with customers.", "Our mainnet is coming soon.", "We raised a big round."]) {
    const result = verifyReferencedAnswer({ status: "answered", sentences: [fact, talk(smuggled)] }, passages);
    assert.equal(result.answer, fact.text, smuggled);
    assert.equal(result.audit.rejected[0].reason, "conversation_carries_a_claim");
  }
  assert.equal(verifyReferencedAnswer({ status: "answered", sentences: [talk("Great question!"), talk("Let me explain.")] }, passages).status, "no_reference");
  // At most two conversational sentences.
  assert.equal(verifyReferencedAnswer({ status: "answered", sentences: [fact, talk("One."), talk("Two."), talk("Three.")] }, passages).audit.kept_conversation, 2);
});

test("small talk gets a friendly reply, and a real question inside it does not", () => {
  assert.match(smallTalkAnswer("Hi!"), /^Hi!/);
  assert.match(smallTalkAnswer("thanks, that helps"), /^Glad/);
  assert.equal(smallTalkAnswer("hi, is mainnet live?"), null);
  assert.equal(smallTalkAnswer("thanks. what about motors"), null);
});

test("a follow-up carries the previous question and answer into retrieval and the prompt", async () => {
  resetCorpusMemo();
  const { env } = runtime();
  const worker = createWorker(knowledge, corpusServer());
  const quote = "does not establish signed paid customers";
  const answer = (sent) => {
    const list = JSON.parse(sent.messages[0].content.split("Passages: ")[1]);
    const found = list.find((passage) => passage.text.includes(quote));
    return found
      ? { status: "answered", sentences: [{ kind: "fact", text: "We don't have signed paying customers yet.", citations: [{ passage: found.id, quote }] }] }
      : { status: "no_reference", sentences: [] };
  };
  const { result, requests } = await withProvider(answer, async () => {
    const first = await (await ask(worker, env, "Does Carbon have paying customers?")).json();
    const second = await (await ask(worker, env, "why is that?", first.continuation)).json();
    return { first, second };
  });
  assert.equal(result.first.status, "supported");
  assert.equal(requests.length, 2);
  const prompt = requests[1].body.messages[0].content;
  assert.ok(prompt.includes("Does Carbon have paying customers?"));
  assert.ok(prompt.includes("We don't have signed paying customers yet."));
  assert.ok(prompt.includes("Commercial position"), "the short follow-up retrieved with the earlier question");
});

test("a greeting is answered without reading documents or calling the model", async () => {
  resetCorpusMemo();
  const { env } = runtime();
  const calls = [];
  const { result, requests } = await withProvider({ status: "no_reference", sentences: [] },
    async () => (await ask(createWorker(knowledge, corpusServer(undefined, calls)), env, "Hello there!")).json());
  assert.equal(result.status, "conversation");
  assert.equal(requests.length, 0);
  assert.equal(calls.length, 0);
});
