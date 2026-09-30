"use strict";
// GOAL-WORKBENCH-16 slice 1: the live Workbench's problem builder inside the
// Pilot Designer, carried by a v2 brief that the receiver and the internal
// Workbench accept, with every v1 brief and package unchanged.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const F = require("../src/engine.js");
const I = require("../src/intake.js");
const G = require("../src/workflow.js");
const E = require("../src/problem/engine.js");
const B = require("../src/system_builder.js");
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
const { enrolled, exportRef, mailed, openStore, principalFor, scoping } = require("./staff_fixture.cjs");

const ROOT = path.resolve(__dirname, "..");
const ATLAS = JSON.parse(fs.readFileSync(path.join(ROOT, "data/atlas.json")));
const IDS = ATLAS.opportunities.map((item) => item.id);
const reader = (raw) => F.readWorkspace(raw, IDS, ATLAS.source.sha256);
const component = () => ({ schema_version: F.WORKSPACE_VERSION, application_version: F.APP_VERSION, source_sha256: ATLAS.source.sha256, evidence_catalog: [], drafts: [], shortlist: [], migration_receipts: [] });
const inspect = (raw) => I.inspect(raw, F.strictJsonParse);
const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");

// The illustrative cooling example's structure, words removed as the builder
// removes them.
function coolingSystem() {
  const system = E.template("cooling", "job_test").problem;
  for (const key of I.SYSTEM_WORDS) system[key] = "";
  return system;
}

function v2Draft(system = coolingSystem(), revision = "rev-001") {
  const draft = I.newDraft("pilot-system-001", revision, system);
  draft.answers.intended_decision = { state: "VALUE", value: "Choose a cold-plate channel layout for the next board.", origin: "USER_ENTERED_LOCAL" };
  draft.answers.requested_result = { state: "VALUE", value: "Predict peak junction temperature across flow rates.", origin: "USER_ENTERED_LOCAL" };
  draft.summary = I.summaryFor(draft);
  return I.validateDraft(draft);
}

function reviewed(brief, version = I.REVIEW_VERSION_V2) {
  return {
    schema_version: version,
    brief,
    pilot: { label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])) },
    field_provenance: [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((field) => `pilot.${field}`)].map((field) => ({
      field,
      origin: brief.answers[field]?.state === "VALUE" ? "CLIENT_TYPED" : "UNKNOWN",
      suggestion_id: null,
    })),
    accepted_suggestions: [],
    unresolved_assumptions: [],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  };
}

test("the problem engine is the live Workbench's, byte for byte", () => {
  const record = JSON.parse(fs.readFileSync(path.join(ROOT, "data/problem_engine_provenance.json")));
  assert.equal(record.problem_schema, E.VERSION);
  assert.equal(record.rules, E.RULES);
  assert.deepEqual(Object.keys(record.files).sort(), ["src/problem/cooling-v02.js", "src/problem/engine.js"]);
  for (const [file, entry] of Object.entries(record.files))
    assert.equal(sha256(fs.readFileSync(path.join(ROOT, file))), entry.sha256, file);
});

test("a v2 brief carries the system, and its summary reports it", () => {
  const draft = v2Draft();
  assert.equal(draft.schema_version, I.DRAFT_VERSION_V2);
  assert.equal(draft.summary.mapping_version, I.MAPPING_VERSION_V2);
  assert.equal(draft.source.mapping_version, I.MAPPING_VERSION_V2);
  assert.match(draft.summary.text, /Physical components: .+\(Heat transfer\)/);
  assert.match(draft.summary.text, /Outputs: /);
  // An empty system is still a v2 brief, and still validates.
  const blank = I.newDraft("pilot-blank", "rev-001", null);
  blank.summary = I.summaryFor(blank);
  assert.equal(I.validateDraft(blank).schema_version, I.DRAFT_VERSION_V2);
  assert.match(blank.summary.text, /Physical components: none listed/);
});

test("the canonical identity covers the system, so a system edit is a new revision", async () => {
  const first = v2Draft();
  const changed = coolingSystem();
  changed.outputs[0].unit = "degC";
  const second = v2Draft(changed);
  const [a, b] = await Promise.all([first, second].map((draft) => I.sha256(I.canonical(draft))));
  assert.notEqual(a, b);
});

