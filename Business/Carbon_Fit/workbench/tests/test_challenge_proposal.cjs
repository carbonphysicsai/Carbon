"use strict";
// GOAL-WORKBENCH-16 slice 2: a proposed Challenge from a client's brief, with
// the exam-design evidence behind each setting.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const I = require("../src/intake.js");
const E = require("../src/problem/engine.js");
const P = require("../src/challenge_proposal.js");

const ROOT = path.resolve(__dirname, "..");
const REPO = path.resolve(ROOT, "../../..");
const RECORD = JSON.parse(fs.readFileSync(path.join(ROOT, "data/challenge_families_v1.json"), "utf8"));
const BATTERY = "battery-fastcharge-ageing-development-v1";

function brief(words, build = () => {}) {
  const system = E.blankProblem();
  build(system);
  const draft = I.newDraft("proposal-test", "rev-001", system);
  for (const [field, value] of Object.entries(words)) draft.answers[field] = { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" };
  draft.summary = I.summaryFor(draft);
  return I.validateDraft(draft);
}
const input = (id, name, unit, min, max) => ({ ...E.row("inputs", id), name, unit, min, max });
const batteryBrief = (inputs = []) =>
  brief({ intended_decision: "Choose a fast-charge protocol for a lithium pouch cell without plating." }, (s) => {
    s.components.push({ ...E.row("components", "cmp_cell"), name: "Pouch cell", physics: "chemical" });
    s.inputs.push(...inputs);
    s.outputs.push({ ...E.row("outputs", "out_v"), name: "Terminal voltage", unit: "V" });
  });

test("the family record relays each readiness record exactly as recorded", () => {
  assert.equal(RECORD.schema, "carbon.pilot-designer.challenge-families.v1");
  for (const family of RECORD.families) {
    const source = path.join(REPO, family.record.path);
    const bytes = fs.readFileSync(source);
    assert.equal(family.record.sha256, "sha256:" + crypto.createHash("sha256").update(bytes).digest("hex"), family.id);
    const record = JSON.parse(bytes);
    for (const key of ["status", "limits", "costs", "reviews", "training_budget_study", "unresolved", "reference", "population"])
      assert.deepEqual(family[key], record[key], `${family.id} ${key}`);
    // No approval appears that the record does not hold.
    for (const limit of family.limits) assert.equal(limit.approved, record.limits.find((l) => l.name === limit.name).approved);
  }
});

test("every quoted line of evidence still appears verbatim in its source", () => {
  for (const evidence of Object.values(RECORD.evidence)) {
    const text = fs.readFileSync(path.join(REPO, evidence.source.path), "utf8");
    for (const setting of evidence.settings) for (const quote of setting.quotes) assert.ok(text.includes(quote), quote);
    for (const quote of evidence.limits_of_evidence) assert.ok(text.includes(quote), quote);
  }
});

test("the battery bounds are the domain module's", () => {
  const domain = fs.readFileSync(path.join(REPO, "carbon/battery/domain.py"), "utf8");
  const battery = RECORD.families.find((f) => f.id === BATTERY);
  for (const variable of battery.design_variables) {
    const found = domain.match(new RegExp(`"${variable.name}": \\(([-0-9.]+), ([-0-9.]+)\\)`));
    assert.ok(found, variable.name);
    assert.deepEqual(variable.bounds, [Number(found[1]), Number(found[2])], variable.name);
  }
});

// A negative assertion needs a specimen: the scan below must find a planted
// hidden-material key before its silence on the real record means anything.
function hiddenKeys(value, found = []) {
  if (Array.isArray(value)) value.forEach((item) => hiddenKeys(item, found));
  else if (value && typeof value === "object")
    for (const [key, item] of Object.entries(value)) {
      if (/seed|private_root|reference_output|hidden/i.test(key)) found.push(key);
      hiddenKeys(item, found);
    }
  return found;
}
test("the public record carries no seed, private root or reference output", () => {
  assert.deepEqual(hiddenKeys({ nested: [{ private_root: "x" }] }), ["private_root"]);
  assert.deepEqual(hiddenKeys(RECORD), []);
});

test("a battery brief gets an evidence-backed proposal with every setting sourced", () => {
  const proposal = P.propose(batteryBrief(), RECORD);
  assert.equal(proposal.kind, P.KIND.EVIDENCE);
  assert.equal(proposal.family.id, BATTERY);
  assert.equal(proposal.authority, "PROPOSAL_ONLY_NOT_REGISTERED_QUALIFIED_OR_APPROVED");
  assert.deepEqual(proposal.matched.keywords.sort(), ["cell", "charge protocol", "fast-charge", "lithium", "plating"].sort());
  const ids = proposal.settings.map((s) => s.id);
  assert.deepEqual(ids, ["train_cases", "screening_batch", "rotation", "equivalence_margin", "promotion_rule", "gates", "screening_cost"]);
  for (const setting of proposal.settings) {
    assert.ok(setting.why && setting.section && setting.table.rows.length, setting.id);
    assert.equal(setting.covered, true);
  }
  // The margin carries its limit exactly as recorded: proposed, not approved.
  const margin = proposal.settings.find((s) => s.id === "equivalence_margin").limit;
  assert.deepEqual([margin.proposed, margin.approved], [0.057, null]);
});

test("conditions the client did not give are proposed from the tested design, and labelled", () => {
  const proposal = P.propose(batteryBrief(), RECORD);
  for (const condition of proposal.conditions) {
    assert.equal(condition.status, "PROPOSED_FROM_TESTED_DESIGN", condition.variable);
    assert.deepEqual(condition.proposed_range, condition.tested_range);
    assert.match(condition.note, /confirm or change/);
  }
});

test("a client range is compared with the tested range, never silently accepted", () => {
  const inside = P.propose(batteryBrief([input("inp_amb", "Ambient temperature", "degC", 10, 35)]), RECORD);
  assert.equal(inside.conditions.find((c) => c.variable === "t_amb_c").status, "INSIDE_TESTED_RANGE");
  const outside = P.propose(batteryBrief([input("inp_rate", "First-stage charge rate", "C-rate", 0.5, 3)]), RECORD);
  const c1 = outside.conditions.find((c) => c.variable === "c1");
  assert.equal(c1.status, "OUTSIDE_TESTED_RANGE");
  assert.match(c1.note, /does not cover this/);
  assert.ok(outside.settings.every((s) => s.covered === false));
  const noRange = P.propose(batteryBrief([input("inp_soc", "Initial state of charge", "1", null, null)]), RECORD);
  assert.equal(noRange.conditions.find((c) => c.variable === "soc0").status, "SUPPLIED_RANGE_MISSING");
});

test("units are never converted: a different or ambiguous unit asks for confirmation", () => {
  for (const unit of ["%", "C", "K"]) {
    const proposal = P.propose(batteryBrief([input("inp_amb", "Ambient temperature", unit, 10, 35)]), RECORD);
    const t = proposal.conditions.find((c) => c.variable === "t_amb_c");
    assert.equal(t.status, "UNITS_TO_CONFIRM", unit);
    assert.equal(t.proposed_range, null, unit);
  }
  const spelled = P.propose(batteryBrief([input("inp_amb", "Ambient temperature", "°C", 10, 35)]), RECORD);
  assert.equal(spelled.conditions.find((c) => c.variable === "t_amb_c").status, "INSIDE_TESTED_RANGE");
});

test("an input the family does not vary is reported, not dropped", () => {
  const proposal = P.propose(batteryBrief([input("inp_tab", "Tab cooling coefficient", "W/m2K", 5, 50)]), RECORD);
  assert.deepEqual(proposal.extra_client_inputs, ["Tab cooling coefficient"]);
  assert.match(P.markdown(proposal), /does not vary: Tab cooling coefficient/);
});

test("a family without evidence proposes no exam setting and shows no invented cost", () => {
  const cooling = JSON.parse(fs.readFileSync(path.join(ROOT, "intake/fixtures/cooling_system_draft_v2.json"), "utf8"));
  const proposal = P.propose(cooling, RECORD);
  assert.equal(proposal.family.id, "chip-cold-plate");
  assert.equal(proposal.kind, P.KIND.SCOPED);
  assert.deepEqual(proposal.settings, []);
  for (const condition of proposal.conditions) assert.equal(condition.tested_range, null);
  assert.ok(proposal.costs.every((c) => c.basis !== "unknown" || c.usd === null));
  assert.match(P.markdown(proposal), /No exam-design evidence yet/);
});

test("matching uses whole words and the client's physics, and a blank brief matches nothing", () => {
  const blank = P.propose(brief({}), RECORD);
  assert.equal(blank.kind, P.KIND.NONE);
  assert.deepEqual(blank.matches, []);
  const excellent = P.match(brief({ intended_decision: "An excellent decision" }), RECORD);
  assert.ok(!excellent.some((m) => m.keywords.includes("cell")));
  const physicsOnly = P.match(brief({}, (s) => s.components.push({ ...E.row("components", "cmp_em"), name: "Field", physics: "electromagnetic" })), RECORD);
  assert.deepEqual(physicsOnly.map((m) => m.family_id).sort(), [BATTERY, "electric-motor-magnetics", "photonic-coupler"].sort());
});

test("a client may choose another family; an unknown one is refused", () => {
  const chosen = P.propose(batteryBrief(), RECORD, "electric-motor-magnetics");
  assert.equal(chosen.family.id, "electric-motor-magnetics");
  assert.equal(chosen.matched, null);
  assert.throws(() => P.propose(batteryBrief(), RECORD, "not-a-family"), /Unknown Challenge family/);
});

test("the same brief always gives the same proposal", () => {
  const draft = batteryBrief([input("inp_amb", "Ambient temperature", "degC", 10, 35)]);
  assert.equal(JSON.stringify(P.propose(draft, RECORD)), JSON.stringify(P.propose(JSON.parse(JSON.stringify(draft)), RECORD)));
  assert.equal(P.markdown(P.propose(draft, RECORD)), P.markdown(P.propose(draft, RECORD)));
});

test("the built Pilot Designer carries the proposal and its record under its content policy", () => {
  const html = fs.readFileSync(path.join(ROOT, "Carbon_Client_Pilot_Designer_Preview.html"), "utf8");
  const policy = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];
  const hash = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "src/challenge_proposal.js"), "utf8")).digest("base64");
  assert.ok(policy.includes(`'sha256-${hash}'`));
  const embedded = JSON.parse(html.match(/<script id="challenge-families" type="application\/json">([^<]*)<\/script>/)[1]);
  assert.deepEqual(embedded, RECORD);
});
