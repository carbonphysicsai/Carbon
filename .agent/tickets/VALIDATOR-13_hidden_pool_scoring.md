# VALIDATOR-13: score Graphite constructions on hidden batches through the real validator

**Status:** approved by the Test Lead on 2026-10-05, with the §6 amendment.
Being built.

**Authority:**
- The owner, 2026-10-05: testing must operate like mainnet, with hidden
  conditions used for scoring. This extends the owner's testnet and mainnet
  parity direction of 2026-10-04.
- The Test Lead, 2026-10-05: item 2 (hidden-batch scoring through the real
  validator) is in the wave's scope, battery first, design before build.
- Item 3 (weights, chain, settlement and the cross-validator set-up) is not
  part of this ticket. It is reserved for the owner and goes to them directly.

**Executor:** the Carbon Validator session. Branch
`claude/validator-13-hidden-pool`, from main `0f2a055c9`.

## Problem

Graphite scores each construction on the public PRACTICE references
(`graphite/experiment.py` step 4, evidence `DEVELOPMENT_PUBLIC_ADAPTIVE`). The
agent sees every result and adapts, so the score measures fit to cases it has
already seen, not generalisation. Mainnet scores on hidden batches the miner
never sees. Graphite's evidence must come from the same place.

## Design (battery)

**1. A separate operator deployment, `graphite-hidden-battery-v1`.**
- It is battery's existing deployment format (`carbon/battery/deployment.py`),
  with its own state, `private_root`, `journal` and `work`, and the carrier
  backend (isolated worker). No new evaluation path exists: battery's only
  path is `deployment.evaluate`, and this design uses it unchanged.
- **Why separate:** Graphite's many adaptive submissions must not rotate or
  burn the testnet deployment's pool, and EV5's sealed batch (journal sequence
  14) and `graphite-confirmation-v1` stay untouched.
- **Operator actions:** creating the root and the configuration is an operator
  action; the owner supplies the paths. Nothing here creates or reads a root.
- **Pool rule: battery's rule v2** (`exam.DEVELOPMENT_RULE_V2`), as
  OWNER-VALIDATOR-MAINNET-PARITY-01 item 2 decided:
  - one scored submission per hotkey per 360-block tempo;
  - rotation by finalized block;
  - hidden-batch results sealed from miners.

  No new scientific value.
- **The receipt block** comes from a clock the caller passes in. In operation
  that is testnet's finalized block (a read-only chain read). Tests use a
  fixed clock.
- **The per-hotkey cap:** a run is one development identity, so it gets one
  hidden score per tempo, as a single mainnet miner does. A submission in a
  used window is recorded `WINDOW_USED`, with its next block. That is not a
  refusal, and the practice loop continues.
- **The commitment check** (`require_commitment`) needs a chain commitment
  reader, which the deployment does not wire today (`commitments=None`). It
  arrives with the weights ticket. Until then the hidden deployment sets
  `require_commitment: false` and records that difference from mainnet.

**2. Hook: a new module, `carbon/agent_campaign/graphite/hidden_score.py`.**
- `Experiment` takes an optional `hidden` scorer. With None, behaviour and
  bytes are unchanged; every current test stays byte-pinned.
- After a proposal passes the reconstruction gate, the same admitted recipe is
  submitted to the hidden deployment through `deployment.evaluate`, as a
  `Submission` with a per-run development identity (a Graphite run id, never a
  chain hotkey) and the pinned `contract_digest`.
- The validator rebuilds on its own carrier worker on the operator host and
  predicts on its hidden pool. Pods are never involved: no hidden case, seed,
  fingerprint or prediction is ever staged to rented compute.
- The PRACTICE loop is unchanged. It is the free loop (invariant 12), and the
  agent keeps its practice feedback.

**3. Disclosure, the core of the design.**
- The agent's tool result gains only `BatteryValidator.outcome`, the miner
  allow-list. Under the sealed rule that is state, refusal codes and digests:
  no number computed from a hidden batch, exactly as a mainnet miner sees it.
- The operator score record (`BatteryAdapter.score_record`, replay-verified
  against stored predictions) is written under the run's private root, which
  is operator-only.

**4. Evidence.**
- The hidden result is a new class, `DEVELOPMENT_HIDDEN_POOL`. Graphite's
  report ranks constructions on it.
- The practice score is still shown, labelled `DEVELOPMENT_PUBLIC_ADAPTIVE`,
  and never ranked.
- Neither confers qualification, reward, weight or LIVE authority.

**5. Failure typing.**
- Validator unavailability, `FAILED_INFRA` and a used hotkey window are
  recorded as the hidden result's typed state (`UNAVAILABLE`, `FAILED_INFRA`
  or `WINDOW_USED`). They are never a candidate failure, never charged to the
  agent, and never block the practice result.
- **Stale pools under rule v2.** The owner's v2 rule never stalls: when a
  rotation is due and no batch is ready, it keeps scoring on the current
  batches and records `rotation_overdue` once per pool version. That replaces
  v1's `ROTATION_PENDING`.
  - Every hidden record scored on an overdue pool version carries
    `rotation_overdue: true`, so stale-pool evidence is always visible.
  - The run plan prepares enough batches for this not to happen.
  - Changing v2's no-stall rule would be an owner decision.
