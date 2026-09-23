"use strict";
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
const { DurableIntakeStore } = require("../tools/team_intake_store.cjs");
const ROOT = path.resolve(__dirname, "..");
const atlas = JSON.parse(fs.readFileSync(path.join(ROOT, "data/atlas.json"), "utf8"));
const scenarios = JSON.parse(fs.readFileSync(path.join(ROOT, "data/goal_workbench_09_team_scenarios_v1.json"), "utf8")).scenarios;
const component = () => ({ schema_version: F.WORKSPACE_VERSION, application_version: F.APP_VERSION, source_sha256: atlas.source.sha256, evidence_catalog: [], drafts: [], shortlist: [], migration_receipts: [] });
const reader = (raw) => F.readWorkspace(raw, atlas.opportunities.map((item) => item.id), atlas.source.sha256);
const { StaffDirectory } = require("../tools/team_staff_directory.cjs");
// Synthetic and local. The journey needs a real authenticated identity because
// the receiver no longer accepts a principal the caller describes for itself.
const RECEIVER_TOKEN = "synthetic-journey-receiver-0001";
const { enrolled, openStore, principalFor, scoping } = require("./staff_fixture.cjs");
const receiver = principalFor(
  new StaffDirectory([enrolled("synthetic-receiver", "carbon-fit", ["INTAKE_RECEIVER"], RECEIVER_TOKEN)]),
  RECEIVER_TOKEN,
);

function draftFor(scenario) {
  if (scenario.source_fixture)
    return JSON.parse(fs.readFileSync(path.join(ROOT, scenario.source_fixture), "utf8"));
  const draft = I.newDraft("gw09-incomplete", "rev-001");
  draft.answers.intended_decision = {
    state: "VALUE",
    value: "Understand whether a first feasibility pilot is worth defining.",
    origin: "USER_ENTERED_LOCAL",
  };
  draft.summary = I.summaryFor(draft);
  return draft;
}

function reviewed(draft, scenario) {
  return {
    schema_version: I.REVIEW_VERSION,
    brief: draft,
    pilot: {
      label: "Draft pilot for Carbon review",
      ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])),
      bounded_first_pilot: scenario.assessment_focus,
      next_discussion: scenario.next_question,
    },
    field_provenance: [
      ...I.TEXT_FIELDS,
      ...I.QUANTITY_FIELDS,
      ...I.PILOT_FIELDS.map((field) => "pilot." + field),
    ].map((field) => ({
      field,
      origin: ["pilot.bounded_first_pilot", "pilot.next_discussion"].includes(field)
        ? "CLIENT_TYPED"
        : "UNKNOWN",
      suggestion_id: null,
    })),
    accepted_suggestions: [],
    unresolved_assumptions: ["Scientific adequacy, rights, cost and execution remain unresolved."],
    ai_guidance: { enabled: false, provider: null, guidance_version: I.GUIDANCE_VERSION, notice_version: null, consented_at: null, cleared_locally: false },
    sharing: { include_conversation: false, conversation: [] },
    contact: { name: "", email: "", organization: "" },
    local_scope: I.REVIEW_SCOPE,
  };
}

