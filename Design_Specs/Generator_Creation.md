# Generator Creation — Reference-Evidence Build Plan

**Carbon Subnet**  
**Version:** 2.0  
**Status:** OWNER-RECOMMENDED generator/reference creation architecture; Challenge-specific scientific acceptance remains evidence- and reviewer-owned.  
**Purpose:** Define how Carbon creates a Challenge generator **and the hard evidence package required to defend the reference used to evaluate it**.  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md), [`Challenge_Instance_Distribution.md`](./Challenge_Instance_Distribution.md), [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md), [`Data_Management.md`](./Data_Management.md), [`Scoring.md`](./Scoring.md), [`Runtime_Julia_Truth_Oracle.md`](./Runtime_Julia_Truth_Oracle.md), `SPEC.md`.

---

# 0. Executive rule

Carbon does **not** claim that a Validation Dossier creates absolute physical truth.

Carbon's defensible claim is narrower:

> **For an exact registered physical task and population, Carbon may use a reference process only after the evidence shows that its uncertainty, disagreement, applicability, and failure regions are sufficiently characterized to support the scientific comparison the Challenge intends to make.**

The creation process therefore has two outputs:

```text
A. EXECUTABLE CHALLENGE GENERATOR
   fresh seeded cases from a registered population/SamplingPlan

B. REFERENCE-EVIDENCE PACKAGE
   hard data showing why the reference path is adequate for those cases
```

The generator is not truth by definition. A solver is not truth by brand name. Agreement between a candidate and the generator is not sufficient evidence of physical correctness.

> **Narrowing the physical job makes a defensible reference claim possible; the evidence package determines whether that claim is actually earned.**

If the reference evidence cannot support the desired envelope or resolution, Carbon must **shrink the envelope, coarsen the scientific claim, mark the comparison indeterminate, or block LIVE**.

---

# 1. Authority chain

Generator creation follows this scientific chain:

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
                +
      CandidateOutputContract
                +
       Claim / Operating Envelope
                ↓
       TARGET POPULATION P(x)
                ↓
   InstanceDistributionContract
                ↓
          SamplingPlan Q(x)
                ↓
     ChallengeInstanceGenerator
                ↓
       CanonicalChallengeCase
                ↓
       REFERENCE POLICY
                ↓
    REFERENCE REALIZATION + EVIDENCE
                ↓
      MeasurementContracts
                ↓
       VALIDATION DOSSIER
                ↓
         Score Pack binding
                ↓
        Challenge Registry LIVE
```

The scientific task owns the population. The SamplingPlan owns finite evidence allocation. The generator implements that plan. The reference policy defines how authoritative comparison values are produced. The dossier qualifies the relevant links; it does not invent them after candidate results are seen.

---

# 2. What Carbon means by “reference truth”

Use precise language.

## 2.1 Preferred terminology

Use **reference**, **reference realization**, **qualified reference evidence**, or **authoritative reference within a stated uncertainty** unless an analytic or otherwise unusually strong case justifies the narrower word “truth.”

## 2.2 Three practical reference classes

```text
CLASS A — analytic / semi-analytic reference
Strongest case when assumptions and implementation are controlled.

CLASS B — qualified numerical reference
A numerical solution with convergence, verification, uncertainty,
applicability, and failure evidence.

