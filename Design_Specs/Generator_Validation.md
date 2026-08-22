# Carbon Validation Dossier — Challenge Distribution, Generator, Truth, and Measurement Qualification

**Version:** 2.0  
**Status:** LOCKED ARCHITECTURE — owner-ratified on 2026-08-21; challenge-specific criteria, exact schemas, and implementation details remain subject to tech/science review.  
**Purpose:** Define the evidence package required before Carbon may treat a registered Challenge exam as scientifically fit to judge candidates.  
**Related:** `Challenge_Instance_Distribution.md`, `Generator_Creation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Scoring.md`, `Physical_System_Representation.md`, `Launch_Bar.md`.

> **The distribution architecture defines the exam population. The Validation Dossier earns the right to use that population as an exam.**

Numerical examples are never globally normative unless an exact Challenge explicitly adopts and qualifies them. Reference caches are dossier evidence or qualified runtime infrastructure, not automatically the live answer key. The dossier qualifies prospectively registered scientific objects and implementations; it does not invent them after candidate results are observed.

---

# 1. Executive rule

Before a Challenge becomes LIVE, Carbon must establish that **the exam itself deserves to judge candidates**.

A dossier must keep separate at least these questions:

1. Is the physical system represented correctly enough for the intended Challenge?
2. Is the claimed envelope defensible?
3. Is the target population scientifically relevant to the task?
4. Is the finite SamplingPlan capable of producing meaningful evidence?
5. Does the executable generator conform to the registered population and plan?
6. Is the reference/truth path credible enough?
7. Do representation/materialization adapters preserve the same physical case?
8. Are registered measurements applicable and scientifically adequate?
9. Is the finite evidence statistically sufficient for the intended estimands?
10. Are secrecy, role separation, decontamination, provenance, and censoring controlled well enough for authoritative use?

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

The dossier qualifies this chain. It does **not** define score weights, make an unqualified measurement score-bearing, create official seeds, expand the envelope, certify a product, or rewrite a population after seeing who wins.

---

# 3. Required evidence classes

Each evidence class is explicitly one of:

```text
REQUIRED
NOT_APPLICABLE_WITH_RATIONALE
DEFERRED_BLOCKING_LIVE
```

A missing required class fails closed for LIVE.

## D1 — Physical-system adequacy

Evidence that the Challenge's physical semantics correspond to the intended system, including assumptions, exclusions, variable/parameter semantics, BC/IC semantics, dimensional or nondimensional interpretation where material, and source reconciliation.

Structured physics describes the system; it does not certify it.

## D2 — Claim / envelope adequacy

Evidence supporting parameter ranges, geometry family, BC/IC classes, operating regimes, exclusions, extrapolation semantics, and claim limits.

If evidence is weaker than the written envelope, **shrink the envelope**.

## D3 — Target-population adequacy

Evidence that `InstanceDistributionContract` represents a scientifically meaningful population for the intended task.

Review may include marginals, joint/conditional structure, physical constraints, geometry/topology population, hierarchy/strata, query/observation population, workload-frequency evidence, rare-event semantics, provenance, uncertainty, and sensitivity to plausible alternate population models.

The dossier must distinguish:

```text
support / envelope
!=
target population P(x)
!=
stress / consequence population
```

## D4 — SamplingPlan / finite-evidence adequacy

Evidence that the finite exam can support its intended comparison.

Review may include proposal distribution `Q(x)`, target population `P(x)`, stratum/tail allocation, sample budget, replication, query allocation, minimum subgroup evidence, uncertainty/tail-resolution targets, stopping/extension rules, duplicate policy, censoring policy, and planned importance weighting or separate stress reporting.

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

The dossier states whether raw sample averages estimate the target population or whether reweighting/separate reporting is required.

## D5 — Generator implementation integrity

Evidence for version/content binding, deterministic replay where required, seed-domain behavior, role separation, support/exclusion enforcement, constraints, canonical-case reproducibility, official-eval independence, hidden-realization secrecy, and failure-state classification.

## D6 — Generator distribution conformance

Evidence that generated cases actually conform to the registered distribution and SamplingPlan.

Tests may include marginal/joint/conditional conformance, constraint satisfaction, geometry-family coverage, stratum/tail frequencies, query-population conformance, duplicate/near-duplicate rates, effective sample size, and intended-versus-realized sample distribution after failures/censoring.

Reference agreement does not prove distribution conformance.

## D7 — Reference / truth adequacy

Evidence supporting the truth source, depending on Challenge type: analytic derivation, mesh/temporal convergence, solver verification, code-to-code comparison, multi-code consensus, experiment, partner goldens, calibration, uncertainty, applicability, and disagreement policy.

