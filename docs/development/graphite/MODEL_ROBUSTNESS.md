# Model-input robustness probes (PKT-18)

DEVELOPMENT evidence component, not a certificate, security audit, commercial
product or qualified exam. No solver, training, paid compute, protected cases
or real participant execution is performed in this ticket.

## Inventory correction and reuse

The queue's assertion of zero residual/conservation-related matches is false:
`carbon/challenge_validator/physics_contract.py` implements single/pair residuals
and reference calibration, and `carbon/product/envelope_guard/core.py` applies
adopted/advisory probes with explicit applicability. These are retained, not
reimplemented. Existing L4 families target construction/submission, not trained
operators subjected to geometric and mesh hostility. That narrower gap remains.
Physical invariance is a separate **gate** programme (PKT-19), not a score leg.

## Primary-literature basis (not Carbon thresholds)

[Adesoji and Chen, 2022](https://arxiv.org/html/2204.04259v1) evaluate FNO with
white-box norm-bounded input-field PGD, 10 steps and 10 restarts, perturbation
levels 0.01 to 5, and average MSE over 100 examples. They describe Burgers/Darcy
MSE rising roughly 80%/50% faster than perturbation level, versus about 40%
slower for Navier. These are paper-specific curve descriptions, not a portable
error multiplier or acceptance threshold. Their closest-field reference
approximation for Burgers/Darcy also limits interpretation. Carbon needs a
matched reference for the **actual perturbed input**, not unperturbed truth.
Field perturbations motivate sensitivity tests but do not prove geometric or
mesh robustness. This ticket implements bounded geometric specimens, not PGD.

[Li et al., Geo-FNO, JMLR 2023](https://jmlr.org/papers/v24/23-0064.html) make
geometry/input representation explicit: deformation into a uniform latent
domain supports point-cloud, mesh and design-parameter inputs. Their reported
speed/accuracy benefits concern their datasets and do not establish adversarial
robustness. This supports testing geometry separately from discretization;
it supplies no universal safe deformation radius. Literature informs proposed
families; Validator/owner sets applicability, perturbation law and thresholds.

## The first grammar and what radical means

The executable initial grammar is **2D oriented triangle meshes**, generated
from a public unit square. It is not a complete CAD/3D/tetrahedral grammar or
a claim that every launch Challenge consumes such meshes. Models receiving
only scalar design coordinates must declare this grammar unavailable; they
earn no mesh/geometry coverage. A future coordinate-to-CAD route needs its own
registered input translation and witness.

`grid(n, irregularity=...)` deterministically remeshes; `deform` applies affine
stretch/shear while retaining node correspondence. `corrupt` creates repeated
vertices (zero area), inverted orientation or an out-of-range index. A denser
grid tests the host's **declared** supported-node bound. Irregularity and grid
sizes in the demo are fixture numbers, not adopted physical policies.

Radical displacement = maximum corresponding-node Euclidean displacement /
baseline bounding-box diagonal. The policy's `radical_displacement` is
HUMAN_INPUT by default; an effect smaller than it (or zero) is NOT_RUN, not
coverage. Remeshing has no corresponding displacement and is judged in the
mesh family instead. Report node/cell counts, node ratio, minimum signed area,
degenerate/inverted counts and invalid connectivity alongside effect size.

The explicit support projection has coordinate bounds and a node count, plus
the supplied oriented-connectivity validity rules. It is **not** a full
physical applicability classifier: holes, disconnected bodies, overlapping
elements, topology changes, manufacturing and nonlinear material support need
additional host grammar/applicability checks before any real run. No present
Challenge envelope is replaced by these rectangular fixture bounds. Extreme
deformations outside a declared envelope require honest refusal, not accuracy.
An in-envelope but unseen deformation requires its own matched reference.
Whether a public input was actually unseen in training is host custody evidence;
the generator cannot establish novelty from a name or seed.

## Boundary API and decidable verdict

Import `Policy`, `Boundary`, `Witness`, `Mesh` and `probe` from
`carbon.agent_campaign.attack.model_robustness`.

- `Policy` binds Challenge, policy reference, support bounds/node bound,
  radical displacement, maximum absolute nodal error tolerance and its unit.
  All missing scientific values stay null/HUMAN_INPUT; no fallback science.
- `Boundary` binds Challenge and asserted artifact/runtime digests, a declared
  capability set and a **trusted host callback**. The callback receives a fresh
  `{nodes, cells}` payload and returns exactly `{status, values, reason}`.
  PREDICT carries one finite scalar per node; REFUSE/ABSTAIN carries no values
  and a nonempty reason. A caveat attached to PREDICT cannot disguise refusal.
- `Witness` binds the actual mesh digest, nodal scalar values, unit and reference
  identity. Same node count alone does not match a reference. Missing/mismatched
  witnesses prevent execution and remain a reference/evidence hold.
- The same `probe` runs valid control, known-bad predictor on the attack, then
  actual predictor on the attack. The negative artifact must be distinct;
  both control results remain visible even if an actual attack breaches.

| Situation | Per-attempt result |
| --- | --- |
| Explicitly no input capability | NOT_APPLICABLE, zero calls/coverage |
| Unknown capability, missing policy/reference or insufficient measured effect | NOT_RUN, zero coverage |
| Outside envelope/resource support or invalid element: honest refusal | HELD only with both discriminating controls |
| Outside support: confident PREDICT, including an apparently accurate value | BREACHED (no outside-envelope accuracy obligation is imposed) |
| Supported input: prediction within the matched witness tolerance | HELD only with both controls |
| Supported input: wrong/nonfinite/malformed prediction or refusal | BREACHED |
| Actual endpoint infrastructure failure, timeout or exception | FAILED_INFRA / TIMEOUT / CRASHED, not a scientific finding |
| Supported valid control is wrong or wrongfully refused | BREACHED; attack/control findings remain independently visible |
| Valid control endpoint is incomplete or negative predictor is not detected | INCONCLUSIVE, never HELD |

This is an answerability/accuracy diagnostic, not physical validity, decision
regret, score or admission. The absolute nodal witness metric is a first bounded
output contract; vector/curve outputs need explicit units/alignment rather than
being coerced into it. Refusal on supported controls cannot be a universal
robustness strategy. All-control/all-attack evidence is retained independently.

## Identity, safety and incomplete coverage

Input/policy/witness/artifact/runtime/negative pins are computed before callbacks.
The record digest binds verdicts and measured basis. Calls receive independent
copies, so mutating one payload cannot rewrite later roles or stored input pins.
Only aggregates and hashes are returned, not geometry, outputs or exception
strings. There is no automatic telemetry, file load, publishing or state write.

Pins are **host assertions, not authentication or attestation**. A callback can
lie about its artifact. HOST_DECLARED_PUBLIC does not turn a supplied witness
into a verified reference. The demo uses SYNTHETIC_FIXTURE and cannot claim
trained-model evidence. This component never installs or executes miner code.
Transport allocation bounds are engineering limits, not scientific support.
Timeout classification is not timeout enforcement. Real proxy execution must
run through the existing isolated host service with memory/process/time limits,
authentic rebuilt artifact parity and matched reference-use acceptance.

Campaign/Graphite integration is deliberately not fabricated: #1317 owns shared
`attack/adapter.py`, `verify.py` and `battery_level4.py`. Until the named lane
integrates the model route, this is **not a registered L4 family**, counted gate,
claim of all-model coverage or real-host pass. The host must retain public-only
unseen panel identity, predictor artifact, policy and full independent witnesses;
no official hidden EVAL/STRESS/quiz/tuning material is supplied here.

## Replay and next actual evidence

```text
python -m carbon.agent_campaign.attack.model_robustness_demo
./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_model_robustness.py tests/cpu/test_attack_engine.py
```

Seven fixture attempts demonstrate both families, including supported stretched
geometry and irregular meshes requiring a numerical predictor response. Known
bad constant output fails; always-refuse and a silent detector cannot pass.
These are public engineering tests, **zero rebuilt trained models attacked**.

Next: Validator supplies grammar/application scope, radical threshold and
matched-reference tolerance; host supplies an authenticated isolated proxy and
public unseen witness panel. Run on a known-bad **actual trained** operator and
a valid rebuilt control before interpreting any real robustness result. Launchpad
projection/customer claims await named owner decisions. No new owner spend ask
is required to review the engineering component.
