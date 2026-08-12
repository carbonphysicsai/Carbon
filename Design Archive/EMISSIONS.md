# Hydrogen Emissions Overview (Current State)

**Last Updated:** July 2026

## Current Emissions Model

Hydrogen currently uses **standard Yuma Consensus** miner emissions.

- The validator computes weights using the `ChallengeWinnerTracker`.
- Weights are submitted via the standard `subtensor.set_weights()` call.
- Miner rewards are determined by Yuma Consensus (stake-weighted median + clipping + normalization).

## Weight Distribution Logic (Active)

The `ChallengeWinnerTracker` produces weights with the following characteristics:

- Strong preference for current leaders of active challenges (winner-heavy).
- Small participation "dust" for recent miners who do not win.
- Exponential decay on old performance.
- Only miners who beat the current best **combined score** on a challenge receive meaningful credit.

## Summary

| Aspect                    | Current Status          | Notes |
|---------------------------|-------------------------|-------|
| Base emissions            | Standard Yuma           | Via `set_weights()` |
| Per-challenge rewards     | Partially supported     | Via tracker per-challenge logic |
| Daily/round reset         | Supported via tracker   | Exponential decay + round reset |

For the most up-to-date behavior, refer to `ChallengeWinnerTracker.get_weights()` and the validator's `_set_weights()` method.
