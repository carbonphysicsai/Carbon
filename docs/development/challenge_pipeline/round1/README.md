# First customer-shaped DEVELOPMENT round

> **Current follow-up to #817:** [Battery ambient-map v3](battery-ambient-map-v3.md)
> supersedes the shared-protocol decision: one protocol/switch/cooling action
> per band, band-local hard limits and buyer-mix-weighted minutes. Use its
> [continuous law](../question-laws/battery-ambient-indexed-v3.md) and
> [optimizer](../optimizers/battery-ambient-map-v3.md). Numerical distributions,
> action/observer support and value resolution remain explicit seams.
> Cooling's 53-job recipe is **ON HOLD** pending the
> [analytic budget and temperature-plane decision](cooling-thermal-budget-v2.md).
> Earlier supplements below are preserved prospective history where superseded.

> **Historical #817 input proposals:** [Cooling v2 spreader/TIM inputs and panel](cooling-spreader-v2.md)
> await owner approval; the [panel recipe](cooling-spreader-panel-v2.json) has
> no dispatch authority. Battery uses the [continuous-primary law proposal](../question-laws/battery-continuous-v3.md)
> and [prospective optimizer v2](../optimizers/battery-ev-fast-charge-v2.md).
> Numeric distributions/aggregation and variable-SOC/restart support remain
> explicit owner/reference seams. Earlier packet versions are preserved.

