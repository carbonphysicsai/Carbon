# AI cooling counted CFD v1 — closeout index

**Status:** complete, frozen, synthetic DEVELOPMENT evidence.

This directory is the lightweight repository status package for the first
AI-accelerator-cooling decision experiment. It makes the campaign state and
claim ceiling available to every agent without adding the 2.935 GiB raw
OpenFOAM archive to Git.

The machine-readable authority for the numbers below is
[`completion.json`](completion.json). Its source completion manifest was
captured after the campaign at SHA-256
`697a510bd15ab0f350c7ea16dd4d62f7f6826db8eff1176cc1ad1f8c0025054d`.
The exact human science and compute/spend authorization is retained separately
as [`approval.json`](approval.json); its digest is bound by the completion
manifest.

## Exact identities

- PR #552 approved head:
  `0a1994b9bcad0f8b9f9e352d992819b853da4bc5`
- PR #552 merge:
  `e8b5abb35171bd0cd9d21a2a52aadf0eedf7083b`
- Construction:
  `sha256:5f2a504fa43b280770490246ac5e1c2c26f9c1df1e584a9f16cc7cbf350a4f50`
- Campaign:
  `sha256:b862575afb95c71af444fa06c11145df53bd60e1eca13ce5b5145d632b87a0ca`
- Solver image:
  `opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319`

## Result in plain language

The campaign ran all 48 planned design-condition cases through the registered
Docker/OpenFOAM path. All 48 finished `OK`; no retry ran. Every one of the four
model/search arms chose design `d03`:

| Variable | Value |
| --- | ---: |
| Channel width | 0.25 mm |
| Fin width | 0.30 mm |
| Channel depth | 2.50 mm |
| Flow control coefficient | 1.25 L/min/kW |

CFD confirmed `d03` feasible at all six registered conditions. The four
representative cases had a minimum die-temperature margin of 11.762 °C and a
maximum periodic-cell hydraulic power of 0.130275 W. The two boundary-stress
cases had a minimum margin of 6.824 °C and maximum hydraulic power of 0.117740
W.

The entire registered eight-design set resolved. Two designs were feasible and
six were confirmed infeasible. `d03` was the best feasible member under the
registered minimum-worst-case-hydraulic-power objective. Exact finite-set
regret was therefore 0.0 W for every arm.

This is agreement, not evidence that the learned model made a better design
decision. The learned KRR selected the same design as the analytical model.
The registered screen-then-confirm method did reduce model-query attempts:
48 to 13 for the analytical model and 48 to 18 for KRR.

## Evidence and cost accounting

- Six unique selected design-condition reference cases were reused across 24
  arm-condition uses; there were 18 reuses. These are not 24 independent
  trials.
- False-feasible proposals: 0/4. This is a descriptive count from one shared
  decision problem, not a population reliability estimate.
- Unavailable or invalid reference evidence: 0.
- Decision coverage: 4/4 proposals; abstentions: 0/4.
- Campaign wall time: 7,176.1 seconds.
- Construction + campaign + evaluation wall time: 7,177.093588600033 seconds
  (1.994 hours).
- Sum of per-execution solver wall time: 41,171.2 seconds.
- Allocated CPU-wall accounting at two CPUs per case: 22.873 core-hours.
  This is an allocation-based measure, not actual CPU consumption.
- Retained raw artifacts: 3,151,966,132 bytes (2.935 GiB).
- Ledger integrity: `ok`; surviving campaign containers: 0.

## Artifact retention

The full evidence has been copied out of the disposable PR worktree to the
durable WSL store. Its logical contents are:

```text
ai-cooling-approval-record.json
ai-cooling-construction/
AI_ACCELERATOR_COOLING_CFD_PLAN.json
ai-cooling-cfd-attempt-1/
ai-accelerator-cooling-synthetic-v1-campaign.sqlite3
ai-cooling-counted-result/
ai-cooling-campaign-completion.json
```

The durable host location is
`/home/carbon/shared/evidence/ai-cooling-counted-v1/` in the
`Ubuntu-24.04` WSL distribution. It is owned by `carbon:carbon`; directories
are mode `0550` and files mode `0440`.

The 2026-10-04 custody copy checked all 6,259 files against the original with
`rsync --checksum --dry-run`. The seven completion-manifest anchors matched
exactly, and the copied completion manifest itself retained SHA-256
`697a510bd15ab0f350c7ea16dd4d62f7f6826db8eff1176cc1ad1f8c0025054d`.
The original worktree copy is intentionally retained until the required
off-machine replica is confirmed. The planned OneDrive replica is not yet
evidence: its exact destination and successful sync still need to be recorded.
The hashes support an integrity check; they do not recreate missing artifacts.

## Claim ceiling

The result establishes only the registered decision outcome for the frozen
eight-design, six-condition, periodic straight-channel cell under the approved
synthetic 100 °C die and 0.25 W hydraulic limits. It does not establish
population reliability, generalisation confidence, a global optimum, customer
requirements or acceptance, manifold behavior, two-dimensional heat-map
behavior, transients, controller performance, experimental validity,
scientific qualification, production qualification or LIVE readiness.

The representative and boundary-stress groups remain separate. No combined
weighting or pass threshold is inferred.

## Known generated-report limitations

The immutable counted `result.json` retains two reporting defects:

1. `conclusion.next_expansion` still says to run the already completed
   campaign.
2. `cost.study_end_to_end_wall_s` omits the reference-campaign wall time.

Neither changes the solver evidence or decision. Use the completion manifest's
`interpretation.recommended_next_step` and
`execution.observed_pipeline_wall_s`. Repair the generator only in a
prospective ticket because its code identity is part of the completed study
freeze.

## Frozen next step

Do not add faster paid-compute cases to this campaign after observing its
results. Any broader cooling study must be a new, prospectively registered
campaign with an approved sampling design, independent observation unit,
physical scope, reference policy, evidence allocation and compute cap.
