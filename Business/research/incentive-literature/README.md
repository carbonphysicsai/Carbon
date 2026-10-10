# INCENTIVE-LITERATURE-01 — owner brief

**RESEARCH / RECOMMENDATION ONLY.** Read against Carbon main `93875b7dc68bed83562db199427a1cb91d7639a4`, Constitution C0 override and Business Canon. No policy changes, simulations, solver runs, spend, chain transactions or protected data. This is a companion to optimizer's incentive simulation and [Validator #971](https://github.com/carbonphysicsai/Carbon/pull/971), frozen at `40267571912a6bb7cd3c0f6c80c4e3f89e907406`.

**The key distinction is nomination → promotion → published weights → consensus incentive → realized emissions.** A correct Carbon weight row establishes only one link. Yuma rewards stake-supported weights; it does not independently discover scientific truth. With a single serving validator, agreement cannot supply independent corroboration of its evaluation.

Two public winner-focused examples, Macrocosmos Pretraining and Finetuning, give older submissions an age-dependent comparison advantage. Finetuning additionally smooths winner weights. Those mechanisms protect early discovery but can delay better challengers. Their public code demonstrates mechanism design, not successful anti-copy or profitable mining outcomes. Validator weight copying is a documented failure mode in Opentensor's working paper; copying a miner model is a different problem. Hash binding checks identity and integrity, not originality.

Recommend the simulation compare scientific quality, admission, promotion, pay lag, incumbent survival and challenger return separately, including static-quality, rapid-improvement, copier, sybil, absent-validator and UID-reuse scenarios. Parameter values are either the existing development policy or explicit exploratory assumptions in [RESEARCH.md](RESEARCH.md); none is a proposed live setting.

Recommend #971 retain its passive weight check and add a separately labelled, read-only epoch-emission receipt when authorized: finalized block, runtime/spec version, active validators/stake, policy and incumbent-feed identities, weights, incentive, dividends, recipient identities and emission units. An unreadable or incomparable receipt is UNVERIFIED. The existing role rehearsal still needs its own owner authorization and calibration.

Current protocol documentation mixes legacy mathematics with newer branches. This report pins code and records that **the deployed runtime and subnet parameters were not sampled**. Mainnet defaults and historical paper parameters must not be imported into Carbon testnet by analogy.

Delivery scope: these two new documents only. Hub impact: no runtime, stage status, dependencies, authority or primary hub links change; the hub is retired under the current delivery protocol. Research is SPECIFIED, not economically or scientifically qualified. PR Head owns review/merge; economic adoption remains the owner's decision.
