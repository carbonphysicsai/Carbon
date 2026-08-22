# Review These Preliminary Decisions — Score Pack Architecture

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject.  
**Purpose:** Distill the Score Pack gauntlet into a compact review queue.  
**Current authority preserved:** `Design_Specs/Scoring.md` remains sole current P0 scoring authority until accepted changes are migrated intentionally.

---

# Executive disposition

The gauntlet supports preserving the current P0 ScoreEngine boundary while broadening the long-term Score Pack concept.

Master recommendation:

> **Treat Score Pack as a versioned Evidence Use Contract. Keep ScoreEngine small, deterministic, closed, and scientifically non-authoring.**

Review model:

```text
Q1  ACCEPT / MODIFY / REJECT
...
Q16 ACCEPT / MODIFY / REJECT
```

---

# Q1 — Ratify Score Pack as an Evidence Use Contract

### Preliminary decision: ACCEPT

The Score Pack should define how already-qualified evidence becomes admissibility and ranking. It should not qualify physics, generators, references or measurements.

**Confidence:** Very high.

---

# Q2 — Admissibility precedes ranking

### Preliminary decision: ACCEPT

Mandatory physical/scientific requirements are evaluated before continuous ranking.

> **Mandatory failure cannot be compensated by strong soft performance elsewhere.**

This preserves `physics > loss` as a constitutional rule rather than merely a weight choice.

**Confidence:** Very high.

---

# Q3 — Introduce future `EvidenceEligibilityPolicy`

### Preliminary decision: ACCEPT CONCEPTUALLY

Evidence states such as eligible, non-applicable, missing required, reference unavailable, infra failure, censored and invalid evidence must remain distinct.

ScoreEngine must not silently drop or reinterpret them.

**Confidence:** Very high.

---

# Q4 — Introduce future `AdmissibilityPolicy`

### Preliminary decision: ACCEPT CONCEPTUALLY

A future pack should be able to bind qualified MeasurementContract outputs to mandatory predicates, thresholds, scopes, strata and applicability rules.

Current P0 binary gates are the first narrow implementation.

**Confidence:** Very high.

---

# Q5 — Make score-bearing estimands explicit

### Preliminary decision: ACCEPT

Every objective should identify what quantity it intends to rank: expected target-population error, failure probability, tail risk, worst-stratum behavior, consequence-weighted performance, answerability/coverage, reproducibility, etc.

A scalar metric name is insufficient scientific meaning.

**Confidence:** Very high.

---

# Q6 — Preserve P(x), Q(x), w(x) separation in scoring

### Preliminary decision: ACCEPT

Target population, finite sampling/proposal distribution, and score/evidence weighting are different semantics.

Oversampled stress cases must not silently become claims about workload frequency.

**Confidence:** Very high.

---

# Q7 — Add explicit stratum policy capability

### Preliminary decision: ACCEPT

Future packs should support mandatory per-stratum gates, minimum stratum evidence, weakest-stratum pressure, registered aggregate weighting, and under-sampled-stratum behavior where scientifically required.

**Confidence:** Very high.

---

# Q8 — Add Challenge-specific uncertainty/ranking policy capability

### Preliminary decision: ACCEPT WITH CARE

Carbon should preserve the distinction between numerical score difference and scientific distinguishability.

Future policy may support repeats, uncertainty reporting, equivalence/indeterminate states, qualified conservative bounds, or minimum meaningful separation where justified.

No universal confidence rule is ratified.

**Confidence:** High.

---

# Q9 — Reconstruction variability may become score-relevant evidence

### Preliminary decision: ACCEPT CONCEPTUALLY

When Carbon claims method-level reproducibility, variability across independent reconstructions may require repeats or a reproducibility estimand/gate.

This is distinct from evaluation-instance variance.

**Confidence:** High.

---

# Q10 — Keep scientific performance, compute, information value, commercial utility and economics distinct

### Preliminary decision: ACCEPT

Resource compliance may be a separate admissibility/objective when registered. Novelty/information value should use separate bounties/research mechanisms. Product utility belongs to qualification. Emissions mapping is downstream of scientific score.

**Confidence:** Very high.

---

# Q11 — Keep model-family neutrality in score semantics

