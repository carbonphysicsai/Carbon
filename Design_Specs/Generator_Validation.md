# Carbon Validation Dossier — Challenge Distribution, Generator, Truth, and Measurement Qualification

> **Reconciliation:** Validation requirements are conditional on physics/evidence type. Numerical examples are illustrative unless adopted by an exact Challenge. Reference caches are dossier evidence, not live official exam data. The dossier qualifies registered scientific objects and implementations; it does not invent them after observing candidate results.

**Carbon Subnet**  
**Version:** 2.0 design draft  
**Status:** Core scientific-qualification architecture for tech/science-lead review  
**Related:** `Challenge_Instance_Distribution.md`, `Generator_Creation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Scoring.md`, `Physical_System_Representation.md`, `Launch_Bar.md`.

---

# 1. Executive rule

Before a Challenge can become LIVE, Carbon must establish that the **exam itself deserves to judge candidates**.

The Validation Dossier is the evidence package for that judgment.

> **The distribution architecture defines the exam population. The Validation Dossier earns the right to use that population as an exam.**

A valid dossier must not collapse these questions:

1. Is the physical system represented correctly enough for the intended Challenge?
2. Is the claimed envelope defensible?
3. Is the intended population scientifically relevant to the task?
4. Is the finite SamplingPlan capable of producing meaningful evidence?
5. Does the executable generator actually implement the registered distribution and plan?
6. Is the reference/truth path credible enough?
7. Do representation/materialization adapters preserve the same physical case?
8. Are the registered measurements applicable and scientifically adequate?
9. Is the finite evidence statistically sufficient for the intended estimands?
10. Are secrecy, role separation, and provenance strong enough for authoritative use?

A single `generator_valid=true` flag is insufficient.

---

# 2. Authority chain

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
                +
      CandidateOutputContract
                +
       Claim / Operating Envelope
                ↓
       TARGET POPULATION
                ↓
   InstanceDistributionContract
                ↓
          SamplingPlan
                ↓
     ChallengeInstanceGenerator
                ↓
       CanonicalChallengeCase
                ↓
     Reference / Truth Policy
                ↓
        MeasurementContracts
                ↓
       VALIDATION DOSSIER
                ↓
         Score Pack binding
                ↓
        Challenge Registry LIVE
```

The dossier qualifies this chain. It does **not**:

- define score weights;
- make a proposed measurement score-bearing;
- create official seeds;
- expand the claim envelope;
- certify a product;
- rewrite a population after candidate outcomes are known.

---

# 3. Dossier evidence classes

Every Challenge must explicitly classify each section as:

```text
REQUIRED
NOT_APPLICABLE_WITH_RATIONALE
DEFERRED_BLOCKING_LIVE
```

A missing required section fails closed for LIVE.

## D1 — Physical-system adequacy

Evidence that the Challenge's `PhysicalSystemSpec` and scientific interpretation correspond to the intended system.

Possible evidence:

- equation/model review;
- assumptions and exclusions;
- parameter semantics;
- dimensional/nondimensional interpretation;
- boundary/initial-condition semantics;
- comparison to authoritative domain definitions;
- unresolved-source reconciliation.

**Important:** structured physical semantics describe the system; they do not certify it.

## D2 — Claim / envelope adequacy

Evidence supporting the support of the Challenge claim.

Must include, where applicable:

- parameter ranges;
- geometry family;
- BC/IC classes;
- operating regimes;
- explicit exclusions;
- intended extrapolation semantics;
- evidence limits.

If evidence is weaker than the claimed envelope, **shrink the envelope**.

## D3 — Target-population adequacy

Evidence that the registered `InstanceDistributionContract` represents a scientifically meaningful population for the intended task.

This may include:

- marginal distributions;
- joint/conditional structure;
- physical constraints;
- geometry/topology population;
- hierarchical/stratified structure;
- query/observation population;
- workload-frequency evidence;
- rare-event semantics;
- provenance and uncertainty;
- sensitivity to plausible alternate population models.

The dossier must distinguish:

```text
support / envelope
!=
target population P(x)
!=
stress/consequence population
```

## D4 — SamplingPlan / finite-evidence adequacy

Evidence that the finite exam can support its intended scientific comparison.

Review should address, where material:

- proposal/sampling distribution `Q(x)`;
- target population `P(x)`;
- stratum allocation;
- rare/tail allocation;
- sample budget;
- replication policy;
- query allocation;
- minimum subgroup evidence;
- uncertainty target;
- tail-resolution objective;
- stopping/extension rules;
- duplicate/near-duplicate policy;
- planned treatment of importance weighting or separate stress reporting.

### Core distinction

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

The dossier must state whether raw sample averages estimate the target population or whether reweighting/separate reporting is required.

## D5 — Generator implementation integrity

Evidence that the executable generator behaves as the registered implementation requires.

Checks may include:

- version/content hash binding;
- deterministic replay where required;
- seed-domain behavior;
- role separation;
- support/exclusion enforcement;
- constraint enforcement;
- canonical-case reproducibility;
- no miner control of official eval/stress generation;
- no hidden-realization leakage;
- failure-state classification.

## D6 — Generator distribution conformance

Evidence that generator output actually conforms to the registered distribution and SamplingPlan.

Possible tests:

- marginal goodness-of-fit / conformance;
- joint/dependence checks;
- conditional distribution checks;
- geometry-family coverage;
- stratum frequencies;
- rare/stress category frequencies;
- query-population conformance;
- constraint satisfaction;
- duplicate/near-duplicate rates;
- effective sample size;
- intended vs realized sample distribution after generator/reference failures.

This evidence is distinct from reference-solver agreement.

## D7 — Reference / truth adequacy

Evidence supporting the truth source associated with sampled cases.

Depending on Challenge type:

- analytic derivation;
- mesh convergence;
- temporal convergence;
- solver verification;
- code-to-code comparison;
- multi-code consensus;
- experiment;
- partner goldens;
- calibration evidence;
- uncertainty characterization;
- applicability by regime;
- disagreement policy.

### Reference statuses

The evidence architecture should support distinctions such as:

```text
REFERENCE_AVAILABLE
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