Reference status remains distinct from candidate outcome, for example:

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

Evidence that model-family-specific materializations preserve the same registered physical case: grid/mesh parity, coordinates/frames, geometry identity, BC/IC and parameter preservation, query parity, lossy transformations, and representation-induced measurement limits.

Mixed-family Challenges require especially strong scrutiny here.

## D9 — Measurement adequacy and applicability

Every score-eligible measurement identifies or references its scientific property, required observables, numerical method, discretization/sampling, normalization/aggregation, precision/reference floor, applicability, uncertainty, limitations, implementation version, and validation evidence.

A governing equation does not uniquely determine a residual metric or threshold.

Applicability should be determined independently of the candidate where possible. Non-applicable cases are not silently treated as pass, fail, or missing.

## D10 — Statistical sufficiency and estimand clarity

The dossier states what each scientific quantity means and whether finite evidence is sufficient for that meaning.

Possible estimands include expected target-population error, physical-failure probability, tail risk, worst-stratum behavior, consequence-weighted performance, answerability/coverage, and robustness under a registered stress population.

No universal sample-size formula is assumed.

## D11 — Evaluation secrecy, decontamination, and role separation

Evidence that producers cannot reconstruct or control the official exam. This includes protected official seeds, construction/evaluation/stress separation, disclosure allow-lists, reference-cache separation, and semantic decontamination when different seeds alone do not ensure independent scientific evidence.

## D12 — Censoring, limitations, and residual uncertainty

The dossier records generator/reference/infrastructure failures, timeouts, invalid cases, non-applicable measurements, corrupted observations, weak evidence strata, solver disagreement, distribution uncertainty, representation approximations, unsupported regimes, and unresolved scientific questions.

Hard physical cases must not disappear silently from the realized evidence population because they are expensive or difficult to evaluate.

---

# 4. Dossier status model

Internal sections should not collapse to one opaque boolean.

```text
EvidenceSectionStatus:
  PASS
  FAIL
  NOT_APPLICABLE
  BLOCKED
  PASS_WITH_LIMITATIONS
```

`PASS_WITH_LIMITATIONS` is acceptable only when limitations are reflected in the registered claim/envelope and do not violate mandatory evidence requirements. Registry/Launch Bar policy owns the final LIVE decision.

---

# 5. Required identity binding

The dossier binds the exact identities/digests of all material objects it qualifies, where present:

```text
challenge_id / challenge_version
PhysicalSystemSpec semantic identity + artifact digest
claim / envelope identity
distribution identity / version + digest
SamplingPlan identity / version + digest
generator version + environment digest
ReferencePolicy / solver / instrument versions
representation adapter identities
MeasurementContract identities
Validation Dossier identity / version / digest
```

Historical evidence remains attributable to these exact identities. Score Pack binding happens only after the relevant evidence and measurements are qualified.

---

# 6. Prospective authoring

Correct process:

```text
scientific task authored
        ↓
population + SamplingPlan authored
        ↓
generator + truth + measurements implemented
        ↓
validation evidence produced
        ↓
dossier reviewed
        ↓
Score Pack bound
        ↓
LIVE
```

Forbidden process:

```text
run candidates
→ inspect who wins
→ change population / measurements / thresholds
→ call it the same exam
```

Material scientific changes create new prospective versions and, where required, new qualification evidence.

---

# 7. Population / sampling examples

A Challenge can fail scientifically even when every physical solve is correct:

- same envelope, wrong sampling density;
- physically meaningful correlations replaced by independent box sampling;
- rare high-consequence cases omitted or misrepresented as ordinary workload frequency;
- different seeds that are semantically near-duplicates for a claimed generalization test;
- generator conformance bugs such as uniform sampling where the registered population is log-uniform.

D3/D4/D6/D11 must distinguish these failure modes.

---

# 8. Reference / truth architecture

A `ReferencePolicy` should make visible, where material:

```text
reference type
backend / instrument identity
version
numerical / experimental configuration
applicability
verification / convergence evidence
calibration evidence
uncertainty
disagreement policy
failure policy
disclosure class
```

For multi-fidelity programs, fidelity allocation is visible and qualified. Difficult regions must not silently receive weaker truth merely because they are expensive.

---

# 9. Reference caches

Precomputed caches may support dossier evidence or efficient runtime evaluation where appropriate. They are not automatically the live official exam set.

A cache manifest should bind challenge, distribution/SamplingPlan, generator, reference policy/backend, qualified case provenance, representation schema, hashes, and creation environment.

Exact hidden official realizations remain protected.

---

# 10. Distribution uncertainty and partner evidence

Industrial population evidence may come from telemetry, simulation campaigns, requirements, expert elicitation, test matrices, future-use scenarios, or regulatory/qualification matrices.

