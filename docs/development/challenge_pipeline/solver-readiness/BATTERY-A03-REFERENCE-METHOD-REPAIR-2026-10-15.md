# Battery A03 reference-method repair, 15 October 2026

## Approved implementation update

Ryan approved the complete guarded DEVELOPMENT protocol in Test Lead. The
direct-human approval receipt SHA256 is
`e4a7dd4d8f51e3aaac38d75d5e763dfbc6061cc59715d65a3bdad94e3c8c4696`.
It binds the reviewed document at immutable commit `d208997dc`, SHA256
`fc731a4ad5f5a700d0855f5763dce9f73b09fe2646f92fdc6988c0711b16e123`.
The historical proposal below retains its original pending-status wording;
this update prospectively supersedes that status only. The original failed
A03, old390TRAIN rows and18fits remain unchanged.

Implementation in `scripts/dev/battery/guarded_reference.py` provides a new
protocol ID `carbon.scorelab.battery-v3.guarded419-protocol.v1`, observer ID
`carbon.scorelab.battery-v3.guarded419-full30-observer.v1`, dataset ID
`carbon.scorelab.battery-v3.guarded419-first-T5-h1.v1` and guarded binding/receipt
schemas. Legacy jobs still command4.2V. Only the exact three new T5/h1 jobs
opt into4.19V; the pinned release's existing legacy experiment-model mode is
made explicit on that path. Old source/task/numerical-policy/export semantics
are not silently migrated.

The prospective N1 context is
`carbon.scorelab.battery-v3.guarded419-n1-context.v1`, explicitly UNBOUND until
matching-protocol data and a separate consumer binding exist. The first-triple
binding cannot make old TRAIN rows/fits compatible or produce an N1/EVAL release.

The active CV-mode witness is the actual Current-variable equation in
`model.algebraic`, structurally matching processed Voltage minus the actual
target, plus its measured residual. The pinned legacy setup merges equations
without updating the original `model.submodels` circuit object; that object's
class/control is retained only as a diagnostic. Positive and negative tests
exercise the actual extraction function with that stale dictionary, an RHS-only
equation and a different equation whose residual happens to be zero.

The existing `feasibility02 solve --calibration-binding ...` durable collector
handles both versioned paths. The new schema requires all nine source hashes,
new observer/method/data identity and exactly the first triple before workers
start. Each returned row is preserved before the real tracking checks and
unchanged five-quantity numerical checks are conjoined. A raw OK solve can
therefore yield REFERENCE_UNRESOLVED. Only a compatible guarded first-triple
receipt is possible; full-calibration/EVAL/N1 release flags remain false.

Root materializes `guarded_reference.inputs()` and
`guarded_reference.execution_binding(source_commit=EXACT_PUSHED_COMMIT,
source_files=ACTUAL_NINE_FILE_SHA256_MAPPING)`, records the exact binding byte
SHA256, and uses that same binding/command path. Source hashes are the exact
`REQUIRED_SOURCES` set, including the new helper. This builder performs no
dispatch. Include `scripts.dev.battery.guarded_reference` in the pod's shipped
modules and re-freeze any changed payload manifest. Root independently checks
actual clean source/commit, image/overlay, mode/lease, two aggregate CPUs,
45-minute deadline and USD2 reservation from the existing shared grant.

Root owns all application tests, actual source interoperability, paid dispatch
and merge. Author-side evidence here is source/static only until actual CI
returns. First paid validation remains only the approved new T5/h1 triple.

## Historical reviewed proposal at d208997dc

Engineering: additive diagnostic source and synthetic controls prepared, not
tested. Science: original A03 remains NUMERICAL_CALIBRATION_INADEQUATE /
REFERENCE_UNRESOLVED. The recommendation below is not adopted and changes no
execution behavior.

## Actual failure and exact source

At source `3ee7144aa0bd35b0f693d9a154e07bea553eff29`, the first T5/h1
calibration tuple completed all30cycles on meshes20/40/80. Whole-programme
maxima were4.200000000000250,4.200000000000342 and4.200000000000225V,
all at CC2 endpoints. CV also has small signed residuals around4.2. The
unchanged strict raw-max check correctly refuses them. Fifteen offered jobs
were NOT_DISPATCHED. Phase summaries cannot exclude missed interior extrema
or authenticate the terminal event; original full trajectories/states were
not retained.

Immutable public SHA256 identities:

- Records: `5d923ae443e18fd60e1ec612b23c67c4634b5c52c1c3809f6d05be97c2956c3c`.
- Stop receipt: `32110295581964e988f48038bfe17d0243e3f12f43327133eedfa3c5eae13e4a`.
- Collection: `e1d59fab3b86dec909c30eac9c9baaec562ac54bb419360f95d4c031c505e2b6`.
- Research diagnostic: `6fc3757c926559b2fd2ae0bfa729a50a1d7a815c8d92f9554d900fb6ba398188`.

The pinned public PyBaMM26.8.0.0 wheel was downloaded, SHA256-verified as
`b5977b7867f7159d2a3fe84fe1669ef9ae36312cfe234daf4681569a5c960289`, and
read as ZIP source without install/import/execution. Seven selected members
match release-tag commit `79fb27f190d2be468bec704f735ade20389dd93a`;
idaklu_solver.py, base_solver.py and solution.py also match actual installed
source hashes captured in A03. The other four members were not hashed by that
historical run. This is not loaded/native/transitive dependency attestation.

Pinned source under `packages/pybamm/src/pybamm/` establishes:

- VoltageTermination on charge evaluates `-(Battery voltage [V] - target)`.
- VoltageFunctionControl adds algebraic `Voltage [V] - Voltage function [V]`.
- IDAKLU root_tol/root_method control initial-condition consistency, not event
  voltage accuracy. closest_event_idx is the smallest absolute event residual;
  the library termination label is not an independent root certificate.
- IDAKLU retains terminal state with output_variables, but also populates
  terminal time on final-time returns. Presence of t_event is not an event.
- Output-only storage disables retained Hermite interpolation. Finite sampled
  extrema and local WRMS error controls do not certify a continuous one-sided
  physical-voltage bound.

