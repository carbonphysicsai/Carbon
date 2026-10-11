# Mainnet incentive options and evidence limits

**MAINNET-INCENTIVE-OPTIONS-01 — research only; no option adopted.**

The owner retains economics, identity/attribution, legal rights and deployment decisions. [Business Canon](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/Business/Business_Canon.md) and [invariants](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/.agent/INVARIANTS.md) separate commercial value, scientific merit, frontier promotion and settlement. No solver, construction, rescore, incentive simulation, chain read/write, hidden state, AX42 or spend was used. This note reads public source and previously committed aggregate simulations.

## The mechanism has separate layers

A reward distribution cannot fix an unsafe or low-value scientific ordering. First test the judge under SCORE-PROOF-DESIGN-01; safety gates cannot be compensated by payouts. Then keep these layers explicit:

| Layer | Question | Authority boundary |
| --- | --- | --- |
| Admission/query opportunity | Which submitted artifact gets evaluated, how often, under what duplicate rule? | Anti-abuse/identity protocol, separately reviewed; no prior-similarity term smuggled into official scientific score |
| Measurement and scientific promotion | Has a contender passed the registered gates and fresh comparison? | Registered scientific contract; payment, fees, sponsor size and similarity do not create merit |
| Artifact attribution | Which authorized claimant receives entitlement for identical submitted work? | Owner legal/economic decision; a hash proves byte identity, not authorship |
| Reward target | Winner/slate share, temporal smoothing, decay and unused-share destination | Owner economic policy, versioned separately from the score |
| Consensus/transport | How validator rows are combined, masked, clipped, delayed and rounded | Actual network/runtime configuration; local targets are not settled payouts |
| Settlement | Who actually received how much, when? | Finalized receipts; no token-value or income forecast from a target weight |

Winner-take-most and top-k describe **recipient allocation**. Smoothing describes **temporal response**. Decay describes **budget versus incumbent age**. They are composable dimensions, not four mutually exclusive mechanisms. Challenger advantage/margin is another dimension; copying controls cannot be inferred from any one distribution shape.

## Carbon baseline: what source actually says

Pinned Carbon main snapshot `fb47eb5725338a7733f6074650e58271c355006b`; full source identities in [SOURCES.md](SOURCES.md).

The [testnet-winner-v1 policy](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/weight_policies/testnet-winner-v1.json) lists **N=3** Challenges. Each gets integer `Q12 // N`; unused shares and rounding go to burn. [winner_decay](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/winner_decay.py) gives the eligible incumbent its full share during the first **24 hours**, then halves it each **24 hours**. Policy cadence is **360 blocks**. These are **SOURCE_FACT, low=base=high**, not recommendations for mainnet. They differ from the sims' assumed N=8 and synthetic window-to-day mapping.

The [eligibility ledger](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/carbon/rewards/winner_eligibility.py) follows the validator's actual incumbent and eligible promotion, not a floating-point leaderboard winner. Registered fresh decided improvements are eligible; the version's absent public baselines allow its provisional first-incumbent route. All three baselines and the self-improvement factor are null in this version. Same hotkey or same coldkey retains its previous clock; another coldkey is not proof of another independent human. Ineligible or absent-metagraph winners burn their share. This research does not propose loosening those conditions.

The policy parser recognizes a separately authorized `finney` route as well as testnet. Its historical “testnet” wording must not be used to claim mainnet support is absent; equally, source support is not proof of a live deployment, owner adoption or actual emissions. No live Carbon configuration was inspected here.

## Compare the four families

The comparative effects below are **mechanism hypotheses/inferences**, unless explicitly linked to a source or committed result. No entry rate, fraud rate or expected miner income is invented.

