# Score Pack Gauntlet Simulation — Evidence-to-Ranking Architecture

**Branch:** `design/symbolic-numeric-integration`  
**Status:** design-forward simulation; no current P0 scoring/runtime change.  
**Purpose:** Stress-test Carbon's Score Pack architecture against the generalized physical-system, population, SamplingPlan, generator, reference, measurement, mixed-model, agentic, qualification, and lifecycle vision.  
**Current authority preserved:** `Design_Specs/Scoring.md` remains the sole current P0 scoring authority until an accepted architecture is explicitly migrated into a later schema/version.

---

# 1. Executive conclusion

Current A5 scoring has the correct security instinct: ScoreEngine consumes already-authorized scalar evidence, applies pack-bound mandatory gates and deterministic aggregation, and does not invent science. That remains correct.

The generalized architecture needs a stronger semantic abstraction above the current fixed `physics / robustness / accuracy` pack shape.

The durable rule should be:

> **A Score Pack is a versioned Evidence Use Contract: it states which qualified evidence is eligible, which failures make a candidate inadmissible, what scientific estimands are being ranked, how uncertainty and strata are handled, and how admissible evidence becomes a deterministic ranking result.**

The ScoreEngine remains deliberately non-scientific:

> **The engine executes registered evidence-use decisions. It does not decide which evidence is scientifically valid or what ought to matter.**

Current P0 45/30/25 weighted-geometric scoring can remain one narrow Score Pack profile.

---

# 2. Upstream dependencies

A future Score Pack should bind only already-qualified upstream objects:

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
     SCORE PACK
        ↓
     ScoreEngine
        ↓
  ScoreResult / RankInput
```

The Score Pack must not silently repair missing upstream science.

---

# 3. Proposed durable decomposition

```text
ScorePack
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

Economic emissions mapping remains a separate downstream concern unless a future explicit protocol decision changes that boundary.

---

# 4. Gauntlet A — hard physical necessity vs compensatory scoring

### Case

Candidate has exceptional predictive accuracy but violates a mandatory physical condition.

### Failure mode

A weighted average lets accuracy compensate for a physically disqualifying failure.

### Result

**PASS only with admissibility above ranking.**

```text
qualified evidence
    ↓
mandatory admissibility
    ↓ pass
continuous ranking
```

### Learning

`physics > loss` is primarily an admissibility doctrine, not merely a larger numerical weight on a physics leg.

Current hard-zero semantics survive.

---

# 5. Gauntlet B — multiple different mandatory conditions

### Case

One Challenge requires conservation, another finite-output safety, another interface continuity, another answerability floor.

### Result

**PASS if admissibility is measurement-binding based rather than hard-coded by model family.**

### Learning

A future `AdmissibilityPolicy` should bind qualified MeasurementContract outputs to required predicates, thresholds, strata, and applicability rules.

---

# 6. Gauntlet C — target population P(x), proposal Q(x), score weighting w(x)

### Case

Rare critical cases are oversampled in evaluation.

### Failure

Raw average over Q(x) is interpreted as expected performance under P(x).

### Result

**PASS only if the Score Pack states the estimand and weighting semantics.**

Possible policies:

- separate nominal and stress reports;
- qualified importance weighting;
- consequence-weighted objective;
- mandatory stress gates plus nominal ranking.

### Learning

The Score Pack must never infer population meaning from sample prevalence.

---

# 7. Gauntlet D — finite-sample uncertainty

### Case

Two candidates differ by 0.002 in scalar score, but sampling uncertainty is much larger.

### Failure

Leaderboard declares a false precision winner.

### Result

**Requires explicit ranking uncertainty policy.**

Possible policy classes:

- deterministic point-estimate ranking with declared uncertainty but no probabilistic claim;
- minimum meaningful separation / equivalence band;
- registered repeat policy;
- conservative lower-bound ranking for selected measurements;
- tie/indeterminate state when evidence cannot discriminate.

### Learning

Carbon must distinguish `numerically ordered` from `scientifically distinguishable`.

Exact policy is Challenge-specific; no universal confidence rule is implied.

---

# 8. Gauntlet E — stochastic construction and candidate variance

### Case

The same submitted construction strategy produces different artifacts across independent reconstructions.

### Failure

One lucky reconstruction determines emissions.

### Result

**PASS only if reconstruction variability can be represented in the evidence and ranking policy.**

Possible requirements:

- multiple reconstruction seeds;
- dispersion estimand;
- worst/mean/tail reconstruction performance;
- reproducibility gate.

### Learning

Reconstruction variability is not the same as evaluation-instance variability.

---

# 9. Gauntlet F — reference uncertainty

### Case

Reference truth is uncertainty-bearing or two trusted solvers disagree.

### Failure

Candidate error below the reference uncertainty floor is treated as scientifically meaningful.

### Result

