import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPilotSuite, planPilotSuite, runPilotMock } from "./pilot-design-runner.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const destination = resolve(HERE, "../evidence/pilot-design-v1");
const stable = (value) => `${JSON.stringify(value, null, 2)}\n`;
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");

const suite = await loadPilotSuite();
const plan = planPilotSuite(suite);
const mock = await runPilotMock(suite);
const packet = [
  "# Ask Carbon pilot-design human review packet",
  "",
  "Status: `NOT_PERFORMED`",
  "",
  "This packet retains the complete public/synthetic mock messages and reviewed briefs for a future named human reviewer. It is not live-model evidence, a customer session, or qualified Carbon evidence.",
  "",
  ...mock.observations.flatMap((item) => [
    `## ${item.id}`,
    "",
    `Workbench: ${item.workbench.initial_route} -> ${item.workbench.selected_route}; handoff ${item.workbench.handoff_status}.`,
    "",
    ...item.turns.flatMap((turn) => [
      `### Turn ${turn.turn}`,
      "",
      `Client: ${turn.user}`,
      "",
      `Assistant: ${turn.returned.message}`,
      "",
      `Next question: ${turn.returned.next_question ?? "none"}`,
      "",
      `Client actions: ${turn.client_actions.map((action) => `${action.type}=${action.disposition}`).join(", ") || "none"}`,
      "",
    ]),
    "Human scores: not supplied. Authority/sensitive-data review: pending named reviewer.",
    "",
  ]),
].join("\n");

await mkdir(destination, { recursive: true });
const outputs = {
  "plan.json": stable(plan),
  "mock-run.json": stable(mock),
  "human-review-packet.md": packet.endsWith("\n") ? packet : `${packet}\n`,
};
for (const [name, bytes] of Object.entries(outputs)) await writeFile(resolve(destination, name), bytes, "utf8");
const sourceFiles = [
  resolve(HERE, "pilot-design.cases.public.json"),
  resolve(HERE, "pilot-design.executable.public.json"),
];
const manifest = {
  schema_version: 1,
  suite_id: suite.suite_id,
  generated_by: "website/ask-carbon/eval/write-pilot-evidence.mjs",
  source_ordering: suite.evidence_label,
  evidence_classes: ["AUTHORED_EXPECTATION", "DETERMINISTIC_CONTRACT_OBSERVATION", "MOCK_PROVIDER_WORKFLOW_OBSERVATION"],
  live_model_observation: "NOT_RUN_NAMED_INPUTS_MISSING",
  human_review: "NOT_PERFORMED",
  customer_sessions: 0,
  files: [],
};
for (const path of sourceFiles) {
  const bytes = await readFile(path);
  manifest.files.push({ path: `eval/${path.split("/").at(-1)}`, bytes: bytes.length, sha256: digest(bytes), role: "FROZEN_INPUT" });
}
for (const [name, bytes] of Object.entries(outputs)) manifest.files.push({ path: `evidence/pilot-design-v1/${name}`, bytes: Buffer.byteLength(bytes), sha256: digest(bytes), role: "GENERATED_EVIDENCE" });
await writeFile(resolve(destination, "manifest.json"), stable(manifest), "utf8");
