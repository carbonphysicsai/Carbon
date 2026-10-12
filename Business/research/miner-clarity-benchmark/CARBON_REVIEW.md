# Carbon's draft: concrete repairs and source precedence

**Recommendation only.** Read-only owner-supplied public draft:
`codex-queue/inputs/championship/CHAMPIONSHIP_MINER_SUMMARY_DRAFT.md`.
SHA256 **d66919079d51c8124eb92f2558ec685900af2f60fb094106f34ce0612459552a**.
The copy is not committed or edited. Its title is “How a model becomes king (battery, testnet).”

Authority snapshot: **ca71b8ecf500250f57c9dfd731950e1ff5e1f731**. The [championship decision](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-01.md) fixes the planned battery cohort/clock/margin. The [later amendment](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-02.md) controls draw-unit SE, t-quantile and cumulative disclosure. Neither makes the future caller built or mainnet-live. The owner separately instructs retirement of **all scored cases**. The [earlier stats review](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/Business/research/championship-stats-review/README.md) remains historical evidence, not a reason to silently undo the owner's later decisions.

## What works

The draft has a short two-stage story, an exact UTC clock, a clear incumbent/tie outcome, delayed public feedback, version-change protection and a development/testnet label. Preserve those. The title and payment section explain the incentive quickly; the missing part is how a new miner produces a valid entry and interprets its next step.

## Wording and navigation changes

| Draft wording / gap | Why it matters | Proposed repair / authority |
| --- | --- | --- |
| “qualified” | Screening eligibility can be mistaken for scientific qualification | Human wording **eligible for the championship**. Preserve runtime/API enums unless separately authorized; [framework](../deliverable-framework/FRAMEWORK.md) distinguishes model qualification |
| “safety checks” | Reference-relative false-feasible/important-region checks do not establish physical safety | **Model feasibility checks against the reference**; link exact gate/measurement version and known limitations |
| “rebuilds exactly” | Bit-exactness and registered bounded reproducibility are different claims | **Rebuilds from the frozen recipe under the posted reproducibility rules**; actual supported identity/tolerance controls |
| fixed **3.09 × SE** | The later owner amendment uses the declared draw unit, paired block means and a t-quantile | Explain measured paired uncertainty in plain wording; technical rule **t(1−0.01/K; B−1) × sd(block means)/sqrt(B)**. Battery single-case units after duplicate-pair collapse; a retained q leg is question-based |
| “so a lucky draw can't crown you” | A nonzero risk target cannot guarantee zero false crown | State the **1% per-round false-takeover target** and assumptions; do not label target as a certified empirical rate |
| “next target: beat … 2.25%” | The independent noise bar can be larger | Show the fixed margin **and** the current comparison's measured noise threshold, with uncertainty/pending status when unavailable |
| No score direction/unit on the card | Screening A-Q and accuracy-final loss are different measurements | Display both definitions/version and whether higher/lower is better. [Finals decision](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/.agent/decisions/2026-10-11-OWNER-BATTERY-V3-FINALS-01.md) separates them; an unmeasured composite round remains unposted |
| “your recipe is never published” | Public leaderboard privacy and submitted-work use/license are separate | “The public leaderboard does not publish your recipe; authorized use/access follows the submitted-work terms.” [Terms draft](../ip-license-options/MINER_TERMS_DRAFT.md) is not operative. Owner/counsel approve actual promise |
| “no penalty” for miner-side infra | Missing a round still costs an opportunity; attribution/retry policy must be precise | State typed outcome, reason and retry path. Scientific failure, reference failure and infrastructure failure remain distinct |
| Payment lacks decay/value/version link | “King earns” does not specify the amount or active network | Link current reward share, decay and testnet payment status; **HUMAN_INPUT**. No invented earnings/ROI |
| Entry path absent | Understanding the contest is not successfully entering it | Front link **Start → Practice → Submit → My status**, minimal recipe, hardware/cost card and public preflight; current intake availability, not a promised live championship |
| Screening rank delayed **about 18 hours** | Entrant freeze may need scores not yet public | Show own latest evaluated status and cutoff eligibility, while respecting release policy. Specify pending-at-cutoff and tie/commit interpretation from the caller; **HUMAN_INPUT** until binding |
| Private/public field promise too narrow | Future allowed aggregates may exceed three fields; arbitrary internals must remain private | Generate from approved projection, not “everything useful”; no seeds, case IDs, reverse identifiers, protected rows or reconstruction-sensitive traces |

## What the target means