| Family | Copy/Sybil behavior | Newcomer/ incumbent effect | Validator agreement and lag | Fit to Carbon |
| --- | --- | --- | --- | --- |
| **Winner-take-most**: one scientifically established incumbent takes the active Challenge allocation; residual may burn | A copy cannot create new merit, but duplicate screens can create extra noisy chances before promotion. A single payout slot limits simultaneous recipient splitting, not screening Sybils or claimant theft. | Clear high payoff for a real advance. A strong incumbent plus a large meaningful-gain margin can exclude genuinely better but smaller improvements. Entry response is unmeasured. | Different validators selecting different winners can generate abrupt disagreement/clipping. A shared final promotion receipt can improve consistency, but agreement alone cannot establish physical truth. | Closest to current one-incumbent target route. Keep fresh paired scientific comparison and distinct attribution/admission review. #974 supplies a conditional lock-in counterexample. |
| **Top-k**: a bounded slate of independently admissible useful models gets a declared allocation | Without artifact/actor controls, one builder can occupy several slots. Splitting one model's target among duplicate identities still invites registration capture. | Can reward a credible runner-up before it dethrones a frontier leader. May reduce the expected winner prize and pay unneeded near copies. More models require final evidence. | Boundary at rank k remains discontinuous. Slate disagreement can affect several miner columns. Rank-based shares avoid relying on arbitrary score units; they do not solve judge error. | Requires a new owner contract for slate eligibility, retention/revalidation and allocation. Current incumbent ledger does not establish qualified runners-up. No Carbon top-k behavioral result exists. |
| **Smoothed allocation/targets**: blend newly authorized target and prior target | A persistent copier can inherit a reward tail if it was previously credited. Broad positive tails across identities amplify clone capture unless total artifact entitlement is capped. | Softer transitions help continuity but delay reward to new genuine winners. Incumbent tails consume newcomer budget. | Can reduce target churn, while extending stale disagreement and making old rows valuable to weight copiers. Chain bond EMA and local target EMA are different mechanisms. | Would add target-state/version and withdrawal semantics. A failed/ineligible model must not remain payable because of history. #1007 did not test local EMA or softmax. |
| **Decaying reward/burn**: active share depends on time since an eligible advance | Same-actor no-reset blocks simple replay through linked keys. Distinct unlinked coldkeys or attribution changes may still try to restart age. Age decay is not duplicate detection. | Reduces passive income but may lower reward for late entrants and useful plateaus. A reset rule can invite minimal tweaks or strategic waiting. | Changes amount even with the same recipient; validators need consistent clocks/promotion receipts. Does not reduce disagreement about quality. | Already implemented in the pinned testnet route. #974/#1007 compare decay factors conditionally; they do not identify the best long-run policy. |

Illustrative mathematical definitions, **not runtime policy**:

- Winner: target for the registered incumbent is the active Challenge share B; all other recipients have zero in that Challenge.
- Top-k: target_i = B*r_i/sum_(eligible slate) r, with r_i declared rank shares. Eligibility, k, ties, group budget and unfilled-slot disposition are **HUMAN_INPUT**.
- EMA option: T_t = lambda*T_(t-1) + (1-lambda)*A_t, where lambda is **retained-history weight**. Reapply admissibility, identity and Challenge-budget caps before publication; null/failed targets cannot survive through an old tail. The removed amount's burn/redistribution treatment is **HUMAN_INPUT**.
- Smooth score-response option: a declared monotone map of within-Challenge eligible decision merit, with a temperature/scale **HUMAN_INPUT**. Raw scores across Challenges are not comparable; an exponential of arbitrary score units is not an economic law.
- Decay option: active B_t = B*d(age_since_eligible_advance), with start/reset/halting/unused-budget rules **HUMAN_INPUT**. The current halving is one source-pinned d, not the default for this proposal.

## External examples: practice, code and theory have different force

