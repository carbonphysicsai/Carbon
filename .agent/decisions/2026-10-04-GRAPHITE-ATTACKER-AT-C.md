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
   `HELD` with `refused_by: graphite`; the oracle is not consulted. The
   research loop's own refusals are Graphite's too: its `rejected_call`
   records (`REJECTED_BEFORE_DISPATCH` with a loop refusal `code` from
   `research_loop.REFUSAL_CODES` and a `fix`: malformed, truncated,
   selection, finish and compaction refusals) and its trial-ceiling
   `UNAVAILABLE` (no path `operation` envelope). The miner research tools'
   own contract refusal (`REJECTED_BEFORE_DISPATCH` without a loop code) stays
   the path's. Reports count Graphite's refusals apart
   (`refused_by_graphite`), never as completed or held.
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
   (`pods=`, a mapping by attempt identity or a callable), Carbon's rebuilt
   record is compared with it by the adapter's `rebuild_differences(rebuilt,
   built)` (handed exactly what the adapter's `rebuild` returned) or, by
   default, `experiment.rebuild_differences` on the extracted record. A
   difference is `FAILING_TRIGGER` and the attempt is not scored; a crash in
   the comparison is `INFRA` (`rebuild_compare_crashed`). A result saying a
   pod scored it (`status: SCORED`) with no build record supplied is
   `UNDETERMINED` (`pod_build_record_not_supplied`), not scored and not a
   finding: that is Carbon's own missing evidence (the experiment already
   compared `built.json` before scoring), and recording it would block every
   later expansion. (Revised after review; the first version made it a
   `FAILING_TRIGGER`.) A phase-3 feedback status `SCORED` or
   `CANDIDATE_FAILED` reads as the path having accepted the construction, so
   an unrebuildable construction a pod ran is the fail-open of decision 6.
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
    both work. Attempts map through the adapter's `family_of(attempt)` or
    `family_for(tool, arguments)` (battery's), then a family's `matches`, then
    a neutral default from miner-SDK operation to one of the eight shared
    checks (first family with that check); the rest is `UNASSIGNED`, reported.
12. **Reports.** Per family: attempts, budget used, completed, held,
    undetermined, refused by Graphite, verified, findings, near misses,
    timeouts and crashes, NOT_RUN, and wrongful rejection on trained and
    held-out controls. The engine's no-answer verdicts (`FAILED_INFRA`,
    `TIMEOUT`, `CRASHED`) on attacks and controls read as `INFRA`: counted
    apart, never completed, held, passed or refused. A family with no finding
    is `ATTEMPTED_COVERAGE` (with `bound: null`) only when at least one attempt
    reached the path and was judged `HELD`, and an engine run's state is not
    `INCONCLUSIVE`; otherwise it is `INCONCLUSIVE` (`engine_state_inconclusive`
    for a silent or unanswered specimen, `no_attempt_judged` when every attempt
    was infrastructure, Graphite's refusal, undetermined or not applicable). A
    declared seam, or a family with no attempt, is `NOT_RUN`. A breach and a
    wrongly refused control (trained or held-out) are `FAILING_TRIGGER`. Only
    the report reads held-out controls; verification never calls
    `adapter.controls`. The `controls_held_out` argument is required. The
    engine state is computed by the engine's own rule (`engine.family_state`),
    restated locally until AT-A's engine is merged.
13. **B2.** Each family's sides are cut to their first `budget` attempts in
    run order (one integer, or a mapping that must cover every family), each
    summarized like the report, and the store snapshot digest the Attacker ran
    under is recorded (`sha256:` form), with `store_snapshot_status`
    `PINNED` or `store_snapshot_missing`. An engine side's family state is
    recomputed from its records within the budget (the cut attacks and their
    specimens); controls are engine diagnostics, not attempts, so they are
    never budgeted and a wrongly refused control is a finding at any budget.
    The comparison is descriptive, never a grade.
    `benchmark.track_a_baseline` reads battery's deterministic side from
    `track_a.run()` unchanged.
14. **An agent naming a protected case is `OTHER_SIGNAL`, with its own
    reason.** A loop-local result that echoes the agent's own protected
    request (a finish summary naming a protected case; Graphite refuses such
    requests to the path, so the protected words in the result are the
    agent's) is withheld as `protected_material_named_by_agent` and recorded
    `OTHER_SIGNAL` with reason `protected_named_by_agent`, apart from a path
    exposure (`exposure:...`). This applies the design's "a development
    finding that names a protected case is itself an OTHER_SIGNAL finding";
    like decision 3 it is fail-closed and blocks later expansion until the
    technical owner grades it.
15. **The oracle seam.** The oracle is handed an `OracleAttempt`: `name`
    (the journal identity), `arguments`, `tool`, `path_accepted` (the path's
    plain answer: True, False or None) and, unless the adapter derives its own
    input per family (`attempt_input`, battery's), `value` (the construction,
    else the arguments) for an oracle that re-runs it on the real boundary
    (`attack.adapter.family_oracle`). Oracle verdicts read: `HELD`,
    `BREACHED` (its condition, else `FAILING_TRIGGER`), `EXPOSURE` →
    `BREACHED` `OTHER_SIGNAL`; `FAILED_INFRA`/`TIMEOUT`/`CRASHED` → `INFRA`;
    `NOT_RUN` → `NOT_APPLICABLE`; `INCONCLUSIVE` (a hold the detector cannot
    vouch for, or an unclear path answer) and `UNDETERMINED` → `UNDETERMINED`.
    Only `HELD` and `BREACHED` are scored. A rebuilt record is read from a
    mapping, a `record`/`built`/`expected` attribute, the engine `Rebuilt`'s
    `detail["record"]` (battery's), or that `Rebuilt`'s digests and detail.
    Integration tests run against AT-A's real `DeclaredAdapter` and AT-B's real
    battery adapter when those modules are present (`pytest.importorskip`);
    on this branch alone they skip.

### Mutations covered

Each switched off by monkeypatch turns its guarding test red:
counting `FAILED_INFRA` as a pass (`analysis.INFRA_STATES`, and
`report.NOT_COMPLETED` for attacker and engine runs); reading the engine's
no-answer verdicts as held (`report._ENGINE_ATTACK`); a silent specimen read
as coverage (`report.engine_state`); a finding outside `CONDITIONS`
(`verify.check_conditions`, in verify and report); expansion after a finding
(`CampaignController._expansion_blocked`); scoring an unrebuildable
construction (`verify.is_unrebuildable`, with a refusal that carries a record,
so the mutation reaches the oracle); skipping the pod rebuild comparison
(`verify._differences`); a pod-scored attempt without its record treated as
unscored-by-a-pod (`verify._pod_scored`); the loop's refusals read as the
path's (`analysis.REFUSAL_CODES`); comparing past the B2 budget
(`benchmark._within`).

### Not decided here

Isolation for hostile code (reserved to the security owner), any numerical
reproduction tolerance (`HUMAN_INPUT`), any attack budget for an admission
run, and the grading of any finding (the technical owner's).
