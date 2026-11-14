# OWNER-MAINNET-QUALIFIED-STANDING-01: what launches on mainnet is qualified for crown pay

Date: 2026-11-14 (CST, about 06:25)
Status: DECIDED by the owner, typed in the Lead session (the team decision ledger) and posted verbatim by the Lead on
TEAM_BOARD (Sat 14 Nov 06:25 CST, line 10325).

Line typed (verbatim): "Holy shit yes it's qualified anything we launch on mainnet is qualified what an insane safety blocker. ITS ON MAINNET. They get the 25% per challenge"

## Decided
- This is the human qualification (AGENTS.md invariant 5) that `carbon.rewards.winner_eligibility.decide` waits for
  before a sealed-exam crown (incumbent reason `bank_comparison_sealed_testnet`) may be paid off testnet.
- Motor 1.8 (electric-motor-magnetics 1.8) on finney netuid 116 is QUALIFIED for mainnet crown pay now: its king is
  paid its Challenge's 1/4 under the registered decay (full 24 h from the crown, then half every 24 h).
- STANDING: every Challenge version Carbon launches on mainnet is qualified at its launch, each paid its 1/4.

## Implemented by
- Weight policy `mainnet-winner-v3` (`carbon/rewards/weight_policies/`): field `qualified_sealed` names each
  qualified Challenge with this record's sha256 and the exact evaluation pack digest(s) its crowns must come from.
  Motor 1.8 on 116: pack `sha256:ee2348b1738fb13984601473b5624bfefc2f65d8c7c7e91471c2d4c419a5742c` (the 116 door).
- A Challenge launched later (Cooling 1.8, Ribbed Bracket, Burst Thermal), or a re-seal of Motor on a new pack, is
  added by a new policy version naming its pack under this same record (Validator review); it is never paid
  silently.
- Pay runs only under the owner's weights go typed in the Test Lead-C session naming the policy digest.

## Not covered by this record
- No score, threshold, floor or margin value; no change to the exam, the door or its crown rule.
