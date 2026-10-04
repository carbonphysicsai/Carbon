# Graphite phase 4: the Attacker and the general attack engine

**Authority.** OWNER-GRAPHITE-ATTACKER-01
(`.agent/decisions/2026-10-04-OWNER-GRAPHITE-ATTACKER-01.md`), recorded again
as OWNER-GRAPHITE-TEST-WAVE-01 §2 (carbonphysicsai/Carbon#556). The owner
approved a general attack capability "that generalizes to any challenge at any
construction level and improves as it goes", built as a multi-agent workflow,
and approved its live grant GRAPHITE-GRANT-PHASE4 as proposed.

This page covers the **phase-4 session driver**, slice AT-E. The challenge-
neutral attack engine itself (the neutral core, the per-Challenge adapters, the
analysis, verify, knowledge, report and benchmark modules) lives in
`carbon.agent_campaign.attack` and is documented with those modules.

## The driver

`carbon.agent_campaign.graphite.phase4` runs one Attacker session and then
Carbon's own side of it through the engine's published interfaces. It owns no
science, no grade and no authority; nothing here submits, opens a pull request,
writes weights or touches chain state.

```
python -m carbon.agent_campaign.graphite.phase4 run --root DIR --dry-run [--challenge TOKEN]
python -m carbon.agent_campaign.graphite.phase4 run --root DIR \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json \
    --credential-file PATH \
    --miner-profile PROFILE.json --miner-campaign ID [--session N] [--challenge TOKEN]
python -m carbon.agent_campaign.graphite.phase4 prelive --root DIR [--challenge TOKEN] [--grant PATH]
python -m carbon.agent_campaign.graphite.phase4 cancel --root DIR --session N
python -m carbon.agent_campaign.graphite.phase4 status --root DIR [--dry-run]
python -m carbon.agent_campaign.graphite.phase4 log --root DIR [--dry-run]
```

`--challenge` names any adapter registered at Level 0 in
`attack.adapter.ADAPTERS` (default: battery).

### The session

`AttackerProvider` is #504's `Phase3Provider`, so an Attacker session inherits:

- the **v2 session-limits rule**: no session-turn cap and no per-role call cap.
  The grant's per-run money cap (the token share) and its elapsed limit are the
  only bounds;
- the engine's recorded **context compaction** and the **parallel-call rule**.

It differs from a Constructor session where an Attacker does something else:

- its **brief comes from the adapter alone**: the public identity, the
  contract token and digest, the construction level, the families (each with
  its check and its boundary as the goal), the families declared NOT_RUN, the
  code-run wall allowance, and the attack-knowledge snapshot it runs under. An
  adapter that lacks its session surface (`public_identity`,
  `code_run_seconds`) is refused with a typed code; the driver never
  substitutes battery's values. `start` refuses a brief whose identity, level,
  families or allowance are not its adapter's;
- it has **no baseline and launches no pod**: an Attacker proposes no
  construction. Its frozen session record says so (`pods_per_session: 0`,
  `verify_pod_rebuild: NOT_RUN`, `on_limit_stop: record_attempts_only`), with
  none of the Constructor's pod, delivery or stall fields;
- `AttackerTools` enforces one resource rule before dispatch: a sandbox code
  run must ask for a wall allowance of at most the adapter's
  `code_run_seconds` (family `resource_and_failure_accounting`). The rule is
  the adapter's own `code_run_refusal` (else the core's
  `attack.adapter.code_run_refusal`), the same function that family attacks.
  A run that reaches its own allowance ends `DEADLINE`
  (`OWN_ALLOWANCE_ELAPSED`, `research_carrier`), its own outcome and never a
  pass; only a failure Carbon cannot attribute to the run is an
  infrastructure failure.

SIGINT or SIGTERM, or `cancel`, asks a running session to stop at its next
checkpoint. Since no pod is launched there is nothing to reconcile after it.

### Carbon's side

From the session's journal, never the model's prose:

1. `attack.analysis.attempts` reads the attempts; `map_to_families` assigns
   each to one of the adapter's families (or `UNASSIGNED`, reported).
2. `attack.verify.verify` judges every attempt. Carbon rebuilds each
   construction with the adapter's `rebuild` (an unrebuildable one is typed
   and never scored), re-checks it with the adapter's oracle, and bundles a
   breach's specimen for a clean rebuild.
3. A verdict is a finding exactly when it is `BREACHED`, and then it carries
   its conditions in the CONDITIONS vocabulary; a verdict where the two
   disagree is refused. Each finding is recorded through `verify.record` ->
   `controller.record_finding`, after which every expansion is refused
   (`admission_expansion_after_finding`).
4. Every verdict is written to the attack-knowledge store with its own
   outcome. A timeout, an infrastructure failure (stored `FAILED_INFRA`,
   never folded into a crash) or a crash, an unrebuildable construction and Graphite's
   own refusal are never stored as a hold; a near miss is stored only when the
   oracle reports one. A record the store refuses is listed with its typed
   code.
