# C-MLP-01: DEVELOPMENT miner launchpad foundation

Status: in progress; local controller implementation and native diagnostics complete.
Canonical acceptance, Hub reconciliation and normal merge remain outstanding.

Primary Hub map: `SYSTEM/AGENT-EXECUTION`; `HUB_UPDATE_REQUIRED` for the
isolated controller, its boundaries, ticket and successor links. The scientific
WAVE selector remains owned by the research workstream.

## Acceptance repair plan (2026-09-17)

KEEP the closed rehearsal profile, SQLite lifecycle and existing UI. REPAIR
connection-state truth, reload-safe unconfirmed launch retries, storage-error
regressions, bounded HTTP admission and host-portable ownership locking. Reuse
the Hub's existing Chromium/CDP test utility for real browser/server testing.
Native Windows diagnostics are not canonical acceptance. Current main and this
branch use OWNER-DX-03 delivery; older mandatory human/GPT receipts are superseded.
Run focused regressions during repair, reconcile Hub sources, then use the
unchanged path classifier and pinned CI acceptance with the required Merge gate.
No provider, scientific runtime, CI exemption or deployment change is included.

## Owner request and scope

On 2026-09-17 the owner requested: "I want to build this now. So we can test,
optimize, and expand before launching Carbon."

This selects an isolated engineering branch for the miner launchpad. It does not
replace the active scientific ticket or consume another campaign's resource grant.
Read the current main and active work before integration. Do not overwrite
concurrent research, website, Workbench, scoring or historical evidence changes.

The first slice implements a private, local controller rehearsal. It owns run
control only, not scientific submission, evaluation, ranking or settlement.
Rehearsal completion is not successful research. The distinct schema and closed
profile make that boundary explicit. No Carbon scientific modules are called.

## Implemented in this draft

- SQLite-persisted runs and event history, with request-key replay protection.
- Launch, pause, resume, stop and fixed lifetime limits; four active runs maximum.
- Restart recovery requires explicit resume. It preserves steps and deadlines.
- Loopback-only HTTP, generated local session token, Host/Origin checks, bounded
  closed requests, static assets, no credentials in browser persistence.
- Responsive Carbon interface, run selection and provenance-labelled JSON export.
- Explicit unavailable capabilities for real research, Hermes, personal agents,
  Mira, Chutes, Lium, Engy and wallet registration. No silent fixture fallback.

Runtime: `scripts/dev/miner_launchpad/`.
Tests: `tests/cpu/test_miner_launchpad.py`.
Operator instructions and successor scope:
`docs/development/MINER_LAUNCHPAD_HANDOFF.md`.

## Acceptance still required

1. Run current canonical Python 3.11 formatting, quality, invariants, package,
   relevant regression and applicable CI. Do not broaden a CI exemption.
2. Test the browser against the actual HTTP server in the Carbon environment:
   authentication, launch, replay, pause, resume, stop, export and reconnect.
3. Test restart, expired runs, storage errors and ownership-lock conflicts.
4. Reconcile the relevant Hub sources using its maintenance contract and the
   existing DEVELOPMENT/tooling map. Do not invent qualification or mark the
   scientific wave complete. Keep non-launchpad active work intact.
5. Inspect the code, repair defects, mark the PR ready, require the existing
   Merge gate, and merge with its expected-head guard under DELIVERY_PROTOCOL.

## Evidence and limits

Native Python 3.13.5 diagnostics: 56 pytest cases passed. JavaScript syntax check
passed. Offline Chromium layout checks passed at 1440px and 390px with no
horizontal overflow. Chromium refused localhost navigation under this execution
environment's administrator policy; browser-to-server E2E is NOT VERIFIED. No
policy was changed. These checks are not the repository's canonical acceptance.

Continuation diagnostics: 63 Python 3.12 Windows tests passed, including
transaction rollback on event-storage failure, fixed HTTP infrastructure errors,
request admission limits and cross-process lock release after termination.
Actual Chromium/server smoke passed launch, lost-response/reload retry,
pause/resume/stop, fresh export, storage failure, controller/server recovery,
expiry and 1440/390px layouts. The previous browser blocker is resolved for this
environment. Docker daemon/WSL unavailability leaves pinned CI acceptance pending.

No real provider calls, training, GPU rental, wallet connection, chain transaction,
protected evaluation, payment, production deployment or miner earnings occurred.
The local HTTP server is not a hardened public multi-tenant service.

## Successor

C-MLP-02: real public/synthetic DEVELOPMENT research bridge. Use the existing
Carbon research/reconstruction/reporting implementation. Do not build a second
scientific evaluator or another research-reporting dashboard. See the handoff.