CLASS C — engineering evidence reference
Experimental, telemetry, partner-golden, calibrated multi-fidelity,
or hybrid evidence with explicit measurement/model uncertainty.
```

The strength of the Carbon claim must decrease as reference uncertainty and model-form dependence increase.

## 2.3 What the reference claim does not mean

A qualified reference does **not** imply:

- universal physical truth;
- zero model-form error;
- regulatory certification;
- validity outside the registered envelope;
- validity under a different solver/configuration/version;
- automatic product qualification;
- that an independent second solver is itself unbiased truth.

---

# 3. Reference claim must be written before evidence generation

Every generator project must begin with a `ReferenceClaim` written in scientific prose and machine-readable metadata.

At minimum it answers:

1. **Quantity:** What exact field, trajectory, observable, or derived quantity is the reference intended to establish?
2. **Physical assumptions:** Which PDE/model, parameters, BCs/ICs, forcing, geometry, dimensional/nondimensional conventions, and exclusions apply?
3. **Population:** Which target population and strata does this reference claim cover?
4. **Resolution:** At what spatial/temporal/query representation is the reference authoritative?
5. **Uncertainty:** What kinds of uncertainty can remain: analytic implementation, discretization, iterative, sampling, experimental, calibration, model-form?
6. **Decision use:** Which candidate measurements or comparisons will depend on the reference?
7. **Failure policy:** What happens when the reference is unavailable, uncertain, divergent, inconsistent, or outside applicability?

No evidence campaign should begin with the vague objective “show the solver is accurate.”

---

# 4. Hard data required in every reference-evidence package

Every Challenge-specific reference-evidence package must retain **raw or reconstructible data**, not only narrative conclusions or plots.

## 4.1 Identity and provenance data

Required:

```text
challenge_id / challenge_version
PhysicalSystemSpec identity + digest
CandidateOutputContract identity
InstanceDistributionContract identity + digest
SamplingPlan identity + digest
generator version + digest
reference policy identity + version
reference implementation source/version
container/environment digest
compiler/runtime/library versions where material
hardware profile where material
precision policy
reference configuration
measurement implementation identities
case IDs / audit-seed commitments
creation timestamp / run manifest
```

A screenshot, notebook summary, or unpinned solver name is insufficient.

## 4.2 Case-level physical input data

For every reference-audit case retain, as applicable:

- canonical physical inputs;
- parameter values;
- initial conditions;
- boundary conditions;
- forcing;
- geometry/topology identity;
- requested output/query locations/times;
- stratum/category label;
- intended population/proposal metadata;
- reference applicability status.

The evidence must allow an independent reviewer to reconstruct **what physical problem was actually solved**.

## 4.3 Case-level reference output data

Retain the reference outputs actually used for qualification, with enough precision to reproduce the derived measurements:

- field/trajectory values or a content-addressed artifact reference;
- coordinates/query grid;
- units/scaling;
- solver status;
- convergence/termination information;
- residual/defect information where meaningful;
- invariant/balance diagnostics;
- interpolation/materialization steps;
- any uncertainty estimate attached to that realization.

## 4.4 Derived comparison data

Retain the per-case values used to support the qualification decision, not only aggregate means:

- reference-vs-reference discrepancies;
- generator-vs-reference discrepancies;
- discretization/refinement differences;
- conservation/balance errors;
- measurement values;
- stratum-level summaries;
- failure/censoring states;
- uncertainty intervals or bounds where available.

Aggregate tables must be reproducible from the retained case-level data.

---

# 5. Hard data required by reference class

## 5.1 Analytic / semi-analytic reference

An analytic formula is not accepted merely because it appears in literature or symbolic form. Carbon must validate the **implemented reference**.

Required evidence, where applicable:

1. **Equation recovery** — numerically evaluate the governing relation on representative reference trajectories/fields and show the implementation satisfies it to the expected numerical differentiation/evaluation floor.
2. **IC/BC recovery** — verify initial and boundary conditions exactly or within the known representation/numerical floor.
3. **Known invariant / monotonicity checks** — verify properties implied by the exact problem statement.
4. **Limiting/simple cases** — compare against cases with independently obvious or simpler behavior where available.
5. **Independent implementation check** — preferably implement the analytic/semi-analytic solution through a second code path or compare against an independently implemented numerical witness.
6. **Precision/refinement sensitivity** — demonstrate that the reference values used by Carbon are stable to numerical quadrature, transform resolution, truncation, interpolation, root solving, or precision choices used inside the analytic implementation.
7. **Failure map** — identify parameter/input regimes where the implementation becomes ill-conditioned, under-resolved, unstable, or otherwise unreliable.

The evidence package must distinguish **mathematical exactness of the derivation** from **numerical error of Carbon's implementation of that derivation**.

## 5.2 Qualified numerical reference

For a numerical solver intended to carry authoritative evidence, retain:

1. **Verification cases** — manufactured, analytic, benchmark, or otherwise independently checkable cases relevant to the solver path.
2. **Refinement study data** — spatial and temporal refinement results sufficient to demonstrate convergence/stability in the registered regime. A Challenge may choose a different scientifically justified design, but one single-resolution solve is not sufficient by itself.
3. **Observed convergence behavior** — raw errors/differences versus refinement level, not merely the label “mesh independent.”
4. **Solver-tolerance sensitivity** — evidence that iterative/nonlinear tolerances do not materially control the reference result at the intended decision resolution.
5. **Scheme/configuration sensitivity** — where material, compare plausible numerical formulations/discretizations so a convenient scheme artifact is not silently treated as physics.
6. **Conservation/balance evidence** — problem-appropriate integral/structural checks independent of candidate scoring.
7. **Failure/conditioning map** — timeouts, divergence, stiffness, poorly resolved gradients, mesh pathologies, or other regions where the solver stops being reliable.
8. **Independent witness** — for material regimes, compare against a separately implemented solver/formulation or stronger analytic/experimental evidence.
9. **Reference uncertainty estimate** — a documented uncertainty/floor attached to the quantities Carbon will compare.

Do not collapse discretization error, iterative convergence, solver disagreement, and infrastructure failure into one generic “solver error.”

## 5.3 Experimental / partner / telemetry reference

When physical measurement rather than an analytic/numerical solver is part of the reference authority, retain as applicable:

- instrument identity/calibration;
- measurement uncertainty;
- sampling frequency/resolution;
- filtering/preprocessing;
- synchronization/alignment;
- test conditions and environmental state;
- missingness/censoring;
- repeat runs/replicates;
- sensor drift and recalibration history;
- provenance/chain of custody;
- transformation from raw measurement to Challenge observable;
- known systematic biases;
- applicability/extrapolation limits.

Partner goldens are evidence, not unquestioned truth. If Carbon cannot inspect enough provenance to characterize their uncertainty, the claim must remain correspondingly narrow.

---

# 6. Reference disagreement is data, not an inconvenience

When two credible reference paths disagree, Carbon must retain the disagreement as first-class evidence.

Required disagreement record:

```text
case identity
reference A identity/config/output
reference B identity/config/output
absolute/relative discrepancy by qualified measurement
discrepancy spatial/temporal structure
stratum/regime
known numerical/experimental uncertainty for each path
investigation status
proposed cause if supported
resolution / unresolved status
claim impact
```

Permitted dispositions:

```text
AGREE_WITHIN_QUALIFIED_UNCERTAINTY
PRIMARY_SUPPORTED_BY_WITNESS
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

