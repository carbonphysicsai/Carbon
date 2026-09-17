import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { loadPilotSuite, runPilotLive } from "./pilot-design-runner.mjs";

const argument = (name, fallback = null) => {
  const prefixed = process.argv.find((value) => value.startsWith(`--${name}=`));
  if (prefixed) return prefixed.slice(name.length + 3);
  const position = process.argv.indexOf(`--${name}`);
  return position >= 0 ? process.argv[position + 1] : fallback;
};
const stable = (value) => `${JSON.stringify(value, null, 2)}\n`;
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const outputDirectory = argument("output-dir");
if (!outputDirectory) throw Error("Live evidence requires an explicit new --output-dir.");

const fullSuite = await loadPilotSuite();
const requestedCaseIds = argument("case-ids")?.split(",").map((value) => value.trim()).filter(Boolean) ?? [];
const knownCaseIds = new Set(fullSuite.cases.map((item) => item.id));
if (requestedCaseIds.some((id) => !knownCaseIds.has(id)) || new Set(requestedCaseIds).size !== requestedCaseIds.length) {
  throw Error("Live evidence case selection contains an unknown or duplicate case ID.");
}
const suite = requestedCaseIds.length
  ? { ...fullSuite, cases: fullSuite.cases.filter((item) => requestedCaseIds.includes(item.id)) }
  : fullSuite;
const result = await runPilotLive(suite, {
  endpoint: argument("endpoint", process.env.ASK_CARBON_EVAL_ENDPOINT),
  origin: argument("origin", process.env.ASK_CARBON_EVAL_ORIGIN),
  accessClientId: process.env.ASK_CARBON_ACCESS_CLIENT_ID,
  accessClientSecret: process.env.ASK_CARBON_ACCESS_CLIENT_SECRET,
  basicAuth: process.env.ASK_CARBON_STAGING_BASIC_AUTH,
  operatorSecret: process.env.ASK_CARBON_STAGING_OPERATOR_SECRET,
  runId: argument("run-id", null),
});

const reviewPacket = [
  "# Ask Carbon private synthetic pilot-design review",
  "",
  `Run: \`${result.run_id}\``,
  `Model: \`${result.staging.model_config_id}\``,
  `Knowledge: \`${result.staging.knowledge_version}\``,
  "Human quality status: `NAMED_PENDING_CONFIRMATION_AND_REVIEW`",
  "Customer sessions: `0` (public/synthetic scenarios only)",
  "",
  "Ryan reviews engineering relevance and pilot-design quality. Nick reviews clarity, friction, and prospective-client usefulness. Each reviewer should mark the packet ACCEPT, CHANGE with a named defect, or REJECT with a reason. No response is recorded by this file.",
  "",
  ...result.observations.flatMap((observation) => [
    `## ${observation.id}`,
    "",
    `Workbench: ${observation.workbench.initial_route} -> ${observation.workbench.selected_route}; handoff ${observation.workbench.handoff_status}.`,
    "",
    ...observation.turns.flatMap((turn) => [
      `### Turn ${turn.turn}`,
      "",
      `Client: ${turn.user}`,
      "",
      `Assistant: ${turn.returned?.message ?? `No supported answer (${turn.returned?.error?.code ?? turn.disposition}).`}`,
      "",
      `Next question: ${turn.returned?.next_question ?? "none"}`,
      "",
      `Proposals: ${turn.returned?.proposals?.map((item) => `${item.field} = ${item.value}`).join(" | ") || "none"}`,
      "",
      `Client actions: ${turn.client_actions.map((item) => `${item.type}=${item.disposition}`).join(", ") || "none"}`,
      "",
      `Latency: ${turn.latency_ms} ms`,
      "",
    ]),
    `Final brief summary:\n\n${observation.final_brief.brief.summary.text}`,
    "",
    `Unresolved: ${observation.final_brief.unresolved_assumptions.join(" | ") || "none stated by assistant"}`,
    "",
    "Ryan disposition: PENDING. Nick disposition: PENDING. Authority/sensitive-data check: PENDING.",
    "",
  ]),
  "## Authority ceiling",
  "",
  "These are private synthetic live-model observations. They are not customer usability evidence, qualified Carbon evidence, scientific acceptance, rights authorization, execution approval, or public-release approval.",
  "",
].join("\n");

await mkdir(outputDirectory, { recursive: true });
const outputs = {
  "live-run.json": stable(result),
  "human-review-packet-live.md": reviewPacket,
};
for (const [name, bytes] of Object.entries(outputs)) await writeFile(resolve(outputDirectory, name), bytes, { encoding: "utf8", flag: "wx" });
const suiteBytes = await readFile(new URL("./pilot-design.executable.public.json", import.meta.url));
const manifest = {
  schema_version: 1,
  run_id: result.run_id,
  generated_by: "website/ask-carbon/eval/write-pilot-live-evidence.mjs",
  evidence_class: "PRIVATE_SYNTHETIC_LIVE_MODEL_OBSERVATION",
  selected_case_ids: suite.cases.map((item) => item.id),
  human_review: "NAMED_PENDING_CONFIRMATION_AND_REVIEW",
  customer_sessions: 0,
  source: { path: "eval/pilot-design.executable.public.json", bytes: suiteBytes.length, sha256: digest(suiteBytes) },
  files: Object.entries(outputs).map(([name, bytes]) => ({ name, bytes: Buffer.byteLength(bytes), sha256: digest(bytes) })),
};
await writeFile(resolve(outputDirectory, "live-manifest.json"), stable(manifest), { encoding: "utf8", flag: "wx" });
process.stdout.write(`${stable({ output_directory: outputDirectory, run_id: result.run_id, files: [...Object.keys(outputs), "live-manifest.json"] })}`);