test("the system holds structure only: its words belong to the brief", () => {
  for (const key of I.SYSTEM_WORDS) {
    const system = coolingSystem();
    system[key] = "a second copy of the words";
    assert.throws(() => v2Draft(system), new RegExp("belongs to the brief"));
  }
});

test("a malformed system is refused by the problem model's own rules", () => {
  const dangling = coolingSystem();
  dangling.couplings.push({ ...E.row("couplings", "cpl_dangling"), from: "missing-component", to: dangling.components[0].id });
  assert.throws(() => v2Draft(dangling), /missing component/);
  const extra = coolingSystem();
  extra.unexpected = true;
  assert.throws(() => v2Draft(extra), /missing or unsupported fields/);
  const draft = v2Draft();
  draft.system.sourceRefs = ["PHY-Z99"];
  assert.throws(() => I.validateDraft(draft), /atlas source ID/);
});

test("a summary that does not match the system is refused", () => {
  const draft = v2Draft();
  draft.system.outputs[0].name = "edited after the summary was made";
  assert.throws(() => I.validateDraft(draft), /deterministic mapping/);
});

test("v1 briefs and packages keep their meaning; versions cannot be mixed", async () => {
  const v1Raw = fs.readFileSync(path.join(ROOT, "intake/fixtures/existing_method_v1.json"), "utf8");
  const v1 = JSON.parse(v1Raw);
  assert.equal(I.validateDraft(v1).schema_version, I.DRAFT_VERSION);
  assert.equal(I.validateReviewedPackage(reviewed(v1, I.REVIEW_VERSION)).brief.schema_version, I.DRAFT_VERSION);
  // A v1 brief's canonical digest is what it was before v2 existed.
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/fixture_manifest.json")));
  const recorded = JSON.stringify(manifest).match(/sha256:[0-9a-f]{64}/g) || [];
  assert.ok(recorded.includes(await I.sha256(I.canonical(v1))), "v1 canonical digest is unchanged");
  assert.throws(() => I.validateReviewedPackage(reviewed(v1, I.REVIEW_VERSION_V2)), /versions disagree/);
  assert.throws(() => I.validateReviewedPackage(reviewed(v2Draft(), I.REVIEW_VERSION)), /versions disagree/);
  // A v1 brief cannot carry a system, and a v2 brief must.
  assert.throws(() => I.validateDraft({ ...v1, system: coolingSystem() }), /unsupported or missing fields/);
  const { system, ...withoutSystem } = v2Draft();
  assert.ok(system);
  assert.throws(() => I.validateDraft(withoutSystem), /unsupported or missing fields/);
});

