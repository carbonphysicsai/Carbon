# Data, Generator, and Truth vNext Reconciliation

**Status:** OWNER-RECOMMENDED reconciliation overlay for `Data_Management.md`, `Trustless_Verification.md`, and `Generator_Creation.md`.  
**Purpose:** Preserve current seed/data-role security while inserting the qualified population, SamplingPlan, generator-conformance, truth, and censoring architecture.

## 1. Authority chain

```text
PhysicalSystemSpec
+ CandidateOutputContract
+ Claim / Envelope
        ↓
InstanceDistributionContract  owns P(x)
        ↓
SamplingPlan                  owns finite Q(x)
        ↓
ChallengeInstanceGenerator    implements the plan
        ↓
CanonicalChallengeCase
        ↓
ReferencePolicy               owns truth realization semantics
        ↓
MeasurementContracts
```

The generator does not author the target population by whatever distribution happens to exist in code.

## 2. Envelope != distribution

An envelope defines support/claim bounds. A distribution defines prevalence/dependence/strata/query semantics. A stress population may be different again.

Do not treat a uniform range in YAML as a scientific population merely because it is executable.

## 3. SamplingPlan

A finite exam should prospectively define, where relevant:

- sample budget;
- proposal distribution `Q`;
- stratification / hierarchy;
- tail/rare-case allocation;
- replication;
- query/observation allocation;
- truth-fidelity allocation;
- minimum subgroup evidence;
- duplicate policy;
- censoring behavior;
- stopping/extension rules.

The dossier determines whether this finite design is sufficient for the intended estimands.

## 4. Train / eval / stress remain useful but not universal ontology

For current neural P0, separate `train`, `eval`, and `stress` roles remain correct security primitives.

Long-term construction may instead use:

- training samples;
- calibration observations;
- ROM snapshots;
- solver-query budgets;
- experimental observations;
- equations with no sampled construction data.

The durable roles are construction information, official evaluation evidence, stress/rare evidence, and later qualification evidence.

## 5. Generator conformance

Generator qualification must test more than determinism:

- support/exclusions;
- marginals;
- joint/conditional dependencies;
- strata/tail frequencies;
- geometry/topology coverage;
- query distribution;
- duplicates/effective sample size;
- role separation;
- intended vs realized evidence after failures/censoring.

A perfectly solved wrong sample distribution is still a scientifically wrong Challenge.

## 6. ReferencePolicy separation

Reference/truth may be:

- analytic / semi-analytic;
- manufactured;
- high-fidelity numerical;
- multi-code consensus;
- experiment;
- partner goldens;
- dataset-backed;
- a controlled external service.

No one backend is universal.

Reference status must distinguish available, uncertain, disagreement, numerical failure, infrastructure failure, and not applicable.

## 7. Truth fidelity allocation

Physical-case sampling and reference-fidelity allocation are different designs. Hard cases must not silently receive weaker truth simply because they are expensive.

If multiple fidelities are used, the SamplingPlan / ReferencePolicy should expose how fidelity is allocated and how resulting evidence is interpreted.

## 8. Seed separation is necessary but may be insufficient

Different seeds do not guarantee scientific decontamination. Depending on the claim, Carbon may require separation by:

- geometry family;
- specimen/source;
- mission/time window;
- partner dataset segment;
- parameter distance;
- semantic scenario class.

The Validation Dossier owns the evidence that the chosen separation supports the intended generalization claim.

## 9. Query / observation population

For operator/query tasks, where and how the model is queried is part of the scientific task. Query locations, sensors, time points, or observation masks should not be treated as incidental implementation details when they affect the estimand.

## 10. Intended vs realized evidence population

Generator failure, reference failure, timeout, invalidity, or measurement non-applicability may censor cases.

Record:

```text
intended SamplingPlan
realized generated cases
reference-valid cases
measurement-applicable cases
candidate-valid cases
```

Do not silently average over whichever cases survived.

## 11. Burgers correction

Historical P0 Burgers sampling varied `nu` while the candidate received only `u0`. The first owner-recommended authoritative repair fixes `nu=5e-3` and assigns new Challenge identity. Later `(u0, nu) -> u(T)` is a different conditioned task.

Low-viscosity stress and undeclared nonlinear IC warps are not score-bearing in the repaired v1 unless explicitly authored and qualified.

## 12. Reference caches

Caches may support dossier evidence or efficient qualified evaluation where security allows. They are not automatically the live answer key.

Cache identity should bind Challenge, distribution/SamplingPlan, generator, ReferencePolicy, representation, creation environment, and artifact hashes.

## 13. Material changes

Changes to population, SamplingPlan, generator semantics, truth policy, representation, or censoring treatment may change the meaning of evidence even if a numeric score formula stays the same.

Such changes are versioned, prospective, and requalified where material.

## 14. Final rule

> **The scientific task owns the population. The SamplingPlan defines finite evidence. The generator implements it. The ReferencePolicy realizes truth. None of these layers silently inherits authority from another.**
