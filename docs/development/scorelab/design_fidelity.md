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

## Reusable run for newly tested models

The prospective `rich-design` command uses the same reducer and v4 ScoreEngine
for an explicit, hash-bound public development input. It does not construct a
model, invoke inference, collect reference truth or replace the normal model
bank/receiver. A Challenge adapter binds the normal retained artifact and its
native measurements before supplying this projection.

```sh
python -m scripts.dev.score_lab rich-design \
  --input public-rich-design-input.json \
  --input-sha256 <exact-64-character-sha256-of-input-bytes> \
  --out new-score-report.json
```

The input has schema `carbon.scorelab.rich-design-input.v1`, scope
`PUBLIC_DEVELOPMENT`, and fields `policy`, `reference`, `models`,
`original_pack`, `original_benchmark` and `provenance`. The optional
`original_result` supplies the retained native result for exact same-core replay.
`policy`/`reference`/`models` are the existing pure reducer inputs. The original
pack and benchmark retain native gates, broad Physics, cost and artifact
identities. Provenance binds the original pack digest and canonical benchmark
digest plus any source-owned evidence identities. Missing or mismatched
bindings are refused; this JSON declaration cannot authenticate scientific
acceptance, hidden custody or official eligibility.

One input can contain all compatible models or a selected cohort. Its native
benchmark must contain exactly the same unique model artifacts as the reducer
input. The measurement/pack identity depends on the fixed policy, reference
and original pack, not which other models happen to be tested alongside it.
Per-run model/input digests remain in provenance. Comparisons still require
compatible original Challenge, measurement and reference identities; this does
not authorize comparison across different rulers.

The output contains the per-model verified-value/critical-fidelity reduction
and two same-core projections:

- `PARTIAL_POINT_DIAGNOSTIC` retains a labelled numeric point result where
  calculable, along with gaps and adverse outcomes. It grants no registered
  score, scientific qualification or production authority.
- `REGISTERED_COMPONENTS_REQUIRED` keeps Design and total unavailable when
  accepted reference resolution or required coverage is missing. It never
  converts that evidence gap into a candidate-caused physics failure.

Native gates, Physics measurements and measured workflow costs are preserved.
A correct finite-menu pick is not broad boundary or OOD evidence. The finite
coverage recommendation remains unadopted; no coverage rule or accepted
interval is inferred by this command. Existing results are immutable: the CLI
requires a fresh output path and refuses a changed input digest, duplicate JSON
keys, nonfinite constants or a nonpublic input scope.

Author validation of this follow-up is static only until Product/CI runs the
new pure projection and CLI toy suites. No new actual-model or reference result
is claimed by adding the reusable command. The fixed reference panel is reused
across models; a new compatible prediction does not require another solver
campaign.

### Normal measurement-basis handoff

An optional `measurement_basis` input supplies the existing normal caller's
closed `carbon.scoring.dual-measurement-contract.v1` object: `schema`,
`producer_digest`, `accuracy_definition_sha256`,
`important_limit_definition_sha256`, and `design_objective_sha256`. All four
digests are exact `sha256:` identities. Its measurement digest uses the normal
caller's sorted compact JSON plus final newline. This is deliberately distinct
from a raw file hash or an arbitrary descriptive policy digest.

Only the registered-components-required projection may bind that basis. The
point diagnostic keeps a different descriptive measurement/pack identity, so a
numeric partial result cannot be substituted under the registered basis. The
full policy/reference audit remains in the projection report. Supplying a
well-shaped basis authenticates nothing: the normal trusted producer still has
to bind its actual code, definition-role bytes, model/state/query originals,
reference acceptance and independently registered measurement receipt. Missing
reference resolution or applicability still leaves the registered score null.
No validator/receiver parser is loosened by this handoff.
