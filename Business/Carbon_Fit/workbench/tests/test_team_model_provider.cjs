"use strict";
// External model processing of a client record (owner direction, 26 September
// 2026). Chutes is named in the provider schedule; the guard against automatic
// transfer stays; the switch is per client and off by default. The owner lifted
// the synthetic-only restriction the same day: a real record is sent only with
// that client's own signed opt-in, and a synthetic opt-in never opens one.
// Every refusal is paired with the same call going through, and no test here
// reaches a network: the provider's fetch is a recorder.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const { createIntakeServer } = require("../tools/team_intake_server.cjs");
const { scopingBasis } = require("../tools/team_record_basis.cjs");
const P = require("../tools/team_model_provider.cjs");
const { enrolled, mailed, openStore, principalFor, scoping } = require("./staff_fixture.cjs");
const I = require("../src/intake.js");

const ROOT = path.resolve(__dirname, "..");
const MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731-TEE";
const TOKENS = { receiver: "model-receiver-token-0001", reviewer: "model-reviewer-token-0001", steward: "model-steward-token-00001" };
const DIRECTORY = new StaffDirectory([
  enrolled("model-receiver", "carbon-fit", ["INTAKE_RECEIVER"], TOKENS.receiver),
  enrolled("model-reviewer", "carbon-fit", ["TEAM_REVIEWER"], TOKENS.reviewer),
  enrolled("model-steward", "carbon-fit", ["DATA_STEWARD"], TOKENS.steward),
]);
const as = (name) => principalFor(DIRECTORY, TOKENS[name]);
const BRIEF_SENTINEL = "SYNTHETIC-BRIEF-SENTINEL-7Q2";
const CONTACT_SENTINEL = "contact-sentinel-9x4@example.invalid";
const CREDENTIAL = "synthetic-credential-" + "k3v8".repeat(8);
const ASK = { purpose: "Synthetic review question", question: "What does the brief leave unresolved?" };

function raw() {
  const brief = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8"));
  brief.draft_id = "model-" + crypto.randomBytes(4).toString("hex");
  return JSON.stringify({
    schema_version: I.REVIEW_VERSION,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((f) => [f, ""])), bounded_first_pilot: "Synthetic " + BRIEF_SENTINEL },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((f) => "pilot." + f)].map((field) => ({ field, origin: "UNKNOWN", suggestion_id: null })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "Synthetic Contact", email: CONTACT_SENTINEL, organization: "Synthetic Org" },
    local_scope: I.REVIEW_SCOPE,
  });
}

function credentialFile(mode = 0o600) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-model-cred-"));
  const file = path.join(dir, "provider.key");
  fs.writeFileSync(file, CREDENTIAL + "\n", { mode });
  fs.chmodSync(file, mode);
  return file;
}

/** A recording fetch: every call is kept, and it answers like a provider. */
function recorder({ fail = null } = {}) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init, body: JSON.parse(init.body) });
    if (fail) throw fail;
    return new Response(JSON.stringify({ choices: [{ message: { role: "assistant", content: "Synthetic answer." } }], usage: { prompt_tokens: 10, completion_tokens: 3 } }), { status: 200 });
  };
  return { calls, fetch };
}

function world(options = {}) {
  const store = openStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), "carbon-model-")), "store.json"), options);
  const rec = recorder(options.recorder);
  const provider = P.scheduledProvider({ provider: "chutes", model: MODEL, credentialFile: options.credentialFile || credentialFile(), fetch: rec.fetch });
  return { store, provider, calls: rec.calls };
}

const optIn = (ref = "synthetic-opt-in-0001") => P.signedOptIn({ ref, provider: "chutes" });

test("the schedule names Chutes and the model confirmed from the live API", () => {
  const schedule = P.loadSchedule();
  const chutes = schedule.providers.find((entry) => entry.id === "chutes");
  assert.equal(chutes.endpoint, "https://llm.chutes.ai/v1");
  const model = chutes.models.find((entry) => entry.id === MODEL);
  assert.equal(model.context_length, 1048576);
  assert.equal(model.confidential_compute, true);
  assert.deepEqual(schedule.conditions.map((c) => c.state), ["SATISFIED_BY_THIS_ENTRY", "OWNER_DETERMINATION_2026_09_26", "REQUIRED_PER_CLIENT_DEFAULT_OFF"]);
  // Anything not in the schedule cannot be built.
  assert.throws(() => P.scheduledProvider({ provider: "engy", model: MODEL, credentialFile: "x" }), /not in the provider schedule/);
  assert.throws(() => P.scheduledProvider({ provider: "chutes", model: "deepseek-ai/DeepSeek-V3.2", credentialFile: "x" }), /model is not in the provider schedule/);
  assert.throws(() => P.signedOptIn({ ref: "synthetic-opt-in-0001", provider: "engy" }), /provider in the provider schedule/);
  // Specimen: the scheduled pair builds, and sends to the scheduled endpoint.
  assert.equal(P.scheduledProvider({ provider: "chutes", model: MODEL, credentialFile: "x" }).endpoint, "https://llm.chutes.ai/v1/chat/completions");
});