If disagreement exceeds what the Challenge can defend, the correct response is to **investigate, narrow the envelope, increase uncertainty, weaken the measurement claim, or block LIVE**.

Forbidden: silently average two incompatible references until candidates can be ranked.

---

# 7. Reference uncertainty must constrain scientific resolution

The reference evidence must establish a floor below which Carbon does not pretend to resolve candidate differences.

Conceptually:

```text
reference uncertainty
+ measurement uncertainty
+ reconstruction variance
+ evaluation-sampling variance
        ↓
SCIENTIFIC RESOLUTION / CONTESTED BAND
```

The exact combination is Challenge-specific and requires statistical/scientific review; this document does not prescribe a universal formula.

Required evidence before LIVE:

- empirical distribution of reference discrepancies across qualified audit cases;
- uncertainty/floor by relevant measurement and stratum;
- repeated reconstruction × fresh-evaluation matrix for representative strategies when candidate reconstruction is stochastic;
- rank/gate stability analysis under reference/evaluation variation;
- documented minimum resolvable improvement or indeterminate rule for frontier promotion.

> **Economic reward concentration must not be sharper than scientific resolution.**

If candidate A and B differ by less than the qualified resolution, Carbon has no authority to claim one is scientifically superior.

---

# 8. Generator correctness and reference correctness are separate experiments

A correct reference does not prove the generator samples the correct population, and a distribution-correct generator does not prove its labels/reference values are sufficiently accurate.

Run and retain two independent campaigns:

```text
CAMPAIGN G — GENERATOR CONFORMANCE
Does the executable generator implement P/Q/constraints/strata correctly?

CAMPAIGN R — REFERENCE ADEQUACY
Are the authoritative comparison values accurate/reliable enough
for the claim and measurements?
```

## 8.1 Generator-conformance hard data

Retain:

- realized marginal distributions;
- joint/conditional distribution checks;
- constraint violation counts;
- range/support coverage;
- stratum/tail frequencies;
- duplicate/near-duplicate rates;
- invalid-case rates;
- generator failure rates by stratum;
- intended-versus-realized distribution after censoring;
- deterministic replay checks;
- train/eval/stress role-separation checks.

