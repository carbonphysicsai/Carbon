import { readFile } from "node:fs/promises";
import { readCorpusAtRevision } from "./website/ask-carbon/eval/referenced-eval.mjs";
import { PROVIDERS } from "./website/ask-carbon/worker/providers.mjs";
import { referencedInstructions, referencedSchema, retrieve } from "./website/ask-carbon/worker/referenced.mjs";
const [model, ...qs] = process.argv.slice(2);
const corpus = readCorpusAtRevision("origin/main");
for (const q of qs) {
  const passages = retrieve(corpus.passages, q);
  const body = PROVIDERS.chutes_chat_completions.buildBody({ request_model: model, temperature: 0 }, { instructions: referencedInstructions(passages), userText: q, schemaName: "ask_carbon_referenced_answer", schema: referencedSchema(passages.length), maxOutputTokens: 1600 });
  const r = await fetch("https://llm.chutes.ai/v1/chat/completions", { method: "POST", headers: { authorization: `Bearer ${(await readFile("/home/carbon/.carbon/private/chutes/ask-carbon-eval.key", "utf8")).trim()}`, "content-type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  console.log("Q:", q, "| passages:", passages.length, "| prompt chars:", body.messages[0].content.length, "| finish:", j.choices?.[0]?.finish_reason);
  console.log(String(j.choices?.[0]?.message?.content ?? JSON.stringify(j.error ?? j)).slice(0, 900), "\n");
}
