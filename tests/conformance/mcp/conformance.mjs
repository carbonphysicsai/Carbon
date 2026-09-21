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
  "catalogue_prefix_and_strict_schemas",
  "catalogue_rejects_caller_supplied_principal",
  "catalogue_uses_objects_not_json_envelopes",
  "strict_inputs_reject_encoded_objects",
  "schema_rejection_precedes_dispatch",
  "adapter_error_contract",
]);
const STUB_CONTROLLED = new Set([
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

export async function run(target) {
  const stamp = "conformance-" + Date.now().toString(36).padStart(10, "0");
  let client = await connect(target);
  // Adapter-level failures cannot be triggered portably on an arbitrary
  // conforming server, so every refusal seen during the run is collected and
  // the error contract is judged against whatever the server actually emitted.
  const observedErrors = [];
  const call = async (operation, args) => {
    const result = await client.callTool({ name: PREFIX + operation, arguments: args });
    if (result.isError) observedErrors.push(JSON.stringify(result.content ?? ""));
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
