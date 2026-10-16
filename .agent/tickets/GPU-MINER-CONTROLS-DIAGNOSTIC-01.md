# GPU miner effective-controls refusal diagnostic

Status: working contract; Root-assigned bounded source repair 2026-10-16.
Base: `4124b0080c7e6d30571a75a7307f7f3849f23405` (current merged main at start).
Primary map: `SYSTEM/AGENT-EXECUTION`; the Hub is retired by owner direction,
and this task does not change its purpose, placement, status, dependencies,
boundaries, maturity, or links.

The ordinary accepted-971 JAX practice task `rtsk_6812c329624ccd150e12b41c0369e3ae60e7b37d69c402692f52f563fd86bff1`
reached fixed `BATTERY_PUBLIC_PRACTICE` carrier `CONTROLS` and failed with
`reconstruction.worker.policy.mismatch`. Its task-owned failure record has no
failing predicate. The carrier created and started its GPU practice container,
then refused before fit/predict; cleanup was independently reconciled. No CUDA
success, scientific failure, or qualification follows. Preserve that evidence.

Decision `GPU-MINER-CONTROLS-DIAGNOSTIC-01`: preserve every current control
comparison, policy refusal, and cleanup path. At a failed effective-controls
check, derive the first failing predicate from a closed source-defined enum and
put only that enum in `WorkerFailure.private_diagnostic` when the caller
explicitly selects the fixed battery-practice diagnostic. Other inspector
callers keep an empty policy diagnostic, including Graphite, whose carrier
may write private diagnostics to a program log. The fixed-practice
carrier may copy it into its owner-only `failure-CONTROLS.json` only for exact
`BATTERY_PUBLIC_PRACTICE`, stage `CONTROLS`, and `WorkerCode.POLICY`. Unknown
diagnostics, other stages, and other provenances disclose nothing new. Never
retain observed values, raw Docker output, environment, paths, labels, tokens,
keys, or truth payload. Diagnostic computation must not replace the original
failure if it itself fails.

Owned paths: this ticket, `.agent/decisions/2026-10-16-GPU-MINER-CONTROLS-DIAGNOSTIC-01.md`,
`carbon/reconstruction/worker/docker_runtime.py`,
`carbon/development_session/research_carrier.py`, and focused CPU tests.
No public API/schema change beyond an optional private task-owned failure field;
success and public result contracts remain unchanged. No official execution,
strict/local grant, science, hardware acceptance, or production security change.

KEEP the existing inspector and carrier. WRAP only failure diagnosis. Earlier
alternatives rejected: blind retry cannot distinguish predicates; a Docker event
poll can race immediate cleanup; relaxing a control would invent security
acceptance. This is reversible by removing the private enum field and helper.
Affected owner: runtime/security engineering; no human-reserved value selected.

Plan: source diagnosis; closed enum instrumentation; focused exact-refusal and
no-leak tests; independent complete-diff review; Root canonical checks, normal
one-PR delivery and one fresh task-owned diagnostic under its TEST lease. Root
alone owns Docker/host/test/provider/model actuation and result reconciliation.
Required canonical validation includes
`./scripts/dev/canonical.sh pytest tests/cpu/test_fixed_practice_failure_diagnostics.py tests/cpu/test_gpu_self_service_controls.py tests/cpu/test_c03_worker_contract.py`,
the changed-path CI classifier scope, Ruff and exact-head Merge gate. A pass on
the final tree is required; source review alone cannot close the ticket.
Completion follows current `OWNER-DX-03` delivery: fix concrete review findings,
pass required automated acceptance on the unchanged candidate, normally merge
with an expected-head guard, confirm GitHub's merge, and post one bounded
completion comment. The independent source review is useful engineering evidence,
not a new mandatory receipt or human-approval gate.
Final maturity ceiling: bounded implemented/tested diagnostics only; actual
JAX and PyTorch CUDA fit/predict remain separate required evidence.