| Primary source | What it documents | Transfer to Carbon and limits |
| --- | --- | --- |
| [Macrocosmos SN1 Apex incentive documentation](https://docs.macrocosmos.ai/subnets/subnet-1-apex/incentive-mechanism) | A full competition reward for the best submitted solution; delayed code release; increasing burn while a solution remains unchallenged | A documented winner-plus-age/burn design. Publication describes intent, not independently measured anti-copy or newcomer outcomes. Reveal delay concerns submission code, not hidden exam disclosure. |
| [Macrocosmos pretraining whitepaper](https://www.macrocosmos.ai/research/pretraining_whitepaper.pdf) and [pretrain/validation.py](https://github.com/macrocosm-os/pretraining/blob/2def63f8c860cd51b74398f4101bede799b0010d/pretrain/validation.py) | Maintainer-described winner competition; pairwise loss comparisons give earlier submissions an age-dependent epsilon advantage | Epsilon decay reduces **incumbent comparison advantage**, not payment halving. Do not import it into Carbon's scientific score or relax evidence gates. |
| [Pretraining constants](https://github.com/macrocosm-os/pretraining/blob/2def63f8c860cd51b74398f4101bede799b0010d/constants/__init__.py) | One configuration uses LinearDecay from 0.005 to 0.0005 over 50,400 blocks; other competitions differ | SOURCE_FACT point values, low=base=high. No wall-clock duration or deployed adoption inferred. At this main head, substantial validator source is commented out: the helper and configuration are not proof of today's served route. |
| [Fine-tuning validator](https://github.com/macrocosm-os/finetuning/blob/afd44037e9a116fb1844dea6aaa0718cd23bc248/neurons/validator.py) and [constants](https://github.com/macrocosm-os/finetuning/blob/afd44037e9a116fb1844dea6aaa0718cd23bc248/constants/__init__.py) | Step weights select every exact highest-win-rate tie, then a competition tracker updates subnet weights; configured ALPHA=0.90 and minimum competition-weight threshold=0.18 | A source example of winner selection followed by temporal processing. A stale docstring says softmax; the actual step assignment is binary winner/ties. Dependency behavior and deployed weights must be verified before calling it a particular smoothing schedule. Values are not Carbon defaults. |
| [Kaggle Konwinski Prize rules](https://www.kaggle.com/c/konwinski-prize/rules) | Leaderboard prizes for five places, additional threshold prizes, a larger top prize; multiple accounts prohibited | A bounded top-k contest with separate eligibility/rights rules. Its fixed contest prizes do not predict continual subnet emissions, registration economics or miner retention. |
| [Topcoder final-prize example](https://www.topcoder.com/challenges/30087004) | Top-five system-test placement plus runnable submission, documentation and licence conditions for final prizes | Ranking is necessary but not sufficient for award. Useful analogue for independently verified product deliverables, not evidence that k=5 is optimal. |
| [Lazear–Rosen (1981)](https://doi.org/10.1086/261010) | Rank-order tournaments can incentivize effort under specified noise, information and risk assumptions | Provides theory for prize spread and heterogeneous entry. It does not identify optimal Carbon parameters under Sybils, costly exams, copyable models or token volatility. |

External numerical configurations and prize-place counts are sourced **low=base=high**, not benefit forecasts. Repo heads were checked on 2026-10-10: pretraining `2def63f8c860cd51b74398f4101bede799b0010d`, fine-tuning `afd44037e9a116fb1844dea6aaa0718cd23bc248`. No public operational evidence was found here that isolates the causal entry/retention effect of a reward shape from benchmark difficulty, price, registration cost and model release. That gap remains **HUMAN_INPUT / prospective measurement**.

## Published failure cases and what each actually proves

**Validator free-riding, documented by Bittensor.** The [official weight-copying guide](https://guides.learnbittensor.org/learn/weight-copying-in-bittensor) describes copying revealed rows or a stake-weighted consensus estimate to collect dividends without independent evaluation. It also states the limitation of concealment when miner rankings change too slowly: stale weights may remain useful. This is validator **weight** copying, distinct from miner recipe/model copying. No measured prevalence or economic loss is supplied here. Local payout smoothing can extend that stale period (inference); commit-reveal/liquid-alpha effectiveness depends on the deployed branch and dynamics, not a blanket guarantee.

**Multiple-account test-query abuse, documented by ImageNet organizers.** The [2015 organizer announcement](https://www.image-net.org/challenges/LSVRC/announcement-June-2-2015.php) records at least **30 accounts** and at least **200 test-server submissions**, exceeding the then **two-per-week** limit, and a requested **12-month** exclusion. These are historical source facts (counts are lower bounds, with unreported upper bounds). The issue was adaptively selecting similar models and research choices from the test server. This supports artifact/actor-aware query custody and fresh confirmation. It does not demonstrate token Sybil prevalence or prove that winner-take-most caused the incident.

**Carbon's own simulated failures** below are conditional counterexamples, not published incidents of real miner abuse. Keep that distinction in investor/public language. Likewise, do not call a published anti-copy policy proof that copying has been eliminated.

## What Carbon has and has not measured

[#974](https://github.com/carbonphysicsai/Carbon/pull/974) is merged simulation evidence. [#989](https://github.com/carbonphysicsai/Carbon/pull/989) is **closed unmerged**; [#1007](https://github.com/carbonphysicsai/Carbon/pull/1007) is its merged replacement. #989 and #1007 are not two independent studies. Source pins and table selectors are in [SOURCES.md](SOURCES.md) and [options.json](options.json). #974 and #1007 also share a base simulation and noise proxy; different attack experiments are not independent empirical replication.

The [first manifest](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-mechanism-sim/assumptions.v1.json) and [replacement manifest](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-policy-options/assumptions.v1.json) assume synthetic true errors, admissible models, arrival laws, common-case noise, a one-eighth Challenge share and a 40-window horizon. Their public-practice recipe seed-spread proxy is **not measured hidden-window noise**. They approximate the registered comparison with a Gaussian/normal-interval surrogate and stop at targets. Neither includes miner effort/entry, stake-weighted consensus, publisher failures, actual Alpha receipts or price. This research reruns neither.

The following are read directly from committed CSV rows: the registered-slice relative margin **0.056993107446249414**, decay factor **0.5** and **three** paired evidence windows. Those are source facts about the simulated slice; they are not new settings. **Low/base/high below means MC interval lower / estimate / upper, conditional on the fixed assumptions**, not a forecast uncertainty range for mainnet.

| Merged source / scenario | P(best model has final positive target): low / base / high, MC 95% | Attacker fraction of paid target: point estimate | Lesson |
| --- | --- | --- | --- |
| #974, one-key weaker actor | 0.701 / 0.817 / 0.894 | 0.166 | One actor already competes for a noisy screening opportunity |
| #974, four keys, same weaker quality | 0.490 / 0.617 / 0.729 | 0.347 | More screening opportunities can install a model that blocks a later smaller true improvement under the margin |
| #1007, exact four, per-hotkey screens | 0.579 / 0.688 / 0.778 | 0.282 | Exact clones gain from repeated opportunities |
| #1007, exact four, digest-first screens | 0.815 / 0.900 / 0.948 | 0.090 | Deduplicating **before screening** removes the extra exact-clone opportunity in this model |
| #1007, near four, exact-digest only | 0.541 / 0.650 / 0.745 | 0.317 | Exact hashes do not identify distinct near-copy artifacts |
| #1007, near four, tight assumed cluster | 0.672 / 0.775 / 0.853 | 0.204 | Hypothetical near clustering still leaves gain |
| #1007, near four, over-wide assumed cluster | 0 / 0 / 0.046 | 0.904 | Zero measured Sybil gain can result from blocking the actual best model |

Point attacker estimates have **SOURCE_POINT low=base=high** for faithful transcription; that is not a statistical confidence bound. Their underlying model uncertainty is unquantified. #974 uses **60** Monte Carlo episodes per row, #1007 **80**. Their intervals measure only episode sampling under the assumed world, not real-world science or economics.

The #1007 exact-four per-hotkey extra attacker share versus its one-key control is MC low/base/high **0.113 / 0.192 / 0.271**. Exact-digest policies reduce that extra share to **0 / 0 / 0** in this slice. For near-four with digest-first, the extra share is **0.147 / 0.238 / 0.328**; tight assumed clustering gives **0.057 / 0.124 / 0.192**. These conditional gains do not identify any safe production similarity threshold. Prior similarity remains forbidden as an official scientific score input; a separately adopted admission/attribution treatment needs its own false-merge evidence and owner/security/legal review.

For copied-best attribution in the same slice, equal splitting gives the copier **0.452** of paid target even when the honest submission was first. First-claimant attribution gives **0** when honest was first and **0.905** when copier was first. These are source points, low=base=high, not confidence ranges. Model-level best-target probability alone hides entitlement going to the wrong actor. Authenticated commit order, byte identity and IP authority are different things; independent identical rebuilds also need an owner rule.

The [#1007 README](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/incentive-policy-options/README.md) reports exact-digest-first paid budget fractions **0.788 / 0.894 / 1.000** under decay factors **0.5 / 0.75 / 1.0** at the registered slice. This is a **three-scenario sensitivity**, not a probability interval. In this experiment decay changes amount while the promotion probability remains the same. That is not evidence of improved long-run entry or discovery under a slower decay.

Mapping the existing experiments to the options:

| Option | Supported question from existing sims | Missing decisive evidence |
| --- | --- | --- |
| Winner-take-most | Screen chance, margin lock-in, actor timing and one-incumbent target | Score-to-real-decision alignment; genuine entry/effort; reference/gate uncertainty in the promotion model |
| Top-k | Exact-clone and attribution failures warn what a slate must avoid | No top-k simulation or empirical entry result; independent useful runners-up; slate cost and consensus effects |
| Smoothing | Current target variation supplies a comparison endpoint | No Carbon EMA/softmax experiment; stale-tail cost; payout withdrawal after disqualification; multi-validator delay |
| Decay | Current and hypothetical reward factors' target amount/burn/variation | Best decay under actual improvement cadence, construction cost, registration cost, miner entry and receipts |

## Validator agreement changes every local option

Under the [Yuma equations](https://www.bittensor.com/docs/internals/consensus), miner weights above stake-supported consensus are clipped before reward calculation; validator trust measures retained weight, and bonds affect dividends. Agreement about an incumbent can therefore affect realized rewards even when each validator publishes a concentrated target. It does not certify the incumbent's physical decision quality. Common source versions and a finalized promotion receipt are operational alignment evidence; scientifically independent reference evidence remains separate.

As an **illustrative assumption**, hold kappa at 0.5 and vary active-stake support for a new winner low/base/high **0.4 / 0.5 / 0.6**. If all remaining validators assign it zero, minority support below kappa can clip its positive column to zero in the idealized median equation. Thus an independently correct early validator's local winner target need not reach that miner as intended. This is algebraic sensitivity, not a chain experiment or a recommendation for kappa. Stale incumbent consensus, active-stake skew, asynchronous evidence and a copier matching the consensus must be measured in any option's evaluation.

The [current liquid-alpha documentation](https://www.bittensor.com/docs/hyperparameters/liquid-alpha-enabled) makes the branch dependence explicit: Yuma3 bond processing and liquid-alpha enablement are separate, and the classic branch does not use that toggle. The code source pin is Subtensor main `5c6e83e2f4936f257234f246957f75684c35227c`; checked public code distinguishes Yuma and Null, and Yuma3 versus classic bonds. Actual deployed runtime/flags/consensus source remain unobserved here. Local target smoothing, historical bond smoothing, age-dependent incumbent epsilon and Carbon's reward halving must never share a mislabeled “decay” parameter.

Current [Null-consensus documentation](https://www.bittensor.com/docs/guides/null-consensus) describes an owner-selected alternative with one elected highest-stake validator and different reward/bond behavior. This note **does not recommend switching** or assume Carbon uses it. It is another reason to record the actual epoch mode before translating simulated targets into predicted receipts. No configuration or owner-only score feed was accessed.

## Owner options and the evidence each needs

| Review package | Why an owner might choose it | Smallest missing evidence/decision |
| --- | --- | --- |
| **A — established incumbent, explicit artifact attribution, declared decay** | Focus on one trusted advance and minimize slate complexity | Adopt an exact-artifact query treatment and claimant policy; prove meaningful score-to-value ordering; establish actual targets versus receipts and no clock-reset abuse |
| **B — qualified top-k slate, one total budget per independent artifact/group** | Reward useful alternatives and make a credible runner-up path | Define what makes a runner-up independently useful/admissible; measure marginal product value, extra evidence cost, clone occupation and newcomer effort response |
| **C — winner or slate with bounded smoothing** | Prioritize payment continuity during genuine model changes | Define stale-tail budget and immediate hard-failure withdrawal; measure newcomer delay and target/consensus/dividend lag jointly |
| **D — alternative age/burn/reset schedule** | Prioritize improvement pressure or longer builder payback | Specify who can reset, under what independent improvement evidence; measure plateau usefulness, construction cost, time-to-advance and waiting/identity strategy |

These are options, not a ranked economic optimum. A can be the nearest bounded comparison control because it resembles the source-pinned route; that is an implementation-distance observation, not proof of maximum value. A top-k or smoothed alternative should beat that control on the owner's declared objectives under equal total budgets.

Recommend an evidence sequence without new runs in this PR: verify the score's decision value; separate exact-duplicate query opportunity from claimant attribution; evaluate all options under the same qualified promotion receipts and total budget; then compare local targets with observed network/settlement evidence through the authorized canary/operator. The owner-only AX42 score-feed task stays outside research; no agent action is requested there.

## Parameters and outcome ledger for the optimizer/canary

This specifies what a later authorized study should record, not another simulation to run here.

| Parameter group | Existing source basis | Proposed sensitivity/unknown |
| --- | --- | --- |
| Scientific comparison | Exact Challenge/rule/contract digests; paired fresh comparison; #974's historical margin/noise surrogate | Admissibility, reference uncertainty and real decision value must come from the registered judge, never economics |
| Recipient allocation | Current single incumbent | k, shares, ties, unfilled slots, total per-artifact/actor budget: **HUMAN_INPUT** |
| Smoothing | No Carbon result in #974/#1007 | Type, retained-history lambda, half-life, unsafe-tail withdrawal: **HUMAN_INPUT**; match conventions before comparing with external ALPHA |
| Reward age | Pinned testnet full day/daily halving | Start, reset, self-improvement, floor and burn destination: **HUMAN_INPUT** |
| Admission/identity | Sims' one versus four keys; exact/near synthetic groups | Exact digest authority, same-party linkage, query budget, independent identical submissions and appeals: **HUMAN_INPUT** |
| Network | Source branches and target arithmetic only | Deployed runtime/epoch mode, active stakes, clipping, commit-reveal, liquid alpha, bond age, publisher lag/outage and rounded receipts: record through authorized operator |
| Entry/effort | Not simulated or publicly measured for Carbon | Construction/evaluation costs, affordable participation, abandonment and genuine innovation rates: **HUMAN_INPUT** with future source/receipt |

Report real decision regret of the model that holds the target; hard-failure placement; genuine challenger promotion latency/censoring; extra duplicate query advantage; target concentration at artifact and actor level; attribution correctness; newcomer retention/effort; burned and paid budget; target variation; multi-validator agreement; final receipts and reconciliation failures. “Known best” and wrong dethrone require independently known quality, otherwise **NOT_IDENTIFIABLE**. Entry measures require observed actors/effort, not counts of new hotkeys.

Every new economic setting and acceptance bar stays **HUMAN_INPUT**. No mainnet token price, yield, miner-income estimate or Carbon traction claim is made. Maturity is **RESEARCH_OPTIONS_SPECIFIED**, not empirically selected economics, network qualification or deployment readiness. Hub impact NONE: research-only; no runtime/maturity change and the retired Hub is not regenerated.