for (const scenario of scenarios) {
  test(scenario.scenario_id + " completes durable intake through scoped handoff", async () => {
    const raw = JSON.stringify(reviewed(draftFor(scenario), scenario));
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), "gw09-journey-"));
    const store = openStore(path.join(directory, "store.json"));
    const receipt = await store.accept(raw, "key-" + scenario.scenario_id, receiver, scoping());
    const inspection = await I.inspect(raw, F.strictJsonParse);
    const workspace = G.newWorkspace(component());
    G.commitIntakeImport(workspace, inspection, G.previewIntakeImport(workspace, inspection));
    const job = workspace.jobs[0], design = job.designs[0];
    job.team_review.service_receipts.push({
      receipt_id: receipt.receipt_id,
      inquiry_id: receipt.inquiry_id,
      revision: receipt.revision,
      raw_sha256: receipt.raw_sha256,
      status: "PERSISTED_PRIVATE_SYNTHETIC",
      observed_by: "synthetic journey harness",
    });
    job.team_review.assigned_reviewer = "Synthetic reviewer";
    job.team_review.queue_state = "UNDER_REVIEW";
    job.team_review.current_action = scenario.next_question;
    job.team_review.next_restart_event = "Named source or client response for this exact question";
    job.team_review.provenance = "LOCAL_MANUAL_ASSERTION";
    job.accountable_owner = "Synthetic owner";
    job.lead = scenario.route === "DEVELOP_NEW_CAPABILITY" ? "R1" : "S1";
    design.assessment.intended_engineering_decision = job.assignment.intended_decision;
    design.assessment.reference_gaps = "Reference identity, adequacy and permission remain unresolved.";
    design.assessment.smallest_useful_pilot = scenario.assessment_focus;
    design.assessment.stop_conditions = scenario.stop_condition;
    design.assessment.open_questions = [scenario.next_question];
    const routeInput = {
      rationale: scenario.situation,
      source_or_capability_ref:
        scenario.route === "ADAPT_SUPPORTED_CHALLENGE"
          ? "periodic_viscous_burgers_1d_v1 / proposed adaptation"
          : scenario.route === "USE_EXISTING_CAPABILITY"
            ? "client-reported existing method"
            : "unsupported capability request",
      route_basis: scenario.assessment_focus,
      unresolved_conditions: ["science", "rights", "reference feasibility"],
      next_decision: scenario.next_question,
      selected_by_assertion: "Synthetic scenario operator",
      status_provenance: "LOCAL_MANUAL_ASSERTION",
    };
    if (scenario.route === "DEVELOP_NEW_CAPABILITY")
      Object.assign(routeInput, {
        bounded_question: scenario.next_question,
        stop_condition: scenario.stop_condition,
        restart_event: "Named dependency response",
      });
    G.selectRoute(design, scenario.route, routeInput);
    const handoff = G.handoff(design, {
      request_id: "handoff-" + scenario.scenario_id.toLowerCase(),
      recipient: job.lead,
      lead: job.lead,
      question: scenario.next_question,
      required_output: "Return one source-bound finding or precise blocker for this exact design revision.",
      permitted_data: "Public/synthetic reviewed brief only",
      rights: "Unresolved",
      required_authority: "Native source owner retains its authority",
      allowance: "No execution allowance supplied",
      stop_condition: scenario.stop_condition,
      input_refs: ["intake:" + inspection.canonical_digest, "design:" + design.design_id + "@" + design.revision],
      dependency_owner: job.lead,
      restart_event: "Named response for this exact request",
      route: "MANUAL",
    });
    assert.equal(handoff.status, "PREPARED");
    assert.equal(design.decision.scientific_qualification, "NOT_QUALIFIED");
    assert.equal(design.decision.security_rights, "UNRESOLVED");
    assert.deepEqual(
      design.assessment.scientific_task_dependencies.map((item) => item.availability),
      ["AVAILABLE_NOT_REQUESTED", "CORE_INTERFACE_PENDING", "AVAILABLE_NOT_REQUESTED"],
    );
    const client = G.clientPilotBrief(job, design), internal = G.internalExecutionBrief(job, design);
    assert.equal(client.design_id, internal.design_id);
    assert.equal(client.authority.includes("not feasibility"), true);
    assert.equal(internal.handoff_bindings[0].status, "PREPARED");
    const reopened = G.readWorkspace(JSON.stringify(workspace), reader, "VERIFIED_WEB_CRYPTO");
    await G.revalidateIntakeRecords(reopened);
    assert.equal(reopened.jobs[0].team_review.service_receipts[0].receipt_id, receipt.receipt_id);
    assert.equal(reopened.jobs[0].designs[0].handoffs[0].status, "PREPARED");
    assert.equal(G.previewIntakeImport(reopened, inspection).action, "EXACT_REPLAY");
  });
}