> **Historical #804 Battery/Cooling versions (2026-10-08):**
> [Battery v2](battery-ev-fast-charge-v2.md) (minimise admissible session time;
> no hard 30-minute limit; charging 45 C, test-discharge diagnostics) and
> [Cooling cell v2](cooling-cell-v2.md) (post-spreader interface heat map,
> stated buyer properties; no selected TIM/ratio/inlet alternative).
> [Planning amendment v2](first-three-requirements-v2.json) and
> [#776 law/quiz impacts](../question-laws/quiz-impact-v2.md) record the changes.
> The first-three v1 rows/packets/sheet and feasibility follow-up below are
> **historical**, not the current Battery/Cooling brief. The 35.6-min probe
> report is explicitly corrected to a 63.3-min charge-integral observation,
> distinct from the reported 32.9-min best within limits. No historical rescore.
> Motor and the five new-family packets are unchanged.

**Authority:** [OWNER-PORTFOLIO-DEV-ROUND-01](../../../../.agent/decisions/2026-10-06-OWNER-PORTFOLIO-DEV-ROUND-01.md),
the owner's direct rolling delegation on 2026-10-06, extended prospectively
to the first three buyer briefs by
[OWNER-FIRST-THREE-CUSTOMER-ROUND-01](../../../../.agent/decisions/2026-10-07-OWNER-FIRST-THREE-CUSTOMER-ROUND-01.md).
These eight hypothetical buyers define useful decisions, not paid customer demand.
The five new families' core limits and grants in [requirements.json](requirements.json) are **selected first-round
DEVELOPMENT requirements**, not unanswered proposals, measured material laws,
or production tolerances. Material constants are explicitly synthetic fixtures.

| Packet | What the buyer wants Carbon to choose | Why a wrong decision costs them | Main new work / reuse |
| --- | --- | --- | --- |
| [Motor precision joint](motor-precision-joint.md) | A geometry/command pair providing 6-N·m holding and smooth torque | Commissioning stop or geometry/prototype redo | Reuse 60-angle reference; new command-role/cogging decision policy; no thermal/dynamic joint certification |
| [Cooling full manifold](cooling-accelerator-manifold.md) | A plate/manifold and flow meeting 85 °C / 50 kPa / 2.5 W | Prototype redo or a thermally interrupted module | Reuse periodic assets, not periodic truth as full-manifold evidence |
| [Battery EV fast charge](battery-ev-fast-charge.md) | A cell protocol meeting warm 30-min turnaround and 45-°C / 0-V model constraints | Lost driver time or investigation/replacement burden | Retain 30 cycles; prospective SOC/timing observer; no EV5/live-contract change |
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
The first three now have independent buyer briefs in the same format;
[first-three-requirements.json](first-three-requirements.json) is their
separate planning sheet. It grants no execution or money and is not imported
by runtime scoring. Their new numerical reference criteria are demands to
verify, not a reinterpretation of existing adequacy/study outcomes. Test Lead
and Carbon Validator own later versioned gate/quiz/tuning integration.

## Buyer reference credibility targets

Each packet's Reference policy now states the assumed buyer tool, Carbon's
current/proposed reference, target tier, published benchmark candidates and
HUMAN_INPUT agreement recommendations. The [shared credibility contract](reference-credibility.md)
defines the three tiers, evidence custody and claim boundary. Targets are
not earned evidence; no benchmark comparison or lab test ran for this addition.
Battery's real EV-use target needs Tier 3; the other seven offline simulator
design jobs target Tier 2, with hardware claims requiring the named later lab
evidence. Same solver name alone cannot establish Tier 1.

Latest owner scope: ignore full-cold-plate packaging/cost work. Cooling's new
credibility recommendation is cell-level only; the older full-assembly brief
remains deferred, not satisfied by a green periodic-cell result. None of the
new recommendations edits numeric sheets, grants, scorers or existing evidence.

## Selected reference-feasibility allowances

| Task | Maximum allocated node-hours | vCPU-hours ceiling | RAM ceiling (GiB) | Solver launches, including failed/refinement/control work | All-in USD cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| f02 | 6 | 96 | 24 | 50 | 20 |
| f06 | 12 | 192 | 256 | 36 | 60 |
| f08 | 12 | 192 | 24 | 36 | 30 |
| f13 | 8 | 128 | 24 | 40 | 25 |
| f17 | 8 | 128 | 32 | 40 | 25 |
| **Aggregate** | **46** | **736** | one node at a time | **202** | **160** |

The packets complete geometry, observation and sampling conventions not
encoded in the core numeric sheet; a runnable adapter must bind both.
These five-family allowances are unchanged by the three added buyer briefs.
They are owner-delegated, non-transferable first feasibility grants, **not
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

Each packet now also names a **prospective population of buyer design
questions** in §3. A question fixes the physical context, service conditions,
buyer requirement vector, allowed actions and a committed choice or abstention
rule; f02 chooses a schedule separately for each declared scenario. Different
questions may use the **same physical design/reference bank** when that bank
already resolves all needed conditions and quantitative outputs. Varying a
requirement can change the reference-best admissible design without a new
solver run; the eligible range and answer diversity must be verified, not
assumed. Changing only a seed, grid order or probe on an unchanged question
does not create a fresh answer. Questions sharing a cell, assembly or bank
remain clustered for power and exposure accounting.

Each Challenge still has **one quiz per batch**. Its design questions must be
fresh draws from a registered `P_job`/protected `Q_job`, with their bank exposure
counted under the bank lifecycle; a retired or published question cannot return
to hidden use. The current eight packets mostly fix one question each. Their
proposed question axes and scoping inventory sizes are `HUMAN_INPUT`
recommendations, not an adopted law, powered hidden batch or reference grant.
Before scoring, the buyer/authoring owner must approve eligible conditions and
requirements, the reference owner must demonstrate bank coverage and cost, and
Test Lead must establish sufficient unexposed questions, answer diversity,
attack separation and clustering. Otherwise the design leg is diagnostic.
Question variation cannot silently alter the registered Challenge or turn a
fixture into a deployment claim.

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

The first screen found a plain structural beam compliance of 0.0352 mm/N
(above the 0.03-mm/N target), so ribs must demonstrate their value rather than
receiving a pass by assumption. Duct mode cutoff is about 4.02 kHz, but chamber
cutoffs lie at 1.44–1.83 kHz inside the acoustic band: a 1D transfer model cannot
be presumed adequate. Mixer Re is 0.083–0.416 while Pe is 833–16667; the principal
numerical risk is scalar smearing, not turbulent flow. Optical geometry remains
above 180-nm line/space after declared offsets, but 10-nm full-3D memory feasibility
is unresolved. These are model-form screens, not results on a physical device.

Thermal RC probes deliberately bracket the 95 °C decision boundary: about
99.41 °C for the rectangular probe, 94.14 °C for the ramp and 97.39 °C for the
two-pulse probe. Even the below-limit screen is not an admissibility result:
the spatial hotspot and numerical error have not been measured. These actions
are frozen diagnostics, not a list of approved safe bursts.

Read-only review repairs before dispatch: f02 reserves four steady baselines
and freezes RC-selected near-limit probes; f08 places its second observation
on solid material and limits complete convergence to a named subset; f13's
40 launches are controls/preflight only, not a full-band p10 exam; the screen
refuses increased per-family ceilings even if the aggregate is edited too.

Next: pin f02 geometry/waveform/extraction and solver packaging, controls first,
under the protocol's stage permission. For the other four, prepare equivalent
deterministic case/deck implementations in separate tickets; inspect price and
memory before allocation. Reference adequacy is **NOT_DEMONSTRATED** for all
five until retained controls/refinements satisfy the selected criteria. Later
model comparisons, budget studies, fresh confirmation, experimental rights,
security and launch need their own exact contracts/evidence/authority.
