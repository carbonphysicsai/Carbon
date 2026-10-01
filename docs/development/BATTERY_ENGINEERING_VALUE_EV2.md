# EV2: pre-registration

**Status.** RUN, 2026-10-01. Results are in §6. Pre-registered 2026-09-29. This document and the contract
`carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json`
(digest `sha256:1877091055d1dac2515da5aa05bf4f0ad56cf3376045d73086dcf1f0848ce743`)
were committed **before any EV2 reference solve or reconstruction**. Results are
added in a later commit. Anything changed after the first solve is reported as
a change, not silently applied.

**Authority.** The owner approved EV2 and the decision-aware robustness
component on 2026-09-29, as programme-state items 14 and 15.

**Scope.** Public synthetic DEVELOPMENT evidence only:
- no chain action, reward or spend;
- no change to the testnet rule;
- no qualification claim;
- "best" always means best in the tested candidate set.

## 1. Why EV2 exists (from EV1)

EV1 (`BATTERY_ENGINEERING_VALUE_EV1.md` §5) left three open problems:

1. **Its verification test was degenerate.** No verification scenario had a
   feasible protocol, so verification only measured whether a model avoided a
   false acceptance.
2. **The score has a blind spot.** An error-accurate `boundary_optimist`
   control, which selects unsafe protocols, scored above every reconstructed
   member.
3. **The panel was mostly repeated seeds.** Its members were largely seed
   repetitions of one MLP recipe.

## 2. What changes, and what does not

| | EV1 | EV2 |
|---|---|---|
| Decision unit | one protocol per scenario, worst case over 4 conditions | **one protocol per operating condition** |
| Candidates | c1 {0.75, 1.25, 1.75, 2.0} × c2 {0.4, 0.6, 0.8, 1.0} = 16 | **c1 0.5–2.0 in steps of 0.25 (7) × c2 0.2–1.0 in steps of 0.2 (5) = 35**, the generator's full range in even steps |
| Conditions | 3 + 3 scenarios × 4 | **8 development + 8 verification, fresh.** Development: t_amb {7, 17, 27, 37} °C × soc0 {0.08, 0.28}. Verification: t_amb {11, 21, 31, 40} °C × soc0 {0.18, 0.45}. No EV1 condition repeats. |
| Reference solves | 384 | 560 |
| Panel | 11 members, 7 recipes | **15 members:** EV1's 11, plus DeepONet (2 seeds), a wide shallow MLP (512 × 2) and a 15-neighbour kNN |
| Scoring rules | control and 4 weight profiles | the same, **plus 3 decision-aware profiles** |

**Unchanged from EV1:**
- the objective, the 4.19 V time-to-CV-onset definition, and the constraints
  and their thresholds (plating margin ≥ 0 V, peak temperature ≤ 45 °C,
  reaching CV within the window);
- the uncertainty bands;
- the mistake costs (false acceptance 10, missed opportunity 1, regret 1 per
  120 s);
- the minimum useful improvement, the baseline (c1 0.75, c2 0.6) and the tie
  rule;
- the pinned PyBaMM reference, the scoring set (refs-b, 1588 cases) and EV1's
  weight profiles;
- the rule-selection rule: choose on development by Kendall τ, ties to the
  control.

**Why these choices were made without EV1's verification results:**
- The per-condition decision and the full-range grid follow from the *reason*
  EV1 was degenerate: a worst case over four conditions, combined with a grid
  that excluded gentle protocols. They do not follow from which EV1 protocols
  won.
- The EV2 conditions are regular grids fixed before solving.
- If a verification condition still has no feasible protocol, it is reported,
  never replaced.

## 3. The decision-aware robustness component

**What the component compares.** For every scoring-set case and every contract
constraint, it compares two calls:
- the model's PASS/FAIL call, from its own predictions, with no band;
- the reference's call, with the contract's uncertainty bands.

An UNRESOLVED reference call is excluded, never forced either way.

**Costs.** A false acceptance (model PASS, reference FAIL) costs the contract's
`false_acceptance` (10). A false rejection costs `missed_opportunity` (1).

**Score.** Component = 1 / (1 + mean cost per resolved call), in (0, 1].

