# Ready-to-run DEVELOPMENT comparators

CHEAP-BASELINE-COMPARATORS-01, main starting identity
`65ef88660fe02018c26f54d14655fe7b66354aa8`. Implements #864's method proposals;
does not adopt a new question or earn V4. No solver, spend, protected material,
AX42 discovery, bank construction, score or power changes.

## One command per eligible return

```sh
python -m carbon.development_comparison.portfolio_baselines \
  --panel PUBLIC_DEVELOPMENT-panel.json --expected-sha256 PANEL_BYTE_SHA256 \
  --materials PUBLIC_DEVELOPMENT-materials.json --materials-sha256 MATERIAL_BYTE_SHA256 \
  --output new-report.json
```

The producer supplies explicit files and their independently checked byte
identities. The output must not exist. Neither this command nor its imports
launch a solver. It reads no search roots, network or protected data. Its
environment reports `canonical: false`; run it in the canonical environment
for accepted acquisition evidence. Native toy execution is only a diagnostic.

The panel remains the closed
`carbon.design-search.solved-panel-export.v1`, including complete runnable
tasks, physical actions, quantity units, frozen candidate order, observers,
objective/limits, P/Q/w and existing reference-resolution evidence. Ordinary
non-indexed tasks are supported here; an indexed f02 schedule needs a future
adapter and is refused, not silently flattened. Motor and indexed battery
continue using #917's command.

## Companion material contract for Data Collection

### Optimizer equal-budget handoff

The report now includes `equal_budget_screening` (schema
`carbon.development-cheap-screen.v1`) for EQUAL-BUDGET-DESIGN-01. Each
`query_rows` entry identifies the physical candidate/condition, prediction or
abstention, measured CPU/wall `query_cost`, and separate `fit_cost` (including
context preparation). A query produces the whole registered observable vector;
it is not a design question, frequency, scalar output or reference solve.
Query time includes method evaluation, reduction and finite-output checks but
excludes fitting, witness diagnostics, loading/validation and process startup.
Unsupported queries retain attempted cost. A failed fit has null query cost,
not a free successful query. Totals, means and wall p50/p95 report denominators.

`candidate_rankings` is one list per registered question: predicted-feasible
and predicted-infeasible candidates, each sorted by the task's objective,
secondary objective and frozen candidate order; incomplete/unsupported designs
are unranked. Objective/secondary values retain buyer units and task identities.
Only comparator point predictions enter this ranking, never reference verdicts
or repaired values. Point-predicted feasibility is **not** a safety certificate
or a qualified uncertainty interval. Any conservative screen needs its own
registered policy; the optimizer must not silently relabel this one.

This is a held-out **measurement export, not an equal-budget workflow run**.
Fold fitting is repeated for validation and is not a single production-model
training cost to amortise. Both export/material digests bind the rankings and
timings; the original export supplies exact candidate actions. Threshold-only
questions can reuse observable predictions, but requirement aggregation and
ranking have their own measured cost. Optimizer owns query/verification budgets,
full process costs, fitting amortisation and a matched Carbon arm. Acquisition,
verification, RAM and money remain separately measured or null. Synthetic
timings are implementation diagnostics, not forecast deployment costs.

Use `seal_materials(body)` after preparing this closed shape. Hashing binds
identity, not truth, rights or independent custody.

| Field | Required content |
| --- | --- |
| `schema`, `family`, `scope` | `carbon.development-comparator-materials.v1`; one of cooling-cell/f02/f08/f13; PUBLIC_DEVELOPMENT or SYNTHETIC_FIXTURE only |
| `export_digest` | The neutral export's identity; no mixed observers or historical contracts |
| `observer_versions` | Sorted unique task observer versions, exactly matched |
| `settings.coordinate_fields` | Ordered numeric physical registered-action fields; never candidate IDs. Include the complete geometry for cooling, complete waveform action for f02, complete cache/geometry action for f08/f13. Hold out all matching coordinates across sibling conditions |
| `settings.lags` | Fixed before measurement, integer 1–128; used only by f02, not selected on held-out error |
| `settings.reducers` | Rows `{quantity, unit, kind}` covering every objective and hard limit. Quantity/unit must match the task. No threshold inferred from family |
| `rows` | Exactly one row per deduplicated physical candidate/condition, not one per threshold question |
| `costs` | `original_acquisition_cpu_s`, `reference_refinement_cpu_s`, `retained_verification_cpu_s`, `peak_process_ram_bytes`, `money_eur`: measured nonnegative numbers or null. Include failed acquisition work; no absent cost represented as zero |

