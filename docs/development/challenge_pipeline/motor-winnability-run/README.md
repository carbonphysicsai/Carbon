# Motor complete-buyer winnability worker

PKT-13 / BATCH2-RUNNABILITY-MOTOR-01. DEVELOPMENT preparation only.
Carbon Validator reviews the contract; Data Collection supplies and confirms
physical runnability. The [PKT-09 runbook](../challenge-factory/pilots/motor.md)
and [round-2 question law](../question-laws/motor-round2.md) govern scope.
Physical execution is **HOLD**, pending the inputs below. Software implements
the retained-data route; no physical pilot, reference acquisition or grant
was exercised by this ticket.

## Commands

From the repository root in the pinned Linux study environment:

```bash
python -m carbon.development_comparison.motor_pilot dry-run --out out/motor-dry-run.json
python -m carbon.development_comparison.motor_pilot data-plan --out out/motor-jobs.json
python -m carbon.development_comparison.motor_pilot check public-inputs/bundle.json
python -m carbon.development_comparison.motor_pilot run public-inputs/bundle.json --out out/motor-pilot.json
```

The last command is Data Collection's single worker command after packaging
the seven pinned inputs. It fits the unchanged plain L0 recipe at public seeds
0/1/2 and invokes OPT-12 for each. It makes **zero reference/provider calls**.
It masks reference values before handing the query export to the trainer.
The dry-run uses deterministic synthetic curves and an explicit trainer
stand-in: it is wiring evidence only, with `real_pilot_executed=false` and
`scope=SYNTHETIC_FIXTURE`. A deliberately false peak prediction exercises
unsafe-pick reporting. Synthetic documents/labels are refused by public run.

For an independently authorized operator, the existing shared launcher can
consume a generated job spec; this command only writes the spec:

```bash
python -m carbon.development_comparison.motor_pilot pod-spec public-inputs/bundle.json --code-ref COMMIT_SHA --minutes OPERATOR_MINUTES --rate-ceiling-usd-per-hr AUTHORIZED_RATE --cap-usd AUTHORIZED_CAP --out out/motor-job-spec.json
```

That spec uses the existing `carbon.agent_campaign.pod_jobs` launcher and
study image; no new cloud launcher or provider integration. An actual launch
still needs the operator's separate exact grant, capacity and current quote,
account configuration, retained ledger and termination receipt. This ticket
does not launch, access keys, or authorize spend. No AX42 access.
Operator arguments have no guessed defaults. The launcher enforces its existing
USD50 per-run standing guard as well as worst-case disk/cleanup costs. The
PKT-09 USD77.20 maximum scenario is therefore not launchable through that
guard. Supply a quoted lower rate/duration fitting both ceilings and complete
work, or keep HOLD for a separate owner/operator plan. Export/cleanup minutes
are included within the 64-hour lifecycle; no automatic split or cap override.

## Full buyer panel and kit

The existing `motor_10p12s_kit` is KEEP. `motor_pilot_kit` WRAPs its signed
48-sample slice output, gamma-5d queries and theta+d shifts. Three equal slices
average once; each complete action observes holding J10/gamma0, peak J15/gamma0
and J0 cogging. Five gamma offsets {-10,-5,0,5,10} at each loaded current,
plus one zero-current curve, cover all skew {0,2,4} siblings: eleven unique
raw sweeps per geometry. No legacy 8p/24s, reduced peak target, interpolation
of absent curves, or ordinal regression coordinates.

The registered grammar remains magnet [1.5,4] mm, coverage [0.65,0.95], gap
[0.3,1] mm, tooth [0.20,0.40], opening [0.03,0.12], slot bottom [34,42] mm.
Reuse `feasibility02.topology.validity` for the actual geometric predicates.
TRAIN is still `carbon.motor-10p12s.train-record.v1`, raw signed `t00..t47`.
The wrapper predicts those raw outputs and derives complete-panel metrics,
rather than fitting torque averages or a privileged objective label.

Each task has one composite condition:
`holding-J10-g0_peak-J15-g0_cogging-J0`. Its seven hard quantities are holding
mean, peak mean, both absolute/fractional ripple and cogging. Limits must stay
within round-2's stricter-or-equal proposed support; peak mean is >=12 N m.
Peak absolute ripple is twice holding; both fractional caps match. Objective
is minimum holding ripple fraction. The fixed holding current ties across
actions, so frozen bank order completes the tie rule. The worker does not
infer a 2-second thermal rating or continuous/3D/end-effect validity.

## Data Collection input contract