A generator can solve every PDE case correctly and still fail Campaign G.

## 8.2 Reference-adequacy hard data

Retain the evidence in §§4–7 across a **prospectively defined audit set** that covers the interior, boundaries, difficult strata, and known numerical risk regions of the claim.

Do not select only the cases where the reference implementation behaves well.

---

# 9. Choosing the audit campaign

There is no universal correct number of audit cases.

The audit design must be strong enough to support the exact claim. Use a prospectively registered `ReferenceAuditPlan` containing:

```text
audit objective
target population / strata references
case-selection policy
interior allocation
boundary allocation
stress/risk-region allocation
replication/refinement plan
reference paths required per case
measurements recorded
uncertainty objective
failure/censoring policy
stopping/extension rule
```

Recommended design principle:

> **Increase audit depth until the estimated reference/measurement uncertainty and observed disagreement are stable enough to support the intended scientific resolution with margin.**

Do not choose `N` because another benchmark used that value. Do not stop merely because a plot looks smooth.

The Validation Dossier must justify why the retained audit campaign is sufficient.

---

# 10. Burgers v1 reference-evidence campaign

For the recommended first authoritative fixed-viscosity 1D periodic viscous Burgers Challenge, use the following hierarchy:

```text
REGISTERED PHYSICAL PROBLEM
u_t + u u_x = ν u_xx
periodic 1D domain
fixed ν = 5×10⁻³
registered smooth periodic IC population
        ↓
PRIMARY REFERENCE
periodic Cole–Hopf implementation
        ↓
SECONDARY WITNESS
independently implemented high-resolution conservative numerical solver
        ↓
GENERATOR UNDER TEST
production/Challenge generator realization
```

This section specifies **what data must be produced**; it does not pre-approve any tolerance or sample count.

## 10.1 Cole–Hopf implementation evidence

Produce and retain:

1. exact code/environment identity;
2. test cases with analytically/simple expected behavior where available;
3. IC recovery at `t=0` or the nearest numerically meaningful limit;
4. periodicity error;
5. spatial-mean conservation error over time;
6. energy evolution consistent with unforced viscous dissipation;
7. maximum-principle consistency where applicable;
8. equation-defect/residual diagnostics computed with a separately qualified numerical differentiation procedure if used as evidence;
9. transform/quadrature/truncation/resolution sensitivity;
10. precision sensitivity if material;
11. explicit failure/ill-conditioning cases;
12. content-addressed reference outputs for the registered audit cases.

## 10.2 Independent numerical witness evidence

For the same registered audit cases, retain:

- solver implementation/version/environment;
- discretization/scheme;
- grid and time-step sequence used for refinement;
- solver tolerances;
- output at each refinement level;
- convergence/difference data for the exact quantities Carbon measures;
- conservation/balance diagnostics;
- solver status/failure information;
- final witness-vs-Cole–Hopf discrepancy by case and stratum.

The numerical witness is corroboration, not automatic authority merely because it is a different codebase.

## 10.3 Generator-under-test evidence

Across the same audit plan, retain:

- generated canonical case identity;
- generator output/reference realization;
- generator-vs-Cole–Hopf field discrepancy;
- generator-vs-witness discrepancy;
- error versus time/query where applicable;
- physical diagnostics;
- stratum label;
- generator failure/censoring state;
- any concentration of error near a boundary/risk region.

## 10.4 Burgers-specific stop-ship tests

The first Burgers Challenge must not go LIVE if material evidence shows, among other conditions:

- the generator/reference error is comparable to the candidate differences Carbon intends to reward;
- the generator-oracle can outrank a qualified physical-reference oracle because the Score Pack rewards generator bias;
- Cole–Hopf and the numerical witness disagree materially without a bounded explanation;
- hard strata systematically coincide with reference failure/censoring;
- measurement thresholds are below the qualified numerical/reference floor;
- the historical final-state spatial-balance proxy is represented as a full PDE residual despite missing `u_t`;
- stochastic reconstruction/evaluation variation materially flips gate/rank decisions without an indeterminate policy.

---

# 11. Measurement qualification must consume reference hard data

Reference evidence is not complete until it supports the measurements used in the Challenge.

For every score-eligible `MeasurementContract`, produce a calibration/qualification table containing:

```text
measurement_id / version
scientific property claimed
required observables
reference path used
numerical operator/discretization
normalization/aggregation
reference/numerical floor by audit case or stratum
applicability rule
known failure modes
uncertainty summary
proposed role: mandatory / soft / diagnostic
proposed threshold or scale derivation method
```

A governing equation alone does not justify a residual metric. A conservation law alone does not justify a universal tolerance.

Score Pack thresholds must be traceable to these data plus the scientific/engineering relevance of the property. The ScoreEngine executes the registered decision; it does not create the scientific threshold.

---

# 12. Required reference-evidence tables in the Validation Dossier

At minimum the Dossier should contain or reference machine-readable forms of these tables.

## Table R0 — Reference identity

Exact software, environment, configuration, data/artifact identities and digests.

## Table R1 — Audit coverage

Case counts and coverage by population stratum, envelope boundary/risk region, reference path, and status.

## Table R2 — Analytic/reference implementation checks

IC/BC, invariant, residual/defect, precision/refinement, limiting-case, and implementation cross-check results.

## Table R3 — Numerical convergence / witness data

Per-case/refinement outputs, observed differences/convergence behavior, solver tolerance sensitivity, balance errors, and failures.

## Table R4 — Reference disagreement

Primary-vs-secondary discrepancies, uncertainty, status, investigation/disposition, and envelope impact.

## Table R5 — Generator-vs-reference

Case-level and stratum-level discrepancies, failure/censoring rates, and boundary/risk-region concentration.

## Table R6 — Measurement floors

Qualified numerical/reference floors and uncertainty for every score-eligible measurement.

## Table R7 — Decision-resolution study

Repeated reconstruction/evaluation results, gate/rank flip rates, and the resulting indeterminate/resolution policy.

## Table R8 — Limitations / unresolved regions

Every region, quantity, solver mode, representation, or measurement for which the reference claim is weakened or blocked.

A dossier that contains only summary prose and a few plots is insufficient for an authoritative LIVE decision.

---

# 13. Per-phase reference rigor

| Phase | Typical problem | Reference evidence expected | Defensible public claim |
|---|---|---|---|
| **P0 / academic** | Burgers, Poisson, heat, Darcy, simple elasticity | analytic/manufactured evidence where available; pinned numerical witness; convergence/implementation checks; explicit uncertainty/failure map | bounded scientific comparison inside the qualified academic envelope |
| **Engineering-like** | geometry, harder CFD/FEA regimes | stronger mesh/time verification; code-to-code comparison; representation parity; uncertainty by regime | bounded engineering-like evidence, not universal deployment validity |
| **Sponsored / industrial** | partner-specific operating population | partner evidence + independent reference path where possible; workload provenance; measurement uncertainty; privacy-aware auditability | exact customer/program evidence claim |
| **Multiphysics / high-consequence** | coupled systems | component + interface + assembled-system reference evidence; multi-fidelity policy; stronger disagreement/censoring analysis | no system claim beyond the assembled evidence |

Reference rigor scales with the claim. Carbon does not obtain industrial credibility by attaching an industrial solver name to an otherwise weak evidence campaign.

---

# 14. Partner / proprietary truth path

A customer may keep a proprietary high-fidelity solver, dataset, or experimental system private.

Preferred architecture:

```text
Carbon sends authorized canonical cases
        ↓
customer-hosted reference service executes privately
        ↓
returns bounded reference outputs + signed/provenance metadata
        ↓
Carbon runs registered measurements / evidence process
```

Before this can carry an authoritative Challenge, Carbon still needs evidence for:

- endpoint identity/authenticity;
- exact solver/configuration version;
- case/output binding;
- reproducibility or known variability;
- measurement uncertainty;
- failure/censoring behavior;
- tamper/replay protections;
- sufficient independent corroboration for the intended claim where feasible;
- audit access appropriate to confidentiality constraints.

Confidentiality changes who may inspect evidence; it does not remove the need for evidence.

---

# 15. Fallback playbook

