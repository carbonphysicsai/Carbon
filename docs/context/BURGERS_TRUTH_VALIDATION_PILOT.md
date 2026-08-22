# Burgers-1D Truth Validation Pilot — Cole–Hopf Cross-Check

**Branch:** `design/symbolic-numeric-integration`  
**Status:** exploratory numerical validation; not a production Validation Dossier.  
**Purpose:** Independently check the current Burgers-1D procedural generator/reference implementation against a stronger truth source before treating the Challenge as scientifically qualified.

---

# 1. Recommendation

For the current periodic viscous Burgers Challenge,

```text
u_t + u u_x = nu u_xx
x in [0,1), periodic
```

with the repository's zero-mean finite Fourier initial conditions, the preferred truth hierarchy is:

1. **Primary truth source: Cole–Hopf solution**, evaluated independently of the generator implementation.
2. **Secondary numerical witness: independently implemented high-resolution solver** (e.g. Julia/SciML method-of-lines or a high-resolution spectral/FVM implementation), with convergence study.
3. **Generator implementation under test:** current `poc/generators/burgers1d.py::burgers_reference_solve`, an IMEX Fourier method with explicit advection, implicit viscosity, and 2/3 dealiasing.

The current function name `burgers_reference_solve` is potentially misleading in the generalized architecture: it is the generator's numerical realization and should not be considered an independent qualification reference merely because it is called `reference`.

---

# 2. Why Cole–Hopf is especially valuable here

For viscous Burgers with `nu > 0`, the Cole–Hopf transform converts the nonlinear PDE into the linear heat equation.

For the repo's periodic zero-mean initial conditions,

```text
u(x,0) = sum_k a_k sin(2 pi k x) + b_k cos(2 pi k x),
```

a periodic potential `psi_x = u0` exists. Define

```text
phi(x,0) = exp(-psi(x)/(2 nu)).
```

Then

```text
phi_t = nu phi_xx,
u = -2 nu phi_x / phi.
```

This gives an independent semi-analytic truth path whose numerical work is only heat-kernel evolution/quadrature, not integration of the same nonlinear Burgers discretization used by the generator.

That independence is useful for the Validation Dossier because agreement is not merely two implementations of the same IMEX method agreeing with each other.

---

# 3. Repository configuration checked

Current `main` Challenge config:

```text
nx = 128
T = 1.0
periodic BC
4 Fourier IC modes

train nu:  [0.001, 0.01]
eval nu:   [0.001, 0.01]
stress nu: [0.0005, 0.005]

train/eval coefficient bound: 0.5
stress coefficient bound:     0.8
```

The current generator numerical realization uses an IMEX Fourier method at the same `nx=128` output grid.

---

# 4. Pilot method

An independent numerical loop was executed outside the repository runtime:

```text
sample Fourier IC coefficients + viscosity
        ↓
run current repo-equivalent IMEX Fourier generator solve at nx=128
        ↓
run independent Cole–Hopf periodic heat-kernel solution
        ↓
compare final u(x,T)
        ↓
record relative L2 and max-absolute error
```

The Cole–Hopf implementation used direct positive heat-kernel quadrature rather than dividing two potentially cancellation-dominated FFT reconstructions at low viscosity. Quadrature convergence was checked from 8,192 to 65,536 source points; representative low-viscosity outputs changed only at machine precision in that refinement check.

This pilot tests **generator/reference adequacy**, not FNO training quality.

---

# 5. Random eval/stress loop results

Eight random eval-role cases and eight random stress-role cases were sampled under the current parameter rules.

### Eval cases

| case | nu | relative L2 | max abs |
|---:|---:|---:|---:|
| 0 | 0.006390 | 0.000140 | 0.000124 |
| 1 | 0.006202 | 0.000174 | 0.000069 |
| 2 | 0.005138 | 0.000097 | 0.000041 |
| 3 | 0.009613 | 0.000109 | 0.000039 |
| 4 | 0.008556 | 0.000132 | 0.000056 |
| 5 | 0.005933 | 0.000112 | 0.000132 |
| 6 | 0.006153 | 0.000089 | 0.000086 |
| 7 | 0.009390 | 0.000391 | 0.000069 |

These sampled eval cases agree very closely with Cole–Hopf truth, but none landed near the difficult lower edge `nu = 0.001`. Therefore they do **not** qualify the full eval envelope.

### Stress cases

| case | nu | relative L2 | max abs |
|---:|---:|---:|---:|
| 0 | 0.004389 | 0.000251 | 0.000263 |
| 1 | 0.004008 | 0.000171 | 0.000147 |
| 2 | 0.003206 | 0.000955 | 0.000447 |
| 3 | 0.004979 | 0.000052 | 0.000036 |
| 4 | 0.004741 | 0.000239 | 0.000395 |
| 5 | 0.004032 | 0.000136 | 0.000137 |
| 6 | 0.004079 | 0.000076 | 0.000026 |
| 7 | 0.000795 | **0.278873** | **0.413751** |

The final stress sample is a material failure of the current `nx=128` generator realization against Cole–Hopf truth.

---

# 6. Resolution convergence on the failing case

For the exact failing stress IC at `nu = 0.0007949656515`, the current IMEX method was rerun at higher spatial resolution while comparing to Cole–Hopf truth:

| nx | relative L2 | max abs |
|---:|---:|---:|
| 64 | 1.424790 | 0.789219 |
| 128 | 0.278873 | 0.413751 |
| 256 | 0.013345 | 0.024092 |
| 512 | 0.000234 | 0.000488 |

This is strong evidence that the error is primarily a spatial-resolution / realizability problem, not a failure of the Cole–Hopf reference.

At `nx=512`, the same generator family converges closely to the independent truth.

---

# 7. Targeted viscosity sweep

Using the same challenging four-mode stress IC, the current `nx=128` generator was evaluated across viscosity:

| nu | relative L2 | max abs |
|---:|---:|---:|
| 0.00050 | **0.877254** | **0.745346** |
| 0.00075 | **0.339584** | **0.483497** |
| 0.00100 | **0.125502** | **0.188821** |
| 0.00150 | 0.027264 | 0.036939 |
| 0.00200 | 0.007953 | 0.009643 |
| 0.00300 | 0.001024 | 0.000998 |
| 0.00500 | 0.000110 | 0.000036 |

A separate moderate-amplitude (`coeff_bound=0.5`) IC also showed non-negligible low-viscosity discrepancy:

| nu | relative L2 | max abs |
|---:|---:|---:|
| 0.0010 | 0.051597 | 0.045260 |
| 0.0015 | 0.023628 | 0.023475 |
| 0.0020 | 0.011078 | 0.011606 |
| 0.0030 | 0.002375 | 0.002394 |
| 0.0050 | 0.000141 | 0.000166 |
| 0.0100 | 0.000206 | 0.000183 |

These are individual diagnostic cases, not statistically sufficient envelope qualification, but they demonstrate that the present lower-viscosity edge cannot be assumed accurate at `nx=128`.

---

# 8. Scientific conclusion

The pilot changes the status of the current Burgers Challenge design.

> **The current `nx=128`, `T=1`, stress viscosity range down to `5e-4` should not be considered generator-qualified on the basis of the existing implementation alone.**

There is also evidence that the eval lower edge near `nu=0.001` can be materially inaccurate for some four-mode ICs at `nx=128`.

This does **not** mean Burgers is a bad P0 Challenge. It means the Validation Dossier architecture is doing its job: the numerical realization must earn the envelope it claims.

---

# 9. Recommended next actions

## A. Adopt Cole–Hopf as primary Burgers truth witness

For the current zero-mean periodic finite-Fourier IC family, use a reviewed Cole–Hopf implementation for dossier qualification and regression tests.

Do not necessarily use it as the runtime generator if another implementation is faster or operationally simpler.

## B. Add an independent numerical secondary witness

Recommended choices:

1. Julia/SciML method-of-lines with a separately specified spatial discretization and tight tolerances; or
2. a high-resolution conservative finite-volume method; or
3. a high-resolution pseudo-spectral solver with an independent time integrator.

The purpose is not to outvote the analytic transform. It is to detect implementation mistakes in either truth path.

## C. Requalify spatial resolution and envelope together

Do not choose `nx` independently of `nu`, IC amplitude, and `T`.

Run a structured grid over:

```text
nu
IC coefficient norm / steepness
T
nx
```

and determine a defensible error envelope against Cole–Hopf.

Possible outcomes:

- raise P0 generator resolution;
- shrink the official low-viscosity envelope;
- use resolution conditional on case difficulty;
- shorten `T` for the lean proof;
- or split easy and hard strata with separately qualified realization policies.

The scientific choice belongs to the tech/science lead after evidence review.

## D. Never tune a gate to hide generator error

Reference/generator error must be characterized before candidate thresholds are calibrated.

If the generator's own truth error is comparable to a proposed candidate gate, the gate is not scientifically defensible.

## E. Rename semantic roles

The current generator helper `burgers_reference_solve` should eventually be described as the **generator numerical realization** unless/until it is independently qualified as a reference source. The Validation Dossier should bind the true independent reference policy separately.

---

# 10. Proposed Burgers dossier structure

```text
PhysicalSystemSpec
  viscous periodic Burgers
        ↓
InstanceDistributionContract
  4-mode zero-mean Fourier ICs
  viscosity / amplitude populations
        ↓
SamplingPlan
  nominal + lower-viscosity stress strata
        ↓
Generator
  IMEX Fourier realization, exact version
        ↓
Dossier truth hierarchy
  PRIMARY: Cole–Hopf
  SECONDARY: independent high-resolution numerical solver
        ↓
Generator conformance + reference agreement
        ↓
Measurement qualification
        ↓
Score Pack calibration
```

The Score Pack should only be calibrated after this generator/truth qualification is complete.

---

# 11. What this pilot did not prove

This pilot did **not**:

- run the full JAX FNO training loop;
- qualify a production error threshold;
- establish the minimum acceptable `nx` over the entire population;
- establish a statistically sufficient SamplingPlan;
- prove all stress IC transformations are compatible with the zero-mean Cole–Hopf path;
- approve any LIVE Challenge.

It did execute the generator-versus-independent-truth loop and reveal a concrete lower-viscosity resolution failure that must be resolved before scientific qualification.

---

# 12. Bottom line

> **For Burgers P0, use Cole–Hopf as the strongest primary truth source, cross-check it with an independent numerical solver, and require the IMEX generator to earn its exact viscosity/amplitude/time/resolution envelope through convergence evidence.**

The first execution already shows why this separation matters: the current generator is excellent in the easier sampled regime but can be materially wrong near the present low-viscosity boundary at `nx=128`.
