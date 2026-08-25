# Carbon’s Independent Physics Exam
## Burgers v1 — how the exam creates fresh questions, a qualified answer key, and a defensible economic signal

Paul,

I thought more about the concern you raised around whether Carbon can really evaluate against “truth data” or data close enough to truth.

The cleanest way to explain the design is to separate two jobs:

> **The case generator creates the questions.**  
> **The reference process creates the answer key.**

Carbon does **not** treat any solver as truth by definition. For each Challenge, it freezes the physical problem, the population of cases, the case generator, the reference path, and the measurement suite before competition. The reference then has to **earn authority** through independent verification and uncertainty characterization.

For Burgers v1, the proposed primary reference is periodic Cole–Hopf, cross-checked against a methodologically independent refined numerical solver. The resulting uncertainty floor must sit below the resolution at which ranking and reward occur.

If it does not, the Challenge remains pre-LIVE.

---

# 1. The full validator-side exam flow

For the official exam, the entire authoritative path runs through pinned validator-side code.

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
                         independent refined solver qualified this path pre-LIVE
        ↓
VALIDATOR MEASUREMENTS
compare û(x,T), uref(x,T), and u0(x)
        ↓
mandatory physics gates
+ soft physics fidelity
+ robustness across hard strata
+ reference-field accuracy
        ↓
ScoreInput
        ↓
registered Score Pack / ScoreEngine
        ↓
scientific evaluation result
```

The miner does **not** submit a self-graded model and does **not** control:

- official evaluation cases;
- official evaluation seeds;
- official reference solutions;
- official physics measurements;
- official scoring thresholds.

The validator reconstructs the candidate, generates the hidden physical cases, computes the qualified reference on those same cases, and performs the registered measurements.

---

# 2. What Carbon is actually trying to prove

Carbon does not need universal physical truth.

For each Challenge, it needs to establish a narrower and testable claim:

> **For this exact physical problem, this exact population of cases, and this exact measurement process, the reference is accurate enough that Carbon can distinguish candidate methods at the resolution being rewarded.**

That means Carbon must know not only a score, but also the **resolution of the experiment**.

If two candidates differ by less than that resolution, the exam has no scientific authority to manufacture a winner.

---

# 3. Why one solver should not automatically be “truth”

Using high-fidelity solver data directly as the grading reference makes sense operationally, especially for future CFD or FEA Challenges.

But a numerical solver still contains approximation choices:

- spatial discretization;
- timestep;
- nonlinear and iterative tolerances;
- numerical scheme;
- mesh or grid;
- implementation details;
- sometimes model-form assumptions.

If Carbon says:

```text
Solver X output = truth
```

then the mechanism is really rewarding:

```text
Who best reproduces Solver X?
```

That may be close to the physical solution, but Carbon should **demonstrate that relationship rather than assume it**.

The stronger architecture is:

```text
fresh physical case
        ↓
primary reference candidate
        ↓
independent verification + uncertainty characterization
        ↓
qualified reference
        ↓
candidate grading
```

For future industrial Challenges, the primary reference may absolutely be a high-fidelity solver.

The difference is that the solver **earns authority**.

---

# 4. Why Burgers is a strong first proof

The proposed first Challenge is:

\[
u_t + u\,u_x = \nu u_{xx}
\]

with:

- a 1D periodic domain;
- fixed viscosity \(\nu = 5\times10^{-3}\);
- smooth periodic initial conditions;
- a fixed prediction time \(T\).

For v1, Carbon should use **zero-mean initial conditions**:

\[
\langle u_0 \rangle = 0
\]

This removes a mostly trivial Galilean translation and makes the periodic Cole–Hopf construction cleaner and easier to qualify.

The physical exam for one hidden case is:

```text
hidden eval seed
    ↓
fresh initial condition u0(x)
    ↓
    ├── candidate predicts û(x,T)
    │
    ├── Cole–Hopf produces uref(x,T)
    │
    └── independent high-resolution solver has qualified / cross-checked
        the Cole–Hopf reference path before LIVE