test("the internal Workbench imports a v2 package and maps its system into the job", async () => {
  const raw = JSON.stringify(reviewed(v2Draft()), null, 2);
  const inspection = await inspect(raw);
  assert.equal(inspection.transport_kind, "REVIEWED_PACKAGE");
  const workspace = G.newWorkspace(component());
  const preview = G.previewIntakeImport(workspace, inspection);
  assert.equal(preview.action, "CREATE_NEW_JOB");
  G.commitIntakeImport(workspace, inspection, preview);
  const job = workspace.jobs[0], design = job.designs[0];
  const system = inspection.draft.system;
  assert.equal(design.route_plan.route, "UNASSESSED");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  for (const output of system.outputs) assert.ok(design.scope.outputs.includes(output.name), output.name);
  for (const input of system.inputs) assert.ok(design.scope.conditions.includes(input.name), input.name);
  const fromSystem = design.requirements.filter((r) => /#system\.requirements\./.test(r.source_reference));
  assert.equal(fromSystem.length, system.requirements.length);
  for (const [index, item] of fromSystem.entries()) {
    const source = system.requirements[index];
    assert.equal(item.kind, source.kind === "physical" ? "MATERIAL" : "PREFERENCE");
  }
  // The job survives the workspace's own save and reopen, which re-inspects
  // the stored package.
  const saved = G.readWorkspace(JSON.stringify(workspace), reader, "VERIFIED_WEB_CRYPTO");
  await G.revalidateIntakeRecords(saved);
  assert.equal(saved.jobs[0].intake_records[0].validated_draft.schema_version, I.DRAFT_VERSION_V2);
  assert.equal(G.previewIntakeImport(saved, inspection).action, "EXACT_REPLAY");
});

test("mapped requirements stop at the job's limit of sixteen", () => {
  const system = coolingSystem();
  const output = system.outputs[0].id;
  system.requirements = Array.from({ length: 20 }, (_, index) => ({ ...E.row("requirements", "req_many_" + index), output, operator: "max", target: index }));
  const draft = v2Draft(system);
  const mapped = I.mapDraft(draft, "sha256:" + "0".repeat(64));
  assert.equal(mapped.requirements.length, 16);
});

test("the private receiver accepts a v2 package through the same checks", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "carbon-pilot-system-"));
  const staff = new StaffDirectory([enrolled("synthetic-receiver", "carbon-fit", ["INTAKE_RECEIVER"], "synthetic-receiver-token-0001")]);
  const receiver = principalFor(staff, "synthetic-receiver-token-0001");
  const store = openStore(path.join(directory, "store.json"));
  const raw = JSON.stringify(reviewed(v2Draft()), null, 2);
  const receipt = await store.accept(raw, "pilot-system-key-001", receiver, scoping(), mailed(), exportRef());
  assert.equal(receipt.status, "PERSISTED_PRIVATE_SYNTHETIC");
  assert.equal(receipt.authority, "RECEIPT_ONLY_NOT_SCIENTIFIC_COMMERCIAL_OR_EXECUTION_APPROVAL");
  // A package whose brief was altered after its summary is refused before it is stored.
  const tampered = reviewed(v2Draft());
  tampered.brief.system.outputs[0].name = "changed in transit";
  await assert.rejects(store.accept(JSON.stringify(tampered), "pilot-system-key-002", receiver, scoping(), mailed(), exportRef()), /deterministic mapping/);
});

test("a saved /workbench/ draft opens in all three formats it was saved in", () => {
  const job = E.template("cooling", "job_saved");
  const words = B.wordsFrom(job.problem);
  assert.equal(words.intended_decision, job.problem.decision);
  assert.equal(words.current_baseline, job.problem.baseline);
  assert.ok(words.requested_result.startsWith(job.problem.title));
  // The editable draft.
  const editable = B.readWorkbenchDraft(E, E.exportJob(job));
  assert.equal(editable.kind, "current");
  assert.deepEqual(editable.problem, job.problem);
  // The unsent submission preview wraps the same draft with a contact email.
  const preview = B.readWorkbenchDraft(E, JSON.stringify({ schema: "carbon.client-intake/1", job, contact: { email: "client@example.invalid" }, consent: { analysis: true, noticeVersion: "UNCONFIGURED" }, assistantHistory: [] }));
  assert.deepEqual(preview.problem, job.problem);
  assert.equal(preview.email, "client@example.invalid");
  // An earlier rules version is migrated by the engine's own rule update.
  const older = E.copy(job);
  older.ruleVersion = "problem.rules.2026-09-12.1";
  assert.equal(B.readWorkbenchDraft(E, JSON.stringify(older)).kind, "rules_update");
  assert.throws(() => B.readWorkbenchDraft(E, "not json"), /valid Carbon draft/);
  assert.throws(() => B.readWorkbenchDraft(E, JSON.stringify({ schema: "carbon.client-intake/1" })), /no draft inside/);
});

test("the built Pilot Designer carries the builder under its own content policy", () => {
  const html = fs.readFileSync(path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html"), "utf8");
  const policy = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];
  for (const source of ["src/problem/cooling-v02.js", "src/problem/engine.js", "src/intake.js", "src/system_builder.js", "src/intake_app.js"]) {
    const hash = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, source), "utf8")).digest("base64");
    assert.ok(policy.includes(`'sha256-${hash}'`), source);
  }
  // Still no connection beyond the page's own origin, which serves the guidance.
  assert.match(policy, /connect-src 'self';/);
  assert.match(html, /<script id="research-leads" type="application\/json">/);
  const leads = JSON.parse(html.match(/<script id="research-leads" type="application\/json">([^<]*)<\/script>/)[1]);
  assert.equal(leads.opportunities.length, 64);
  assert.equal(html, fs.readFileSync(path.join(ROOT, "Carbon_Client_Intake_Preview.html"), "utf8"));
});

