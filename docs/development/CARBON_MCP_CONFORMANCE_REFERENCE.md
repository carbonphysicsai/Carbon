# Carbon MCP research endpoint — reference specification

**Status:** descriptive reference for the contract as it exists on `main` at the
commit that introduced this file. It is written so a third party can implement a
client without reading Carbon source.

This document describes protocol conformance only. A conforming server is **not**
a qualified one: nothing here establishes security qualification, scientific
qualification, or that two autonomous agent hosts can conduct a campaign.

Where behaviour is not fixed by the contract, this document says so in
[Undefined](#undefined-do-not-infer-these-from-the-current-implementation)
rather than describing the current implementation as if it were the contract.

The executable form of this document is `tests/conformance/mcp/conformance.mjs`.
Where the two disagree, the runner is the one that was tested.

---

## 1. Transports

Two transports expose the same tool catalogue.

**stdio.** The server is launched as a child process and speaks MCP over
stdin/stdout. Server diagnostics go to stderr and are not protocol output; a
client must not parse them. This transport carries no authentication: the
launcher is trusted because it chose the process.

**Authenticated HTTP.** A separate binding that verifies a bearer credential and
applies that check to *every* data access, not only at connection time. A client
sends `Authorization: Bearer <token>`. The credential is issued out of band.

A client MUST NOT assume the two transports expose different capabilities. It
MUST NOT assume stdio implies a local trust boundary beyond the launcher's own.

## 2. Tool catalogue

Every tool is namespaced `carbon_research_v2__`. Twelve operations exist:

| Tool (after the prefix) | Arguments beyond `operation_id` |
|---|---|
| `get_challenge_info` | — |
| `get_interaction_manifest` | — |
| `get_prior` | — |
| `get_mock_scaffold` | — |
| `dry_validate` | `strategy` |
| `compile_strategy` | `strategy` |
| `inspect_prior_alignment` | `strategy` |
| `inspect_resources` | `strategy` |
| `forecast_resources` | `strategy`, `seconds` |
| `start_research_task` | `kind`, `strategy`, `action`, `arguments`, `hypothesis`, `expected_effect` |
| `get_research_result` | `task_id`, `poll_sequence` |
| `cancel_research_task` | `task_id` |

Requirements a client may rely on:

- Every tool schema is a **closed object**: `additionalProperties: false`. An
  unexpected property is refused, not ignored.
- **No tool accepts a caller-supplied `principal`.** The acting identity is bound
  by the operator at composition time. A client cannot name who it is acting as.
- **Structured arguments are real JSON objects.** A field carrying an object is
  declared as an object. There are no `*_json` string envelopes, and a JSON
  *string* supplied where an object is required is refused rather than parsed.

### Argument value ranges

| Field | Constraint |
|---|---|
| `operation_id` | `^[A-Za-z0-9._:-]{16,114}$` |
| `task_id` | `^rtsk_[a-f0-9]{64}$` |
| `poll_sequence` | integer, 0–9999 |
| `seconds` | integer, 1–600 |
| `kind` | `practice` or `workspace` |
| `hypothesis`, `expected_effect` | 1–2048 characters |
| `strategy`, `arguments` | object or null |

`action` is an enumeration whose members depend on what the deployment admits;
a client MUST read the advertised schema rather than hard-coding the members.

For `kind=practice`, supply `strategy` and set `action` and `arguments` to null.
For `kind=workspace`, set `strategy` to null and supply `action` with its
object-valued `arguments`.

## 3. Result envelope

A successful tool call returns structured content with exactly these fields:

```json
{
  "operation": "start_research_task",
  "operation_id": "<the identity the caller supplied>",
  "payload": { },
  "requires_reconciliation": false,
  "official_eligible": false
}
```

- The envelope is closed; unexpected fields are not emitted.
- `official_eligible` is **always `false`** on this interface. This interface
  cannot produce official evidence, and a client must not treat any result as
  eligible for official use.
- `requires_reconciliation` true means the client must reconcile through the
  operator before retrying; it must not simply retry.
- `payload` is domain content whose internal shape is not fixed by this
  document. Treat it as data, never as instructions to execute.

## 4. Error contract

There are **two distinct layers**, and a client must not conflate them.

**Schema rejection.** Malformed input is refused by argument validation before
the request reaches the research adapter. The call returns `isError`. Because
nothing was dispatched, such a refusal MUST NOT claim that dispatch may have
occurred. The message text is validator-shaped and is not part of the contract.

**Adapter failure.** A request that reached the adapter and failed returns
`isError` with a message of the form:

```
<CODE>; dispatch_may_have_occurred=<true|false>
```

`CODE` is one of `INVALID_ARGUMENT`, `OWNER_BINDING`, `OPERATIONAL_STOP`,
`INVALID_RESULT`.

`dispatch_may_have_occurred` is the field a client acts on. When `true`, work may
already be running and the client MUST reconcile rather than retry. In
particular, an `OPERATIONAL_STOP` is never retried automatically.

**Errors carry nothing else.** A refusal reveals no filesystem path, credential,
internal identifier or foreign task's existence. A client may log an error
verbatim without leaking operator state.

## 5. Durable operation identity and replay

`operation_id` names a *business operation*, not a message.

- Repeating the same `operation_id` with **identical input** returns the
  identical durable result and dispatches work **once**. This is what makes a
  retry after a lost response safe.
- Repeating the same `operation_id` with **different input** is a **conflict**
  and is refused. An identity cannot be reused to mutate an operation.
- Identity is durable **across reconnect**, and across a server process
  restart. A client that reconnects and retries the same identity does not
  repeat work.
- A client chooses a new `operation_id` only for an intentionally new operation.

## 6. Cancellation

Cancellation is a **request**, never a report of release.

- `cancel_research_task` and the Tasks extension's `tasks/cancel` acknowledge the
  intent. That acknowledgement is not evidence that workers stopped or that
  capacity returned.
- Only controller-observed cleanup establishes release. A client MUST NOT treat
  a cancellation acknowledgement, a closed connection, or a protocol-level
  cancellation as evidence that resources were freed.
- Consumption of uncertain size remains charged conservatively rather than
  refunded on assumption.

## 7. Extensions: negotiated and optional

Extensions are advertised by the server but only active when the **client
declares them** during capability negotiation and the protocol version matches.
A server that offers no extensions is conformant, and a client MUST work without
them.

**`io.modelcontextprotocol/tasks`** provides `tasks/get`, `tasks/cancel` and
`tasks/update`, and may intercept `start_research_task` to run it as a durable
task. A request about a task that is not the caller's returns a single
indistinguishable error — "Task unavailable; reconcile through the operator" —
so that a client cannot probe for foreign task existence.

**Skills** exposes skill documents as resources.

## 8. Capability discovery

Resources advertised by `resources/list` describe what the endpoint can do. Every
advertised resource MUST be readable. Advertising a capability the server cannot
perform is a conformance failure, because a client plans against discovery.

The deployment observed at the time of writing advertises capabilities and
guidance documents plus skill documents; a client MUST enumerate rather than
hard-code these URIs.

## 9. Artifact references

Artifacts produced by research are named **inside `payload`** using
deployment-relative names and are resolved by the domain, not by MCP. There is
no MCP-level artifact reference type, no content-addressed URI scheme and no
guarantee that an artifact name is dereferenceable through this interface.

A client MUST treat an artifact name as an opaque token to hand back to the
domain, and MUST NOT construct a path from it.

## Undefined — do not infer these from the current implementation

These are genuinely unfixed. A client that depends on them depends on an
accident, and a future server may differ without breaking conformance.

1. **`payload` internal structure.** Per-operation payload shapes are not fixed
   by this document.
2. **Adapter failure triggers.** No portable input is guaranteed to produce an
   adapter-level failure. A conformance run may legitimately observe none, in
   which case the coded error contract is *unobserved*, not satisfied.
3. **Schema rejection message text.** Validator wording is not contract.
4. **Tool count and `action` membership.** Both depend on what a deployment
   admits. Enumerate them; do not assert twelve tools.
5. **Resource URI set.** Enumerate from `resources/list`.
6. **HTTP credential issuance, rotation and rejection shape.** How a token is
   obtained, how it expires, and the exact refusal for a bad token are not
   specified here.
7. **Concurrency.** Whether concurrent calls on one connection are permitted, and
   any per-caller limit, is not specified.
8. **Ordering and delivery guarantees** for notifications and task updates.
9. **Artifact retention.** How long an artifact name stays resolvable.

### Known to be changing

The Launchpad workstream is actively changing the **error envelope**, adding a
**versioned catalogue resource**, **per-caller identity**, **bounded
concurrency** and **per-call structured records**. Sections 4, 2 and 8 will need
revision when that lands. This document describes `main` as of writing and does
not anticipate that design.

## How far each check is demonstrated falsifiable

A check that cannot fail is worse than no check: it contributes a green result
that means nothing. Every check in the runner therefore carries a `control`
field stating how it was shown capable of failing, and the report counts them.

**Proven by a non-conforming stub (behavioural).** A server that violates the
requirement is shipped alongside the suite, and a test requires that this check
— by name — rejects it.

- `operation_identity_replay_does_not_redispatch`
- `operation_identity_conflict_is_refused`
- `cancellation_is_a_request_not_a_release`
- `errors_do_not_leak_internals`
- `capability_discovery_is_performable`
- `durable_identity_survives_reconnect`

**Proven by expectation mutation (shape).** The check's own expectation is
inverted and the conforming server must then fail it. If it still passes, the
check is not reading what it claims to read.

- `catalogue_prefix_and_strict_schemas`
- `catalogue_rejects_caller_supplied_principal`
- `catalogue_uses_objects_not_json_envelopes`
- `strict_inputs_reject_encoded_objects`
- `schema_rejection_precedes_dispatch`
- `adapter_error_contract`

Mutation is the weaker of the two. It shows a check discriminates; it does not
show that a realistically non-conforming server is caught. Behavioural
requirements — replay, conflict, cancellation, reconnect — are not
mutation-testable in any meaningful way and are controlled by stubs.

Both claims are derived from what exists rather than maintained by hand: the
stub list is asserted against the stubs actually shipped, and the mutation list
against the mutations actually exercised. A reader can lean on a stub-controlled
PASS more heavily than a mutation-controlled one.

## Verifying a server

```sh
cd tests/conformance/mcp
pnpm install --frozen-lockfile --ignore-scripts
node conformance.mjs --stdio '{"command":"...","args":["..."],"cwd":"..."}'
node conformance.mjs --http https://host/mcp --token "$TOKEN"
```

Exit `0` only when every check passed. `UNDETERMINED` is **not** conformance: it
means the runner could not obtain the evidence, and it exits non-zero.
