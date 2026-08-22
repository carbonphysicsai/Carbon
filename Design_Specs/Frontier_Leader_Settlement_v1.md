# Carbon Frontier Leader Settlement v1

**Status:** OWNER-RECOMMENDED v1 — ready for tech/economic/protocol review.  
**Purpose:** Define Carbon's challenge-local frontier replacement and equal-challenge settlement semantics.  
**Does not redefine:** scientific Challenge qualification, Score Pack semantics, Bittensor/Yuma consensus, or product qualification.

---

# 1. Core rule

> **Carbon pays for verified frontier advances, not permanent incumbency and not participation.**

For each reward-enabled qualified Challenge, Carbon maintains one scientific frontier. A miner earns the Challenge's base reward slot only when its submitted construction method becomes a new scientifically verified frontier under the registered Leader Replacement Policy.

---

# 2. Equal Challenge breadth

At the start of each settlement window, Carbon freezes the set of Challenges satisfying:

```text
LIVE
AND reward_enabled
AND scientific qualification current
```

Let the number of such Challenges be `N`.

Each Challenge receives equal logical base allocation:

```text
slot_fraction = 1 / N
```

This allocation is independent of:

- raw Challenge score magnitude;
- number of submissions;
- incumbent score;
- current popularity;
- model family;
- Challenge-specific score range.

Carbon's intended operating target may be 4–7 simultaneous Challenges. P0 may target seven PDE Challenges, but unqualified Challenges do not enter the reward-enabled set merely to achieve a count.

---

# 3. Persistent frontier, event-based reward

A `FrontierRecord` is persistent scientific state.

Remaining the incumbent does not itself create a reward event.

```text
leader remains best -> no new frontier reward
new verified method advances frontier -> reward event
```

The reward unit is a `FrontierAdvanceEvent`.

---

# 4. Challenge launch baseline

Every reward-enabled Challenge must start with a registered `FrontierBaseline`.

A first miner does not earn merely by being first or barely admissible.

The baseline may be:

- a protocol-owned benchmark construction method;
- an independently qualified baseline model;
- a requalified compatible prior frontier;
- another dossier-approved baseline.

The first paid miner must establish scientific superiority over the baseline.

---

# 5. Submission and screening

Submissions during a settlement window may undergo normal Challenge evaluation for validity, scientific admissibility, and screening.

A contender is promotion-eligible only if its result state and evidence satisfy the registered policy.

Non-eligible states remain distinct:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
```

No non-eligible state can create a frontier reward.

---

# 6. Common frontier promotion exam

Stored scalar scores from different hidden draws are not sufficient for leader replacement.

The final promotion decision must compare incumbent and eligible contenders on a common prospective scientific exam identity.

Conceptually:

```text
incumbent method
eligible contender methods
        ↓
same Challenge version
same distribution / SamplingPlan compatibility
same Score Pack
same fresh hidden promotion case bundle
same registered reconstruction-repeat policy
        ↓