Under the posted accuracy-final interpretation, define loss reduction
**g = (mean incumbent error − mean contender error) / mean incumbent error**.
Compare the paired contrast in the **registered units**, not an unpaired ranking difference. A nonpositive/undefined incumbent denominator requires the caller's explicit policy; no guessed target.

The design requires **g > 2.25%** and a positive-improvement uncertainty test. After expressing the latter in the same relative units, a readable target is **more than max(posted margin, comparison-specific noise threshold)**. This is explanatory algebra, not a new test of “the improvement exceeds 2.25% with confidence”; that would change the null. Gates remain separate and precede ranking.

**ASSUMPTION examples**, not Carbon results: a relative SE of **0.5%** with an illustrative multiplier **3.09** gives a noise threshold **1.545%**, so the fixed **2.25%** binds; SE **1.0%** gives **3.09%**, so noise binds. Equal low/base/high triplets retain each hypothetical point. Actual t multiplier, effective draw count, weighting and score-proof rule come from the deployed contract; no winner is inferred from these examples.

## Daily and monthly risk wording

Keep the owner's daily target and monthly disclosure. The approved [amendment](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-02.md) explicitly says about **7% per week** and **26% over 30 all-null rounds**, with the stated bound/interpretation. Arithmetic:
**1−0.99^7 = 6.7935%**, **1−0.99^30 = 26.0300%**.

Those cumulative bounds require the relevant **conditional per-round error guarantee** (or appropriate independence) across the histories used. If only marginal daily bounds were established, the dependence-safe union bounds are **7%** and **30%**. A resettable daily target is not a lifetime 1% guarantee. Normal/t approximation and empirical SE alone do not prove validity for every distribution. This is a claim-discipline condition, **not a proposal to change the owner's chosen allowance**; proof/stress evidence belongs in the technical rule record.

Use wording “targets … under the registered draw/test assumptions; over 30 all-null rounds the stated cumulative bound is about 26%.” Link to the actual sizing/stress record when public, **HUMAN_INPUT** for that link. Do not say no lucky takeover is possible, extrapolate the all-null illustration to every adaptive scenario without proof, or hide accumulated risk.

## Minimal public information architecture

| Surface | Content | Current reusable source / remaining work |
| --- | --- | --- |
| **Start** | One sentence task; availability/network; prerequisites/hardware/cost; first public example; expected next receipt | [Research MCP](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/carbon/miner_mcp/README.md) and Control Center routes already documented; exact deployed intake/version/URL **HUMAN_INPUT** |
| **Rules & target** | Current score/gates, units/direction, round clock/cutoff, fixed margin plus noise bar, ties, failure policy, reward schedule, terms | Owner decisions and registered public rule projection; generate repeated values rather than copy them |
| **Practice & submit** | Public research kit, smallest valid frozen recipe, environment preflight, artifact/commit confirmation and status | MCP documents practice/freeze/commit/development submit; registration/human signer/intake availability are real gates. Public practice is incomplete and never the exam |
| **My status** | Accepted/rebuild/pending/eligible/cutoff/entered/fail/infra outcome, public-safe reason and next action; own versus public release time | Proposed human labels **not API enum changes**. Show available evidence and missing legs rather than promise an instantaneous scientific result |
| **Results & help** | Rounded public standings, active king, next clock/target, rule digest/version, status freshness, FAQ, change log and support route | Approved allow-list and release policy; no case traces/seeds/diagnostic predictions beyond that policy |

A single approved machine-readable rule card can feed the human page, leaderboard and agent client. Its proposed fields: Challenge/version, environment/status, intended miner artifact, score definitions/directions, gate references, schedule/cutoff, cohort rule, margin/statistical-rule reference, release policy, public target availability, reward/terms links, practice/setup/intake links, and effective version/date. This is a **recommendation**, not an implemented endpoint or permission to widen disclosure.

## Publication gaps and owner/Validator decisions

- Current deployed championship caller, operational start/version and exact entry/leaderboard/status URLs.
- Final score-proof pick, whether a q leg remains and its measured paired noise; keep that round type unposted until registered.
- Actual gate/important-region definitions and typed failure/retry policy presented from the caller.
- Eligibility snapshot at cutoff with delayed screening, exact-duplicate/tie priority interpretation, reward/decay and payment network.
- Operative submitted-work terms and the approved public/private diagnostic projection.
- Public statistical adequacy/stress record supporting the conditional error claim.

The proposed one-pager is ready for wording review with these explicit gaps. It does not activate the championship, promise profit, alter launch readiness or certify a physics model.
