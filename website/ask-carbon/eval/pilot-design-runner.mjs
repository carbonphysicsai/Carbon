import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createWorker, AskCarbonUsageLedger } from "../worker/index.mjs";
import knowledge from "../knowledge/public-knowledge.v1.json" with { type: "json" };

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const F = require("../../../Business/Carbon_Fit/workbench/src/engine.js");
const I = require("../../../Business/Carbon_Fit/workbench/src/intake.js");
const G = require("../../../Business/Carbon_Fit/workbench/src/workflow.js");
const ATLAS = require("../../../Business/Carbon_Fit/workbench/data/atlas.json");
const IDS = ATLAS.opportunities.map((item) => item.id);
const FIXED_ACCEPTED_AT = "2026-09-16T12:00:00Z";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async transaction(callback) { return callback(this); }
}

const component = () => ({
  schema_version: F.WORKSPACE_VERSION,
  application_version: F.APP_VERSION,
  source_sha256: ATLAS.source.sha256,
  evidence_catalog: [], drafts: [], shortlist: [], migration_receipts: [],
});
const componentReader = (raw) => F.readWorkspace(raw, IDS, ATLAS.source.sha256);
const blankPilot = () => ({ label: "Draft pilot for Carbon review", ...Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, ""])) });
const fieldNames = () => [...I.TEXT_FIELDS, ...I.QUANTITY_FIELDS, ...I.PILOT_FIELDS.map((field) => `pilot.${field}`)];
const getField = (state, field) => field.startsWith("pilot.")
  ? state.pilot[field.slice(6)]
  : state.brief.answers[field]?.value;
