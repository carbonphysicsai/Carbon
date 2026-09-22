"use strict";
// GOAL-WORKBENCH-14: the public onboarding edition.
//
// Two things need proving here and they are different. That the public edition
// reports what the accepted check returned, without softening or hiding any of
// it; and that the artifact it exports is the same draft the internal Workbench
// imports, rather than something that merely looks similar.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const ROOT = path.resolve(__dirname, "..");
const F = require("../src/engine.js");
const E = require("../src/c05_evidence.js");
E.installFixtureIndex(
  JSON.parse(fs.readFileSync(path.join(ROOT, "data/c05_fixture_index_v2.json"))),
);
const S = require("../src/scientific_studies.js");
const P = require("../src/public_workbench.js");
const W = require("../src/workflow.js");
const { PROMPTS } = require("../src/public_app.js");
const BUNDLE = path.join(ROOT, "Carbon_Public_Workbench_Onboarding.html");
const INTERNAL = path.join(ROOT, "Carbon_Opportunity_Workbench.html");

const FIELDS = [...P.SCOPE_FIELDS, ...P.REFERENCE_FIELDS.map((f) => "reference_plan." + f)];

/** A draft with every visitor-closable issue closed. */
function completeDraft(id = "public-draft-0001") {
  const draft = P.emptyDraft(id);
  Object.assign(draft.scope, {
    physics_family: S.TEMPLATE,
    requested_goal: "Dynamics",
    intended_use: "Decide whether a fast surrogate is worth scoping",
    inputs: "Twelve Fourier coefficients, viscosity and requested times",
    outputs: "Velocity at 64 points for each requested time",
    units: "dimensionless",
    geometry: "Periodic line of unit length",
    conditions: "Periodic and unforced, smooth initial field",
    regime: "Smooth through steepening, before any shock",
    exclusions: "No shock capture, no three-dimensional geometry",
    query_workload: "A few hundred evaluations per design iteration",
    turnaround: "Same working day",
    failure_consequences: "A wasted design iteration",
    data_access: "Synthetic cases only",
    rights_scope: "SYNTHETIC_INTERNAL",
    commercial_context: "Evaluating whether to run a pilot",
    disclosure_scope: "Internal use only",
    deployment_environment: "An engineer's laptop",
  });
  draft.reference_plan.equation = "Viscous Burgers equation";
  draft.reference_plan.method = "Spectral reference solver";
  return draft;
}

test("every field a visitor is asked about is a real design field, asked once", () => {
  // The prompts are new; the field identities are the internal design's. A
  // prompt for a field that does not exist would export a draft the internal
  // side cannot import, and a field with no prompt would be silently
  // unanswerable while still being checked.
  for (const field of FIELDS)
    assert(PROMPTS[field], "no question is asked about " + field);
  const staged = P.STAGES.flatMap((stage) => stage.fields);
  assert.deepEqual([...staged].sort(), [...FIELDS].sort());
  assert.equal(new Set(staged).size, staged.length, "a field is asked twice");
  for (const field of Object.keys(PROMPTS))
    assert(FIELDS.includes(field), "a question exists for the unknown field " + field);
});

test("an empty draft reports the accepted check's own issues, attributed", () => {
  const result = S.check(P.checkable(P.emptyDraft("public-draft-0002")));
  const view = P.explain(result);
  assert.equal(view.status, "INPUTS_UNRESOLVED");
  // Pass-through, not paraphrase: the check's own values.
  assert.equal(view.qualification, result.qualification);
  assert.equal(view.limitations, result.limitations);
  assert.deepEqual(view.issues, result.issues);
  // Every issue is present, in order, with its original wording intact.
  assert.equal(view.explained.length, result.issues.length);
  result.issues.forEach((issue, index) =>
    assert.equal(view.explained[index].issue, issue),
  );
  assert.equal(view.unclassified, 0, "an issue had no plain-language note");
  assert.equal(view.open_for_visitor + view.held_by_carbon, result.issues.length);
});

test("a visitor can close every issue that is theirs, and one remains that is not", () => {
  const result = S.check(P.checkable(completeDraft()));
  const view = P.explain(result);
  assert.equal(view.open_for_visitor, 0);
  // The exact shape of reusing the accepted check unchanged: with no physical
  // definition the check always asks for one, and no field a visitor can type
  // closes it. Reported as Carbon's rather than presented as the visitor's
  // failure, and the status is still the check's own.
  assert.deepEqual(result.issues, [
    "Adopt the private service's exact public-source physical definition.",
  ]);
  assert.equal(view.held_by_carbon, 1);
  assert.equal(view.status, "INPUTS_UNRESOLVED");
  assert.equal(view.qualification, "NOT_QUALIFIED");
});