Reference/truth failure is **not candidate failure**.

## D8 — Representation fidelity

Evidence that model-family-specific materializations preserve the same registered physical case.

Potential checks:

- grid/mesh interpolation parity;
- coordinate/frame consistency;
- geometry identity;
- BC/IC preservation;
- parameter preservation;
- query parity;
- lossy transformation analysis;
- representation-induced measurement limitations.

Mixed-family Challenges require especially strong scrutiny here.

## D9 — Measurement adequacy and applicability

For every score-eligible measurement, the dossier should identify or reference:

- scientific source/property;
- required observables;
- numerical implementation;
- discretization/sampling;
- normalization/aggregation;
- precision/reference floor;
- applicability conditions;
- uncertainty;
- limitations;
- implementation version;
- validation evidence.

A governing equation does not uniquely determine a residual metric or threshold.

Measurement applicability should be determined independently of the candidate where possible. Non-applicable cases must not be silently treated as pass/fail/missing.

## D10 — Statistical sufficiency and estimand clarity

The dossier must state what each reported scientific quantity means.

Possible estimands:

- expected error under target operation;
- physical-failure probability;
- tail risk;
- worst-stratum performance;
- consequence-weighted performance;
- answerability/coverage;
- robustness under a registered stress population.

Review should establish that the sample plan and measurement aggregation are sufficient for the intended estimand, without pretending one universal sample-size formula applies to every Challenge.

## D11 — Evaluation secrecy and role separation

Evidence that the official exam cannot be reconstructed or controlled by the producer.

Must align with `Data_Management.md` and trustless verification rules:

- construction/train realization separated from evaluation/stress;
- official seeds protected;
- validator identifiers not used to create scientifically different official exams;
- miner-visible outputs allow-listed;
- reference caches do not become the live answer key;
- semantic decontamination rules applied where seed separation alone is insufficient.

## D12 — Residual uncertainty, limitations, and unresolved issues

Every dossier must state what it does **not** establish.

Examples:

- distribution uncertainty;
- weak evidence strata;
- solver disagreement;
- missing experimental support;
- approximation due to representation conversion;
- unsupported deployment regimes;
- known censoring;
- unresolved scientific questions.

LIVE approval is bounded to the evidence actually present.

---

# 4. Dossier status model

Avoid one opaque pass/fail field internally.

Conceptual section status:

```text
EvidenceSectionStatus:
  PASS
  FAIL
  NOT_APPLICABLE
  BLOCKED
  PASS_WITH_LIMITATIONS
```

Challenge LIVE status remains governed by the registry/Launch Bar policy. A dossier may contain `PASS_WITH_LIMITATIONS` only where those limitations are reflected in the registered envelope/claim and do not violate mandatory evidence requirements.

---

# 5. Required identity binding

A Validation Dossier should bind the exact versions/digests of all material objects it qualifies, where present:

```text
challenge_id / challenge_version
PhysicalSystemSpec semantic identity + artifact digest
claim/envelope identity
distribution_id / distribution_version + digest
SamplingPlan identity / version + digest
generator version + environment digest
reference policy / solver versions
representation adapter identities
MeasurementContract identities
Validation Dossier identity/version/digest
```

