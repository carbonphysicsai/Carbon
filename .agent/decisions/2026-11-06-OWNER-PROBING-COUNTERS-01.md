# OWNER-PROBING-COUNTERS-01: identical recipes graded once; the submission allowance counts per funder

Date: 2026-11-06 (CST, about 12:5x)
Status: DECIDED by the owner, directly in the Lead session (AskUserQuestion, multi-select).

Context: the Chain auditor's probing watch (reports/PROBING_WATCH_20261106.md) found one operator, with many hotkeys funded from one wallet, submitting many settings of a public catalog recipe against a hidden pack. Identical recipes came from several hotkeys, which beats the per-hotkey limit. The Carbon Validator's read: this is selection on the test set, and it breaks no rule today.

Owner's selections (verbatim options):
- "(b) Identical recipe graded once (Recommended)"
- "(a) Limit per funder (Recommended)"
Not selected: "(c) Rotate RB hidden cases sooner" and "Watch only for now".

## Decided (testnet and mainnet)
- (b) A submission whose recipe is identical to one already graded on the same Challenge version, from any account, is not graded again.
- (a) The submission allowance is shared by all hotkeys funded from the same funding wallet.
- Neither applies retroactively. Existing crowns and grades stand, and the overfit check on the current crowns runs separately.

## Not decided here
- The exact identity rule for "identical", and how a funder is determined (Carbon Validator / Chain auditor propose; Validator-2 rules door side).
- The allowance numbers stay as registered.