test("an issue with no plain-language note is surfaced, never dropped", () => {
  // The falsifying case for the presentation layer. If the guidance table is
  // ever out of step with the check — a new issue, a reworded one — the issue
  // must still reach the visitor with its own wording rather than vanish
  // because nothing matched it.
  const invented = "A future issue this page has never seen.";
  const view = P.explain({
    status: "INPUTS_UNRESOLVED",
    issues: [invented],
    qualification: "NOT_QUALIFIED",
    limitations: "synthetic",
  });
  assert.equal(view.explained.length, 1);
  assert.equal(view.explained[0].issue, invented);
  assert.equal(view.explained[0].plain, invented);
  assert.equal(view.explained[0].owner, "UNCLASSIFIED");
  assert.equal(view.unclassified, 1);
  // And it is counted as nobody's to close, so it cannot be mistaken for a
  // formality the visitor has already dealt with.
  assert.equal(view.open_for_visitor, 0);
  assert.equal(view.held_by_carbon, 0);
});

test("no guidance entry rewrites, weakens or withholds the issue it explains", () => {
  // Every issue the check can produce for a public draft, gathered from the
  // check itself rather than from a list maintained here.
  const produced = new Set();
  const drafts = [P.emptyDraft("d-1"), completeDraft("d-2")];
  const variants = [
    ["units", "SI metres and seconds"],
    ["conditions", "Dirichlet walls with forcing"],
    ["physics_family", "compressible_navier_stokes"],
    ["requested_goal", "Optimisation"],
    ["rights_scope", "CUSTOMER_PRIVATE"],
    ["inputs", ""],
    ["outputs", ""],
    ["units", ""],
    ["geometry", ""],
    ["conditions", ""],
  ];
  for (const [field, value] of variants) {
    const draft = completeDraft("d-variant");
    draft.scope[field] = value;
    drafts.push(draft);
  }
  const noEquation = completeDraft("d-no-equation");
  noEquation.reference_plan.equation = "";
  drafts.push(noEquation);
  for (const draft of drafts)
    for (const issue of S.check(P.checkable(draft)).issues) produced.add(issue);
  assert(produced.size >= 10, "too few issues were provoked to judge the table");

  for (const issue of produced) {
    const view = P.explain({
      status: "INPUTS_UNRESOLVED",
      issues: [issue],
      qualification: "NOT_QUALIFIED",
      limitations: "",
    });
    const item = view.explained[0];
    assert.equal(item.issue, issue, "an issue was rewritten");
    assert.notEqual(item.owner, "UNCLASSIFIED", "no guidance for: " + issue);
    assert(item.plain.length > 0, "empty guidance for: " + issue);
  }
});

test("export is deterministic and its digest covers its content", async () => {
  const draft = completeDraft("public-draft-0003");
  const result = S.check(P.checkable(draft));
  const first = await P.exportWorkspace(draft, result, S);
  const second = await P.exportWorkspace(draft, result, S);
  assert.equal(JSON.stringify(first), JSON.stringify(second));
  await P.validateArtifact(first, S);

  // One character elsewhere in the draft changes the digest.
  const changed = completeDraft("public-draft-0003");
  changed.scope.regime += ".";
  const other = await P.exportWorkspace(changed, S.check(P.checkable(changed)), S);
  assert.notEqual(other.digest, first.digest);

  // A tampered artifact is refused, including one whose recorded check result
  // was edited to look better than the check said.
  for (const tamper of [
    (value) => (value.scope.units = "SI metres"),
    (value) => (value.structural_check.status = "STRUCTURALLY_CHECKED"),
    (value) => (value.structural_check.issues = []),
    (value) => (value.revision = 2),
  ]) {
    const copy = JSON.parse(JSON.stringify(first));
    tamper(copy);
    await assert.rejects(() => P.validateArtifact(copy, S), /digest does not match/);
  }
  // An artifact cannot claim authority, whatever its digest says.
  const claiming = JSON.parse(JSON.stringify(first));
  claiming.authority.qualification = "SCIENTIFICALLY_QUALIFIED";
  const redigested = { ...claiming };
  delete redigested.digest;
  claiming.digest = "sha256:" + (await S.digest(P.canonical(redigested)));
  await assert.rejects(() => P.validateArtifact(claiming, S), /carries no authority/);
});

