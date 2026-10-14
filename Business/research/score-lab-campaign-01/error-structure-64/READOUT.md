# Error structure: 64 analytic profiles, all ten candidate proxies

**SYNTHETIC DEVELOPMENT; INSUFFICIENT_EVIDENCE for rule selection.** This is an
actual canonical execution of the existing six-axis error example, extending
the earlier eight-profile, N1-only smoke. All **64 profiles, ten proxies and
seven configured switches** completed: **4,480 candidate-switch rows**. No
solver, model rebuild, EV4 fitting, realism calibration or final holdout ran.
Existing experiment ranges, candidate definitions and result files are unchanged.

## Actual execution and coverage

- Source/contract commit: `69e39b42e5ee06e84d7fa3058fca2e2f530418ec`.
- Canonical native-Linux clone, locked `dev science-jax` groups and one numerical
  library thread. The immutable image and resources are in [EXECUTION.json](EXECUTION.json).
- LHS plan identity: `7f5d6cbfa5ffbe46b06359de033e0101dc1fa8d831175ce71f19e89b6b098c00`.
  Four interleaved shards cover indices 0 through 63 exactly once. The existing
  atlas rejects duplicate, missing or mismatched profile identities.
- Candidate source SHA256: `157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
  The trusted local candidate file is not committed.
- Controls passed before evaluation: historical public EV5 abstention rank
  **2/100**, nominal bilinear offered-grid ceiling capture **1.0**; separate toy
  abstention rank **1/14**, finite-grid capture **1.0**. These are distinct cohorts,
  not a replay of the older 1/75 observation or qualification of a battery exam.
- CLI analysis used **266.571 CPU-s (0.074 CPU-h)** and **266.708 wall-s**, including
  controls, plan generation, four evaluation shards and atlas. Image/bootstrap
  and export costs are excluded; peak RSS was not measured. No cap fired.

The six axes change **only population member 0**: heteroscedasticity, error
region, cross-design correlation, rare-tail rate/size and uncertainty scale.
Other members and the task are fixed. The LHS is a proposal over explicitly
assumed toy knobs, not a Challenge population or a fit to 142 real recipes.
Within a profile the configured toy questions/weights remain fixed. This narrow
experiment cannot establish independent future-task probabilities.

## Baseline OFF switch: alignment depends on the value scope

Cells below are median defined Kendall tau across profiles. The final column
counts profiles with a defined tau in each scope; undefined values are never
filled with zero. `INFORCE` has only 15 defined profiles, so its conditional
medians must not be read as measurements over all 64 profiles.

| Proxy | Target | Shifted | Extrapolated | Neighbour blend | Defined / 64 |
|---|---:|---:|---:|---:|---:|
| INFORCE G-FEAS / A-Q | 0.000 | -0.346 | 0.598 | -0.115 | 15 |
| N1 decision relevance | -0.414 | 0.467 | -0.690 | 0.333 | 64 |
| N2 regret on pick | -0.593 | 0.552 | -0.857 | 0.552 | 64 |
| N3 safe pick x gain | -0.643 | 0.552 | -0.571 | 0.276 | 64 |
| N4 top-region ranking | -0.414 | 0.200 | -0.276 | 0.067 | 64 |
| V10 SIGN+ENV / ARP | -0.267 | 0.258 | -0.713 | 0.086 | 64 |
| V2 rev2 k1 / cost 0.05 | -0.643 | 0.483 | -0.571 | 0.276 | 64 |
| V2 rev2 k3 / cost 0.10 | 0.552 | -0.200 | 0.138 | 0.067 | 64 |
| V2 rev2 k5 / cost 0.25 | 0.690 | -0.333 | 0.276 | -0.067 | 64 |
| V9 ENV / ARP | -0.414 | 0.552 | -0.786 | 0.414 | 64 |

**Every OFF proxy has a negative median tau in at least one value scope.**
For example, the k3 and k5 proxies align positively on the target while their
shifted medians are negative. Their rows change both k and the assumed cost,
so this table does not identify either knob's isolated causal effect.

The neighbour-blend gamer-top-half flag is set in 64/64 OFF profiles for eight
proxies, despite several positive neighbour-blend medians. N2 and V9 have zero
such flags here. A profile flag means a configured gamer ranks in the neighbour-
blend view's top half; it is not a union over the other scopes.
it is not a count of independent miners or proof that a gamer is paid.

## Physics switches: paired descriptive changes versus OFF

Each comparison uses the **same candidate and profile** and the neighbour-blend
tau. There are 591 defined pairs and 49 undefined pairs per switch, retained in
[PAIRED_SWITCH_SUMMARY.json](PAIRED_SWITCH_SUMMARY.json). Positive means higher
tau on that pair; equal means exact equality, not powered equivalence. The
median delta is over defined pairs only. The existing `good_wrongly_excluded`
counter includes loss of admission **or demotion from the primary FLOOR tier**
relative to OFF. These are repeated profile/proxy/member events from the toy's
declared good-member labels, not unique recipes or mandatory gate failures.

| Switch | Positive / equal / negative | Undefined | Median delta tau | Toy good exclusion/demotion events |
|---|---:|---:|---:|---:|
| 1: GATE law + B15 | 0 / 591 / 0 | 49 | 0.000 | 0 |
| 2: FLOOR drift/robustness/extrapolation | 331 / 17 / 243 | 49 | 0.062 | 576 |
| 3: BLEND analytic traits | 317 / 80 / 194 | 49 | 0.057 | 0 |
| 4: GATE B15 assumed limit | 20 / 143 / 428 | 49 | -0.133 | 432 |
| 5: FLOOR B9/B16 assumed limits | 20 / 205 / 366 | 49 | -0.133 | 432 |
| 6: BLEND B15/B9/B16 | 298 / 95 / 198 | 49 | 0.133 | 0 |

The configured B15/B9/B16 quantities in this run are **analytic toy traits**,
not imported physical measurements. All switch limits/weights are unchanged
example ASSUMPTION values. Better median alignment coexists with negative
pairs and, for FLOOR, toy good-member exclusions. No switch is selected from
this tranche, and no threshold recommendation follows from it.

## Evidence and limits

[SUMMARY.csv](SUMMARY.csv) contains all 70 candidate-switch summaries, including
scope-specific coverage, top-1 regret and descriptive worst-tenth tau. The
four `RESULTS_*.json.gz` files retain each profile's tau and within-profile
bootstrap bands, reasons, exclusions, gamer flags and top-1 regret. The four
plans, [ATLAS.json.gz](ATLAS.json.gz), [CONTROL_GATE.json](CONTROL_GATE.json) and
[IDENTITY.json](IDENTITY.json) bind the sources and byte-level output identities.
[COMMANDS.md](COMMANDS.md) records the actual command sequence.

The atlas's `selection` and `sobol_indices` remain null. LHS median splits are
descriptive associations, not Sobol indices or causal effects. Thirty bootstrap
draws per profile and one toy seed do not establish real-world power. This
tranche is not a new Goodhart optimisation run; existing separate Goodhart and
feedback results keep their identities. It does not complete the broad
5,000-20,000 configuration campaign, all component combinations, or held-out
robust winner selection.

The next independent real-data dependency remains a qualified, applicable
reference/common question mask for EV4 fitting and replay. The merged public
v2 replay admits 0/24 full35 questions under its current applicability contract.
Realism calibration, actual battery value advantage, Test Engineer holdout and
final confirmation remain unmeasured. No hidden/AX42 data, spending, LIVE change,
production score adoption or scientific qualification is claimed.