| Problem | Defensible response |
|---|---|
| Analytic path unavailable | Use a qualified numerical/experimental reference; narrow the claim accordingly |
| Reference too expensive | Narrow envelope, use prospectively qualified multi-fidelity allocation, or reduce LIVE scope |
| Primary/witness disagreement | Investigate; quantify; narrow/indeterminate/block — never average for convenience |
| Reference fails mainly on hard cases | Treat as a scientific stop-ship or change reference method; do not censor the hard regime silently |
| Partner goldens lack provenance | Treat as limited supporting evidence, not unquestioned authority |
| Numerical floor exceeds proposed hard-gate tolerance | Raise/rederive the tolerance scientifically or redesign the measurement; do not claim sub-floor resolution |
| Generator error comparable to candidate separation | Improve generator/reference path or coarsen the comparison; do not pay for noise |
| One implementation dominates evidence | Add an independent witness or narrow the strength of the claim |
| Audit sample is too small to stabilize uncertainty | Extend the prospectively defined audit campaign |

Global fallback:

> **Fewer LIVE Challenges with defensible reference evidence are preferable to broad coverage built on uncharacterized answer keys.**

---

# 16. Creation sequence

```text
1. DEFINE PHYSICAL JOB
   PhysicalSystemSpec + CandidateOutputContract + envelope/exclusions

2. DEFINE POPULATION
   P(x) + strata + rare/stress semantics

3. DEFINE FINITE EVIDENCE PLAN
   Q(x) + audit plan + exam SamplingPlan

4. WRITE REFERENCE CLAIM + POLICY
   what is authoritative, where, with what uncertainty/failure semantics

5. IMPLEMENT GENERATOR
   deterministic/versioned/role-separated

6. IMPLEMENT PRIMARY REFERENCE
   analytic, numerical, experimental, or hybrid

7. IMPLEMENT INDEPENDENT WITNESS WHERE REQUIRED
   distinct formulation/code/evidence source

8. RUN GENERATOR-CONFORMANCE CAMPAIGN
   prove implementation realizes P/Q

9. RUN REFERENCE-ADEQUACY CAMPAIGN
   produce raw refinement/disagreement/uncertainty/failure data

10. QUALIFY MEASUREMENTS
    derive numerical/reference floors and applicability

11. RUN SCIENTIFIC-RESOLUTION STUDY
    prove finite evidence can distinguish the intended differences

12. ASSEMBLE VALIDATION DOSSIER
    retain R0–R8 evidence tables + raw artifacts

13. BIND SCORE PACK
    only qualified measurements/evidence become score-bearing

14. LAUNCH BAR / HUMAN SIGN-OFF

15. REGISTRY LIVE
```

Candidate results do not participate in choosing the population, reference policy, or scientific thresholds except through a separately versioned prospective redesign process.

---

# 17. Done-when checklist

A generator/reference package is ready for dossier review only when:

- [ ] physical task, output contract, envelope, and exclusions are explicit;
- [ ] target population `P(x)` is explicit and justified;
- [ ] finite SamplingPlan/audit plan is prospectively registered;
- [ ] generator identity/configuration is content-bound;
- [ ] generator conformance hard data exist;
- [ ] primary reference policy is written and versioned;
- [ ] reference implementation identity/environment/configuration is pinned;
- [ ] analytic implementation checks or numerical/experimental verification data exist as applicable;
- [ ] independent witness/corroboration exists where the claim requires it;
- [ ] case-level reference outputs and comparison data are retained;
- [ ] uncertainty/numerical floors are reported by measurement and relevant stratum;
- [ ] reference disagreement/failure/censoring is visible;
- [ ] measurement calibration tables exist;
- [ ] scientific-resolution/rank-stability study is complete enough for the intended comparison;
- [ ] all limitations and blocked regions are explicit;
- [ ] evidence artifacts are hashed/versioned and independently reproducible to the degree the claim requires;
- [ ] no score threshold sits below the reference/measurement resolution without explicit scientific justification;
- [ ] no claim is wider or sharper than the evidence;
- [ ] required Validation Dossier sections can be populated without relying on candidate leaderboard outcomes.

This checklist means **ready for scientific review**, not automatically LIVE.

---

# 18. Final principle

Carbon's first scientific challenge is not “can we generate PDE data?”

It is:

> **Can we demonstrate, with retained case-level evidence, that the physical reference and measurement process is accurate, stable, applicable, and resolved enough to support the exact comparison for which Carbon intends to create economic consequences?**

Only after that question is answered may a generator become part of an authoritative exam.

> **The exam must earn the right to judge the model.**
