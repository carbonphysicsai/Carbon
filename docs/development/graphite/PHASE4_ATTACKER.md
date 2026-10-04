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
  `code_run_seconds` (family `resource_and_failure_accounting`). A timeout at
  that allowance is `FAILED_INFRA`, never a pass.

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
   outcome. A timeout or crash, an unrebuildable construction and Graphite's
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
refusal and no finding is invented. It makes no network call and spends
nothing.

## The grant

`GRAPHITE-GRANT-PHASE4` (see `grants/README.md` for the derivation): ceiling
USD 10.50, cleanup USD 0.25, worst-case run cost USD 3.41 (six verify pods at
USD 0.246369864 ≈ 1.48, the token share 1.93 ≈ 40 glm-5.2 calls), three
permitted runs, one session at a time, 15,600 s runtime, expiring 2026-12-31.
Money and time bind, never a call count.

**A live run is not executed in this work.** Under OWNER-GRAPHITE-ATTACKER-01
§5 a live run happens only after the engine merges and the scripted dry run
passes; it is a human-driven step beyond this slice.
