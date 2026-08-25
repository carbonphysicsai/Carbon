# Carbon’s Independent Physics Exam
## Burgers v1: how Carbon creates a fresh, independently gradeable physics exam

**Status:** Pre-LIVE scientific design note  
**Purpose:** Explain, as clearly as possible, how Carbon can evaluate model-construction strategies against reference data that is demonstrably close enough to the physical solution to support economic ranking.  
**Important:** This document defines the proposed scientific method. **The Burgers-v1 Validation Dossier is the artifact that must supply the measured evidence before LIVE.**

---

## Executive summary

Carbon does **not** treat any numerical solver as truth by definition.

For each Challenge, Carbon freezes a physical problem, a population of cases, a procedural case generator, a qualified reference path, a measurement suite, and a validator resource contract **before competition begins**. The reference must earn its authority through independent verification and uncertainty characterization. Only differences that are demonstrably larger than the combined numerical and statistical resolution of the exam are allowed to create a scientific winner or economic consequence.

Burgers v1 is the first concrete proof of this design because the reference is unusually strong: Carbon can procedurally generate fresh periodic Burgers initial conditions, use the periodic **Cole–Hopf solution** as the routine primary reference, and qualify that implementation against a methodologically independent, refined conservative solver.

The central separation is:

> **The case generator creates the questions.**  
> **The reference process creates the answer key.**

The generator is qualified by asking whether it samples the **registered problem distribution** correctly. The reference is qualified by asking whether its answers are accurate enough, across that distribution, for the scientific distinctions Carbon intends to reward.

---

# 1. The full validator-side exam flow

```text
MINER
submits a model-construction / training strategy
        ↓
VALIDATOR
independently reconstructs / trains the candidate
under the registered resource contract
        ↓
validator derives protected EVAL / STRESS seed material
        ↓
CASE GENERATOR
seed → fresh canonical Burgers initial condition u0(x)
        ↓
        ├──────────────────────────────→ CANDIDATE
        │                                  u0(x) → û(x,T)
        │
        └──────────────────────────────→ QUALIFIED REFERENCE
                                           u0(x) → Cole–Hopf → uref(x,T)
                                                     ↑
                                   independent refined solver qualified this path
        ↓
VALIDATOR-OWNED MEASUREMENTS
        ↓
mandatory physics gates
        ↓ pass
soft physics + robustness + accuracy
        ↓
ScoreInput
        ↓
registered Score Pack / ScoreEngine
        ↓
scientific evaluation result
```

The independent witness is primarily a **qualification instrument**. It does not need to run in the hot path for every miner evaluation once the exact pinned Cole–Hopf implementation has passed the Validation Dossier for the registered envelope.

The authoritative LIVE path is therefore intended to be computationally simple:

```text
hidden seed
   ↓
fresh physical case
   ↓
qualified Cole–Hopf reference + reconstructed candidate
   ↓
validator measurements
   ↓
registered scoring rules
```

---

# 2. What Carbon is actually claiming

Carbon does not need universal or metaphysical physical truth.

The relevant claim is narrower:

> **For this exact physical problem, this exact population of cases, this exact reference implementation, and this exact measurement process, the uncertainty is small enough that Carbon can distinguish candidate methods at the resolution being rewarded.**

That claim is falsifiable.

If the qualification campaign cannot demonstrate it, then the Challenge must remain pre-LIVE, narrow its envelope, coarsen its resolution, or return an indeterminate comparison.

This is the key connection between the science and the incentive mechanism:

> **Scientific resolution caps economic resolution.**

Carbon must not pay for a distinction the exam cannot resolve.

---

# 3. What the incentive mechanism is not allowed to reward

The official exam must not reward:

- reproduction of one privileged numerical solver’s idiosyncratic error;
- memorization or leakage of a fixed static benchmark;
- a miner-controlled test distribution or answer key;
- a physical-score advantage that sits below the numerical measurement floor;
- a rank difference smaller than the demonstrated reconstruction + evaluation uncertainty;
- performance gains produced by silently censoring hard cases or failed reference cases;
- differences that disappear under fresh common evidence.

If any of these can determine an economic winner, the Challenge is not scientifically ready for LIVE use.

---

# 4. Why one solver should not automatically be “truth”

