# INCENTIVE-MECHANISM-SIM-01 — prospective incentive sensitivity

**DEVELOPMENT analysis only.** The curves are predictions conditional on synthetic qualities, an assumed window-noise model, and a fast comparison surrogate. They are not observed miner behavior, a testnet receipt, a qualified frontier policy, a recommended economic setting, or a basis for LIVE weights. No solver, hidden bank, AX42 data, chain transaction or spending was used.

## Reproduce

The [manifest](assumptions.v1.json) is the complete simulation input. Its source is the committed public-practice [run-5 summaries](../evidence/graphite-run5-q1/practice-summaries.json), pinned by SHA-256 `503b2cf04bffff3571ecc55f6a17413884e1b3739c8cee205ae36b84642c99ad`. Regenerate [all 324 aggregate curve rows](curves.v1.csv) and the [canary prediction template](canary-predictions.v1.json) with:

```sh
python -m scripts.dev.incentive_mechanism_sim \
  docs/development/incentive-mechanism-sim/assumptions.v1.json \
  docs/development/incentive-mechanism-sim/curves.v1.csv \
  --canary-predictions docs/development/incentive-mechanism-sim/canary-predictions.v1.json
```

The public summaries have 27 scores for nine recipes (three seeds each). The median within-recipe standard deviation is **0.001536 score units**. This is a seed/rebuild spread on 200 adaptively seen *public PRACTICE* cases. Applying it as the standard deviation of a 100-case future window is an **ASSUMPTION**, not a measurement of hidden-window noise. The worst recipe has substantially larger spread; the median is a robust but narrow proxy. The synthetic random seed is for offline replay and is unrelated to any exam seed.

## Mechanism represented

The score path follows the *provisional development* battery rule in [`carbon/battery/exam.py`](../../../carbon/battery/exam.py): lower case error wins; one scored submission per hotkey/window; a screen requires a relative margin beyond the incumbent; a fresh finalist comparison requires a better overall estimate and no important-region regression. The registered values represented here are `equivalence_margin_rel = 0.056993107446249414`, `n_min = 30`, `important_min = 10`, `alpha = 0.05`, and a 100-case screening/final panel. The registered final uses **4,000 percentile-bootstrap draws**. For a tractable multi-axis sweep, this script uses a *Gaussian mean-score model and normal interval* at the same alpha. It therefore does **not** reproduce a validator decision exactly, and it deliberately contains no import path to official bank or reference state.

The comparison sweep draws 1, 3 or 5 fresh synthetic evidence windows and delays promotion until that many windows are available. `paired_same_case` shares a declared 75% noise component between incumbent and challenger; `unpaired_counterfactual` draws independent noise and is not the approved final-comparison path. An assumed bank-level offset refreshes every exposure `E = 5` windows, reflecting the development bank's retirement cadence; this is not a case-level reproduction of the bank. Forty windows are observed, with a synthetic 20-window mapping to the current 24-hour reward period. That mapping is an **ASSUMPTION** about tempo duration, not a chain-time assertion.

After a decided promotion, the simulator models a **target** for one assumed Challenge share (`1/8` of network Q12) and burns the remainder. The current `0.5` alternative matches [`winner_decay`](../../../carbon/rewards/winner_decay.py)'s Q12 halving arithmetic: full share for the first reward period, then half each period. The `0.75` and `1.0` curves are hypothetical alternatives. A same-coldkey/sybil handoff never renews the reward clock, matching [`winner_eligibility`](../../../carbon/rewards/winner_eligibility.py). Under an ideal direct-winner-plus-burn publisher and exact settlement, the targets are also *conditional predicted emission fractions*. The model stops at target weights. It does not model publisher availability, UID conversion, consensus, chain readback, actual emitted Alpha, price, miner receipts, or settlement. Scientific promotion, target weight and observed emission remain separate.

The synthetic truth uses error 0.074 for the initial incumbent, 0.066 for the best model and 0.068 for the sybil actor. These numbers, the 0.0004 sniper offset, strategy arrival timing, one-eighth share, case dependence, bank offset and model admissibility are **ASSUMPTIONS**. Every model is assumed to pass mandatory gates. A copy uses the current incumbent's true quality but a distinct coldkey. `sybil_one_key_control` submits the same 0.068 model through one hotkey; `sybil` submits it through four. Both obey one scored submission per hotkey/window. An honest actor stops resubmitting after its model is incumbent. The timing actor withholds the 0.066 best model until window 5. Each window nominates only its best observed screen result; this is a simulation simplification.

## Selected curves

