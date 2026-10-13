# Solenoid pole: proposed retained-data pilot worker

PKT-10 second independent PR against main, not stacked on the f02 worker.
**DEVELOPMENT / REPRESENTATIVE; no physical pilot, grant or adoption.**
Carbon Validator reviews the software; Data Collection confirms actual
operational runnability after the absolute-input and native reference holds.

## One command, and a separate stand-in

```sh
python -m carbon.development_comparison.solenoid_pilot run /uploads/bundle.json --out /results/pilot.json
python -m carbon.development_comparison.solenoid_pilot dry-run --out stand-in.json
python -m carbon.development_comparison.solenoid_pilot data-plan --out acquisition-proposal.json
```

The first rebuilds the fixed L0 on registered public TRAIN and feeds OPT-12;
it invokes **no** reference solver. The second uses a tiny explicit trainer
stand-in, scope SYNTHETIC_FIXTURE, distinct output schema, zero physical
solves. It proves the wiring only. The third emits a dimensionless proposal
with every absolute/rights/physics/grant binding still HUMAN_INPUT. It is not
a reference registration. No solver builds, spend, provider calls, keys,
AX42/hidden/journal/EV5 access or live runtime IDs are added.

## Same buyer job, not motor or TEAM substituted

Use the [original pole packet](../magnetics-first-panels/solenoid-pole.md),
[intake gaps](../replacement-onboarding/solenoid-pole-intake.json) and
[conditional runbook](../challenge-factory/pilots/solenoid-pole.md).
Proportional-actuator magnetics engineer chooses a pole profile meeting
the complete approved force/stroke/current envelope within a fixed non-PM
axisymmetric pot/coil. All three nominal/hot/axial-gap strata are mandatory.
No dynamic/thermal-duty, friction or eccentric 3D claim is made.

The kit uses the four existing dimensionless proposal coordinates with their
unchanged ranges. It predicts **135 raw outputs per complete curve**: closing
force, flux linkage, material peak B, nonlinear coenergy and stated-temperature
DC I-squared-R at all 27 states. Flattening order is current fractions
0.25/0.60/1.0 outer, stroke fractions 0/8..8/8 inner. Force is positive closing;
the producer separately retains the signed axial Maxwell force and its sign
conversion. No sample, stratum or repeated requirement is an independent
geometry. Entire geometries, including all strata/rungs, remain TRAIN or held out.

**Objective support proposal, not adoption:** worst absolute force departure
from the supplied buyer target curve, minimized across mandatory conditions,
in N. The kit computes `force_envelope_error_n` from the predicted raw force
curve and the same buyer target; it never learns privileged reference regret.
The worker requires this exact supported objective and full 27-point hard
force limits. The absolute target, limits/bands and objective approval remain
HUMAN_INPUT. If the buyer requires a different preference (e.g. least DC loss),
HOLD and extend the explicit contract prospectively; don't relabel it as the
minimax proxy or claim buyer value without approval. Safety limits do not move.

## Proposed acquisition and reuse plan (Data Collection, not run here)

`data-plan` retains S01-S10 from the original dimensionless proposal. TRAIN:
16 predeclared interior Halton points, index 1..16, bases 2/3/5/7 scaled to
the four bounds; held-out additions H01/H02 use index 17/18. This is an
engineering Q proposal, not a customer P or approved dimensional realization.
No outcome-driven selection. Physical clearance/coil/fillet/CAD validity is
still a hold; an invalid design is recorded, never clipped or redrawn. If an
invalid point prevents the full registered experiment, return a plan revision.

28 geometries x three strata =84 primary complete curves (48 TRAIN, 36 held
out). S01/S04/H01/H02 x three strata =12 refined curves, each 27 ordinary
states plus twelve virtual-displacement probes. Four control allocations x27
states; four charged failed-curve slots x27 states. **104 curves / 2,952 field
states max**, probe included, no retries. This changes no earlier EUR20
first-panel plan; it specifies the later runbook's distinct pilot proposal.

Controls: zero current; linear weak-field I-squared/current reversal;
exterior-air growth; stress-contour invariance. Verify axis regularity,
ampere-turn excitation, the single 2*pi*r normalization, force sign and
nonlinear coenergy before any volume run. Refined displacement steps must
remain valid and converge; use the adopted epsilon/bands only when supplied.
Do not use 0.5 B H for nonlinear iron, nor motor stack-length normalization.
Existing motor GetDP 3.5 / Gmsh 4.15.2 image is **environment reuse only**;
its linear planar A_z MMS acceptance is not A_phi force acceptance.

