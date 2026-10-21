# OWNER-REBUILD-TIME-LIMIT-01: rebuild time is the only training limit; Battery accepts build code

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session.
Implementation: **not yet implemented.** Today the construction limits still carry fixed step caps (Battery: 20,000), and Battery grades graph recipes only.

## Questions (relayed from a miner's feedback)

1. Should Battery accept build-code (bundle) recipes, as Motor does?
2. Should the fixed step cap be raised, or the budget set by time instead?

## Owner, verbatim

> yes, yes I don't want to limit miners. the limit should be a rebuild time not a step count for all challenges

## Decided

- **Battery accepts bundle (build-code) recipes,** as Motor, Cooling, F08 and F02 do.
- **For every Challenge, the only training limit is the registered rebuild wall time.** There's no fixed step cap. A recipe declares its own training settings (steps and the rest), and the validator rebuilds exactly what is declared.
- **A rebuild that exceeds the wall time is refused** as the candidate's own construction outcome (typed, never FAILED_INFRA).

## How this keeps rebuilds deterministic (Validator)

- **The time limit is a cap, not a budget.** Training does not run "until time is up", because a faster machine would then train a different model from a slower one, and validators would disagree.
- **A declared recipe trains the same way on every host.** Only whether it finishes in time can differ.

## Consequences (stated to the owner)

- **Longer rebuilds raise the rolling mean rebuild time Σt.** Under OWNER-CADENCE-AND-ROTATION-02, that lowers every miner's daily allowance a.
- **Speed differs between hosts.** A recipe that finishes just under the limit on one validator may exceed it on a slower one, so miners should keep headroom. The registered wall times are unchanged by this record.
- **New kit version:** removing the step caps changes the construction limits, so it's a new kit and evaluation version. It's prospective and lands with the step-2 recalibration.

## The wall time is measured (owner, 2026-10-21)

- **The relay:** the owner gave this in the Test Lead's session.
- **Confirmed directly in the Carbon Validator's session ("Measured: 2× slowest"),** superseding the fixed 30 minutes the owner had picked a few minutes earlier.
- **The rule:** the rebuild wall time is **2× the build time of the slowest Carbon-tested catalog backbone**, measured on the registered validator host class.
  - The Validator records the measurement: which backbone, host fingerprint, image digest and seconds.
  - Until it's measured, the current 1800 s (`MAX_TASK_WALL`) stays as the interim value.
- **It's the only training limit.** No shorter deadline may act as a second training cap (see `VALIDATOR_MINER_PATH_LIMITS_RULINGS_20261021.md`).
- **Re-measure** when the slowest catalog entry changes, or when the host class or image changes.