```

The key distinction is:

> **The case generator is verified against the registered problem distribution.**  
> **The reference process is verified for numerical / analytic accuracy.**

Those are two different scientific questions.

---

# 5. How the case generator is built and validated

For Burgers, the initial condition can be generated procedurally using a bounded periodic Fourier representation:

\[
u_0(x)
=
\sum_{k=1}^{K}
\left[
a_k\cos\left(\frac{2\pi kx}{L}\right)
+
b_k\sin\left(\frac{2\pi kx}{L}\right)
\right]
\]

The Challenge specification — not the generator code itself — defines:

- allowed modes \(K\);
- coefficient distributions;
- correlations;
- amplitude limits;
- gradient limits;
- spectral-complexity limits;
- exclusions;
- ordinary and stress strata.

At runtime:

```text
protected seed
    ↓
SamplingPlan selects a registered stratum
    ↓
Fourier coefficients are sampled
    ↓
physical constraints / exclusions are applied
    ↓
canonical u0(x) is constructed
    ↓
case identity + provenance are bound
```

The generator is then audited against the registered specification.

Carbon checks:

- empirical vs registered coefficient distributions;
- empirical vs registered joint / conditional structure;
- stress-stratum allocation;
- deterministic replay;
- support and exclusion compliance;
- duplicate / near-duplicate rate;
- boundary coverage;
- train / eval / stress seed isolation;
- failure and censoring rates.

So generator validity is a **distribution-conformance and software-integrity problem**, not a “truth” problem.

---

# 6. How the reference is qualified

For Burgers v1, the strongest hierarchy is:

```text
PRIMARY REFERENCE
periodic Cole–Hopf implementation

        ↓ cross-check