Using high-fidelity solver data as the grading reference is often operationally sensible and will likely be necessary for future CFD, FEA, and multiphysics Challenges.

But a numerical solver still contains approximation choices:

- spatial discretization;
- timestep / temporal integration;
- nonlinear and iterative tolerances;
- numerical flux or scheme;
- mesh / grid;
- stabilization choices;
- implementation details;
- sometimes model-form assumptions.

If Carbon simply declares:

```text
Solver X output = truth
```

then the incentive mechanism is formally rewarding:

```text
Who best reproduces Solver X?
```

That may be an excellent proxy for the physical solution—but Carbon should **demonstrate the approximation quality**, not assume it.

The stronger rule is:

> **A solver may become the operational reference only after its uncertainty and failure regions are characterized tightly enough for the intended ranking decision.**

For Burgers, Carbon can do better than relying on one solver because Cole–Hopf provides an analytic/semi-analytic route.

---

# 5. Why Burgers is a good first proof

The proposed first Challenge is

\[
u_t + u\,u_x = \nu u_{xx}
\]

on a 1D periodic domain, with:

- fixed viscosity \(\nu = 5\times10^{-3}\);
- smooth periodic initial conditions;
- a fixed prediction horizon \(T\);
- a registered target population and stress strata;
- a fixed candidate output contract.

For v1, Carbon should use **zero-mean initial conditions**:

\[
\langle u_0 \rangle = 0.
\]

This should be a v1 requirement rather than an informal preference. The spatial mean is exactly conserved, while a non-zero mean mainly induces a Galilean translation. Zero mean therefore removes a largely trivial degree of freedom and makes the periodic Cole–Hopf construction cleaner and easier to qualify.

The exam is then:

```text
hidden seed
    ↓
fresh initial condition u0(x)
    ↓
    ├── candidate predicts û(x,T)
    │
    ├── qualified Cole–Hopf produces uref(x,T)
    │
    └── independent solver has already challenged / qualified that reference path
```

---

# 6. The case generator: how the questions are created

For Burgers, the procedural generator can define the initial condition using a bounded periodic Fourier representation:

\[
u_0(x)
=
\sum_{k=1}^{K}
\left[
a_k\cos\left(\frac{2\pi kx}{L}\right)
+
b_k\sin\left(\frac{2\pi kx}{L}\right)
\right].
\]

The **Challenge specification**, not the generator code, defines:

- allowed modes \(K\);
- coefficient distributions;
- correlations / conditional structure;
- amplitude limits;
- gradient limits;
- spectral-complexity limits;
- exclusions;
- ordinary and stress strata;
- target distribution \(P(x)\);
- finite SamplingPlan \(Q(x)\).

At runtime the validator-side generator:

1. receives protected role-separated seed material;
2. selects the registered stratum according to \(Q(x)\);
3. samples the Fourier coefficients from the registered conditional distribution;
4. applies deterministic envelope / exclusion rules;
5. constructs \(u_0(x)\);
6. verifies zero mean, periodicity, finiteness, support, and structural invariants;
7. binds the coefficients, physical case, versions, role, and provenance into an immutable case identity.

The generator returns the **physical question**. It does not decide the answer.

---

# 7. How the case generator is validated

The case generator is not validated against physical truth, because it is not claiming to solve the PDE.

It is validated against the **registered population and SamplingPlan**.

Carbon should retain empirical evidence for:

```text
registered coefficient distribution
            vs
realized coefficient distribution
```

and:

```text
registered stratum / stress allocation
            vs
realized allocation
```

plus:

- deterministic replay;
- marginal, joint, and conditional distribution conformance;
- support / exclusion compliance;
- boundary coverage;
- duplicate / near-duplicate rate;
- train / eval / stress isolation;
- generator failure rate by stratum;
- intended vs realized distribution after failures / censoring.

A generator can produce perfectly valid Burgers functions and still fail qualification if it samples the wrong scientific population.

---

# 8. The Burgers reference hierarchy

For v1:

```text
PRIMARY OPERATIONAL REFERENCE
periodic Cole–Hopf implementation

        ↓ qualification challenge

METHODOLOGICALLY INDEPENDENT WITNESS
refined conservative numerical solver
```

The witness exists to test the primary reference—not to vote on truth.

