# KOTH-TAKEOVER-RULE-01: better score wins beyond measured rebuild noise; a self-improving king keeps his clock

Date: 2026-10-19
Status: ADOPTED for development. Payable use still needs an adopted score pack and a registered four-Challenge weight policy, both the owner's.
Authority: the owner delegated this decision to the Test Lead on 2026-10-19:

> keep it simple. better score wins and takes the emission, halves every 24 hours, existing winner beating himself is the one I need you to decide on.

The Test Lead decided it and relayed it to the Carbon Validator, who records and implements it. Unchanged by this record: `CARBON_BUILD_TARGET.md` §4 (1/N, full for 24 h, then halving every 24 h; no fresh-case tournament).

## 1. Who takes the crown

A challenger takes the crown when its score **exceeds the king's score on the same bank key by more than that Challenge's measured rebuild noise**.
- **Within the noise:** a tie, and **the king keeps it**.
- **There is no fixed margin.**
- **Rebuild noise is defined as:** the largest absolute difference in total score between independent fresh rebuilds of one recipe, evaluated on the same bank key. That means at least three rebuilds, on the Challenge's pinned build and judge images. It is registered per Challenge, with the digest of its measurement record.
- **It is measured, never set.** The packs lane measures it, and the Validator reviews it.
- **It's not the same as inference repeat noise** (`paired_repeat`), which reruns one frozen model. Rebuild noise retrains from the recipe, so it also covers build jitter. That's the jitter an exact copy would otherwise win on.
- **Until a Challenge has registered rebuild noise, promotion there is UNAVAILABLE.**

## 2. The king beating himself

If the incumbent's own miner takes the crown with a better model:
- the better model becomes the incumbent, which raises the bar for everyone;
- **the reward clock does not reset**, and halving continues from the original promotion.

"Same miner" is exactly the existing same-miner clock safeguard (`winner_eligibility.decide`: same hotkey, or the same coldkey frozen in the ledger). No new identity rule.

## 3. What stays unchanged

- The 1/N shares, the burn of unpaid allocation and integer remainders, and the eligibility ledger.
- An infrastructure or indeterminate result never wins and never dethrones.
- A contender that isn't scored never wins.
- **Still open:** whether a king that fails a mandatory gate on a new evaluation version is dethroned. Today it's UNAVAILABLE, and nothing changes.

## 4. Implementation (branch `codex/p3-paired-key`)

- `compare_private_pair` takes the comparator's `rebuild_noise` (`value`, `measurement_digest`). A challenger wins only if `total > king_total + value`. If no noise is registered, the result is UNAVAILABLE.
- `winner_eligibility.decide` accepts a bank-comparison promotion kind. It uses the existing predecessor check and the same-miner `no_reset`.