- `INVALID_CONSTRUCTION` cannot newly appear: Graphite's gate already ran the
  same compile, and a disagreement is a typed `GATE_DISAGREEMENT` finding (the
  VALIDATOR-10/12 property, checked live).

**6. Fresh cases (amended by the Test Lead, 2026-10-05).**
- A run's winner is re-scored once on a fresh hidden batch from
  `graphite-hidden-battery-v1` (`fresh_cases_rerun`, currently NOT_RUN). That
  batch has never been scored before, and it is retired after that single
  use and recorded as consumed.
- The Challenge's sealed confirmation set is one-shot (WAVE-05 §4). It is not
  used per run, because per-run re-scoring would burn it adaptively. It is
  kept for the single final confirmation, after the panel, the score rule and
  the analysis are frozen; that is an operator action the owner orders. This
  session never reads or regenerates a sealed set.

## Tests (DEVELOPMENT; synthetic root and batches only)

- **The non-leak differential.** Two hidden pools that give one construction
  different scores must produce agent-visible tool results that are equal byte
  for byte. This is the test that proves the hidden score cannot reach the
  agent.
- **No hidden material on the pod side.** The bytes staged to a pod, and the
  pod's program, contain no hidden batch fingerprint, seed or case id. This
  scans everything staged.
- **With `hidden=None`,** every existing Graphite test passes unchanged.
- **Typed states:** `ROTATION_PENDING`, `FAILED_INFRA` and validator
  unavailability each type correctly and never count against the candidate.
- **Leakage across deployments:** the hidden deployment refuses every reserved
  or sealed role (`interface.role_reserved`).
- **Ranking:** the report ranks on `DEVELOPMENT_HIDDEN_POOL` and never on a
  practice score.

## Attack side (Test Engineer, after the build)

The battery adapter gains the families `hidden_outcome_channel`, a repeated-
probe attack measuring whether outcome bytes vary with the hidden score, and
`rotation_exhaustion`, which drives the pool into `ROTATION_PENDING`. Each
measures the live deployment, not a function.

## Cost and capacity (measured before any run, not assumed)

Rotation every 3 admitted submissions means a run of N proposals consumes
about N/3 prepared 100-case batches, and each batch needs complete reference
solves. Before the first run I measure battery's reference solve time per case
on the operator host, and the run plan states the batches it needs. If too few
batches are prepared, the pool goes to `ROTATION_PENDING` and the hidden
results wait; nothing is scored on a stale pool.

## Cooling and motor (later, in this order)

- Their registered 60 + 2 sets (OWNER-GRAPHITE-TEST-WAVE-05 §4, #599) are
  one-shot confirmation sets, which serves `fresh_cases_rerun`.
- A rotating hidden screening pool needs a seed service and a pool rule
  (batch size, active batches, rotation). Battery's OD-2 values are battery's
  own; for cooling and motor those are scientific values not yet decided. They
  go to the owner when battery's version is built.
- Their reference solvers (OpenFOAM, GetDP) set the per-batch cost.

## Not in this ticket

These were decided by OWNER-VALIDATOR-MAINNET-PARITY-01 and are built as
separate tickets:
- testnet weights from hidden outcomes;
- the commitment reader;
- identical hidden cases and solver results for every validator;
- settlement.

## Maturity ceiling

IMPLEMENTED and TESTED (DEVELOPMENT). It is not a security audit, and no
qualification, reward or LIVE authority.

## Build record

- **Slice 1, hidden scoring.**
  - `graphite/hidden_score.py` (`HiddenPool`) adds the hook
    `Experiment(hidden=...)`.
  - The agent's `hidden` view is the sealed miner outcome.
  - `hidden-operator.json` holds the operator record;
    `Experiment.hidden_records()` reads it.
- **Slice 2, fresh-case rerun (§6).**
  - `BatteryValidator.fresh_rerun` adds the store methods `claim_rerun_set`,
    `record_rerun` and `rerun`, with no schema change. A prepared finalist
    batch is held `FINALIST` during the rerun, then `CONSUMED`, which makes it
    releasable.
  - Graphite calls it through `HiddenPool.fresh_rerun` and
    `Experiment.hidden_rerun(pid)`, for the winner the operator names.
- **Follow-ups:**
  - Delivery's selection moves onto the hidden evidence after #606 and #613
    land, since they overlap `delivery.py`.
  - A CLI flag wires a configured deployment into phase 3 and phase 4.
  - The attack families `hidden_outcome_channel` and `rotation_exhaustion`
    go to the Test Engineer.

## Validation

- `tests/cpu/test_graphite_hidden_score.py`: 12 passed (canonical).
- The battery validator suites (daemon, rule v2, deployment, service,
  adapter, intake), Graphite phase 3, the pod suites and the lessons log
  passed (canonical).
- `scripts/check_quality.py --base origin/main`: passed.
- **Slice 3, overdue pools** (the Test Lead's ruling, 2026-10-05).
  - Each operator record carries `overdue_margin_blocks`.
  - `hidden_score.report` and `Experiment.hidden_report()` rank only
    non-overdue, replay-reproduced scores, per pool version.
  - Overdue-pool scores are listed separately, counted, with their margin, as
    descriptive evidence only. They never enter a primary ranking, an
    alignment (Q1) result or a promotion claim.
  - Hidden-score tests: 14 passed (canonical).
