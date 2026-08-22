# Emissions Mapping Gauntlet — Preserve the Scientific Signal

**Branch:** `design/symbolic-numeric-integration`  
**Status:** executed architecture pilot; no Bittensor economic policy change.  
**Purpose:** Test whether plausible score-to-emissions transforms preserve scientific meaning or amplify differences beyond what the evidence supports.

---

# 1. Core separation

Carbon's scientific and economic layers remain distinct:

```text
qualified evidence
    ↓
Score Pack / ScoreEngine
    ↓
scientific ScoreResult
    ↓
Economic / Emissions Mapping
    ↓
Bittensor weights
```

The emissions layer may change incentives. It must not retroactively change what the scientific score means.

---

# 2. Pilot scores

The integrated Burgers objective gauntlet produced three non-zero illustrative scores:

```text
generator_oracle       0.973314
physical_truth_oracle  0.930064
smoothed_generator     0.711155
```

These scores are **not production-authoritative** because the Burgers generator is not yet qualified in the difficult low-viscosity region. They are used here only to test mapping behavior.

---

# 3. Mapping comparison

| Mapping | Generator oracle | Physical truth oracle | Smoothed |
|---|---:|---:|---:|
| proportional / linear | 0.3723 | 0.3557 | 0.2720 |
| softmax T=2 | 0.3986 | 0.3655 | 0.2359 |
| softmax T=5 | 0.4819 | 0.3882 | 0.1299 |
| softmax T=20 | 0.7011 | 0.2952 | 0.0037 |
| rank-linear | 0.5000 | 0.3333 | 0.1667 |
| winner-take-all | 1.0000 | 0.0000 | 0.0000 |

## Finding

High-temperature softmax, rank-only mapping, and winner-take-all can substantially amplify a score difference whose scientific significance has not been established.

The issue is not that concentration is always wrong. The issue is:

> **Economic concentration must not imply scientific certainty that the evidence does not support.**

---

# 4. Near-tie stress test

Illustrative scores:

```text
A = 0.841
B = 0.839
C = 0.800
```

A and B differ by only 0.002.

| Mapping | A | B | C |
|---|---:|---:|---:|
| softmax T=2 | 0.3428 | 0.3414 | 0.3158 |
| softmax T=5 | 0.3565 | 0.3530 | 0.2905 |
| softmax T=20 | 0.4165 | 0.4001 | 0.1834 |
| softmax T=100 | 0.5449 | 0.4461 | 0.0090 |

The A/B scientific difference remains 0.002, but aggressive temperature increasingly turns it into a large economic advantage.

### Required principle

> **The economic mapping should be no sharper than the scientific resolution the registered evaluation can defend.**

This does not require probabilistic ranking. It requires that the mapping policy know when the score layer has not established a meaningful separation.

---

# 5. Recommended v1 emissions invariants

These are architecture recommendations for later economic-layer review, not current runtime changes.

## E1 — only `VALID_RANKED` candidates receive scientific-performance emissions

Do not map:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
```

into ordinary positive scientific-performance weights by silently treating them as low scalar scores.

Their retry/refund/economic treatment belongs to the appropriate protocol layer.

## E2 — if no candidate is scientifically admissible, emit no fictitious scientific winner

The economic layer must support the state:

> **No submitted method earned scientific-performance emissions for this evaluation window.**

Fallback network economics, if required by Bittensor mechanics, should be explicitly non-scientific and separately labeled.

## E3 — mapping is monotone in scientific rank

For candidates within the same exact Challenge/Score Pack identity, a scientifically worse score must not receive greater scientific-performance emissions absent a separately declared economic policy.

## E4 — no raw cross-Challenge score pooling

A score of 0.9 on Challenge A and 0.9 on Challenge B is not a shared physical unit.

Challenge allocation is a separate governance/economic decision.

## E5 — uncertainty/equivalence can limit economic sharpness

If a registered Score Pack declares candidates scientifically equivalent or indeterminate, the emissions layer should not manufacture a large deterministic economic distinction from an arbitrary tie-break.

## E6 — submission frequency must not multiply scientific evidence

Repeated submissions/evaluations should not gain emissions merely by producing more correlated draws. Identity, cooldown, epoch, and decontamination policy must govern this separately.

## E7 — economic transforms never rewrite ExperimentRecord

Decay, temperature, winner bonuses, challenge allocation, or other incentives are downstream transformations. The original scientific score/evidence remains immutable.

---

# 6. Preferred initial posture

For early P0/testnet, prefer a conservative, auditable mapping over a highly concentrated one.

A reasonable design direction is:

```text
scientific admissibility
        ↓
within-Challenge score ordering
        ↓
optional equivalence / resolution grouping
        ↓
moderately monotone allocation
        ↓
separate challenge-level budget allocation
```

Do not choose the final transform until the qualified Burgers campaign reveals the empirical score distribution, variance, rank stability, and rate of admissible candidates.

---

# 7. What must be measured before production economics

The first qualified Challenge should estimate:

- fraction of submissions that are scientifically admissible;
- score distribution among admissible miners;
- repeat/eval variance;
- reconstruction variance;
- probability of rank reversal under fresh draws;
- typical gap between adjacent miners;
- frequency of scientific equivalence/indeterminate states;
- effect of economic mapping on miner reward concentration;
- susceptibility to submission spam or repeated correlated attempts.

Only then should Carbon calibrate mapping sharpness.

---

# 8. Verdict

The Score Pack → ScoreResult separation remains correct.

The emissions gauntlet adds one important doctrine:

> **Reward concentration is an economic choice constrained by scientific resolution, not evidence of scientific certainty.**

The next economic implementation should therefore consume explicit result state + rank/equivalence information, not merely a naked scalar.