Every material row contains exactly `candidate`, `condition`, `coordinates`,
`context_sha256`, `reference_source_sha256`, `calibration_source_sha256`,
`payload`. Coordinates must equal the declared physical action values.
`context_sha256` is the identity of the full matched physical context: solver,
mesh/observer/grid, materials, maps, service condition, basis normalization and
applicable output units; omit only the held-out action coordinates. A string
condition label alone is not that receipt. Different contexts never share a
fit. Keep the referenced source artifacts and custody/rights manifest with the
return. For f02 and f08, calibration hashes must differ from ALL witness hashes
in the export, not merely that row. The consumer cannot establish that a
claimed independent artifact is scientifically independent from its hash.

The sidecar is bounded to 32 MiB, arrays to two million elements each. Larger
public panels need a prospectively registered partition; do not truncate a
curve or omit unfavorable rows to meet the tooling bound.

## Implemented methods and unsupported scope

### Cooling cell: fixed-kernel response surface

Payload is `{}`. Fit task observable vectors (including the registered local
case-plane peak, not a die or assembly quantity) using #917's Gaussian RBF,
training-fold coordinate scaling, fixed epsilon/smoothing and no holdout
hyperparameter tuning. Hold out a whole geometry across siblings. Only
same-context physical rows train it. Repeated same-context geometry must give
the same truth; duplicates do not multiply training observations. Outside
training coordinate bounds, or fewer than two independent geometry rows,
abstain. A bounding box is an interpolation support check, not a qualified
physical error bound. No implicit inlet/map/TIM or full-plate scaling.

### f02: two-source spatial causal impulse-response fit

Payload: `time_s` (uniform, event-aligned, starts at zero), `extra_power_w`
(`[time, 2 patches]`, nonnegative power ABOVE the independent base-load case),
`baseline_temperature_c` and witness `temperature_c` (`[time, spatial probes]`).
The baseline includes the actual initial/20 W response and is independently
acquired, never estimated from the target's temperature. Identical grid and
probe ordering across a context is mandatory. Use other complete waveform
actions to fit two causal FIR kernels per retained spatial probe with ordinary
least squares. Require full calibration rank and retained amplitude support;
do not scale into an unobserved nonlinear regime. Leave out the entire waveform
action across contexts. Target temperature is read only for diagnostics, after
prediction. Reducers: `temperature_max`, `temperature_final_max`,
`extra_energy_j` (piecewise-constant interval integration; last sample is an
endpoint, not an extra interval). Producer quantities must be in the indicated
degrees C and joules. This version does NOT implement a recovery crossing
observer: a task needing one must supply a future matched reducer, not omit it.
Sparse probes/time samples never certify continuous top-surface extrema;
reference grid/refinement applicability remains the producer's responsibility.

### f08: independent same-geometry modal cache

Payload: `frequency_hz`, `mode_hz`, positive `damping_ratio`, complex
`residue_real`/`residue_imag` (`[probe, mode]`), complex
`static_residual_real`/`static_residual_imag` (`[probe]`),
`static_compliance` (`[probe]`), `input_scalars`, and complex held-out
`response_real`/`response_imag` (`[frequency, probe]`). Modal frequencies are
Hz; residues must be mass-normalized and already converted so the response is
in the declared task unit (residue unit = response unit / second squared).

