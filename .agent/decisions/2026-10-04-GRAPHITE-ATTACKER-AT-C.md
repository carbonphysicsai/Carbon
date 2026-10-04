## 2026-10-04 — GRAPHITE-ATTACKER-AT-C: attack analysis, verification, reports and benchmark B2

**Authority:** OWNER-GRAPHITE-ATTACKER-01 (2026-10-04), which approves a
challenge-neutral attack engine with one adapter per Challenge and
construction level, its evidence rules (§3) and benchmark B2 (§4). This slice
records engineering working decisions inside that authority. It decides no
scientific value, threshold, gate, security acceptance or spend, and runs no
live session: everything is exercised with synthetic journals, a stub
adapter, the scripted phase-3 harness and battery's real in-process gate.

**Slice.** `carbon/agent_campaign/attack/{analysis,verify,report,benchmark}.py`
and their tests. It repairs `carbon/agent_campaign/graphite/attack.py` from the
unmerged `origin/agent/challenge-protocol-04b` (be61e7435): only the reading of
attempts and the acceptance parsing are kept; the vectors, brief and suite
coverage are not carried (the brief is phase 4's, the suite is AT-A's).

### Decisions

1. **Journal identities read one way.** `analysis.attempts` reads every
   `*-intent.json` under `ledger/epoch-N[/<stage>]/` and accepts it only when
   `research_loop.tool_identity(epoch, turn, position, stage)` rebuilds the
   identity exactly and the file sits in its own session's folder. A
   non-canonical or misfiled identity raises; it is never guessed. Attempts are
   ordered by epoch, the unstaged session before staged ones, then turn and
   position, so v2 turns with several calls (`-KK`) read in run order.
2. **Protected material on every read and write.** An attempt whose request
   names protected material (`graphite.tools.protected`) carries no arguments;
   one whose result was withheld by Graphite (`protected_material_in_result`)
   or whose journalled result names protected material carries no result. The
   attempt keeps its identity and digests. A specimen whose construction
   names protected material is not written, and finding evidence that would
   name it is recorded redacted (verdict digest only) — redacted, never
   suppressed.
3. **An exposure is `OTHER_SIGNAL`.** A result Graphite withheld for naming
   protected material is recorded as an `OTHER_SIGNAL` finding (the design's
   "exposure = OTHER_SIGNAL"). This supersedes be61e7435, which reported it
   `UNDETERMINED`: Carbon cannot tell an over-refusal from an exposure without
   reading the material, and it never reads it, so the fail-closed direction
   is to emit the finding and let the technical owner grade it.
4. **Graphite's own refusal is never the path's defense.** A call Graphite
   refused before dispatch (`dispatched: false`, or a protected request) is
   `HELD` with `refused_by: graphite`; the oracle is not consulted.
5. **Infrastructure is never a pass.** A result in `FAILED_INFRA`,
   `TIMED_OUT`, `TIMEOUT` or `CRASHED` (in the result, its reply, its reply's
   result or its terminal task), a missing result, an unresolved dispatch, or a
   crash in Carbon's own rebuild, oracle or specimen check is `INFRA`: never
   scored, never `HELD`, never a finding (invariant 7).
6. **Rebuild or refuse, typed; the unrebuildable is never scored.** Every
   construction an attempt carries (`strategy_json`, or the adapter's own
   `construction(attempt)`) goes through `adapter.rebuild`. A typed refusal —
   any object or exception whose class name contains `Unrebuildable` — is
   recorded with its code and the oracle is not consulted. The path accepting
   it is a reproduced fail-open, `FAILING_TRIGGER`; the code
   `construction_contract_unrecorded` means Carbon can check nothing and is
   `UNDETERMINED`. A `Verdict` cannot be constructed `scored` and
   `UNREBUILDABLE`.
7. **Pod rebuild.** When a pod build record is supplied for an attempt
   (`pods=`, a mapping by attempt identity or a callable), or the result says a
   pod scored it (`status: SCORED`), Carbon's rebuilt record is compared with
   it by the adapter's `rebuild_differences` or, by default,
   `experiment.rebuild_differences`. A difference (including a missing record)
   is `FAILING_TRIGGER` and the attempt is not scored.
8. **Specimens.** A breached attempt with a rebuilt construction is bundled
   when `specimen_dir` is given — by the adapter's `bundle_specimen`, or in the
   Graphite phase-3 bundle format (`delivery.BUNDLE_SCHEMA`) — and re-checked
   from the bundle alone by the adapter's `clean_rebuild` or
   `delivery.clean_rebuild`. `REBUILD_MISMATCH` adds `FAILING_TRIGGER`; a
   bundle Carbon could not write or check is reported, adds nothing and is
   never a pass.
9. **Only `CONDITIONS`.** Every finding condition is checked against
   `challenge_readiness.admission.CONDITIONS` when a verdict is built, when a
   report is built and when it is recorded; any other condition raises. An
   oracle breach without a condition is `FAILING_TRIGGER`.
10. **Recording stops expansion.** `verify.record` records each condition with
    `CampaignController.record_finding` under an id derived from its evidence
    digest (idempotent). The controller then refuses every expansion
    (`admission_expansion_after_finding`); the tests drive the real controller.
11. **The oracle is called with the family's name.** `adapter.oracle(family,
    attempt)` receives the family name string, the same key
    `map_to_families` returns. Family names are read from `name`, `family_id`
    or a mapping, so the engine's `FamilyDef` and battery's track_a `Family`
    both work. Attempts map through the adapter's `family_of`, then a family's
    `matches`, then a neutral default from miner-SDK operation to one of the
    eight shared checks (first family with that check); the rest is
    `UNASSIGNED`, reported.
12. **Reports.** Per family: attempts, budget used, completed, held,
    verified, findings, near misses, timeouts and crashes, NOT_RUN, and
    wrongful rejection on trained and held-out controls. A family with no
    finding is `ATTEMPTED_COVERAGE` with `bound: null`; a declared seam, or a
    family with no attempt, is `NOT_RUN`. A breach and a wrongly refused
    control (trained or held-out) are `FAILING_TRIGGER`. Only the report reads
    held-out controls; verification never calls `adapter.controls`. The
    `controls_held_out` argument is required.
13. **B2.** Each family's sides are cut to their first `budget` attempts in
    run order (one integer, or a mapping that must cover every family), each
    summarized like the report, and the store snapshot digest the Attacker ran
    under is recorded (`sha256:` form or none). The comparison is descriptive,
    never a grade. `benchmark.track_a_baseline` reads battery's deterministic
    side from `track_a.run()` unchanged.

### Mutations covered

Each switched off by monkeypatch turns its guarding test red:
counting `FAILED_INFRA` as a pass (`analysis.INFRA_STATES`, and
`report.NOT_COMPLETED`); a finding outside `CONDITIONS`
(`verify.check_conditions`, in verify and report); expansion after a finding
(`CampaignController._expansion_blocked`); scoring an unrebuildable
construction (`verify.is_unrebuildable`); skipping the pod rebuild comparison
(`verify._differences`); comparing past the B2 budget (`benchmark._within`).

### Not decided here

Isolation for hostile code (reserved to the security owner), any numerical
reproduction tolerance (`HUMAN_INPUT`), any attack budget for an admission
run, and the grading of any finding (the technical owner's).
