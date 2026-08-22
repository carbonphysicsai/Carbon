# Burgers-1D Challenge Qualification v1

**Status:** OWNER-RECOMMENDED challenge design v1 — ready for tech/science-lead review; **NOT YET LIVE-QUALIFIED**.  
**Purpose:** Repair the current Burgers PoC into the narrowest scientifically coherent Challenge capable of proving Carbon's judge, reconstruction, evidence, Score Pack, and emissions path.  
**Related:** `Challenge_Instance_Distribution.md`, `Generator_Validation.md`, `Score_Pack_Architecture_v1.md`, `POC_Burgers_FNO.md`, `Data_Management.md`.

---

# 1. Executive decision

The current PoC should **not** be used as authoritative emissions evidence without repair.

Three material issues were found by the integrated incentive gauntlet:

1. **The current task varies viscosity while the FNO receives only `u0`.** The target map is therefore not a function of the declared candidate input. For the same initial condition, changing `nu` materially changes `u(T)`.
2. **Several current score-bearing stress draws exceed the written Challenge envelope or IC family.** Current `low_viscosity` includes values below the declared stress lower bound; current shock/amplitude transforms can also exceed written stress semantics.
3. **The current final-state `residual` is not a full Burgers PDE residual because no `u_t` is available.** It must not remain a mandatory physical truth gate under an IC -> final-state task.

### v1 design choice

> **Keep P0 narrower: fix viscosity for the first authoritative Burgers Challenge rather than expanding the FNO input contract during the proof-of-judge stage.**

The next parameter-conditioned Challenge may explicitly use `(u0, nu) -> u(T)`. P0 v1 should prove the judge first.

---

# 2. Canonical P0-v1 task

```text
PDE:
    u_t + u u_x = nu u_xx

Domain:
    x in [0,1), periodic

Fixed physical parameter:
    nu = 5e-3

Task:
    u0(x) -> u(x,T)

T:
    1.0

Candidate output grid:
    nx = 128, periodic uniform grid
```

`nu=5e-3` is selected provisionally because the independent truth pilots show strong numerical agreement in this regime while retaining nonlinear steepening and dissipation. It is a Challenge-specific P0 choice, not a universal Burgers parameter.

---

# 3. Why viscosity is fixed in v1

The existing FNO forward path consumes only the initial field. The current generator nevertheless samples `nu` per case. That makes the apparent operator

```text
u0 -> uT
```

non-identifiable: two cases with the same `u0` and different viscosity have different valid targets.

Independent Cole-Hopf calculations on five random four-mode initial conditions found relative differences of roughly **0.27-0.59** between the `nu=0.002` and `nu=0.01` solutions for the same `u0` at `T=1`.

This is not a training weakness. It is a task-contract defect.

### Future path

After P0:

```text
P0 v1:
    fixed nu; u0 -> uT

later conditioned Challenge:
    (u0, nu) -> uT
```

The later Challenge must modify the `CandidateOutputContract` and model input adapter explicitly rather than hiding `nu` from the candidate.

---

# 4. Target population

## 4.1 Nominal construction/evaluation population

Initial conditions are zero-mean periodic four-mode Fourier fields:

```text
u0(x) = sum_{k=1}^4 [a_k sin(2 pi k x) + b_k cos(2 pi k x)]

a_k, b_k independently sampled in [-0.5, 0.5]
```

For P0 v1:

```text
P_construct = P_eval = registered four-mode coefficient population
nu = 5e-3 fixed
T = 1
```

Construction and evaluation **realizations/seeds remain cryptographically distinct** even when their target distributions are the same.

## 4.2 Stress population

Score-bearing stress remains inside an explicitly registered claim family. Recommended P0-v1 stress strata:

1. **higher-amplitude IC** — same four modes, coefficient bound increased but capped at `0.8`;
2. **phase-shift IC** — periodic translation of a valid IC;
3. **moderate added high-frequency content** — only if explicitly included in the registered stress family and independently qualified;
4. **coefficient-edge/corner strata** — deliberate coverage near admissible amplitude boundaries.

