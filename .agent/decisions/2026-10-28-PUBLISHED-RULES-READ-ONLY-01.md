# Published scoring rules remain readable while execution is reserved

Working contract for the owner's bounded launch regression repair. Base:
`77f17e58f6f6600ace8508af0f06e477e0b78cbc` (tree
`5ecdfc33f1c007e0358fe2d01ca63d06ae7d33c1`). Classification:
`IMPLEMENTATION_LAG`.

`docs/MINING.md` under **How you're tested** promises that
`carbon_challenges_v1__scoring_rules` returns the existing published formula,
legs, gates and minimums, and refuses versions without published rules. The
tool's original owner instruction, recorded in `test_scoring_rules_tool.py`,
also requires agents to be able to read and hypothesize from these rules.
Execution readiness is a separate contract: RESERVED versions must still be
refused by `describe`, `resolve` and admission. Publication does not register
missing constants, qualify an exam or admit a workload.

The actual failure is that the read-only tool calls the execution-gated full
description before applying its existing closed publication projection. The
exact-77 canonical full-suite evidence reported by Codex-INT includes five
published RESERVED rows failing there: Cooling 1.5/1.6, F02 2.5 and F08 1.6/1.7.
Weakening their success assertions would contradict the published contract.
The earlier `codex/public-contract-fixtures` scoring-test change is superseded
and is not an input to this fix.

KEEP the publication table, `scoring_rules_view` allow-list, public schema,
published values and execution gates. REPAIR the lookup with a small public
metadata helper that shares the registry's existing identity/development-only
validation and unsupported-version errors, requires an exact registered
version, and returns only its identity and existing published block. It does
not inspect host capabilities, invoke a Challenge description or select a
profile. The MCP tool applies the unchanged closed view. Unknown identities,
unknown versions and missing publications remain typed refusals. Existing
execution refusal order and behavior stay unchanged.

The independent early-stop lifecycle regression also has a stale synthetic
Docker protocol: the maintained controller calls
`run(["logs", "--tail", "200", name])`, while `ScriptedDocker` lacks that case.
Carry only its bounded synthetic stdout/stderr response and assertions from
the superseded branch. Preserve WorkerFailure classification and cleanup;
make no controller change or test exclusion.

Regression scope includes every existing published-block MCP success and
disclosure projection, explicit read-only access to all five RESERVED rows
while `describe`/`resolve` still refuse them, implemented rows, unknown and
missing-publication refusal, and the early-stop diagnostic/cleanup path.
Remote-only validation targets `test_scoring_rules_tool.py`,
`test_challenge_registry.py`, `test_mcp_challenges_compact.py`,
`test_published_exam.py`, `test_published_exam_pool.py`,
`test_development_variant_refusals.py`, `test_no_leakage.py` and
`test_local_controller_lifecycle.py`, plus changed-path canonical quality and
applicable producer/invariant checks. No local Python, tests or formatters.
Source/wheel/worker identities change prospectively; no old image receipt is
relabelled. Producer identity checks remain part of remote validation.

Hub primary `map_ref`: `SYSTEM/AGENT-EXECUTION`. Its existing public discovery,
execution and authority boundaries remain accurate: this restores an already
promised metadata view and adds no tool, profile, capability or maturity claim.
The current handoff keeps the historical Hub frozen; record this bounded
implementation finding in the existing handoff logs, without regenerating or
changing historical Hub status.

Conditional completion requires canonical checks on the final exact source,
independent non-author source review, and the owner's reserved integration
receipt. This branch earns implementation evidence only until those checks;
it grants no science, security, network, economic, launch or deployment
acceptance. Real GPU replay remains the higher-priority task.
