# OPT-18: off-chain scoring source boundary (development audit)

## Working contract

This audit implements the Test Lead's SCORE-PROOF-OFFCHAIN-EVIDENCE-01 request.
It reads repository source only. It does not query a chain, a hidden exam,
an AX42 host, or a scoring database. `Design_Specs/Scoring.md` owns A5's
closed input contract; `CONSTITUTION.md` separates scientific merit from
network settlement. The primary orientation map ref is `WAVE-B/OPT-18`.
The Development Hub is retired under `.agent/DELIVERY_PROTOCOL.md`; this
audit changes no Hub selection, status, authority or navigation meaning.

**Result: PARTIAL PROOF, with an explicit unknown.** The static import guard
proves a narrow source boundary for three pure score kernels. It does not
prove that every validator caller or the weight publisher is incapable of
reading chain state before a score. Transitive source reachability crosses
those layers today. No LIVE/security qualification follows from this audit.

## Score-input inventory and origin

| Scoring entry | Inputs that can change its result | Origin and boundary found |
| --- | --- | --- |
| `carbon.scoring.engine.ScoreEngine.score` | Exact `ScoreInput` pin, numeric gate and component actuals, Boolean gate actuals; exact `LoadedScorePack` thresholds, weights and transforms | Validator-authorized closed scalar input and loaded pinned pack per `Design_Specs/Scoring.md` §§3–4. Its static local-import closure has no chain/reward module or dynamic import. Fixture-only A5; no LIVE origin is proved. |
| `carbon.battery.value.scoring.components`, `decision_agreement`, `rule_scores` | `predictions`, `case_ids`, reference `store`, optional/frozen `contract`, and computed component vector | Its static local-import closure has no chain/reward module or dynamic import. Caller provenance and a real exam remain outside this proof. |
| `carbon.design_search.score_bridge.evaluate_design_score` | `sealed_bank` (question/reference outcomes), `committed_predictions`, `registered_rule` (objective, equivalence, losses, kind costs and aggregate) | The pure library's static local-import closure has no chain/reward module or dynamic import. Bank custody and caller provenance are outside this proof. |
| `carbon.battery.value.score_tuning.score_member` | Candidate rule and each member's scored leg row; related scoring functions consume registered limits and references | **UNPROVED end-to-end.** The module's transitive import closure reaches `carbon.chain` via `false_acceptance → panel → track_a → worker → level1_worker → development_session.battery_gpu → research_campaign → service`. Reachability is not evidence of a chain read, but prevents a blanket no-chain assertion. |
| `carbon.challenge_validator.*_scoring` practice rules | Submitted predictions, public PRACTICE references/material, frozen Challenge rule and comparison inputs | **UNPROVED end-to-end.** Their transitive imports reach `carbon.chain` through development-session modules. Practice is intentionally incomplete and is not the hidden exam. |
| `carbon.scoring.development` | Development rule, metric actuals and scalar score inputs | **UNPROVED transitive import closure:** `development_session.profile → carbon.chain.models`. That is a chain type import, not a demonstrated chain read. |

The score-bearing A5 schema forbids fees, payments, hotkeys, blocks, miner
identity, raw datasets and other unspecified values (`Design_Specs/Scoring.md`
§§4, 10). This is a structural fact about that bounded engine; it is not a
claim that all other score callers have equally closed schemas.

## The downstream direction and the unresolved reverse path

`carbon.rewards.winner_eligibility` reads validator promotion records;
`carbon.rewards.winner_decay` maps an eligible winner under its registered
policy; `carbon.rewards.testnet_winner_publication` issues a typed intent;
`carbon.chain.publisher.VerifiedWeightPublisher` observes the chain and
publishes checked targets. Chain observations affect eligibility and payout
transport. The current source graph also reaches scoring modules from
`testnet_winner_publication` through `carbon.battery.deployment → daemon →
research → development_session.research_service → research_profile →
carbon.scoring.development → engine`. A second path reaches battery value
scoring through challenge-validator imports. These are import paths, not a
verified runtime call from the publisher into a scorer. They make the
strong converse claim **UNPROVED**, rather than clean by assertion.

The producer's on-chain commitment may control **admission** of a recipe;
that is a distinct path from the numeric score input. This audit does not
equate admission influence with a scientific score input or prove that every
deployed caller preserves that distinction.

## Executable evidence and remaining proof

`scripts/dev/score_offchain_audit.py` resolves local imports from named score
roots and reports forbidden reachability, dynamic import calls and shortest
source paths. Traversal includes existing implicit ancestor package
initializers, including `carbon/__init__.py`; namespace packages without an
initializer add no source. Calls through named or aliased
`from importlib import import_module` bindings are conservatively reported as
dynamic and unproved, even if another statement might shadow the binding.
`tests/invariants/test_score_offchain_boundary.py` requires the
three clean kernels to remain chain/reward-free and injects a fake direct
`carbon.chain` import into `ScoreEngine` source as a negative control. The
guard catches that injection. The same test preserves the publisher's
transitive scorer reachability as a visible **unknown**. Additional negative
controls inject a chain import into each of `carbon` and `carbon.scoring`'s
initializers and call direct, aliased and attribute-based dynamic loaders.
These controls do not execute the imported code or access a chain.

Closing the unknown needs a function-level call and data-origin proof at the
validator and publication callers, or a bounded import-boundary refactor,
followed by a runtime negative control in which chain-read callbacks fail if
invoked during scoring. No scientific, chain or security policy value is
chosen here. Until that evidence exists, the owner directive remains a rule
to enforce, not an end-to-end property this PR has proved.