INDEPENDENT WITNESS
high-resolution conservative numerical solver
```

The witness should be **methodologically independent**, not just a second wrapper around the same numerical machinery.

Where feasible, it should differ in:

- spatial discretization family;
- time integration method;
- codebase / implementation path;
- numerical representation.

If the Cole–Hopf implementation relies heavily on Fourier / FFT machinery, a conservative finite-volume or otherwise numerically distinct witness is preferable to a second spectral solver.

The discrepancy statistics between the two are part of the Validation Dossier.

For the registered audit cases, Carbon measures:

- Cole–Hopf vs witness field discrepancy;
- spatial refinement sensitivity;
- temporal refinement sensitivity;
- solver-tolerance sensitivity;
- conservation behavior;
- hard-regime disagreement;
- failure / conditioning regions.

If they disagree materially, Carbon must:

- investigate;
- narrow the envelope;
- weaken the claim;
- increase the uncertainty;
- or block that region from LIVE use.

It must **not** average away disagreement to manufacture an answer.

---

# 7. Cole–Hopf is strong, but its implementation still needs qualification

For zero-mean periodic \(u_0\), define a periodic potential \(F_x=u_0\) and:

\[
\phi_0(x)=\exp\left[-\frac{F(x)}{2\nu}\right]
\]

Then:

\[
\phi_t=\nu\phi_{xx}
\]

and:

\[
u_{\text{ref}}
=
-2\nu\frac{\phi_x}{\phi}
\]

This is mathematically powerful because Burgers is reduced to the heat equation.

But the **implemented** Cole–Hopf reference is still numerical.

At small viscosity, the exponential can become badly conditioned in some regimes. Carbon therefore has to map:

- transform conditioning;
- truncation / resolution sensitivity;
- precision sensitivity;
- regions where \(\phi\) approaches numerical underflow;
- reference disagreement in hard cases.

Those regions must either remain inside a demonstrated uncertainty budget or be excluded from the qualified envelope.

This is why “analytic transform” does not mean “unqualified truth implementation.”

---

# 8. Uncertainty floor and minimum resolvable improvement

This is the core answer to “how close to truth is close enough?”

The pre-LIVE qualification campaign must produce a quantitative uncertainty budget.

At minimum, Carbon needs:

1. **Reference discrepancy**  
   Distribution of Cole–Hopf vs independent-witness error across the registered envelope and stress strata.

2. **Measurement floor**  
   Numerical uncertainty associated with the actual measurements used by the Score Pack.

3. **Reconstruction variability**  
   Variation caused by independently retraining / reconstructing the same strategy with fresh registered training seeds.

4. **Finite-exam variability**  
   Variation in scores caused by fresh hidden evaluation draws.

Conceptually:

\[
U_{\text{exam}}
=
f(
U_{\text{reference}},
U_{\text{measurement}},
U_{\text{reconstruction}},
U_{\text{sampling}}
)
\]

The exact combination is Challenge-specific and should be established statistically rather than assumed.

Carbon then derives a **minimum resolvable improvement**.

A frontier or economic winner may only be created when the observed improvement clears the registered resolution rule with the required confidence / stability.

> **Scientific resolution caps economic resolution.**

If the exam can only resolve a 2% improvement reliably, the mechanism cannot defend paying for a 0.2% floating-point lead.

---

# 9. Resource contract and determinism

The validator-side reconstruction and evaluation process must also be scientifically controlled.

Before competition, Carbon registers the resource contract:

- allowed training data budget;
- reconstruction steps / compute budget;
- model-family constraints where applicable;
- numerical backend profile;
- evaluation case count;
- stress allocation.

The same strategy may still produce variation because modern training can be stochastic.

That non-determinism is **not ignored**.

It is measured through repeated reconstruction and included in the scientific-resolution study.

Where exact deterministic execution is feasible, exact replay should be required.

Where only decision-level reproducibility is feasible, Carbon must demonstrate that the final gate / rank decision is stable outside the registered contested band.

---

# 10. The full submission and evaluation process

## Step 1 — Carbon freezes the scientific Challenge

Before miners compete, Carbon registers:

- Burgers equation and fixed viscosity;
- domain, BCs, IC population, and output contract;
- target population \(P(x)\);
- SamplingPlan \(Q(x)\);
- ordinary and stress strata;
- case-generator version;
- qualified Cole–Hopf reference implementation;
- measurement definitions;
- mandatory gates;
- soft-score transforms;
- resource contract.

These are prospective, versioned scientific inputs.

They are not changed after seeing who wins.

## Step 2 — Miner submits a construction strategy

The miner submits a declarative training / construction strategy describing how the candidate should be built inside the allowed search space.

The miner does not supply the official grade.

## Step 3 — Validator independently reconstructs the candidate

The validator executes the registered construction process under the resource contract using validator-controlled fresh training realization(s).

The graded artifact is therefore the validator’s reconstruction of the submitted method.

## Step 4 — Validator generates the hidden exam

Protected EVAL / STRESS seed material enters the pinned case generator.

Fresh canonical Burgers cases are created according to the registered SamplingPlan.

## Step 5 — Validator computes the reference for each hidden case

Each canonical \(u_0(x)\) is passed to the exact pinned, qualified Cole–Hopf implementation:

\[
u_0(x)
\rightarrow
u_{\text{ref}}(x,T)
\]

The independent witness is primarily a **pre-LIVE qualification instrument**. It does not need to run for every miner evaluation unless policy or monitoring requires it.

## Step 6 — Candidate solves the same hidden cases

The same canonical case is materialized into the candidate representation:

\[
u_0(x)
\rightarrow
\hat u(x,T)
\]

Reference and candidate therefore solve the same registered physical problem.

## Step 7 — Validator computes the scientific measurements

The validator has:

```text
u0(x)
û(x,T)
uref(x,T)
```

Registered measurement code computes:

- finite-output status;
- mean-conservation defect;
- energy behavior;
- maximum-principle consistency;
- reference-field error;
- stress-stratum field-error summaries.

## Step 8 — Mandatory admissibility is applied first

If a mandatory physics gate fails:

```text
candidate inadmissible
        ↓