5. The per-family report is built from the session's verdicts
   (`report.attacker_runs`), with the held-out controls' wrongful-rejection
   measurement and the adapter's seams. Benchmark B2 compares the Attacker
   with the adapter's deterministic engine runs (`attack.adapter.run_adapter`;
   for battery, the families `track_a` runs) at an equal attempt budget, and
   is recorded under the store snapshot the session was pinned to before it
   opened.
6. The per-check view (`coverage.checks`, schema
   `carbon.graphite.attacker-coverage.v3`) lists all eight Track A checks.
   Under each one it names the run families and NOT_RUN seams the adapter
   declares for that check, with each family's report status. The check comes
   from the adapter's own `FamilyDef.check` / `SeamFamily.check`, never from a
   report row, so a check covered only by seams (battery's
   `fresh_attack_confirmation`) is still named. A check nothing declares is
   listed as `undeclared`, a report or B2 row that lost its check is listed
   under `report_rows_without_check`, and a row whose check disagrees with
   the adapter's declaration is refused.

Zero findings is reported as attempted coverage, never an exploit-free bound.
The coverage report claims neither security acceptance nor a grade.

**Seam: Carbon's verify-pod rebuild.** Rebuilding attack constructions on
Carbon-launched phase-3 pods is declared NOT_RUN in phase 4
(`phase4.POD_REBUILD_SEAM`). `verify` receives no pod build records, so an
attempt the path says ran on a pod is `UNDETERMINED`, never a pass. The live
runner uses a pod backend that launches nothing (`NoVerifyPods`); the grant
keeps the pods' share reserved.

### The attack-knowledge snapshot

Before a session opens, the driver freezes the store (`AttackStore.snapshot`)
and records the digest under `DIR/attacker/pins/session-N.json`; a resumed
session reuses it. The brief carries the snapshot's digest and its per-family
counts for this Challenge, and B2 records the same digest. Records the session
adds belong to the next snapshot.

### The dry run

`run --dry-run` runs one session with a scripted model and `ScriptedPods` under
`DIR/attacker-dry-run`, with a synthetic copy of the grant and no miner path,
then Carbon's side with the real engine, producing the coverage report and B2.
With no miner path nothing reaches the path: every attempt is Graphite's own
refusal and no finding is invented. It makes no network call (the whole run is
under a network guard that refuses and records any socket connect or name
lookup) and spends nothing: the scripted model reports a zero charge, and a
run whose settled amount is not exactly zero exits 4.

### The pre-live gate

The dry run's scripted model and pods stand where the real code runs, so a
defect in the real code's threading cannot show there (phase-3 session 3).
`prelive` (`phase4_prelive`) must pass before the first live run. It runs the
live run's own parts (`phase4.live_checks`, `live_model`, `live_provider`,
`run_live`) up to the network boundary, with a fake only at that boundary:

- the grant and code checks (L1, below) on the real checkout, and a copy with
  its ceiling raised refused;
- the session: the real `AttackerProvider`, campaign controller, research
  loop and ledger (`asyncio.run` on the main thread, each model call through
  `asyncio.to_thread`), the real model client (`LiveModel` ->
  `SelectionTransport`, `engy-chat`, its key read from a file and posted from
  its own worker thread) answered by a fake opener in Engy's Chat Completions
  shape with a zero charge, and the real miner-path translation over a fake
  miner door;
- Carbon's side: analysis, verify, the report and B2, the attack-knowledge
  store's hash-chained journal, the session pin, a resume reusing it and a
  view under another digest refused, and the controller's findings;
- the pod and compute-store path (`RunPodPods` over `operator_compute` and
  its sqlite `ComputeStore`) with a fake RunPod transport, driven the way
  phase 3 drives it (`asyncio.to_thread`) and, as a control, on the thread
  that built it. Phase 4 launches no pod, but this step still blocks the
  gate until the pod store is thread-safe. When the pod layer provides its
  own real-path check (`pods.real_path_check`) the gate calls it.

A sqlite thread guard records any use of a connection from a thread other
than the one that opened it, even one a caller catches, and a network guard
refuses every connect. The gate prints one JSON report (each path, what it
exercised, its status and detail, `blocking_findings`, and
`phase4_live_path` for the phase-4 paths alone) and exits 0 only when every
path passed with no network use. Run it from the repository
root, exactly as the live run will be started.

## The grant

`GRAPHITE-GRANT-PHASE4` (see `grants/README.md` for the derivation): ceiling
USD 10.50, cleanup USD 0.25, worst-case run cost USD 3.41 (six verify pods at
USD 0.246369864 ≈ 1.48, the token share 1.93 ≈ 40 glm-5.2 calls), three
permitted runs, one session at a time, 15,600 s runtime, expiring 2026-12-31.
Money and time bind, never a call count.

A live run reads the grant from git, never from the working tree
(`check_committed_grant`): the file passed must equal the committed blob at
HEAD (`git show HEAD:docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json`),
HEAD must be on a remote branch, and the grants directory must match HEAD.
An operator who edits the working-tree grant and passes it is refused.

**A live run is not executed in this work.** Under OWNER-GRAPHITE-ATTACKER-01
§5 a live run happens only after the engine merges and the scripted dry run
passes; it is a human-driven step beyond this slice.
