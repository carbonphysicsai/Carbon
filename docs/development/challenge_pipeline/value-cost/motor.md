# Motor — precision-joint magnetic shortlist scorecard

DEVELOPMENT / SPECIFIED. [Current buyer packet](../round1/motor-precision-joint-v2.md).
Recommendation: await revised-space S3 T1/T2, no new reframe while it runs.
KEEP: NOT_DEMONSTRATED. No change to torque/ripple/cogging limits.

## Part V — buyer value

Proposed numeric adoption and adequacy acceptance remain HUMAN_INPUT; existing
owner-selected DEVELOPMENT limits are preserved, not reopened by this analysis.

### V1 — real decision

Buyer role: frameless robot-joint electromagnetic engineer selects a geometry
and declared holding/peak commands before thermal/control/bench verification.
[Kollmorgen robotic-motor applications](https://www.kollmorgen.com/en-us/solutions/robotics/humanoid-robots)
show the joint-integration role; independent
[COMSOL 2D motor workflow](https://doc.comsol.com/6.4/doc/com.comsol.help.models.acdc.pm_motor_2d_introduction/pm_motor_2d_introduction.html)
computes mean torque and torque variation. These establish workflow, not
Carbon demand or the exact robot's acceptance. Magnetic shortlist is not
positioning accuracy, duty-cycle thermal capability or controller certification.

### V2 — low/base/high in buyer units

ASSUMPTION better feasible shortlist reduces holding ripple by **0.1 / 0.5 /
1 percentage point** at the same verified torque. No inferred micrometres or
joint speed gain. Avoided first-pass engineering rework ASSUMPTION **2 / 6 /
16 h** at **$100 / $150 / $200 per h** gives gross **$200 / $900 / $3,200 per
revision**. Retain independent FEA, prototype and tuning costs; net benefit
unproven. Do not add the older packet's whole prototype/commissioning losses
to this narrower screening-labour scenario. False-feasible picks are rejected,
not priced as an acceptable expected loss.

### V3 — precision-joint programme revisions

Independent anchors: [Universal Robots' 2024 media kit](https://www.universal-robots.com/media/1830013/ur_media_kit_a4.pdf)
lists arm platforms and launch dates; [Kollmorgen's frameless KBM range](https://www.kollmorgen.com/en-us/products/motors/direct-drive/kbm-series-frameless)
shows motor families and customization. Platforms and stocked variants are
not annual new designs; six joints are not six independently designed motors.

Low/base/high **ASSUMPTIONS**: 10/30/100 in-scope engineering teams ×2/6/12
shortlist-changing revisions/team/year = **20/180/1,200 decisions/year**.
Product-family count is NOT_MEASURED; target teams include OEM and specialist
motor suppliers without double-counting the same outsourced project.
V2 gives **$4,000/$162,000/$3.84m conditional annual gross**.
Empirical lower bound zero; no claimed industry flow or paid adoption.
Ask for CAD releases, distinct motor families, carried-over parts, task
eligibility and dated FEA revision logs; robot shipments are not the denominator.

### V4 — expensive curves versus already-cheap search

[Ren et al.'s motor optimization](https://pdfs.semanticscholar.org/8117/28aba09d970a1bd7a289f42119dce7867c60.pdf)
reports **505 FEM sampling points**, separately from 10,000 cheap surrogate
testing points. Its 24-slot/4-pole machine is not Carbon's revised 10p/12s/skew
space. **N=50/505/2,000 complete command curves** is an assumed transfer,
not a measured precision-joint workload; multiple commands/slices count once
in each complete curve and extra tolerance work must be itemized.

Current curve C1 **NOT_MEASURED** for this economic sheet. Inference
1/0.1/0.001 s and legacy 1,800-curve acquisition are shared sensitivities,
not measured model bounds. Dollar/wall savings remain **NOT_MEASURED**;
substitute matched curve CPU/wall into the shared formula rather than use
old unskewed timings. Enabled case: a 10,000-geometry tolerance/ripple/cogging
shortlist within a design-review window, if decision-parity and uncertainty
support it. Compare existing FEM-plus-response-surface, cached harmonics and
analytic magnetic-circuit controls; the cited study already uses a surrogate.
V4 PASS remains NOT_DEMONSTRATED. [Model](volume-leverage.json).

### V5 — credibility

Assumed buyer tool Ansys Maxwell; Carbon Gmsh/GetDP is not that tool.
Target Tier 2, earned NOT_DEMONSTRATED. #767 matched 10p/12 s, zero-current,
holding/peak/saturation and skew witnesses; pointwise and verdict/pick/ripple
regret, absolute near-zero cogging floors. Target does not earn Tier 3 physical
joint performance, 3D end effects, thermal or control claims.

## Part T — running revised-space panel owns the answer

### T1 — feasible answer

Old 8p/24 s bank: owner-reported 246 points, none ≥6 N·m with ≤5% ripple;
minimum ripple8%, cogging0.4–2.8 N·m vs 0.05 cap. That is NOT a failure result
for the revised topology. Public [S1/S2/S3 registry at96983b03](https://github.com/carbonphysicsai/Carbon/blob/96983b03b1b7fb06749e7584b16f0bb7be2dcc01/docs/development/evidence/motor-feasibility-02/registry.json)
defines 10p/12 s, declared commands and skew slices; a registry is not refined
feasibility. Complete common geometry/command answer across mandatory roles
NOT_DEMONSTRATED at inspected public head.

### T2 — contested boundary

Await ≥5 feasible and ≥5 one-band-near infeasible distinct plausible designs
per mandatory role, buyer-unit margin spread and settled answer changes.
Zero-current cogging and signed positive-drive torque need separate observers;
repeat angles/slices cannot inflate action counts. Fractions diagnostic.
Do not relax ≥6 N·m, ≤5% holding ripple or ≤0.05-N·m unpowered cogging to get
five passes. Peak-role limits remain those in the packet, not a copied holding rule.

### T3 — power

NOT_DEMONSTRATED. Optimizer gets registered full curves and role-aware tasks;
four controls and reference bands must test false feasibility, mean-only/flat
curves, phase/sign error and missed extrema. Use k/windows/remaining E and
whole-geometry clustering. Historical decision studies do not qualify this job.

### T4 — close calls

NOT_DEMONSTRATED question-level residual rate. Refine angular extrema AND
spatial gap mesh independently; no best-of-coarse-grid pass. Boundary rows
retain UNRESOLVED and enter the denominator, never favorable redraw.

### T5 — reference

Prospective rotating multi-slice phase/normalization, signed mean/pp/cogging
and saturation consistency require their pinned receipt. Source/phase/timing
identity and successful solver execution alone do not prove adequacy at these
limits. Reference/infra failures remain separate from candidate defects.

## Part C — current route, not historical timing

### C1 — per-case cost

UNMEASURED revised-space complete command-curve p50/p95/RSS with all slices,
mesh/angle refinement. Old motor timing calibration is different scope.

### C2 — startup

NOT_DEMONSTRATED. Legacy 1,800-curve manifest at the shared illustrative €20
overhead reserve leaves **1.95 serial wall-min/curve**; no proof new curves
fit it. Use actual current bank size/command curves, separate slice invocations,
controls/refinements, wall bill and resource-limited concurrency.

### C3 — ongoing

NOT_DEMONSTRATED until registered draw/window law, E, full bank refresh and
AX42 throughput exist. Reference generation is producer-side; retired public
training rows do not add another reference solve, nor renew exposure.

### C4 — validator

NOT_DEMONSTRATED buyer-task capacity under #727. Interface-v1 adapter #706
exists, but does not prove this command/cogging integration's rebuild/inference
cost. No reference motor solver in the validator.

## Reframe hold

Current V2 before/after is identical; no sacrificed scope proposed now.
If S3 T1/T2 actually fails, return a sourced one-reframe choice before any
extra route, retaining hard precision/safety. No hypothetical failure is
permission to duplicate the acquisition lane or reinterpret old curves.