combined score = 0
        ↓
not eligible for scientific reward
```

Accuracy cannot rescue a mandatory scientific failure.

## Step 9 — Soft score is calculated for admissible candidates

The validator constructs the authorized ScoreInput.

The Score Pack computes:

```text
S_physics
S_robustness
S_accuracy
        ↓
weighted geometric combination
        ↓
combined scientific score
```

## Step 10 — Ranking nominates; frontier promotion confirms

Ordinary hidden evaluation nominates strong contenders.

For leader replacement, the incumbent and contender should be reconstructed / evaluated on the **same fresh common promotion evidence**.

The result is:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

A floating-point lead alone is not a scientific frontier advance.

---

# 11. What the incentive mechanism is not allowed to reward

Carbon should explicitly prohibit economic reward for:

- reproduction of a single privileged solver’s numerical idiosyncrasies;
- memorization or leakage of a static official benchmark;
- candidate-controlled official grading data;
- performance differences smaller than the demonstrated numerical + statistical resolution of the exam;
- apparent gains created by reference failure or selective censoring of difficult cases;
- floating-point rank differences that do not survive fresh common evidence.

---

# 12. Why this design fits Carbon’s incentive mechanism

Carbon needs an exam that is both:

1. **fresh**, so repeated economic optimization cannot simply memorize a finite answer key; and  
2. **objectively gradeable**, so scientific authority is not discretionary.

A static benchmark gives easy grading but becomes increasingly vulnerable to leakage and specialization.

A fresh case generator solves the freshness problem.

An independently qualified reference solves the answer-key problem.

Together:

```text
fresh hidden case
+
independently qualified answer
=
repeatable scientific exam
```

That gives Carbon:

- hidden official cases;
- exact replay after evaluation;
- no miner control over the exam;
- no miner control over the reference;
- a common physical contract;
- explicit uncertainty;
- an indeterminate state when evidence is insufficient;
- a direct evidence chain from physical case to economic result.

---

# 13. Adversarial reference-bias test

Hidden cases alone do not eliminate every gaming risk.

A sophisticated miner may try to learn systematic bias in the operational reference implementation.

Carbon should therefore include a direct adversarial qualification test:

```text
Candidate A
trained / tuned to imitate a weaker biased production solver

Candidate B
tracks the stronger qualified reference

        ↓

run both through the proposed official measurement + scoring path
```

Candidate A must not outrank Candidate B because the exam rewards a reference artifact.

If it can, the Challenge is not ready.

This test should be executable across the audit set, not merely a thought experiment.

---

# 14. How the same hierarchy generalizes beyond Burgers

Burgers is unusually convenient because Cole–Hopf gives a strong primary reference.

Future engineering Challenges may instead use:

```text
PRIMARY HIGH-FIDELITY SOLVER
candidate for reference
        ↓
verification + UQ
        ├── manufactured / analytic cases where available
        ├── grid / mesh refinement
        ├── timestep refinement
        ├── tolerance / scheme sensitivity
        ├── conservation / balance checks
        ├── independent cross-code comparison
        └── experimental / partner evidence where available
        ↓
CHARACTERIZED RESIDUAL UNCERTAINTY
        ↓
QUALIFIED OPERATIONAL REFERENCE
        ↓