### Deferred from score-bearing P0 v1

- hidden viscosity variation;
- `nu < 5e-3` low-viscosity stress;
- undeclared `tanh(2.5 u)` shock warping;
- any stress transform that leaves the registered IC family without explicit distribution semantics and qualification.

These can return in a later Challenge version after explicit contract expansion.

---

# 5. Truth/reference policy

## 5.1 Primary reference: periodic Cole-Hopf

For this Challenge, the preferred primary truth source is the periodic Cole-Hopf transform:

```text
u_t + u u_x = nu u_xx

u = -2 nu * phi_x / phi

phi_t = nu phi_xx
```

For the zero-mean periodic Fourier IC family, this gives a strong semi-analytic truth path in which the nonlinear Burgers solve is reduced to heat-equation evolution.

### Implementation requirement

The reference implementation should:

- construct the periodic antiderivative analytically from Fourier coefficients;
- form `phi0` with numerically stabilized exponentiation;
- evolve the heat equation spectrally;
- recover `u(T)`;
- use an internal reference grid materially finer than the candidate output grid;
- downsample only after the high-resolution truth realization is formed;
- retain exact implementation/version/environment provenance.

## 5.2 Internal-resolution convergence

Pilot comparisons against a `4096`-point Cole-Hopf realization showed that a `2048`-point internal reference grid differed by approximately:

- <= ~0.12% in sampled low-viscosity `nu=0.001` cases;
- <= ~0.08% around `nu=0.0015`;
- <= ~0.02% around `nu=0.002`;
- effectively negligible in the intended fixed `nu=0.005` P0 regime.

For fixed `nu=0.005`, the reference floor is therefore substantially below the accuracy scale needed for the first P0 competition.

## 5.3 Independent numerical witness

An independent conservative finite-volume witness was also piloted. At `nu >= 0.002`, its sampled final states were within roughly one percent of Cole-Hopf in the tested cases; it became much less reliable at lower viscosity due to its own numerical diffusion/resolution limitations.

This supports two rules:

> **An expensive or independent numerical solver is evidence, not automatic truth.**

and

> **Cole-Hopf is the primary P0 reference because this exact PDE admits the stronger analytic transformation.**

A pinned Julia/SciML or other independently reviewed numerical witness should still be retained in the formal dossier for selected audit cases, but disagreement must be interpreted according to each method's demonstrated numerical regime.

---

# 6. Generator policy

The current IMEX Fourier solver may remain useful as:

- an independent numerical implementation;
- a generator-conformance witness in the qualified regime;
- a regression oracle for code changes.

It should **not** be called the scientific reference merely because the function is named `burgers_reference_solve`.

For authoritative P0 labels, prefer Cole-Hopf-generated truth for the fixed-viscosity Challenge.

This removes the failure mode found in the prior gauntlet where a candidate matching generator error could outrank a candidate matching independent physical truth.

---

# 7. Measurement set v1

The IC -> final-state task permits strong physical measurements that do not require a trajectory.

## M1 — Finite output

Mandatory.

```text
all candidate outputs finite
```

## M2 — Periodic mean/mass conservation

For periodic viscous Burgers without forcing:

```text
mean(u(T)) = mean(u0)
```

Use a registered discrete measurement and Challenge-calibrated numerical tolerance.

## M3 — Energy non-increase

For the unforced viscous system:

```text
E(T) <= E(0)
E = integral (u^2 / 2) dx
```

Use a registered discrete approximation and a small numerical tolerance justified by the dossier.

## M4 — Maximum-principle consistency

Viscous Burgers obeys a maximum principle. Final-state extrema should not create new values beyond the admissible initial extrema, subject to registered discrete/representation tolerance.

## M5 — Relative field error against qualified Cole-Hopf truth

Primary accuracy estimand for P0.

## M6 — Stress-stratum field error

Robustness evidence is reported by registered stress stratum, not only as one global average.

## Residual proxy disposition

