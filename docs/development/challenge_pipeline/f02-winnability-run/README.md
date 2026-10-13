# f02 retained-data winnability worker

PKT-10 / PILOT-RUNNABILITY-F02-01. Engineering pipeline, DEVELOPMENT only.
This is **not** a spend grant, a solver run, a population adoption, or evidence
that f02 is winnable. Carbon Validator reviews it; Data Collection confirms
actual operational runnability after supplying the return contract below.

## One command on the public pod

```sh
python -m carbon.development_comparison.f02_pilot run /uploads/bundle.json --out /results/pilot.json
```

It checks all source pins and data holds, rebuilds the existing f02 plain-L0
MLP on the registered TRAIN subset at seeds 0/1/2 (no replica selection), and
replays all three OPT-12 arms. No solver is invoked. It does not ingest hidden,
official, EV5, journal or AX42 material. No provider or credential operation
exists in this worker. A successful run means a public diagnostic was produced,
not that the Challenge passes a value bar, has Tier-2 credibility or is qualified.

Before a pod, `check bundle.json` checks the data contract without fitting.
`dry-run --out stand-in.json` runs a tiny two-context, sixteen-action stand-in
through the same judge and OPT-12 using an explicit trainer stand-in, without
reference solves or real MLP fitting. Its schema is
`carbon.f02.winnability-dry-run.v1`, scope SYNTHETIC_FIXTURE and
real_pilot_executed=false. It is not accepted as a public run bundle.

## Keep the buyer problem

Reuse [menu-v2 registration](../equal-budget-registration-v2-f02-menu.json),
the [source registration](../../evidence/reference-packages-01/f02-menu-v2/registry.json)
and [existing kit](../../../../carbon/development_comparison/f02_kit.py).
Sixteen peak/duration actions per twenty-four cooling/initial/split/waveform
contexts; fixed constant-property silicon/TIM/copper stack, two spatial source
patches, 20 W base, burst at 20 s, 120 s horizon. The objective is extra J,
subject to top-die spatial/temporal maximum <=95 C with the existing 0.5 C
reference band and retained refinement settlement. No average-temperature
substitution. Known integrated waveform energy is identical for every arm;
the MLP's energy output never changes the selection objective.

The complete held-out menu has 384 physical rows. TRAIN is exactly the first
eight valid registered draws per context: 192 rows from the existing 960-row
generation order, not a new TRAIN distribution. Physical disjointness ignores
IDs and rung names. The continuous TRAIN registration is never changed.
All 24 conditions share one package support cluster; repeated questions and
seeds do not become independent buyers or give a bootstrap confidence interval.
NONE_FEASIBLE questions remain; unsettled truth stays UNRESOLVED.

## Data Collection return contract (data plans, no new acquisition here)

Supply a local PUBLIC_DEVELOPMENT `carbon.f02.winnability-bundle.v1` JSON:
`{schema, scope, sources}`. `sources` has exactly the six roles below, each
`{path, sha256}`. Paths are distinct public relative files under the bundle
directory, no symlinks, traversal or protected names. SHA256 is `sha256:...`.
Each file is <=95 MiB; launcher total upload is <=1 GiB. No labels go into
the candidate view passed to the trainer.

| Role | Exact data needed / hold owner |
|---|---|
| export | Existing `f02_export.build` menu-v2 sealed public export, every primary present; original all-rungs refinement settlement retained. Data Collection: do not convert missing/reference failures to infeasibility. |
| train | `carbon.f02.train-record.v1` JSONL, the 192 registered rows, finite peak_top_c and extra_energy_j, no fixture tags. Data Collection: acquisition and timing receipts for the full acquired set, including 960 if all were acquired, must not be divided down to 192. |
| cheap_screen | `carbon.f02.train-only-spatial-rom-screen.v1`, described below. Data Collection: independently prepared spatial two-input ROM, not a one-node RC, exact bank lookup, or held-out fit. Missing basis/calibration is HOLD. |
| costs | `carbon.f02.winnability-costs.v1`, described below. Data Collection: complete costs, including failed attempts and controls, never assumed free. |
| policy | `carbon.f02.winnability-policy.v1`, declared before held-out labels. Data Collection/Test Lead: P/Q/w diagnostic identities and the strongest adaptive/direct finite-menu policy; no deliberately weak blind competitor. |
| reference_receipt | `carbon.f02.pilot-reference-return.v1`. Data Collection: immutable solver/observer/verification/convergence/conservation references. No accepted physical adequacy is inferred from an MMS acceptance. |

Schemas are closed in `f02_pilot.py`; fixtures demonstrate their shapes but
**their numeric data and hashes are not a real return**.

**cheap_screen** fields: schema, scope, method
`multi-input-spatial-impulse-response-or-state-space-v1`, export_digest,
train_sha256, calibration_role=TRAIN_ONLY, policy_digest (bundle policy file
SHA256), nonempty source_digests, predictions (existing closed
`carbon.development-prediction-input.v1` covering every menu row, explicit
abstention allowed), query_costs (one measured wall_s/core_s pair per question).
The receipt's method name is an asserted producer provenance contract, not a
scientific verification of the algorithm. Validator/Data Collection must
inspect the retained extractor, basis and calibration records. Use separate
patch input responses, full top-surface outputs, initial-state decay and the
20-W baseline. Include acquisition/reduction cost, temporal/spatial maxima and
an independent witness against the actual observer. Existing #994-style
held-out-curve regressions are not silently relabelled TRAIN-only spatial ROMs.
Do not tune method or hyperparameters on pilot answers. A strongest-cheap gap
stays a hold rather than passing a weakened comparison.

