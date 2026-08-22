# Review These Preliminary Decisions — Integrated Incentive System

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions after executed Burgers + emissions gauntlets.  
**Related:** `INTEGRATED_BURGERS_INCENTIVE_GAUNTLET.md`, `EMISSIONS_MAPPING_GAUNTLET.md`, `Score_Pack_Architecture_v1.md`.

---

# Executive disposition

The integrated pilot supports the architecture but blocks any claim that the current Burgers implementation is already an authoritative scientific market.

The key finding is that the score can prefer an exact match to an under-qualified generator over an independently verified physical truth solution. That must be impossible in a production-qualified Challenge within the scientific resolution claimed by the exam.

Review model:

```text
I1 ACCEPT / MODIFY / REJECT
...
I10 ACCEPT / MODIFY / REJECT
```

---

# I1 — Add an integrated truth-dominance stop-ship test

### Preliminary decision: ACCEPT

Before LIVE, construct one or more independent truth/reference candidates and verify that the official evidence path does not systematically reward generator-specific numerical error over qualified physical truth.

Preferred rule:

> **Within the qualified resolution of the exam, disagreement with generator error must not be rewarded over agreement with qualified physical truth.**

Confidence: **Very high**.

---

# I2 — Current Burgers low-viscosity region requires requalification

### Preliminary decision: ACCEPT

The executed pilot found material generator/Cole-Hopf disagreement at `nx=128`, `T=0.5` near `ν≈1e-3` and below.

Do not lower score thresholds to hide this. Qualify by resolution/envelope study first.

Confidence: **Very high** for the tested cases; exact production boundary still requires systematic campaign.

---

# I3 — Current final-time spatial residual proxy is not sufficient as a full PDE-residual claim

### Preliminary decision: ACCEPT

The existing proxy `|u u_x - ν u_xx|` omits `u_t` and therefore is not the full Burgers PDE residual.

It may remain diagnostic. Score-bearing use requires a qualified MeasurementContract and accurate naming.

Confidence: **Very high**.

---

# I4 — Require a non-degenerate admissible miner population before emissions calibration

### Preliminary decision: ACCEPT

P0 must demonstrate that realistic strategies under the registered budget produce multiple scientifically admissible candidates with meaningful score spread.

If all plausible candidates fail, there is no useful scientific ranking market to monetize.

Confidence: **Very high**.

---

# I5 — Rank stability across fresh draws is a launch requirement

### Preliminary decision: ACCEPT

For deliberately distinct strategies, estimate rank-reversal frequency across fresh evaluation/stress draws and, where relevant, independent reconstructions.

A single deterministic score execution is not sufficient evidence that the market ranks methods reliably.

Confidence: **Very high**.

---

# I6 — Economic mapping consumes result state, not only scalar score

### Preliminary decision: ACCEPT

The emissions layer should distinguish at least:

```text
VALID_RANKED
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
FAILED_INFRA
REJECTED_INVALID
```

Do not silently map every non-success state to scalar zero and treat it as equivalent scientific evidence.

Confidence: **Very high**.

---

# I7 — No scientifically admissible candidate means no fictitious scientific winner

### Preliminary decision: ACCEPT

If an evaluation window contains no scientifically admissible candidate, the protocol should represent that state explicitly.

Any required fallback Bittensor/economic behavior must be labeled as economic/protocol fallback, not scientific victory.

Confidence: **Very high**.

---

# I8 — Economic sharpness is constrained by scientific resolution

### Preliminary decision: ACCEPT

Aggressive softmax/winner-take-all transforms can convert tiny score gaps into large emission gaps.

Mapping sharpness should be calibrated after measuring score variance, rank stability, and meaningful separation under a qualified Challenge.

Confidence: **High**; exact transform remains empirical/economic.

---

# I9 — Cross-Challenge allocation remains separate

### Preliminary decision: ACCEPT

Do not pool raw Challenge scalar scores into one economic scale. Challenge budget/allocation requires a separately justified mechanism.

Confidence: **Very high**.

---

# I10 — Integrated Challenge qualification precedes document-level empirical claims

### Preliminary decision: ACCEPT

The Canon/WP/LP/deck may describe the architecture now, but any claim that Carbon has empirically demonstrated correct miner incentives should wait until the qualified Burgers campaign passes:

```text
truth qualification
→ measurement qualification
→ admissible strategy population
→ adversarial metric test
→ validator agreement
→ rank stability
→ emissions-preservation test
```

Confidence: **Very high**.

---

# Owner conclusion

> **The architecture has reached the point where failure is being detected at the correct layer. The remaining job is to qualify the first Challenge and demonstrate that the complete market, not merely the formulas, selects better construction strategies reproducibly.**
