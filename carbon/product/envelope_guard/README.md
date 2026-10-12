# Envelope Guard — PRD-02 development contract

The Guard checks a trusted local model adapter against an explicit development
contract, surrogate envelope, native trust-map aggregate and declared policy.
Every query returns TRUST, VERIFY or REFUSE, reasons and a local receipt.
These are DEVELOPMENT advisory verdicts. This package cannot issue product
qualification, production TRUST, scientific scores or LIVE authority.

Construction validates closed data shapes, finite values, units and exact
artifact/runtime/contract/envelope/map/reference identity bindings and snapshots
the configuration. Raw mathematical strings are never executed. The model is
a trusted host-supplied callable; this wrapper supplies no hostile-code sandbox.
Content hashes and source references do not authenticate scientific acceptance
or establish that the callable matches its claimed artifact.

The initial Guard-owned development contract projection supports `bound`,
`initial_condition` and `prefix_invariance`. It does not replace PLT-01 or
adopt the packet drafts. Every verdict law needs ADOPTED status, an adoption
reference, an exact-image calibration record and a tolerance in the observable's
units no tighter than its registered reference error. Unadopted laws are listed
as diagnostics. Unsupported adopted laws refuse construction; missing human
policy prevents TRUST. Source drafts remain definitions, never adopted gates.

The reference route is separate from the surrogate envelope. VERIFY requests
independent reference work only inside that route's declared applicability;
the Guard never invokes it. Unknown or unavailable reference applicability
gives REFUSE and preserves FAILED_REFERENCE / FAILED_INFRA. Out-of-envelope
surrogate calls are avoided. No failed reference is charged to the candidate.

Local query probes are deterministic functions of query, complete policy/version
and contract using a domain-separated SHA-256 counter. Steps and model-call
budget are explicit policy inputs. The receipt includes the derivation and
query/probe/configuration identities. It contains no official entropy and the
library writes no logs, performs no network or filesystem I/O and sends no
telemetry. Audit retention and disclosure remain HUMAN_INPUT.

Native `carbon.trust-map.v1` cells retain their units, empirical pooling and
NO_DATA semantics. Cell support/error/disagreement thresholds come from the
explicit policy, never defaults. Absent or insufficient cell evidence and
unresolved mandatory probes cannot become TRUST. Calibrated intervals, when
available, are checked under the declared policy; missing uncertainty remains
GAP and follows the explicit no-interval/required-interval policy.

Assistant-selected candidates still require independent solver verification.
Pooled map error and a Guard TRUST label never certify selected-pick feasibility,
regret, safety or physical validation. PRD-03 must measure selection pressure
through PB-INV/ADV and keep provisional and verified choices separate.

Battery demonstrations reuse public input/output shapes, with synthetic toy
predictions and synthetic map/policy/calibration records only. Main's actual
battery validity is Undeclared; this package preserves that hold. No real model
is trained or solver run, no protected material is read or produced, and no
scientific value is selected. Public benchmark results will report full-query
overhead, model calls, host/runtime and limitations.

**Production latency target: HUMAN_INPUT (null).** The owner must set the
accepted PB-LAT use/device target. Toy timing is engineering evidence about
that adapter, not a production latency promise. Scientific tolerances,
applicability, trust thresholds, probe budgets and uncertainty/acceptance rules
likewise require their owners before real product use.

Plan: native baselines → validated development projections/native map wrapper
→ deterministic per-query verdicts → public-interface fixture regressions
→ bounded overhead benchmark → exact-head CI → named-review PR handoff.
KEEP D01–D11/Q0–Q8 and PB-ESC/ART/LAT authority. Hub is retired.
Reviewer: Carbon Validator, plus Data Collection. Guard code awaits named review
before merge; PR Head/owner handles that gate. The Product queue stops here.

## API and records

PRD-03 compatibility note: native maps now use `carbon.trust-map.v2` and carry
the registered code-verification acceptance-link receipt. Guard construction
revalidates that receipt against the current registered public source bytes.
The prior v1 arithmetic fixture is isolated to SYNTHETIC_FIXTURE policy, or a
missing policy that can only REFUSE; REGISTERED_DEVELOPMENT cannot use it.
The demo builds plain synthetic cells rather than invoking an accepted-solver
map producer with a fake image. A historical code-verification link cannot
override a current product-use solver/applicability hold. The PRD-02 latency
record preserves its original implementation byte hashes and is historical
evidence, not a fresh measurement of the PRD-03 composition.

