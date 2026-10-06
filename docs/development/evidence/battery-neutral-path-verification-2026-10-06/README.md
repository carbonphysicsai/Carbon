# Battery neutral validator — bounded DEVELOPMENT verification

This is a retrospective engineering regression on published DEVELOPMENT
examples, not a new scientific experiment or an official hidden exam.

## Identity and execution

- Source commit: `d12b14f79e095f0e2adf80b0c7eba289d22378be` (main after
  Motor Interface-v1 PR #706).
- Source tree: `edafb1fbefa3cac92eb8146d4bae495f93d2b28a`.
- Runtime: `./scripts/dev/canonical.sh`, pinned Ubuntu 24.04/linux-amd64,
  CPython 3.11.16, uv 0.12.7, `dev science-jax` lock groups.
- Command, from the source-tree root:

  ```bash
  CARBON_UV_GROUPS=science-jax ./scripts/dev/canonical.sh python -m pytest -q \
    tests/cpu/test_challenge_validator_battery.py \
    tests/cpu/test_challenge_validator_contract.py \
    tests/cpu/test_challenge_validator_scoring.py \
    tests/cpu/test_challenge_readiness.py
  ```

- Result: **156 passed in 99.56 seconds**. No test was skipped or failed in
  this selection. This was a local canonical check; PR CI is separate.

The source tree pins all inspected code and tests. Additional SHA-256 checks
for the relevant files (hex, lower case):

| Path | SHA-256 |
| --- | --- |
| `carbon/challenge_validator/battery.py` | `246a88ae52ef998abd0d47d1eba78d448b8bbdd6bea6bbe308a23f0b5d238827` |
| `carbon/challenge_validator/dispatch.py` | `a7fce0dc195f58ee2b58433c3efca54abd7c7ae4df7aa08e5a0b1fe0afe8b473` |
| `tests/cpu/test_challenge_validator_battery.py` | `a230f31d88519ad7b9c6decf4f2cb935ee839895b94a485bdda3205fc2b5146a` |
| `tests/cpu/test_challenge_validator_contract.py` | `f4978475316f341d9843665915f48eb0bc3b48364beda64c44d3cb2e1c66b63b` |
| `tests/cpu/test_challenge_validator_scoring.py` | `5e5f63630d87df487f1fcbc845201f092fccb8c1650c115112ca29229c71048a` |
| `tests/cpu/test_challenge_readiness.py` | `e259203097f769514122045f3d304ef9ad04e313c3736c245f2decf92dfa458f` |
| `carbon/challenge_readiness/records/battery-fastcharge-ageing-development-v1.v3.json` | `abd8ff2b9bc1cf279a3771e52ed5fe49982ddee6d69c5a1dbbdc3cb9558218b9` |

## What this establishes

The existing `BatteryAdapter` still dispatches Battery submissions through the
Challenge-neutral validator on this source tree. The Battery-specific test
compares a sequence of published DEVELOPMENT examples through the direct
deployment and neutral routes, asserting byte-identical miner outcomes and
matching stored scores, bindings and finals (aside from wall-clock columns).
The selected tests also cover strict transport/contract admission, rule pins,
operator-only score replay, disclosure of no hidden case/seed, reserved and
sealed role refusal without journal mutation, typed `UNAVAILABLE`, and
infrastructure failure that does not become a scientific score.

The tests use retained published PyBaMM reference examples and a
`DirectBackend` with temporary test-local validator roots. The literal
reserved role `ev5-confirmation` is tested for refusal; EV5's actual sealed
batch and journal sequence 14 were not opened or changed.

## What this does not establish

- `DirectBackend` does not test production worker/container isolation or a
  security-acceptance claim.
- Published DEVELOPMENT examples do not estimate performance on a fresh
  protected population, validate the Score Pack candidate, or constitute
  mainnet/Graphite qualification.
- The current Battery readiness record remains
  `PROPOSED_DEVELOPMENT_DESIGN`. Its admission tracks and training-budget
  study are `NOT_STARTED`; scientific, numerical-reference, customer and
  launch reviews are also `NOT_STARTED`, and security is `IN_REVIEW` in that
  record. This ticket does not reinterpret or update those states.
- The prospective 45/30/25 physics/robustness/accuracy weighting is not an
  adopted Battery rule. No score, gate, population or LIVE setting changed.

## Next justified step

Use the already owned readiness and scoring work to resolve its named gaps,
then run the registered gate with owner/operator evidence. Do not convert
this bounded regression into a readiness declaration or use it to inspect
protected cases.