The current quantity

```text
|u u_x - nu u_xx|
```

at one final state omits `u_t`. It is a spatial-balance proxy, not the Burgers PDE residual.

### v1 decision

> **Remove it from mandatory admissibility and primary physics scoring for the final-state task.**

It may remain `DIAGNOSTIC_ONLY` if correctly named and useful for research.

A future trajectory-output Challenge may introduce a qualified spacetime residual with `u_t` available.

---

# 8. Admissibility before ranking

Recommended logical order:

```text
valid execution/evidence
        ↓
finite output
mean conservation
energy non-increase
maximum-principle consistency
accuracy ceiling
required stress-stratum ceilings
        ↓ PASS
soft continuous ranking
```

Exact numerical thresholds are Challenge-owned and must be calibrated in the Validation Dossier. They are **not** universal values and are not locked by this architecture document.

---

# 9. Non-degenerate strategy population pilot

A local JAX FNO pilot was rerun after fixing viscosity at `nu=0.005` and using Cole-Hopf labels.

The same current one-input FNO architecture then became capable of producing admissible reconstructions under a provisional physically meaningful gate set.

Two 1000-step strategy families were tested across multiple reconstruction seeds:

- data + physical penalties;
- data-only.

Observed examples included:

- data+physics reconstruction: eval rel-L2 ~0.58, stress errors ~0.70-0.76, admissible;
- data-only reconstruction: eval rel-L2 ~0.58, stress errors ~0.70-0.76, admissible;
- stronger reconstruction example: eval rel-L2 ~0.39 with improved stress behavior, admissible;
- other reconstructions of the same strategy failed mass/accuracy/stress gates.

Physics-only and deliberately undertrained strategies remained strongly inadmissible.

### Learning

The fixed-viscosity task repairs the non-identifiability and creates a usable P0 selection problem, but **reconstruction variance is material**.

Therefore one lucky reconstruction is not yet sufficient evidence of method quality.

---

# 10. Reconstruction-repeat requirement

Before authoritative emissions, P0 must quantify reconstruction variability for the realistic strategy population.

Owner recommendation:

1. run at least several independent reconstruction seeds per candidate during the qualification campaign;
2. measure admissibility rate, score mean/dispersion, and failure mode;
3. select an economical production repeat policy only after observing that distribution;
4. do not silently equate one artifact with method quality.

The final production repeat count remains a tech/science/economic decision.

---

# 11. Required validation campaign before LIVE

The Burgers Validation Dossier should contain, at minimum:

1. Cole-Hopf derivation/implementation review;
2. internal-grid convergence audit;
3. independent numerical witness on selected cases;
4. nominal IC population conformance;
5. explicit stress-family conformance;
6. train/eval/stress seed separation;
7. measurement implementation tests for M1-M6;
8. truth-reference numerical floor;
9. candidate-family adversarial tests;
10. reconstruction-repeat statistics;
11. score/rank stability over fresh evaluation draws;
12. validator implementation agreement;
13. stop-ship limitations and exact claim boundary.

---

# 12. Stop-ship conditions

Do not enable authoritative emissions if any of the following remains true:

- a score-bearing physical parameter is hidden from the candidate while changing the target map;
- score-bearing stress leaves the registered claim family;
- the generator can beat independent truth under the official score because labels are biased toward generator error;
- a final-state residual proxy is represented as a full PDE residual;
- no realistic submitted strategies become admissible;
- ranking is dominated by reconstruction seed luck;
- validators materially disagree on the same authorized evidence;
- the economic transform amplifies unresolved scientific noise into winner-take-most rewards.

---

# 13. Final v1 statement

> **The first authoritative Carbon Burgers Challenge should be a fixed-viscosity, independently truth-qualified `u0 -> u(T)` problem with explicit physical invariants, qualified stress strata, repeat-aware method evidence, and scoring that cannot reward generator error over physical truth.**

This is the narrowest Challenge that tests Carbon's judge honestly without prematurely expanding model freedom or physics depth.
