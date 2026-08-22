# Carbon Score Pack Architecture v1

**Status:** OWNER-RECOMMENDED v1 — ready for tech/science-lead review and modification.  
**Branch:** `design/symbolic-numeric-integration`  
**Current runtime authority:** `Design_Specs/Scoring.md` remains the sole current P0 scoring authority until a reviewed migration explicitly changes it.  
**Basis:** `SCORE_PACK_GAUNTLET_SIMULATION.md`, `Score_Pack_Architecture.md`, the Challenge distribution architecture, and Validation Dossier v2.

---

# 1. v1 decision

> **A Score Pack is a versioned Evidence Use Contract.**

It governs how already-qualified evidence becomes:

1. evidence eligibility;
2. scientific admissibility;
3. score-bearing estimands;
4. soft objective values;
5. deterministic ranking;
6. a bounded internal `ScoreResult` suitable for downstream emissions mapping.

The Score Pack does **not** qualify the physical system, target population, SamplingPlan, generator, reference source, representation adapter, or MeasurementContract. Those authorities are upstream and must be bound by identity.

The ScoreEngine remains intentionally non-authoring:

> **The engine executes registered scientific decisions. It does not make them.**

---

# 2. Authority chain

```text
PhysicalSystemSpec
+ CandidateOutputContract
+ Claim / Envelope
+ InstanceDistributionContract
+ SamplingPlan
+ ChallengeInstanceGenerator
+ ReferencePolicy
+ MeasurementContracts
        ↓
Validation Dossier
        ↓
Score Pack
        ↓
ScoreEngine
        ↓
ScoreResult
        ↓
Economic / Emissions Mapping
```

No layer may silently repair missing authority from the layer above it.

---

# 3. v1 semantic decomposition

The v1 architecture fixes these semantic responsibilities:

```text
ScorePack
  ├─ IdentityPins
  ├─ EvidenceEligibilityPolicy
  ├─ AdmissibilityPolicy
  ├─ EstimandBindings
  ├─ MeasurementUseBindings
  ├─ StratumPolicy
  ├─ UncertaintyPolicy
  ├─ AggregationPolicy
  ├─ RankingPolicy
  └─ DisclosurePolicyRef
```

They do not all need separate runtime classes. A future compiler may flatten them into a closed JSON artifact. The separation is conceptual and reviewable.

---

# 4. Identity pins are mandatory

A score is meaningful only under the exact exam identity that produced it.

A future generalized pack must be able to bind, directly or through the Challenge Registry:

```text
challenge identity/version
physical-system identity/digest
claim/envelope identity
distribution identity/version
SamplingPlan identity/version
generator identity/version/digest
reference-policy identity/version
representation-adapter identities where material
MeasurementContract identities/versions
Validation Dossier identity/version/digest
Score Pack identity/version/digest
numerical execution profile
```

If a material upstream object changes, score compatibility must be explicitly re-established. Numeric formula equality alone is insufficient.

---

# 5. Evidence eligibility comes first

Before a candidate can fail science or receive a score, Carbon determines whether the evidence is eligible for the registered score path.

v1 evidence states:

```text
ELIGIBLE
NOT_APPLICABLE
MISSING_REQUIRED
REFERENCE_UNAVAILABLE
REFERENCE_UNCERTAIN
INFRA_FAILURE
CENSORED
INVALID_EVIDENCE
```

The policy for each state is prospective and Challenge-specific.

Constitutional rules:

- reference failure is not candidate failure;
- infrastructure failure is not candidate failure;
- non-applicable is not pass, fail, or missing;
- required missing evidence never disappears silently;
- censoring never silently changes the realized exam population.

---

# 6. Admissibility precedes ranking

This is the core interpretation of `physics > loss`.

```text
eligible evidence
      ↓
mandatory scientific predicates
      ↓
PASS? ── no ──> SCIENTIFIC_INADMISSIBLE
  │
 yes
  ↓
continuous ranking objectives
```

> **Mandatory physical/scientific failure cannot be compensated by accuracy or another soft objective.**

A mandatory rule may be scoped by:

- measurement identity;
- estimand;
- threshold or qualified bound;
- physical stratum;
- applicability condition;
- evidence-failure policy.

Current P0 binary hard gates are the first narrow implementation of this doctrine.

---

# 7. Estimands are explicit

A metric name is not enough. Every score-bearing objective must state what scientific quantity it intends to rank.

Examples:

```text
expected error under target population
probability of mandatory physical failure
stress-population tail risk
worst-stratum margin
consequence-weighted performance
answerability / coverage
reconstruction reproducibility
```

An estimand binds at least:

```text
population identity
SamplingPlan identity
MeasurementContract identity
eligible population
aggregation semantics
uncertainty semantics
```

