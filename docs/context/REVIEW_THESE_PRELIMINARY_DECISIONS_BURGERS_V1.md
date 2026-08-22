# Review These Preliminary Decisions — Burgers P0 v1 Repair

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science/protocol lead may accept, modify, or reject.  
**Purpose:** Convert the integrated Burgers repair/incentive experiments into an actionable v1 review queue.

---

# Executive recommendation

> **Do not broaden P0. Repair the existing Burgers Challenge into one fixed-viscosity, independently truth-qualified experiment that can actually support a meaningful admissible miner population and stable emissions signal.**

---

## B1 — Fix viscosity for the first authoritative P0 Challenge

**Preliminary decision: ACCEPT**

Set `nu = 5e-3` for the first authoritative `u0 -> u(T)` Challenge.

### Why

The current model receives only `u0`, while current data varies `nu`. The target is therefore not uniquely determined by the candidate input. Same-IC Cole-Hopf comparisons across viscosity changed final solutions by roughly 27-59% in a small pilot.

### Future

A later Challenge may explicitly define `(u0, nu) -> u(T)` and modify the candidate adapter accordingly.

**Confidence: Very high.**

---

## B2 — Use Cole-Hopf as primary P0 truth

**Preliminary decision: ACCEPT**

For periodic zero-mean viscous Burgers, use a pinned high-resolution periodic Cole-Hopf implementation as primary truth.

Keep independent numerical solvers as corroborating witnesses, not automatic authorities.

**Confidence: Very high.**

---

## B3 — Replace authoritative IMEX-generated labels with qualified truth labels

**Preliminary decision: ACCEPT**

The current IMEX Fourier method can remain a numerical implementation/regression witness. It must not be the sole source of official labels if its own numerical error can influence ranking.

**Confidence: Very high.**

---

## B4 — Remove final-state spatial-balance proxy from mandatory physics gates

**Preliminary decision: ACCEPT**

`|u u_x - nu u_xx|` without `u_t` is not a full Burgers PDE residual.

Keep only as `DIAGNOSTIC_ONLY` if correctly named. A future trajectory task can qualify a true spacetime residual.

**Confidence: Very high.**

---

## B5 — Use final-state physical invariants for P0 admissibility

**Preliminary decision: ACCEPT**

Candidate measurement set should include, after qualification:

- finite output;
- periodic mean/mass conservation;
- energy non-increase;
- maximum-principle consistency;
- truth-relative accuracy;
- required stress-stratum accuracy.

Exact thresholds remain Challenge/Dossier values.

**Confidence: Very high.**

---

## B6 — Score-bearing stress must remain inside explicit registered semantics

**Preliminary decision: ACCEPT**

Do not use undeclared low-viscosity, amplitude, or `tanh` stress transforms simply because generator code can produce them.

P0 v1 should stress IC shape/amplitude at fixed viscosity. Any expanded family requires explicit distribution semantics and qualification.

**Confidence: Very high.**

---

## B7 — Require a non-degenerate admissible strategy population before LIVE

**Preliminary decision: ACCEPT**

A valid Challenge must demonstrate that realistic strategy variation can produce:

- more than one admissible candidate;
- meaningful soft-score separation;
- clear failure of intentionally poor strategies.

A judge that rejects all realistic miners cannot support a useful incentive market.

**Confidence: Very high.**

---

## B8 — Treat reconstruction variability as method-level evidence

**Preliminary decision: ACCEPT**

Fixed-viscosity pilots showed that different reconstruction seeds of the same strategy can cross the admissibility boundary.

Before production, quantify admissibility probability and score dispersion across independent reconstruction seeds. Do not select the best reconstruction post hoc.

Exact repeat count remains open pending cost/variance data.

**Confidence: Very high.**

---

## B9 — Require fresh-draw rank stability before emissions

**Preliminary decision: ACCEPT**

Controlled synthetic candidates retained the same scientifically expected ordering across 20 fresh draw bundles. Real strategy populations must undergo the same test before LIVE.

**Confidence: Very high.**

---

## B10 — Require validator numerical agreement

**Preliminary decision: ACCEPT**

A pilot float32/float64 evidence calculation produced a maximum combined-score difference of about `5.7e-8`, far below controlled candidate separations.

Production qualification should similarly demonstrate that validator implementation disagreement is below the Challenge's scientific resolution.

**Confidence: Very high.**

---

## B11 — Start emissions mapping proportionally

**Preliminary decision: ACCEPT FOR P0 BASELINE**

Within one Challenge, map positive `VALID_RANKED` scores proportionally at first.

Do not start with winner-take-all or aggressive softmax concentration.

Any stronger power/temperature is a separately versioned economic parameter that must be justified by stable rank-resolution data.

**Confidence: High.**

---

## B12 — No admissible candidate means no scientific winner

**Preliminary decision: ACCEPT**

Emit `NO_ADMISSIBLE_SCIENTIFIC_SIGNAL` rather than rewarding the least-bad failing candidate.

Bittensor/runtime fallback behavior must preserve this semantic truth.

**Confidence: Very high.**

---

## B13 — Keep training-time physics terms as miner hypotheses

**Preliminary decision: ACCEPT**

The compact pilot found data-only and data+current-physics penalties very similar, while physics-only optimization could satisfy its training penalties and still be physically inaccurate against truth.

No training-loss term receives score privilege because it is labelled `physics`.

**Confidence: Very high.**

---

## B14 — Do not update high-level public claims until the repaired P0 loop is rerun

**Preliminary decision: ACCEPT**

The architecture is strong, but WP/LP/deck empirical language should wait until:

```text
fixed-nu Challenge
+ qualified truth
+ repaired measurements
+ realistic strategy bank
+ reconstruction repeats
+ fresh-draw stability
+ validator agreement
+ conservative emissions mapping
```

has been executed as one integrated loop.

Architecture-level explanatory updates may proceed separately.

**Confidence: High.**

---

# Recommended immediate implementation order

```text
1. create fixed-nu Burgers challenge profile
2. implement/pin Cole-Hopf truth backend
3. add final-state invariant measurements
4. remove residual proxy from score-bearing path
5. constrain/rewrite stress suite to registered fixed-nu semantics
6. run larger strategy × reconstruction × eval-seed matrix
7. calibrate thresholds/repeat policy from dossier evidence
8. validate independent validator package
9. bind Score Pack v1 profile
10. enable conservative emissions mapping only after all above pass
```

---

# Owner conclusion

> **The integrated gauntlet did not show that Carbon's architecture is unsound. It showed that the original Burgers instantiation violated the architecture in several concrete ways. The fixed-viscosity v1 repair is the smallest path to an honest P0 experiment.**
