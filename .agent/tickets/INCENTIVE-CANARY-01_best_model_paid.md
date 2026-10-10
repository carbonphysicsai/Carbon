# INCENTIVE-CANARY-01: a continuous testnet check that the best model is paid

**Asked:** the owner, via the Test Lead (2026-10-09): "we just need a test to
make sure the best model is getting paid". **Executor:** Carbon Validator.

**Scope:**
- testnet 567 only;
- DEVELOPMENT evidence;
- it signs nothing, sets no weight, and changes no policy value.

The policy values (margin, decay, split) are the existing registered
development values. Any change to them is HUMAN_INPUT.

## 1. How testnet weight-setting works today (main `b58bc2d54`)

1. **Score.** valV2's battery validator scores each admitted submission on
   the live hidden windows under its rule (v2-bank). A miner sees only the
   allow-listed outcome.
2. **Nomination.** `exam.nominate` nominates a screened submission when:
   - it is eligible;
   - it is better than the incumbent's score on the same pool version and
     the same rebuild device class, by the rule's margin;
   - it has no important-region regression beyond that margin.
3. **Promotion (the frontier step today).** The daemon runs a nominee's final
   on a fresh, consumed set.
   - A decided `IMPROVEMENT`, beyond the rule's equivalence margin of about
     5.7% relative, makes it the incumbent (an `incumbent` event).
   - While the policy has no public baseline (now), the first eligible
     submission is the incumbent (`FIRST_INCUMBENT`).
4. **Winner** (`rewards.winner_eligibility`):
   - `battery_promotion` reads the incumbent and its promotion.
   - `WinnerLedger.decide` records it once, at the finalized time it is first
     seen.
   - A promotion is eligible only if its kind is `FINAL_IMPROVEMENT` or
     `FIRST_INCUMBENT` and it is not on an overdue pool version.
   - A same-miner promotion keeps the old clock (`self_improvement_factor` is
     null).
5. **Targets** (`rewards.winner_decay`, policy `testnet-winner-v1`):
   - 1/N per Challenge, with N = 3 (battery, cold plate, motor);
   - the winner gets the full share for 24 hours from promotion, then half
     every 24 hours;
   - everything unpaid burns to UID 0. That covers decay, Challenges with no
     winner, and remainders.
6. **Publication** (`rewards.testnet_winner_publication`): at most once per
   360-block epoch, under the standing authorization
   (OWNER-TESTNET-WEIGHTS-01).
   - A winner absent from the snapshot is paid nothing.
   - A registered canary (OWNER-CANARY-LIST-01) is never weighted; its share
     burns.
   - An owner **hotkey** is refused.
   - An owner-**coldkey** winner is paid on testnet, so Carbon's own miners
     exercise winning.

## 2. Against AGENTS.md §14's target

Target: score → contender nomination → frontier promotion →
`FrontierAdvanceEvent` → `SettlementObligation` → treasury settlement.

| Target step | Today | Gap |
|---|---|---|
| ScoreResult | the validator's score record | none |
| Contender nomination | `exam.nominate` (rule margin) | none |
| Frontier promotion | the validator's own final, `IMPROVEMENT` beyond ~5.7% | no separate registered frontier evidence policy; promotion is the single validator's decision |
| `FrontierAdvanceEvent` | the `incumbent` event plus the `WinnerLedger` record | not a first-class, versioned event type |
| `SettlementObligation` | none: targets go straight to weights | no obligation object; settlement is direct winner plus burn (OWNER-C0-REWARD-01) |
| Treasury settlement | none (burn to UID 0) | treasury is optional, by owner decision |

**Other gaps** that matter for "best is paid":
- one serving validator (valV2), so there is no multi-validator agreement;
- the first-incumbent rule while no baseline is set;
- the same-miner factor is unmeasured;
- the score is Challenge-bound, so the comparison is per Challenge only.

## 3. The check

It extends the canary runner (#901) with its `weights` stage, S2, which is
NOT_BUILT today. It also adds a role-scripted mode that drives several of our
test hotkeys through the real Launchpad path, with recipes of controlled
relative quality:

| Role | Recipe | Expected |
|---|---|---|
| `strong` | the library's best known battery recipe | becomes incumbent and is paid |
| `degraded` | the same recipe at a much smaller budget (fewer steps or width) | never nominated over `strong` |
| `noise` | `strong` with a seed-level change only | never promoted (inside the equivalence margin) |
| `challenger` (later) | a recipe expected to beat `strong` by more than the margin | after its final, takes over; its clock starts |

"Expected to beat" is a hypothesis until a calibration run measures it. The
check then verifies, from **public surfaces only** (no hidden material, no
AX42 access):

1. **Who is paid:** valV2's on-chain weight row each epoch. Battery's share
   goes to the incumbent hotkey the score feed reports (VALIDATOR-29,
   `leaderboard.incumbent`), and to nobody else.
2. **The amount:** that share equals `winner_decay.epoch_targets` for the
   incumbent's promotion time, within one integer unit (full for 24 hours,
   then halving).
3. **Ordering:** `degraded` and `noise` never become incumbent while
   `strong` holds. `challenger` becomes incumbent only after a decided final.
4. **The canary list:** no hotkey on `canary.CANARY_HOTKEYS` ever has
   weight.
5. **Burn:** UID 0 receives the remainder.

A mismatch writes a `BLOCKER` line to the journal and pings, the same way
the canary does. A check that cannot read a surface is `UNVERIFIED`, never a
pass.

## 4. Decision needed before the build: which hotkeys play the roles

- **Canary hotkeys don't work:** they are never weighted by design, so they
  cannot show "paid".
- **The roles need registered test hotkeys** that are not on the canary list
  and are not owner hotkeys. Owner coldkeys are fine, because testnet pays
  them.
- **minerD–G (UIDs 8–11) are on stage A,** and minerC is on the ladder. One
  hotkey, one deployment.
- **Proposal:** three new rehearsal hotkeys (strong, degraded or noise,
  challenger) registered by the owner. Or the Test Lead assigns three of
  D–G once stage A frees them.

Until then the S2 stage verifies (1), (4) and (5) passively, for whoever the
incumbent is. That alone checks "the incumbent is paid, and only it".

## 5. Slices

1. **S2 passive** (no new hotkeys): read valV2's weights, the score feed's
   incumbent and the policy, then verify (1), (2), (4) and (5) each epoch.
2. **Roles:** the role-scripted miners and the ordering checks in (3), once
   the hotkeys are assigned.
3. **Challenger:** the takeover after a measured, calibrated challenger.

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT) at most. It is not a security or
economic qualification of the weight path.