### Preliminary decision: ACCEPT

Score-bearing evidence must be available through the common CandidateOutputContract or required equally from all admissible families.

No neural/symbolic/mechanistic/ROM/hybrid internal property receives automatic score privilege.

**Confidence:** Very high.

---

# Q12 — Material upstream changes can invalidate score compatibility

### Preliminary decision: ACCEPT

A distribution, SamplingPlan, MeasurementContract, reference-policy or representation change may change score meaning even if numeric thresholds/formulas remain identical.

Compatibility must be explicit and versioned.

**Confidence:** Very high.

---

# Q13 — Cross-Challenge scalar scores are not automatically comparable

### Preliminary decision: ACCEPT

`0.85` on two different Challenges is not a universal unit of physical competence. Cross-Challenge allocation is a separate governance/economic problem unless explicit calibration earns comparability.

**Confidence:** Very high.

---

# Q14 — Internal ScoreResult and public disclosure are separate contracts

### Preliminary decision: ACCEPT

Rich internal evidence may be retained while miner-facing disclosure remains allow-listed and evaluation-information-budgeted.

Score Pack transparency does not imply hidden exam disclosure.

**Confidence:** Very high.

---

# Q15 — Scalar subnet ranking must preserve richer evidence

### Preliminary decision: ACCEPT

The subnet may require a scalar rank for emissions, but ExperimentRecord should retain the full admissibility, objective, strata, uncertainty, failure and provenance evidence needed by Landscape and qualification.

**Confidence:** Very high.

---

# Q16 — Keep ScoreEngine scientifically non-authoring

### Preliminary decision: ACCEPT

ScoreEngine should load an exact registered pack, consume authorized evidence, deterministically evaluate eligibility/admissibility/transforms/aggregation/ranking, and return a result.

It must not parse physical semantics to invent metrics, infer thresholds, choose weights, repair missing science, alter distributions, or make product claims.

**Confidence:** Very high.

---

# Consolidated review table

| ID | Decision | Preliminary verdict | Confidence |
|---|---|---|---:|
| Q1 | Score Pack = Evidence Use Contract | ACCEPT | Very high |
| Q2 | admissibility before ranking | ACCEPT | Very high |
| Q3 | EvidenceEligibilityPolicy | ACCEPT CONCEPT | Very high |
| Q4 | AdmissibilityPolicy | ACCEPT CONCEPT | Very high |
| Q5 | explicit estimands | ACCEPT | Very high |
| Q6 | P/Q/w separation | ACCEPT | Very high |
| Q7 | stratum policy | ACCEPT | Very high |
| Q8 | uncertainty/ranking policy | ACCEPT WITH CARE | High |
| Q9 | reconstruction variability | ACCEPT CONCEPT | High |
| Q10 | keep value layers distinct | ACCEPT | Very high |
| Q11 | model-family-neutral scoring | ACCEPT | Very high |
| Q12 | upstream compatibility/versioning | ACCEPT | Very high |
| Q13 | no automatic cross-Challenge comparability | ACCEPT | Very high |
| Q14 | internal result != disclosure | ACCEPT | Very high |
| Q15 | preserve richer evidence | ACCEPT | Very high |
| Q16 | ScoreEngine non-authoring | ACCEPT | Very high |

---

# Explicitly not decided here

This review does **not** change or ratify:

- current P0 45/30/25 weights;
- current hard-gate thresholds;
- current schema `1.0` runtime JSON shape;
- current `python_binary64_v1` profile;
- exact future uncertainty method;
- exact tie/equivalence rule;
- exact future aggregation operator;
- exact stratum syntax;
- exact SamplingPlan weighting implementation;
- economic score-to-emissions transform;
- product qualification acceptance policy;
- cross-Challenge allocation mechanism.

---

# Owner preliminary conclusion

> **The current A5 ScoreEngine boundary is fundamentally sound. The long-term evolution belongs primarily in the semantics of what the Score Pack is allowed to bind—not in making the engine smarter.**

If Q1–Q16 are accepted, the next step is a targeted reconciliation of `Scoring.md` that preserves schema-1.0 P0 behavior while documenting the future Evidence Use Contract architecture and identifying only the cheap compatibility hooks worth preserving now.