test("the artifact's field set is closed", async () => {
  const draft = completeDraft("public-draft-0004");
  const artifact = await P.exportWorkspace(draft, S.check(P.checkable(draft)), S);
  const extra = { ...artifact, submitted_to: "carbon" };
  await assert.rejects(() => P.validateArtifact(extra, S), /fields are closed/);
  const short = { ...artifact };
  delete short.scope;
  await assert.rejects(() => P.validateArtifact(short, S), /fields are closed/);
});

test("the internal Workbench imports the public artifact as the same draft", async () => {
  const draft = completeDraft("public-draft-0005");
  const publicResult = S.check(P.checkable(draft));
  const artifact = await P.exportWorkspace(draft, publicResult, S);
  await P.validateArtifact(artifact, S);

  const { job, design } = W.importPublicScoping(artifact);

  // The same draft, named the same way on both sides.
  assert.equal(design.design_id, artifact.design_id);
  assert.equal(design.revision, artifact.revision);
  // The same structural check result, recomputed internally rather than read
  // from the artifact. A prose comparison would not establish this.
  const internalResult = S.check(P.checkable(design));
  assert.equal(internalResult.status, publicResult.status);
  assert.deepEqual(internalResult.issues, publicResult.issues);
  assert.equal(internalResult.status, artifact.structural_check.status);
  assert.deepEqual(internalResult.issues, artifact.structural_check.issues);
  // Every scope field arrived without retyping.
  for (const field of P.SCOPE_FIELDS)
    assert.equal(design.scope[field], artifact.scope[field]);
  for (const field of P.REFERENCE_FIELDS)
    assert.equal(design.reference_plan[field], artifact.reference_plan[field]);
  // And the import is accepted by the internal validator, not just constructed.
  W.validateJob(job);
  W.validateDesign(design, job.job_id);

  // Nothing about importing a client's draft promotes anything.
  assert.equal(design.status, "DRAFT");
  assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
  assert.equal(design.decision.launch_authorization, "NOT_AUTHORIZED");
  assert.equal(design.decision.security_rights, "UNRESOLVED");
  assert.deepEqual(design.cases, []);
  assert.deepEqual(design.measurement_evidence, []);
  assert.deepEqual(design.source_assessments, W.newDesign("j", "d").source_assessments);
  // The provenance of every imported value is on the record.
  assert.equal(design.change_log.length, P.SCOPE_FIELDS.length);
  assert(design.change_log.every((entry) => entry.note.includes(artifact.digest)));
  assert(job.assignment.client_source.includes(artifact.digest));
});

test("an artifact the internal side should refuse is refused", () => {
  const draft = completeDraft("public-draft-0006");
  for (const [mutate, pattern] of [
    [(v) => (v.schema_version = "carbon.goal-workbench.workspace.v0.10"), /Unsupported public workspace/],
    [(v) => (v.design_id = "not a valid identity"), /Invalid design ID/],
    [(v) => (v.revision = 0), /Invalid design revision/],
    [(v) => delete v.scope.units, /scope fields are closed/],
    [(v) => (v.scope.extra_field = "x"), /scope fields are closed/],
    [(v) => (v.reference_plan.role = "witness"), /reference fields are closed/],
  ]) {
    const value = JSON.parse(JSON.stringify(draft));
    value.digest = "sha256:" + "0".repeat(64);
    mutate(value);
    assert.throws(() => W.importPublicScoping(value), pattern);
  }
});

