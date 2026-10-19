# Pure DEVELOPMENT Design-fidelity reduction

This is the bounded implementation slice under
`OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01`. The working four-Challenge
measurement design is [specified here](four_challenge_design_fidelity_dev1.md).
It is not a scientific acceptance, a deployed Score Pack or a full four-packet
readiness claim.

## Reuse and contract

`carbon.scoring.design_fidelity.reduce_design(policy, reference, models)` is a
pure standard-library reduction. It performs no I/O, model construction,
inference, reference execution, case sampling or final score computation.
Challenge-owned adapters supply native observed quantities, a reference-only
frozen cohort/pair policy, exact common identities, committed predictions and
choices, and explicit unit-matched normalization. There are no Challenge
thresholds, weights or budgets in the reducer.

The policy declares case/action IDs; quantity units and learned/analytic roles;
objective sense, scale and equivalence; margin/response/gap/resonance components;
and required side/proximity coverage. References declare settled status, native
values and source-accepted intervals where available. Models supply artifact
identity, their committed choice and predicted quantities on the common mask.
Malformed contracts are refused. Caller-supplied receipt strings bind a source
assertion; this pure function cannot authenticate scientific acceptance.

The output retains verified-value credit V, critical-prediction credit C,
`point_estimate_D=min(V,C)`, raw errors, interval bounds, limiting components,
coverage, and separate candidate/reference outcomes. `registered_D` remains
null when required reference resolution/coverage or value equivalence is
unresolved. A numeric partial diagnostic is not a complete exam or an
eligibility permission. Analytic quantities earn no critical-prediction credit.
Reference failure never becomes a scientific candidate failure; actual invalid
predictions or proven unsafe selection remain visible independently.

## Same-score-engine integration

Keep native gates and broad Physics A in the existing benchmark input. A caller
binds a new measurement identity and supplies the resolved Design benefit to
`ScoreEngine.score_dual_benchmark_v4`, using its existing typed measurement
states, immutable pack identity and 50/50 arithmetic rule. The reducer does not
modify that core, historical results, bank promotion or emission logic.

For incomplete public development evidence, distinguish a labelled point-only
diagnostic projection from a registered-components-required projection. The
latter uses REFERENCE_UNRESOLVED rather than a numeric measurement when
`registered_D` is null. The bank/receiver's real custody and eligibility contract
continues to control intake; a Boolean emitted by this library grants no
official, product TRUST or promotion authority.

## Validation and maturity

`tests/cpu/test_design_fidelity.py` exercises toy tasks only: continuous loss,
correct pick/wrong margins, response/gap fidelity, units, analytic exclusion,
unresolved references, candidate-invalid/unsafe coexistence, side/proximity
coverage, interval differences and minimization/maximization regret bounds.
Self-comparison is exactly zero; one feasible action cannot acquire regret
merely because its reference has an interval. Full credit is not registered
when objective equivalence remains unresolved.

The module bytes match the retained operator reducer at SHA256
`042d89658b30937d0f3e905617acb5d57b3cf1190c6350331e530d1364c6db20`.
Product's actual isolated operator suite passed 30 toys; its saved-data adapter
used this module with the unchanged ScoreEngine over eight existing public
Motor/Cooling models. That is bounded development evidence, not canonical
validation of this repository placement. The canonical test command for this
slice is:

```sh
./scripts/dev/canonical.sh --focused tests/cpu/test_design_fidelity.py
```

No author-side application tests, hidden material, new model/solver runs or
production changes accompany this source slice. f02/f08 native accepted
reference outputs and their source-owned adapters remain separate work.

Hub impact: no Hub mutation; the current lean owner protocol freezes that
derived surface. Existing scoring, native observer, producer, bank and product
authority remain controlling. Domain-boundary and reference failure invariants
are exercised without widening execution authority.