The discrepancy statistics between primary and witness become part of the Validation Dossier.

---

# 9. Cole–Hopf is mathematically strong, but its implementation still needs qualification

For zero-mean periodic \(u_0\), let a periodic potential \(F\) satisfy

\[
F_x = u_0,
\]

and define

\[
\phi_0(x)=\exp\left[-\frac{F(x)}{2\nu}\right].
\]

Then \(\phi\) satisfies the heat equation

\[
\phi_t = \nu \phi_{xx},
\]

and Burgers can be recovered through

\[
u_{\text{ref}}(x,t)=-2\nu\frac{\phi_x}{\phi}.
\]

This gives Carbon an unusually strong reference path—but **the numerical implementation is not automatically exact**.

At small \(\nu\), the exponential transform can become strongly conditioned: \(\phi\) may span a very large dynamic range or approach machine zero in difficult cases. The qualification campaign must therefore explicitly map this sensitivity.

The Cole–Hopf implementation must demonstrate, across the registered envelope:

- stable recovery of \(u_0\) at \(t=0\) to the representation floor;
- periodicity;
- mean conservation;
- invariance to harmless rescaling of \(\phi\);
- Fourier / quadrature / truncation convergence;
- precision sensitivity;
- back-transform conditioning;
- failure / unreliable regions.

Where required, the implementation should use numerically stable rescaling, log-domain techniques, or higher precision. Regions that remain ill-conditioned must be excluded, assigned elevated uncertainty, or block LIVE use.

---

# 10. What “independent witness” must mean

The witness must be **methodologically independent**, not merely a second file calling similar numerical machinery.

The qualification plan should prefer:

- a different spatial discretization family;
- a different time integrator;
- a distinct code path / codebase;
- preferably a separate implementation owner or review path;
- no shared use of the same dominant approximation mechanism where avoidable.

For example, if the Cole–Hopf implementation uses FFT / spectral operations to evolve the heat equation, a conservative finite-volume or high-order finite-difference Burgers solver is a stronger witness than another pseudo-spectral Burgers implementation.

For the same prospectively chosen audit cases, the witness campaign should record:

- spatial-refinement sequence;
- timestep-refinement sequence;
- solver-tolerance sensitivity;
- observed convergence behavior;
- conservation / balance diagnostics;
- primary-vs-witness field discrepancies;
- discrepancies by stress stratum;
- all failures / conditioning events.

The witness disagreement distribution is itself evidence. It is not averaged away.

---

# 11. Uncertainty floor and minimum resolvable improvement

This is the quantitative answer to “how close to truth is close enough?”

The Burgers qualification campaign must produce an explicit uncertainty / resolution budget.

At minimum it must characterize:

### A. Reference uncertainty

For each audit case or scientifically relevant stratum, estimate the discrepancy between the qualified Cole–Hopf implementation and the refined independent witness on the quantities Carbon actually uses.

For example:

\[
\delta_{\text{ref},i}
=
\frac{
\|u_{\text{CH},i}(T)-u_{\text{wit},i}(T)\|_2
}{
\max(\|u_{\text{CH},i}(T)\|_2,\epsilon_A)
}.
\]

The dossier must report its distribution, tails, and regime dependence—not just one mean.

### B. Measurement floor

For every physics / accuracy measurement, determine the numerical floor produced by reference resolution, interpolation, quadrature, finite precision, and the measurement implementation itself.

A mandatory gate or soft-score scale must not claim meaningful discrimination below this floor.

### C. Reconstruction uncertainty

If training is stochastic, reconstruct the same representative strategy under multiple authorized reconstruction seeds and measure the spread in the final estimands / scores.

### D. Finite-exam uncertainty

Repeat evaluation on fresh hidden case sets drawn under the registered SamplingPlan and measure how much scores / ranks vary because the exam is finite.

### E. Minimum resolvable improvement

The Challenge must prospectively define a **minimum resolvable improvement** or contested band based on the combined evidence above.

Conceptually:

```text
reference uncertainty
+ measurement uncertainty
+ reconstruction variability
+ finite-exam variability
        ↓
minimum scientifically resolvable difference
```

Carbon does not need one universal formula for combining these terms. The method must be statistically justified for the Challenge.

The operational rule is simpler:

> **A candidate difference smaller than the demonstrated resolution cannot create a scientific frontier advance or sharper economic reward.**

A reviewer should be able to inspect the Burgers Validation Dossier and see actual numbers for this floor.

---

# 12. Resource contract and determinism

The validator must reconstruct each strategy under a registered resource contract so the comparison is not confounded by unequal compute.

The contract should bind, as applicable:

- training data / generation budget;
- optimizer-step / epoch budget;
- wall-clock / accelerator budget where relevant;
- permitted model / training interfaces;
- reconstruction seed policy;
- software / hardware profile.

If reconstruction contains nondeterminism, Carbon should not pretend it does not exist. It becomes a measured source of experimental variance and contributes to the minimum resolvable improvement.

The right standard is therefore not necessarily bit-for-bit identical learned weights. It is **decision reproducibility**: outside the registered contested band, the admissibility / ranking decision should remain stable under the qualified reconstruction process.

---

# 13. Adversarial reference-bias test

Hidden cases protect against memorizing exact answers, but they do not by themselves prevent a sophisticated miner from learning the **class of bias** of a known operational reference.

Carbon should therefore make the reference-bias falsification test operational.

Before LIVE, construct at least two controlled candidate families:

```text
Candidate G
trained / designed to imitate a weaker or deliberately biased production-style solver

Candidate R
trained / designed to track the stronger qualified Cole–Hopf reference
```

Evaluate both through the proposed hidden exam and scoring path.

Required result:

> **A candidate that exploits known weaker-solver bias must not systematically outrank a candidate that follows the stronger qualified reference.**

If it does, the measurement / scoring path is rewarding reference artifacts rather than the intended physical objective and must be repaired before LIVE.

This adversarial campaign should include more than one plausible bias mode where practical—for example excess numerical diffusion or phase / gradient error in steepening regimes.

---

# 14. How physics enters the Burgers score

Carbon should separate:

1. **mandatory physical admissibility**, and
2. **soft physics fidelity among candidates that are already admissible**.

Some physical properties are poor continuous reward targets because “more” does not mean “more correct.”

## Recommended v1 hard / diagnostic checks

### Finite output

NaN / Inf means there is no valid scientific prediction.

### Energy non-increase

For unforced viscous Burgers,

\[
E(u)=\frac12\langle u^2\rangle
\]

and

\[
E(T)\le E(0).
\]

But excess dissipation is not greater fidelity. An over-diffusive model may satisfy this inequality strongly while being wrong. Therefore energy non-increase is best used as a **mandatory gate / diagnostic**, not a “more is better” soft reward.

### Maximum-principle consistency

The viscous solution should not create unphysical extrema outside the qualified initial range. Again, being deeper inside that range is not automatically better, so this is best treated as a **gate / diagnostic**.

### Mean conservation

For periodic Burgers,

\[
\langle u(T)\rangle=\langle u_0\rangle.
\]

Mean conservation is suitable for both a hard admissibility threshold and a continuous defect measure.

---

# 15. Soft physics fidelity

Using a fixed Challenge-level velocity scale \(U_*\), define the mean-conservation defect

\[
\epsilon_M
=
\frac{
|\langle \hat u(T)\rangle-\langle u_0\rangle|
}{U_*}.
\]

For each qualified soft physics defect \(\epsilon_j\), Carbon’s current ScoreEngine transform is

\[
m_j
=
\begin{cases}
1-(\epsilon_j/\tau_j)^2, & \epsilon_j<\tau_j,\\
0, & \epsilon_j\ge\tau_j.
\end{cases}
\]

and

\[
S_{\text{physics}}
=
\sum_j \alpha_j m_j,
\qquad
\alpha_j>0,
\qquad
\sum_j\alpha_j=1.
\]

The \(\tau_j\) values are not guessed. They are Challenge-specific Score Pack values that must be supported by the Validation Dossier and sit above the qualified numerical / measurement floor.

For a final-state-only Burgers v1, Carbon should keep this soft physics leg deliberately narrow rather than claim that weak proxies are rich physics measurements.

If a later Challenge requires time slices or full trajectories, stronger physics measurements become available, including the viscous Burgers energy identity:

\[
E(T)-E(0)
+
\nu\int_0^T\int |u_x|^2\,dx\,dt
=0.
\]