`bundle.json` is a closed manifest with `schema=carbon.motor.pilot-bundle.v1`,
`scope=PUBLIC_DEVELOPMENT` and exactly `sources` for the roles below. Each
source descriptor is `{path,sha256}`: distinct plain relative public paths and
`sha256:` prefixed lowercase 64-hex byte digests. Paths cannot traverse, alias
the manifest, use symlinks, or name private/sealed directories. Manifest is
bounded to 1 MiB; each source to 95 MiB. Duplicate JSON keys are refused.
No worker input, raw curve or question is copied into the repository.

| Role | Required content and holds |
| --- | --- |
| `domain` | `carbon.motor.pilot-domain.v1`, scope, topology `10p12s-double-layer`, `geometry` mapping canonical index strings to six physical coordinates, and `curves` mapping each index to all eleven command curves. Each curve has `j_a_mm2`, `gamma_deg`, signed `outputs` t00..t47 and `source_digest`. Domain contains **heldout** geometry only. |
| `train` | Existing raw-slice TRAIN JSONL, 16 independent physical geometries x all eleven commands =176 labels. Every curve carries source/rights provenance; no nonfinite/excluded or repeated commands. All skew siblings of a heldout geometry are excluded. Existing 19 study designs/128-stage1 plan are not automatically this 16-geometry pilot dataset. |
| `export` | `carbon.motor.complete-panel-export.v1`, scope, family `motor`, questions, `export_digest`. Twelve frozen questions; each has case, support_case, task, reference. Tasks use the existing runnable `tasks.task` schema, finite canonical actions `{design,skew_deg}`, all 12 heldout geometries x three skews =36 actions, one composite condition and all hard limits with adopted nonnegative bands. Reference values include the seven metrics and signed holding/peak/cogging stack samples named `<role>_t00..t47`. They must reproduce the domain's raw curves. |
| `policy` | scope, export_digest, domain_digest, owner_requirements_digest, precommit_receipt, separate question_law `{P,Q,w,panel_use:PUBLIC_HELDOUT}`, solver_orders, served_decisions and seeds `[0,1,2]`. Each solver order lists all 12 canonical integer geometry indices, frozen before truth; no hindsight optimum order. Threshold questions sharing this bank use the same support_case/reference_bank cluster, never twelve invented independent banks. |
| `reference` | scope, export_digest, domain_digest, exact image_digest, observer `10p12s-gamma-5d-theta+d-three-equal-slices-v1`, adequacy_receipt, uncertainty_receipt, source_digests. The historical GetDP/Gmsh pin is `sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05`. Presence/applicability and full-role observer/uncertainty are Data Collection holds. Linear MMS acceptance is insufficient. |
| `cheap` | scope, export_digest, method, strongest_method_receipt, train_digest, predictions (existing carbon_arm prediction schema), query_costs per complete question. Full signed-curve/Fourier Kriging/RBF, nonlinear circuit/cached-FE comparison and whole-geometry calibration belong to the comparator owner. Stack reductions must agree with the supplied curves. No weak holding-average baseline stands in for the strongest method. |
| `costs` | scope, export_digest, preparation `{model,baseline}`, reference list, failed_control_cost, source_digests, new_sweep_attempts, new_field_attempts. Every cost is `{wall_s,core_s}`, separately measured. Reference records give integer design, cost, planning_bound, raw_sweeps=11, field_systems>=528, source_digests. Charge a complete geometry's eleven sweeps once: they supply all three skew reductions. No cross-geometry cache or free acquisition is assumed. |

The domain's grid is 48 signed samples over 12 degrees at 0.25 degrees;
producer must perform registered 96-to-48 export explicitly where applicable.
Proof of nonlinear torque/phase/skew adequacy, complete peak witness and
appropriate uncertainty remains external evidence. A SHA identifies a receipt;
it does not independently certify that receipt's scientific adequacy.

Owner law/support/objective/k/P/Q/w adoption and useful-accuracy/pass/park
thresholds remain HUMAN_INPUT. Missing input produces HOLD with
`candidate_failure=false`. An in-band reference stays UNRESOLVED. No redraw
of NONE_FEASIBLE, lower peak floor, softened hard limit, or automatic fallback
to the historical holding-only panel is implemented.

## Big-machine acquisition inventory, unexecuted

`data-plan` exports this separate proposed public inventory:

| Work | Geometry count | Raw sweep jobs | 48-angle field systems |
| --- | ---: | ---: | ---: |
| Public TRAIN | 16 | 176 | 8,448 |
| Public heldout | 12 | 132 | 6,336 |
| Reusable target corpus | 28 | 308 | 14,784 |