This prevents a sample average under the proposal distribution from being mistaken for a target-population statement.

---

# 8. P(x), Q(x), and w(x) remain distinct

```text
P(x)  target population
Q(x)  finite proposal / sampling distribution
w(x)  score/evidence weighting semantics
```

They may coincide for a simple P0 Challenge. They are not universally equal.

If rare stress cases are deliberately oversampled, the Score Pack must prospectively specify one of the qualified interpretations, for example:

- separate stress gate/report;
- importance-weighted estimand;
- consequence-weighted objective;
- nominal ranking plus mandatory stress admissibility.

> **Sampling prevalence is not real-world prevalence and is not automatically score importance.**

---

# 9. Measurement use is explicit

A qualified MeasurementContract can be used in one or more roles:

```text
MANDATORY_ADMISSIBILITY
SOFT_RANKING_OBJECTIVE
DIAGNOSTIC_ONLY
UNCERTAINTY_SUPPORT
```

No metric becomes score-bearing merely because it exists in the evaluator or PhysicalSystemSpec.

Measurement applicability and eligible population must be explicit.

---

# 10. Stratum policy

Where scientifically material, v1 supports explicit strata/hierarchies.

A Challenge may require:

- minimum evidence per stratum;
- mandatory gates per stratum;
- weakest-stratum pressure;
- registered aggregate weights;
- stratum-specific uncertainty requirements;
- fail-closed behavior for under-filled required strata.

A global average may never erase a mandatory subgroup failure.

---

# 11. Uncertainty policy

The ScoreEngine is deterministic; the evidence may not be.

Relevant uncertainty can arise from:

- finite evaluation sampling;
- stochastic candidate behavior;
- stochastic reconstruction;
- reference uncertainty;
- measurement uncertainty;
- population uncertainty.

The v1 architecture allows a Challenge-specific policy for:

- evaluation repeats;
- reconstruction repeats;
- point-estimate semantics;
- qualified conservative bounds;
- equivalence / indeterminate states;
- minimum meaningful separation;
- unresolved uncertainty.

No universal confidence threshold is specified in v1.

> **Numerically ordered does not necessarily mean scientifically distinguishable.**

---

# 12. Aggregation policy

Aggregation occurs only after admissibility.

A pack may specify:

```text
component transforms
within-objective aggregation
cross-objective aggregation
weights
zero semantics
floors/ceilings
monotonicity requirements
```

v1 fixes these rules:

1. aggregation choice is a protocol hypothesis, not a law of physics;
2. soft transforms may not accidentally create an undeclared hard gate;
3. score transforms should be pack-bound and prospective;
4. current P0 weighted-geometric log-space aggregation remains a valid narrow profile.

The P0 0.45 / 0.30 / 0.25 weights remain a P0 pack decision, not a Carbon universal.

---

# 13. Ranking policy

Ranking is distinct from scientific score calculation.

A v1-compatible policy may define:

- primary scalar or ordered tuple;
- scientifically indeterminate/equivalent state where justified;
- repeat policy;
- deterministic non-scientific tie-break rule;
- handling of insufficient evidence.

Tie-break mechanics do not create new scientific evidence.

---

# 14. Result state model

