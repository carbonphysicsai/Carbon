# f13 — Carbon-owned compact silencer design optimizer (proposal)

**Status:** DEVELOPMENT design specification; no registered optimizer, answer
bank, solver adequacy, score, customer deployment, or qualification. The
[round-one packet](../round1/f13-compressor-silencer.md), its
[numeric sheet](../round1/requirements.json), and the
[common packet](../COMMON_DESIGN_PACKET_V1.md) supply the selected first-round
requirements. Values marked **HUMAN_INPUT (recommended)** below are new
prospective choices, not additions to that packet. Test Lead owns verification,
attacks, sizing, and any score adoption. Carbon must freeze the selected
optimizer and bank before model or protected-reference observations.

## Buyer decision and domain

The hypothetical compressor-skid engineer chooses a *valid two-chamber
geometry* for the fixed synthetic air and fixed 500–2500 Hz incident-power and
matched-termination setup. The action is mixed only after a scoreable bank is
approved: chamber radii `r1,r2 ∈ [55,70] mm`, chamber lengths
`l1,l2 ∈ [40,110] mm`, neck length `ln ∈ [10,50] mm`, and lateral neck offset
`x ∈ [0,25] mm` are continuous in the packet; the neck radius is fixed at
20 mm. Geometry must keep at least 10 mm chamber-wall clearance and fit
140 mm diameter and 300 mm total axial length, including both fixed 10 mm
stubs. Invalid CAD is rejected, never clipped or repaired into another action.

The objective is to **maximize interval-weighted band p10 transmission loss
in dB**, equivalently minimize `−p10_TL` in dB. The packet's p10 ≥ 5 dB is a
buyer success limit; a geometry below it is not a successful design even if it
is the best available. Report minimum TL, mean TL and the full refined curve,
including narrow failures. Package/clearance limits precede ranking; a good
band average cannot compensate for one of them. The 500–2500 Hz band is an
integration variable with interval-width weight, not a set of independent
buyer scenarios. No operating-flow or source-noise objective is licensed.
There is no packet-authorized secondary commercial objective or Pareto weight.
For an exact p10 tie, use canonical lexicographic order
`(r1,r2,l1,l2,ln,x)` after unit normalization. This is a deterministic tie
rule, not a claim that smaller coordinates are better. If no candidate in
the registered bank is verified to meet all limits, the answer is
`NONE_FEASIBLE`/abstain, with a complete-bank versus unresolved-evidence
distinction. Never return the least-bad violating geometry as feasible.

**Scenario gap:** the packet fixes the medium, source, termination and band.
It does not define multiple independent operating scenarios or buyer strata.
A changed medium, impedance or band needs a prospective owner decision and
new reference evidence. Repeating frequency nodes or geometry searches does
not create hidden-batch sample size.

## Fixed search and decision budget

**Class (b), multi-start local search snapped to a scoreable geometry bank, is
proposed.** Six continuous dimensions make an exhaustive fine tensor lattice
expensive, while a differentiable model is not part of the prepared Level-0
construction contract. The registered bank, neighbor graph, starts, query
order, stop rule, and tie order must be immutable and Carbon-owned. A possible
first bank is **HUMAN_INPUT (recommended): 16 valid geometries**, chosen by a
precommitted space-filling rule that includes coaxial and offset controls and
band/geometry-boundary anchors. This is a *finite decision contract*, not an
optimum over every continuous geometry. If that coverage is inadequate, expand
the bank prospectively; do not silently strengthen the claim.

**HUMAN_INPUT (recommended): eight complete-curve model evaluations per design
task**, counting every bank geometry queried, failed query and repeated query.
Start at **HUMAN_INPUT (recommended): four** distinct Carbon-producer-selected
bank points and traverse registered neighbors by predicted p10, with a fixed
lexicographic tie rule and no early acceptance merely because 5 dB is
predicted. Carbon, never the miner, derives hidden starts. These counts are
planning values pending model latency, bank coverage and validator-cadence
measurements. The runner may return `UNRESOLVED_BUDGET` if it cannot complete
the fixed schedule; it cannot request more official queries. An alternative
registered exhaustive-bank search can be a Test Lead diagnostic, but cannot
be swapped in after seeing results.

## Truth verification and cost

Judge a selected geometry only by pinned, independent Elmer complex-power
reference truth under the packet's straight-duct, single-chamber, passivity,
mesh and frequency-refinement controls. Recompute p10 using interval widths,
not equal weight per adaptively added node. For regret, compare against the
best **fully reference-resolved, successful geometry in the same registered
finite bank**, measured in dB of p10 TL: `best_p10 − selected_p10`. This is
finite-bank regret, never unrestricted-geometry regret. If any potentially
better bank member is unresolved, report a best-observed difference only;
exact regret is unavailable. If the selected geometry violates a hard limit,
report the physical violation separately rather than converting it to a
favorable regret value. False `NONE_FEASIBLE` is exposed when a verified
successful bank member exists; no numerical penalty is specified here.

