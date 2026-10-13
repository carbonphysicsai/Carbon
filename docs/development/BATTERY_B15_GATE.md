# Battery B15 deployment component (PLT-13)

The owner adopted B15 in
[OWNER-PHYSICS-GATES-01](../../.agent/decisions/2026-10-13-OWNER-PHYSICS-GATES-01.md).
This implements that decision for prospective DEVELOPMENT/testnet states.
It does not deploy a validator, change a current window, reinterpret EV5 or
qualify a solver, model, security boundary or mainnet policy.

`carbon/battery/physics_contract.v2.json` keeps v1's law definitions,
measurement geometry and all other adoption states. Only B15 becomes ADOPTED:
temperature at 0, 30, 60 and 90 seconds is invariant under the registered c1
or c2 move, at most 1e-4 degC absolute, with zero permitted violations.
The 120-second switch endpoint is excluded. Its reference image is
`sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940`.
The old v1 and its public screen remain historical evidence.

## Operator registration and new state

The existing `carbon.battery.validator-deployment.v1` configuration accepts
an optional `physics_contract` component. Its closed shape is:

```json
{
  "contract_sha256": "<hex SHA-256 of physics_contract.v2.json bytes>",
  "probes_path": "<operator-registered JSON probe plan path>",
  "probes_sha256": "<hex SHA-256 of that plan's bytes>",
  "reference_image": "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
}
```

The registered plan is an object with exactly `schema`
(`carbon.battery.physics-probes.v1`), `contract_sha256` and `pairs`.
Each pair has exactly `axis` (`c1` or `c2`), `base` and `partner`. Both inputs
contain exactly c1/c2/t_amb_c/soc0 and lie in the unchanged contract box.
Only the named axis moves, upwards by 0.05 of its registered range; all other
inputs match. Pairs are nonempty, unique and cover both axes. No default
population, count, new sampling law, solver run or paid campaign is supplied
by this code. The operator must register the intended explicit plan. Relative
paths resolve against the repository; JSON size is bounded to 4 MiB as an
engineering input limit. Wrong bytes, image or adoption are refused before
deployment state/private inputs are opened. A new image requires a new owner
screen/adoption and prospective contract implementation, not a config override.
The loader also refuses a mainnet deployment configuration explicitly.

The component's identity binds contract bytes, plan bytes, adoption reference,
image and both checker modules' bytes. It is included in `identities()` and
admission bindings only when configured. Existing `PoolStore.bind` refuses
adding/removing/changing it on old state; the carryover allow-list also refuses
it. Use a new deployment state from its first window. Release inclusion and
testnet upgrade belong to PR Head and the owner. No deployment is performed.

## Eligibility, retries and evidence

The retained candidate is inferred on those pairs through its existing worker,
without a reference solve. Predictions are stored under a component-specific
`physics/` namespace, apart from scored cases, quiz/design/leak predictions.
Screening conjuncts B15 with existing exam and registered-score gates before
nomination. A violation or incomplete/invalid candidate prediction yields
ineligible and closed `physics_gate_b15`; soft scores cannot compensate.
Worker infrastructure failures propagate as FAILED_INFRA/retry, never a B15
failure. Finals independently check both fresh rebuilt models; a challenger
failure forbids promotion. Decision verification and G-FEAS stay in place.

The operator score record retains B15's basis/counts/maximum and two
measurement-only model-card blocks: B16 maximum rest-voltage leak in mV;
B9 maximum below-ambient deficit and shares of resolved cases above 0.1 and
1 degC. Every metric reports checked/unresolved counts; absent evidence is
null, never a zero reading. B16/B9 do not affect eligibility or scoring.
`BatteryAdapter.score_record` replays these from stored predictions without
dispatching work, and refuses a mismatch. No new fields are disclosed to
miners: the existing nonsealed gate-code list may contain `physics_gate_b15`;
sealed outcomes still expose no screening evidence. No probe points, plan
identities, raw residuals or card metrics enter miner projections.

Without the component the same identities, scoring, outcomes and worker calls
remain: a golden test compares the complete legacy score record. Acceptance
also covers the inclusive allowance boundary, incomplete plans/predictions,
image/digest mismatch, new-state/carryover rejection, fresh finalists,
infrastructure retry, read-only replay and miner import closure. The retained
public screen's 65 good-value and 137 rebuilt members pass the adopted
allowance; the constructed boundary optimist fails. This reuses recorded
public evidence rather than re-running a calibration or declaring qualification.
