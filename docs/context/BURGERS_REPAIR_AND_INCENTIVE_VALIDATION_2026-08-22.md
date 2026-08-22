# Burgers Repair + Incentive Validation — 2026-08-22

**Status:** executed design/validation record; not a production qualification certificate.  
**Branch:** `design/symbolic-numeric-integration`.

---

# 1. Purpose

Continue the integrated incentive gauntlet after the first truth-loop exposed that the existing low-viscosity generator could materially disagree with independent Cole-Hopf truth.

This pass tested:

1. whether the current candidate input actually defines a deterministic task;
2. whether a narrower Burgers task can produce an admissible miner population;
3. whether physically meaningful final-state measurements behave sensibly;
4. whether synthetic candidate ranking is stable over fresh draws;
5. whether validator numerical implementation differences are negligible relative to scientific differences;
6. how strongly candidate scores should be concentrated economically.

---

# 2. Major finding: the current variable-viscosity task is non-identifiable

The current FNO forward path consumes only `u0`.

The current generator samples viscosity `nu` per case.

Therefore the nominal task is effectively presented as:

```text
u0 -> u(T)
```

while the true physical map is:

```text
(u0, nu) -> u(T)
```

For the same random four-mode initial condition, independent Cole-Hopf calculations comparing `nu=0.002` with `nu=0.01` produced final-state relative differences of approximately:

```text
0.281
0.273
0.289
0.593
0.296
```

This is a Challenge-contract defect, not a model-training defect.

### Decision consequence

The owner-recommended P0 v1 Challenge fixes `nu=0.005` and keeps the existing `u0 -> u(T)` candidate input contract. A later explicitly conditioned Challenge may expose viscosity as a candidate input.

---

# 3. Truth-source qualification observations

The periodic Cole-Hopf transform was used as the primary independent truth path.

Internal-reference convergence was tested by comparing sampled `nx=128` outputs produced with different high-resolution Cole-Hopf internal grids.

For a small random audit with coefficient bound up to `0.8`, `2048` versus `4096` internal grids gave maximum observed relative differences approximately:

```text
nu=0.0010   1.12e-3
nu=0.0015   7.14e-4
nu=0.0020   1.07e-4
```

At the recommended fixed P0 value `nu=0.005`, convergence error was below the scale relevant to the first competition in the executed pilots.

An independently implemented conservative finite-volume witness was also compared with Cole-Hopf. At `nu >= 0.002`, tested cases were generally within about one percent. At lower viscosity it became much less reliable because of numerical diffusion/resolution limits, demonstrating that an independent numerical code is not automatically the stronger truth source.

---

# 4. Measurement repair

The current final-time spatial quantity

```text
|u u_x - nu u_xx|
```

is not a full PDE residual because `u_t` is absent.

For the IC -> final-state task, the stronger available physical properties are:

- finite output;
- periodic mean/mass conservation;
- energy non-increase;
- maximum-principle consistency;
- field accuracy against qualified Cole-Hopf truth;
- explicit stress-stratum accuracy.

The residual proxy should therefore be diagnostic-only in the repaired P0 Challenge.

---

# 5. Synthetic score red-team under repaired measurements

A provisional P0-v1 measurement/score profile was exercised on six controlled candidate classes over independently generated Cole-Hopf cases:

```text
truth          exact qualified truth
noise2         truth + small 2% noise
smooth         Fourier-smoothed truth
atten90        0.9 * truth
shift          small spatial shift
zero           zero field
```

One representative run produced approximate combined scores:

```text
truth      1.0000
noise2     0.9731
smooth     0.9596
atten90    0.8959
shift      0.7829
zero       0.0000 (inadmissible)
```

The physics invariants alone intentionally do not reject `atten90` or `shift`: those outputs can conserve mass and dissipate energy while still being inaccurate. The accuracy/stress evidence supplies the needed scientific discrimination.

This confirms the desired layered behavior:

```text
physical admissibility
        +
truth-relative performance
        ↓
meaningful rank
```

rather than assuming physical invariants alone prove solution correctness.

---

# 6. Fresh-draw rank stability

The same synthetic candidate set was evaluated over **20 independently generated nominal/stress draw bundles**.

Observed ordering was identical in all 20:

```text
truth
> noise2
> smooth
> atten90
> shift
> zero
```

Mean combined scores across the 20 bundles were approximately:

```text
truth      0.9999995
noise2     0.97494
smooth     0.95821
atten90    0.89595
shift      0.78194
zero       0
```

Observed standard deviations were small relative to the separations in this controlled set. This does not prove production miner rank stability, but it confirms that the repaired measurement/aggregation logic is not intrinsically unstable on known perturbation classes.

