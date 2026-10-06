# First customer-shaped DEVELOPMENT round

**Authority:** [OWNER-PORTFOLIO-DEV-ROUND-01](../../../../.agent/decisions/2026-10-06-OWNER-PORTFOLIO-DEV-ROUND-01.md),
the owner's direct rolling delegation on 2026-10-06. These five hypothetical
buyers define useful decisions, not five claims of paid customer demand.
Numbers in [requirements.json](requirements.json) are **selected first-round
DEVELOPMENT requirements**, not unanswered proposals, measured material laws,
or production tolerances. Material constants are explicitly synthetic fixtures.

| Packet | What the buyer wants Carbon to choose | Why a wrong decision costs them | Main new work / reuse |
| --- | --- | --- | --- |
| [f02 burst thermal](f02-burst-thermal.md) | The highest-energy permitted burst that stays under 95 °C | Throttling or a thermal-limit breach | New transient solid reference; reuse thermal representations/custody, not steady CFD truth |
| [f06 grating coupler](f06-grating-coupler.md) | A TE coupling geometry robust to the declared offsets over 1530–1570 nm | A mask with poor coupling or excess reflection | New 3D grating/mode overlap; keep old supermode asset only as a baseline/control |
| [f08 resonant structure](f08-resonance-structure.md) | A light support with low worst-band motion and adequate stiffness | Precision loss from a missed resonant peak | New CAD/modal/harmonic adapter; reuse generic case/evidence contracts |
| [f13 silencer](f13-compressor-silencer.md) | A compact two-chamber design with useful band attenuation | Packaging spent on attenuation that disappears in narrow bands | New 3D Helmholtz adapter; transfer matrices remain a strong baseline |
| [f17 micromixer](f17-passive-micromixer.md) | A groove design with uniform outlet concentration and low pump burden | Inconsistent reagent delivery or excessive residence/pumping | Reuse OpenFOAM packaging patterns; new velocity/scalar/flux contract |

All use the F1 ten-section outline from #718. No shared runtime is duplicated:
`carbon/authoring` owns physical/case/population contracts, `reference_runtime`
owns reference requests, `reconstruction` owns builds, `challenge_validator`
owns grades, and readiness/admission/design-search retain their roles. New
domain adapters wait for their authorized stage; planning labels are not IDs.
The Battery-led protocol remains **DEFINING**. These packets do not move its
queue, lock it, register Challenges or alter the original three contracts.

## Selected reference-feasibility allowances

| Task | Maximum allocated node-hours | vCPU-hours ceiling | RAM ceiling (GiB) | Solver launches, including failed/refinement/control work | All-in USD cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| f02 | 6 | 96 | 24 | 46 | 20 |
| f06 | 12 | 192 | 256 | 36 | 60 |
| f08 | 12 | 192 | 24 | 36 | 30 |
| f13 | 8 | 128 | 24 | 40 | 25 |
| f17 | 8 | 128 | 32 | 40 | 25 |
| **Aggregate** | **46** | **736** | one node at a time | **198** | **160** |

These are owner-delegated, non-transferable first feasibility grants, **not
estimated cost or an enforced runner**. One 16-vCPU CPU allocation, one solver
process at a time, no GPU, no automatic retries. A solver launch reserves an
attempt before dispatch; each separate normalization/static/eigen/harmonic
process also counts. Per-launch timeout is 3,600 s (f06: 7,200 s). Stop at the
first attempt/time/memory/spend cap. Controls or required refinements that do
not fit remain unresolved. No expanding the allowance to get a green result.

Include setup, meshing, normalization, extraction, retained failures,
storage/egress and teardown in actual cost. Require an exact quote, pinned
image/build/license inventory, deterministic deck/panel manifest, resource
enforcement and retained ledger before dispatch. `runpod-cpu5c-16vcpu` is the
existing timing baseline, **not a promise of RAM availability**. Do not buy a
different profile silently or call its timing baseline-comparable. No paid
execution has occurred. There is no GPU grant disguised as a CPU allowance.

Preserve ledger, artifacts and logs after interruption. Inspect states and
surviving processes; keep uncertain attempts charged. No budget reset by
renaming the campaign, changing output directory or deleting its ledger.
Unsupported reconciliation stops that campaign with the precise decision
needed. This package adds no resumption subsystem.

## Evidence and scoring design

Each packet distinguishes design **actions** from exogenous conditions and
declares synthetic `P_dev`, diagnostic `Q` and the interpretation of `w`.
Quota/boundary feasibility panels cannot be treated as draws from P or as a
population reliability trial. Reused curves, wavelengths and time probes are
correlated within a case; model arms share the decision problem.

Public generated TRAIN and intentionally incomplete PRACTICE may be exposed
after implementation. Protected EVAL/STRESS, their seeds and labels, and final
sealed confirmation stay operator-side. No hidden batch is being created here.
Preregister development comparisons before observations; freeze finalists and
rules before fresh independent confirmation. No tuning on that confirmation.

These are engineering-value observables and reference checks, **not adopted
Score Packs**. No exam scalar, soft-physics score, fresh-case promotion margin,
winner weight or reward is set. 45/30/25 remains a prospective candidate;
separate metric qualification and score adoption are still required. A failure
of a mandatory limit cannot be averaged away by a good mean. Reference failures
remain missing evidence, never candidate scientific failure or favorable zeros.

## What can run now, and what cannot

The offline screen is safe to run; it calls no solver, provider or registry:

```text
./scripts/dev/canonical.sh python scripts/dev/portfolio_round1_screen.py
./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_portfolio_round1_screen.py
```

It checks simple dimensional/limiting calculations, not reference adequacy.
Its output names what it checked and what it cannot establish. Runtime remains
fail closed (`dispatch_ready:false`); this field is descriptive, not a runner
authorization token. No code reads this sheet to grant execution authority.

Next: pin f02 geometry/waveform/extraction and solver packaging, controls first,
under the protocol's stage permission. For the other four, prepare equivalent
deterministic case/deck implementations in separate tickets; inspect price and
memory before allocation. Reference adequacy is **NOT_DEMONSTRATED** for all
five until retained controls/refinements satisfy the selected criteria. Later
model comparisons, budget studies, fresh confirmation, experimental rights,
security and launch need their own exact contracts/evidence/authority.
