# Fixed practice failure diagnostics

Status: working engineering contract; Root assignment 2026-10-15.
Base: `514788a4f7a5a4aeda04ae47aacfdffa6870328a`.
Primary map: `SYSTEM/AGENT-EXECUTION`; Hub retired by OWNER-WORKFLOW-SPEED-01.

The actual c41 JAX public practice task ended FAILED_INFRA. Its owned intent
retained the expected image/device binding, but no stdout, export or snapshot
survived. DockerCLI deletes a failed stream destination, so absence cannot
locate the error before program execution. No underlying CUDA cause is proven.

KEEP fixed programs, image/device checks, launch identities, stream deletion,
public generic failures, exact container cleanup, reservation and reconciliation.
REPAIR only private observability for BATTERY_PUBLIC_PRACTICE after durable intent.
Write an owner-only, bounded closed record per failed stage, containing schema,
stage, closed exception category, validated WorkerCode and closed diagnostic
markers. Never retain exception text, traceback, arbitrary class names, paths,
inputs, seeds, environment, tokens or raw diagnostics. Markers are diagnostic
hints, not independently established causes. Existing records remain immutable.

The diagnostic write is best effort and must not replace the original exception
or change cleanup/accounting/retry behavior. A cleanup error may have its own
record; original error propagation remains as before. No new public field or
automatic replay. Miner-authored and validator paths gain no diagnostic record.

Owned manifest: this ticket; its new decision; research_carrier.py; new
tests/cpu/test_fixed_practice_failure_diagnostics.py. Open PR overlap check was
disjoint (1396, 1395, 1385, 1255, 1246, 1222). One writer and one PR.

Plan: contract/decision; bounded stage recorder and focused injected failures;
author static formatting/AST; Root canonical focused tests plus automated CI;
Root targeted public GPU diagnosis and continued JAX/PyTorch fit/predict trials.
Root alone executes tests, host/model/provider work and merges. Baseline tests
requested from Root; no author execution is implied by this contract.

DoD: create/start/control/program/cleanup failures retain only closed metadata;
same exception escapes; failed writes do not mask it; exact cleanup, no retry,
reservation and normal reconciliation remain intact; arbitrary secret-bearing
messages/classes never appear in records or public results. Existing GPU route
and worker/research secrecy regressions pass. Static checks are not runtime proof.

Maturity ceiling: implemented/tested engineering observability only. No scientific,
security, production, LIVE or GPU acceptance claim follows from this repair.
Ticket closes after Root confirms tested normal merge. The user's separate GPU
objective remains open until actual CUDA fit/predict results exist for both.