Score Pack binding occurs after the relevant measurements/evidence are qualified.

Historical evidence must remain attributable to the exact identities above.

---

# 6. Dossier authoring must be prospective

The correct process is:

```text
scientific task authored
        ↓
population / SamplingPlan authored
        ↓
generator + reference + measurements implemented
        ↓
validation evidence produced
        ↓
dossier reviewed
        ↓
Score Pack bound
        ↓
LIVE
```

Forbidden pattern:

```text
run candidates
        ↓
inspect who wins
        ↓
change population / measurements / thresholds
        ↓
call that the same exam
```

Material changes create new prospective versions and, where required, new qualification evidence.

---

# 7. Population and sampling validation examples

## 7.1 Same envelope, wrong density

Declared envelope:

```text
Mach ∈ [0.6, 0.9]
AoA  ∈ [-2°, 8°]
```

If the generator places almost all mass around one easy central regime, reference CFD can still be perfect while the Challenge is weak.

D3/D6 must detect this.

## 7.2 Correlated physical variables

If pressure, temperature, Mach, Reynolds number, geometry, or material state have conditional relationships, independent box sampling may generate scientifically irrelevant combinations.

D3 must justify the population structure; D6 must verify implementation conformance.

## 7.3 Rare high-consequence conditions

A condition with low deployment prevalence may be deliberately oversampled for stress evaluation.

The dossier must distinguish:

```text
deployment prevalence
sampling prevalence
scientific consequence / score treatment
```

## 7.4 Semantic train/eval contamination

Different seeds do not guarantee scientifically distinct evidence. Geometry-family, specimen, mission, source-data, or temporal separation may be required for a particular generalization claim.

D11 must evaluate this where material.

---

# 8. Reference/truth evidence architecture

Reference sources are evidence-bearing implementations, not absolute authority merely because they are expensive.

The dossier should document:

```text
ReferencePolicy {
  reference_type
  backend / instrument identity
  version
  numerical / experimental configuration
  applicability
  convergence / verification evidence
  calibration evidence
  uncertainty
  disagreement policy
  failure policy
  disclosure class
}
```

For multi-fidelity programs, the SamplingPlan should make fidelity allocation visible. Difficult regions must not silently receive weaker truth because they are expensive.

---

# 9. Reference caches

Precomputed reference caches may support dossier evidence or efficient evaluation where scientifically and security-wise appropriate.

They are **not** automatically the live official exam set.

A cache manifest should bind at least:

```text
challenge identity
distribution / SamplingPlan identity
generator version
reference policy/backend version
case identities or qualified sampling provenance
representation schema
artifact hashes
creation environment
```

Public disclosure of cache contents is Challenge/security dependent. Exact hidden official realizations remain protected.

---

# 10. Distribution uncertainty and partner evidence

For industrial Challenges, the population itself may be uncertain.

Evidence may come from:

- telemetry;
- simulation campaigns;
- engineering requirements;
- expert elicitation;
- test matrices;
- future-use scenarios;
- regulatory/qualification matrices.

The dossier should record source provenance, observation period, selection mechanisms, missingness, uncertainty, and extrapolations.

A partner-provided historical workload is not automatically the correct future Challenge population.

---

# 11. Hierarchical populations and subgroup evidence

Where the target population is hierarchical or multi-regime, the dossier should check whether aggregate metrics can hide important subgroup failure.

Possible requirements:

- minimum evidence per stratum;
- stratum-level confidence/uncertainty;
- mandatory stratum gates;
- documented aggregate weighting;
- prevention of Simpson-type interpretation errors.

No universal hierarchy schema is required for P0.

---

# 12. Censoring and missing evidence

The dossier must define how the validation program treats:

- generator failures;
- reference failures;
- infrastructure failures;
- timeouts;
- invalid cases;
- non-applicable measurements;
- corrupted experimental observations.

A hard or expensive physical regime must not disappear silently from evidence because its truth path is difficult.

The realized valid-evidence population should be compared to the intended SamplingPlan where censoring is material.

---

# 13. Validation evidence classes by Challenge maturity

The same architecture applies at different depths.

### Academic / P0

Likely evidence:

- clear system semantics;
- envelope/range review;
- explicit distribution config;
- generator determinism/conformance;
- analytic or high-confidence numerical truth;
- simple convergence checks where applicable;
- physics checks;
- role/secrecy tests;
- sufficient finite sample for the narrow proof goal.

### Engineering-like Challenge

Add, as appropriate:

- geometry/population evidence;
- conditional/correlated workload structure;
- richer strata/tails;
- solver verification / cross-code evidence;
- uncertainty;
- representation parity;
- task-relevant measurement validation.

