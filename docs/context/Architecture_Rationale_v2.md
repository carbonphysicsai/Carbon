# Carbon Architecture Rationale v2

**Status:** OWNER-RECOMMENDED integrated rationale for review.  
**Supersedes for current architectural reasoning:** `docs/context/Architecture_Rationale.md`.  
**Does not change runtime by itself.**

## Why Carbon qualifies the exam first
A model can only be judged scientifically if the task, population, truth path, measurements, and finite evidence deserve authority. A deterministic generator or reproducible score is not enough. The Validation Dossier therefore qualifies the exam before the exam qualifies candidates.

## Why envelope and population are different
An envelope says where a claim may apply. It does not say how cases occur inside that scope. Expected performance, tail risk, and subgroup behavior depend on a target population. Carbon therefore separates the operating envelope from `InstanceDistributionContract`.

## Why P, Q, and w are separate
`P(x)` is the target population; `Q(x)` is how finite evidence is sampled; `w(x)` is how evidence contributes to an estimand or score. Stress oversampling should not silently become a claim about real-world frequency or scientific importance.

## Why generators do not own truth
A generator implements a registered population/SamplingPlan. It can be deterministic and still sample the wrong population or produce inaccurate labels. Generator conformance and reference/truth adequacy are separate evidence claims.

## Why truth is Challenge-specific
Some Challenges have analytic or semi-analytic truth, some need mesh-converged numerical solvers, some require experiment, datasets, partner goldens, or multi-code consensus. “Use Julia,” “use CFD,” or “use an independent solver” is not a scientific law. A reference backend earns authority only within its qualified regime.

## Why MeasurementContracts exist
A governing equation does not uniquely determine a numerical metric, discretization, normalization, applicability rule, uncertainty floor, or threshold. Measurement definition, measurement qualification, and score use therefore remain separate authorities.

## Why Score Pack is an Evidence Use Contract
ScoreEngine should not invent science. The Score Pack binds already-qualified evidence to eligibility, mandatory admissibility, explicit estimands, soft transforms, aggregation, and Challenge-bound rank evidence.

## Why admissibility precedes ranking
Some scientific failures are non-compensatory. A physically disqualifying failure cannot be rescued by high average accuracy. `physics > loss` is therefore primarily an admissibility doctrine, not a statement that physics always receives a particular numeric weight.

## Why numerical ordering is not always scientific ordering
Finite evaluation samples and stochastic reconstruction create uncertainty. Small score differences can be noise. Carbon preserves indeterminate/equivalent states where the registered evidence cannot defend a scientific distinction.

## Why leader promotion is a second experiment
A challenger’s score from one hidden draw should not automatically replace an incumbent whose score came from another draw. When variance matters, Carbon compares incumbent and eligible challengers under the same fresh promotion experiment and registered reconstruction policy.

## Why Carbon rewards frontier advance rather than incumbency
Persistent incumbent rent rewards possession of past state of the art. Carbon’s base performance market is intended to buy new verified scientific progress. A new `FrontierAdvanceEvent` creates the performance entitlement; remaining leader does not.

## Why Challenge slots are equal
Different Challenges use different scientific rulers, so raw scores should not be pooled. Equal notional `1/N` opportunity across a frozen Challenge portfolio deliberately buys breadth without pretending equal score scale, difficulty, commercial value, or scientific importance.

## Why unused Challenge opportunity is not redistributed
If difficult Challenges lose their unused slot to easy/high-activity Challenges, search pressure concentrates rather than broadens. Under the base policy, no frontier event means no performance entitlement for that Challenge-period.

## Why a treasury separates Bittensor transport from Carbon economics
Bittensor/Yuma weights are relative and normalized. Carbon’s Challenge accounting is absolute and event-bound. A separately governed treasury neuron/vault can receive miner-side emission and settle exact frontier entitlements without forcing 4–7 Challenge accounting into normalized validator rows.

## Why treasury governance is not science governance
The scientific layer determines whether the frontier moved. Treasury validators verify that a payout proposal corresponds to an already-authoritative `FrontierAdvanceEvent`, correct recipient, and exact entitlement. They do not vote on physics after the fact.

## Why event-bound payouts matter
Binding every transfer to a finalized frontier-event digest reduces operator discretion, prevents duplicate payment, and makes settlement audit a mechanical correspondence problem rather than subjective patronage.

## Why payout failure is not scientific failure
RPC outage, contract bug, governance delay, or timelock state can delay payment without invalidating the scientific event. Carbon therefore records scientific state and settlement state separately.

## Why P0 proves one Challenge before 4–7
One qualified Challenge exposes end-to-end failures cleanly. Once the judge works, Phase-0 expands under the same constitution toward a small portfolio so Carbon can demonstrate breadth rather than overfitting the institution to Burgers.

## Why the old Burgers PoC stays historical
The PoC proved wiring, but later gauntlets found hidden viscosity, under-resolved labels, a truth-vs-generator inversion, and a final-time spatial proxy described too strongly as a PDE residual. Repaired science gets new Challenge identities; historical evidence is not rewritten.

## Why reconstruction variance is method evidence
If Carbon rewards a construction method, one lucky artifact is insufficient. Where reconstruction is stochastic, method quality may require multiple independent builds, admissibility probability, dispersion, or another registered repeat policy.

## Why Landscape cannot aim base emissions dynamically
Landscape is decision support. It may propose new Challenges, future versions, retirements, stress changes, or separate information-value bounties. It does not rewrite the equal base performance opportunity inside a frozen Challenge epoch.

## Why product qualification remains separate
A frontier winner has survived a search exam. A product claim requires exact artifact/system identity, job-shaped evidence, context of use, answerability/escalation, and lifecycle control.

> **Rank nominates. Evidence qualifies.**

## Why documentation authority is explicit
Carbon now has historical PoCs, gauntlets, current runtime specs, and vNext architecture in the same repository. Preserving all of them is valuable only if authority is visible. `DOCUMENTATION_STATUS.md` is therefore part of the engineering control plane, not housekeeping.
