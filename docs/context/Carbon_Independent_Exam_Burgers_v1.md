# Carbon’s Independent Physics Exam
## Why the generator/reference design is appropriate for the incentive mechanism

Nasir,

I thought more about the question you raised around using solver data as the “truth” source.

I think the cleanest way to explain Carbon is to separate two jobs that I blurred together on the call:

> **The generator creates the questions.  
> The reference process creates the answer key.**

That distinction is the core of the design.

---

## 1. What Carbon is actually trying to prove

Carbon does **not** need to prove universal physical truth.

For each Challenge, it needs to establish something narrower:

> **For this exact physical problem, this exact population of cases, and this exact measurement process, the reference is accurate enough that Carbon can fairly distinguish candidate methods at the resolution being rewarded.**

If Carbon cannot show that, then the exam should not create an economic winner.

That is the standard I think the incentive mechanism needs.

---

## 2. Why one solver should not automatically be “truth”

Your suggestion of using solver data directly as the grading reference makes sense operationally, especially for harder CFD or FEA problems.

But I do not think Carbon should treat one solver as truth **by definition**.

A numerical solver still contains approximation choices:

- spatial discretization;
- timestep;
- nonlinear and iterative tolerances;
- numerical scheme;
- mesh or grid;
- implementation details;
- sometimes model-form assumptions.

If Carbon simply says:

```text
Solver X output = truth
```

then the incentive mechanism is really rewarding:

```text
Who best reproduces Solver X?
```

That may be close to the physical solution, but Carbon should demonstrate that rather than assume it.

So the stronger architecture is:

```text
fresh physical case
        ↓
primary reference
        ↓
independent numerical / analytic check
        ↓
characterized uncertainty
        ↓
candidate grading
```

For future industrial Challenges, the primary reference may absolutely be a high-fidelity solver.

The difference is that the solver **earns authority** through verification and uncertainty characterization instead of receiving authority because of its name.

---

# 3. Why Burgers is a good first proof

For the first Challenge, Carbon can choose a problem where the reference is unusually strong.

The proposed v1 problem is:

\[
u_t + u\,u_x = \nu u_{xx}
\]

with:

- a 1D periodic domain;
- fixed viscosity \(\nu = 5\times10^{-3}\);
- smooth periodic initial conditions;
- a fixed prediction time \(T\).

I would also recommend that the first version use **zero-mean initial conditions**.

That removes a mostly trivial advective offset and makes the periodic Cole–Hopf construction cleaner.

The exam then looks like this:

```text
hidden seed
    ↓
fresh initial condition u0(x)
    ↓
    ├── candidate predicts û(x,T)
    │
    ├── Cole–Hopf produces uref(x,T)
    │
    └── independent high-resolution solver checks uref
```

This is important:

> **The case generator is not being “checked against truth.”**

The case generator is checked against the **registered problem distribution**.

The reference process is what is checked for numerical / analytic accuracy.

Those are two different validation problems.

---

# 4. How the case generator itself is validated

For Burgers, the generator can create the initial condition using a bounded periodic Fourier representation:

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

The Challenge specification defines:

- the allowed modes \(K\);
- the coefficient distributions;
- amplitude limits;
- gradient limits;
- spectral-complexity limits;
- correlations;
- excluded regimes;
- ordinary and stress strata.

The generator then samples from that specification.

We can directly test whether it does so correctly.

For example:

```text
registered coefficient distribution
            vs
empirical generated coefficient distribution
```

and:

```text
registered stress allocation
            vs
realized stress allocation
```

along with:

- deterministic replay;
- support / exclusion compliance;
- duplicate rate;
- boundary coverage;
- train / eval / stress seed isolation;
- failure and censoring rates.

So the generator’s correctness is not subjective.

It is a statistical and software-conformance question.

---

# 5. How the reference is validated

For Burgers v1, the strongest hierarchy is:

```text
PRIMARY REFERENCE
periodic Cole–Hopf solution

        ↓ cross-check

INDEPENDENT WITNESS
high-resolution conservative numerical solver
```

The independent solver should use a genuinely different numerical route so that it does not simply reproduce the same error mechanism.

For the audit cases, Carbon compares:

- Cole–Hopf vs the independent solver;
- both across spatial / temporal refinement;
- conservation behavior;
- numerical sensitivity;
- failure regions;
- hard-regime disagreement.

If the two disagree materially in some regime, Carbon does **not** hide that disagreement.

It has to:

- investigate;
- narrow the envelope;
- weaken the claim;
- increase the uncertainty;
- or block that region from LIVE use.

The important test is:

> **Is the uncertainty of the reference much smaller than the performance difference Carbon wants to reward?**

If not, the incentive mechanism is trying to resolve more than the science can support.

---

# 6. Why this design fits Carbon’s incentive mechanism

Carbon needs an exam that is both:

1. **fresh**, so miners cannot simply memorize the answer key; and  
2. **objectively gradeable**, so the validator is not making subjective scientific decisions.

A static benchmark gives you objective grading, but it becomes increasingly vulnerable to overfitting and leakage under repeated economic optimization.

A fresh generator solves the freshness problem.

The independently qualified reference solves the grading problem.

Together:

```text
fresh hidden case
+
independent answer key
=
repeatable scientific exam
```

That gives Carbon:

- hidden official cases;
- exact replay after evaluation;
- no miner control over the exam;
- no miner control over the reference;
- the same physical contract for all candidates;
- a measurable scientific resolution;
- the ability to say **indeterminate** when the evidence cannot separate two methods.

That last point matters for the economics:

> **Scientific resolution should cap economic resolution.**

If two methods differ by less than the uncertainty of the exam, Carbon should not manufacture a winner from a floating-point difference.

---

# 7. How physics should enter the Burgers score

I think Carbon should separate **hard physical admissibility** from **soft physics fidelity**.

Some physical properties are bad candidates for a continuous reward because “more” does not mean “more correct.”

### Recommended hard / diagnostic checks

**Finite output**

A candidate containing NaN or Inf has no valid scientific result.

**Energy non-increase**

For unforced viscous Burgers:

\[
E(u)=\frac12\langle u^2\rangle
\]

and physically we expect:

\[
E(T) \le E(0)
\]

But a model should not earn extra credit simply for dissipating more energy.

An over-diffusive model may satisfy this very strongly while being inaccurate.

So this is better treated as a **mandatory gate / diagnostic**.

**Maximum-principle consistency**

The viscous solution should not create unphysical new extrema outside the qualified initial range.

Again, being further inside the allowed range does not mean the model is more correct.

So this is also better treated as a **gate / diagnostic**.

---

# 8. Soft physics fidelity for Burgers

The clearest final-state soft physics quantity is the defect in mean conservation.

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

For any qualified soft physics defect \(\epsilon_j\), Carbon’s current scoring transform is:

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
\sum_j \alpha_j = 1
\]

The important point is that \(\tau_j\) is **not guessed**.

It comes from the Validation Dossier and must be above the numerical / reference floor.

For a final-state-only v1, I would keep this soft physics leg deliberately narrow rather than pretend weak proxies are rich physics.

If Carbon later requires time slices or full trajectories, then much stronger physics quantities become available, such as the energy balance:

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

A normalized defect in this identity would be a much stronger soft-physics measurement than simple energy monotonicity.

---

# 9. Accuracy

For each hidden case \(i\), use a qualified reference-field error:

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

This answers the basic question:

> **How close is the model to the qualified physical reference?**

---

# 10. Robustness

Robustness should answer a different question:

> **Does the model remain accurate when the physical problem becomes difficult?**

For Burgers, stress strata should be defined from the actual steepening / diffusion physics rather than arbitrary “hard case” labels.

Useful descriptors include:

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

For each stress category \(c\), calculate field errors \(e_i\) and summarize both average and tail behavior:

\[
\mu_c = \mathrm{mean}(e_i \mid c)
\]

\[
q_c = Q_q(e_i \mid c)
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
\sum_c \gamma_c = 1
\]

The tail statistic matters because an average can hide brittle behavior.

But it is only scientifically useful if each stress stratum has enough hidden samples to estimate the tail with acceptable uncertainty.

If not, the right outcome is **insufficient evidence**, not silent renormalization.

---

# 11. Final incentive score

After all mandatory physics gates pass, Carbon combines:

- physics fidelity;
- robustness;
- accuracy.

The current top-level form is:

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

The geometric form is useful because a very weak leg cannot be completely washed out by a strong one.

But I would **not** present the current 45 / 30 / 25 split as scientifically established.

Those weights should come after:

- measurement qualification;
- sensitivity testing;
- rank-stability analysis;
- and the first Burgers evidence campaign.

---

# 12. The actual falsification standard

Before Burgers should ever become LIVE, I would want Carbon to demonstrate all of the following:

1. The case generator statistically matches the registered initial-condition population.
2. The Cole–Hopf implementation is stable throughout the qualified envelope.
3. A genuinely independent refined solver agrees with Cole–Hopf within a characterized uncertainty.
4. The physics thresholds sit above the numerical / reference floor.
5. The hidden stress strata contain enough samples for meaningful tail estimation.
6. Repeated reconstruction and fresh exams produce a measured minimum resolvable improvement.
7. A model that imitates production-solver bias cannot beat a model that follows the stronger qualified reference.

If those hold, the exam is doing what Carbon needs it to do:

> **reward performance on fresh physical problems against an independently qualified answer key.**

Not:

> reward memorization of a static benchmark or imitation of a privileged solver.

---

## Bottom line

I think the most defensible way to describe Carbon is:

> **The generator creates fresh valid questions from a registered physical distribution.  
> The reference process independently establishes the best available answer for each question.  
> Physics gates reject scientifically unacceptable behavior.  
> Soft physics and robustness distinguish quality among the candidates that survive.  
> And the incentive mechanism only rewards differences larger than the demonstrated resolution of the exam.**

That is the argument I wish I had given on the call.

I would genuinely value your criticism of the reference hierarchy and the hard/soft Burgers split.

Best,  
Carbon Physics AI

---

### Technical basis

- C. J. Roy, *Review of code and solution verification procedures for computational simulation*, Journal of Computational Physics 205 (2005), 131–156.
- C. J. Roy and W. L. Oberkampf, *A comprehensive framework for verification, validation, and uncertainty quantification in scientific computing*, CMAME 200 (2011), 2131–2144.
- ASME V&V 20, *Verification and Validation in Computational Fluid Dynamics and Heat Transfer*.
- Standard Cole–Hopf theory for viscous Burgers.
- Carbon internal specifications: `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, and `Challenge_Instance_Distribution.md`.