test("the guidance context is unchanged: no system value is sent to the provider", () => {
  const draft = v2Draft();
  const context = I.guidanceContextFrom(draft, Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])), []);
  assert.deepEqual(Object.keys(context).sort(), ["answers", "pilot", "unresolved_assumptions", "version"]);
  const sent = JSON.stringify(context);
  for (const component of draft.system.components) assert.ok(!sent.includes(component.name), component.name);
  for (const input of draft.system.inputs) if (input.name) assert.ok(!sent.includes(input.name), input.name);
});

test("the schema's enumerations restate the engine's keys exactly", () => {
  const enums = JSON.parse(fs.readFileSync(path.join(ROOT, "data/problem_enums.json")));
  assert.deepEqual(enums.physics, Object.keys(E.PHYSICS));
  assert.deepEqual(enums.goal, Object.keys(E.GOALS));
  for (const [key, values] of Object.entries(enums)) {
    if (key === "physics" || key === "goal") continue;
    assert.deepEqual(values, Object.keys(E.OPTIONS[key]), key);
  }
  assert.deepEqual(Object.keys(enums).filter((k) => !["physics", "goal"].includes(k)).sort(), Object.keys(E.OPTIONS).sort());
  const schema = JSON.parse(fs.readFileSync(path.join(ROOT, "data/intake_draft_v2.schema.json")));
  assert.deepEqual(schema.properties.system.required, E.problemKeys);
  assert.deepEqual(schema.properties.system.properties.economics.required, E.econKeys);
});

// The live /workbench/ page rendered its assistant and send-brief panels twice:
// its index.html was saved from an already-rendered page, and assist-ui.js
// inserted both panels again, so 16 element IDs were duplicated and the second
// copies were never wired. The Pilot Designer is built from a source template;
// this keeps every ID in it unique.
test("every element ID in the built Pilot Designer is unique", () => {
  const ids = (html) => [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
  const duplicates = (list) => [...new Set(list.filter((id, i) => list.indexOf(id) !== i))];
  // Specimen: the check finds a doubled ID when one exists.
  assert.deepEqual(duplicates(ids('<div id="assistant"></div><div id="assistant"></div>')), ["assistant"]);
  const html = fs.readFileSync(path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html"), "utf8");
  const found = ids(html);
  assert.ok(found.length > 50);
  assert.deepEqual(duplicates(found), []);
});

// GOAL-WORKBENCH-16 migration ticket, sections 4.3 and 5.1.
test("every control the page ships disabled states its reason beside it", () => {
  const html = fs.readFileSync(path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html"), "utf8");
  const body = html.slice(html.indexOf("<body"), html.indexOf("<script"));
  const controls = [...body.matchAll(/<(button|textarea|input|select)\b[^>]*\sdisabled\b[^>]*>/g)].map((m) => m[0]);
  // Specimen: a disabled control without a described reason is caught.
  const unexplained = (tags) => tags.filter((tag) => {
    const ref = /aria-describedby="([^"]+)"/.exec(tag);
    return !ref || !new RegExp(`id="${ref[1]}"[^>]*>[^<]{10,}`).test(body + '<p id="x">specimen reason</p>');
  });
  assert.equal(unexplained(['<button disabled>Go</button>']).length, 1);
  assert.ok(controls.length >= 5, "the page ships its disabled controls");
  assert.deepEqual(unexplained(controls), []);
});

test("the live Workbench's hedges are carried word for word", () => {
  const source = fs.readFileSync(path.join(ROOT, "src/system_builder.js"), "utf8");
  for (const phrase of [
    "Concept diagram. No simulation or feasibility result.",
    "This is a work list, not a feasibility score.",
    "These are requested targets. They are not measured performance or a promise of delivery.",
    "No solver or scientific assessment has run.",
  ]) assert.ok(source.includes(phrase), phrase);
});