**No new number is chosen.** The constraints, bands and costs are the
contract's.

**The profiles that use it.** In the decision-aware profiles, the robustness
leg *is* this component. It replaces the important-region error, which is a
separate experimental factor.

| Profile | physics | robustness (decision) | accuracy |
|---|---|---|---|
| `dar-p0-r100-a0` | 0 | 1.0 | 0 |
| `dar-p0-r30-a70` | 0 | 0.30 | 0.70 |
| `dar-p0-r50-a50` | 0 | 0.50 | 0.50 |

Physics stays NOT_MEASURABLE for battery. Gates stay mandatory under every rule.

## 4. Hypotheses and how they are reported

- **H1 (primary).** Kendall τ between two rankings of the reconstructed
  members, on the verification conditions:
  - the ranking by the development-chosen rule's score;
  - the ranking by decision loss.

  Every other rule's τ is reported beside it. No significance claim is made at
  this panel size.
- **H2 (pass/fail).** `dar-p0-r100-a0` scores the labelled `boundary_optimist`
  control below **every** eligible reconstructed member. The same check is
  reported for every rule.
  - **Interpretation, fixed now:** H2 shows sensitivity to one constructed
    failure mode, optimism at the limits. It does not show that the component
    catches every unsafe model. The controls' definitions are EV1's,
    unchanged.
- **Neither outcome changes the testnet rule.** Adopting a decision-aware
  component on the exam would need its own prospective owner decision.

## 5. How it runs

- **Command:**
  `python -m carbon.battery.value run --root <root> --contract carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json`.
  It is resumable, one runner per root.
- **References:** pinned PyBaMM (`pybamm==26.8.0.0`) from the hash-locked
  overlay, on sandbox CPU, like EV1. This is not the digest-pinned image.
- **Cost:** USD 0. OD-5 is untouched.
- **Reconstruction:** Carbon rebuilds every member from its recipe on public
  TRAIN v1 with its declared seed. Selection sees predictions only.

## 6. Results (run of 2026-09-30 to 2026-10-01)

**Evidence:** `docs/development/evidence/ev2-2026-10-01/`. It holds the
manifest, results, report, the 560 decision references (gzipped) and the
digests of the 15 prediction bundles. The contract digest is unchanged from
the pre-registration.

**What ran.**
- **References:** 560 decision-reference solves, all on the conditions fixed
  in advance.
- **Members:** 15 reconstructed members plus the five EV1 controls.
  `mlp_raw-s0` failed a mandatory gate and is ineligible under every rule, as
  in EV1.
- **Interruptions:** container restarts and job time limits interrupted the
  run several times. Each time it resumed from its own records; no reference
  or prediction was recomputed or reinterpreted.

**What changed after the first solve.** One cosmetic change: the generated
report was titled "EV1" whatever the contract. It is now titled from the
contract's `case_prefix`. No number changed.

### 6.1 The EV1 design problems are fixed

The verification conditions are no longer degenerate.
- **EV1:** no verification condition had a feasible protocol.
- **EV2:** 6 of the 8 verification conditions have a best feasible protocol
  in the tested set. The other two (V-T11-S0.18 and V-T40-S0.18) have none,
  and are reported as such.

### 6.2 H2 (pass/fail): PASS

`dar-p0-r100-a0` scores the `boundary_optimist` control below every one of
the 14 eligible reconstructed members.

| Rule | Optimist below every eligible member | Members at or below it |
|---|---|---|
| control-exam-v1 (current testnet rule) | no | 14 of 14 |
| p0-r30-a70 | no | 7 of 14 |
| p0-r20-a80 | no | 13 of 14 |
| p0-r40-a60 | no | 5 of 14 |
| dar-p0-r100-a0 | **yes** | 0 of 14 |
| dar-p0-r30-a70 | **yes** | 0 of 14 |
| dar-p0-r50-a50 | **yes** | 0 of 14 |

- **The current rule is blind to this failure.** Under the testnet rule, the
  optimist scores at or above every real member. EV1 found the same thing.
- **The decision-aware component fixes it,** at every weight tested, even
  at 30%.
- **What this does not show** (the interpretation fixed in §4): this is
  sensitivity to one constructed failure mode. It does not show that the
  component catches every unsafe model.

