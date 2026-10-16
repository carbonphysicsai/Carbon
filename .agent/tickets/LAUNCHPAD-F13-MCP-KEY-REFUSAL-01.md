# LAUNCHPAD-F13-MCP-KEY-REFUSAL-01 — typed public MCP key refusal

Status: bounded implementation prepared for Root review. Starting base:
`97106c1b36a19f7750f8e7ac344c4d6536d4b767`. Primary hub `map_ref`:
`SYSTEM/AGENT-EXECUTION`; OWNER-DX-03 has retired routine Hub
maintenance, so no Hub source or generated output changes are needed.

Authority: OWNER-MINER-SETUP-AGENT-FIRST-01, the existing Launchpad setup
operations table, `LAUNCHPAD-T02-DOOR-PARITY-01`, the F13 public refusal
checkpoint, repository constitution and invariants. Root owns runtime/host
dispatch, review routing, push and merge. This ticket changes no real key,
provider, signer, chain, deployment or security-acceptance behavior.

## Working contract and decision

`carbon_setup_inference` advertises `model_key_file`, never `key`. A client that
nevertheless sends a `key` member must receive the existing closed
`key_must_be_a_file_on_this_door` refusal with `field=key` and the existing
`next_step`, regardless of the supplied value, before argument validation or
the setup callback. The value must not be inspected, echoed or persisted.
All other unknown fields and all other setup tools keep strict SDK validation.
The browser continues to advertise its own paste-once `key` field and use the
shared setup operation; this ticket does not change browser behavior.

KEEP the setup table, `perform`, the strict arguments model, `ExactMetadata`,
tool registration and browser route. WRAP only the inference tool's `run`
prevalidation path. The pinned MCP SDK's metadata validation catches a
`ToolError` raised inside `pre_parse_json` as an unexpected failure, so that
hook cannot produce the closed refusal safely. The tool-level wrapper checks
member presence without reading its value, raises the existing `ToolError`
body, and delegates every other request to the unchanged `Tool.run`.

Owned paths: this ticket, `carbon/miner_mcp/mcp_setup.py`, and
`tests/cpu/test_miner_setup_agent_first.py`. Tests use a synthetic sentinel,
assert the exact public MCP code/field/next step, no value echo, no callback or
billing, unchanged strict unknown-field behavior, and the browser schema and
safe refusal comparison. No `app.js` or PR #1407 overlap.

## Validation and conditional handoff

Static AST/format and diff checks may run in this isolated worktree. Root
reserves canonical application tests and exact-head CI. Focused command:
`./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_miner_setup_agent_first.py`.
Implementation remains reviewable source and test evidence until that command,
applicable CI, and fresh complete-diff review pass. No F13 live refusal cell,
installed-source claim, spend, scientific or security qualification follows.
