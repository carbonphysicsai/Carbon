# BATTERY-TESTNET-M3 — Battery validator daemon

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** OWNER-BATTERY-TESTNET-01 (OD-2, OD-4a/b, OD-5, OD-6, OD-7),
OWNER-BATTERY-TESTNET-03 and OWNER-DX-03. Working decisions: M3-D1 to D16 in
`.agent/DECISIONS.md`.
**Depends on:** BATTERY-TESTNET-M2 (exam, seeds, truth service) and
BATTERY-TESTNET-M5A (Challenge registry and shared MCP workflow).

## Outcome

One battery validator daemon admits, screens and compares submissions under
the approved exam (OD-2), exactly as the rule is written. Every battery
submitter reaches it by the same path: a miner, the Launchpad or Carbon's
autonomous agent.

## Scope

- `carbon/battery/pool_store.py`: durable, owner-only validator state. It
  holds:
  - batches, references, pool version and admitted count;
  - admissions and retained model states;
  - predictions and scores;
  - the incumbent and finals;
  - operations and events.
- `carbon/battery/daemon.py` (`BatteryValidator`):
  - **admission:** signed transport, commitment, Challenge and version,
    contract digest, compile, identity binding;
  - **screening:** one isolated rebuild and inference over the whole active
    300-case pool, all gates across it; the incumbent brought onto the pool by
    inference; `exam.nominate`; rotation committed with the score;
  - **finalist comparison:** frozen rule and identities, one claimed fresh
    set, fresh matched-seed rebuilds, `exam.final_compare`; only IMPROVEMENT
    promotes;
  - **distinct outcomes:** invalid construction, reconstruction failure, gate
    failure, reference failure, infrastructure failure and insufficient
    evidence;
  - an allow-listed miner outcome and service-key signatures.
- `carbon/battery/worker.py`:
  - the fixed reconstruct and infer programs;
  - `CarrierBackend` (the isolated carrier) and `DirectBackend` (trusted,
    reported as such);
  - `WorkLedger`, the carrier's operation ledger, kept in the validator state.
- `carbon/battery/recipes.py`: trained-state export and import. A retained
  model is inferred on later pools without retraining.
- `carbon/battery/signing.py`: OD-6 service keys, and the Phase A all-burn
  intent only.
- `carbon/battery/deployment.py`, `operate.py`: the operator's deployment
  configuration and commands.
- The Launchpad, miner and agent submit path goes through the daemon. M2's
  in-process evaluation is removed.
- Carbon's autonomous agent on battery:
  - a Challenge-neutral prompt;
  - battery's own discovery document as its observation;
  - a finite recorded plan and budget;
  - the miner's capabilities only.

## Definition of Done

- [x] Screening binds the pool version, rule, recipe, reconstruction,
      references and data identities, and covers the whole active pool.
- [x] Duplicate admission and replay count once. A conflicting replay is
      refused.
- [x] Restart is safe at each stage:
  - after admission;
  - between reconstruction and score;
  - between rotation and journal retirement;
  - after a final's infrastructure failure.
  Nothing is double-counted, double-rotated or dispatched twice.
- [x] Rotation is durable. Retained models are inferred, not retrained. An
      exhausted or incomplete pool waits.
- [x] A reference failure is withdrawn consistently for every model, and the
      original identities are kept.
- [x] Infrastructure failure (worker host unavailable, killed at its bound,
      partial output) is retried under a new attempt and is never scored.
- [x] Contract, artifact and cross-challenge mismatches are refused by name.
- [x] Outcomes disclose no private case, input, label or seed. Published
      campaign cases are refused as hidden cases.
- [x] The finalist comparison is frozen before evaluation, runs on fresh cases
      and records its actual outcome.
- [x] In real containers, created with the carrier's isolation arguments:
  - rebuild and inference match the in-process backend;
  - screening matches;
  - no container remains;
  - no network;
  - a crashed run is reconciled onto a new attempt.
- [x] Complete-diff review findings closed, each with a test:
  - a pending rotation resumes when a batch completes;
  - a nomination commits with its score, and a promotion with its decision;
  - a stale final is withdrawn and its challenger re-nominated;
  - the incumbent's inference retries under a new identity;
  - infrastructure retries are capped;
  - references for other inputs are refused;
  - there is one writer per deployment, and status is read-only;
  - an owner-only work directory is required;
  - the service key signs only the all-burn intent.
- [x] Launchpad and miner submit through the daemon (end-to-end MCP test).
- [x] Carbon's agent on battery, scripted provider: discovery, check_design,
      capability request, practice, select, daemon score and a self-reported
      stop are recorded. A disclosure scan covers every campaign file.
- [x] An external `mcp` stdio client discovers, compiles, checks and practises
      battery.

## Evidence classes (kept separate)

| Class | This ticket |
|---|---|
| Implemented | Everything in Scope |
| Tested locally (in-process) | `tests/cpu/test_battery_validator_daemon.py`, `test_battery_validator_deployment.py`, `tests/service/test_battery_mcp_research.py`, `test_battery_mcp_stdio.py` |
| Tested in isolated containers | `tests/service/test_battery_validator_containers.py`, with a local test image built from the locked wheels, on a cgroup-v1 host. The host doctor is not consulted, and this is not the accepted digest-pinned image. It skips without `CARBON_BATTERY_TEST_IMAGE`. |
| Tested on GPU | No (M4) |
| Real autonomous agent | No: a scripted provider, i.e. deterministic client acceptance |
| Observed on testnet | No (M7) |

## Known limits

- The two-instance commit-reveal cross-check is not implemented.
- There is no chain `CommitmentReader`. A deployment requiring commitments
  refuses every submission until one exists.
- Retired-case release is listed (`releasable`), never performed. Release
  policy details remain open.
- Truth solves run in the pinned truth image on a host. Tests use the
  exam-design campaign's retained references.
- The executable host handoff is `docs/development/BATTERY_TESTNET_HOST_HANDOFF.md`.
