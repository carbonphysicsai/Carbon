# OWNER-LAUNCHPAD-E2E-SUITE-01

## 1. Authority and scope

Ryan supplied the answers in section 3 directly on 2026-10-15, then instructed
Platform2: "Not moving the answers. Act on them like they’re in section 3 or put
them there for me now." Platform2 records them here and applies them immediately.
No further owner confirmation is required for these decisions.

This record directs the Launchpad acceptance suite, evidence, release sequencing
and owner execution blocks. It does not establish that an unrun cell passed,
that a release was cut, or that a reserved security acceptance occurred. Root
retains host, test-dispatch, spend and merge actuation under the current owner
amendment. The first owner block is T-07 only.

## 2. Application

The answers below control prospectively over conflicting older suite preparation.
Historical observations retain their original revision, date, result and scope.
The existing acceptance plan and cell schema remain the evidence basis:
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`, section 2.

Platform2 owns reconciliation and evidence backfill; Test Lead coordinates the
bounded implementation work and actual owner-block execution. Deferred level
coverage and LA-F17 do not block the base T-07 path. Required implementation
defects are findings with an owner and ticket, not renewed questions to Ryan.

## 3. Owner answers, 2026-10-15

**D1 — LA-F17 (bootstrap signs for the subnet publisher): OWN TICKET, NOT A LAUNCH BLOCKER.**
Carbon Validator reviews, owner accepts per AGENTS.md §13. Until accepted, the release check labels that path "untested" and the cell stays BLOCKED with this reason. Nothing else waits on it.

**D2 — Release cut for LA-F10: YES, THIS WEEK.**
One worker-image release after the commit op. It unblocks practice on released images (F08), the `--update` cell (F02), and lets Graphite practise on what miners practise on — OWNER-LAUNCHPAD-PROD-02 #10's rule.

**D3 — Owner hands: TWO 90-MINUTE BLOCKS A WEEK, STARTING THIS WEEK.**
On `carbon-fresh`. The Launchpad lane writes the agenda the day before: which cells, which keys, which machines, in order. Cells are written *during* the block, not after. First block is T-07 end to end: tunnel → review → launch → practice → freeze → commit (TTY) → submit → verdict. If that first block produces F05–F12 as cells, the matrix goes from 0 to 8 recorded flows in ninety minutes. *Beyond the handoff:* if a block can't produce cells because something is broken, the block is spent writing findings, not retrying — the finding is the output.

**D4 — "Untested" by default: CONFIRMED.**
Anything without a PASS cell at this revision (or an earlier revision the cell names) is hidden or labelled "untested" on both doors, as a closed field the MCP door returns. Starts from everything. A BLOCKED or FAIL cell never shows as tested. This is the 2026-10-07 rule; T-06 makes it code.

**D5 — VALIDATOR-25 dev-ladder: AFTER THE FIRST REAL VERDICT, NOT BEFORE.**
Levels are not in the base acceptance. The Carbon Validator's `served_contracts` + `battery-dev-ladder` on valV2 is scheduled the week after T-07 lands F12. Until then every level cell is BLOCKED with that reason on both doors — which is the truthful label and what the release check will show.

**D6 — Multi-intake in the base configuration: YES.**
Add F15: two real receiver-paired targets, one admits, one refuses, both journals present, no averaging of verdicts. It is the mainnet shape, and testing the single-intake path only would be testing a configuration miners won't run.

---

**Three riders for the record:**

**R1 — The first owner block is T-07, nothing else.** Not compute cells, not inference checks, not snippets. One real submit → verdict through the Launchpad is the single cell that proves the path exists; everything after is coverage.

**R2 — Backfill is mandatory before new runs.** F01 (run 1 FAIL, run 2 PASS at `f1dd652debdf`), F03 PASS, and the 2026-10-08 Graphite smoke as F07 get written as cells first, truthfully, with their findings linked. The scoreboard starts from what already happened.

**R3 — The two "confirm" items are week-1 deliverables, not questions.** Whether the service journey and `browser_smoke.py` run in CI, and whether practice/freeze/submit have durable idempotency keys. Each is either confirmed with a pointer to the lane or test, or it becomes T-01 / a correctness ticket. No third state.

## 4. Immediate recorded dispositions

These are source-inspection dispositions, not new execution results. Inspected
source: `27f74451eacc346e323f1ff2d5f86a8b12407187`; final release adoption must be
checked against the actual selected release.

- **R3, durable keys: CONFIRMED.**
  `scripts/dev/miner_launchpad/operations.py` accepts keyed practice,
  freeze_candidate and submit under the replay gate.
  `scripts/dev/miner_launchpad/runner.py` persists
  `launchpad_operation_keys` in SQLite, keyed by principal and request key,
  checks the request digest, and replays accepted work without redispatch.
  `tests/cpu/test_miner_operation_idempotency.py` covers changed-request
  conflicts, controller restart and concurrent submit. This does not promise
  idempotent retries when the caller omits or changes the key.
- **R3, normal CI execution: T-01 finding.**
  `pyproject.toml` collects `tests/cpu` by default;
  `scripts/dev/ci.sh` does not include
  `tests/service/test_launchpad_production_journey.py` in its explicit service
  lane. The same script runs
  `scripts/dev/miner_launchpad/browser_smoke.py` only when
  `CARBON_LAUNCHPAD_SMOKE=1` on shard 4, and otherwise reports NOT RUN; the
  normal CI workflow does not set that flag. Missing-browser execution can
  also skip. The deliverable is a bounded T-01 CI repair with actual execution
  evidence, not treating the presence of either test as coverage.
- **R2, historical evidence preservation.** F01's original run-1 failure and
  run-2 success are recorded in
  `docs/development/evidence/fresh-miner-2026-10-07/README.md`, with LA-F1/LA-F2
  in `docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`.
  Backfill must preserve the failed attempt and original revision; no new
  installed acceptance is inferred from it.
- **D5/R1, execution order.** Earlier combined-contract stand-in proposals are
  deferred beyond the first real T-07 verdict. A source default that prevents
  the base path is an implementation finding to repair, not a reason to run
  the dev-ladder first. Level cells remain blocked with D5's explicit reason.
- **D1, scope.** LA-F17 remains a separate security-sensitive ticket and
  blocked/untested cell until Carbon Validator review and owner acceptance.
  Its acceptance is not inferred from this record.

Recording this decision does not schedule calendar times or create a recurring
automation. The lane prepares the day-before agenda for the actual selected
owner block and records cells or findings during that block.
