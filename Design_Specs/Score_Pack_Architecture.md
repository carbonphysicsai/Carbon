# Carbon Score Pack Architecture — Evidence Use, Admissibility, and Ranking

**Status:** DESIGN INTEGRATION DRAFT — no current P0 runtime change.  
**Purpose:** Define a durable, model-family-neutral Score Pack architecture that consumes already-qualified evidence and deterministically converts it into scientific admissibility and subnet ranking.  
**Current authority:** `Scoring.md` remains sole current P0 scoring authority. This document is a future architecture candidate derived from `docs/context/SCORE_PACK_GAUNTLET_SIMULATION.md`.

---

# 1. Core rule

> **A Score Pack is a versioned Evidence Use Contract.**

It states:

- what qualified evidence is eligible;
- which conditions make a candidate scientifically inadmissible;
- what estimands are being ranked;
- which physical populations those estimands refer to;
- how strata, missingness, reference status and uncertainty are handled;
- how admissible evidence is transformed and aggregated;
- how deterministic rank is produced;
- what internal score information may be eligible for later disclosure.

The Score Pack does **not** qualify physics, generators, references or measurements. Those authorities sit upstream.

The ScoreEngine does not make scientific judgments:

> **The engine executes registered evidence-use decisions. It does not author them.**

---

# 2. Authority chain

```text
PhysicalSystemSpec
CandidateOutputContract
Claim / Envelope
InstanceDistributionContract
SamplingPlan
ChallengeInstanceGenerator
ReferencePolicy
MeasurementContracts
Validation Dossier
        ↓
     Score Pack
        ↓
    ScoreEngine
        ↓
    ScoreResult
        ↓
Ranking / downstream economic mapping
```

No Score Pack may repair or infer missing upstream scientific qualification.

---

# 3. Architectural decomposition

A future Score Pack should conceptually separate:

```text
ScorePack
  ├─ IdentityPins
  ├─ EvidenceEligibilityPolicy
  ├─ AdmissibilityPolicy
  ├─ EstimandBindings
  ├─ MeasurementUseBindings
  ├─ UncertaintyPolicy
  ├─ StratumPolicy
  ├─ AggregationPolicy
  ├─ RankingPolicy
  └─ DisclosurePolicyRef
```

These may compile to a simpler runtime schema. They are separate semantic responsibilities even when encoded compactly.

---

# 4. Identity pins

A score only has meaning when bound to the exact scientific exam identity.

Future score identity should be capable of binding, directly or through the Challenge Registry:

```text
challenge identity/version
PhysicalSystemSpec identity/digest where present
claim/envelope identity
distribution identity/version
authorized SamplingPlan identity/version
generator identity/version/digest
reference policy identity/version
MeasurementContract identities/versions
Validation Dossier identity/version/digest
Score Pack version/digest
numerical profile
```

P0 may continue using its current narrower exact pin until an explicit migration.

---

# 5. Evidence eligibility

Before admissibility or ranking, evidence must be eligible.

Conceptual states include:

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

The Score Pack defines how registered evidence states affect the score path; the ScoreEngine never silently drops invalid or missing evidence.

Reference failure and infrastructure failure are not scientific candidate failure.

---

# 6. Admissibility policy

Admissibility is logically above continuous ranking.

A future policy may bind qualified measurements to mandatory predicates:

```text
AdmissibilityRule {
  id
  measurement_contract_ref
  estimand_ref
  predicate
  threshold / qualified bound
  scope
  strata
  applicability_policy
  evidence_failure_policy
}
```

### Constitutional rule

> **Mandatory physical failure cannot be compensated by soft performance elsewhere.**

`physics > loss` therefore means more than a large physics weight: required physical behavior is a condition of admissibility.

---

# 7. Estimand bindings

A scalar measurement is not enough to define scientific meaning.

Each score-bearing objective should identify the estimand being ranked, for example:

```text
expected target-population error
physical-failure probability
stress-population tail risk
worst-stratum margin
consequence-weighted performance
answerability / coverage
reconstruction reproducibility
```

Conceptually:

```text
EstimandBinding {
  id
  population_ref
  sampling_plan_ref
  measurement_contract_ref
  eligible_population
  aggregation_semantics
  uncertainty_semantics
}
```

This prevents raw evaluation frequency under `Q(x)` from being mistaken for the scientific target under `P(x)`.

---

# 8. Population / sampling / weighting rule

The Score Pack must preserve:

```text
P(x) = target population
Q(x) = proposal / finite sampling distribution
w(x) = evidence weighting / scientific importance
```

These are not automatically equal.

If stress cases are oversampled, the pack must explicitly choose one of the qualified interpretations: separate stress reporting/gating, importance weighting where justified, consequence weighting, or another registered estimand.