A sweep is a signed angle curve, not one field solve or a whole buyer question.
For all skew siblings, commands are J0/gamma0 and J10/J15 at five offsets.
The 36 heldout skew actions remain 12 physical geometries; requirement variants
and skew siblings do not multiply independent evidence.

Historical allocated CPU-seconds per sweep, taken from round-2's arithmetic
sheet: standard planning 4,320, shared-host p50/p95 4,164/6,648; rung2 planning
28,800, historical 28,997/56,500. These are elapsed x2 allocated cores, **not
measured process user+system CPU, portable p95, or big-machine wall time**.
Measure both CPU and elapsed on the first complete-case probe. A fresh standard
corpus alone estimates 369.6 allocated CPU-hours and cannot fit this 56-hour
pilot cap. Reuse is conditional on complete roles, source pins, rights and
disjointness; missing corpus needs a separately authorized acquisition plan.

PKT-09's new-attempt prefix is four standard 48-angle and two rung2 96-angle
sweeps = six attempts /384 field systems, failures included, zero retries.
Reserve controls/probe/refinement inside this prefix; uncovered controls,
additional peak sweeps or a changed multiplicity produce HOLD and prospective
repricing. No dispatch plan chooses missing actual geometry/command identities.
The RSS hypothesis is <=16 GiB under a 64-GB host profile; measured peak RSS is
null. It is not a measurement or a capacity guarantee. Timing, RAM and complete
job pins must be confirmed before batch dispatch.

The sealed half is a **separate owner/validator acquisition plan**: job counts,
timings and memory are HUMAN_INPUT/null here. No sealed cases, seeds, IDs,
draws or manifests are read/generated; no sealed inputs mount in this worker.
Do not infer its inventory from the public pilot. This separation is a hold,
not a fabricated second corpus or a declaration of hidden-bank readiness.

## Accounting, report readers and shared family pieces

Retain PKT-09's <=4 aggregate CPU-hours for all three fits and total actual
CPU cap 56 hours. The Linux worker uses a 16-GiB address-space ceiling and
process CPU limit; the shared operator launcher owns the 64-hour lifecycle
deadline and deletion/ledger checks. Address space and RSS are different;
the strict address cap may stop JAX before the RSS hypothesis is reached.
Proposed 32-vCPU allocation totals 2,048 billed vCPU-hours at 64 hours even
if fewer cores run. USD77.20 is the existing conditional all-in ceiling,
dependent on inclusive quote <=USD1.20/hour and extras <=USD0.40; it is not a
current quote or spending authorization. Probe <=90 lifecycle minutes and
USD2.20 remains included. No cap promises completed scientific evidence.

Each seed's `reports[].report.learnable` exposes signed-curve learning and
unsafe/missed-feasible/abstention outcomes. `curve_diagnostics` adds separate
holding/peak/cogging maxima and coverage plus per-limit near-band counts.
`advantage_and_headroom[].model_vs_cheap` reports paired verified decision
differences; `finite_bank_headroom` reads MLP regret in holding ripple units.
Only the settled finite bank defines that regret. Missing/reference-in-band
truth gives no model outcome or fake qualification. Prep acquisition, fit,
cold compilation, per-question query, failed/control and full verification
costs are charged; served-decision amortisation assumptions stay visible.
All-none or single-bank evidence cannot establish an unobserved buyer benefit.
Equal-budget candidates are complete geometry panels, preserving the registered
6/12/24 geometry ladder. Model/cheap action ordering collapses to first-occurrence
geometry order. Each independently verified geometry supplies the best feasible
skew's objective; any unresolved sibling keeps that panel unresolved. Raw
learning/unsafe-pick diagnostics still assess the model's specific initial
geometry/skew choice. Verification may select another covered skew after the
complete solve; it cannot bypass a peak limit or claim off-bank performance.

Electromagnetics can share GetDP/Gmsh pin management, discretisation MMS,
retained source loader, public/fixture separation, L0 raw-output trainer,
whole-geometry folds, cost ledgers, OPT-12 and operator launcher mechanics.
Solenoid axisymmetric Aphi/force observers and material/coil acceptance do
not transfer to rotating motor topology, signed torque/phase/skew, peak or
cogging. No generic physics authority is imported from #1275.

Tests use synthetic data only; canonical CI supplies engineering acceptance.
Hub files are frozen/retired. No real MLP result, solves, rental, protected
material, customer result, qualification, score, LIVE or settlement is claimed.
