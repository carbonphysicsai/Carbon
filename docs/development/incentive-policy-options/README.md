# INCENTIVE-POLICY-OPTIONS-01 — duplicate reward policy options

**DEVELOPMENT simulation only.** These are predictions conditional on synthetic
qualities, assumed artifact identities and distances, the pinned *public
practice* seed-spread noise proxy, and #974's Gaussian/normal-interval
comparison surrogate. They are neither observed testnet emissions nor a
qualified incentive policy. The owner controls margins, decay, duplicate
identity, attribution, emission split and any activation.

## Reproduce and interpret

The [manifest](assumptions.v1.json) pins every assumption. Generate the
[315 aggregate rows](curves.v1.csv) with:

```sh
python -m scripts.dev.incentive_policy_options \
  docs/development/incentive-policy-options/assumptions.v1.json \
  docs/development/incentive-policy-options/curves.v1.csv
```

The source of score noise is the 27-score, nine-recipe *public practice*
[run-5 summary](../evidence/graphite-run5-q1/practice-summaries.json), SHA-256
`503b2cf04bffff3571ecc55f6a17413884e1b3739c8cee205ae36b84642c99ad`.
Its median within-recipe seed SD (~0.001536 score units) is **not measured
exam-window noise**. The synthetic incumbent/best/weaker-model errors are
0.074/0.066/0.068. A normal interval at registered development alpha 0.05
approximates the 4,000-draw bootstrap; it does not reproduce the validator.
All candidates are assumed admissible. The paired same-case correlation is an
assumed 0.75, three fresh comparison windows are used, the horizon is 40
synthetic windows and bank exposure is five. The synthetic similarity
coordinate and thresholds 0.012/0.055 are unitless **ASSUMPTIONS**, not a
measured model-similarity rule. The latter intentionally over-merges a better
model under a first-submitted weaker artifact. The assumed one-eighth Challenge
budget and 20-window reward period are for target-weight arithmetic only.

The five policy labels mean:

| Policy | Screening | Target attribution |
| --- | --- | --- |
| `hotkey` | Each hotkey receives a chance | Winner hotkey |
| `digest_split` | One query per exact rebuilt-artifact digest | One total artifact target, split equally among its registered hotkeys |
| `digest_first` | One query per exact digest | First registered claimant owns the target |
| `near_first_tight` / `near_first_wide` | One query per assumed similarity cluster | First claimant of the winning artifact |

The `exact_four` actor submits four hotkeys with one synthetic digest; its
one-key control has the same model. `near_four` has four distinct digests with
equal assumed true quality and nearby coordinates; its one-key control has
one. The `copy_best_*` cases submit the **same best artifact** from honest and
attacker hotkeys and reverse their assumed within-window registration order.
This ownership test is distinct from #974's weaker-actor sybil comparison and
from the Validator's live two-miner strong-recipe canary.

This simulator retains #974's **one incumbent target per window**. It tests
extra screening opportunity and hypothetical attribution of that single
target. It does **not** predict whether the deployed publisher can create two
simultaneous targets for the same rebuilt artifact; the live canary must
measure that separately.

The CSV's `P(best paid)` means the known-best **model** holds a positive
theoretical target at window 40. It can be credited to the wrong actor.
`attacker_target_fraction` and `sybil_gain_vs_one_key` are fractions of paid
**target weight**, not actual Alpha or receipts. Sybil gain is the four-key
minus one-key attacker share using matched episode identities; its percentile
bootstrap interval covers Monte Carlo resampling only. Time to best and time
to first dethrone are conditional means with censoring reported separately.
`false_merges_per_run` counts repeated windows in which the assumed similarity
rule groups models with different true quality; it is not a calibrated
false-positive rate. There are 80 deterministic Monte Carlo episodes per row.

## Selected decision curves

At the registered ~5.7% relative challenger margin and current 0.5 decay,
with three fresh paired comparison windows:

| Attack / policy | P(best target at W40) [MC 95%] | Attacker target share | Four-vs-one gain [MC 95%] | Wrong dethrone rate | Time to best if seen; censored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact four / per hotkey | 0.688 [0.579, 0.778] | 0.282 | +0.192 [0.113, 0.271] | 0 | 3.0; 31% |
| Exact four / digest split | 0.900 [0.815, 0.948] | 0.090 | 0 | 0 | 3.0; 10% |
| Exact four / digest first | 0.900 [0.815, 0.948] | 0.090 | 0 | 0 | 3.0; 10% |
| Near four / digest first | 0.650 [0.541, 0.745] | 0.317 | +0.238 [0.147, 0.328] | 0 | 3.0; 35% |
| Near four / tight assumed cluster | 0.775 [0.672, 0.853] | 0.204 | +0.124 [0.057, 0.192] | 0 | 3.0; 23% |
| Near four / wide assumed cluster | 0 [0, 0.046] | 0.904 | 0 | 0 | never; 100% |

Exact-digest deduplication removes the *extra screening chances* for exact
clones in this model; merely capping the eventual total target without
deduplicating before screening would leave #974's route open. It does not
stop distinct near-clone artifacts. The wide assumed threshold makes their
measured sybil gain zero only by suppressing the honest better artifact when
the weaker submission arrives first. That option fails the core objective.

For the same slice, copying the best artifact leaves model-level
`P(best paid)` at 1.000 under both digest policies. Under an equal split, the
copier receives 0.452 of paid target even when the honest submitter was first.
Under first-committer attribution, the copier receives 0 when honest was
first, but 0.905 when the copier was first. **A first-committer rule requires
an authenticated, fair registration order and a policy for independent
identical rebuilds.** A digest split needs a defense against reward capture
through duplicate registrations. Neither attribution rule is safe merely
because exact hashes match.

The full CSV sweeps margins 0, registered ~5.7%, and 10%, and decay factors
0.5, 0.75 and 1.0. At the registered margin, the exact-four digest-first row
keeps `P(best paid)=0.900` across decay factors; paid fraction of the assumed
Challenge budget rises 0.788 → 0.894 → 1.000. The attacker share changes
0.090 → 0.092 → 0.093. Decay changes the amount and stability of target
weight, not the promotion decision in this model. At zero margin, a weaker
model can be promoted and later displaced; at 10%, the assumed best is just
above the threshold relative to the initial incumbent while smaller genuine
improvements could be barred. These synthetic points cannot select a
production margin.

## Dominance and owner packages

For the exact-clone attack at the registered slice, both exact-digest policies
improve model-level best-paid probability and reduce attacker target share
relative to per-hotkey admission, with no worse measured wrong-dethrone or
conditional promotion time. This is **scenario-specific** dominance; the
Monte Carlo intervals and unmeasured false-identification risks still matter.
No rule dominates across exact clones, distinct near clones and copied-best
ownership. The wide near threshold is especially unstable to arrival order.
The three decay choices trade higher target continuity against lower burn;
the simulation cannot select an economic preference.

The following are **review packages**, not changes to any registered rule:

1. **Exact digest plus first claimant, current margin and decay.** Retain
   paired fresh evidence. Requires a trustworthy commit-order mechanism and
   duplicate ownership rules before adoption. Test the live canary's actual
   target weights against the exact-clone prediction.
2. **Exact digest plus one shared target, current margin and decay.** Removes
   duplicate screening chances without a winner-takes-first race, but the
   equal-split prototype rewards copying. It is viable only with an owner
   attribution decision that closes duplicate registration capture.
3. **Near-duplicate research option only.** Keep exact-digest deduplication;
   evaluate a prospective measured similarity rule on independent artifacts,
   including false merges and false splits, before any threshold or payout
   consequence is proposed. The assumed tight radius leaves a positive
   near-clone gain; the assumed wide radius blocks the best model.

The Validator can compare actual **weight targets**, duplicate suppression,
promotion timing and recipient attribution from a controlled canary with
these predictions. Actual emitted Alpha and receipts require separate
observations. The canary cannot by itself identify true best or wrong
dethrones without independently known quality. This study neither changes
testnet behavior nor validates mainnet economics.