test("the switch is off by default; a recorded opt-in turns it on", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "model-001", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  assert.equal(w.store.read(receipt.inquiry_id, as("reviewer")).model_processing.active, false);
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider), /switch is off/);
  assert.equal(w.calls.length, 0);
  // Specimen: with the client's opt-in recorded, the same request is sent.
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  const answer = await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider);
  assert.equal(answer.content, "Synthetic answer.");
  assert.equal(w.calls.length, 1);
});

test("nothing is sent automatically: only an explicit request reaches the provider", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "model-002", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  // Opted in, read, exported, reviewed: still nothing sent.
  w.store.read(receipt.inquiry_id, as("reviewer"));
  w.store.export(receipt.inquiry_id, as("reviewer"), { recipient: { kind: "CARBON_STAFF", ref: "synthetic-reviewer" }, purpose: "Team review" });
  const version = w.store.read(receipt.inquiry_id, as("reviewer")).version;
  w.store.update(receipt.inquiry_id, version, { assigned_reviewer: "model-reviewer", note: "Synthetic note", queue_state: "UNDER_REVIEW" }, as("reviewer"));
  assert.equal(w.calls.length, 0);
  // The store holds no provider: the only call site is modelAssist.
  const source = fs.readFileSync(path.join(ROOT, "tools/team_intake_store.cjs"), "utf8");
  assert.equal(source.match(/\.complete\(/g).length, 1);
  assert.ok(/async modelAssist\([^]*?provider\.complete\(/.test(source));
  // Specimen: the explicit request is the one that sends.
  await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider);
  assert.equal(w.calls.length, 1);
});

test("a real client's record is sent only with that client's signed opt-in, under counsel's standard", async () => {
  const counsel = "COUNSEL-STANDARD-EXAMPLE";
  const accounts = new StaffDirectory([
    { ...enrolled("real-receiver", "carbon-fit", ["INTAKE_RECEIVER"], "real-receiver-token-00001"), screening: { standard: counsel, ref: "screening-record-1" } },
    { ...enrolled("real-reviewer", "carbon-fit", ["TEAM_REVIEWER"], "real-reviewer-token-00001"), screening: { standard: counsel, ref: "screening-record-2" } },
    { ...enrolled("real-steward", "carbon-fit", ["DATA_STEWARD"], "real-steward-token-000001"), screening: { standard: counsel, ref: "screening-record-3" } },
  ]);
  const who = (token) => principalFor(accounts, token);
  const receiver = () => who("real-receiver-token-00001");
  const reviewer = () => who("real-reviewer-token-00001");
  const steward = () => who("real-steward-token-000001");
  const w = world({ screeningStandard: counsel });
  const real = await w.store.accept(raw(), "model-real-1", receiver(), scopingBasis({ nda: "NDA-2026-0042" }), mailed(), "EC-DETERMINATION-17");
  // Off by default for a real record too.
  await assert.rejects(w.store.modelAssist(real.inquiry_id, ASK, reviewer(), w.provider), /switch is off/);
  // A synthetic opt-in cannot open a real record, whichever reference is real.
  for (const [index, [basis, ec]] of [
    [scopingBasis({ nda: "NDA-2026-0042" }), "synthetic-ec-0001"],
    [scopingBasis({ nda: "synthetic-nda-0001" }), "EC-DETERMINATION-17"],
  ].entries()) {
    const mixed = await w.store.accept(raw(), "model-mixed-" + index, receiver(), basis, mailed(), ec);
    assert.throws(() => w.store.recordModelOptIn(mixed.inquiry_id, optIn("synthetic-opt-in-0001"), steward()), /synthetic opt-in cannot open a real client's record/);
  }
  assert.throws(() => w.store.recordModelOptIn(real.inquiry_id, optIn("synthetic-opt-in-0001"), steward()), /synthetic opt-in cannot open/);
  assert.equal(w.calls.length, 0);
  // Specimen: the client's signed opt-in opens the same real record.
  w.store.recordModelOptIn(real.inquiry_id, optIn("OPT-IN-SIGNED-2026-0001"), steward());
  await w.store.modelAssist(real.inquiry_id, ASK, reviewer(), w.provider);
  assert.equal(w.calls.length, 1);
  const [release] = w.store.releases(steward(), { inquiryId: real.inquiry_id });
  assert.equal(release.opt_in_ref, "OPT-IN-SIGNED-2026-0001");
});

test("under the synthetic development standard a real record stays unreachable, opt-in or not", async () => {
  const { SYNTHETIC_STANDARD_PREFIX } = require("../tools/team_intake_store.cjs");
  const standard = SYNTHETIC_STANDARD_PREFIX + "2026-09";
  const screened = (account) => ({ ...account, screening: { standard, ref: "synthetic-screening-" + account.principal } });
  const accounts = new StaffDirectory([
    screened(enrolled("dev-receiver", "carbon-fit", ["INTAKE_RECEIVER"], "dev-receiver-token-000001")),
    screened(enrolled("dev-reviewer", "carbon-fit", ["TEAM_REVIEWER"], "dev-reviewer-token-000001")),
    screened(enrolled("dev-steward", "carbon-fit", ["DATA_STEWARD"], "dev-steward-token-0000001")),
  ]);
  const who = (token) => principalFor(accounts, token);
  const w = world({ screeningStandard: standard });
  const real = await w.store.accept(raw(), "model-dev-1", who("dev-receiver-token-000001"), scopingBasis({ nda: "NDA-2026-0042" }), mailed(), "EC-DETERMINATION-17");
  w.store.recordModelOptIn(real.inquiry_id, optIn("OPT-IN-SIGNED-2026-0001"), who("dev-steward-token-0000001"));
  await assert.rejects(w.store.modelAssist(real.inquiry_id, ASK, who("dev-reviewer-token-000001"), w.provider), /synthetic records only/);
  assert.equal(w.calls.length, 0);
  // Specimen: a synthetic record under the same standard is sent.
  const synthetic = await w.store.accept(raw(), "model-dev-2", who("dev-receiver-token-000001"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(synthetic.inquiry_id, optIn(), who("dev-steward-token-0000001"));
  await w.store.modelAssist(synthetic.inquiry_id, ASK, who("dev-reviewer-token-000001"), w.provider);
  assert.equal(w.calls.length, 1);
});

test("an opt-in and a provider are issued, not written: copied literals are refused", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "model-003", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  assert.throws(() => w.store.recordModelOptIn(receipt.inquiry_id, { ref: "synthetic-opt-in-0001", provider: "chutes" }, as("steward")), /signed opt-in/);
  assert.throws(() => new P.ModelOptIn(Symbol("forged"), {}), /signed opt-in/);
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  let forgedCalls = 0;
  const forged = { id: "chutes", model: MODEL, complete: async () => { forgedCalls += 1; return { content: "" }; } };
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), forged), /built from the provider schedule/);
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), null), /No model provider is configured/);
  assert.equal(forgedCalls, 0);
  // Roles: a reviewer cannot record an opt-in; a steward cannot send.
  assert.throws(() => w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("reviewer")), /not authorized/);
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("steward"), w.provider), /not authorized/);
  // Specimen: the issued provider, by the reviewer, is sent.
  await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider);
  assert.equal(w.calls.length, 1);
});

