# Decision Assistant — PRD-03 DEVELOPMENT contract

The Assistant searches an explicitly declared finite design bank through the
Envelope Guard, freezes provisional top-k and verification order, independently
checks selected picks, and returns an immutable audit result. It supplies no
scientific score, product qualification, production authority or LIVE wiring.
Models, measurement adapters and reference adapters are trusted local host
callables. Their content/runtime identities are assertions, not executable
attestation, authenticated acceptance or hostile-code isolation.

KEEP Carbon's native BudgetCap/BudgetLedger, equal-budget replay, native physical
validity declarations and the public battery decision observer. This package
wraps them rather than rewriting their scientific or budget policies. D01–D11,
Q0–Q8 and PB-INV/ADV/ESC/ART/LAT remain the governing product boundaries.

## Inputs and API

```python
from carbon.product.decision_assistant import DecisionAssistant, assess_finite_bank
from carbon.product.decision_assistant.demo import fixture

# Explicitly SYNTHETIC arithmetic examples, not a real battery model or solver.
inputs = fixture()
assistant = DecisionAssistant(**inputs)
frozen_result = assistant.run()
result = frozen_result.to_dict()
assessment = assess_finite_bank(
    assistant, frozen_result,
    reference=inputs["reference"], budget=inputs["budget"],
)
```

All documents have closed schemas and DEVELOPMENT scope. Native finite numbers
exclude Booleans and overflow; units, identifiers, duplicates, k, shapes and exact
question/model/Guard/reference/measurement identities are checked. Configuration
and output copies cannot mutate a later run. Plain math strings are not executed.

| Input | Required meaning |
| --- | --- |
| Question law | `carbon.product.assistant-question.v1`, exact version and authority, SYNTHETIC_FIXTURE/REGISTERED_DEVELOPMENT basis, separate population/proposal/weight references, objective direction/unit, explicit hard constraints/units/reference bands, action IDs and numeric queries, k, measurement identity and `FINITE_BANK_DECLARED_ORDER_V1`. Maximum 256 actions, 16 constraints and 16 input variables are engineering resource limits. |
| Model and Guard | Nominal `ModelBinding` plus the existing Guard inputs without another model. The question's input units match the Guard. Missing/unknown physical validity and outside-reference queries remain REFUSE. ADOPTED calibrated laws and deterministic probe policy stay owned by the Guard. |
| Measurement | Nominal `MeasurementBinding(id, code_digest, measure)` returning `Measurement(objective, values, units)`. Values match the question's exact constraint IDs/units. Missing objective/limits/bands stay unresolved. Reference bands come from the caller's accepted measurement policy; no tolerance is guessed. |
| Budget | `carbon.product.assistant-budget.v1`, explicit authority, basis, native wall/core/solver-evaluation cap, Guard-query and model-call limits, positive complete Guard/reference call bounds and explicit startup cost. Missing authority stops before any model/reference call. Every Guard probe call counts against the model-call cap. |
| Reference | Nominal `ReferenceBinding(image_digest, record_digest, runtime_digest, kind, status, solve)`. Image and record match the Guard. READY is an asserted host status, not scientific acceptance. SOLVER_NOT_ACCEPTED/unknown/failed status stops execution and prevents a recommendation. The observation binds query, image, receipt, typed status and exact output shape. |
| Expected regret | Optional `carbon.product.assistant-regret-evidence.v1` with an independently assessed role, exact `assistant.regret_pins`, source digest, sample count, units, method, confidence and interval. This is a host-supplied recorded estimate assertion. Without it return null/GAP; never infer expected regret from a prediction, map or observed finite-bank optimum. |

The development schema is an Assistant-owned projection, not a new scientific
question-law or scoring API. It does not adopt battery v3, create a target
population, change P/Q/w, sign records or establish physical applicability.

## Search, verification and cost

Declared action order controls bounded search; objective ties use action ID.
Only non-refused, predicted-feasible actions enter provisional top-k. Unresolved
VERIFY candidates can fill spare shortlist slots. The verification plan puts
VERIFY before TRUST, then provisional order and ID. Its immutable commitment
is created before any reference call. Every selected TRUST pick is still
independently re-solved: pooled map errors never certify optimizer-selected
feasibility. Predicted-infeasible, refused, deferred and unverified rows remain
visible. Search is finite-bank enumeration, not a global optimizer claim.

Reference feasibility is recomputed from outputs under the same question and
explicit reference bands. Any unresolved/failed/incomplete selected verification
or budget overrun yields ABSTAIN and no recommendation, while retaining completed
reference observations. A reference or infrastructure failure is never charged
as a candidate scientific failure. Model-infeasible designs are different from
model scientific ineligibility. No hard constraint is compensated by objective.

The native ledger admits work against explicit complete-call bounds. The wrapper
measures in-process elapsed wall and process CPU seconds, includes its constructor,
supplied external startup costs, dispatch, measurement and audit assembly, and
records every Guard/model/reference call. Import/model startup and caller-side
I/O must be supplied in `startup_cost`; there is no zero default. Serialization
and transport after the returned object are caller-owned. Assessment has its own
explicit budget and separate spend, never free oracle access in search.