> **Sample prevalence is not score importance.**

---

# 9. Measurement-use bindings

A MeasurementContract may be scientifically qualified but not necessarily score-bearing.

The Score Pack explicitly promotes selected qualified measurements into one or more roles:

```text
mandatory admissibility
soft ranking objective
diagnostic only
ranking uncertainty support
```

A metric cannot become score-bearing merely because the generator or physical semantic layer exposes it.

---

# 10. Measurement applicability and missingness

Non-applicable is not the same as pass, fail, or missing.

For every score-bearing measurement, the pack defines:

- applicability semantics;
- eligible population;
- treatment of non-applicable cases;
- treatment of missing required evidence;
- treatment of candidate-invalid output;
- treatment of reference failure;
- treatment of infrastructure failure;
- treatment of censoring.

Applicability should be independently determined where possible.

---

# 11. Stratum policy

Global averages cannot erase mandatory failure in scientifically material subpopulations.

A future `StratumPolicy` may define:

- required strata;
- minimum evidence per stratum;
- stratum-level mandatory gates;
- weakest-stratum pressure;
- aggregate weighting;
- stratum-specific uncertainty requirements;
- behavior when a required stratum is under-sampled.

No universal stratum rule is implied.

---

# 12. Uncertainty policy

Carbon must distinguish deterministic scoring implementation from uncertainty in the underlying evidence.

Potential sources:

- finite evaluation sample;
- stochastic reconstruction;
- stochastic candidate behavior;
- measurement uncertainty;
- reference uncertainty;
- population uncertainty.

A future Score Pack may define a Challenge-specific policy for:

- reconstruction repeats;
- evaluation repeats;
- point-estimate semantics;
- lower/upper-bound semantics where qualified;
- equivalence / indeterminate bands;
- minimum meaningful separation;
- treatment of unresolved uncertainty.

No universal confidence threshold is assumed.

### Key distinction

> **Numerically ordered does not always mean scientifically distinguishable.**

The subnet may still require a deterministic ranking; if so, the scientific record should preserve the uncertainty rather than pretend the scalar is exact truth.

---

# 13. Aggregation policy

Aggregation occurs only among admissible candidates.

A future policy may specify:

```text
component transforms
within-objective aggregation
cross-objective aggregation
weights
zero semantics
floor/ceiling behavior
monotonicity requirements
```

Aggregation is a protocol hypothesis, not a universal scientific law.

Current P0 weighted-geometric log-space aggregation remains a valid narrow profile but not a mandatory terminal architecture.

Soft transforms must not accidentally create undeclared hard gates.

---

# 14. Ranking policy

Ranking semantics are distinct from score calculation.

A future policy may define:

- primary ordering scalar or tuple;
- tie behavior;
- equivalence/indeterminate behavior;
- deterministic non-scientific tie-break procedure;
- treatment of candidates with insufficient evidence;
- repeat/re-evaluation rules where allowed.

Tie-break mechanics do not add scientific evidence.

---

# 15. Candidate/result state model

Carbon should distinguish at least:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
VALID_RANKED
INDETERMINATE_EVIDENCE
```

A scientific zero is evidence. Protocol invalidity and infrastructure failure are not the same thing.

---

# 16. Scientific score vs computational admissibility

A Challenge may require runtime/memory/query limits, but these should be prospectively defined as either:

- construction/execution eligibility;
- computational admissibility;
- a separately identified efficiency objective.

Do not silently fold computational cost into physical fidelity.

Scientific performance, resource efficiency, information value, and commercial utility remain distinct.

---

# 17. Model-family neutrality

Score-bearing evidence should be observable through the common CandidateOutputContract or required equally from every admissible family.

Internal neural, symbolic, mechanistic, ROM, hybrid or solver-specific properties receive no automatic score privilege.

> **Model class is a hypothesis. Registered external evidence is the judge.**

---

# 18. Reconstruction variability

For strategies whose independently reconstructed artifacts vary materially, the Score Pack may bind evidence about reproducibility or multiple reconstructions.

Reconstruction variance is distinct from variation across evaluation cases.

A lucky reconstruction should not automatically establish method quality if the Challenge claims method-level reproducibility.

---

# 19. Reference and measurement uncertainty

The Score Pack references qualified measurement outputs and uncertainty semantics; it does not invent how solver disagreement, experimental noise, discretization error, or reference floors should affect evidence.

If two candidate errors are below qualified truth/measurement resolution, the score should not imply more scientific precision than the evidence supports.

---

# 20. Censoring

The Score Pack must not silently aggregate over whichever cases happened to return valid evidence.

The intended and realized evidence populations remain distinct. Required policy handles:

- reference failure;
- generator failure;
- infra failure;
- candidate timeout;
- measurement non-applicability;
- invalid outputs;
- under-filled strata.

Censoring rules are registered prospectively.

---

# 21. Score Pack versioning

Material score-semantic changes require a new Score Pack/scoring version, including changes to:

- mandatory predicates/thresholds;
- measurement identity;
- estimand definition;
- population compatibility;
- uncertainty policy;
- strata policy;
- transforms;
- weights;
- aggregation;
- ranking semantics.

New versions apply prospectively. Historical scores are never silently reinterpreted.

---

# 22. Upstream-version compatibility

A changed distribution, SamplingPlan, MeasurementContract or reference policy may change score meaning even if Score Pack formula bytes are unchanged.

Therefore the registry/pack compatibility layer must bind the exact upstream identities the score is authorized to consume.

A new measurement implementation with the same human-readable name is not automatically compatible.

---

# 23. Cross-Challenge comparability

A scalar score is Challenge-bound scientific evidence.

```text
0.85 on Challenge A
!= automatically
0.85 on Challenge B
```

Cross-Challenge emissions allocation, challenge weighting, or portfolio economics are separate governance/economic problems unless explicit calibration earns comparability.

Raw scalar score must not masquerade as a universal unit of physical competence.

---

# 24. Score evidence vs economic mapping

Preferred separation:

```text
ScoreResult
    ↓