test("the public bundle carries the check and nothing internal", () => {
  const bundle = fs.readFileSync(BUNDLE, "utf8");
  const internal = fs.readFileSync(INTERNAL, "utf8");

  // It has no network capability at all, and no form can post anywhere.
  assert(bundle.includes("connect-src 'none'"), "the public bundle can connect");
  assert(bundle.includes("form-action 'none'"));
  assert(bundle.includes("default-src 'none'"));
  assert.equal(/fetch\s*\(/.test(bundle), false, "the public bundle calls fetch");
  assert.equal(/XMLHttpRequest|EventSource|WebSocket|navigator\.sendBeacon/.test(bundle), false);
  // It does carry the accepted check, so the reuse claim is about this file.
  assert(bundle.includes("carbon.workbench.scientific-study.request.v1"));
  assert(bundle.includes("INPUTS_UNRESOLVED"));
  assert(bundle.includes(P.WORKSPACE));

  // Content markers for everything the public edition must not contain. Each is
  // asserted absent here and present in the internal bundle, so a marker that
  // stopped discriminating would fail this test rather than silently pass it.
  const forbidden = {
    "CPES study material": "CPES-REFERENCE-REUSE-GAUNTLET-V2",
    "source assessment state": "carbon.goal-workbench.source-assessment-state.v1",
    "the opportunity atlas": "opportunity_workspace",
    "the owner console": "ownerConsole",
    "internal evidence import": "carbon.goal-workbench.authoring-result.v1",
    "the internal workspace schema": "carbon.goal-workbench.workspace.v0.10",
    "client intake capture": "carbon.client-intake.reviewed.v1",
  };
  for (const [what, marker] of Object.entries(forbidden)) {
    assert.equal(bundle.includes(marker), false, "the public bundle contains " + what);
    assert(
      internal.includes(marker),
      "the marker for " + what + " no longer appears in the internal bundle, " +
        "so its absence from the public bundle proves nothing",
    );
  }
  // The private-service route string IS in this bundle, and pretending
  // otherwise would mean shipping a forked copy of the accepted check module to
  // hide a substring. It appears inside `createAdapter`, the only part of that
  // module that reaches the network. What must be true is not that the text is
  // absent but that nothing can reach it, and that is checkable: the public
  // sources never name it, the bundle adds no reference beyond the module's own
  // definition and export, and the page is granted no connection at all.
  // The private build marker is not compared against the internal bundle,
  // because the tracked internal artifact is an offline build and does not
  // carry it either; only a --private-science build does. Asserting its absence
  // from the public bundle would have been a check that could never fail.
  assert.equal(bundle.includes('data-scientific-service="private"'), false);
  // An endpoint attribute, paired against the intake preview, which has one.
  assert.equal(/data-api-url/.test(bundle), false, "the public bundle names an API");
  assert(
    fs
      .readFileSync(path.join(ROOT, "Carbon_Client_Intake_Preview.html"), "utf8")
      .includes("data-api-url"),
    "the intake preview no longer carries data-api-url, so that check is vacuous",
  );

  const module = fs.readFileSync(path.join(ROOT, "src/scientific_studies.js"), "utf8");
  const occurrences = (text, needle) => text.split(needle).length - 1;
  assert.equal(
    occurrences(bundle, "createAdapter"),
    occurrences(module, "createAdapter"),
    "the public bundle references createAdapter beyond the module's own text",
  );
  assert.equal(
    occurrences(bundle, "/api/scientific-studies"),
    occurrences(module, "/api/scientific-studies"),
  );
  for (const relative of ["src/public_app.js", "src/public_workbench.js", "src/public_shell.html"]) {
    const source = fs.readFileSync(path.join(ROOT, relative), "utf8");
    assert.equal(/createAdapter|createController|\/api\//.test(source), false, relative);
  }
  // And the internal bundle does reference it, so the comparison above is
  // between a bundle that uses the adapter and one that merely contains it.
  assert(occurrences(internal, "createAdapter") > occurrences(module, "createAdapter"));

  // Size is evidence about what is in it: the internal bundle is two orders of
  // magnitude larger because it carries the evidence this one does not.
  assert(bundle.length < internal.length / 8, "the public bundle is suspiciously large");
});

test("the emitted bundle is exactly its declared sources", () => {
  const build = fs.readFileSync(path.join(ROOT, "tools/build.py"), "utf8");
  const declared = [...build.matchAll(/^\s{4}"(src\/public[^"]+|src\/scientific_studies\.js)",$/gm)]
    .map((match) => match[1]);
  assert.deepEqual(declared.sort(), [
    "src/public_app.js",
    "src/public_shell.html",
    "src/public_styles.css",
    "src/public_workbench.js",
    "src/scientific_studies.js",
  ]);
  const bundle = fs.readFileSync(BUNDLE, "utf8");
  for (const relative of declared) {
    if (relative.endsWith(".html")) continue;
    const source = fs.readFileSync(path.join(ROOT, relative), "utf8");
    assert(bundle.includes(source.trim()), relative + " is not in the emitted bundle");
  }
  // Nothing else from src/ is in it. This is the assertion that would catch a
  // future edit adding an internal module to the public shell.
  const others = fs
    .readdirSync(path.join(ROOT, "src"))
    .filter((name) => name.endsWith(".js") && !declared.includes("src/" + name));
  for (const name of others) {
    const source = fs.readFileSync(path.join(ROOT, "src", name), "utf8");
    assert.equal(
      bundle.includes(source.trim()),
      false,
      "the public bundle contains src/" + name,
    );
  }
  assert(others.length >= 8, "too few internal modules to make that meaningful");
});
