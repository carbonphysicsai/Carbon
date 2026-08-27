# Carbon Science/GTM Engineering Ticket Delta

**Version:** 0.1 candidate  
**Date:** 2026-08-27  
**Status:** Owner-directed planning amendment; non-self-activating  
**Parent plan:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md`  
**Decision record:** `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

> This document identifies implementation work surfaced by the Science-Backed GTM study. It does not activate a wave or ticket. Coding begins only through the active `.agent/WAVE.md`, an authorized bounded ticket, and Carbon's normal review and merge process.

## 1. Correction to the initial PR scope

The Science/GTM study does create engineering work. The first PR version recorded governance and sequencing but did not make the code and ticket consequences explicit enough.

The correct position is:

- no Science/GTM production code belongs in active Wave A;
- several Wave B contracts and tests need sharper acceptance criteria;
- Waves C and D need concrete reference, measurement, conformance, uncertainty, and adversarial-evidence code;
- reusable MMS, multi-regime reference tooling, and hybrid-solver experiments are real code programs, but they are optional and interruptible before mainnet;
- Waves E through N gain product, commercial, hybrid, lifecycle, and Physics Intelligence implementation work after their controlling waves are authorized.

## 2. Launch-critical engineering delta

### 2.1 Wave B contract and fixture code

| Ticket | Code or schema addition | Required tests | Mainnet role |
|---|---|---|---|
| **B-02A** | Represent target, proposal/sampling, stress, practice, qualification, deployment, and realized-evidence populations as distinguishable identities where applicable. Bind `CanonicalChallengeCase` to population, SamplingPlan, generator, role, query, and censoring provenance. | Role mismatch rejection; population identity replay; query-population binding; manufactured/evidence campaign cannot silently become target population. | Required compatibility and scientific identity foundation. |
| **B-02B** | Extend the fixed Challenge-owned `StructuralComponentRef` seam to express bounded learned-component roles such as warm start, preconditioner action, coarse correction, residual correction, subdomain operator, or nonlinear initial guess. Keep the graph and executable semantics Challenge-owned. | Unknown role rejection; no arbitrary callable, import path, solver graph, or participant executable; component label cannot satisfy a scientific gate. | Compatibility only. Does not implement a hybrid product. |
| **B-03** | Add typed generator outcomes, invalid-case and censoring provenance, deterministic replay evidence, strata/category metadata, rejection/retry accounting, and generator-conformance report hooks. | Same request reproduces same case; support and exclusion enforcement; retry cannot hide hard cases; intended and realized distribution remain distinguishable. | Required for the first generator and Dossier. |
| **B-04** | Add explicit reference evidence roles and exact provenance for analytic/semi-analytic primary, manufactured verification anchor, converged numerical primary, independent witness, experimental/industrial anchor, qualified accelerator reference, and hybrid policy. `ReferenceRunOutcome` and `TruthAsset` must carry applicability, uncertainty, independence limitations, disagreement, and failure state. | Reference role cannot self-authorize; MMS role cannot become physical validation; disagreement cannot average into truth; reference failure cannot become candidate failure; fixture cannot become LIVE. | Required for the first reference path. |
| **B-05** | Extend `MeasurementContract` with claimed property, observables, operator/discretization, sampling or quadrature, normalization, applicability, numerical/reference floor, uncertainty, stratum applicability, evidence references, and mandatory/soft/diagnostic role. | Governing equation name alone is insufficient; non-applicable evidence cannot pass or fail silently; unqualified measurement cannot bind into a Score Pack. | Required for first score-bearing measurements. |
| **B-06** | Add D1-D12 evidence slots for MMS/refinement campaigns, observed order, planted-defect evidence, analytic anchors, primary/witness discrepancy, generator-oracle adversarial tests, measurement floors, decision resolution, limitations, and censoring. Avoid one opaque `generator_valid` or `mms_pass` flag. | MMS alone cannot pass target-population adequacy, model-form validation, context-of-use adequacy, or product qualification; missing required evidence blocks LIVE. | Required for the first Dossier mechanism. |
| **B-07B** | Add failure attribution, evidence-quality metadata, exact scientific-context refs, censoring status, and future-compatible epistemic status to `ExperimentRecord` and `ResearchReceipt`. Keep infrastructure failure nominally separate. | Low-ranked scientific failure remains representable; infrastructure failure cannot enter negative scientific evidence; public projection cannot leak protected evidence. | Required evidence substrate; later Landscape compatibility. |
| **B-E1** | Implement a dependence-aware decision-resolution harness covering reference variability, reconstruction variability, whole-case/trajectory sampling, staged evidence, stopping/extension, and typed contested results. | Correlated pseudo-replication cannot create false precision; unresolved intervals return contested/indeterminate rather than an invented winner. | Required for first scientific resolution claim. |
| **B-E2** | Implement the exact reference failure contract and fixture runners for supported, uncertain, disagreement, not-applicable, numerical-failure, and infrastructure-failure paths. | Every state reaches the correct non-scientific or indeterminate path; no mock or weaker implicit fallback. | Required for first reference runtime integration. |
| **B-E3** | Emit a machine-readable credibility crosswalk showing the question each evidence source addresses and the claims it cannot support. | A source role cannot be rendered as broader authority; correlation limitations remain visible. | Required audit and review support. |
| **B-E4** | Add misuse and aligned-cheating cases involving manufactured evidence, structural component claims, proxy residuals, reference failure, and candidate-specific evidence depth. | No MMS-only LIVE path; no component-label gate bypass; no candidate-specific reference fidelity or stress depth; no proxy score promoted as official evidence. | Required adversarial closeout. |
| **B-GATE** | Add integration assertions for the preceding semantics to the no-placeholder-LIVE audit. | Exact negative tests pass before Wave B closeout. | Required Wave B closeout. |