Pre-call admission reserves the Guard's configured worst-case model-call count.
Insufficient quota defers work before execution. A trusted call that exceeds its
time/core planning bound is charged, retained and stops further work; no action
is recommended. The wrapper cannot preempt a running Python callable and does
not measure other-process/GPU costs. Those need a separately accepted metered
adapter and isolation. This API is for trusted in-process CPU adapters only;
PUBLIC_RECORD_REPLAY is explicit and never called a fresh solver execution.
Its observations can support replay diagnostics but cannot produce a verified
recommendation, a verified order or completed fresh-reference assessment.

## Outcomes and independent assessment

`carbon.product.assistant-result.v1` retains question/budget/artifact/runtime/
Guard/measurement identities, all candidate dispositions, provisional and verified
orders, verification plan, pre-reference commitment, spend, adverse observations,
expected-regret evidence/gap and a timing-separated audit digest. Qualification
and production authority are always false. A reference-relative choice remains
DEVELOPMENT advisory. Equal replay inputs can reproduce a decision; measured
budget exhaustion is host/workload-dependent and is part of the result.

PB-INV/ADV evidence counts false feasibility **on selected picks**, retaining
selected/resolved/unresolved denominators. A partial resolved fraction is labelled
conditional, never a complete-population safety estimate. A Guard TRUST does
not remove a selected pick from this assessment.

`assess_finite_bank` is separate post-freeze reference work. It rechecks declared
reference envelope/physical applicability even for unselected bank members and
charges its own calls. Realized regret is available only when the entire declared
bank resolves and the delivered choice has a feasible reference value. Its oracle
is that finite bank, never a global optimum. NONE_FEASIBLE is established only
on complete resolved bank evidence; incomplete or failed evidence stays GAP.
It does not establish expected regret on a question population or qualify a product.
An assessment callback cannot remove a reference hold frozen into the searched
workflow or its Guard record. Changed acceptance requires a new configured run;
the original result stays attributable to its original authority. Assessment
receipts also bind the supplied reference's exact image, record and runtime.

## Demonstration and the real battery hold

```text
python -m carbon.product.decision_assistant.demo
python -m carbon.product.decision_assistant.public_panel <explicit-public-copy-directory>
```

The runnable demo uses the public battery I/O shapes and native voltage-crossing
observer, with deliberately optimistic **synthetic** temperature predictions,
fictional limits/policies/references and no trained model or physics solve. It
selects two false-feasible picks, including a TRUST pick; independent arithmetic
references reject them and select the feasible slow design. Expected regret is
null; separate complete synthetic finite-bank assessment gives realized regret.
The native equal-budget replay uses clearly assumed costs and replicated toy
band shapes; at its smallest budget the Assistant's first pick is infeasible
while solver-only finds a feasible pick. The adverse curve is retained. These
are workflow tests, not actual battery v3/value/latency evidence.

The owner authorized an explicit read-only copy at
`codex-queue/inputs/physics-calibration-01/`, manifest SHA256
`7d4529df11998aadb6c16f6d87fcccde64fe24009aed1089f6959c8f1e31785b`.
The inspector reads only MANIFEST.json and records.jsonl, checks exact file/line
hashes and every row's image/overlay/version, and emits aggregates only.
The local queue/input files are not copied or committed.

**Owner clarification in this Product chat, 2026-10-12:** proceed with Assistant
and synthetic tests; no complete public reference export exists. This image is
not accepted for the real battery comparison and CPU core-seconds are missing.
The emitted summary therefore says SOLVER_NOT_ACCEPTED, `accepted: false`, null
CPU cost and null real regret. Historical manifest/MMS acceptance text cannot
override that current use-specific hold. Recorded wall_s may support only a
DEVELOPMENT cost estimate; peak RSS and elapsed time never become CPU core-seconds.
Source identity and code verification remain separate from current-use reference
acceptance, physical validity and qualification. Real battery validity is still
Undeclared. No protected, hidden, sealed or private material is accessed.

## Validation and remaining authority

```text
./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_product_decision_assistant.py tests/cpu/test_product_envelope_guard.py tests/cpu/test_design_search_equal_budget.py tests/cpu/test_design_search_verify_aware.py
```

Native-host tests are diagnostics. Use the pinned GitHub acceptance when the
local canonical wrapper is unavailable; do not repeat failed Docker attempts.
Tests exercise selected-pick false feasibility, TRUST verification, reference
holds and failures, unsupported queries, incomplete oracle/regret, independent
budgets and overruns, immutable replay, exact evidence binding, public source
tampering, no query-path I/O and Guard v2 map compatibility.

Scientific/population/measurement policy, real reference acceptance, complete
real cost metering, runtime parity, PB-INV/ADV/ART/LAT/ESC adequacy, production
latency, audit retention/disclosure and customer rights stay HUMAN_INPUT.
The package earns implementation/test maturity only. Carbon Validator and Data
Collection are the review routes; code awaits named review before merge. PR
Head/owner owns merge. Hub retired; Product queue stops after this handoff.
