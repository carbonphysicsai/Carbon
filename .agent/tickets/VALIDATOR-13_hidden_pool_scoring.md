# VALIDATOR-13: score Graphite constructions on hidden batches through the real validator

**Status:** design, for the Test Lead's review before any build.

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
- **Pool rule:** battery's approved `exam.DEVELOPMENT_RULE` (OD-2), unchanged:
  3 active batches of 100, rotation after every 3 admitted submissions. No new
  scientific value.
- **Rule v1 versus v2:** v1 (count rotation) is the default. Rule v2 (one
  scored submission per hotkey per tempo, block rotation) and
  `require_commitment` need chain block receipts and commitments, so they wait
  for the owner's chain decision. Until then the deployment sets
  `require_commitment: false` and records that difference from mainnet in
  every outcome's rule facts.

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
- Validator unavailability, `FAILED_INFRA` and `ROTATION_PENDING` are recorded
  as the hidden result's typed state (`PENDING` or `FAILED_INFRA`). They are
  never a candidate failure, never charged to the agent, and never block the
  practice result.
- `INVALID_CONSTRUCTION` cannot newly appear: Graphite's gate already ran the
  same compile, and a disagreement is a typed `GATE_DISAGREEMENT` finding (the
  VALIDATOR-10/12 property, checked live).

**6. Fresh cases.**
- Every run's winner is re-scored once on its Challenge's sealed confirmation
  set (`fresh_cases_rerun`, currently NOT_RUN). That is an operator action the
  owner orders, run on the operator host. This session never reads or
  regenerates a sealed set.

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

## Not in scope (owner-reserved)

Weights, chain commitments, rule v2's block windows, settlement, and how
mainnet validators share a hidden test.

## Maturity ceiling

IMPLEMENTED and TESTED (DEVELOPMENT). It is not a security audit, and no
qualification, reward or LIVE authority.
