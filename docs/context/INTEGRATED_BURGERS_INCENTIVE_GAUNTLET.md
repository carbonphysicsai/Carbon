# Integrated Burgers Incentive Gauntlet

**Branch:** `design/symbolic-numeric-integration`  
**Status:** executed pilot; design/qualification evidence only, not production qualification.  
**Purpose:** Exercise Carbon's full scientific chain far enough to test whether the current Burgers exam and scoring incentives reward physically better candidates rather than merely candidates that match the current generator.

---

# 1. Executive result

The architecture behaved as intended: the gauntlet found a material exam-side weakness before Carbon would be justified in treating the resulting score as authoritative.

Two results matter most:

1. the current Burgers IMEX-Fourier generator is very accurate in moderate-viscosity cases but develops material error near the lower-viscosity edge at the current resolution;
2. under the current score semantics, a candidate that reproduces the generator's numerical solution can outrank a candidate that reproduces an independent Cole-Hopf physical reference.

That second result is a **stop-ship condition for scientific interpretation of the current Burgers score** until the generator/reference/measurement chain is qualified.

> **A Score Pack cannot rescue an unqualified exam.**

This is exactly the failure mode the new distribution + Validation Dossier + Score Pack architecture is intended to prevent.

---

# 2. Scientific setup

The test used the current Burgers physical semantics:

```text
u_t + u u_x = ν u_xx
x ∈ [0,1), periodic
smooth four-mode Fourier initial conditions
```

The current repository generator uses an IMEX Fourier method:

- explicit advection;
- implicit viscosity;
- spectral spatial derivatives;
- 2/3 dealiasing;
- current time-step rule from `poc/generators/burgers1d.py`.

The independent reference used a periodic Cole-Hopf construction evaluated through a numerically stabilized heat-kernel/log-convolution implementation. This is independent of the generator's nonlinear time-stepping path and is appropriate for the current zero-mean periodic viscous Burgers family.

The pilot did not claim universal Cole-Hopf tooling for arbitrary future Challenges. It is a Challenge-specific truth source for this Burgers family.

---

# 3. Generator-vs-truth check

Selected `nx=128`, `T=0.5` cases were generated with independent IC seeds and compared against Cole-Hopf truth.

| Seed | ν | Relative L2(generator, truth) | Generator wall time |
|---:|---:|---:|---:|
| 11 | 0.00500 | 0.000306 | 0.60 s |
| 12 | 0.00200 | 0.003753 | 1.42 s |
| 13 | 0.00100 | 0.085273 | 2.80 s |
| 14 | 0.00075 | 0.073294 | 2.85 s |

## Interpretation

The generator is excellent in the easier/moderate-viscosity regime and materially weaker near the low-viscosity boundary at this resolution.

This is consistent with the earlier independent truth pilot: spatial resolution, not merely deterministic execution, is a qualification variable.

The relevant scientific conclusion is not that the generator is unusable. It is:

> **The current claimed low-viscosity region cannot be treated as equally qualified evidence without additional convergence/envelope work.**

---

# 4. Objective / Goodhart gauntlet

A fixed moderate-viscosity eval case and four stress cases were evaluated under current Burgers-style score semantics.

Synthetic candidates were chosen to probe different failure modes:

- `generator_oracle`: exactly reproduces current generator labels;
- `physical_truth_oracle`: exactly reproduces independent Cole-Hopf truth;
- `smoothed_generator`: low-pass version of generator output;
- `scaled_generator_0.2`: strongly attenuated output;
- `zero`: identically zero output.

The current score uses the existing conceptual structure:

- hard finite / conservation / residual / accuracy gates;
- soft physics, robustness, and accuracy legs;
- 0.45 / 0.30 / 0.25 top-level weighting;
- weighted-geometric combination.

## Results

| Candidate | Current score | Current eval rel-L2 | Current stress rel-L2 | True eval rel-L2 | True stress rel-L2 | Hard fail? |
|---|---:|---:|---:|---:|---:|---|
| generator_oracle | **0.973314** | 0.000000 | 0.000000 | 0.000178 | 0.049209 | no |
| physical_truth_oracle | **0.930064** | 0.000178 | 0.049158 | **0.000000** | **0.000000** | no |
| smoothed_generator | 0.711155 | 0.091639 | 0.228911 | 0.091617 | 0.221974 | no |
| scaled_generator_0.2 | ~2.1e-7 | 0.800000 | 0.800000 | 0.800007 | 0.800369 | no |
| zero | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | accuracy ceiling |

## Critical finding

The current exam prefers:

```text
generator_oracle
    over
physical_truth_oracle
```

because the score is computed against the generator's own under-qualified labels.

That is scientifically unacceptable as an authoritative subnet incentive, even though the numerical difference is modest in this small pilot.

### Required rule

> **A candidate that is demonstrably closer to qualified physical truth must not be systematically penalized for disagreeing with an unqualified generator realization.**