**Score Pack must consume qualified measurement outputs that already account for reference policy, or explicitly bind an uncertainty-aware estimand.**

### Learning

ScoreEngine must never improvise how solver disagreement changes a metric.

---

# 10. Gauntlet G — measurement uncertainty and numerical resolution

### Case

Residual metric changes materially with discretization or evaluation resolution.

### Result

**PASS if MeasurementContract identity is pinned and the Score Pack references the qualified version.**

### Learning

A metric name like `residual` is not a sufficient score input identity.

---

# 11. Gauntlet H — measurement non-applicability

### Case

Shock-location metric applies only when a shock exists.

### Failure

Non-applicable cases are silently zeroed, dropped, or interpreted as success.

### Result

**Score Pack needs explicit applicability/missingness semantics.**

Non-applicable evidence is distinct from candidate failure, missing evidence, reference failure, and infrastructure failure.

---

# 12. Gauntlet I — hierarchical / stratified physical populations

### Case

Candidate is excellent overall but catastrophically poor in one required geometry or regime stratum.

### Failure

Global averaging hides important subgroup failure.

### Result

**PASS with explicit StratumPolicy.**

Possible use:

- mandatory per-stratum gates;
- minimum stratum score;
- weakest-stratum pressure;
- registered aggregate weighting;
- stratum-specific uncertainty requirements.

### Learning

Aggregate score must not erase mandatory physical subgroup failure.

---

# 13. Gauntlet J — candidate abstention and escalation

### Case

Candidate answers only easy cases and abstains on difficult ones.

### Failure

Conditional performance among answered cases looks excellent.

### Result

**PASS only if answerability/coverage is part of the registered task and scoring estimand.**

Score Pack must bind:

- whether abstention is allowed;
- minimum coverage if any;
- how unanswered cases affect admissibility/ranking;
- escalation correctness if routing is part of the task.

---

# 14. Gauntlet K — mixed model families

### Case

Neural operator, ROM, analytical reduction and hybrid model compete.

### Failure

Scoring rewards an internal property only one model family exposes.

### Result

**PASS only if score-bearing measurements are defined on the common CandidateOutputContract or required equally from all admissible candidates.**

### Learning

No model-family ideology belongs in Score Pack semantics.

---

# 15. Gauntlet L — computational admissibility vs scientific performance

### Case

One method is scientifically excellent but violates the Challenge's acceleration/resource requirement.

### Failure

Latency or memory is silently blended into `physics` or treated as product value.

### Result

**Keep distinct semantics.**

A Challenge may prospectively define computational admissibility or a separate efficiency objective, but scientific performance, resource compliance, information value, and commercial utility must not be collapsed without explicit design.

---

# 16. Gauntlet M — resource-induced censoring

### Case

Hard cases time out more often, changing the realized valid-evidence population.

### Failure

Score ignores censoring and ranks on the easier surviving subset.

### Result

**Score eligibility must fail closed or follow a registered censoring policy; ScoreEngine does not silently drop cases.**

Infrastructure failure remains distinct from scientific failure.

---

# 17. Gauntlet N — invalid / malformed candidate vs physics failure

### Case

Submission cannot execute, violates schema, or produces incomplete outputs.

### Learning

These states must remain distinct:

```text
REJECTED / INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
VALID_AND_RANKED
INDETERMINATE_EVIDENCE
```

Not every non-scoring outcome should become score zero.

A scientific zero is itself evidence and must not be conflated with protocol/infra invalidity.

---

# 18. Gauntlet O — NaN / Inf / numerical pathologies

### Case

Candidate emits NaN on one case.

### Result

Policy must be explicit and fail closed where required.

### Learning

Non-finite handling belongs in registered evidence/admissibility semantics; it cannot be implementation-defined validator behavior.

---

# 19. Gauntlet P — metric trade-off gaming

### Case

Candidate intentionally sacrifices a weakly weighted physical property to gain a heavily weighted accuracy term.

### Result

**Mandatory requirements belong in admissibility; soft margins only rank among admissible candidates.**

### Learning

Weights should express preference among scientifically acceptable outcomes, not define whether a physical necessity matters.

---

# 20. Gauntlet Q — top-level aggregation choice

### Case

Arithmetic, geometric, harmonic, min-like and lexicographic aggregation produce different winners.

### Result

There is no universal correct aggregator.

### Learning

Aggregation choice is a protocol hypothesis requiring justification and versioning. Current weighted-geometric P0 aggregate is a registered design choice, not a law of physics.

---

# 21. Gauntlet R — zero values and geometric aggregation

### Case

One soft component legitimately reaches zero.

### Risk

Geometric aggregation can collapse the total score even when the component is not mandatory.

### Learning

Soft-component transform domains and zero semantics must be explicitly authored and qualified. Hard disqualification should not emerge accidentally from a soft mathematical transform.

