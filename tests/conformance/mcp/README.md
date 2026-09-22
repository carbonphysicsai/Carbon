# Carbon MCP conformance suite

An independent runner that points an official MCP client at a Carbon research
endpoint and reports, check by check, whether it honours the published contract.

It is a **consumer**. It imports no Carbon source, and it does not assume it
built the server it is testing.

Protocol conformance only. **A conforming server is not a qualified one**: this
establishes no security qualification, no scientific qualification, and no claim
about a real agent campaign.

The contract it checks is written up in
[`docs/development/CARBON_MCP_CONFORMANCE_REFERENCE.md`](../../../docs/development/CARBON_MCP_CONFORMANCE_REFERENCE.md).

## Running it

```sh
pnpm install --frozen-lockfile --ignore-scripts
node conformance.mjs --stdio '{"command":"python","args":["server.py"],"cwd":"/srv"}'
node conformance.mjs --http https://host/mcp --token "$TOKEN"
```

Exit `0` only when every check passes. A machine-readable report goes to stdout;
a per-check summary goes to stderr.

Each check reports one of three statuses. `UNDETERMINED` is **not** conformance:
it means the runner could not obtain the evidence, and it exits non-zero. A
caller who could not gather the evidence has not learned that the server
conforms, and silently treating that as a pass is the failure this suite exists
to prevent.

## Why the stubs are part of the artifact

A conformance suite that passes against a non-conforming server is worse than no
suite, because it manufactures confidence. So the suite ships with servers built
to be rejected, and a test that each one *is* rejected **by the check for the
requirement it violates** — not merely rejected for some reason.

| Stub | Violation | Check it must fail |
|---|---|---|
| `duplicate_dispatch` | dispatches again for a repeated identity | `operation_identity_replay_does_not_redispatch` |
| `changed_input_accepted` | accepts changed input under an existing identity | `operation_identity_conflict_is_refused` |
| `cancel_claims_release` | reports cancellation as resources released | `cancellation_is_a_request_not_a_release` |
| `error_leaks_internals` | leaks a path and a credential in an error | `errors_do_not_leak_internals` |
| `advertises_unperformable` | advertises a resource it cannot read | `capability_discovery_is_performable` |
| `loses_task_identity` | loses operation identity across reconnect | `durable_identity_survives_reconnect` |

Shape checks are controlled differently and more cheaply: the check's own
expectation is inverted and the real server must then fail it. Asserting the
prefix is `xyzzy_`, or that results *must* be `*_json` envelopes, must break the
check — otherwise it is not reading what it claims to read. That is precisely
how the leak check was vacuous, and inverting it would have shown that.

Every check carries a `control` field of `stub`, `mutation` or `none`, and both
lists are asserted against what actually exists rather than hand-maintained.

The positive control is the **real Carbon stdio server**, which must be judged
conformant. There is deliberately no "conforming stub": the stubs exist only to
be rejected, and a mock Carbon would be a second server to maintain and a second
thing to be wrong.

Both controls run in `test_mcp_conformance.py`. Set
`CARBON_REQUIRE_MCP_CONFORMANCE=1` to turn the environment skip into a failure.

Two defects in this suite were found by the stubs rather than by review: the leak
check originally probed only malformed input, which the schema layer refuses
before the adapter is reached, so an adapter-level leak went undetected; and the
stub scaffolding failed the conflict check by omission, so no stub was evidence
about conflict. Both are fixed. That is the point of the negative controls.

## Ownership

This suite is the consumer side. The server contract lives in
`carbon/miner_mcp/` and belongs to the Launchpad workstream. If conformance work
exposes a genuine server defect, the finding goes to them as a failing fixture
and the exact required interface — it is not fixed here.
