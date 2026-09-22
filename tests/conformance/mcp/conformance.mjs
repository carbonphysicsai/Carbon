#!/usr/bin/env node
// Carbon MCP conformance runner.
//
// Points an independent MCP client at a Carbon research endpoint and reports,
// check by check, whether it honours the published contract. It is a consumer:
// it never imports Carbon source and never assumes it built the server.
//
// It is not a security qualification and not a claim that a conforming server
// is a qualified one.
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const PREFIX = "carbon_research_v2__";
const CATALOGUE_URI = "carbon://research/v1/catalogue";
const CAPABILITIES_URI = "carbon://research/v1/capabilities";
// A coded refusal as it appears on the wire. The slug is what a client branches
// on, so it is extracted rather than pattern-matched against a fixed list: a
// server may declare a vocabulary this runner has never heard of, and the
// requirement is that it declares whatever it emits.
const REFUSAL_SLUG =
  /([A-Z][A-Z_]{3,39}); ?dispatch_may_have_occurred=(true|false)(?:; ?next_action=([^"\\]*))?/g;
const OPERATION_ID_PATTERN = /^[A-Za-z0-9._:-]{16,114}$/;
const TASK_ID_PATTERN = /^rtsk_[a-f0-9]{64}$/;
const ERROR_PATTERN =
  /(INVALID_ARGUMENT|OWNER_BINDING|OPERATIONAL_STOP|INVALID_RESULT);\s*dispatch_may_have_occurred=(true|false)/;
// A leaked absolute path, home directory or bearer-shaped secret in an error.
const LEAK_PATTERNS = [
  /\/(home|Users|root|private|var\/folders)\//,
  /[A-Za-z]:\\\\/,
  /\b(Bearer|token|secret|password|api[_-]?key)\b\s*[:=]\s*\S+/i,
  /\b[A-Fa-f0-9]{40,}\b/,
];

function parseTarget(argv) {
  const at = (flag) => {
    const index = argv.indexOf(flag);
    return index === -1 ? null : argv[index + 1] ?? null;
  };
  const stdio = at("--stdio");
  const http = at("--http");
  if (stdio && http) throw Error("Choose exactly one of --stdio or --http");
  if (stdio) return { transport: "stdio", launch: JSON.parse(stdio) };
  if (http) return { transport: "http", url: http, token: at("--token") };
  throw Error(
    "Usage: conformance.mjs --stdio '<launch json>' | --http <url> [--token <bearer>]",
  );
}

async function connect(target) {
  if (target.transport === "stdio") {
    const transport = new StdioClientTransport({ ...target.launch, stderr: "pipe" });
    transport.stderr?.on("data", () => {});
    const client = new Client({ name: "carbon-mcp-conformance", version: "1.0.0" });
    await client.connect(transport);
    return client;
  }
  const { StreamableHTTPClientTransport } = await import(
    "@modelcontextprotocol/client/streamableHttp"
  );
  const transport = new StreamableHTTPClientTransport(new URL(target.url), {
    requestInit: target.token
      ? { headers: { Authorization: "Bearer " + target.token } }
      : undefined,
  });
  const client = new Client({ name: "carbon-mcp-conformance", version: "1.0.0" });
  await client.connect(transport);
  return client;
}

// A check reports PASS, FAIL or UNDETERMINED. UNDETERMINED is never silent and
// never counts as conformance: it means the runner could not obtain the
// evidence, which is a result the caller must act on rather than ignore.
// A check with a negative control has a stub that provably fails it, so the
// check is demonstrated falsifiable. A check without one is asserted but not
// demonstrated: it could be probing something another layer already refuses, or
// asserting a condition that holds trivially, and a PASS on it is weaker
// evidence. This list is asserted against the shipped stubs by the test suite,
// so it cannot drift from reality.
// Test-only expectation mutation. Flipping a shape check's own expectation and
// confirming the real server then fails it proves the check discriminates --
// that it reads what it claims to read. It is weaker than a non-conforming
// server being rejected, but it is most of the value for shape checks and it
// would have caught the leak check that probed a layer it could never reach.
const MUTATE = process.env.CARBON_CONFORMANCE_MUTATE || null;
const mutating = (name) => MUTATE === name;

// Behavioural requirements need a stub; shape requirements can be falsified by
// mutating the expectation. A check with neither is asserted but not shown
// falsifiable, and a PASS on it is weaker evidence.
const MUTATION_CONTROLLED = new Set([
  "surface_catalogue_is_versioned",
  "surface_catalogue_separates_surface_from_science",
  "record_policy_is_declared",
  "catalogue_prefix_and_strict_schemas",
  "catalogue_rejects_caller_supplied_principal",
  "catalogue_uses_objects_not_json_envelopes",
  "strict_inputs_reject_encoded_objects",
  "schema_rejection_precedes_dispatch",
  "adapter_error_contract",
]);
const STUB_CONTROLLED = new Set([
  "surface_catalogue_matches_served_tools",
  "refusal_vocabulary_is_declared",
  "refusal_next_action_is_fixed_and_declared",
  "capacity_bound_is_declared_and_honoured",
  "operation_identity_replay_does_not_redispatch",
  "operation_identity_conflict_is_refused",
  "cancellation_is_a_request_not_a_release",
  "errors_do_not_leak_internals",
  "capability_discovery_is_performable",
  "durable_identity_survives_reconnect",
]);

const checks = [];
function record(id, requirement, status, detail) {
  checks.push({
    id,
    requirement,
    status,
    detail,
    control: STUB_CONTROLLED.has(id)
      ? "stub"
      : MUTATION_CONTROLLED.has(id)
        ? "mutation"
        : "none",
  });
}
async function check(id, requirement, body) {
  try {
    const detail = await body();
    record(id, requirement, "PASS", detail ?? "");
  } catch (error) {
    const undetermined = error && error.__undetermined;
    record(
      id,
      requirement,
      undetermined ? "UNDETERMINED" : "FAIL",
      String(error?.message ?? error).slice(0, 400),
    );
  }
}
const undetermined = (message) =>
  Object.assign(Error(message), { __undetermined: true });

const practice = (operationId, steps = 512) => ({
  operation_id: operationId,
  kind: "practice",
  strategy: { parameters: { steps } },
  action: null,
  arguments: null,
  hypothesis: "Conformance probe of durable operation identity",
  expected_effect: "One durable charge for one business operation",
});

function identity(value) {
  // The durable identity a caller would use to decide whether work was
  // dispatched twice. Tool result shape is contract; wording is not.
  const structured = value?.structuredContent;
  if (!structured) throw Error("tool result carried no structuredContent");
  return JSON.stringify(structured);
}

/** Every coded refusal the run has seen, as {slug, dispatch, nextAction}. */
function refusals(observed) {
  const found = [];
  for (const text of observed) {
    // The wire text arrives JSON-encoded inside the tool result, so the
    // next_action runs to the end of the encoded string rather than to a
    // delimiter this runner gets to choose.
    for (const match of text.matchAll(REFUSAL_SLUG))
      found.push({
        slug: match[1],
        dispatch: match[2] === "true",
        nextAction: (match[3] ?? "").replace(/\s+$/, "") || null,
      });
  }
  return found;
}

export async function run(target) {
  const stamp = "conformance-" + Date.now().toString(36).padStart(10, "0");
  let client = await connect(target);
  // Adapter-level failures cannot be triggered portably on an arbitrary
  // conforming server, so every refusal seen during the run is collected and
  // the error contract is judged against whatever the server actually emitted.
  const observedErrors = [];
  // The call that produced each refusal, so a refusal can be provoked a second
  // time without the runner having to know which probe on which fixture
  // happens to trigger a coded failure. Guessing that would make the suite
  // depend on a server's internal state machine, which is the opposite of what
  // a consumer-side suite is for.
  const refusingCalls = [];
  const call = async (operation, args) => {
    const result = await client.callTool({ name: PREFIX + operation, arguments: args });
    if (result.isError) {
      observedErrors.push(JSON.stringify(result.content ?? ""));
      refusingCalls.push({ operation, args });
    }
    return result;
  };

  await check(
    "catalogue_prefix_and_strict_schemas",
    "Every tool is namespaced and accepts a closed object schema",
    async () => {
      const { tools } = await client.listTools();
      assert(tools.length > 0, "server advertised no tools");
      for (const tool of tools) {
        const expected = mutating("prefix") ? "xyzzy_" : PREFIX;
        assert(
          tool.name.startsWith(expected),
          `tool ${tool.name} is outside the ${expected} namespace`,
        );
        assert(tool.inputSchema, `tool ${tool.name} has no input schema`);
        assert.equal(
          tool.inputSchema.additionalProperties,
          false,
          `tool ${tool.name} accepts unspecified properties`,
        );
      }
      return `${tools.length} tools, all namespaced with closed schemas`;
    },
  );

  await check(
    "catalogue_rejects_caller_supplied_principal",
    "No tool lets the caller name the acting principal",
    async () => {
      const { tools } = await client.listTools();
      for (const tool of tools) {
        const properties = tool.inputSchema?.properties ?? {};
        assert(
          mutating("principal") ? "principal" in properties : !("principal" in properties),
          `tool ${tool.name} principal exposure did not match the expectation`,
        );
      }
      return "no tool exposes a principal argument";
    },
  );

  await check(
    "catalogue_uses_objects_not_json_envelopes",
    "Structured arguments are real JSON objects, not encoded strings",
    async () => {
      const { tools } = await client.listTools();
      for (const tool of tools) {
        for (const name of Object.keys(tool.inputSchema?.properties ?? {})) {
          assert(
            mutating("json_envelopes") ? name.endsWith("_json") : !name.endsWith("_json"),
            `tool ${tool.name} field ${name} did not match the envelope expectation`,
          );
        }
      }
      return "no tool exposes a *_json string envelope";
    },
  );

  await check(
    "strict_inputs_reject_encoded_objects",
    "A JSON string where an object is required is refused",
    async () => {
      const id = stamp + "-strict";
      const encoded = { ...practice(id), strategy: JSON.stringify({ parameters: {} }) };
      const result = await call("start_research_task", encoded);
      assert.equal(
        result.isError,
        mutating("encoded_accepted") ? undefined : true,
        "encoded JSON string handling did not match the expectation",
      );
      return "encoded object argument refused";
    },
  );

  await check(
    "schema_rejection_precedes_dispatch",
    "Malformed input is refused without claiming work was dispatched",
    async () => {
      for (const probe of [
        { ...practice(stamp + "-badkind"), kind: "not-a-kind" },
        { ...practice(stamp + "-badid"), operation_id: "short" },
        { ...practice(stamp + "-extra"), unexpected_property: true },
      ]) {
        const result = await call("start_research_task", probe);
        assert.equal(result.isError, true, "malformed input was not refused");
        const text = JSON.stringify(result.content ?? "");
        assert(
          mutating("schema_claims_dispatch")
            ? /dispatch_may_have_occurred=true/.test(text)
            : !/dispatch_may_have_occurred=true/.test(text),
          "schema rejection dispatch claim did not match the expectation",
        );
      }
      return "malformed input refused, and no refusal claimed dispatch";
    },
  );

  await check(
    "operation_identity_replay_does_not_redispatch",
    "Repeating one operation identity with identical input dispatches once",
    async () => {
      const id = stamp + "-replay";
      const first = await call("start_research_task", practice(id));
      if (first.isError)
        throw undetermined(
          "server refused the baseline operation: " +
            JSON.stringify(first.content).slice(0, 200),
        );
      const repeated = await call("start_research_task", practice(id));
      assert.equal(repeated.isError, undefined ?? false, "replay was refused");
      assert.equal(
        identity(repeated),
        identity(first),
        "replay returned a different result, so work was dispatched twice",
      );
      return "identical replay returned the identical durable result";
    },
  );

  await check(
    "operation_identity_conflict_is_refused",
    "Changed input under an existing operation identity conflicts",
    async () => {
      const id = stamp + "-conflict";
      const first = await call("start_research_task", practice(id, 512));
      if (first.isError)
        throw undetermined("server refused the baseline operation for conflict check");
      const changed = await call("start_research_task", practice(id, 1024));
      assert.equal(
        changed.isError,
        true,
        "server accepted changed input under an existing operation identity",
      );
      return "changed input under an existing identity was refused";
    },
  );

  await check(
    "cancellation_is_a_request_not_a_release",
    "Cancellation never asserts that resources were released",
    async () => {
      const { tools } = await client.listTools();
      const named = tools.some((tool) => tool.name === PREFIX + "cancel_research_task");
      if (!named) throw undetermined("server advertises no cancel_research_task tool");
      const result = await call("cancel_research_task", {
        operation_id: stamp + "-cancel",
        task_id: "rtsk_" + "0".repeat(64),
      });
      const text = JSON.stringify(result.structuredContent ?? result.content ?? "");
      assert(
        !/"(released|resources_released|cleanup_confirmed)"\s*:\s*true/i.test(text),
        "cancellation claimed resources were released",
      );
      assert(
        !/\b(resources released|cleanup confirmed|workers stopped)\b/i.test(text),
        "cancellation asserted release in prose",
      );
      return "cancellation reported a request, not a release";
    },
  );

  await check(
    "capability_discovery_is_performable",
    "Every advertised resource can actually be read",
    async () => {
      const { resources } = await client.listResources();
      assert(resources.length > 0, "server advertised no resources");
      for (const resource of resources) {
        const read = await client.readResource({ uri: resource.uri });
        assert(
          read?.contents?.length,
          `advertised resource ${resource.uri} returned no contents`,
        );
      }
      return `${resources.length} advertised resources all readable`;
    },
  );

  await check(
    "durable_identity_survives_reconnect",
    "A repeated operation identity survives a client reconnect",
    async () => {
      const id = stamp + "-reconnect";
      const before = await call("start_research_task", practice(id));
      if (before.isError)
        throw undetermined("server refused the baseline operation before reconnect");
      await client.close();
      client = await connect(target);
      const after = await client.callTool({
        name: PREFIX + "start_research_task",
        arguments: practice(id),
      });
      assert.notEqual(after.isError, true, "replay after reconnect was refused");
      assert.equal(
        identity(after),
        identity(before),
        "operation identity was lost across reconnect",
      );
      return "identity preserved across a full client reconnect";
    },
  );

  await check(
    "errors_do_not_leak_internals",
    "Errors reveal no path, credential or internal identifier",
    async () => {
      // Probe the schema layer, then judge every refusal the run produced.
      // Probing malformed input alone would miss a leak in an adapter-level
      // failure, because malformed input never reaches the adapter.
      await call("start_research_task", {
        ...practice(stamp + "-leak"),
        kind: "not-a-kind",
      });
      await call("start_research_task", { ...practice(stamp + "-leak2"), seconds: 1 });
      assert(observedErrors.length > 0, "no refusal was produced to inspect");
      for (const text of observedErrors) {
        for (const pattern of LEAK_PATTERNS) {
          assert(
            !pattern.test(text),
            `a refusal matched leak pattern ${pattern}: ${text.slice(0, 200)}`,
          );
        }
      }
      return `${observedErrors.length} refusal(s) carried no path, credential or long hex identifier`;
    },
  );

  await check(
    "adapter_error_contract",
    "An adapter failure names a known code and an explicit dispatch flag",
    async () => {
      const vocabulary = mutating("impossible_code")
        ? /(NEVER_A_REAL_CARBON_CODE)/
        : /(INVALID_ARGUMENT|OWNER_BINDING|OPERATIONAL_STOP|INVALID_RESULT)/;
      const coded = observedErrors.filter((text) => vocabulary.test(text));
      if (mutating("impossible_code"))
        assert(coded.length > 0, "no refusal carried the impossible code");
      if (!coded.length)
        throw undetermined(
          "no adapter-level failure occurred during this run, so the coded " +
            "error contract could not be observed; schema rejections were " +
            "checked separately",
        );
      for (const text of coded)
        assert(
          ERROR_PATTERN.test(text),
          "a coded failure omitted dispatch_may_have_occurred=<bool>: " +
            text.slice(0, 160),
        );
      return `${coded.length} adapter failure(s) carried a code and dispatch flag`;
    },
  );

  // --- the versioned surface catalogue, and the refusal guidance with it -----
  //
  // These cover what landed in #269: a catalogue describing the server rather
  // than the science, and a next step attached to every refusal. The runner
  // never hardcodes Carbon's wording. It requires the server to be internally
  // consistent with what it publishes, which is the only thing a third party
  // pinning the document can actually rely on.
  let surface = null;

  const readJson = async (uri) => {
    const read = await client.readResource({ uri });
    const text = read?.contents?.[0]?.text;
    if (typeof text !== "string") throw Error(`resource ${uri} returned no text`);
    return JSON.parse(text);
  };

  await check(
    "surface_catalogue_is_versioned",
    "The surface catalogue is served, versioned, and claims no official standing",
    async () => {
      let document;
      try {
        document = await readJson(CATALOGUE_URI);
      } catch (error) {
        throw Error(
          `${CATALOGUE_URI} could not be read as JSON: ${String(error.message).slice(0, 160)}`,
        );
      }
      surface = document;
      const versioned =
        typeof document.schema === "string" && document.schema.length > 0;
      assert(
        mutating("catalogue_unversioned") ? !versioned : versioned,
        "catalogue schema version did not match the expectation",
      );
      assert(
        typeof document.sdk_version === "string",
        "catalogue carries no sdk_version, so a client cannot tell builds apart",
      );
      // A surface description must not be readable as a claim of standing.
      assert.equal(
        document.official_eligible,
        false,
        "catalogue did not declare official_eligible=false",
      );
      return `catalogue ${document.schema} at sdk ${document.sdk_version}`;
    },
  );

  await check(
    "surface_catalogue_matches_served_tools",
    "The catalogue describes exactly the operations the server serves",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const { tools } = await client.listTools();
      const served = new Set(tools.map((tool) => tool.name));
      const advertised = new Set(surface.operations ?? []);
      const missing = [...advertised].filter((name) => !served.has(name));
      const undeclared = [...served].filter((name) => !advertised.has(name));
      assert.deepEqual(
        missing,
        [],
        `catalogue advertises operations the server does not serve: ${missing}`,
      );
      assert.deepEqual(
        undeclared,
        [],
        `server serves operations the catalogue omits: ${undeclared}`,
      );
      return `${advertised.size} advertised operations all served, none undeclared`;
    },
  );

  await check(
    "surface_catalogue_separates_surface_from_science",
    "The surface catalogue and the scientific capabilities are distinct documents",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const capabilities = await readJson(CAPABILITIES_URI);
      // The separation is what lets a client tell a surface change from a
      // science change instead of rediscovering one as the other.
      const separate =
        JSON.stringify(capabilities) !== JSON.stringify(surface) &&
        typeof surface.limits === "object" &&
        surface.limits !== null;
      assert(
        mutating("catalogue_conflates_surface") ? !separate : separate,
        "surface/science separation did not match the expectation",
      );
      for (const uri of [CAPABILITIES_URI, CATALOGUE_URI])
        assert(
          (surface.resources ?? []).includes(uri),
          `catalogue omits ${uri} from the resources it says it serves`,
        );
      return "surface catalogue and capabilities are separate, and both are listed";
    },
  );

  await check(
    "record_policy_is_declared",
    "The catalogue states what a per-call record keeps about the caller",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const records = surface.records ?? {};
      assert(
        typeof records.schema === "string" && records.schema.length > 0,
        "catalogue declares no record schema, so a miner cannot pin what is kept",
      );
      const withholds = records.arguments_recorded === false;
      assert(
        mutating("records_claim_arguments") ? !withholds : withholds,
        "record argument policy did not match the expectation",
      );
      // Stated plainly because the runner cannot see the server's own logs: a
      // declaration is what a client can check, and it is not the same as
      // evidence that arguments are absent from the records themselves.
      return `records ${records.schema}, arguments_recorded=${records.arguments_recorded} (declared, not observed)`;
    },
  );

  await check(
    "refusal_vocabulary_is_declared",
    "Every refusal code the server emits appears in the vocabulary it publishes",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const declared = surface.refusals ?? {};
      const slugs = Object.keys(declared);
      assert(slugs.length > 0, "catalogue publishes no refusal vocabulary");
      for (const slug of slugs) {
        const action = declared[slug]?.next_action;
        assert(
          typeof action === "string" && action.trim().length > 0,
          `declared refusal ${slug} has no next_action: a client learns what ` +
            "happened and not what now",
        );
      }
      const emitted = [...new Set(refusals(observedErrors).map((r) => r.slug))];
      const outside = emitted.filter((slug) => !slugs.includes(slug));
      assert.deepEqual(
        outside,
        [],
        `server emitted refusal codes it never declared: ${outside}`,
      );
      return `${slugs.length} declared, ${emitted.length} observed, none undeclared`;
    },
  );

  await check(
    "refusal_next_action_is_fixed_and_declared",
    "A refusal carries the next step its catalogue declares, identically each time",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const declared = surface.refusals ?? {};
      // One sample cannot show that the text is fixed, so every call that was
      // refused during this run is re-issued once under a fresh operation id.
      // Some will succeed the second time; any that refuses again is a genuine
      // second sample of the same guidance.
      let repeated = 0;
      for (const [index, previous] of [...refusingCalls].entries()) {
        if (typeof previous.args?.operation_id !== "string") continue;
        const again = await call(previous.operation, {
          ...previous.args,
          operation_id: `${stamp}-again-${index}`,
        });
        if (again.isError) repeated += 1;
      }
      const observed = refusals(observedErrors).filter((r) => r.nextAction);
      if (!observed.length)
        throw undetermined(
          "no coded refusal carrying a next_action occurred during this run",
        );
      const byslug = new Map();
      for (const refusal of observed) {
        assert(
          declared[refusal.slug],
          `refusal ${refusal.slug} carried guidance but is not in the catalogue`,
        );
        assert.equal(
          refusal.nextAction,
          declared[refusal.slug].next_action,
          `refusal ${refusal.slug} carried guidance that disagrees with the ` +
            "catalogue, so a client cannot pin what it was promised",
        );
        const seen = byslug.get(refusal.slug) ?? new Set();
        seen.add(refusal.nextAction);
        byslug.set(refusal.slug, seen);
      }
      for (const [slug, texts] of byslug)
        assert.equal(
          texts.size,
          1,
          `refusal ${slug} carried ${texts.size} different next steps across ` +
            "this run; provider text on the wire is how internal detail escapes",
        );
      // Said precisely: matching the catalogue is shown for every sample, while
      // "fixed across calls" is only shown for a slug seen more than once.
      const stable = [...byslug.entries()].filter(([, texts]) => texts.size >= 1);
      const multiple = [...byslug.keys()].filter(
        (slug) => observed.filter((r) => r.slug === slug).length > 1,
      );
      return (
        `${observed.length} refusal(s) across ${stable.length} slug(s) matched the ` +
        `catalogue exactly; ${repeated} refusal(s) provoked again; fixed text ` +
        `demonstrated for ${multiple.length} slug(s) seen more than once` +
        (multiple.length ? "" : " (none, so stability is asserted not shown)")
      );
    },
  );

  await check(
    "capacity_bound_is_declared_and_honoured",
    "The concurrency bound is published, and refusing for it claims no dispatch",
    async () => {
      if (!surface) throw undetermined("the surface catalogue could not be read");
      const limits = surface.limits ?? {};
      const limit = limits.max_concurrent_calls;
      const deadline = limits.queue_deadline_seconds;
      assert(
        Number.isInteger(limit) && limit > 0,
        "catalogue publishes no positive max_concurrent_calls",
      );
      assert(
        typeof deadline === "number" && deadline > 0,
        "catalogue publishes no positive queue_deadline_seconds",
      );
      // Push past the published bound. A conforming server may serve all of
      // these or refuse some for capacity; what it may not do is leave one
      // neither served nor refused, or refuse for capacity while saying work
      // may have been dispatched.
      const before = observedErrors.length;
      const started = Date.now();
      const settled = await Promise.race([
        Promise.allSettled(
          Array.from({ length: limit + 2 }, (_, index) =>
            call("dry_validate", {
              operation_id: `${stamp}-capacity-${index}`,
              strategy: { parameters: { steps: 1 } },
            }),
          ),
        ),
        new Promise((resolve) =>
          setTimeout(() => resolve(null), (deadline + 60) * 1000),
        ),
      ]);
      assert(
        settled !== null,
        `${limit + 2} concurrent calls did not all settle within the published ` +
          `${deadline}s queue deadline plus a minute`,
      );
      const rejected = settled.filter((outcome) => outcome.status === "rejected");
      assert.equal(
        rejected.length,
        0,
        `a call past the published bound failed at the transport rather than ` +
          `being refused: ${String(rejected[0]?.reason?.message).slice(0, 160)}`,
      );
      const capacity = refusals(observedErrors.slice(before)).filter(
        (refusal) => /CAPACITY/.test(refusal.slug),
      );
      for (const refusal of capacity)
        assert.equal(
          refusal.dispatch,
          false,
          `${refusal.slug} claimed work may have been dispatched; nothing is ` +
            "dispatched before capacity is granted, and claiming otherwise " +
            "manufactures a reconciliation-required state",
        );
      return capacity.length
        ? `${capacity.length} capacity refusal(s), all claiming no dispatch`
        : `bound of ${limit} published and honoured; ${limit + 2} concurrent ` +
          "calls all settled without a capacity refusal, so that path was " +
          "declared but not exercised";
    },
  );

  await client.close().catch(() => {});

  const summary = { pass: 0, fail: 0, undetermined: 0 };
  for (const item of checks) {
    if (item.status === "PASS") summary.pass += 1;
    else if (item.status === "FAIL") summary.fail += 1;
    else summary.undetermined += 1;
  }
  summary.controlled_by_stub = checks.filter((c) => c.control === "stub").length;
  summary.controlled_by_mutation = checks.filter(
    (c) => c.control === "mutation",
  ).length;
  summary.uncontrolled = checks.filter((c) => c.control === "none").length;
  return {
    schema: "carbon.mcp-conformance.report.v1",
    target: target.transport,
    checks,
    summary,
    // Undetermined is not conformance. A caller who cannot obtain the evidence
    // has not learned that the server conforms.
    conformant: summary.fail === 0 && summary.undetermined === 0,
    authority: "PROTOCOL_CONFORMANCE_ONLY_NOT_SECURITY_OR_SCIENTIFIC_QUALIFICATION",
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  let report;
  try {
    report = await run(parseTarget(process.argv.slice(2)));
  } catch (error) {
    process.stderr.write("conformance runner could not execute: " + error.message + "\n");
    process.exit(2);
  }
  process.stderr.write(
    `falsifiability: ${report.summary.controlled_by_stub} proven by a ` +
      `non-conforming stub, ${report.summary.controlled_by_mutation} by ` +
      `expectation mutation, ${report.summary.uncontrolled} neither.\n`,
  );
  for (const item of report.checks) {
    process.stderr.write(
      `${item.status.padEnd(13)} ${("[" + item.control + "]").padEnd(12)} ` +
        `${item.id}\n                ${item.detail}\n`,
    );
  }
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  process.exit(report.conformant ? 0 : 1);
}