### 6.3 H1 (primary): weak and positive, and not better than the current rule

Kendall τ between each rule's ranking and the decision-loss ranking. The
rule is chosen on development and reported on verification.

| Rule | τ development | τ verification |
|---|---|---|
| control-exam-v1 (current) | -0.030 | 0.298 |
| p0-r30-a70 | -0.050 | 0.317 |
| p0-r20-a80 | -0.050 | 0.317 |
| p0-r40-a60 | -0.050 | 0.298 |
| **dar-p0-r100-a0 (chosen on development)** | **0.188** | **0.202** |
| dar-p0-r30-a70 | 0.050 | 0.221 |
| dar-p0-r50-a50 | 0.129 | 0.221 |

- **Every measurable rule has a positive verification τ** (0.20 to 0.32): a
  higher score went with better decisions on the fresh conditions.
- **The development-chosen rule did not carry its advantage over.** It was
  the best rule on development (0.188 against -0.030 for the current rule).
  On verification it is the lowest (0.202 against 0.298).
- **Treat these values as indicative.** With 14 members, the differences
  between rules here are not distinguishable from noise. No significance
  claim is made (§4).
- **The verification losses barely separate the members.** Most real members
  lose almost nothing on verification (9 of 14 lose less than 0.2), so the
  ranking by decision loss is close to ties. This limits what τ can show.
- **With the controls included,** the decision-aware rule separates good
  and bad deciders far better on development (τ 0.466 against -0.071 for the
  current rule). Most of that comes from the controls themselves.

### 6.4 Against the pre-registered statements

| | Stated at `5f0756ad` | Observed | Verdict |
|---|---|---|---|
| H2 | `dar-p0-r100-a0` scores `boundary_optimist` below every eligible member | below all 14 (`summary.boundary_optimist_check`) | **CONFIRMED** |
| H1 | Kendall τ of the development-chosen rule against decision loss on verification, every other rule beside it; no predicted value, no significance claim | 0.202 for the chosen rule, 0.298 for the current rule, lowest of the measurable rules (`comparison.*.tau_verification`) | **No prediction to confirm or refute.** The pre-registration fixed a measurement, not an expected value. The natural reading, that a rule chosen for decision quality on development would rank verification decisions better than the current rule, **did not hold** on this panel. That is a result, and it is not rescued by the panel's low resolution. |

**Score or panel?** EV2 tests the asymmetric cost in the contract's
`mistake_costs`: a false acceptance costs 10 and a missed opportunity costs 1,
in multiples of the minimum useful improvement (`PROVISIONAL_DEVELOPMENT`).
- **H2 implicates the score.** The current testnet rule
  (`control-exam-v1`) ranks the optimist above all 14 real members. That
  happens on the same panel, predictions and references where every
  decision-aware rule ranks it below all 14. The panel exposes the optimism.
  The current score does not price it.
- **H1's weakness implicates the panel.** 9 of 14 real members lose less
  than 0.2 on verification, so the decision-loss ranking is close to ties
  and τ has little to resolve. This limits what H1 can show about any rule.
  It is not evidence that the decision-aware component is wrong.

**Maturity.** Exploratory engineering evidence. It does not qualify the exam
or any rule. MQ-008 is untouched, and no testnet rule changes.

### 6.5 What this means

- **Recorded:** the current testnet rule ranks a model that is optimistic at
  the safety limits above every real model. Two independent experiments now
  show this (EV1 and EV2).
- **Recorded:** a decision-aware component, built only from the contract's
  constraints, bands and costs, removes that blind spot. On verification its
  τ was the lowest of the measurable rules (0.202 against 0.298). The panel
  cannot resolve that difference, so it is reported, not dismissed.
- **Not shown:** that the decision-aware rule ranks real models better than
  the current rule. On this panel, it did not.
- **No rule change follows.** As fixed in §4, adopting a decision-aware
  component on the exam needs its own prospective owner decision. The
  evidence above is what that decision would rest on.
- **Next:** EV3 (design competition) tests whether the score predicts which
  model produces the best design. It is designed and waits on the owner's
  ranking of its candidate problems.
