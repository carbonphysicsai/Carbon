# Open-benchmark onboarding — draft handoff

OPEN-BENCHMARK-ONBOARDING-01 · DEVELOPMENT / DRAFT_ONLY · 2026-10-10.
No solver runs, builds, training, spend, hidden/AX42 data or adopted Challenge.

Research [#1024](https://github.com/carbonphysicsai/Carbon/pull/1024) merged while
the owner's fourth preparation item was being executed. These are the **two
research-priority buyer jobs**, not eight additional launch candidates.
The four existing tools have been applied to both. They emit ten-section
packets and law/panel/status drafts; they do not decide whether a stage passed.

| Proposed job | Buyer decision kept intact | Generated handoff | Single next action / owner |
| --- | --- | --- | --- |
| Backward-facing step | Internal-flow engineer chooses a recovery contour with lower total-pressure loss across a complete operating brief, subject to separation and envelope limits | [Packet](backward-facing-step-packet.md), [law](backward-facing-step-law.json), [panel](backward-facing-step-panel.json), [status](backward-facing-step-status.md) | Test Lead/science and owner settle the supported contour/BC family, pressure-loss measurement and buyer separation/envelope limits; Codex can then expand exact public design-condition-rung tuples. |
| Full 3D periodic metagrating | Optics engineer chooses a genuine two-direction periodic silicon mask and thickness, maximizing desired-order efficiency subject to fabrication/reflection/unwanted-order limits | [Packet](metagrating-3d-packet.md), [law](metagrating-3d-law.json), [panel](metagrating-3d-panel.json), [status](metagrating-3d-status.md) | Test Lead/science and owner settle the mask grammar, full-order measurement and buyer constraints; Codex can then expand period-consistent public tuples. |

Adoption and eventual resource grants remain separate decisions. No approval
prompt is needed to use these drafts for independent preparation. A future
operator may not dispatch from them: cases are empty, pins incomplete, and
reference/novelty acceptance is missing.

## Source crosswalk, not a manufactured approval

The exact current research source is main
`94b193525f5d55eb20168ebbdbcf43ddf33653f1`; [tool-run.json](tool-run.json)
records input/tool digests. Read these source files with each draft:

- [Research summary](../../../../Business/research/benchmark-challenge-briefs/README.md),
  [source register](../../../../Business/research/benchmark-challenge-briefs/SOURCES.md)
  and [structured briefs](../../../../Business/research/benchmark-challenge-briefs/briefs.json).
- [Step-flow evidence](../../../../Business/research/benchmark-challenge-briefs/BACKWARD_FACING_STEP.md):
  adjacent industrial CFD/DoE optimization and open adjoint workflows;
  NASA measured anchor, conventions and partial SU2 route.
- [Metagrating evidence](../../../../Business/research/benchmark-challenge-briefs/METAGRATING_3D.md):
  documented industrial R&D/adjoint workflow, NanoComp numerical anchor and
  partial Meep/S4 routes; no exact-device physical validation.
- [Contamination proposal](../../../../Business/research/benchmark-contamination-policy/POLICY.md):
  public anchors/copies/equivalents excluded from future scored use; catalogue,
  extractor, distances, thresholds and shortcut-transfer checks not implemented
  or approved here.

`*-brief.json` supplies explicit recommendations drawn from those files.
The packet tool's public-source allow-list does **not** accept Business paths.
It is unchanged. Thus all 38 fields per packet correctly remain
`HUMAN_INPUT`, with **zero SOURCE_EXTRACT fields**. Source-linked human
drafting is not automatic verified extraction or scientific acceptance.

Buyer roles remain hypotheses, not actual customers. Range endpoints remain
ASSUMPTION proposals, not registered P, Q or w. The output lists source-only
solver revisions, not accepted containers. No external assets were downloaded,
imported or executed.

## Exact gaps and failure treatment

Both jobs have a ten-section draft, not a passed S1 exit. Status read **four
configured artifacts per job**, reported their gaps and verified **zero stage
exits**. Current stage remains `UNDETERMINED_WITHOUT_VERIFIED_EXIT_EVIDENCE`.
S0/S1/S3/S4 artifact presence is not evidence that those stages completed.
No TESTED, reference credibility tier, market, customer acceptance or launch
claim is earned.

Common holds:

1. **Question law:** approved P/Q/w, scenario aggregation, buyer hard limits,
   objective/ties, action grammar, k, E/B/n and exposure remain open.
   **k is questions per batch**, not actions in one question; action count is
   separately HUMAN_INPUT. Requirement variation does not renew exposure.
   A complete settled NONE_FEASIBLE answer is a valid forward outcome without
   redraw; uncertainty, missing support and reference/infra failure are not it.
2. **Contested frontier:** at least five resolved feasible and five resolved
   infeasible designs, both within **two accepted refinement bands**, in each
   mandatory stratum/question family (Test Lead working value). Widths and power
   stay HUMAN_INPUT. Add frontier resolution; never widen bands to pass.
3. **Reference and panel:** source/licence pins alone are partial. Build digest,
   dependencies, settings, measurement adapter, material/geometry law, accepted
   convergence/uncertainty, exact tuples and reuse index are absent. Empty
   generated cases are an honest missing manifest, not a registered panel.
4. **Value:** demonstrate complete feasibility, meaningful buyer-unit margins,
   changing picks and strongest-cheap-baseline/equal-budget gain. A benchmark
   witness validates only its measured observables and conditions, not the
   novel design family or physical customer hardware.
5. **Custody:** non-scoring published anchors remain distinct from novel
   public witnesses. A seed, rename, remesh or similarity transform does not
   establish novelty. Future protected operators need a prospectively accepted
   catalogue/descriptor/exclusion contract within justified reference support.
   No hidden bank is built, inspected or included in this handoff.

Specific step-flow gaps: consistent Re_H versus Re_theta definition, developed
inlet profile, SST/SSTm option mapping, total-pressure reduction versus shifted
Cp, mass/convergence checks and geometry-valid novel contours. Strong baselines
include applicable loss correlations, a calibrated response map and competent
coarse-to-fine RANS/adjoint search. A constant anchor x/H is only a control.

Specific optics gaps: fixed-period hardware across its scenarios; binary
mask/material-grid semantics; all propagating R/T orders, source normalization,
energy residual and spatial/time/PML/decay convergence; S4 harmonic witnesses
and memory sizing. Full x/y/z fields stay in scope. RCWA and direct/adjoint
optimization are serious competitors; the grating relation alone predicts
direction, not efficiency. Published RETICOLO results do not clear its code
for redistribution.

## Planning cost, not a grant or quote

These are #1024's broader complete-case **ASSUMPTION low/base/high**,
not #1012's earlier screening estimate:

| Proposal | Complete novel cases | Total allocated-host hours | Startup reference/comparator compute EUR |
| --- | --- | --- | --- |
| Step flow | 32 / 64 / 128 | 2.35 / 24.20 / 153.00 | 3.22 / 33.15 / 209.61 |
| 3D metagrating | 32 / 64 / 128 | 1.64 / 26.00 / 306.00 | 2.25 / 35.62 / 419.22 |

Formula: complete-case count x complete-case host-hours, plus separate anchor
and comparator setup, x the owner's planning EUR 1.37/host-hour. Complete-case
time includes necessary normalization, refinement and reductions. Allocation
into questions x actions x scenarios is unregistered and can change totals.

These are **not measured CPU-hours**, elapsed onboarding time or server
quotes. Labor, model construction and the later full equal-budget campaign
are excluded. Actual CPU, RAM and affordability remain UNMEASURED. Both high
scenarios exceed the historical EUR 100 startup target; all scenarios fit the
current **EUR 500 planning maximum**, but that maximum is not authority to
spend and these hypotheses are not enforced upper bounds. Do not narrow the
job or relax limits to fit. A future exact grant binds any execution.

## Reproduce the four draft views

From the repository root, for either `backward-facing-step` or
`metagrating-3d`, substitute the token below. These commands only draft/read
public files; nothing here runs a reference solver.

```text
python -m carbon.challenge_pipeline.onboarding --root . packet --brief docs/development/challenge_pipeline/open-benchmark-onboarding/<token>-brief.json
python -m carbon.challenge_pipeline.onboarding --root . law --brief docs/development/challenge_pipeline/open-benchmark-onboarding/<token>-brief.json
python -m carbon.challenge_pipeline.onboarding --root . panel --brief docs/development/challenge_pipeline/open-benchmark-onboarding/<token>-brief.json
python -m carbon.challenge_pipeline.onboarding --root . status --challenge <token> --bindings docs/development/challenge_pipeline/open-benchmark-onboarding/artifacts.json
```

Packet and status files are retained Markdown; law and panel are retained JSON.
Tests reproduce all four via the same existing APIs and compare the entire
stable output. Tool-run hashes describe drafting inputs and outputs, not
evidence of a qualified reference. Native Windows checks are diagnostic;
exact-head GitHub CI supplies canonical acceptance.

KEEP #973/#976/#977/#979 without changes; WRAP their outputs with a source and
gap handoff. No new registry entry, general pipeline, scope narrowing or
unmerged PR dependency. Hub retired and unchanged. PR Head owns merge.