Reuse-diff completed/scheduled physical tuples before acquisition, ignoring
IDs/rung aliases for TRAIN/held-out disjointness. The worker reads retained
curves; the data plan does not launch the 84 curves. Acquisition receipts
include the entire acquired set, controls, failed/refined attempts and all
virtual probes, not a cheap single field state. No strong hot-material model
is created from a missing B-H(T) table. No permanent magnets are inserted.

## Closed public return bundle

`carbon.solenoid-pole.winnability-bundle.v1` = {schema, scope:
PUBLIC_DEVELOPMENT, sources}. Exactly seven roles, each {path, sha256}:
export, train, domain, cheap, costs, policy, reference. Local distinct public
files, no traversal/symlinks/protected names; per-file <=95 MiB, launcher sum
<=1 GiB. Digests are sha256-tagged hex. `check bundle.json` validates roles
and completeness before fitting; malformed/missing input is HOLD, never a
candidate physics failure. The separate fixture cannot pass the public worker.

### Domain and TRAIN

`carbon.solenoid-pole.material-domain.v1` fields: schema, scope,
anchor_digest, material_digest, coil_digest, domain_digest (public registered
CAD/coherent B-H(T)/coil/domain receipts, not placeholders); conditions
(condition ID -> nominal/hot/gap), strata, coordinate_bounds (exact proposal),
current_fractions, stroke_fractions, force_targets_n (27 finite targets per
stratum). This is a pin contract, **not automatic acceptance of the supplied
physics or customer rights**. The owner/Science must supply valid absolute
Ra/S/gap/clearances, materials and winding/current/temperature data and approval.

TRAIN uses `carbon.solenoid-pole.train-record.v1` JSONL: inputs are the four
coordinates + stratum; outputs are the 135 raw quantities, not target errors.
Exactly 48 unique complete rows at sixteen registered training geometries.
Whole geometry never crosses the split. Nonfinite/failure rows cannot be
silently dropped until 48 remain. Missing hot data or a rejected proposal is
an incomplete experiment, not a valid smaller/easier one.

### Export and policy

`carbon.solenoid-pole.pilot-export.v1` fields: schema, family=solenoid-pole,
questions, export_digest (canonical digest excluding itself). Each question
{case, support_case, task, reference}, existing digest-checked `tasks.task`:
all twelve held-out actions, all three mandatory conditions and limits covering
every force point. Objective exactly the supported minimax force target error.
Reference contains one row per action/condition with all 136 observable fields;
the worker checks its error reduction. Reference intervals crossing a limit
stay UNRESOLVED; no NONE_FEASIBLE redraw. Producer retains all finer-rung
evidence and adopts conservative uncertainty bands before compiling these
values; this worker does not turn a coarse model into refined truth.

`carbon.solenoid-pole.pilot-policy.v1`: schema, scope, export_digest,
domain_digest (domain file SHA256), owner_requirements_digest, question_law
{P,Q,w,panel_use=PUBLIC_HELDOUT}, solver_orders (complete predeclared order per
question), served_decisions [1,10,100] sensitivity, seed_policy [0,1,2],
precommit_receipt. P/Q/w must name the separately approved diagnostic rehearsal,
not pretend the actual customer population is adopted. k=8 is still proposed;
the Test Lead supplies the exact requirement draws and source-approved law.
Support clusters identify real independent packages/jobs; variations of this
one pot/coil remain one cluster. A nonempty receipt hash does not prove
chronology: retain the earlier action-only policy and review it independently.

### Strong cheap arm and complete costs

`carbon.solenoid-pole.strongest-cheap-screen.v1`: schema, scope,
method (`nonlinear-reluctance-fringing-calibrated` or
`manufacturer-cached-fe-rbf-kriging`), export_digest, train_sha256,
domain_digest, precommit_receipt, calibration_role=TRAIN_WHOLE_GEOMETRY_ONLY,
predictions (existing closed prediction schema, all physical rows, abstention
explicit), query_costs (measured wall_s/core_s per complete question),
source_digests (basis/calibration/extractor receipts). Source must show which
competitor wins TRAIN-only whole-geometry calibration. No weak linear circuit,
held-out fit or exact lookup disguised as the strongest applicable arm.
Consumer recomputes target error from the raw predicted force curve. Method
names/provenance hashes are assertions for independent review, not proof that
a nonlinear algorithm actually ran. Missing implementation/calibration remains
Data Collection's cheap-arm hold; this worker doesn't generate a false screen.

