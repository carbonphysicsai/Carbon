# Cooling cell winnability worker (PKT-12)

Implemented retained-public-evidence replay and synthetic wiring. No new
native cooling result, measured winnability, scientific/security acceptance,
production qualification, spend authority or full cold-plate claim.
The Test Lead corrected the queue's Elmer wording: KEEP the existing pinned
OpenFOAM conjugate PG25 interior-cell route and the lid-side TIM2 interface.

## Data Collection's one command

After the producer supplies the seven pinned public files and their manifest:

```bash
python -m carbon.development_comparison.cooling_pilot run public/bundle.json \
  --bundle-sha256 sha256:<manifest-bytes> --out new-result.json
```

Run in the locked CPU Linux environment (`science-jax`). The worker loads and
checks the bundle, fits the shared default MLP for seeds 0/1/2, predicts the
complete frozen bank, and invokes the existing OPT-12 replay. It never starts
a reference solver, a pod, an account operation or a protected reader. The
CLI imposes a 32 CPU-h process ceiling; fitting has an aggregate 4 CPU-h
ceiling. An external execution owner still supplies the memory, wall-clock
and job lifecycle bounds from the PKT-09 plan. An output must be new.
An infrastructure kill is an incomplete return, never a candidate failure.

Check without fitting by replacing `run` with `check` and omitting `--out`.
Missing/null producer inputs return `HOLD`, with `candidate_failure: false`.
Presence of source/acceptance receipt digests binds identities; the receipts'
scientific adequacy must still be reviewed by their domain owners.

## Bundle and producer contracts

The manifest is `{schema: "carbon.cooling-cell.winnability-bundle.v1",
scope: "PUBLIC_DEVELOPMENT", sources: {...}}`. `sources` has exactly the
seven roles below, each `{path: <distinct public relative file>,
sha256: "sha256:<bytes>"}`. JSON files reject duplicate keys/nonfinite tokens;
every file is bounded to 32 MiB. The shared pod upload guard rejects private,
sealed/protected, escaped, remote and symlink paths before source reads.

| Role | Producer supplies |
| --- | --- |
| registration | Sealed `cooling_readiness` registration, three frozen post-spreader maps at point B; complete source/material/observer pins, TIM2/uncertainty, objective and separate P/Q/w. No guessed map or lid law. |
| train | UTF-8 JSONL `carbon.cooling-cell.tim2-train-record.v1`: 16 independent geometries x all three maps = 48 records, disjoint from the 12 held-out geometries. Each record has `inputs` (four actions plus categorical `service`), two `outputs`, `registration_digest`, `observer_version` and retained `observation` arguments for `cooling_readiness.observe`. |
| export | `carbon.cooling-cell.tim2-pilot-export.v1`, public `scope`, `family`, eight `questions` and canonical `export_digest`. Each question is `{case, task, reference}` with a runnable shared task and every candidate/service row. Deduplicated inventory: 12 geometries x three maps = 36 rows. |
| policy | `carbon.cooling-cell.pilot-policy.v1`: scope, export/registration digests, `precommit_receipt`, separate question-law P/Q/w identities and PUBLIC_HELDOUT role, complete `solver_orders` per question, served-decision amortizations and seed policy `[0,1,2]`. |
| reference | `carbon.cooling-cell.pilot-reference.v1`: same scope/digests, `native_acceptance_receipt`, source digests, and one retained native `observations` row per candidate/map, including co-located faces, numerical/pressure uncertainty, pressure and fluid extrema. |
| cheap | `carbon.cooling-cell.strongest-cheap-screen.v1`: same scope/digests, TRAIN byte pin, matching precommit receipt, method `same-map-rbf-kriging` or `calibrated-channel-thermal-response-map`, calibration role `TRAIN_WHOLE_GEOMETRY_ONLY`, shared prediction document, complete-question query costs and source digests. |
| costs | `carbon.cooling-cell.pilot-costs.v1`: same scope/digests; preparation costs for model/baseline, `failed_control_cost`, measured complete per-candidate/map reference costs plus planning bounds/source receipts, source digests and counted `new_attempts` (at most the existing 12-attempt proposal). |