This becomes an integrated Challenge stop-ship test.

---

# 5. Metric-Goodhart observations

The synthetic candidates exposed two additional useful properties.

## 5.1 Hard accuracy gate works against the trivial zero solution

The zero predictor has excellent trivial spatial-balance behavior but receives zero because relative error exceeds the hard accuracy ceiling.

This supports the doctrine:

> mandatory admissibility prevents one easy-to-game physics proxy from defining success.

## 5.2 Soft transforms still need scientific qualification

The `scaled_generator_0.2` candidate remains technically admissible under the selected current thresholds but has an effectively negligible aggregate score.

That is not immediately dangerous, but it illustrates why hard gates and soft transforms must be calibrated from qualified evidence rather than intuition.

---

# 6. Actual FNO strategy pilot

A compact JAX FNO pilot was also executed to test the training-strategy path itself.

This was intentionally reduced for runtime and **is not the exact production P0 campaign**:

```text
nx = 64
T = 0.25
train n = 16
train ν ∈ [0.003, 0.01]
eval n = 8
stress n = 6
stress ν ∈ [0.0015, 0.003]
FNO width = 16
modes = 8
layers = 2
```

Four strategies were trained:

- `gold`: data + current residual proxy + conservation;
- `data_only`;
- `physics_only`;
- `undertrained` data-only.

### Results

| Strategy | Steps | Current eval rel-L2 | True eval rel-L2 | Current stress rel-L2 | True stress rel-L2 | Current status |
|---|---:|---:|---:|---:|---:|---|
| gold | 80 | 1.0128 | 1.0127 | 0.8496 | 0.8490 | inadmissible: residual ceiling |
| data_only | 80 | 1.1331 | 1.1329 | 1.0053 | 1.0061 | inadmissible: residual + accuracy |
| physics_only | 80 | 1.2703 | 1.2703 | 1.1543 | 1.1569 | inadmissible: residual + accuracy |
| undertrained | 8 | 3.8233 | 3.8234 | 3.0936 | 3.1133 | inadmissible: conservation + residual + accuracy |

## Interpretation

This small pilot did **not** produce an emissions-eligible FNO candidate. That is not a failure of the architecture; it is useful calibration evidence.

It tells us that the current PoC thresholds/strategy budget/model size cannot simply be assumed to yield a useful ranked population under arbitrary reduced training conditions.

The ordering is directionally sensible (`gold` best, undertrained worst), but the scientific claim we need is stronger:

> **The authoritative P0 campaign must demonstrate a non-degenerate population of independently reconstructed strategies that are both admissible and meaningfully rankable.**

Until that happens, the subnet should not infer incentive quality from architecture alone.

---

# 7. Integrated stop-ship conditions learned

A Challenge must not become authoritative if any of these hold:

1. a generator-matching oracle outranks independently qualified physical truth because the generator is biased;
2. the generator's error is material relative to the candidate differences the score is intended to resolve;
3. all realistic candidate strategies are inadmissible under the registered budget;
4. rank is dominated by one unqualified measurement proxy;
5. small numerical implementation changes alter winner identity materially;
6. required hard strata are insufficiently resolved by the truth path;
7. finite evidence cannot discriminate strategies at the intended economic resolution.

---

# 8. Required Burgers actions before authoritative scoring

## B1 — qualify the low-viscosity envelope

Run a systematic grid over:

```text
ν
IC amplitude / steepness
T
nx
```

against Cole-Hopf truth.

Choose one or more of:

- increase resolution;
- shrink envelope;
- shorten horizon;
- use regime-conditional resolution;
- split nominal and stress truth policies.

## B2 — replace the current residual proxy as an official physics claim unless requalified

The current `residual_mean` is a final-time spatial-balance proxy:

```text
|u u_x - ν u_xx|
```

It omits `u_t` and is not the full Burgers PDE residual.

It may remain a diagnostic if useful, but official score-bearing use should require a qualified MeasurementContract with precise semantics.

## B3 — re-run strategy discrimination with qualified labels

Train/reconstruct a deliberate miner population under realistic P0 budgets and verify:

- at least several candidates become admissible;
- known-better strategies rank better;
- rankings are stable across fresh eval/stress draws;
- reconstruction variability is measured;
- adversarial strategies do not exploit measurement shortcuts.

---

# 9. Architecture verdict

The integrated gauntlet **supports** the new architecture.

The architecture correctly predicts that:

```text
unqualified generator
    → unqualified evidence
    → Score Pack must not create authority
```

The current Burgers implementation therefore becomes a useful scientific-development target rather than evidence that the architecture is complete.

> **First prove the exam. Then prove the market selects the right methods.**

---

# 10. Bottom line

The current design is strong enough to detect its own failure mode.

The next P0 milestone should not be "turn on emissions." It should be:

> **produce a qualified Burgers exam in which physically better outputs are never systematically disadvantaged by the truth generator, then demonstrate stable discrimination among independently reconstructed miner strategies.**
