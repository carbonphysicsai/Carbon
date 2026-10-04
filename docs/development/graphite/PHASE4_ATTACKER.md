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
Carbon's own side of it through the engine. It owns no science, no grade and no
authority; nothing here submits, opens a pull request, writes weights or
touches chain state.

```
python -m carbon.agent_campaign.graphite.phase4 run --root DIR --dry-run
python -m carbon.agent_campaign.graphite.phase4 run --root DIR \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json \
    --credential-file PATH --runpod-key-file PATH \
    --miner-profile PROFILE.json --miner-campaign ID [--session N] [--challenge TOKEN]
python -m carbon.agent_campaign.graphite.phase4 log --root DIR [--dry-run]
```

### The session

`AttackerProvider` is #504's `Phase3Provider`, so an Attacker session inherits:

- the **v2 session-limits rule**: no session-turn cap and no per-role call cap.
  The grant's per-run money cap (the token share) and its elapsed limit are the
  only bounds. A reintroduced call cap is a mutation its tests catch.
- the engine's recorded **context compaction** and the **parallel-call rule**;
- the experiment's **pods**, on which Carbon rebuilds the constructions it
  scores (the verify step).

It drives the **Attacker role** (`roles.py`): neutral wording that probes the
families named in its brief, for the Challenge and construction level it is
given, through the same research path a participant uses. `AttackerTools`
enforces one resource rule before dispatch: a sandbox code run must ask for a
wall allowance of at most the adapter's `code_run_seconds` (family
`resource_and_failure_accounting`); a timeout at that allowance is
`FAILED_INFRA`, never a pass. An Attacker proposes no construction, so the
session bundles and scores nothing itself.

### Carbon's side

From the session's journal, never the model's prose: `attack.analysis` reads
the attempts and maps each to a family through the Challenge's adapter;
`attack.verify` re-checks each with the adapter's oracle and rebuilds every
attack construction Carbon scores on the pods; a verified breach, or a wrongly
refused control, is recorded on the #475 controller as a `FAILING_TRIGGER`
through `controller.record_finding`, where it stops any later expansion.
Attempts, verified findings and near-misses go into the durable attack-
knowledge store (`attack.knowledge`), whose snapshot digest the run pins. The
per-family report and benchmark B2 (Attacker versus battery's deterministic
`track_a` at an equal attempt budget) come from `attack.report` and
`attack.benchmark`. Findings use only the CONDITIONS vocabulary; zero findings
is reported as attempted coverage, never an exploit-free bound.

### The dry run

`run --dry-run` runs one session with a scripted model and `ScriptedPods` under
`DIR/attacker-dry-run`, with a synthetic copy of the grant and no miner path,
then Carbon's side, producing the coverage report and B2. It makes no network
call and spends nothing.

## The grant

`GRAPHITE-GRANT-PHASE4` (see `grants/README.md` for the derivation): ceiling
USD 10.50, cleanup USD 0.25, worst-case run cost USD 3.41 (six verify pods at
USD 0.246369864 ≈ 1.48, plus about 40 glm-5.2 calls ≈ 1.93), three permitted
runs, one concurrency, 15,600 s runtime, expiring 2026-12-31. One grant covers
the Attacker's model calls and the verify pods. Money and time bind, never a
call count.

**A live run is not executed in this work.** Under OWNER-GRAPHITE-ATTACKER-01
§5 a live run happens only after the engine merges and the scripted dry run
passes; it is a human-driven step beyond this slice.