---

# 7. Validator numerical agreement pilot

The synthetic score path was executed with evidence calculations in binary32-like and binary64 NumPy arithmetic.

Across 10 fresh draw bundles and all six controlled candidate classes, the maximum observed combined-score difference was approximately:

```text
5.73e-8
```

This is many orders of magnitude smaller than the candidate separations in the pilot.

### Learning

For this path, validator floating-point implementation disagreement is not the dominant uncertainty. Scientific uncertainty comes from the Challenge/evidence itself and should stay conceptually separate.

---

# 8. Real FNO pilot: fixing viscosity creates an admissible population

A compact JAX FNO pilot used:

- fixed `nu=0.005`;
- `nx=128`;
- `T=1`;
- Cole-Hopf-generated labels;
- the current one-field FNO input shape;
- independent reconstruction seeds.

With variable hidden viscosity, all tested current-style strategies were strongly inadmissible.

With fixed viscosity, realistic 1000-step data and data+physics strategies began producing admissible reconstructions.

Representative admissible reconstructions included:

```text
data+physics:
  eval rel-L2  ~0.584
  stress errors ~0.70-0.76
  combined pilot score ~0.434

data-only:
  eval rel-L2  ~0.582
  stress errors ~0.70-0.76
  combined pilot score ~0.436

stronger reconstruction example:
  eval rel-L2 ~0.393
  combined pilot score ~0.609
```

Physics-only and deliberately undertrained strategies remained strongly inadmissible.

### Important result

Different reconstruction seeds of the **same** strategy frequently crossed the provisional admissibility boundary. Examples for the data+physics strategy ranged from admissible `eval rel-L2 ~0.58` or `~0.39` to failed reconstructions around `~0.68-0.86`, often because of mass or accuracy/stress gates.

Therefore reconstruction variability is material and must be quantified before emissions claim method quality.

---

# 9. Current physics-loss interpretation

In the compact fixed-viscosity pilot, data-only and data+current-physics-penalty strategies performed very similarly. The physics-only strategy optimized its penalties but produced poor truth-relative solutions.

This is scientifically useful:

> Training-time physics terms are miner hypotheses. They receive no score privilege merely because they are called physics.

The official judge should continue to use independent external evidence.

---

# 10. Emissions concentration calibration

Using the controlled admissible candidate scores from the repaired score pilot, three economic transforms were compared.

Representative reward shares:

```text
PROPORTIONAL TO SCIENTIFIC SCORE
truth      21.7%
noise2     21.1%
smooth     20.8%
atten90    19.4%
shift      17.0%

POWER-2
truth      23.3%
noise2     22.1%
smooth     21.5%
atten90    18.7%
shift      14.3%

SOFTMAX, temperature 10
truth      34.5%
noise2     26.4%
smooth     23.0%
atten90    12.2%
shift       3.9%
```

The aggressive softmax converts moderate scientific differences into much sharper economic concentration.

### Owner recommendation

For initial P0:

> **Use a monotone, bounded-concentration downstream emissions transform. Start with normalized proportional scientific score among `VALID_RANKED` candidates; do not use winner-take-all or a high-temperature softmax.**

If stronger selection pressure is later required, a mild versioned power transform may be tested only after repeated rank-resolution data supports it.

---

# 11. No-admissible-candidate rule

A Challenge may produce no scientifically admissible candidate in a round.

That is valid scientific evidence.

The scientific layer should emit:

```text
NO_ADMISSIBLE_SCIENTIFIC_SIGNAL
```

rather than declaring the least-bad failing candidate a scientific winner.

The chain/runtime owner must define the safe Bittensor behavior for that state without falsifying the scientific record.

---

# 12. Remaining work before LIVE qualification

The highest-value next experiments are:

1. implement the fixed-viscosity challenge as a review branch/profile;
2. replace score-bearing generator labels with pinned Cole-Hopf truth;
3. replace the final-state residual gate with the qualified invariant set;
4. run a larger realistic strategy bank across multiple reconstruction and evaluation seeds;
5. estimate method-level admissibility probability and score dispersion;
6. choose repeat policy and minimum meaningful rank resolution;
7. execute the same evidence bundle through two independently packaged validator environments;
8. bind the final Challenge values into the Validation Dossier and Score Pack;
9. then calibrate production emissions concentration.

---

# 13. Bottom line

The integrated design is now behaving as intended: adversarial testing exposed a hidden-variable task defect, generator-truth mismatch, an invalid residual interpretation, and reconstruction variance **before** authoritative emissions.

The repaired fixed-viscosity Challenge creates a plausible non-degenerate P0 competition while keeping Carbon's first experiment narrow.