test("an opt-in for another scheduled provider does not open this one", async () => {
  const schedule = JSON.parse(JSON.stringify(P.loadSchedule()));
  schedule.providers.push({ id: "second", name: "Synthetic second", endpoint: "https://second.example.invalid/v1", models: [{ id: "synthetic-model" }] });
  const w = world();
  const receipt = await w.store.accept(raw(), "model-004", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(receipt.inquiry_id, P.signedOptIn({ ref: "synthetic-opt-in-0002", provider: "second" }, schedule), as("steward"));
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider), /different provider/);
  assert.equal(w.calls.length, 0);
});

test("withdrawal turns the switch off again, and the history keeps both events", async () => {
  const w = world();
  const receipt = await w.store.accept(raw(), "model-005", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider);
  const off = w.store.withdrawModelOptIn(receipt.inquiry_id, { reason: "Synthetic client withdrew" }, as("steward"));
  assert.equal(off.active, false);
  assert.deepEqual(off.history.map((e) => [e.seq, e.event]), [[1, "OPTED_IN"], [2, "WITHDRAWN"]]);
  await assert.rejects(w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider), /switch is off/);
  assert.equal(w.calls.length, 1);
});

test("the release is logged before sending; the request carries the brief, not the contact or the credential", async () => {
  const w = world({ recorder: { fail: Error("connect ECONNREFUSED " + CREDENTIAL) } });
  const receipt = await w.store.accept(raw(), "model-006", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  const failure = await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider).catch((error) => error);
  assert.equal(failure.outcome, "UNREACHABLE");
  assert.ok(!failure.message.includes(CREDENTIAL));
  // Logged although the send failed: the attempt is a release.
  const [release] = w.store.releases(as("steward"), { inquiryId: receipt.inquiry_id });
  assert.equal(release.channel, "EXTERNAL_MODEL");
  assert.deepEqual(release.recipient, { kind: "MODEL_PROVIDER", ref: "chutes:" + MODEL });
  assert.equal(release.opt_in_ref, "synthetic-opt-in-0001");
  const [call] = w.calls;
  assert.equal(call.url, "https://llm.chutes.ai/v1/chat/completions");
  assert.equal(call.body.model, MODEL);
  assert.equal(release.artifact_sha256, "sha256:" + crypto.createHash("sha256").update(JSON.stringify({ model: MODEL, messages: call.body.messages })).digest("hex"));
  const sent = JSON.stringify(call.body);
  assert.ok(sent.includes(BRIEF_SENTINEL));
  assert.ok(!sent.includes(CONTACT_SENTINEL));
  // Specimen: the contact is in the record; it is withheld, not missing.
  assert.ok(JSON.stringify(w.store.read(receipt.inquiry_id, as("reviewer"))).includes(CONTACT_SENTINEL));
  // The credential went in the header, and nowhere that is kept.
  assert.equal(call.init.headers.authorization, "Bearer " + CREDENTIAL);
  assert.ok(!sent.includes(CREDENTIAL));
  assert.ok(!JSON.stringify(w.store.releases(as("steward"))).includes(CREDENTIAL));
  assert.ok(!fs.readFileSync(w.store.filePath, "utf8").includes(CREDENTIAL));
});