A normalized defect in this identity—or a separately qualified weak / PDE residual—would provide a substantially stronger continuous physics-fidelity signal than one-sided energy monotonicity.

---

# 16. Accuracy

For hidden case \(i\), a natural qualified reference-field error is

\[
e_i
=
\frac{
\|\hat u_i(T)-u_{\text{ref},i}(T)\|_2
}{
\max(\|u_{\text{ref},i}(T)\|_2,\epsilon_A)
}.
\]

For zero-mean v1 cases this is relatively clean. The floor \(\epsilon_A\) must be fixed prospectively to avoid pathological normalization for very small reference norms.

This is the primary answer to:

> **How close is the candidate to the qualified reference field?**

---

# 17. Robustness: difficult but still valid physics

Robustness asks:

> **Does the candidate remain accurate when the physical case becomes difficult inside the registered envelope?**

The stress strata should therefore be derived from Burgers steepening / diffusion physics rather than arbitrary labels.

Useful prospective descriptors include:

### Spectral scale

\[
k_{\mathrm{rms}}
=
\left(
\frac{
\sum_k k^2|c_k|^2
}{
\sum_k|c_k|^2
}
\right)^{1/2}.
\]

### Velocity scale

\[
U_{\mathrm{rms}}=\sqrt{\langle u_0^2\rangle}.
\]

### Effective nonlinear-to-diffusive severity

\[
Re_{\mathrm{eff}}
\sim
\frac{U_{\mathrm{rms}}}{\nu k_{\mathrm{rms}}}.
\]

### Steepening index