### Sponsored / industrial Challenge

Add, as appropriate:

- partner workload provenance;
- independent reference evidence;
- proprietary distribution disclosure policy;
- job-shaped qualification population separation;
- lifecycle/drift plan;
- stronger statistical sufficiency and uncertainty review.

### Multiphysics / high-consequence

Add, as appropriate:

- coupling population compatibility;
- interface evidence;
- multi-fidelity truth policy;
- component/system distinction;
- assembled-system measurement qualification;
- stronger failure/censoring analysis.

---

# 14. Dossier deliverable structure

Recommended human-readable + machine-readable sections:

```text
00 Identity and status
01 Scientific task and authority map
02 Physical system and assumptions
03 Claim / envelope
04 Target population / InstanceDistributionContract
05 SamplingPlan / finite-evidence design
06 Generator implementation integrity
07 Generator distribution conformance
08 Reference / truth qualification
09 Representation/materialization qualification
10 Measurement qualification / applicability
11 Statistical sufficiency / estimands
12 Secrecy / role separation / decontamination
13 Censoring / failure analysis
14 Residual uncertainty / limitations
15 Qualification decision + reviewer sign-off
16 Artifact manifest / hashes / environments
```

The machine-readable manifest should reference evidence artifacts rather than attempting to embed all scientific evidence in one giant JSON object.

---

# 15. Qualification decision semantics

The final dossier decision should state a bounded conclusion such as:

> **The registered Challenge distribution, SamplingPlan, generator implementation, reference path, representation pipeline, and measurement set have sufficient evidence for the stated LIVE search use within the exact registered envelope and limitations.**

It must not state:

- universal physical validity;
- production qualification;
- that any candidate passing the exam is safe for deployment;
- that the same evidence applies to a different distribution/version;
- that a future changed generator remains qualified automatically.

---

# 16. Relationship to Score Pack

The Validation Dossier qualifies scientific evidence objects. The Score Pack governs their score-bearing use.

```text
physical property
    ↓
MeasurementContract
    ↓
Validation Dossier
    qualifies implementation/applicability/evidence
    ↓
Score Pack
    selects mandatory gate / soft component / aggregation / weighting
    ↓
ScoreEngine
```

The dossier may provide calibration evidence relevant to threshold selection. It does not autonomously choose the production threshold/weight.

This separation is mandatory for the next Score Pack architecture review.

---

# 17. Relationship to P0

P0 does not need every future artifact as a runtime class.

For Burgers, the existing generator/config may carry most of the information structurally, provided the scientific review can answer the dossier questions.

P0-safe improvements include:

- explicit distribution identity/version;
- explicit generator identity/version;
- documented intended population;
- documented train/eval/stress relationship;
- simple distribution-conformance tests;
- clear reference status/failure semantics;
- separation of illustrative thresholds from qualified Challenge values;
- evidence manifest binding all relevant versions.

The goal is to harden the scientific seam without turning P0 into a general industrial framework prematurely.

---

# 18. Stop-ship conditions

A Challenge should not become LIVE when any material condition holds, including:

- physical-system ambiguity blocks interpretation;
- envelope claim exceeds evidence;
- target population is undefined or scientifically unjustified;
- generator does not conform to the registered population/plan;
- finite evidence is clearly insufficient for intended scoring semantics;
- reference truth is materially unreliable without a bounded uncertainty policy;
- representation changes the physical task;
- score-bearing measurement lacks adequate qualification;
- official eval/stress realization can leak or be producer-controlled;
- censoring materially removes difficult regimes without accounted policy;
- required evidence is `BLOCKED` or `FAIL`.

---

# 19. Constitutional summary

1. **The exam population is defined before the generator is judged.**
2. **The Validation Dossier qualifies the exam; it does not define it retroactively.**
3. **Population adequacy, SamplingPlan adequacy, generator conformance, reference adequacy, representation fidelity, and measurement adequacy are separate claims.**
4. **Sampling prevalence, target prevalence, and score importance are separate.**
5. **Reference failure is not candidate failure.**
6. **Finite-sample sufficiency is part of scientific qualification.**
7. **Seed separation may require semantic decontamination.**
8. **Censoring must remain visible.**
9. **Material scientific changes require prospective versioning/requalification.**
10. **No layer certifies itself.**

---

# 20. Final statement

> **Carbon should only let an exam judge models after Carbon can defend what population the exam represents, how finite cases are sampled, whether the generator implements that design, whether the truth path is credible, whether the measurements are adequate, and what uncertainty remains.**

That is the role of the Validation Dossier in the generalized Carbon architecture.