**costs** fields: schema, scope, export_digest, reference (one unique
candidate/condition row with positive measured cost, conservative planning_bound,
nonempty source_digests), preparation {model, baseline}, acquisition_sources,
failed_control_cost, lifecycle {status, receipt_digest}. All costs use measured
wall_s/core_s. Reference rows include all mandatory refinement attempts; acquisition
and failed/control work belong in preparation and are not erased. Preparation
must not already include the MLP fitting/warm-up that this worker adds. Baseline
preparation includes its measured fitting, reduction and preprocessing; per-job
baseline queries stay in query_costs. Acquisition receipts distinguish common
public historical material from new attempts. Lifecycle NOT_RUN/null is honest
before dispatch; after dispatch keep the launcher's allocation-to-confirmed-
termination receipt separate from hypothetical buyer replay costs.

**policy** fields: schema, scope, export_digest, question_law {P,Q,w,
panel_use=PUBLIC_HELDOUT}, solver_orders (complete predeclared candidate order
per question), served_decisions=[1,10,100] amortization sensitivity, seed_policy
[0,1,2], frozen_before_heldout=true. P/Q/w are explicitly named **diagnostic
rehearsal** identities; the source law remains UNREGISTERED, not a qualified
population. HUMAN_INPUT/OPEN cannot be passed off as an identity. Reference
export digest binds the later data, while an earlier retained action-only
policy registration demonstrates precommitment. A receipt Boolean cannot
prove chronology: Data Collection retains and reviews that earlier record.

**reference_receipt** fields: schema, scope, image_digest (exact
`sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675`),
export_digest, observer, convergence, conservation, code_verification (each
SHA256 reference), reference_status=PUBLIC_DIAGNOSTIC_ONLY. These are evidence
identity bindings, **not automatic scientific acceptance**. Source records must
state the actual case family, numerical peak/refinement scope and uncertainty.
OWNER-CODE-VERIFICATION-ACCEPT-01 accepted discretisation at t_end=0.375 only.
Current image presence and physical adequacy remain Data Collection/owner holds;
this retained-data worker neither pulls nor runs an Elmer image.

## Bounded launch plan, not permission to spend

After exact green merge, supply the public files above and a pushed code SHA:

```sh
python -m carbon.development_comparison.f02_pilot pod-spec public/bundle.json --code-ref PUSHED_SHA --out f02-pod.json
python -m carbon.agent_campaign.pod_jobs check f02-pod.json --root NEW_CHECK_DIR
# Only Data Collection, under an exact owner grant, may use the launcher's run command.
```

The generated spec uses the existing pinned CPU **study image** for its JAX
trainer, not the separate Elmer image: 32 allocated vCPU, cpu5c, 20 GB disk,
465 job minutes plus the launcher's export allowance, <=$1.20/hour ceiling,
$10 inclusive cap. The launcher adds its disk cost and cleanup reserve and
rejects an over-cap plan; live stock/rate and rights/grant still need checking.
No new overlay or solver binary is required on this retained-data pod.
`pod_jobs` owns claims, self-termination, verified teardown and result fetching.
**Terminate, not stop**, count allocation-to-termination, never CPU-core-divide
the cash rate. A local `check` is not native pod execution or observed capacity.

Worker process CPU ceiling is 6 CPU-h, including all JAX threads; the three
fits share 4 CPU-h, enforced before each fit in the Linux process. Export/
query/replay uses the remainder. Per-run memory availability is still an
operator check; no measured RSS claim is made. No retries, GPU or reference
solves. SIGXCPU, OOM, incomplete input or termination yields infrastructure/
hold semantics, never a false scientific report. Failed worker results stay
in the launcher lifecycle/cost ledger. Data Collection must not reacquire the
576 physical TRAIN/menu rows in a $10 job: the run-plan cap presupposes reuse.
Missing independent ROM basis, controls or reference rows consume the exact
remaining acquisition allowance in a separately approved reference plan;
if they don't fit, HOLD and return the smallest additional scope/cap decision.

## Result and remaining evidence

`pilot.json` retains all seed reports, source pins, receipts, per-stratum K
errors, decision agreement, false/missed feasibility, abstention, finite-bank
J regret/headroom and paired three-arm budget curves at the existing 1/2x,
1x, 2x ladder. Training and all actually executed query warm-ups are charged;
no best replica is selected. Cost amortisation is sensitivity, not buyer volume.
OPT-12 does not implement every prospective V2 net-margin/ceiling-capture gate;
Optimizer owns that metric extension. Do not call this output a V2 PASS.
Pass/park thresholds, solver adequacy, population and any adoption remain
HUMAN_INPUT. Missing calibration/reference returns still block a **real** pilot.