The CSV is the complete sweep of three relative margins (`0`, the registered ~5.7%, `10%`), three reward factors (`0.5`, `0.75`, `1.0`), three evidence-window counts (`1`, `3`, `5`), paired/unpaired evidence and six portfolio/control rows, with 60 Monte Carlo episodes each. `P(best paid)` means a positive theoretical target for the known best model, **not** observed payment. `Wrong dethrone` means a promoted candidate whose synthetic true gain fails the scenario margin. The CSV reports both time to first incumbent replacement and time until the known best is promoted, with censoring fractions. Recipient stability is the mean per-window total-variation distance over hotkey targets **and burn**; target variation isolates the amount change. The first-exposure column asks whether the best is paid before five windows elapsed. A five-window comparison can first pay at window 5 and therefore reads zero there by construction.

At the registered margin, current halving and three evidence windows:

| Comparison; strategy | P(best paid by first E=5) | P(best paid at window 40) | Best-model share of target | Attacker share of target | Mean window of best promotion if seen |
| --- | ---: | ---: | ---: | ---: | ---: |
| Paired; honest only | 1.000 | 1.000 | 0.904 | 0 | 3.02 |
| Paired; copy | 1.000 | 1.000 | 0.905 | 0 | 3.00 |
| Paired; sybil, one key | 0.817 | 0.817 | 0.739 | 0.166 | 3.00 |
| Paired; sybil, four keys | 0.617 | 0.617 | 0.558 | 0.347 | 3.00 |
| Paired; margin sniper | 0.950 | 1.000 | 0.893 | 0.012 | 3.45 |
| Paired; timing | 0 | 1.000 | 0.791 | 0.791 | 7.00 |
| Unpaired; sybil, four keys | 0.483 | 0.683 | 0.540 | 0.366 | 7.68 |

The four-key sybil's final best-model probability is 0.200 lower than its one-key control, and its attacker target share is 0.181 higher. The model's mechanism is repeated screening opportunity: the 0.068 model may promote before the 0.066 best model, after which the best model's true 2.9% gain is below the registered 5.7% margin. This is a **conditional counterexample**, not a measurement that a real sybil can do this on the official exam. The 60-run Wilson interval for the four-key row's `P(best paid at window 40)` is about 0.49–0.73; it covers Monte Carlo error only, not noise-model or science uncertainty.

At zero margin with one paired evidence window, the copy actor takes 0.175 of target and 38% of promotions fail the *zero-margin true-gain* test. At the registered margin and three paired evidence windows, its target is zero in this simulation; at one **unpaired** window it takes 0.017 and the wrong-dethrone rate is 4.8%. Paired same-case evidence is therefore a specific defense in this model. The sniper's target at the registered paired three-window row is 0.012. Delaying the best model from window 1 to 5 lowers its best-model target share from 0.904 to 0.791; the later reward-clock start does not repay the foregone early windows over this 40-window horizon. Different horizons or arrival laws could reverse that trade.

Across current halving, paired honest-only runs, the registered-margin rows pay the best by the first exposure with probability 1.000/1.000/0.000 for 1/3/5 evidence windows; mean promotion time is 1.00/3.02/5.00 windows. With the one-window rule, raising the margin to 10% lowers that first-exposure probability to 0.967. The three-window honest row pays 78.8% of the assumed Challenge budget under `0.5` decay, 89.4% under `0.75`, and 100% under `1.0`; mean normalized per-window target-amount change is 0.0128/0.0064/0, while recipient-and-burn total variation is 0.0385/0.0321/0.0256. These are reward-target sensitivity curves, not recommendations for a decay choice.

## Canary comparison and recommendations

The [canary prediction JSON](canary-predictions.v1.json) selects the paired, registered-margin, current-halving slice. Its join keys are evidence windows and strategy; it reserves an `observed: null` slot. The Validator can compare actual *target weights* and promotion times against it, keeping chain settlement/receipts in separate fields. **P(best paid)** and wrong-dethrone require independently known true model quality in a controlled testnet canary; if the canary lacks that, mark those observed metrics `NOT_IDENTIFIABLE` instead of estimating them from the score being tested. The canary should record actor/coldkey linkage to test the no-reset claim. A difference from these predictions is useful: it falsifies one or more assumptions, not the live observation.

Recommend a controlled paired-versus-unpaired diagnostic and one-versus-four-hotkey canary before selecting a promotion margin or reward cadence. Preserve common fresh paired evidence and the current same-coldkey no-reset behavior while the owner reviews the results. Treat anti-sybil admission or per-party rate limits as a separate protocol and identity decision; this analysis does not implement one. **The owner retains the margin, decay schedule, emission split and any policy change.** The score-to-weight target, actual emission and miner payment must remain separately measured.

Limits: nine public recipes, three seed repeats each; seed variation is not window noise; the Gaussian/normal-interval surrogate omits bootstrap tails and per-component gate interactions; no model-construction cost, registration burn, information advantage, collusion, case-level bank overlap, attack adaptation, missing reference, infrastructure failure, publisher outage or network settlement is simulated. The values are deliberately insufficient for economic optimization or scientific qualification.
