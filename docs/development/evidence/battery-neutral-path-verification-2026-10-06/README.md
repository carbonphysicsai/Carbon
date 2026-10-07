# Battery neutral validator — bounded DEVELOPMENT verification

This is a retrospective engineering regression on published DEVELOPMENT
examples, not a new scientific experiment or an official hidden exam.

## Identity and execution

- Reconciled source commit: `74efce7be818fc028f9304a03ca032ea6bad575d`
  (main after Validator-19 PR #708); tested branch merge commit:
  `5116d881238fb10708f25da4bf1b3ceedb69d784`. The executable files
  are unchanged between that main commit and the tested merge.
- Reconciled main source tree: `b57865af1f488400c52beffe959bf6e3e5847727`.
- Runtime: `./scripts/dev/canonical.sh`, pinned Ubuntu 24.04/linux-amd64,
  CPython 3.11.16, uv 0.12.7, `dev science-jax archive` lock groups.
- Command, from the source-tree root:

  ```bash
  CARBON_UV_GROUPS='science-jax archive' ./scripts/dev/canonical.sh python -m pytest -q \
    tests/cpu/test_challenge_validator_battery.py \
    tests/cpu/test_challenge_validator_contract.py \
    tests/cpu/test_challenge_validator_scoring.py \
    tests/cpu/test_challenge_validator_producer.py \
    tests/cpu/test_challenge_validator_acceptance.py \
    tests/cpu/test_challenge_validator_rotation.py \
    tests/cpu/test_challenge_readiness.py
  ```

- Result: **188 passed in 140.27 seconds**. No test was skipped or failed in
  this corrected selection. This was a local canonical check; PR CI is
  separate.

An earlier four-file selection on `d12b14f79` passed 156 tests in 99.56
seconds. Main then merged Validator-19 changes to the Battery adapter. The
first expanded run at the reconciled head used only `science-jax` and ended
with 173 passes, 14 errors and 1 failure; the first isolated error was
`ModuleNotFoundError: cryptography` in `ProducerKey.create`. That is a test
environment omission: `cryptography==50.0.1` is pinned in the repository's
`archive` dependency group. The corrected full rerun with both groups is the
188-pass result above. The failed attempt is retained as evidence, not
counted as an implementation regression or a pass.

The source tree pins all inspected code and tests. Additional SHA-256 checks
for the relevant files (hex, lower case):

| Path | SHA-256 |
| --- | --- |
| `carbon/challenge_validator/battery.py` | `e21cf3fa537a93ce24be1b004552b1bcba30e60d19a7b861975356e70d3b39b0` |
| `carbon/challenge_validator/dispatch.py` | `a7fce0dc195f58ee2b58433c3efca54abd7c7ae4df7aa08e5a0b1fe0afe8b473` |
| `carbon/challenge_validator/acceptance.py` | `96f6ccba0e5f55d6e1f3929167cce5a68743ada95ee93c9cd9d6af2fbbadcf2` |
| `carbon/challenge_validator/producer.py` | `5fadccd46cfb72705b03c59858ea1be86e5f52811ede880fb93d20ffe8f1f749` |
| `tests/cpu/test_challenge_validator_battery.py` | `a230f31d88519ad7b9c6decf4f2cb935ee839895b94a485bdda3205fc2b5146a` |
| `tests/cpu/test_challenge_validator_acceptance.py` | `fbf3efc9b9e918402e5e60b80a51a3d8a5eb157ad3a6a1274cf2dc545eb163b0` |
| `tests/cpu/test_challenge_validator_rotation.py` | `09d7766d750ca6ec127510727fbb1ddb002b385e6aad1671de90550a0096e73a` |
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
infrastructure failure that does not become a scientific score. The expanded
selection covers the new synthetic producer, acceptance and block-window
rotation path in the merged Validator-19 work.

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
