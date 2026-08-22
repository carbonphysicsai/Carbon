# Scoring vNext Reconciliation — Scientific Score Boundary

**Status:** OWNER-RECOMMENDED reconciliation overlay.  
**Current runtime authority remains:** `Design_Specs/Scoring.md`.  
**Future semantic source:** `Score_Pack_Architecture_v1.md`.

## 1. What remains correct in current scoring

Preserve until intentionally versioned:

- strict exact Score Pack identity / digest;
- closed authorized score inputs;
- deterministic ScoreEngine execution;
- binary mandatory gates in the current P0 profile;
- weighted-geometric log-space aggregation in the current P0 profile;
- 0.45 / 0.30 / 0.25 as a current P0 pack baseline where that exact pack is used;
- no runtime invention of scientific thresholds/weights;
- no use of miner self-reported metrics.

## 2. What changes conceptually

The scoring domain ends at **Challenge-bound scientific `ScoreResult`**.

```text
qualified evidence
      ↓
Score Pack
      ↓
ScoreEngine
      ↓
ScoreResult
```

The scoring document should not own the terminal economic allocation rule.

Future flow:

```text
ScoreResult
      ↓
LeaderReplacementPolicy / promotion exam
      ↓
FrontierAdvanceEvent
      ↓
Challenge-period entitlement
      ↓
Treasury settlement
```

## 3. Remove emissions semantics from future Score Pack schema

Historical/current fields such as:

```text
emissions:
  type: lean_score_decay
```

or direct `w ∝ S_combined * decay` belong to the old economic mapping, not the generalized scientific Score Pack.

Do not remove them from current runtime artifacts without an explicit schema migration. In the next scoring version, eliminate this coupling.

## 4. Physics > loss

Future documentation should lead with:

> **Admissibility precedes ranking. Mandatory physical/scientific failure cannot be compensated by soft objectives.**

45/30/25 is a soft-objective profile among eligible/admissible evidence, not the constitutional meaning of physics priority.

## 5. Evidence eligibility

Future Score Pack must handle states such as:

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

ScoreEngine must not silently drop or reinterpret these states.

## 6. Scientific result states

At minimum:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
VALID_RANKED
```

A scientific zero is evidence; invalidity/infra failure are not equivalent zeros.

## 7. Explicit estimands

Every score-bearing objective should identify the quantity it ranks, such as:

- expected target-population error;
- physical-failure probability;
- stress-tail risk;
- worst-stratum performance;
- consequence-weighted performance;
- coverage/answerability;
- reconstruction reproducibility.

Metric name alone is not enough.

## 8. P/Q/w

The score layer must preserve:

```text
P(x) = target population
Q(x) = finite proposal/sampling distribution
w(x) = evidence/score weighting semantics
```

Oversampled stress cases do not silently become workload prevalence.

## 9. Strata and uncertainty

Future Score Packs may require:

- minimum evidence per stratum;
- mandatory stratum gates;
- weakest-stratum pressure;
- stratum-specific uncertainty;
- repeat policy;
- equivalence/indeterminate bands;
- conservative bounds.

No universal confidence rule is implied.

## 10. Reconstruction variability

When Carbon rewards method quality rather than one lucky artifact, reconstruction variance may be score-relevant scientific evidence. The registered policy should be upstream of frontier settlement; the treasury never chooses the best lucky retraining post hoc.

## 11. Cross-Challenge rule

`0.85` on Challenge A is not automatically commensurate with `0.85` on Challenge B.

Equal Challenge `1/N` opportunity is defined by portfolio economics, not score normalization.

## 12. Scoring vs promotion

ScoreResult answers:

> How did this candidate perform under this registered Challenge evidence-use contract?

LeaderReplacementPolicy answers:

> Is this contender scientifically superior to the registered frontier under the promotion evidence required by this Challenge?

Do not collapse these questions.

## 13. Scoring vs product qualification

ScoreResult is search evidence. Product qualification is a separate job-shaped acceptance process.

> **Rank nominates. Evidence qualifies.**

## 14. Versioning

A material change in measurement identity, estimand, population compatibility, threshold, uncertainty/strata policy, transform, aggregation, or ranking semantics creates a new scoring/Score Pack version. Historical results remain bound to their original identity.

## 15. Migration acceptance

The next scoring runtime revision is ready when:

- current schema remains reproducible for historical/compatibility tests;
- new schema cleanly separates scientific ScoreResult from emissions/frontier settlement;
- all required upstream identities are pinned;
- evidence/result states are type-safe;
- ScoreEngine remains deterministic and scientifically non-authoring;
- frontier promotion consumes ScoreResult without modifying it.

> **Score measures the registered scientific evidence. It does not decide the payout.**