### 2.2 Wave C real-runtime code

| Ticket | Concrete implementation addition | Exit evidence |
|---|---|---|
| **C-02** | Reconstruction receipts must bind repeated-build identity, registered resources, environment, candidate artifact, and dispersion evidence where the policy requests repeats. | Rebuilt artifacts and repeat evidence trace to the same strategy and registered policy without exposing official case material. |
| **C-04** | Implement the protected Burgers primary-reference adapter, independent witness adapter, typed `ReferenceRunOutcome`, qualified cache key, applicability checks, uncertainty evidence refs, and fail-closed no-fallback behavior. Add reusable common-case reference campaign utilities where they do not broaden authority. | Primary and witness run on the exact canonical case; stale/mismatched cache rejects; disagreement and numerical failure remain non-candidate outcomes. |
| **C-05** | Implement score-eligible measurement operators, applicability determination, numerical-floor evidence input, uncertainty-bearing measurement result, and production A5 boundary. | Incomplete, inapplicable, uncertain, and invalid evidence cannot become a scalar score input. |
| **C-06** | Extend signed receipts and the evidence ledger to bind generator, population, SamplingPlan, reference policy, implementation/environment, measurement, uncertainty, and Dossier/qualification-manifest identities. | Reviewer can trace an official result to exact evidence without exposing hidden draws. |
| **C-07** | Orchestrate generator, reference, measurement, scoring, and card publication with typed scientific, reference, strategy, and infrastructure outcomes. | Reference or generator infrastructure failure never becomes candidate physics failure; no direct chain science. |
| **C-10** | Implement independent re-execution, reference/evaluator disagreement records, quarantine, and contested/non-settling paths. | Agreement strengthens evidence only under the registered policy; disagreement cannot silently settle. |

### 2.3 Wave D qualification code and scientific harnesses

Wave D contains human scientific judgments, but those judgments require reproducible code and retained data.

| Ticket | Required code or campaign implementation |
|---|---|
| **D-02** | Generator-conformance campaign runner for support, exclusions, marginals, joints, conditions, strata, duplicates, coverage, retry/censoring, and intended-versus-realized population. |
| **D-03** | Cole-Hopf qualification harness for IC recovery, periodicity, precision, quadrature/transform sensitivity, conditioning, invariants, limiting cases, and failure mapping. |
| **D-04** | Independent conservative numerical witness with spatial/time refinement, scheme and tolerance evidence, conservation diagnostics, and case-level discrepancy records. |
| **D-05** | Measurement qualification and calibration scripts that derive numerical/reference floors and sensitivity evidence before human threshold selection. |
| **D-06** | Reconstruction by whole-case/trajectory experiment runner, dependence-aware interval analysis, minimum resolvable improvement, indifference band, and stopping/extension audit. |
| **D-08** | Adversarial candidate fixtures for weak-reference imitation, generator-oracle bias, easy-case selection, abstention, proxy exploitation, leakage, and reconstruction instability. |

These implementations support the Burgers Dossier. They do not create generic multi-regime authority.

## 3. Optional, interruptible pre-mainnet research code

The following programs are real code additions. They may start only under the owner-approved non-contention rule and a separate authorized ticket.

| Candidate ticket | Implementation | Why it matters | Launch status |
|---|---|---|---|
| **R-MMS-01** | MMS Factory v0: symbolic or automatic derivative generation, forcing/IC/BC construction, exact evaluators, smoothness checks, refinement plans, observed-order reports, and evidence manifests. Initial families: Poisson, diffusion, nonlinear conduction, linear elasticity, and one interface problem. | Reusable code-verification infrastructure and future training/test data research. | Not a testnet or mainnet prerequisite. |
| **R-MMS-02** | Planted-defect and mutation harness for sign, source, coefficient, BC, interface flux, coordinate/unit, derivative, quadrature, time-level, and solver-convergence faults. | Measures what the MMS suite detects instead of assuming coverage. | Not a launch prerequisite. |
| **R-REF-01** | Reusable reference-evidence runner for analytic anchors, numerical primary, independent witness, refinement, tolerance, precision, disagreement, and artifact manifests. | Reduces per-regime implementation burden while preserving Challenge-specific authority. | Not authoritative until adopted by a qualified Dossier. |
| **R-PDE-01** | Poisson reference pack with analytic/MMS islands and an independent converged numerical witness. | Tests portability beyond Burgers and supports commercial elliptic workflows. | Portfolio research only. |
| **R-PDE-02** | Diffusion/heat reference pack with kernel/modal anchors and independent time-dependent numerics. | Bridges judge proof and the thermal commercial hypothesis. | Portfolio research only. |
| **R-HYB-01** | Offchain neural warm-start or preconditioner bake-off against the same conventional solver on identical cases. Record final accepted solution, residual history, iterations, wall time, memory, failures, fallback, and negative acceleration. | Tests a strong early commercial product form without giving the learned component final authority. | Not official scoring; post-launch qualification architecture remains unresolved. |