hidden candidate grading
```

So Burgers is not a special exception to the architecture.

It is simply the cleanest first demonstration of the same rule:

> **Reference authority is earned by evidence.**

---

# 15. How physics should enter the Burgers score

Carbon should separate **hard physical admissibility** from **soft physics fidelity**.

Some properties are bad continuous rewards because “more” does not mean “more correct.”

## Recommended hard / diagnostic checks

### Finite output

A candidate containing NaN or Inf has no valid scientific result.

### Energy non-increase

For unforced viscous Burgers:

\[
E(u)=\frac12\langle u^2\rangle
\]

and:

\[
E(T)\le E(0)
\]

But a model should not earn extra credit simply for dissipating more energy.

An over-diffusive model may satisfy this strongly while being inaccurate.

Therefore this is better as a **mandatory gate / diagnostic**.

### Maximum-principle consistency

The viscous solution should not create unphysical new extrema outside the qualified initial range.

Being further inside the range is not evidence of greater fidelity.

So this is also better as a **gate / diagnostic**.

---

# 16. Soft physics fidelity for Burgers

The clearest final-state soft physics quantity is mean-conservation defect.

For periodic Burgers:

\[
\langle u(T)\rangle = \langle u_0\rangle
\]

Define:

\[
\epsilon_M
=
\frac{
\left|
\langle \hat u(T)\rangle-\langle u_0\rangle
\right|
}{
U_*
}
\]

where \(U_*\) is a fixed Challenge-level velocity scale.

For any qualified soft physics defect \(\epsilon_j\), Carbon’s current transform is:

\[
m_j
=
\begin{cases}
1-(\epsilon_j/\tau_j)^2, & \epsilon_j < \tau_j \\
0, & \epsilon_j \ge \tau_j
\end{cases}
\]

Then:

\[
S_{\text{physics}}
=
\sum_j \alpha_j m_j
\]

with:

\[
\sum_j \alpha_j=1
\]

The threshold \(\tau_j\) is not guessed.

It is derived from the Validation Dossier and must be above the numerical / reference floor.

For final-state-only Burgers v1, it is better to keep the soft physics leg narrow than to pretend weak proxies are rich physical evidence.

If Carbon later requires trajectories, a stronger soft physics measurement becomes possible through the Burgers energy balance:

\[
E(T)-E(0)
+
\nu
\int_0^T
\int
u_x^2
\,dx\,dt
=
0
\]

A normalized defect in this identity would be significantly stronger than simple one-sided energy monotonicity.

---

# 17. Accuracy

For hidden case \(i\):

\[
e_i
=
\frac{
\|\hat u_i(T)-u_{\text{ref},i}(T)\|_2
}{
\max\left(
\|u_{\text{ref},i}(T)\|_2,
\epsilon_A
\right)
}
\]

This answers:

> **How close is the reconstructed model to the qualified reference?**

---

# 18. Robustness

Robustness asks:

> **Does the model remain accurate when the physical problem becomes difficult?**

Burgers stress strata should be defined from steepening / diffusion physics rather than arbitrary “hard case” labels.

Useful prospective descriptors include:

### Spectral scale

\[
k_{\mathrm{rms}}
=
\left(
\frac{
\sum_k k^2 |c_k|^2
}{
\sum_k |c_k|^2
}
\right)^{1/2}
\]

### Velocity scale

\[
U_{\mathrm{rms}}
=
\sqrt{\langle u_0^2\rangle}
\]

### Effective nonlinear-to-diffusive severity

\[
Re_{\mathrm{eff}}
\sim
\frac{
U_{\mathrm{rms}}
}{
\nu k_{\mathrm{rms}}
}
\]

### Steepening index

\[
s
=
\max\left(
0,
-T\min_x u_0'(x)
\right)
\]

These can define prospectively registered strata such as:

- ordinary;
- high spectral complexity;
- steep-gradient formation;
- combined edge-of-envelope cases.

For stress category \(c\), compute field errors \(e_i\):

\[
\mu_c=\mathrm{mean}(e_i\mid c)
\]

and tail error:

\[
q_c=Q_q(e_i\mid c)
\]

Blend them:

\[
r_c
=
b_{\mathrm{mean}}\mu_c
+
b_{\mathrm{tail}}q_c
\]

Then Carbon’s current robustness transform is:

\[
t_c
=
\frac{
1
}{
1+
\exp
\left[
\kappa
(r_c-\tau_R)/\tau_R
\right]
}
\]

and:

\[
S_{\text{robustness}}
=
\sum_c
\gamma_c t_c
\]

with:

\[
\sum_c\gamma_c=1
\]

The tail statistic matters because an average can hide brittle behavior.

But tail quantiles are themselves noisy with small sample counts.

Therefore the Validation Dossier must register:

- minimum effective sample size per stress category;
- uncertainty of the selected tail quantile;
- the policy for insufficient category evidence.

Insufficient evidence should produce an incomplete / indeterminate scientific state, not silent renormalization.

---

# 19. Final incentive score

After all mandatory physics gates pass:

\[
S
=
S_{\text{physics}}^{w_P}
S_{\text{robustness}}^{w_R}
S_{\text{accuracy}}^{w_A}
\]

with:

\[
w_P+w_R+w_A=1
\]

The weighted geometric form is useful because a very weak leg cannot be completely washed out by a strong one.

However, the current 45 / 30 / 25 physics / robustness / accuracy split should **not** be presented as scientifically established.

Production weights should be locked only after:

- measurement qualification;
- construct-validity analysis;
- sensitivity testing;
- rank-stability analysis;
- the Burgers evidence campaign.

---

# 20. The pre-LIVE falsification standard

Before Burgers can create an economic winner, Carbon must attach measured evidence to all of the following:

1. **Generator conformance**  
   The case generator statistically matches the registered initial-condition population and stress allocation.

2. **Cole–Hopf stability**  
   The exact pinned implementation is numerically stable throughout the qualified envelope, including its conditioning limits.

3. **Independent witness agreement**  
   A methodologically independent refined solver agrees with Cole–Hopf within a characterized discrepancy budget.

4. **Measurement floor**  
   Physics and accuracy thresholds sit above the qualified numerical / reference floor.

5. **Tail sufficiency**  
   Hidden stress strata contain enough evidence for meaningful tail estimates.

6. **Reconstruction / exam stability**  
   Repeated reconstruction and fresh exams establish a minimum resolvable improvement.

7. **Reference-bias attack**  
   A candidate that imitates weaker solver bias cannot beat one that follows the stronger qualified reference.

8. **Censoring integrity**  
   Difficult cases do not disappear through reference failure, timeout, or retry in a way that reshapes the exam.

Until these have measured values and pass the registered criteria, the Challenge remains pre-LIVE.

---

# 21. The next concrete deliverable

The architecture is not the proof.

The next proof artifact is the **Burgers-v1 Validation Dossier**.

It should report, at minimum:

```text
generator distribution diagnostics
Cole–Hopf implementation qualification
independent-witness discrepancy statistics
reference uncertainty by regime
measurement numerical floors
stress-tail sample sufficiency
reconstruction variance
fresh-exam variance
minimum resolvable improvement
adversarial solver-bias results
failure / censoring map
```

Only after that evidence package passes scientific review should Burgers v1 be allowed to create an economic winner.

> **Evidence gates LIVE. Architecture does not.**

---

## Bottom line

The most defensible description of Carbon is:

> **The generator creates fresh valid questions from a registered physical distribution.**  
> **The reference process independently establishes the best available answer for each question.**  
> **The reference earns authority through verification and uncertainty characterization.**  
> **Physics gates reject scientifically unacceptable behavior.**  
> **Soft physics and robustness distinguish quality among candidates that survive.**  
> **And the incentive mechanism only rewards differences larger than the demonstrated resolution of the exam.**

That is the standard required if Carbon is going to attach economic consequences to a scientific claim.

---

### Technical basis

- C. J. Roy, *Review of code and solution verification procedures for computational simulation*, Journal of Computational Physics 205 (2005), 131–156.
- C. J. Roy and W. L. Oberkampf, *A comprehensive framework for verification, validation, and uncertainty quantification in scientific computing*, CMAME 200 (2011), 2131–2144.
- ASME V&V 20, *Verification and Validation in Computational Fluid Dynamics and Heat Transfer*.
- Standard Cole–Hopf theory for viscous Burgers.
- Carbon internal specifications: `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, and `Challenge_Instance_Distribution.md`.