The schemas and refusal checks in `cooling_pilot.prepare` are executable
contracts. Point B is a RES-03 DEVELOPMENT ASSUMPTION: inlet 40 C, interface
1000 W, footprint flow 1.50 L/min and 25 kPa cell allocation. Optional C is
outside this run. Its adoption needs the existing separately sourced stress
finding, new frozen tuples and a new cost plan. Full assemblies remain out.

The kit learns `peak_case_c` and `cell_pressure_drop_pa`. It derives half-cell
flow and hydraulic power with the same geometry arithmetic for every arm.
Every TRAIN and reference peak is independently rechecked from co-located
plate T plus local TIM2*q. Relabelled legacy `peak_c`, mean TIM rise, and an
unrelated field maximum fail. Model inputs contain only actions and frozen
service identity; reference labels are zeroed in the training/prediction view.

Tasks keep thermal ceilings <=85 C and cell pressure allocations <=25 kPa;
nonnegative pressure is mandatory. Stricter preregistered buyer limits may
vary between questions. The supplied objective is worst-service minimum
cell pressure or half-cell hydraulic power. Reference bands must cover every
retained map/numerical/pressure uncertainty, conservatively. A crossing stays
UNRESOLVED; NONE_FEASIBLE questions are retained without redraw or relaxation.

Each candidate verification cost sums all three maps, including refinements
and failures in the producer's complete cost receipts. Acquisition/preparation,
fits, cold/warm queries and failed controls are charged. Shared-bank requirement
variants form one physical bootstrap cluster, irrespective of question labels.
Eight questions on one bank do not establish eight independent samples.
Cold-bank exact lookup is a separate control, not a strongest held-out map.
The producer must preregister a competent solver search; a supplied order is
not evidence of adaptive-policy adequacy.

## Dry-run and report readers

```bash
python -m carbon.development_comparison.cooling_pilot dry-run --out fixture.json
python -m carbon.development_comparison.cooling_pilot data-plan --out jobs.json
```

The tiny dry-run uses six synthetic TRAIN rows, nine physical held-out rows,
two same-bank requirement questions and a deterministic trainer stand-in.
It exercises all three seeds and the actual OPT-12 harness with no paid solves.
It reports SYNTHETIC_FIXTURE and `real_training_executed: false`; it is neither
native cooling evidence nor a real L0 result. The ordinary public path refuses
this inventory, even when its outer manifest is relabelled public.

For each seed, read `report.learnable` for K error/coverage and unsafe/missed
decisions; `report.advantage_and_headroom[*].model_vs_cheap` for verified paired
improvement at each amortization/budget, and `.finite_bank_headroom` for MLP
regret against the same solved bank. `pointwise` retains error for all physical
observables; `pointwise_by_service` gives each frozen map's maxima, coverage,
abstentions and near-boundary physical counts. An unresolved reference blocks advantage rather than penalizing
a model. Thresholds stay HUMAN_INPUT; no pass/park or Challenge #2 verdict.

## Big-machine jobs and shared family tooling

[reference-jobs.json](reference-jobs.json) lists 48 TRAIN, 36 public held-out,
four controls and four paired refinements: 92 successful attempts before any
failures. Primary low/base/high timing proxies are 1620/3240/4860 CPU-s per
solve, and refinements are provisionally 2x. These are sourced hypotheses,
not measured timings. Working RSS has a proposed 16 GiB ceiling on the
64 GiB profile; measured RSS and elapsed time are HUMAN_INPUT until a probe.

Cold generation needs an estimated 43.2/86.4/129.6 CPU-h for references alone
under those proxies, then the existing eight-hour fit/check reserve. It cannot
fit the PKT-09 32-hour top-up cap. That cap assumes the matching 84-row corpus
already exists, allowing four controls, four missing rows and four refinements
(12 attempts including failures). More missing rows require HOLD and a separate
prospective bulk-generation grant; no automatic expansion is implemented.

The protected half has no tuples, paths, seeds or results here. Its counts and
resource plan remain HUMAN_INPUT for a separate custody/execution owner.

The heat-family kit can share byte-pinned public loading, geometry holdouts,
shared L0 trainers, complete-question timing, observer identities, uncertainty
propagation, complete-panel costs and OPT-12 reports with f02. f02's Elmer
heat MMS and impulse-response observers do not become OpenFOAM flow/TIM2
authority. Cooling keeps its PG25 applicability, native flow/conjugate controls,
cell hydraulics and localized interface observer. No new reusable solver
authority is earned by sharing the worker pattern from #1275.
