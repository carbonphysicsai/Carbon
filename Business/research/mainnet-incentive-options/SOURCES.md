# Source register and limits

Checked 2026-10-10. Primary maintainer sources, official contest/platform rules and Carbon's committed aggregates. No subreddit anecdotes or unsourced fraud/earnings rates are used.

## Carbon source snapshot

Main commit `fb47eb5725338a7733f6074650e58271c355006b`. Newer source support is not inferred to be LIVE. Numerical policy settings are sourced low=base=high; synthetic inputs retain their ASSUMPTION classification.

| Public file | Blob SHA | Evidence type |
| --- | --- | --- |
| [carbon/rewards/weight_policies/testnet-winner-v1.json](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/weight_policies/testnet-winner-v1.json) | `47e972b3c3d582b8d8092c9ce4e27df1cef19691` | Source/contract or conditional synthetic aggregate; not live receipts |
| [carbon/rewards/winner_decay.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/winner_decay.py) | `85b35e1e25661d7ea7cdaa8abe9240b00ff0cbae` | Source/contract or conditional synthetic aggregate; not live receipts |
| [carbon/rewards/winner_eligibility.py](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/winner_eligibility.py) | `31c366a56b24ada362b47910afcdb0aaf9236cf3` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-mechanism-sim/README.md](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-mechanism-sim/README.md) | `3b0a5517bee33434a2cb16988565aad1ad86055b` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-mechanism-sim/assumptions.v1.json](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-mechanism-sim/assumptions.v1.json) | `3be55d6fa3d47cb0f0783d406c0d396a52eeec01` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-mechanism-sim/curves.v1.csv](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-mechanism-sim/curves.v1.csv) | `e64a04f75503a8a6096193d81bb0c7773e4c6556` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-policy-options/README.md](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-policy-options/README.md) | `bc7e05fdac7598efa335372a6778e5680fd4546f` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-policy-options/assumptions.v1.json](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-policy-options/assumptions.v1.json) | `eb7352a81f37f6ddd861d103d2c2b666cbd62108` | Source/contract or conditional synthetic aggregate; not live receipts |
| [docs/development/incentive-policy-options/curves.v1.csv](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-policy-options/curves.v1.csv) | `bdc282923194ac318b0f05d281a1cc3bbc9423bf` | Source/contract or conditional synthetic aggregate; not live receipts |