The dossier records provenance, observation period, selection mechanisms, missingness, uncertainty, and extrapolations. A partner's historical workload is not automatically the correct future Challenge population.

---

# 11. Hierarchical populations and subgroup evidence

Where the target population is hierarchical or multi-regime, aggregate metrics must not hide important subgroup failure. The dossier may require minimum evidence per stratum, stratum-level uncertainty, mandatory stratum gates, documented weighting, and checks against Simpson-type interpretation failures.

---

# 12. Realized evidence population and censoring

The dossier compares the intended SamplingPlan with the realized valid-evidence population where censoring is material.

Generator failure, reference failure, infrastructure failure, timeout, invalid case, non-applicable measurement, or corrupted experiment are different states. None may be silently discarded in a way that reshapes the scientific exam.

---

# 13. Evidence depth by Challenge maturity

The same architecture applies at different depths.

**Academic / P0:** clear system semantics, envelope review, explicit distribution config, generator determinism/conformance, analytic/high-confidence truth, simple convergence where applicable, physics checks, role/secrecy tests, and enough finite evidence for the narrow proof goal.

**Engineering-like:** add geometry/population evidence, conditional structure, richer strata/tails, stronger solver verification/cross-code evidence, uncertainty, representation parity, and task-relevant measurement validation.

**Sponsored / industrial:** add partner workload provenance, independent reference evidence, private-distribution disclosure policy, qualification-population separation, lifecycle/drift plan, and stronger statistical review.

**Multiphysics / high-consequence:** add coupled-population compatibility, interface evidence, multi-fidelity truth policy, component/system distinction, assembled-system measurements, and stronger censoring/failure analysis.

---

# 14. Recommended dossier deliverable

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

The machine-readable manifest references evidence artifacts rather than embedding the full scientific case in one giant object.

---

# 15. Qualification decision semantics

A valid bounded conclusion is:

> **The registered Challenge distribution, SamplingPlan, generator implementation, reference path, representation pipeline, and measurement set have sufficient evidence for the stated LIVE search use within the exact registered envelope and limitations.**

The dossier does not claim universal physical validity, production qualification, deployment safety, transfer to another distribution/version, or automatic qualification of future generator changes.

---

# 16. Relationship to Score Pack

The Validation Dossier qualifies scientific evidence objects. The Score Pack governs their score-bearing use.

```text
physical property
    ↓
MeasurementContract
    ↓
Validation Dossier
    qualifies implementation / applicability / evidence
    ↓
Score Pack
    selects gate / estimand / aggregation / weighting / ranking semantics
    ↓
ScoreEngine
```

The dossier may provide calibration evidence relevant to threshold selection. It does not autonomously choose production thresholds or weights.

---

# 17. P0 compatibility

P0 does not need every future artifact as a runtime class. Burgers may retain a simple generator/config if the dossier can answer the scientific questions above.

P0-safe hooks include explicit distribution identity/version, explicit generator identity/version, documented intended population and train/eval/stress relationship, simple conformance tests, clear reference status/failure semantics, separation of illustrative from qualified thresholds, and a manifest binding all relevant versions.

---

# 18. Stop-ship conditions

A Challenge does not become LIVE when any material condition holds, including:

- physical-system ambiguity blocks interpretation;
- envelope exceeds evidence;
- target population is undefined or unjustified;
- SamplingPlan is clearly insufficient;
- generator does not conform to the population/plan;
- truth is materially unreliable without a bounded uncertainty policy;
- representation changes the physical task;
- score-bearing measurement lacks adequate qualification;
- official realization leaks or is producer-controlled;
- censoring materially removes difficult regimes without accounted policy;
- required evidence is `BLOCKED` or `FAIL`.

---

# 19. Locked constitutional invariants

1. **The exam population is defined before the generator is judged.**
2. **The Validation Dossier qualifies the exam; it does not define it retroactively.**
3. **Population adequacy, SamplingPlan adequacy, generator conformance, reference adequacy, representation fidelity, and measurement adequacy are separate claims.**
4. **Sampling prevalence, target prevalence, and score importance are separate.**
5. **Reference failure is not candidate failure.**
6. **Finite-sample sufficiency is part of scientific qualification.**
7. **Seed separation may require semantic decontamination.**
8. **Censoring remains visible.**
9. **Material scientific changes require prospective versioning/requalification.**
10. **No layer certifies itself.**

---

# 20. Final statement

> **Carbon should only let an exam judge models after Carbon can defend what population the exam represents, how finite cases are sampled, whether the generator implements that design, whether the truth path is credible, whether the measurements are adequate, and what uncertainty remains.**

That is the locked role of the Validation Dossier in Carbon's generalized architecture.