---

# 22. Gauntlet S — normalization population dependence

### Case

Score transforms depend on current competitor population, leader score, or rolling leaderboard.

### Failure

Historical scores change meaning as competitors arrive.

### Result

Prefer pack-bound absolute/qualified transforms for authoritative scientific score. If population-relative ranking is ever used, its semantics and versioning must be explicit and historical evidence must remain interpretable.

---

# 23. Gauntlet T — ties and order stability

### Case

A > B, B > C, but small uncertainty or transform changes reverse order.

### Learning

Ranking policy should define tie/equivalence/indeterminate behavior and deterministic tie-break inputs separately from scientific score.

Tie-breaker mechanics should not pretend to add scientific evidence.

---

# 24. Gauntlet U — score version changes

### Case

New failure mode causes threshold or weighting change.

### Result

**New Score Pack version, prospective use, no silent historical rescore.**

Landscape may propose changes; it cannot mutate a LIVE pack.

---

# 25. Gauntlet V — distribution version changes without scoring changes

### Case

Same measurement and Score Pack formula, new target population/SamplingPlan.

### Learning

Scientific score identity still changes because the estimand/population changed.

Score results must pin distribution and SamplingPlan identity even if Score Pack bytes remain unchanged, or the registry must require an explicit compatible new exam identity.

---

# 26. Gauntlet W — measurement version changes without threshold changes

### Case

Numerical implementation of a residual changes while threshold is numerically identical.

### Result

Measurement identity change requires requalification and a prospectively compatible Score Pack binding.

Threshold number alone does not preserve semantics.

---

# 27. Gauntlet X — validator agreement / deterministic execution

### Case

Two validators receive identical qualified evidence but compute slightly different scores.

### Result

ScoreEngine numerical profile remains deterministic and versioned. Current A5 `python_binary64_v1` principle survives.

Scientific uncertainty belongs upstream/in the evidence policy; implementation nondeterminism does not masquerade as scientific uncertainty.

---

# 28. Gauntlet Y — leaderboard information leakage

### Case

Rich component scores allow adaptive reconstruction of hidden exam structure.

### Result

Score Pack semantics can be transparent while miner-facing disclosure remains separately budgeted.

### Learning

`ScoreResult` internal richness and `EvaluationCard` external disclosure are distinct contracts. Score Pack may reference a disclosure tier/policy but should not leak through engine internals.

---

# 29. Gauntlet Z — emissions mapping

### Case

Scientific score is directly transformed into Bittensor weights with decay, winner bonuses, challenge allocation, or economic modifiers.

### Failure

Economic policy becomes confused with scientific meaning.

### Result

Keep:

```text
scientific ScoreResult
        ↓
Economic / Emissions Mapping
        ↓
network weights
```

Economic transforms must not retroactively alter the scientific record.

---

# 30. Gauntlet AA — novelty and information value

### Case

A novel method is scientifically mediocre but highly informative.

### Result

Novelty/information value should not be silently inserted into primary performance score.

Use a separate research/bounty/information market if Carbon chooses to reward experiment value.

Performance evidence remains interpretable.

---

# 31. Gauntlet AB — product qualification

### Case

Subnet winner passes lean score but fails job-shaped product battery.

### Result

Search Score Pack does not certify a product.

Product qualification may have its own evidence-use/acceptance policy under a distinct qualification identity.

> **Rank nominates. Evidence qualifies.**

---

# 32. Gauntlet AC — sequential / rollout tasks

### Case

Performance depends on horizon, accumulating error, intervention policy and trajectory events.

### Result

Score architecture survives if MeasurementContracts and estimands can summarize episode-level evidence and admissibility can bind horizon/event-specific failures.

ScoreEngine still consumes authorized evidence, not raw trajectories.

---

# 33. Gauntlet AD — multi-objective engineering task

### Case

No single candidate dominates accuracy, robustness, latency and coverage.

### Learning

Carbon must distinguish:

- scientific admissibility;
- scalar emissions ranking required by the subnet;
- optional Pareto evidence preserved for science/product selection.

Scalar rank need not erase the richer evidence record.

---

# 34. Gauntlet AE — cross-Challenge score comparability

### Case

A score of 0.85 on Burgers and 0.85 on industrial CFD are treated as equivalent scientific competence.

### Result

**Reject universal cross-Challenge semantic comparability unless explicitly qualified.**

Score is Challenge-bound evidence. Cross-Challenge economic allocation is a separate policy problem.

---

# 35. Gauntlet AF — Challenge difficulty manipulation

### Case

Challenge owner changes population/thresholds to inflate or depress scores relative to another Challenge.

### Learning

Cross-Challenge emissions allocation must not rely on raw scalar score comparability without an explicit governance/economic mechanism.

---

# 36. Gauntlet AG — private partner measurements