At minimum Carbon distinguishes:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
VALID_RANKED
```

A scientific zero is an evidence-bearing scientific outcome. Invalidity and infrastructure failure are not scientific zeros.

---

# 15. Scientific performance and other values remain separate

Do not silently merge:

```text
scientific performance
computational/resource admissibility
information value / novelty
commercial utility
product qualification
economic/emissions mapping
```

A Challenge may register a compute requirement or efficiency objective, but its semantics must remain explicit.

Novelty/information value should use a separate research/bounty mechanism unless a future explicit design changes that rule.

Product qualification remains separate:

> **Rank nominates. Evidence qualifies.**

---

# 16. Model-family neutrality

Score-bearing requirements are defined through common candidate outputs and qualified external measurements.

No automatic score privilege is granted because a method is:

- neural;
- symbolic;
- mechanistic;
- reduced-order;
- hybrid;
- interpretable;
- novel.

> **Model class is a hypothesis. Registered external evidence is the judge.**

---

# 17. Reconstruction variability

If Carbon claims method quality rather than one lucky artifact, independent reconstruction variability may become evidence.

The architecture therefore permits:

- multiple reconstruction seeds;
- reconstruction dispersion;
- reconstruction-level failure probability;
- reproducibility gates or objectives.

This is distinct from variation across evaluation cases.

No mandatory repeat count is set in v1; it is Challenge-specific and dossier-qualified.

---

# 18. Censoring and truth failure

The Score Pack cannot silently score only the easy subset that returned valid evidence.

The policy must address:

- reference failure;
- generator failure;
- infrastructure failure;
- candidate timeout;
- invalid outputs;
- measurement non-applicability;
- under-filled strata.

The intended sampled population and realized valid-evidence population remain separately recorded.

---

# 19. Versioning

A new scoring version is required when scientific score semantics change materially, including changes to:

- mandatory predicates/thresholds;
- score-bearing measurement identity;
- estimand definition;
- population/SamplingPlan compatibility;
- strata policy;
- uncertainty policy;
- transforms;
- weights;
- aggregation;
- ranking semantics.

All such changes are prospective. Historical scores stay bound to their original exam identity.

---

# 20. Cross-Challenge comparability is rejected by default

```text
0.85 on Challenge A
!= automatically
0.85 on Challenge B
```

A ScoreResult is Challenge-bound scientific evidence.

Cross-Challenge emissions allocation, challenge weighting, or portfolio economics require their own explicit calibration/governance mechanism. Raw scalar score is not a universal unit of physics competence.

---

# 21. Disclosure is separate

The internal `ScoreResult` may retain substantially richer evidence than a miner-facing response.

Public/miner disclosure remains separately allow-listed and governed by the Evaluation Information Budget.

Transparent scoring semantics do not require disclosure of hidden cases, seeds, rich per-instance vectors, or exploitable diagnostics.

---

# 22. Rich evidence survives scalar ranking

Bittensor may require a scalar rank, but Carbon must preserve the richer scientific record:

```text
admissibility outcome
measurement/objective values
population + strata context
uncertainty
reference status
censoring/failure state
reconstruction provenance
exact identity pins
```

The scalar is an economic interface, not the complete scientific record.

---

# 23. ScoreEngine v1 boundary

The generalized ScoreEngine should only:

```text
load exact registered Score Pack
validate exact pins
consume authorized evidence
apply eligibility policy
apply admissibility policy
compute registered estimands/transforms
aggregate according to pack
apply deterministic ranking policy
return ScoreResult
```

It must not:

- parse PhysicalSystemSpec to invent metrics;
- infer thresholds;
- choose scientific weights;
- change populations;
- repair missing upstream evidence;
- decide product qualification;
- invent uncertainty treatment;
- perform cross-Challenge economic normalization.

---

# 24. P0 profile under v1

Current P0 remains a narrow compiled profile:

```text
EvidenceEligibilityPolicy
  closed validator-authorized scalar ScoreInput

AdmissibilityPolicy
  mandatory binary hard gates

Objectives
  physics fidelity
  robustness
  predictive accuracy

AggregationPolicy
  pack-bound transforms
  0.45 / 0.30 / 0.25
  weighted geometric, log-space

RankingPolicy
  deterministic scalar rank
```

No current schema-1.0 runtime change is implied by this architecture document.

---

# 25. v1 constitutional invariants

1. **Admissibility precedes ranking.**
2. **Mandatory physical failure cannot be compensated by soft performance.**
3. **Score Pack is an Evidence Use Contract, not a truth generator.**
4. **Only qualified measurements may become score-bearing.**
5. **Score meaning binds the exact population, SamplingPlan, measurement, dossier, and pack identity.**
6. **P(x), Q(x), and score weighting are distinct semantics.**
7. **Missing, non-applicable, reference-failed, infra-failed, censored, invalid, and scientific-failure states are distinct.**
8. **Mandatory stratum failure cannot be averaged away.**
9. **Finite evidence may be insufficient to scientifically distinguish numerically different candidates.**
10. **Model-family internals receive no automatic score privilege.**
11. **Scientific performance, compute, information value, commercial utility, product qualification, and economic mapping remain distinct.**
12. **Material score-semantic changes are versioned and prospective.**
13. **Cross-Challenge scores are not automatically comparable.**
14. **Internal ScoreResult and public disclosure are separate.**
15. **Scalar ranking does not erase the richer ExperimentRecord.**
16. **ScoreEngine executes science; it does not invent science.**

---

# 26. Tech/science-lead review boundary

This v1 intentionally leaves Challenge-specific science to the appropriate reviewers. The tech/science lead should review/edit rather than redesign from scratch:

- exact P0 gate thresholds;
- exact measurement definitions;
- exact sample/repeat counts;
- exact uncertainty/equivalence policy;
- exact stratum requirements;
- exact soft transforms and weights;
- exact product-independent compute constraints.

Those values become authoritative only through the Challenge/Dossier/Score Pack qualification path.

---

# 27. Final v1 statement

> **Carbon ranks only after it has qualified what evidence means, established which failures are disqualifying, bound the population and estimands being measured, and explicitly defined how admissible evidence may be aggregated.**

This is the owner-recommended Score Pack v1 architecture for tech/science-lead review.