\[
s
=
\max\left(0,-T\min_x u_0'(x)\right).
\]

These can prospectively define categories such as:

- ordinary;
- high spectral complexity;
- steep-gradient formation;
- combined edge-of-envelope cases.

For category \(c\), calculate the field errors \(e_i\) and summarize both mean and tail behavior:

\[
\mu_c=\mathrm{mean}(e_i\mid c),
\]

\[
q_c=Q_q(e_i\mid c).
\]

Blend them:

\[
r_c
=
b_{\mathrm{mean}}\mu_c
+b_{\mathrm{tail}}q_c,
\qquad
b_{\mathrm{mean}}+b_{\mathrm{tail}}=1.
\]

Carbon’s current robustness transform is

\[
t_c
=
\frac{1}{1+
\exp\left[
\kappa(r_c-\tau_R)/\tau_R
\right]},
\]

and

\[
S_{\text{robustness}}
=
\sum_c\gamma_ct_c,
\qquad
\gamma_c>0,
\qquad
\sum_c\gamma_c=1.
\]

The tail statistic is useful because an average can hide brittle failure.

But an empirical tail quantile is noisy when a category contains too few cases. The Validation Dossier must therefore specify a minimum effective sample size / uncertainty requirement for every score-bearing stress category.

If a category has insufficient evidence, Carbon should return **incomplete / indeterminate evidence**, not silently drop that category or renormalize the remaining weights.

---

# 18. Final score and current weight status

After all mandatory gates pass, the current top-level scoring form is

\[
S
=
S_{\text{physics}}^{w_P}
S_{\text{robustness}}^{w_R}
S_{\text{accuracy}}^{w_A},
\]

with

\[
w_P+w_R+w_A=1.
\]

The weighted geometric form is appropriate because a near-zero leg cannot be completely washed out by a strong score elsewhere.

However:

> **The current 45 / 30 / 25 physics / robustness / accuracy split is a P0 design prior, not a scientifically established Burgers result.**

Production weights should only be frozen after measurement qualification, score-sensitivity analysis, and rank-stability studies.

If the Burgers-v1 soft physics leg remains intentionally narrow, the evidence campaign should specifically test whether giving it a large top-level exponent produces the intended scientific ranking rather than overweighting one proxy.

---

# 19. How the same architecture generalizes beyond Burgers

Burgers is special because Carbon has a strong analytic/semi-analytic primary reference. Future engineering Challenges may not.

The architecture still applies:

```text
PRIMARY HIGH-FIDELITY SOLVER
candidate operational reference
        ↓
REFERENCE QUALIFICATION
code / solution verification
manufactured or analytic cases where available
grid / timestep convergence
solver-tolerance studies
conservation / balance checks
cross-code comparison where feasible
experimental / partner evidence where available
        ↓
CHARACTERIZED UNCERTAINTY + FAILURE ENVELOPE
        ↓
QUALIFIED OPERATIONAL REFERENCE
        ↓
hidden fresh exam
```

The strength of Carbon’s scientific claim must track the strength of this evidence.

A high-fidelity CFD solver can therefore become the primary operational answer source—but only for the envelope and resolution its evidence supports.

This is consistent with the logic of established verification / validation / uncertainty-quantification practice: numerical authority is earned by verification evidence and bounded uncertainty, not by solver reputation alone.

---

# 20. The pre-LIVE falsification standard

Before Burgers v1 is allowed to create an economic winner, Carbon must attach measured evidence to all of the following:

1. **Generator distribution:** the case generator statistically matches the registered initial-condition population and SamplingPlan.
2. **Cole–Hopf qualification:** the implementation remains numerically stable across the registered envelope, including mapped back-transform / conditioning limits.
3. **Witness agreement:** the methodologically independent refined solver agrees with Cole–Hopf within a characterized discrepancy distribution.
4. **Measurement floors:** mandatory thresholds and soft-score scales sit above their qualified numerical / reference floors.
5. **Stress evidence:** every score-bearing stress stratum has enough hidden evidence to support its mean / tail estimands.
6. **Reconstruction variability:** repeated independent reconstruction measures any stochastic training variability under the registered resource contract.
7. **Finite-exam variability:** fresh repeated exams quantify sampling-driven score / rank uncertainty.
8. **Minimum resolvable improvement:** Carbon derives and registers a scientific contested band / improvement threshold from the above evidence.
9. **Reference-bias adversary:** a candidate designed to reproduce weaker-solver bias cannot systematically outrank one that follows the stronger qualified reference.
10. **No silent censoring:** hard cases, reference failures, and infrastructure failures remain visible and cannot reshape the realized exam population unnoticed.

If these tests do not pass, the Challenge remains pre-LIVE.

---

# 21. The Validation Dossier is the gate to LIVE

This document is an architecture and scientific-method statement. It is **not evidence that Burgers v1 has already achieved the required resolution**.

The next concrete scientific deliverable is the Burgers-v1 Validation Dossier.

It must report actual measured values for at least:

- generator distribution diagnostics;
- Cole–Hopf implementation convergence / conditioning;
- independent-witness discrepancy statistics;
- uncertainty / numerical floors by measurement and stratum;
- stress-category sample sufficiency;
- reconstruction variance;
- finite-evaluation variance;
- score / rank stability;
- adversarial reference-bias tests;
- minimum resolvable improvement / contested band;
- explicit limitations and blocked regions.

The Challenge should remain **PRE-LIVE** until those numbers exist, pass review, and are bound to the exact Challenge / generator / reference / measurement / Score Pack identities.

That is not a caveat around Carbon’s trust claim. It is the trust mechanism:

> **Carbon refuses to create an economic winner until the exam itself has earned the right to judge one.**

---

## Bottom line

> **The generator creates fresh valid questions from a registered physical distribution.**  
> **The reference process independently establishes the best qualified answer for each question.**  
> **The reference must have measured uncertainty smaller than the distinctions Carbon rewards.**  
> **Physics gates reject scientifically unacceptable behavior.**  
> **Soft physics, robustness, and accuracy differentiate the candidates that survive.**  
> **And if the evidence cannot distinguish two methods, the incentive mechanism is not allowed to manufacture a winner.**

That is the scientific basis for Carbon’s independent exam.

---

## Technical basis

Carbon’s reference-qualification method is intended to follow the logic of established verification, validation, and uncertainty-quantification practice, including:

- C. J. Roy, *Review of code and solution verification procedures for computational simulation*, Journal of Computational Physics 205 (2005), 131–156.
- C. J. Roy and W. L. Oberkampf, *A comprehensive framework for verification, validation, and uncertainty quantification in scientific computing*, Computer Methods in Applied Mechanics and Engineering 200 (2011), 2131–2144.
- ASME V&V 20, *Verification and Validation in Computational Fluid Dynamics and Heat Transfer*.
- Standard Cole–Hopf theory for viscous Burgers.
- Carbon internal specifications: `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, and `Challenge_Instance_Distribution.md`.