## 4. Post-launch and later-wave code additions

These additions belong in future wave boards. They should not be smuggled into Waves A-D.

### Wave E: evidence memory

- Failure-atlas ingestion for scientific gate failures, reference disagreement, reconstruction instability, hybrid stagnation, Product Battery failure, and requalification failure.
- Evidence-quality assessment based on provenance completeness, execution validity, reproducibility, and sample support.
- Machine-readable epistemic types: observed, predictive, causal candidate, and experimentally supported.
- Challenge-health analytics that cannot mutate a live Challenge.

### Wave F: product qualification

- `ProductCandidateModelCard` role and immutable lineage.
- Append-only `ProductBatteryRecord`, including failed attempts.
- Versioned `QualificationRecord`, limitations, context of use, evidence refs, and requalification triggers.
- Disclosure projections for public, buyer-controlled, and private audit surfaces.

The exact hybrid-system qualification identity remains deferred. Wave F must not hard-code one before the post-launch owner decision.

### Wave G: commercial engagement

- Structured engineering-job intake that records decision, workload, geometry/material/BC variation, outputs, consequences, latency, rights, reference access, fallback, and integration constraints.
- Reference-economics estimator that compares qualification and lifecycle cost with solve frequency and decision value. It is planning support, not scientific authority.
- Customer-hosted reference-service and controlled private-evaluation interfaces after rights, security, and science approval.

### Wave J: model-family neutrality

- Candidate adapters for neural operators, ROMs, and bounded hybrid learned/numerical systems.
- Common task/output contracts so model family does not alter the physical exam.
- Family-specific materialization parity tests.

### Wave K: generalized construction search

- Registered construction grammar for solver/model hybridization, representation choice, staged construction, and component composition.
- Search agents may propose hybrid structure but cannot define official measurements or inspect official evaluation state.

### Wave L: generalized reconstruction

- Isolated reconstruction worker for richer registered construction programs.
- Receipts for outer-solver identity, learned component, discretization, integration, resources, dependencies, and produced artifact/system.
- No arbitrary executable or external dependency by default.

### Wave M: engineering system lifecycle

- System-level product identity and evidence graph.
- Runtime acceptance, abstention, fallback, escalation, drift intake, and requalification.
- Deployment parity and hardware/runtime change tracking.
- The post-launch hybrid decision determines whether records are assembled-system, linked component/system, or another bounded form.

### Wave N: Physics Intelligence

- Prospective decision experiment service that compares Landscape recommendations against registered baselines.
- Transfer-prediction, method-selection, risk-prediction, and evidence-allocation tasks with held-out outcomes.
- No promotion from retrospective fit to a Physics Intelligence claim.

## 5. Suggested implementation ownership

Exact paths remain ticket-owned, but the current package boundaries suggest this division:

| Concern | Existing or future package boundary |
|---|---|
| Physical task, canonical case, Challenge binding | `carbon/challenges` and `carbon/physics` |
| Population, SamplingPlan, case materialization, conformance | `carbon/data` plus Challenge-specific implementations |
| Reference, measurement, uncertainty, Dossier, orchestration | `carbon/evaluation` |
| Registered backbones and fixed structural components | `carbon/backbones` |
| Evidence receipts and audit commitments | `carbon/audit` plus owner-specific stores |
| Landscape failure atlas and epistemic objects | `carbon/landscape` |
| Product evidence and lifecycle | Future Wave F/M owner package after schema ratification |
| Commercial engagement and customer rights | Future Wave G owner package; never inside scoring |

No current package name grants authority by itself. Each ticket must preserve the active semantic owner's boundary and import rules.

## 6. What this PR should and should not contain

This PR should contain the planning, ticket, and acceptance changes above. It should not contain production implementation because Wave A remains active and the owner decisions did not activate Wave B or a parallel research ticket.

After merge:

1. Wave A closes under its existing tickets.
2. Wave B activation can use these amendments when its exact contracts and ticket files are reviewed.
3. Code lands through the corresponding authorized tickets.
4. Optional research code receives its own explicit owner authorization and pauses on mainnet contention.

The absence of production code in this documentation PR is an authority decision. The absence of engineering consequences would be a roadmap error. This delta corrects that error.