comparable ScoreResults
```

Where method-level reconstruction is stochastic, no method may be represented by a cherry-picked reconstruction.

---

# 7. Batch settlement

Carbon settles at most one Challenge frontier reward per Challenge per settlement window.

Recommended sequence:

1. submission cutoff;
2. resolve protocol-valid retries / infrastructure failures according to policy;
3. determine promotion-eligible contenders;
4. execute the common frontier promotion exam;
5. evaluate Leader Replacement Policy;
6. establish at most one `FrontierAdvanceEvent`;
7. settle the Challenge's logical slot.

Arrival order and evaluator latency do not define scientific priority.

---

# 8. Leader Replacement Policy

A new leader is not defined by `challenger_score > incumbent_score` alone.

The registered policy returns at least:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

It may use Challenge-qualified semantics such as:

- minimum meaningful scientific separation;
- repeated evaluation;
- reconstruction-repeat evidence;
- uncertainty/equivalence bands;
- conservative bound comparison;
- mandatory stratum requirements already expressed by Score Pack.

The Leader Replacement Policy consumes qualified ScoreResults. It does not invent new physical measurements or thresholds outside the registered scientific chain.

> **A frontier advance is an evidence state, not a floating-point event.**

---

# 9. Equivalent challengers

If multiple challengers are scientifically superior to the incumbent but remain scientifically indistinguishable from one another after the registered extension/repeat policy, v1 does not manufacture a paid scientific winner via arrival order, hash, or arbitrary tie-break.

Preferred v1 behavior:

```text
still indeterminate -> no FrontierAdvanceEvent this window
```

The evidence remains recorded. A future co-frontier reward policy may be separately reviewed.

---

# 10. Same miner may advance the frontier

The frontier is defined by construction-method / strategy identity and scientific evidence, not merely by hotkey identity.

A current leader's miner may submit a genuinely improved method and establish another frontier advance if it passes the same promotion policy.

Exact duplicate strategy/artifact identity cannot create a new frontier event.

This design does not claim to solve unobservable strategic withholding of a stronger latent method. Mitigations include one payout maximum per Challenge window, meaningful superiority requirements, no carry-forward jackpot, submission economics, and empirical monitoring.

---

# 11. Settlement semantics

For every Challenge in the frozen `ChallengeSetEpoch`:

```text
FrontierAdvanceEvent exists -> PAY(uid, 1/N)
no event                    -> WITHHOLD(1/N)
```

v1 uses **no carry-forward** for unused Challenge slots.

No-event allocation is not redistributed to other Challenge winners at the abstract Carbon settlement layer.

This preserves equal Challenge opportunity and the rule that only verified new winners receive that period's Challenge allocation.

---

# 12. No incumbent rent

The current leader does not receive the Challenge slot in a no-improvement period.

The incumbent remains the comparison frontier but has no automatic ongoing miner reward merely for maintaining that position.

---

# 13. Multiple Challenge advances by one miner

If one miner independently establishes new frontiers in several Challenges during the same settlement window, it may receive each applicable Challenge slot.

Carbon enforces breadth across scientific Challenges, not an identity-level reward quota.

---

# 14. Challenge set lifecycle

A `ChallengeSetEpoch` freezes for each settlement window:

```text
challenge identities + versions
reward_enabled state
N
slot_fraction = 1/N
window boundaries
```

Challenge activation, suspension, retirement, or re-entry applies prospectively at a later settlement boundary.

No mid-window activation may dilute another Challenge's already-announced slot.

---

# 15. Scientific version changes and frontier lineage

Material scientific changes may break frontier comparability, including changes to:

- target population;
- SamplingPlan;
- generator/truth compatibility;
- MeasurementContract;
- mandatory gates;
- Score Pack;
- reconstruction-repeat policy.

A changed exam version requires explicit frontier compatibility handling. The old score is not numerically compared with the new score merely because both are scalar.

The new version must establish a new `FrontierBaseline` or explicitly requalify a compatible prior frontier.

---

# 16. Scientific defect / emergency freeze

If a material generator, truth, measurement, leakage, or scoring defect is discovered:

```text
Challenge reward settlement -> FROZEN
```

No new frontier event is established until the Challenge is repaired and requalified.

Historical scientific/economic records remain bound to their original versions. This v1 does not define retrospective clawback or fraud enforcement.

---

# 17. Exact settlement objects

## `FrontierRecord`

Conceptually binds:

```text
challenge identity/version
frontier method/strategy identity
owner/hotkey provenance
qualified ScoreResult/evidence refs
LeaderReplacementPolicy version
promotion exam identity
established period/time
```

## `FrontierAdvanceEvent`

Conceptually binds:

```text
challenge identity
prior frontier identity
new frontier identity
promotion exam identity
superiority decision evidence
settlement window
payee uid/hotkey
```

## `SettlementObligation`

```text
PAY(uid, slot_fraction)
WITHHOLD(slot_fraction)
```

The settlement obligation is economic protocol state downstream of scientific evidence.

---

# 18. Bittensor adapter boundary

Carbon's abstract settlement semantics must not be silently changed to fit convenient validator weights.

Current Bittensor behavior includes row normalization of surviving validator weights and normalized miner incentive. Therefore an inactive Challenge share is not necessarily preserved merely by assigning zero weight to its would-be winner.

Current Bittensor also supports withholding miner incentive routed to subnet-owner-associated hotkeys, but this can affect `MinerBurned` and therefore the subnet's broader emission economics.

A separate `BittensorSettlementAdapter` must be tested and reviewed to implement:

```text
PAY(1/N)
WITHHOLD(1/N)
```

without unintended redistribution or paying non-winners.

It must account for current chain constraints such as:

- row normalization;
- Yuma consensus/clipping;
- `min_allowed_weights`;
- max weight limits;
- commit-reveal;
- weight update rate limits;
- miner burn/recycle behavior;
- effect of `MinerBurned` on Carbon's subnet emission share.

No particular sink/burn implementation is ratified here.

---

# 19. Base protocol reward vs sponsor funding

Equal Challenge slots define Carbon's base protocol breadth mechanism.

Later high-cost industrial Challenges may receive additive sponsor/program bounties. Those are separate funding instruments and do not make raw scientific scores cross-Challenge comparable.

---

# 20. v1 invariants

1. **Only a verified frontier advance creates the Challenge's miner reward event.**
2. **Remaining incumbent creates no automatic reward.**
3. **Reward-enabled Challenges receive equal logical base slots.**
4. **Only scientifically qualified reward-enabled Challenges count in `N`.**
5. **Every Challenge launches from a registered frontier baseline.**
6. **Leader replacement uses a common fresh promotion exam, not stored scores from unrelated draws.**
7. **A frontier advance is a scientific superiority decision, not `score_new > score_old`.**
8. **At most one paid frontier event exists per Challenge per settlement window.**
9. **No frontier event means the Challenge slot is withheld, not redistributed by Carbon's abstract policy.**
10. **v1 has no carry-forward jackpot.**
11. **Exact duplicate method identity cannot generate a new event.**
12. **Same miner may advance the frontier with a genuinely new superior method.**
13. **Scientific version changes are prospective and may reset frontier lineage.**
14. **A material Challenge defect freezes frontier settlement.**
15. **Bittensor settlement mechanics are an adapter problem and may not rewrite scientific/economic intent.**

---

# 21. Final statement

> **Carbon's base subnet incentive is a portfolio of equal scientific Challenge opportunities, each paying only when independent evidence establishes a new frontier.**

This v1 is the owner-recommended leader replacement and settlement architecture for review.
