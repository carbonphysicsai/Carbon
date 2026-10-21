# OWNER-FIRST-CROWN-BEATS-BASELINE-01: the first crown must beat Carbon's baseline

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("A").
Implementation: `codex/koth-baseline-floor` (this commit), in the KOTH comparator and `koth_registry`.

## Question

The leg minimums come from Carbon's baseline (OWNER-LEG-MINIMUM-BEST-AGENT-01). A model passes them at equality (`legs < minimum` fails). Today's placeholder baselines are public scaffolds. So any miner could submit the public scaffold unchanged, sit exactly on the minimums, and take the first crown and its share for no work.
- **A:** the first crown must beat the baseline. The baseline acts as an unpaid starting king, so the first real king must beat it by the registered margin, and the share burns until then.
- **B:** matching is enough.

The Validator recommended A. The owner answered: "A".

## Decided

- **The baseline total** is the pack's own total at its leg minimums, with the same combination `dual_score` uses.
- **To become the first incumbent, or to take the crown from a king that fails a mandatory gate,** a scored contender must exceed the baseline total by the registered rebuild noise. Otherwise:
  - with no king, there's no winner (`within_baseline_floor`);
  - a gate-failing king is still dethroned, and the crown vacates.
- **A pack without leg minimums,** or with no registered noise, is UNAVAILABLE (`baseline_floor_unregistered` or `rebuild_noise_unregistered`). It's never a free crown.
- **The leg minimums themselves are unchanged:** meeting them still makes a submission scored. Only taking the crown requires beating the baseline.
- **Everything else in KOTH-TAKEOVER-RULE-01 is unchanged.**
