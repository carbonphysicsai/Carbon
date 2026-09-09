# C0 development score rewards

Owner direction: OWNER-C0-REWARD-01. Implementation: C-REWARD-D1. This contract is
DEVELOPMENT only. Carbon owns accepted scientific records and reward policy;
Bittensor owns consensus and settlement. No live parameters are inferred here.

Register each immutable challenge context with its own resolved accepted baseline,
S0 < U, allocation schedule, opening, admission cutoff and funding end. Registration
publishes the actual registered ScorePack coefficients through A6 before opening.
The local fixture adapter requires the existing NET-3/A7/A8/A6 accepted record;
neither a commitment nor a caller-supplied accepted Boolean earns credit.

Opening credit is zero. After the existing exact scientific comparison admits a
strict improvement, add `(new_record - previous_record)/(U - S0)`. Each contribution
decays with a 24-hour half-life from immutable finalized-chain activation. The
current holder gets the whole current earned target, including after a takeover;
self-improvement adds credit, and previous holders retain no winner share. Ties
retain the incumbent. A closed batch selects its best accepted record once, with
authenticated original receipt order resolving equal new winners.

Scientific binary64 `float.hex` values remain in private provenance. Reward
arithmetic uses their canonical shortest round-trip decimal representation with
Decimal precision 80. It floors the earned fraction to Q12, then floors allocation
times that fraction. Every remainder is unearned. Checkpoints retain unrounded
absolute gain and its age; queries never mutate it. With S0=.8, U=1, score=.99,
the fractions are .95 initially, .475 after one day and .007421875 after seven.

The ledger keeps at most 64 simultaneous registered contexts, 1,024 allocation
steps per context and 256 candidates per admitted batch. These are tested
development limits, not production SLOs. It shares NET-2's SQLite journal and
NET-3's artifact identity. Registration excludes already submitted artifacts from
fresh opening credit. Opening a batch freezes all available new commitments and
their original receipts before admission. A pending competitor prevents closure;
late commitment processing cannot rewrite a sealed cutoff. Exact replay returns
the original result; conflicting replay fails. Indexed immutable provenance plus
one gain checkpoint per context avoids replaying lifetime history on restart.

Activation is the batch's registered finalized-chain time before admission,
including when evaluation finishes later. Processing admitted pending work remains
owed after the cutoff or funding end, but targets cease at the published funding
end. These are published finite funding terms, not escrow or guaranteed receipts.
An interrupted A7 process-local execution remains indeterminate under NET-3's
recovery boundary; operators must reconcile it, not silently dispatch again.

Challenge accounting stays separate until shared holders aggregate before UID
mapping. Missing, recycled, disqualified or contested holders receive zero new
target. No worse result is promoted. DIRECT_WINNER_PLUS_BURN includes each
challenge's unearned amount and all unallocated capacity. The earned subset is
never normalized to full emissions. NET-4B must verify the runtime's actual sink,
integer vector and constraints; this application ledger is not proof of burning.
Stored chain weights outlive a local process or application expiry. Heartbeat,
readback, stale exposure and settlement observation belong to NET-4B/5/6.

The optional treasury implementation is disabled. C-TREASURY is a separate
unselected follow-up, covering destination health, custody and settled plus
pending/dispatched/committed/unrevealed liabilities. Unknown treasury state sends
new unearned allocations to burn while preserving winner targets and old
liabilities. A global reserve is not an isolated per-challenge purse. No deployment,
deposit cap guarantee, reset, jackpot or cross-challenge spending is authorized.

Weekly reviews are anchored to opening. Each uses the preceding 72 complete
healthy one-hour accounting windows. Strictly below 10% earned/allocated triggers
PLATEAU_REVIEW. Missing, duplicate, unhealthy or zero-denominator coverage is
indeterminate. Redelivery with the same evidence identity is idempotent; a second
logical observation marks the window conflicted. Equal-hour average application
targets are the diagnostic inputs, not chain receipts. Both burn and treasury are
unearned, so route changes cannot alter the ratio. Reports retain participation,
acceptance and operational health evidence. Alerts do not retire, reweight or
declare saturation; tiny gains never reset the schedule. Operators must distinguish
limited score headroom, inadequate participation/funding and operational failure.

A6 owns `carbon/cards/development_scorecard.py`: versioned positive allow-lists,
synthetic maturity, public challenge/miner/result aliases, actual weighted
geometric composition and physics/robustness/accuracy coefficients. After existing
acceptance, combined and aggregate component scores display at three decimals
(half-even), independently of scientific comparison. Release is limited to 256 new
records per opening-anchored hour and 10,000 per challenge context, with durable
disclosure accounting and replay. No hotkeys, seed/case IDs, private references,
per-case outputs, margins, credentials or transcripts are projected. This fixture
release capability cannot authorize real scientific disclosure.

Finite score range and zero opening credit bound the lifetime constant-allocation
target by 1/ln(2), approximately 1.443 days of full allocation. A half-life describes
targets without fresh improvement, not wallet receipts or fiat value. Withholding
can move credit into a higher-allocation period; drip-feeding can extend later
targets. Identity coordination can coordinate that timing but cannot renew copied
artifacts or preserve previous-holder shares. Tests retain these counterexamples.
No strategy-proofness, economic optimality or proven participation is claimed.

Tests: `test_reward_core.py`, `test_reward_ledger.py`, `test_reward_boundary.py`,
plus NET-1/2/3, A7/A8, A6 cards, scoring and leaderboard regressions in the focused
canonical network profile. Canonical integration uses the actual verified fixture
registry and existing evaluation service. Store doubles and analytical vectors are
explicitly synthetic and are not independent science or chain evidence.