`carbon.solenoid-pole.pilot-costs.v1`: schema, scope, export_digest,
preparation {model,baseline} measured wall_s/core_s, reference (candidate,
condition, cost, planning_bound, field_states>=27, source_digests),
failed_control_cost, source_digests, new_curve_attempts<=104,
new_field_attempts<=2952. Every condition's complete costs add to one candidate
evaluation. Include extra displaced/refined fields; no 27-point curve priced
as one field solve. Every positive cost must fit its planning bound.
Preparation includes acquisition/reduction/fitting except the new MLP fitting
and warm-up passes the worker adds. All failed/control costs remain, and all
actually executed warm-up/inference/fit timings are charged. Actual acquisition
and lifecycle cash is separately retained; hypothetical matched-budget replay
does not imply reference systems physically ran again.

### Native reference holds, data plans only

`carbon.solenoid-pole.pilot-reference-return.v1`: schema, scope,
export_digest, domain_digest, image_digest (exact packaged new route),
formulation=AXISYMMETRIC_APHI,
observer_scope=MAXWELL_FORCE_NONLINEAR_COENERGY_VIRTUAL_WORK,
source_digests and native_acceptance_receipt. The exact equation/mesh/extractor,
convergence, conservation/force-contour and native verification records are
mandatory upstream. Current existence, rights, acceptance and Tier-2 buyer-tool
agreement remain **NOT_DEMONSTRATED**; no runtime parser can infer them from
hash presence. Data Collection supplies the public records; human science owns
adequacy and any new image/MMS acceptance. A motor binary alone never resolves
these holds. Tool disagreement is a reference finding, not a failed model.

## Launcher and all-in cap

```sh
python -m carbon.development_comparison.solenoid_pilot pod-spec public/bundle.json --code-ref PUSHED_SHA --out solenoid-pod.json
python -m carbon.agent_campaign.pod_jobs check solenoid-pod.json --root NEW_CHECK_DIR
```

Generator composes existing `pod_jobs` and its economic validator; no provider
calls. CPU study image for JAX, 32 allocated vCPU, cpu5c, 20 GB disk, 1,790 job
minutes plus export reserve, <=$1.20/hour ceiling, inclusive $36.40. Current
rate/stock, exact owner approval and launcher enabling remain required;
historical quote isn't a live offer. The launcher handles account/weekly cap,
self-termination, verified removal and receipt retrieval. Terminate, never
stop; allocation-to-confirmed-termination counts, not used-core fractions.

All three L0 replicas share <=4 CPU-h, enforced before each Linux in-process
JAX fit; worker process ceiling24 CPU-h. Fits use unchanged shared defaults:
width256/depth3/GELU/6000 Adam-cosine/float64. No best-seed selection, GPU or
retries. Actual working RSS/tail remain unmeasured and require Data Collection's
first probe. Stop on memory/time/CPU/adequacy/grant/teardown risk, retain
incomplete evidence, do not create a favorable partial result. Reference
acquisition has its own exact stage authority; this retained-data pod neither
builds GetDP nor acquires missing curves. Its cap isn't permission to do so.

## Reports / smallest unresolved decisions

All three seeds retain pointwise **maximum signed-force curve error (N)**,
decisions, false/missed feasibility, abstention, complete costs, and OPT-12
paired curves/finite-bank regret in the buyer's supported N objective. No
qualified score, global-optimum proof, automatic V2 PASS or launch decision.
Optimizer owns prospective V2 metric extensions. The new budget route is a
separate immutable representative **proposal**, never an official Challenge ID.

Before a real run: approve/bind the coherent absolute pot/coil/material case
and force envelope/minimax preference; supply axisymmetric-native verified
reference and strongest-cheap/TRAIN returns; then the exact measured resource
and spend grant. Until then the software is dry-run tested, while physical
runnability remains HOLD. Do not substitute an easier architecture or invent
missing force/current/material/temperature values to make the worker pass.
