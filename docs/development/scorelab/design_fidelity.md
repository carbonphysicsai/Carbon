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


### Complete finite-task point-reference candidate

The optional `finite_task_registration` adds a separate
`FINITE_TASK_POINT_REFERENCE` projection. This is a prospective DEVELOPMENT
candidate for an exhaustively enumerated finite menu: every action under every
mandatory condition must have a pinned native reference and prediction. It
uses the same native Physics, gates, accounting and 50/50 combination, with
continuous `D=min(V,C)` and raw point-reference errors. It grants no learned
credit to analytically known quantities.

Native Motor/Cooling DEVELOPMENT `customer_decision._reference_verdict`,
`verify`, and `exam.score_case` at source
`f3bb0742a24f5931120867a7d313608485cd5f0a` accept artifact-admitted matching OK
point references. An accepted numerical interval is not a prerequisite to that
narrow fixed-reference task. The earlier rich candidate's stronger interval and
boundary-coverage requirements remain unchanged, as do its historical nulls.

The new projection explicitly reports reference uncertainty `UNMEASURED`.
Absent sign sides in a complete finite menu do not prove boundary proficiency;
no population, independent OOD, numerical-uncertainty or qualification claim
follows. Missing or unresolved reference rows defer the complete common task;
missing/invalid candidate outputs remain candidate-specific ineligibility.
Source acceptance and native-contract hashes bind the supplied provenance but
cannot authenticate the source or create scientific authority by themselves.

Its closed `carbon.scoring.finite-task-point-registration.v1` document pins
policy/reference identities, ordered action and case rosters, all mandatory
conditions and the complete action/condition-to-case mapping. Optional
`finite_task_measurement_basis` uses the normal five-field basis. Its producer
and Design-definition pins must differ from a simultaneously supplied stronger
interval basis; the distinct `finite_task_point_design_benefit` metric also
prevents pack-identity aliasing across calls. Normal trusted producer receipts
and selected-role bindings still apply.

The public CLI accepts these two optional fields. Frozen old input files are
unchanged. New Motor/Cooling complete-roster candidate inputs reuse all saved
48-row panels and require no new fit, inference or solver execution. Source
static checks alone are not their runtime validation or score adoption.


### Normal physical producer: current bounded implementation

`private_evaluation_source.produce_dual_benchmark_input` now has a fixed f02
cold-eight source path. It reuses retained graph inference authentication,
source/pack receipt builders, the original all-eight/near-four/worst Physics
formula, deterministic energy-max/lexical selection, the shared rich Design
reducer and the same dual core. It imports no participant producer callback.
Other Challenge producers remain explicitly unavailable in this slice.

The source-owned public definitions use method
`f02-cold-eight-rich-design.v1` and schemas
`carbon.scoring.f02-cold-accuracy.v1`,
`carbon.scoring.f02-cold-limits.v1`, and
`carbon.scoring.f02-cold-design.v1`. They supply the exact producer/TRAIN
identities, positive measured TRAIN spread, fixed native gate set, source bands
identity and explicit canonical Design policy/scales. No scale is defaulted.
Private case-bank, reference-row, solver-evidence and Score Pack role bytes are
required. The case bank binds all eight original actions, the fixed cold
context and exact input digest. The private reference role binds actual B10
family acceptance, all three native B8 rungs, the actual raw reference vector,
source acceptance content and any separately accepted intervals. A hash alone
cannot make the native acceptance gate pass. Truth remains private-role data.

**This is not a ready normal physical grader.** The real normal role files have
not been materialized, and current graph worker originals contain only one
inference. All four native gates, including `paired_repeat`, remain required.
The fixed producer refuses missing repeat evidence explicitly; it never treats
two copies of one retained output as a repeat and never silently removes that
gate. Platform/Lead owns the actual normal worker/custody evidence extension.
The selection derived by this producer is labelled as derived from frozen
predictions; it is not described as a previously saved committed action.

The first fixed f02 producer emits only the stronger registered-interval
Design measurement when its native evidence is complete. Point-only results
remain diagnostics there. The separate finite-task point candidate above is
currently the saved-evidence path; supporting it in the normal producer needs
its own exact source-owned definition/Score Pack binding. No runtime or source
completion claim follows from the inert tests or static validation.
