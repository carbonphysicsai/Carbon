## 2026-10-04 — GRAPHITE-ATTACKER-AT-F: before the first live phase-4 run — pre-live gate, grant from git, scoped ids and follow-ups

**Amends** GRAPHITE-ATTACKER-AT-E
(`.agent/decisions/2026-10-04-GRAPHITE-ATTACKER-AT-E.md`), the phase-4
Attacker session driver merged in carbonphysicsai/Carbon#563. AT-E is
unchanged; this file records the follow-up to #563.

The follow-up PR to #563 (head 456e05ae). The Test Lead requires it to merge
before the first live phase-4 run. Every change is an engineering choice
within the attack engine's delegated authority (OWNER-GRAPHITE-ATTACKER-01,
OWNER-GRAPHITE-TEST-WAVE-01/02). None changes a scientific value, threshold
or gate, EV5 or sealed material, the live construction contract or the
expansion records. Battery's `track_a` output stays byte-identical (the
digest pin test passes), and the store stays unreachable from the miner
paths (`tests/invariants/test_attack_store_unreachable.py`). No live run,
spend or pod.

1. **L1: the grant check reads git, not the working tree.**
   `check_committed_grant` compared the given copy with the working-tree
   file, both under the operator's control. It now:
   - reads the committed blob (`git show HEAD:<GRANT_FILE>`); none is
     `phase4_grant_not_committed`;
   - compares the given copy's canonical digest with that blob
     (`grant_differs_from_the_committed_phase4_grant`), so an edited
     working-tree grant, passed directly or copied, is refused;
   - requires HEAD on a remote branch (`grant_commit_not_pushed`);
   - binds the grant to main, which is what the owner approved (Test
     Lead's condition C1 on #569): it fetches `origin main` and requires
     HEAD's grant blob to be main's (`grant_differs_from_main`; no fetch or
     no grant on main is `main_grant_unavailable`), so a pushed feature
     branch carrying an edited grant is refused;
   - requires the grants directory to match HEAD, untracked files included
     (`grants_directory_has_uncommitted_changes`).
   `phase4.live_checks` runs it with #504's `check_code_ref` (HEAD pushed,
   shipped code clean). Tests build a repository with a bare remote and
   check each refusal, plus a mutation showing the old disk read let the
   edit through.
2. **L2: the pre-live gate (`phase4 prelive`, `phase4_prelive`).**
   - `command_run` is split into `live_checks`, `live_model`,
     `live_provider` and `run_live`. The gate calls exactly these, with a
     fake only at the network boundary: Engy's Chat Completions shape
     through `LiveModel`'s new `opener` (replacing urllib's opener in
     `SelectionTransport`, as its tests already could), a fake miner door
     under the real `MinerPathTools`, and a fake RunPod transport and pod
     HTTP under the real `RunPodPods` and `operator_compute`.
   - The live threading runs as in a live run: `asyncio.run` on the main
     thread, each model call in `asyncio.to_thread`, posted from
     `model_provider`'s worker thread.
   - A sqlite thread guard records any use of a connection from another
     thread, even one a caller catches, and keeps `check_same_thread` on. A
     network guard refuses and records every connect and name lookup.
   - **Result on this branch: the phase-4 paths PASS; the pod step FAILS
     and blocks the gate.** The pod path, built on the main thread and driven through
     `asyncio.to_thread` as `Phase3Tools.call` drives it, fails at once:
     `sqlite3.ProgrammingError` at `operator_compute/store.py`
     `record_balance` -> `_tx` (`BEGIN IMMEDIATE`), the `compute.sqlite3`
     connection opened on `MainThread` and used on `asyncio_0`. That is
     phase-3 session 3's defect. The same path on the thread that built the
     store passes, so the fakes are not the cause. Phase 4's live provider
     uses `NoVerifyPods` (asserted by the gate) and never opens a
     `ComputeStore`, so `phase4_live_path` is PASS; the pod step
     (`pods_compute_store_phase3_threading`) is listed under
     `blocking_findings` (`blocks_phase4_live_run: false`) and the gate's
     verdict is FAIL, exit 4, until the store is thread-safe.
     `pods.py` and `store.py` are not changed here: the fix is a separate PR
     (claude/fix-pod-store-threads), which also adds the pod layer's own
     real-path check (`pods.real_path_check`). The gate calls that check
     when it exists and its own minimal one until then, so the pod step, and
     the gate, go green once that PR merges.
   - The gate also showed that the runner must start from the repository
     root: from elsewhere `AttackerProvider` fails at construction, because
     the pod pricing it reads lives in the `scripts` package. The gate fails
     loudly there too, so it should be run from the directory the live run
     will be started from.
   - Tests cover a deliberate cross-thread sqlite use (raised, swallowed, and
     with `check_same_thread=False`), the network guard, the whole gate on a
     synthetic Challenge and on battery through the CLI, a cross-thread
     defect injected into the phase-4 session path (gate FAIL, exit 4), and
     a refused grant stopping the gate.