```python
from carbon.product.envelope_guard import EnvelopeGuard
from carbon.product.envelope_guard.demo import fixture_inputs, QUERY, UNITS

# SYNTHETIC interface demonstration only; no real battery policy or model.
guard = EnvelopeGuard(**fixture_inputs())
receipt = guard.evaluate(QUERY, units=UNITS)
```

`ModelBinding(model_id, artifact_digest, runtime_digest, predict)` wraps the
trusted adapter. It returns `Prediction(outputs, intervals=None)` with exactly
the contract's outputs. Scalars are accepted only for length-one outputs;
receipt predictions are normalized vectors. `development_pins(...)` produces
the exact content identities for policy authoring. Changing a configuration
requires a new Guard; it cannot be replaced by query arguments. The constructor
snapshots documents, validates them, and stores frozen configuration values.
Malformed or incompatible configuration raises a fixed-code
`GuardConfigurationError`, with no source or exception-content echo.

| Input | Development schema and required semantics |
| --- | --- |
| Contract | `carbon.product.guard-contract.v1`: version, challenge, reference_image, output names/lengths/units and laws. Each law has id/type/status/spec/adoption_ref/calibration. Bound specs name output/low/high; initial_condition names output/input; prefix_invariance names output/inputs/points. The prefix count excludes later grid points as declared by that contract, never a guessed switch time. |
| Envelopes | `carbon.product.guard-envelope.v1`: separate surrogate and reference documents, each with version and scalar input low/high/unit. These are support records; physical validity remains separately supplied. |
| Physical declarations | Native `Declared`, `Undeclared` or `NoPropertyModel` from `carbon.challenge_validator.validity`. Every declared observation must be present in the query. Output-dependent applicability needs a separately accepted observation adapter; it is not inferred from the model. |
| Reference | `carbon.product.guard-reference.v1`: image_digest, separate code_verification_ref and owner_acceptance_ref, and READY/UNRESOLVED/FAILED_REFERENCE/FAILED_INFRA. It is metadata, not a reference executor. Missing acceptance refs refuse configuration; a missing route or failed route refuses a query. |
| Map | Native DEVELOPMENT `carbon.trust-map.v1`, PUBLIC/RELEASED source and matching model/reference; complete grid and aggregate denominators, native units and NO_DATA checked. Coverage can be smaller than the surrogate envelope; an uncovered query needs verification. No interpolation of empty cells. |
| Policy | `carbon.product.guard-policy.v1`: version, SYNTHETIC_FIXTURE/REGISTERED_DEVELOPMENT basis, authority_ref, exact pins, probe_steps, max_model_calls, min_cell_count and per-output error/disagreement limits in native units. Every quantitative decision is an explicit input. No policy or null authority_ref yields REFUSE. |
| Uncertainty | Explicit EXPLICIT_NO_INTERVALS/REQUIRED policy, nullable image-bound calibration and per-output width limits. Supplied intervals must bound the point prediction; available uncalibrated intervals, missing required intervals or excessive width yield VERIFY. This does not perform an independent calibration study. |

Every projection above has `scope: DEVELOPMENT`; production/LIVE scope is
refused. Adoption/calibration references are host-provided record assertions,
not authenticated signatures or permission to manufacture a scientific value.
Current packet drafts do not match the adopted development projection and are
not executable Guard contracts. The `demo` module is an explicit fixture
authoring example; it is not a source of real adoption, calibration or validity.

Receipts contain reasons, check outcomes and evidence basis, all configuration
identities, normalized provisional prediction, model-call/observed-probe counts,
seed derivation, query/probe digests and `decision_digest`. The latter excludes
elapsed time and latency reporting so a deterministic adapter can replay the
same decision. Fixed probes do not qualify the adapter's own reproducibility.
An interrupted budget or failed model call has visible incomplete evidence.
No raw query or probe-coordinate list is automatically logged or published.

Run the focused interaction suite with the canonical wrapper when available:

```text
./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_product_envelope_guard.py tests/cpu/test_trust_map.py tests/cpu/test_validity_envelope_rule.py tests/cpu/test_customer_deliverable_generator.py
python -m carbon.product.envelope_guard.demo --iterations 500
```

Native host tests and the [toy timing record](../../../docs/development/product/envelope_guard/latency-fixture.json)
are diagnostics. Required exact-head CI supplies engineering acceptance.
The timing record binds the implementation bytes used, preserves the null
production target and counts the full query, including its model calls.
Actual model/runtime parity, law/probe/map-policy acceptance, physical evidence,
PB-INV/ADV composition, PB-LAT target and scientific/security/product
qualification remain separate owner work.