Primary source: [exact PyBaMM release](https://github.com/pybamm-team/PyBaMM/tree/79fb27f190d2be468bec704f735ade20389dd93a/packages/pybamm/src/pybamm).

## Engineering repair prepared

KEEP equations, programme, solver settings, all old extrema/statuses and the
calibration reduction. Each of181actual steps, including initial rest, gets:

- Its actual flattened Experiment.steps descriptor, control kind/value/direction
  and termination definitions, independently of the phase label.
- Original-order all-point and strict-interior extrema, first/penultimate/
  terminal voltage/time, and paired-array SHA256. No rounding, clipping,
  sorting or removal from the existing maximum. These summaries and hashes
  do not retain the full trajectory.
- CV signed Voltage-minus-actual-target extrema/counts over all recorded
  samples, explicitly distinguished from a full DAE residual certificate.
- Per-step termination, terminal time/state count/hash, every termination
  expression reevaluated at that state, cell and battery terminal voltage,
  actual circuit class/control and terminal current-control equation/residual.
- Explicit unavailable/malformed/nonfinite states and selected installed
  event/control source hashes. Record actual runtime series-cell count; never
  assume Battery voltage equals cell voltage. No acceptance flag or replacement Vmax.

Synthetic controls cover terminal roundoff; large interior overshoot with
zero terminal residual; gross CV error; wrong target/direction/event; final-time
return with a terminal state; malformed times/state; all30cycles and a
noncontrolled-phase overshoot; and unchanged strict calibration refusal. The
tests are written, not run. Root owns validation after actual MAIN closure.

## One preferred prospective recommendation

**Recommend a separately versioned guarded charging programme: command CC2
cutoff and CV hold at4.19V, retaining the exact hard4.2V limit on the unchanged
recorded whole-programme maximum.** Keep CC1/switch, C/20 cutoff, all30cycles,
rests/discharges, other task limits, DFN/OKane2022, cooling, meshes20/40/80
and solver tolerances unchanged.

This requires owner/domain adoption as an explicit controller design change.
It is not an extraction fix or numerical error allowance. The proposed10mV
headroom separates a commanded operating point from the hard maximum; it is
not derived from rtol/atol or observed residuals and is not a certified error
bound. A commanded equality boundary has no numerical headroom; a guarded
programme retains an ordinary raw measurement and strict comparison. The
exact10mV remains an experimental design recommendation, not a source-derived
physical fact or claim of optimal/sufficient headroom. Only actual prospective
results may satisfy the existing numerical checks. They still do not establish
hardware safety or a continuous physical bound.

The same prospective recommendation includes an explicit **target-fidelity
criterion of1e-6V**, separately registered with the programme. This is a proposed
DEVELOPMENT numerical criterion on the existing voltage-pair reporting scale,
not a source-derived error certificate, hardware tolerance or allowance above
the hard4.2V maximum. Its numeric value requires owner/domain adoption too.
Before a new guarded-protocol triple can count as compatible, every cycle must
satisfy all of the following in addition to unchanged calibration checks:

1. Exact source/control/target/termination identities, all30cycles and every
   phase, ordered finite nonduplicate samples, actual terminal-state evidence
   and actual runtime series-cell count1. Missing/different/ambiguous evidence
   means REFERENCE_UNRESOLVED. Source bytes alone are not a state certificate.
2. Each CC2 ends at the expected charge voltage event with target4.19V; its
   signed event residual has absolute value<=1e-6V, the last sampled time equals
   the terminal-state time, and independent terminal Voltage and Battery voltage
   evaluations agree with the sampled terminal voltage within1e-6V.
3. Every CC2 strict-interior voltage and its first sample are <=4.19+1e-6V.
   A spike at4.195V followed by a perfect4.19V endpoint fails target fidelity
   even though it is below the physical4.2V maximum. Do not discard that sample.
4. Each CV uses the authenticated algebraic voltage-control relation with
   target4.19V and expected current-cutoff termination. Over every recorded CV
   sample, max(abs(Voltage-4.19))<=1e-6V. Its actual terminal current-control
   equation must be the selected voltage relation and its signed residual
   <=1e-6V in absolute value. Wrong mode/target/event is unresolved, never
   inferred from the phase label or a small residual of another equation.
5. The original unmodified whole-programme maximum, including all endpoints,
   CV samples, rests and discharges, must still be <=4.2V exactly. Keep the
   original pair-change1e-6V and four-quantity adequacy rules too. There is no
   added epsilon on that physical guard and no reinterpretation of the old run.

A consistently wrong4.199V CV trajectory at command4.19V must therefore fail:
its9mV target residual is above the proposed1microV fidelity criterion despite
raw Vmax<4.2V and perfect cross-rung agreement. The prepared diagnostics expose
this negative control; no target-fidelity acceptance code is enabled here.
This finite-sample criterion still does not certify unobserved interior peaks
or continuous physical compliance; it is a bounded operational model study.

Do not silently adopt an event-defined setpoint as the old measured Vmax.
The API provides no one-sided certificate, and finite residual alone could
accept a grossly incorrect CV solution. Do not clip/drop samples, add a posthoc
epsilon, repeat unchanged solves hoping for a favorable residual sign or sweep
meshes. A validated one-sided DFN integrator is a different project, not a
bounded PyBaMM setting repair.

Adoption must prospectively version the reference programme/question-law
binding and observer/method/source identities. Retain the old failed records.
Existing390TRAIN rows and18fits using4.2-command labels belong to a different
protocol. Preserve them; do not discard, relabel or silently mix them with
4.19-command truth. Existing N1 source and fits can proceed independently;
use with the amended protocol needs an explicit compatible data/measurement
binding before release. They are not automatically matching new-protocol
TRAIN evidence; additional compatible data or an explicitly identified transfer
study may be needed. No change to the
hard4.2V threshold is recommended. Current code has no4.19behavior.

Smallest owner decision: adopt or reject the complete4.19V commanded programme
and explicit1e-6V target-fidelity criterion for a newly identified
PUBLIC_DEVELOPMENT reference, with unchanged4.2V raw guard and all stated
identity/coverage limits. Rejection leaves the scientific path unresolved;
additive diagnostic engineering can still ship. Research independent critique
and adoption are pending, not implied by software tests, assignment or silence.

## Minimal validation and release boundary

After critique, explicit adoption, implementation and Root's actual MAIN
checkpoint closure, Root binds exact new source/method/inputs and a fresh
bounded reservation. First paid validation is only the same original physical
tuple (c1=1.25,c2=.40,switch4.00,T5,h1,soc0=.1), all30cycles, meshes20/40/80,
under new prospective case identities distinguishing the amended protocol.
No later cases are released in advance.

Require expected event/control identities, ordered finite phase coverage,
raw interior/terminal/CV/noncontrolled extrema and actual residual evidence
at every rung. Missing evidence stays unresolved. Apply unchanged hard
raw-max4.2V, voltage pair-change1e-6V and registered four-quantity cross-rung
adequacy checks under the prospective binding. If inadequate, retain failure
and stop. Only actual compatible results may release later registered cases
under Root's grant. Full calibration, EVAL and N1 retain complete-stage gates.