Economic / Emissions Mapping
    ↓
Bittensor weights
```

Winner decay, challenge allocation, participation policy, bounties, and other economic transforms must not rewrite the scientific record.

---

# 25. Performance vs information value

Novelty, scientific information value, causal identification, and uncertainty reduction are not primary performance-score terms by default.

If Carbon funds informative experiments, use a separate registered bounty/research mechanism so the performance score remains interpretable.

---

# 26. Search vs product qualification

A lean Score Pack answers:

> Which submitted methods survive this registered search exam and rank best under its objective?

It does not answer:

> Is this exact artifact/system qualified for a specific engineering job?

Product qualification uses distinct job-shaped evidence and acceptance semantics.

> **Rank nominates. Evidence qualifies.**

---

# 27. Disclosure separation

The internal ScoreResult may contain more evidence than miners should receive.

Score Pack transparency does not require disclosure of hidden realizations or rich diagnostic vectors.

Miner/public disclosure remains governed by a separately budgeted allow-list / Evaluation Information Budget.

---

# 28. Numerical execution profile

The ScoreEngine remains deterministic, closed-schema, bounded, and versioned.

Current `python_binary64_v1` illustrates the correct principle: implementation reproducibility is explicit.

Scientific uncertainty should enter as authorized evidence semantics, not validator floating-point disagreement.

---

# 29. Current P0 as a narrow instance

The existing P0 architecture maps cleanly:

```text
EvidenceEligibilityPolicy
  closed validator-authorized ScoreInput

AdmissibilityPolicy
  mandatory binary hard gates

Estimands / objectives
  physics fidelity
  robustness
  predictive accuracy

AggregationPolicy
  fixed leg transforms
  pack-bound 0.45 / 0.30 / 0.25
  weighted-geometric log-space aggregate

RankingPolicy
  deterministic scalar ranking
```

This future architecture does not change current `Scoring.md` until an explicit reviewed schema migration.

---

# 30. Proposed constitutional invariants

1. **Admissibility precedes ranking.**
2. **Mandatory physical failure cannot be compensated by soft objectives.**
3. **Score Pack is an evidence-use contract, not a scientific-truth generator.**
4. **Only qualified measurements may become score-bearing.**
5. **Population, SamplingPlan, MeasurementContract, Validation Dossier and Score Pack identities jointly define score meaning.**
6. **Target prevalence, sample prevalence and score importance are separate.**
7. **Non-applicable, missing, reference-failed, infra-failed, censored and candidate-failed evidence are distinct states.**
8. **Finite evidence may be insufficient to scientifically distinguish numerically different candidates.**
9. **Mandatory stratum failure cannot be averaged away when the registered Challenge declares it mandatory.**
10. **Model-family internals receive no automatic score privilege.**
11. **Scientific performance, computational admissibility, information value, commercial utility and economic mapping remain distinct.**
12. **Material score-semantic changes are versioned and prospective.**
13. **Internal ScoreResult and public disclosure are separate contracts.**
14. **Cross-Challenge scores are not automatically comparable.**
15. **Scalar ranking does not erase the richer ExperimentRecord.**
16. **ScoreEngine executes science; it does not invent science.**

---

# 31. Final design statement

> **Carbon's Score Pack is the prospective contract that states how already-qualified evidence may become scientific admissibility and deterministic rank.**

The ScoreEngine should do nothing more—and nothing less—than execute that contract faithfully.