Compute `sum R_j/(omega_j²-omega²+2i*zeta*omega*omega_j) + residual`.
Reducers: dynamic peak over every retained probe/frequency, absolute static
maximum, and geometry-owned input scalars such as mass. This is a cached
static/eigen acquisition plus held-out harmonic-response measurement, NOT
novel-geometry interpolation. The held-out response is not used to fit modes,
residues, residuals, damping or truncation. Count the independent acquisition
and retained direct witnesses in full cost. Mode truncation, refined resonance
search, high-mode static correction and direct-witness adequacy remain OPEN;
a sampled peak is not a qualified continuous-band maximum.

### f13: scoped plane-wave transfer-matrix control

Payload: ordered complete `frequency_hz`, `rho_kg_m3`, `sound_speed_m_s`,
`port_radius_m` (equal input/output ports), boolean `coaxial`, explicit
`mean_flow_m_s`, `segments` (`{length_m, radius_m}`), `input_scalars`, and
held-out power-normalized witness `tl_db`. Rigid lossless circular segments,
volume-velocity impedance `rho*c/area`, `exp(+i omega t)`, equal ports.
Use the chained two-port matrix to calculate transmitted power TL, not a
pressure-only amplitude ratio. No witness TL enters prediction.

Abstain unless coaxial, no flow, and the entire frequency grid is below the
lowest first transverse-mode cutoff over every segment/port. These tests do
NOT qualify an abrupt-junction plane-wave approximation; evanescent junction
correction, loss and cutoff-margin adequacy still need witnesses/approval.
Original offset chambers and above-cutoff questions require the absent stronger
multimode/mode-matching arm. The report labels this absence. It must not turn
unsupported full-task coverage into a V4 win for a cheap method.

Reducers: `interval_p10_tl_db` (trapezoidal frequency-interval masses, left
weighted quantile), `minimum_tl_db`, independent geometry input scalars. The
producer must register that exact reduction, retain the full band and converge
notches; dense adaptive samples do not gain extra population mass. If the
producer uses a different established quantile observer, add its matched
version rather than changing historical values. Power-balance/conservation
acceptance remains reference evidence, not inferred from synthetic algebra.

## Reports and cost accounting

Witness reductions are checked against registered panel values with a tight
floating-point arithmetic check, not a newly selected physical tolerance.
Bad observer alignment refuses the input; reference failure is not candidate
failure. Requirement variants reuse physical rows and do not renew exposure.

The same #917 task optimizer commits a pick before the independent reference
judge reports feasibility agreement, false-feasible/false-infeasible counts,
exact picks, regret in the task's buyer units, abstention, NONE_FEASIBLE and
unresolved masks. Closed lookup replay is a separate sanity check. No arbitrary
finite regret is assigned to an unsafe pick. Curve errors and observable errors
both report their denominators; zero compared rows is not agreement.

Measured costs include fitting, prediction and reductions per held-out row;
existing optimizer/reference-assessment CPU/wall costs are separate. The CLI
also times input reading, validation and complete reporting. Fit work is
repeated for each held-out context/query in this conservative implementation;
do not present its CV total as deployment query latency. Producer acquisition,
refinement, retained verification, process RAM, euros and matched Carbon rebuild
costs remain separately reported or NOT_MEASURED. Source hashes and environment
versions bind the execution. Serialization/I/O and process startup are not in
the timed measurement: Data Collection must retain an external process timing
and peak-RSS receipt for a full economic comparison.

No eligible complete four-family public export is retained on starting main:
aggregate capacity/error reports are not solved-panel training observations.
Only synthetic fixtures were executed here. Real findings await Data
Collection's matched returns. `UNRESOLVED_NO_MATCHED_CARBON_ARM` is always the V4
state until Test Lead compares a matched Carbon arm and decides applicability.

Source contracts: [return requirements](data-collection-return.md),
[cooling](cooling-cell.md), [f02](f02.md), [f08](f08.md), [f13](f13.md).
