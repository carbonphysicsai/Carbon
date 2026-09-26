"use strict";
// Live synthetic rehearsal of external model processing, run by hand, never by
// CI (it is not a test_*.cjs file). One synthetic record, received the relayed
// way (Path A), is opted in with a synthetic opt-in and sent, by one explicit
// reviewer request, to the scheduled Chutes model. No client content exists or
// is sent: every reference is synthetic, and the store refuses anything else.
//
//   CARBON_TEAM_MODEL_CREDENTIAL_FILE=/path/to/chutes.key node tests/live_model_provider_rehearsal.cjs
//
// Prints a JSON observation: the release entry, the model's answer and usage.
// The credential is read from its file at send time and appears nowhere.
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const P = require("../tools/team_model_provider.cjs");
const { enrolled, mailed, openStore, principalFor, scoping } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731-TEE";

async function main() {
  const credentialFile = process.env.CARBON_TEAM_MODEL_CREDENTIAL_FILE;
  if (!credentialFile) throw Error("Set CARBON_TEAM_MODEL_CREDENTIAL_FILE");
  const tokens = { receiver: "rehearsal-receiver-token-01", reviewer: "rehearsal-reviewer-token-01", steward: "rehearsal-steward-token-001" };
  const directory = new StaffDirectory([
    enrolled("rehearsal-receiver", "carbon-fit", ["INTAKE_RECEIVER"], tokens.receiver),
    enrolled("rehearsal-reviewer", "carbon-fit", ["TEAM_REVIEWER"], tokens.reviewer),
    enrolled("rehearsal-steward", "carbon-fit", ["DATA_STEWARD"], tokens.steward),
  ]);
  const as = (name) => principalFor(directory, tokens[name]);
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-model-rehearsal-")), "store.json"));
  const brief = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "intake/fixtures/fresh_burgers_v1.json"), "utf8"));
  const raw = JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((f) => [f, ""])), bounded_first_pilot: "Synthetic public-development rehearsal." },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  });
  const receipt = await store.accept(raw, "rehearsal-001", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  store.recordModelOptIn(receipt.inquiry_id, P.signedOptIn({ ref: "synthetic-opt-in-rehearsal", provider: "chutes" }), as("steward"));
  const provider = P.scheduledProvider({ provider: "chutes", model: MODEL, credentialFile });
  const started = Date.now();
  const answer = await store.modelAssist(
    receipt.inquiry_id,
    { purpose: "Synthetic rehearsal of external model processing", question: "In three sentences: what is this brief asking for, and what does it leave unresolved?" },
    as("reviewer"),
    provider,
  );
  const observation = {
    evidence_class: "PRIVATE_SYNTHETIC_LIVE_MODEL_OBSERVATION",
    observed_at: new Date().toISOString(),
    provider: answer.provider,
    model: answer.model,
    endpoint: provider.endpoint,
    elapsed_ms: Date.now() - started,
    usage: answer.usage,
    answer: answer.content,
    release: store.releases(as("steward"), { inquiryId: receipt.inquiry_id }),
    model_processing: store.read(receipt.inquiry_id, as("reviewer")).model_processing,
  };
  const text = JSON.stringify(observation, null, 2);
  if (text.includes(fs.readFileSync(credentialFile, "utf8").trim())) throw Error("The credential reached the observation");
  process.stdout.write(text + "\n");
}

main().catch((error) => {
  process.stderr.write((error.outcome ? error.outcome + ": " : "") + error.message + "\n");
  process.exit(1);
});