PR lineage: [#974](https://github.com/carbonphysicsai/Carbon/pull/974) merged at `efd6ec5e37f32df964f56c752b2a4b37e32a7a9d`; [#989](https://github.com/carbonphysicsai/Carbon/pull/989) closed unmerged, head `780e9be0958f346cfe8d40292ab520ec8e679e96`; replacement [#1007](https://github.com/carbonphysicsai/Carbon/pull/1007) merged at `357231a02dd97a3d295f3fe3381dda932d32e1c3`. The replacement and predecessor do not count as independent evidence.

CSV selectors: #974 `comparison=paired_same_case, margin_rel=0.056993107446249414, decay_factor_per_period=0.5, comparison_windows=3`, then the strategy named in the table. #1007 the same margin/decay/evidence-window slice, then scenario/policy named in the table. P(best) bounds are Wilson MC intervals; duplicate-gain bounds are the committed paired episode-bootstrap intervals. Actor shares without intervals are source points, not precision claims. No CSV or simulation was changed.

## Bittensor and subnet primary sources

| Source | Supports | Limit |
| --- | --- | --- |
| [Official Yuma mechanism](https://www.bittensor.com/docs/internals/consensus) | Consensus clipping, trust and bond/dividend separation | Ideal mechanism/source description, not Carbon settlement |
| [Official liquid-alpha flag documentation](https://www.bittensor.com/docs/hyperparameters/liquid-alpha-enabled) | Classic/Yuma3 branch and per-pair bond response distinctions | Actual Carbon runtime/flags unobserved |
| [Official Null-consensus guide](https://www.bittensor.com/docs/guides/null-consensus) | Current alternative epoch mode has different agreement/bond behavior | No switch or adoption recommended |
| [Official weight-copying guide](https://guides.learnbittensor.org/learn/weight-copying-in-bittensor) | Documented validator free-riding and static-ranking caveat | No quantified fraud prevalence; distinct from miner recipe copying |
| [Macrocosmos SN1 incentive docs](https://docs.macrocosmos.ai/subnets/subnet-1-apex/incentive-mechanism) | Documented winner reward, delayed solution release and age/burn design | Maintainer-described intent, not causal proof of effectiveness |
| [Macrocosmos pretraining whitepaper](https://www.macrocosmos.ai/research/pretraining_whitepaper.pdf) | Historical maintainer-described competition design | No earnings/quality claim is imported into Carbon |

Public code heads checked:
- Subtensor `5c6e83e2f4936f257234f246957f75684c35227c`, [run_epoch.rs](https://github.com/opentensor/subtensor/blob/5c6e83e2f4936f257234f246957f75684c35227c/pallets/subtensor/src/epoch/run_epoch.rs), blob `b7d540d3164540cf0d0d4f0fcacf355929e4d9ab`; inspected public branch snippets, not a live chain.
- Pretraining `2def63f8c860cd51b74398f4101bede799b0010d`: [validation helper](https://github.com/macrocosm-os/pretraining/blob/2def63f8c860cd51b74398f4101bede799b0010d/pretrain/validation.py), blob `30796e8d22061070a5becec0c0d84b3fd0bf9d7f`; [constants](https://github.com/macrocosm-os/pretraining/blob/2def63f8c860cd51b74398f4101bede799b0010d/constants/__init__.py), blob `be525f58da741a343d39f21a34f1bad0329d22d7`. Main validator source contains extensive commented code; these are algorithm/configuration examples, not today's served implementation.
- Fine-tuning `afd44037e9a116fb1844dea6aaa0718cd23bc248`: [validator](https://github.com/macrocosm-os/finetuning/blob/afd44037e9a116fb1844dea6aaa0718cd23bc248/neurons/validator.py), blob `182e25d75f02a7cb2653880e5ee6e4797a70f4ad`; [constants](https://github.com/macrocosm-os/finetuning/blob/afd44037e9a116fb1844dea6aaa0718cd23bc248/constants/__init__.py), blob `31f33039074c0d9e81c2445e9048e7bf516cab4c`. Actual step selection inspected; downstream tracker/deployment not reconstituted.

The old technical-paper links under docs.learnbittensor.org/papers and docs.bittensor.com/papers redirected to a documentation landing page during this research. They are **not** used as verified full-text evidence. Current official guides and source are the cited basis; no generic “liquid alpha eliminates copying” claim is made.

## Comparable contests and theory

| Source | Supports | Limit |
| --- | --- | --- |
| [Kaggle Konwinski Prize rules](https://www.kaggle.com/c/konwinski-prize/rules) | Top-five ladder/threshold prize design and single-account requirement | Page indexed rules; fixed contest terms, not a repeated subnet |
| [Topcoder system-test prize conditions](https://www.topcoder.com/challenges/30087004) | Top-five ranking plus delivery/licence conditions | Particular contest, not a universal optimal slate |
| [ImageNet organizers, June 2, 2015](https://www.image-net.org/challenges/LSVRC/announcement-June-2-2015.php) | Documented multi-account excess queries and comparability failure | Historical benchmark abuse, not a token-economic incident |
| [Lazear and Rosen (1981)](https://doi.org/10.1086/261010) | Rank-order tournament incentive theory | Assumptions do not include Carbon's copyable artifacts, exam protocol or token economy |

The ImageNet account/query numbers are published lower bounds; no finite high bound is available. Other source points have low=base=high, with unmeasured real-world uncertainty left explicit. The note's policy effects are reasoned hypotheses, not sourced numerical forecasts.
