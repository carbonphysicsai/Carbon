# Existing-law gate controls and threshold curves (PKT-19)

This is a synthetic control harness and observable-coverage audit. It executes
existing registered gate operators, tests their negative controls and reports
counterfactual threshold curves. It does not add an adopted scientific gate,
choose a tolerance, alter a score or qualify a model/reference/exam.

The ticket's claim that no conservation/boundary/PDE checks existed is
**DOCUMENTATION_LAG**. The Test Lead accepted this bounded scope correction;
additional scientific scope still requires Carbon Validator's identified law,
observable, Challenge, applicability and owner-set adoption/tolerance.

## The actual implemented inventory

| Check | Quantity and authority | Implemented role |
|---|---|---|
| Burgers conserved mean | Equal-space mean of the periodic field versus prescribed initial mean, divided by prescribed amplitude | Mandatory DEVELOPMENT gate in `carbon.scoring.development`; existing limit 0.01, strict comparison with its arithmetic guard |
| Burgers initial condition | Maximum sampled initial-field error versus the prescribed input, divided by amplitude | Mandatory DEVELOPMENT gate; existing representation allowance 32 float32 eps |
| Burgers energy trajectory | Sampled fluctuation-energy path versus reference | Existing mandatory gate; integrated dissipation balance and finite-mode weak-PDE residual stay explicitly limited diagnostics |
| Battery initial temperature (B2) | Initial predicted temperature versus ambient | Existing exam gate, using its reference-derived tolerance rule |
| Battery initial voltage (B3) | Initial voltage near pinned OCV | Existing bounded-offset gate; it is not exact equality because the reference has side-reaction offsets |
| Battery voltage bounds (B1) | Protocol's cycler limits | Existing exam gates |
| Battery inventory capacity bound | Every checkpoint obeys `0 < Q_k <= Q_bound`; bound from minimum electrode/lithium-inventory capacity | Existing exact exam gate, with no tolerance |
| Battery B15 | Rest-prefix temperature causality | Adopted additional gate at the owner's 1e-4 C allowance, unchanged |
| Battery B16 / B9 / B8 | Rest-voltage leak / below-ambient deficit / ambient monotonicity | B16 card; B9 card plus Guard VERIFY; B8 diagnostic. Their roles are unchanged |

Sources: [Burgers rule and limitations](../CW1_DEVELOPMENT_SCORING_RULE.md),
[measurements](../../../carbon/measurement_runtime/development.py),
[battery gate definitions](../../../carbon/battery/exam.py), and
[owner's adoption record](../../../.agent/decisions/2026-10-13-OWNER-PHYSICS-GATES-01.md).
The decision and working contract are tracked with this PR.

## What runs

[The harness](../../../scripts/dev/physics_law_gates.py) has no candidate or
reference data-input path. Its `--check` option reads a generated fixture
artifact for comparison.
It admits only its built-in synthetic fixtures. No native solve, host worker,
model training, protected material, model submission or deployment runs.

For Burgers it reuses the analytic `verification-v2` controls, the derived
measurement, and the actual DEVELOPMENT judge. A mean-drifting control is
rejected even when its descriptive score exceeds a lawful comparator's score.
A shifted initial row preserves mean/extrema and must fail initial recovery.
The score API's 2x12x3 rectangle repeats each one-control fixture; those rows
are **not** independent physical cases or reconstructions.

For battery it executes `exam.evaluate_case` and `exam.aggregate` on synthetic
curves. Initial-temperature, over-inventory and zero-capacity controls must
fail. A missing output cannot pass. Even a hypothetical zero error cannot
compensate the boundary failure. Reference-invalid and infrastructure-failed
controls retain their distinct states and no candidate-law breach is inferred.
The 25 C/3.6 V/4.5 Ah outputs and 5 Ah bound are **fixture settings**, not a
calibration of the actual battery parameter-set inventory bound.

`controls_passed` has a twelve-check basis. Tests deliberately replace the
underlying battery checker with an always-pass checker and remove Burgers law
failures: both broken implementations must break the harness controls.

## The curves and the fail-closed seam

[synthetic-curves.json](synthetic-curves.json) retains each proposed threshold,
admitted/excluded/unresolved control identities and counts. Threshold points
are observed residual breakpoints, midpoints and adjacent floats. They are not
selected/fitted science values. Curves operate on **one law**, not overall
candidate admissibility; a model passing a temperature check can still fail
its inventory check or decision-value exam.

The battery temperature curves also retain actual gate verdicts for direct
agreement. Inventory sweeps call the actual capacity gate at each hypothetical
bound, retaining its strict positive-capacity requirement. Missing/nonfinite
readings remain UNRESOLVED; they never disappear from the basis. The inventory
curve illustrates fixture parameter sensitivity: the actual `Q_bound` is
derived from the registered parameter set and must not be fitted to admit
models. This curve supplies no alternative capacity-calibration rule.
A threshold
of `None` returns `HUMAN_INPUT`, makes zero threshold comparisons and cannot
pass. Additional law/observable/Challenge/applicability/tolerance slots remain
null with `adoption: HUMAN_INPUT` and `admissible: false`. No new gate is effective.

Generation inside the pinned canonical environment:

```sh
python -m scripts.dev.physics_law_gates --output docs/development/physics-law-gates/synthetic-curves.json
```

Verification from a noncanonical host:

```sh
CARBON_UV_GROUPS='science-jax archive' ./scripts/dev/canonical.sh python -m scripts.dev.physics_law_gates --check docs/development/physics-law-gates/synthetic-curves.json
CARBON_UV_GROUPS='science-jax archive' ./scripts/dev/canonical.sh --focused tests/cpu/test_physics_law_gate_controls.py tests/cpu/test_physics_contract.py tests/cpu/test_battery_physics_gate.py tests/cpu/test_cw1_development_scoring.py
```

The artifact pins the existing operator/authority bytes and harness bytes.
These pins establish what ran, not scientific qualification. It has its own
synthetic-controls schema and cannot replace a deployment physics contract.

## What remains unobservable or unadopted

Mean/initial recovery does not prove Burgers dynamics: a frozen initial field
satisfies those laws but the registered energy-path gate rejects it. Periodic
Fourier closure on an endpoint-excluded grid is a representation identity;
it does not independently test boundary traces. Underresolved energy balance
and finite-mode weak residuals do not become physical-solution certificates.

Battery's published voltage/temperature/plating-margin/cycle-capacity outputs
do not contain the internal lithium inventories, current and thermal-flux
terms required for a new full charge or heat balance. The capacity bound is
an inventory-derived inequality, not that equality. No new law is inferred
from absent observables. Additional scope stays with the Validator/owner.