test("an unsafe credential file is refused before anything is sent", async () => {
  for (const unsafe of [credentialFile(0o644), (() => { const target = credentialFile(); const link = target + ".link"; fs.symlinkSync(target, link); return link; })()]) {
    const w = world({ credentialFile: unsafe });
    const receipt = await w.store.accept(raw(), "model-007", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
    w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
    const failure = await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider).catch((error) => error);
    assert.equal(failure.outcome, "NOT_ATTEMPTED_CREDENTIAL_UNSAFE");
    assert.equal(w.calls.length, 0);
  }
  // Specimen: the same file at 0600, not a link, is read and sent.
  const w = world({ credentialFile: credentialFile(0o600) });
  const receipt = await w.store.accept(raw(), "model-008", as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
  w.store.recordModelOptIn(receipt.inquiry_id, optIn(), as("steward"));
  await w.store.modelAssist(receipt.inquiry_id, ASK, as("reviewer"), w.provider);
  assert.equal(w.calls.length, 1);
});

test("the receiver: opt-in and model requests over HTTP, and 501 when no provider is configured", async () => {
  for (const configured of [false, true]) {
    const w = world();
    const receipt = await w.store.accept(raw(), "model-http-" + configured, as("receiver"), scoping(), mailed(), "synthetic-ec-0001");
    const server = createIntakeServer({ store: w.store, users: DIRECTORY, modelProvider: configured ? w.provider : null });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    const { totp } = require("../tools/team_staff_directory.cjs");
    const { secretFor } = require("./staff_fixture.cjs");
    const session = async (token) => {
      const opened = await fetch(base + "/private/session", {
        method: "POST",
        headers: { authorization: "Bearer " + token, "content-type": "application/json" },
        body: JSON.stringify({ code: totp(secretFor(token), Date.now()) }),
      });
      return "Bearer " + (await opened.json()).session_token;
    };
    const post = (who, suffix, value) =>
      fetch(`${base}/private/intake/${receipt.inquiry_id}/${suffix}`, { method: "POST", headers: { authorization: who, "content-type": "application/json" }, body: JSON.stringify(value) });
    try {
      const reviewer = await session(TOKENS.reviewer);
      assert.equal((await post(reviewer, "model-assist", ASK)).status, configured ? 403 : 501);
      const steward = await session(TOKENS.steward);
      assert.equal((await post(steward, "model-opt-in", { ref: "synthetic-opt-in-0001", provider: "chutes" })).status, 200);
      const answered = await post(reviewer, "model-assist", ASK);
      assert.equal(answered.status, configured ? 200 : 501);
      if (configured) assert.equal((await answered.json()).content, "Synthetic answer.");
      assert.equal(w.calls.length, configured ? 1 : 0);
    } finally {
      server.close();
    }
  }
});
