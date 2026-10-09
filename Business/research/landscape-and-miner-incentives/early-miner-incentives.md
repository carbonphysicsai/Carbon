# Early-miner incentives: evidence and recommendations

Research snapshot: 2026-10-09. Economics and incentives are the owner's decision.
This brief compares mechanisms and recorded outcomes; it proposes no payment,
emission allocation, treasury change or network launch. Primary-source IDs and
numeric observations are in [evidence.json](evidence.json).

## What public examples establish

| Example | Mechanism | What worked, failed or remains unverified |
| --- | --- | --- |
| **Masa / CoinList incentivized testnet** | Performance-based data contribution programme, initially announced for July 2024. Announced pool ceiling: **3,000,000 MASA**, sourced low/base/high **HUMAN_INPUT/HUMAN_INPUT/3,000,000**; eligibility slots: **256**, sourced **256/256/256**. The announcement tied distribution to a later mainnet event and left lockup terms to be announced. | Masa later reported filling capacity in the first week and **over 750** competing miner entries: sourced lower bound **750/HUMAN_INPUT/HUMAN_INPUT**, strictly greater than the lower endpoint. This supports reported recruitment, not unique skilled people, retention, verified payouts or causal attribution to reward size. The launch report describes a longer testnet than the initial announcement; do not assume the initial schedule was final. [M01: programme operator](https://blog.coinlist.co/announcing-the-masa-bittensor-incentivized-testnet-rjlsb/), [M02: Masa-issued launch report](https://chainwire.org/2024/08/27/masa-launches-bittensor-subnet-mainnet-with-genesis-institutional-validator-partners/). |
| **Enigma** | Open research challenges, public workbench, reproducible submitted solutions and prize pools funded through its treasury/emission design, with validator payout governance. Its inaugural challenge was a treasury-wallet security bounty. | The project reports RSA and quantum challenge solutions, published methods that later winners reused, and a community-reported environment flaw being patched. These are reported useful outputs. The wallet bounty closed unclaimed: absence of a winning attack does not qualify security. Payout accounting, participant retention and independent outcome audit were not verified here. [M03: official mechanism and results](https://github.com/qbittensor-labs/enigma). |
| **Gittensor** | Current OSS contribution rewards and registered-miner issue discovery; discovered issues earn credit after related contributions are merged. Repository eligibility, review, credibility and spam controls gate rewards. | This demonstrates a documented engineering-contribution mechanism, not a verified prelaunch recruitment result or a cash vulnerability-payout history. Independent miner retention and revenue outcomes are unavailable. Code-volume scoring does not establish scientific merit. [M04: issue discovery](https://docs.gittensor.io/issue-discovery.html), [M05: contribution rules](https://docs.gittensor.io/oss-contributions.html). |
| **Gauntlet / Templar** | Continuous rewards for useful distributed-training contributions; reliability filtering precedes validation-loss contribution scoring and duplicate-work controls. | The authors report a permissionless training run and token payments based on contribution value. That is research evidence for a functioning contribution mechanism, not proof that a launch bonus recruited or retained superior miners. This task's gradients and loss do not directly define Carbon's scientific grade. [M06: primary paper](https://arxiv.org/abs/2505.21684v1). |
| **Earlier SN9 and proposed IOTA** | Earlier independent full-model training used winner-takes-all incentives. IOTA proposes cooperative training and marginal-contribution credit. | Macrocosmos authors report model hoarding under the earlier rewards and a whole-model hardware barrier. The cited IOTA work explicitly calls its replacement results preliminary. Treat this as a reported design failure and an unconfirmed remedy, not a measured retention effect or proof Carbon should change its reward law. [M07: primary paper](https://arxiv.org/html/2507.17766v1). |
| **Foundation subnet-template testnet (archived)** | Historical public test-network onboarding lets participants exercise miner/validator integration with test currency. The repository is now archived. | The instructions distinguish testnet from real TAO emissions. A testnet is a development route, not an income promise; participation may still require user-funded hardware. This documentation supplies no recruitment or retention outcome and is not a current command guide. [M08: archived official template instructions](https://github.com/RaoFoundation/bittensor-subnet-template/blob/main/docs/running_on_testnet.md). |

The pool ceiling and censored entry count intentionally have unknown endpoints.
An announced token pool is not money paid, a currency conversion, or a return
forecast. No example establishes a general optimum reward size. Current
programmes above are not all prelaunch programmes: their stage is explicit.

## Recommendations for Carbon

**Make entry concrete.** For a technically strong prospective miner, including
someone like ultraligie, provide the public construction kit, reproducible
examples, baseline results, input/output contracts, compute requirements,
known gaps and the rules for acceptance. Do not infer that person's hardware,
motivation or required income. Public reference access and participant-owned
practice seeds must preserve protected official evaluation. An unresolved
feasibility problem cannot be fixed by paying miners more.

**Consider bounded engineering bounties separately from research rewards.**
Owner-approved, reproducible public-kit bug reports, integration fixes and
documentation repairs could improve entry quality before a scientific contest
is ready. Define scope, duplicate handling, acceptance authority, fixed payment
terms and release rights before announcing them. A merged patch or a reported
bug earns only the relevant engineering credit; it does not create physical
qualification, a leaderboard grade or an emission entitlement. This is an
inference from Gittensor's gates and Enigma's shared outputs, not an adopted policy.

**Require an adequate exam before paying for official scientific superiority.**
A research contest needs feasible and contested questions, credible reference
outputs, registered measurements, independent reconstruction and cheap
baseline comparison. Publish realistic entry costs and a payment timetable.
Separate candidate failure from reference or infrastructure failure. Keep public
learning useful while preserving independent official evidence.

**Prefer clear terms over speculative early-emission promises.** Masa's
announcement shows how deferred distribution and unsettled lockups can leave
participants unable to assess compensation. Its recruitment report does not
prove those terms failed. The SN9 paper supplies a different warning about
hoarding and entry barriers, not a universal argument against winner rewards.
Carbon's current owner-directed route is `DIRECT_WINNER_PLUS_BURN`;
treasury is optional, and this research does not replace that route. Confirm
all terms against the
[current launch authority](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.7.md)
before proposing an executable programme.

**Measure useful participation.** Record independent entrants, time to an
admissible submission, reproducible accepted improvements, participant cost,
continued contribution after rewards, and buyer decision benefit. Distinguish
hotkeys from people and registrations from accepted contributions. Also record
published allocation, accepted claims and actual payout receipts separately.
The examples do not supply comparable causal recruitment or retention data.

## Owner decision record, deliberately unfilled

| Decision or quantity | Proposed status / low–base–high |
| --- | --- |
| Programme adoption, reward type, currency and source of funds | `HUMAN_INPUT`; no adoption |
| Total budget, per-award budget, duration and eligibility targets | `HUMAN_INPUT`; each **null/null/null** |
| Expected qualified entrants, retained miners, useful outputs and payout delay | `HUMAN_INPUT`; each **null/null/null** |
| IP/release terms, engineering acceptance owner and public disclosure rules | `HUMAN_INPUT` |
| Scientific qualification and live network authorization | Separate owner decisions; no authority earned by this brief |

A fixed engineering programme, a research prize and a network emission stream
create different obligations. Any eventual proposal must include its own
reviewable rules, funding and acceptance evidence.