### Case

Score Pack references proprietary measurement details or thresholds.

### Result

Scientific authority and disclosure can be separate. Exact pack/measurement artifacts may be controlled while validators bind content-addressed identities and public claims expose appropriate provenance/limitations.

Security review required; obscurity alone does not create scientific validity.

---

# 37. Gauntlet AH — adversarial candidate targets score transform

### Case

Miner learns exact transform and exploits a cliff just inside threshold.

### Result

This is not automatically a flaw: the registered objective is what miners should optimize. The defense is that admissibility/measurement/distribution represent the actual intended science, plus protected fresh realizations and budgeted feedback.

Avoid hidden arbitrary scoring rules as a substitute for good scientific design.

---

# 38. Gauntlet AI — metric redundancy / double counting

### Case

Two score legs measure strongly correlated manifestations of the same error, effectively overweighting one property.

### Result

Score Pack authoring/Validation Dossier should examine conceptual and empirical redundancy before assigning weights. The ScoreEngine cannot detect scientific double-counting reliably at runtime.

---

# 39. Gauntlet AJ — causal interpretation of score components

### Case

Higher physics score is interpreted as evidence that a specific architectural mechanism caused improvement.

### Result

Reject. Score records outcome under an intervention; causal attribution belongs to later experiment/Landscape design.

---

# 40. Gauntlet AK — changing model-family search freedom

### Case

Challenge expands from neural strategies to ROM/hybrid models under same physical task.

### Result

Score Pack can remain scientifically stable if CandidateOutputContract, measurement applicability, resource policy and representation qualification remain valid across families. If not, a new compatible score/evidence version is required.

---

# 41. Reconciled architectural conclusions

The gauntlet supports these durable principles:

1. **Admissibility precedes ranking.**
2. **A Score Pack is an evidence-use contract, not a scientific truth generator.**
3. **Score-bearing measurements must already be qualified.**
4. **Population, SamplingPlan, MeasurementContract and Score Pack identities jointly define score meaning.**
5. **Target prevalence, sample prevalence and score weight are distinct.**
6. **Finite-sample uncertainty can limit scientific distinguishability even when deterministic scores differ.**
7. **Reference/measurement/infra invalidity is distinct from candidate scientific failure.**
8. **Stratum-level mandatory failure cannot be averaged away when the Challenge declares it mandatory.**
9. **Model-family-specific internals receive no automatic score privilege.**
10. **Scientific performance, computational admissibility, information value, commercial utility and economic emissions policy are distinct layers.**
11. **Score version changes are prospective; historical scores remain pinned.**
12. **Internal score evidence and public disclosure are separate contracts.**
13. **Cross-Challenge scores are not automatically scientifically comparable.**
14. **The scalar subnet score should not destroy richer evidence needed for Landscape or qualification.**
15. **ScoreEngine should remain small, deterministic, closed-schema, and scientifically non-authoring.**

---

# 42. Proposed future Score Pack architecture

Conceptually:

```text
ScorePack {
  identity / exact pins

  evidence_eligibility_policy

  admissibility_policy {
    mandatory predicates
    applicability
    stratum scope
    missing/reference/infra semantics
  }

  estimand_bindings[] {
    id
    population_ref
    sampling_plan_ref
    measurement_contract_ref
    eligible_population
    uncertainty_semantics
  }

  measurement_use_bindings[]

  uncertainty_policy {
    repeat policy
    equivalence / indeterminate policy if used
    lower-bound / point-estimate semantics if used
  }

  stratum_policy

  aggregation_policy {
    transforms
    within-objective aggregation
    top-level aggregation
    weights
  }

  ranking_policy {
    ordering
    tie / equivalence behavior
    deterministic non-scientific tie break ref if needed
  }

  disclosure_policy_ref
}
```

Exact runtime schema should be designed only after tech/science review. Current schema 1.0 remains authoritative for P0.

---

# 43. P0 mapping

Current P0 can be interpreted as a narrow instance:

```text
EvidenceEligibilityPolicy
  closed ScoreInput keys

AdmissibilityPolicy
  mandatory binary hard gates

Estimands
  physics fidelity
  robustness
  predictive accuracy

AggregationPolicy
  fixed leg transforms
  0.45 / 0.30 / 0.25 pack-bound weights
  weighted geometric log-space aggregate

RankingPolicy
  deterministic scalar order
```

Nothing in this gauntlet requires changing current P0 before an explicit migration decision.

---

# 44. Final conclusion

> **Carbon's Score Pack should be the prospective contract that says how qualified scientific evidence is allowed to become admissibility and rank. The ScoreEngine should do nothing more—and nothing less—than execute that contract deterministically.**

This preserves `physics > loss`, model-family neutrality, finite-evidence discipline, population semantics, auditability, and the separation between scientific truth and economic reward across Carbon's full vision.