One complete curve starts with 201 frequencies on the packet's 10 Hz grid,
then requires resonance-directed frequency and mesh refinement. With a
separate process per frequency, the **lower bound is 201 solver launches per
evaluated geometry** before any controls or refinements. The proposed 16-bank
would therefore need at least **3,216 launches**, and the first-round grant is
only 40 launches/8 node-hours/$25 for controls and sparse preflight. A verified
multi-frequency deck could change process accounting, but no such deck or
timing exists. **Reference CPU-hours, dollars per full geometry, and producer
cost per task are NOT_DEMONSTRATED.** The producer's minimum work for a
complete 16-member bank is `16 × measured full-curve cost` plus controls,
refinements, retained failures and setup; the design query itself costs eight
complete-curve model evaluations. This cannot be represented as fitting the
current grant or a known validator cadence. Test Lead must obtain a pinned
per-geometry quote and a separate bank/confirmation allowance before a
reference-judged task can run. Reuse solved bank truth across candidate models
only under the same exact scenario and version pins.

The packet's straight-duct |TL| ≤ 0.25 dB, power balance ≤ 1%, mesh-halving
ΔTL ≤ 0.5 dB, resonance-location change ≤ 10 Hz, and complete-curve p10/mean
stability ≤ 0.25 dB are **selected numerical checks**, not proven uncertainty
or qualification. A p10 near 5 dB is `UNRESOLVED` until refinement establishes
a one-sided verdict. **HUMAN_INPUT (recommended): use a provisional ±0.25 dB
decision-review region around 5 dB solely to trigger refinement**, because
the packet already demands 0.25 dB p10 stability; Test Lead must replace it
with measured reference uncertainty before grading. Residual unresolved
points remain explicit; any pessimistic scoring backstop belongs to Test Lead
and cannot recast reference failure as candidate failure.

## Gaming, power and buyer use

For Test Lead's preregistered attack study, include (1) an edge-optimist that
inflates p10 just above 5 dB at near-limit geometries, (2) an over-cautious
model that rejects genuinely successful better attenuation, (3) a sign-error
model reversing transmission-loss preference or power ratio, and (4) an
optimizer-aware model accurate on visible search paths but wrong at held-out
starts or neighbors. Hidden Carbon-produced starts and a different registered
bank-search diagnostic can test path sensitivity; **only reference-judged
outcomes decide**, and disagreement requires investigation rather than an
automatic pass. Physical-unit regret is necessary to expose caution. Compare
cheap transfer-matrix and retained-mode baselines under the same design/query
budget; park this topology if those methods make the decision adequately.

**Hidden-batch task count is HUMAN_INPUT, NOT_DEMONSTRATED.** The packet now
sketches [acoustic target/band questions](../round1/f13-compressor-silencer.md)
over a complete solved curve bank and recommends four for a scoping inventory.
Test Lead must first obtain an approved `P_job`/protected `Q_job`, supported
reference contract, answer diversity, exposure and cost, then preregister
good/bad constructions and minimum task count with shared-bank clustering.
Report false feasible, false `NONE_FEASIBLE`, physical regret and each attack
subtype separately. **HUMAN_INPUT (recommended): eight eligible, unexposed
questions for an initial power pilot only after that law and funding exist**;
neither the four-question inventory nor eight-question pilot is a powered
batch or score bar. Frequency nodes remain within-question measurements.

The buyer-facing tool would take a pinned band, medium/source/termination,
package envelope and approved geometry bank; return chosen CAD parameters,
verified or predicted p10/mean/minimum TL curve, limit margins, provenance,
and `NONE_FEASIBLE`/unresolved status. It would replace manual geometry
sweeps for this passive, no-flow setup, not acoustic rig testing or compressor
operating design. **HUMAN_INPUT (recommended): five-minute interactive
decision latency** for a bench design session; this target is absent from the
packet and requires measured model/runtime performance. The same registered
optimizer, version and tie rule must serve grader and tool; protected truth
and starts remain operator-side.

## Open gates

Test Lead/owner must approve the finite bank and coverage, start/query budget,
scenario population and strata, reference-cost quote, numerical uncertainty
policy, power target and latency before testing. Exact `carbon/design_search/tasks.py`
named in the task was not present in this checkout; adaptation to the current
Challenge-neutral `carbon/design_search/` interfaces is a later implementation
decision. No changes to graders, hidden pools, validators, live contracts or
miner surfaces follow from this document. Reference adequacy remains
**NOT_DEMONSTRATED**; no full curve or paid solve is claimed.