3. **L3: short sealed ids are scoped.** Cooling's final condition ids
   (`rep-01`…`rep-04`, `boundary-01`, `boundary-02`) became a
   `scoped_phrase` entry with the study's scope from the cold-plate freeze
   record (`study_id` `ai-accelerator-cooling-synthetic-v1`, Challenge
   `chip-cold-plate`). An id matches study-qualified anywhere
   (`ai-accelerator-cooling-synthetic-v1/rep-01`, `chip-cold-plate rep-04`),
   or bare only in a value that names the study or Challenge. "boundary 01"
   in ordinary text no longer matches. False positives, string by string:
   - battery adapter's attack corpus (162 items: boundaries, attack
     examples, every family's attack inputs, controls, seams): 0 before, 0
     after;
   - attack and test fixtures at the base commit (6,088 strings): 9 cooling
     hits before (6 the registry's own bare ids, 3 bare-id test probes), 0
     after; every other identity's hits unchanged (13, 2, 3, 4, 4);
   - attack and test fixtures on this branch (6,579 strings): 5 cooling
     hits, all deliberate study-qualified test probes;
   - repository text outside the attack package (84,456 strings): no
     cooling hit before or after; the 3 other hits are the genuine
     `ev5-confirmation` and `graphite-confirmation-v1` role names.
4. **Follow-ups from the engine review.**
   - The knowledge journal is hash-chained (journal schema v2: each entry
     carries `prev`, the sha256 of the previous line). Every read checks
     schema, `seq` 1, 2, … and the chain, and refuses a dropped, reordered,
     duplicated, edited or unchained entry (`attack_record_corrupt`).
   - One code-run rule: `attack.adapter.code_run_refusal`. Battery's
     `code_run_refusal` calls it, and `AttackerTools` calls the adapter's
     own rule (`phase4.code_run_rule`), so `resource_accounting` attacks the
     dispatcher's rule, not a copy.
   - The neutrality scan covers every module of `carbon/agent_campaign/
     attack` (the per-Challenge `adapters/` excepted). `benchmark.
     track_a_baseline` moved behind the adapter (`BatteryLevel0Adapter.
     deterministic_baseline`); `benchmark.adapter_baseline` names no
     Challenge.
   - The dry run reports a zero charge, runs under the network guard, and
     exits 4 unless the settled amount is exactly zero; its test adds its own
     socket guard.
   - `analysis.construction` reads a `check_design` design
     (`analysis.design_of`: its strategy, or the whole design when it asks
     for capabilities); battery's attempt input reads it the same way.
     The generic `family_oracle` judges nothing for a session attempt Carbon
     rebuilt no construction for (`NO_REBUILT_CONSTRUCTION`; verify:
     `UNDETERMINED`, `oracle_needs_a_rebuilt_construction`).
   - `verify._oracle` scores a `HELD` only with the specimen's `FIRED`
     verdict; `{"held": True}` alone is `UNDETERMINED`
     (`oracle_hold_without_specimen`).
   - `breached()` runs inside `answer()` (`engine.judged`), in the engine
     and in `family_oracle`: a judgement that raises is CRASHED (or TIMEOUT,
     FAILED_INFRA), never propagated. The track_a byte pin holds.
   - `FamilyRun.not_attempted` reaches the report and B2 (None for an
     Attacker run, which has no fixed attack set).
   - `store_outcome` stores an infrastructure failure as `FAILED_INFRA`
     (a new store outcome, inconclusive), not `CRASH`. The `AttackerTools`
     docstring now says a run that reaches its own allowance ends
     `DEADLINE` (`OWN_ALLOWANCE_ELAPSED`), as `research_carrier` types it.
   - `analysis` reads results, and `verify.finding_body` and
     `_record_body` redact, by the narrowed rule (`knowledge.protected` or a
     registered sealed identity), not `graphite.tools.protected`. Graphite's
     harness, which still withholds a result naming `.env` or `secret` from
     the agent, now records why (`material`: `attack_target` or
     `protected_material`); Carbon reads an attack-target refusal as the path
     answering (`UNDETERMINED`, `result_withheld_attack_target`), never an
     exposure. A refusal that does not say why is still an exposure.
   - The held-out identity registry is scoped per adapter: by the run
     context's `(challenge, profile)`. A registration replaces its scope's
     set, `clear_held_out` drops one, and one adapter's identities never
     refuse another's controls.
   - Identity and marker matching fold common Cyrillic and Greek look-alikes
     to Latin (`knowledge.HOMOGLYPHS`).

**Not done here.** The `ComputeStore` cross-thread defect (its own PR,
claude/fix-pod-store-threads, above).
Still open from the earlier list: a check-only control that declares no
input is identified by its family and name, and
`SUITE_V1_BATTERY_COVERAGE.json` still needs a canonical regeneration.