const setField = (state, field, value) => {
  if (field.startsWith("pilot.")) state.pilot[field.slice(6)] = value;
  else state.brief.answers[field] = { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" };
  state.brief.summary = I.summaryFor(state.brief);
};
const contextFor = (state) => ({
  version: "carbon.client-intake.guidance-context.v1",
  answers: Object.fromEntries(I.TEXT_FIELDS.map((field) => [field, state.brief.answers[field].state === "VALUE" ? state.brief.answers[field].value : null])),
  pilot: Object.fromEntries(I.PILOT_FIELDS.map((field) => [field, state.pilot[field] || null])),
  unresolved_assumptions: state.unresolved,
});

const makeRuntime = () => {
  const ledger = new AskCarbonUsageLedger({ storage: new MemoryStorage() });
  const env = {
    ASK_CARBON_ACTIVATION: "enabled",
    ASK_CARBON_RUNTIME_MODE: "staging",
    ASK_CARBON_APPROVED_ORIGINS: "https://staging.example",
    ASK_CARBON_APPROVED_MODEL_CONFIGS: "gpt-5.6-luna:low:v1,gpt-5.6-terra:low:v1",
    ASK_CARBON_MODEL_CONFIG_ID: "gpt-5.6-luna:low:v1",
    ASK_CARBON_OPENAI_API_KEY: "test-only-provider-key",
    ASK_CARBON_CONTINUATION_SIGNING_SECRET: "test-only-signing-secret",
    ASK_CARBON_PRIVACY_MODE: "evaluation_public_synthetic_only",
    ASK_CARBON_STAGING_ACCESS_MODE: "cloudflare_access",
    ASK_CARBON_EDGE_ACCESS_POLICY_ID: "test-only-private-access",
    ASK_CARBON_EDGE_ABUSE_POLICY_ID: "test-only-abuse-policy",
    ASK_CARBON_LEDGER_AUTHORITY_ID: "ask-carbon-provider-budget-v2",
    ASK_CARBON_ENVIRONMENT: "staging",
    ASK_CARBON_OPERATIONAL_SCOPE_ID: "ask-carbon-bakeoff-v1",
    ASK_CARBON_OPERATIONAL_SCOPE_LIMIT_MICRO_USD: "5000000",
    ASK_CARBON_MONTHLY_LIMIT_MICRO_USD: "50000000",
    ASK_CARBON_DAILY_REQUEST_LIMIT: "100",
    ASK_CARBON_MAX_CONCURRENCY: "4",
    ASK_CARBON_CLIENT_REQUESTS_PER_HOUR: "20",
    ASK_CARBON_CLIENT_COUNTER_RETENTION_MS: "86400000",
    ASK_CARBON_MAX_INPUT_TOKENS: "24000",
    ASK_CARBON_MAX_OUTPUT_TOKENS: "700",
    ASK_CARBON_PROVIDER_TIMEOUT_MS: "15000",
    ASK_CARBON_PILOT_MAX_REQUESTS_PER_SESSION: "8",
    ASK_CARBON_EDGE_RATE_LIMITER: { limit: async () => ({ success: true }) },
    ASK_CARBON_USAGE_LEDGER: { idFromName: () => "global", get: () => ({ fetch: (url, options) => ledger.fetch(new Request(url, options)) }) },
  };
  return { ledger, env };
};

const providerBody = (mock, id) => ({
  id: `mock-${id}`,
  model: "gpt-5.6-luna",
  status: "completed",
  output: [{ type: "message", role: "assistant", content: [{ type: "output_text", text: JSON.stringify(mock) }] }],
  usage: { input_tokens: 100, input_tokens_details: { cached_tokens: 0 }, output_tokens: 50, output_tokens_details: { reasoning_tokens: 10 }, total_tokens: 150 },
});

const applyActions = (state, response, actions, caseId, turnIndex) => {
  const outcomes = [];
  for (const action of actions) {
    if (action.type === "SKIP" || action.type === "SWITCH_TO_FORM") {
      outcomes.push({ ...action, disposition: action.type === "SKIP" ? "UNKNOWN_RETAINED" : "SAME_BRIEF_PRESERVED" });
      continue;
    }
    if (action.type === "CLIENT_EDIT") {
      setField(state, action.field, action.value);
      const provenance = state.provenance.find((item) => item.field === action.field);
      if (provenance) Object.assign(provenance, { origin: "CLIENT_TYPED", suggestion_id: null });
      state.accepted = state.accepted.filter((item) => item.field !== action.field);
      outcomes.push({ ...action, disposition: "CLIENT_VALUE_RECORDED" });
      continue;
    }
    const proposal = response.proposals.find((item) => item.suggestion_id === action.suggestion_id);
    if (!proposal) {
      outcomes.push({ ...action, disposition: "EXPECTED_PROPOSAL_ABSENT" });
      continue;
    }
    if (action.type === "REJECT") {
      outcomes.push({ ...action, field: proposal.field, disposition: "REJECTED_NO_MUTATION" });
      continue;
    }
    if (action.type === "ACCEPT") {
      state.history.set(proposal.suggestion_id, { field: proposal.field, previous: getField(state, proposal.field) ?? "" });
      setField(state, proposal.field, proposal.value);
      state.accepted = state.accepted.filter((item) => item.field !== proposal.field);
      state.accepted.push({ suggestion_id: proposal.suggestion_id, field: proposal.field, proposed_value: proposal.value, rationale: proposal.rationale, accepted_at: FIXED_ACCEPTED_AT });
      const provenance = state.provenance.find((item) => item.field === proposal.field);
      Object.assign(provenance, { origin: "AI_SUGGESTED_CLIENT_ACCEPTED", suggestion_id: proposal.suggestion_id });
      outcomes.push({ ...action, field: proposal.field, disposition: "ACCEPTED_CLIENT_REVIEW" });
      continue;
    }
    if (action.type === "UNDO") {
      const history = state.history.get(action.suggestion_id);
      const current = state.accepted.find((item) => item.suggestion_id === action.suggestion_id);
      if (!history || !current) outcomes.push({ ...action, disposition: "NO_EFFECT_SUPERSEDED_OR_ABSENT" });
      else {
        setField(state, history.field, history.previous);
        state.accepted = state.accepted.filter((item) => item.suggestion_id !== action.suggestion_id);
        const provenance = state.provenance.find((item) => item.field === history.field);
        Object.assign(provenance, { origin: history.previous ? "CLIENT_TYPED" : "UNKNOWN", suggestion_id: null });
        outcomes.push({ ...action, disposition: "UNDONE" });
      }
      continue;
    }
    outcomes.push({ ...action, disposition: "UNSUPPORTED_SCRIPT_ACTION", case_id: caseId, turn_index: turnIndex });
  }
  state.unresolved = [...new Set(response.unresolved_assumptions)];
  return outcomes;
};

const reviewedPackage = (state) => I.validateReviewedPackage({
  schema_version: I.REVIEW_VERSION,
  brief: state.brief,
  pilot: state.pilot,
  field_provenance: state.provenance,
  accepted_suggestions: state.accepted,
  unresolved_assumptions: state.unresolved,
  ai_guidance: { enabled: true, provider: "OPENAI_API", guidance_version: I.GUIDANCE_VERSION, notice_version: "ask-carbon-guided-intake-notice-v1", consented_at: FIXED_ACCEPTED_AT, cleared_locally: false },
  sharing: { include_conversation: false, conversation: [] },
  contact: { name: "", email: "", organization: "" },
  local_scope: I.REVIEW_SCOPE,
});

const routeValues = (caseSpec) => ({
  rationale: "Operator-selected after reviewing the public synthetic intake.",
  source_or_capability_ref: caseSpec.route === "DEVELOP_NEW_CAPABILITY" ? "" : "client-reported-existing-method",
  route_basis: "Client-reviewed brief; applicability and science remain unresolved.",
  unresolved_conditions: ["scientific applicability", "rights", "reference adequacy"],
  next_decision: caseSpec.handoff_question,
  selected_by_assertion: "Synthetic evaluation operator",
  status_provenance: "LOCAL_MANUAL_ASSERTION",
  ...(caseSpec.route === "DEVELOP_NEW_CAPABILITY" ? {
    bounded_question: caseSpec.handoff_question,
    stop_condition: "Stop after one bounded finding; no numerical campaign is authorized.",
    restart_event: "The named lead returns the bounded finding.",
  } : {}),
});

const workbenchRoundTrip = async (packageValue, caseSpec) => {
  const raw = JSON.stringify(packageValue, null, 2);
  const inspection = await I.inspect(raw, F.strictJsonParse);
  const workspace = G.newWorkspace(component());
  const preview = G.previewIntakeImport(workspace, inspection);
  if (preview.action !== "CREATE_NEW_JOB") throw Error(`${caseSpec.id}: expected a new job preview`);
  const committed = G.commitIntakeImport(workspace, inspection, preview);
  const job = workspace.jobs.find((item) => item.job_id === committed.job_id);
  const design = job.designs.find((item) => item.design_id === job.working_design_id);
  if (design.route_plan.route !== "UNASSESSED") throw Error(`${caseSpec.id}: intake did not start UNASSESSED`);
  job.accountable_owner = "Ryan";
  job.lead = "S1";
  G.selectRoute(design, caseSpec.route, routeValues(caseSpec));
  const handoff = G.handoff(design, {
    request_id: `handoff-${caseSpec.id}`,
    recipient: caseSpec.route === "USE_EXISTING_CAPABILITY" ? "Engineering" : "S1",
    lead: caseSpec.route === "USE_EXISTING_CAPABILITY" ? "Engineering" : "S1",
    question: caseSpec.handoff_question,
    required_output: "Return one bounded finding and retain unknowns and negative results.",
    route: "MANUAL",
    input_refs: [job.intake_records[0].canonical_digest],
    required_authority: "No scientific, rights, execution or launch authority supplied.",
    allowance: "Preparation only; no execution allowance supplied.",
    stop_condition: "Stop after one bounded finding.",
    dependency_owner: "Named source or business owner",
    restart_event: "The bounded finding is returned.",
  });
  const replay = G.previewIntakeImport(workspace, inspection);
  if (replay.action !== "EXACT_REPLAY") throw Error(`${caseSpec.id}: exact replay was not deduplicated`);
  const changed = structuredClone(packageValue);
  changed.contact.organization = "changed bytes under the same identity";
  const changedInspection = await I.inspect(JSON.stringify(changed), F.strictJsonParse);
  const conflict = G.previewIntakeImport(workspace, changedInspection);
  if (conflict.action !== "IDENTITY_CONFLICT") throw Error(`${caseSpec.id}: changed same-identity bytes did not conflict`);
  let revision = null;
  if (caseSpec.exercise_revision) {
    const successor = structuredClone(packageValue);
    successor.brief.predecessor = { draft_id: inspection.draft.draft_id, revision_id: inspection.draft.revision_id, canonical_digest: inspection.canonical_digest };
    successor.brief.revision_id = "rev-002";
    successor.brief.answers.requested_result = { state: "VALUE", value: "Corrected public synthetic output request.", origin: "USER_ENTERED_LOCAL" };
    successor.brief.summary = I.summaryFor(successor.brief);
    const successorInspection = await I.inspect(JSON.stringify(successor), F.strictJsonParse);
    const successorPreview = G.previewIntakeImport(workspace, successorInspection);
    const result = G.commitIntakeImport(workspace, successorInspection, successorPreview);
    revision = { preview: successorPreview.action, result: result.action, intake_record_count: job.intake_records.length };
  }
  const saved = JSON.stringify(workspace);
  const reopened = G.readWorkspace(saved, componentReader);
  await G.revalidateIntakeRecords(reopened);
  const reopenedJob = reopened.jobs.find((item) => item.job_id === job.job_id);
  return {
    preview: preview.action,
    committed: committed.action,
    initial_route: "UNASSESSED",
    selected_route: design.route_plan.route,
    handoff_status: handoff.status,
    handoff_authority: handoff.authority,
    exact_replay: replay.action,
    changed_identity: conflict.action,
    revision,
    reopened_intake_records: reopenedJob.intake_records.length,
    science: design.decision.scientific_qualification,
    rights: design.scope.rights_scope,
    launch: design.decision.launch_authorization,
    source_assessment_responses: design.source_assessments.responses.length,
  };
};

const initialState = (caseSpec) => {
  const brief = I.newDraft(`pilot-${caseSpec.id}`, "rev-001");
  for (const [field, value] of Object.entries(caseSpec.initial_answers)) brief.answers[field] = { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" };
  brief.summary = I.summaryFor(brief);
  return {
    brief,
    pilot: blankPilot(),
    provenance: fieldNames().map((field) => ({ field, origin: field in caseSpec.initial_answers ? "CLIENT_TYPED" : "UNKNOWN", suggestion_id: null })),
    accepted: [], unresolved: [], history: new Map(), conversation: [],
  };
};

export const loadPilotSuite = async () => JSON.parse(await readFile(resolve(HERE, "pilot-design.executable.public.json"), "utf8"));

export const planPilotSuite = (suite) => ({
  mode: "PLAN_NO_NETWORK",
  suite_id: suite.suite_id,
  scenario_count: suite.cases.length,
  turn_count: suite.cases.reduce((sum, item) => sum + item.turns.length, 0),
  profile: "PILOT_DESIGN",
  knowledge_version: knowledge.knowledge_version,
  model_config_id: "gpt-5.6-luna:low:v1",
  shared_ledger_authority: "ask-carbon-provider-budget-v2",
  shared_monthly_ceiling_micro_usd: 50_000_000,
  nested_bakeoff_ceiling_micro_usd: 5_000_000,
  maximum_reserved_exposure_micro_usd: suite.cases.reduce((sum, item) => sum + item.turns.length, 0) * 5_640,
  network_calls: 0,
  live_gate: {
    status: "NOT_RUN_NAMED_INPUTS_MISSING",
    missing: ["exact permitted private staging route and access authentication", "installed provider secret", "provider-project retention disposition", "current shared-ledger snapshot and execution authorization"],
  },
  cases: suite.cases.map((item) => ({ id: item.id, turns: item.turns.length, actions: item.turns.flatMap((turn) => turn.actions.map((action) => action.type)), route: item.route })),
});

export const runPilotMock = async (suite) => {
  const runtime = makeRuntime();
  const worker = createWorker(knowledge);
  const originalFetch = globalThis.fetch;
  const originalNow = Date.now;
  const observations = [];
  let providerCalls = 0;
  let activeMock = null;
  globalThis.fetch = async (url) => {
    if (String(url) !== "https://api.openai.com/v1/responses" || !activeMock) throw Error("Mock mode blocked an unexpected network request");
    providerCalls += 1;
    return new Response(JSON.stringify(providerBody(activeMock.response, activeMock.id)), { status: 200, headers: { "content-type": "application/json" } });
  };
  Date.now = () => Date.parse(FIXED_ACCEPTED_AT);
  try {
    for (const caseSpec of suite.cases) {
      const state = initialState(caseSpec);
      const turns = [];
      for (let index = 0; index < caseSpec.turns.length; index += 1) {
        const turn = caseSpec.turns[index];
        const disclosedContext = contextFor(state);
        activeMock = { response: turn.mock, id: `${caseSpec.id}-${index + 1}` };
        const requestBody = { question: turn.user, mode: "PILOT_DESIGN", session_id: `session-${caseSpec.id}`, turns: state.conversation.slice(-10), draft_context: disclosedContext };
        const response = await worker.fetch(new Request("https://staging.example/api/ask-carbon", {
          method: "POST",
          headers: { origin: "https://staging.example", "content-type": "application/json", "cf-connecting-ip": `192.0.2.${observations.length + 10}` },
          body: JSON.stringify(requestBody),
        }), runtime.env);
        const body = await response.json();
        if (!response.ok || body.status !== "supported" || body.mode !== "PILOT_DESIGN") throw Error(`${caseSpec.id}: Worker returned ${response.status}/${body.error?.code ?? body.status}`);
        const actionOutcomes = applyActions(state, body, turn.actions, caseSpec.id, index + 1);
        state.conversation.push({ question: turn.user, answer: body.message });
        turns.push({
          turn: index + 1,
          user: turn.user,
          consent: "AFFIRMATIVE_ENABLE_AI_GUIDANCE_BEFORE_REQUEST",
          disclosed_context: disclosedContext,
          returned: { message: body.message, next_question: body.next_question, proposals: body.proposals, unresolved_assumptions: body.unresolved_assumptions, source_ids: body.sources.map((item) => item.id), maturity_note: body.maturity_note },
          client_actions: actionOutcomes,
          request_association: { mode: body.mode, knowledge_version: body.knowledge_version, model_config_id: body.model_config_id, request_id: "REDACTED_NONDETERMINISTIC_MOCK_REQUEST_ID" },
        });
      }
      const packageValue = reviewedPackage(state);
      for (const field of caseSpec.required_final) {
        if (!getField(state, field)) throw Error(`${caseSpec.id}: required final field ${field} is empty`);
      }
      for (const field of caseSpec.required_unknown) {
        if (state.brief.answers[field].state !== "UNKNOWN") throw Error(`${caseSpec.id}: ${field} did not remain unknown`);
      }
      const workbench = await workbenchRoundTrip(packageValue, caseSpec);
      observations.push({ id: caseSpec.id, evidence_class: "MOCK_PROVIDER_WORKFLOW_OBSERVATION", turns, final_brief: packageValue, workbench, human_quality_review: "NOT_PERFORMED" });
    }
  } finally {
    globalThis.fetch = originalFetch;
    Date.now = originalNow;
  }
  const snapshotResponse = await runtime.ledger.fetch(new Request("https://usage.internal/snapshot", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ now_ms: Date.now() }) }));
  const ledger = await snapshotResponse.json();
  const period = FIXED_ACCEPTED_AT.slice(0, 7);
  return {
    mode: "CONTRACT_MOCK_NO_EXTERNAL_NETWORK",
    suite_id: suite.suite_id,
    evidence_label: suite.evidence_label,
    scenario_count: observations.length,
    provider_attempts: providerCalls,
    external_provider_calls: 0,
    customer_sessions: 0,
    model_config_id: "gpt-5.6-luna:low:v1",
    knowledge_version: knowledge.knowledge_version,
    budget: { authority: "ask-carbon-provider-budget-v2", monthly_ceiling_micro_usd: 50_000_000, bakeoff_ceiling_micro_usd: 5_000_000, mock_settled_micro_usd: ledger.months?.[period]?.settled_micro_usd ?? 0, unresolved_micro_usd: ledger.months?.[period]?.unresolved_micro_usd ?? 0, note: "Mock ledger exercise only; no paid provider spend." },
    live_model_quality: "NOT_MEASURED",
    human_quality_review: "NOT_PERFORMED",
    public_activation: "DISABLED_UNCHANGED",
    observations,
  };
};
