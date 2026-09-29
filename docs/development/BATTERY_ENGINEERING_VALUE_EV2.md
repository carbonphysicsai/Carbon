# EV2: pre-registration

**Status.** PRE-REGISTERED, 2026-09-29. This document and the contract
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
