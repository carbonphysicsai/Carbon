# OWNER-BATTERY-AMBIENT-MAP-03 — prospective DEVELOPMENT buyer decision

Ticket CHALLENGE-CUSTOMER-INPUTS-04. Ryan's direct 2026-10-08 instruction
selects an ambient-indexed charge map, superseding the single-protocol
decision in packet v2 and #817's Battery proposal. This is owner-approved
mock DEVELOPMENT semantics, not scientific qualification or runtime adoption.

One (c1, c2, switch voltage, cooling level) action is selected at each of
5/15/25/35/40 C. Every band meets charging T<=45 C, every-charge plating>=0 V,
programme voltage<=4.2 V and Q30/Q1>=0.99. Discharge thermal extrema remain
diagnostics. Minimize band session minutes; aggregate with the buyer's
ambient mix. Cooling is allowed, not silently free physical hardware.

The owner selects buyer-mix weighting of band value. Keep this `w_band`
distinct from the distribution P of buyer questions, diagnostic Q and any
outer-question evidence weights. Start-SOC support 10/20/30% and the explicit
session-start-SOC-to80 observable are selected by the owner; their reference
coverage is not demonstrated. Suggested 0.5-min best-anchored value
resolution, numeric probability/margin laws, lattice and observer adequacy
remain HUMAN_INPUT. A positive band weight changes value, not the independent
band's argmin; do not claim extra answers from mixture draws.

Align the prospective regret recommendation with #820's indexed-task
proposal: zero within the best-anchored value band, full minute difference
outside it. Report excess minutes above the band separately. This score-use
recommendation and numeric tolerance remain HUMAN_INPUT; no current frozen
score is changed. #820 at `e1d0fdbec3a77f464e936d2750b55a78dfb5d2a8`
already owns neutral indexed-task implementation; this ticket does not duplicate it.

KEEP public evidence at `f79e7a61da10f1005e7438362ffc8baf6bf80d61`,
`docs/development/evidence/battery-feasibility-02/ambient-indexed.json`.
Its historical metadata calls the then-unadopted map a diagnostic; retain
that identity. It reports a complete feasible map when cooling is allowed,
not fully settled optima in all bands. The selected warm bests use x4; some
35-C x2 actions are also feasible, while the reported 40-C feasible set uses
x4. Do not overstate that 35 C can only be feasible with x4.

WRAP in new packet, law and optimizer versions. Existing `BatteryCase` lacks
switch/cooling inputs and retains c2<=1.0; the public study's c2=1.25 and
variable switches are prospective extensions, not current runtime support.
Variable SOC needs session-start-to80 observation; arbitrary initial SOH
remains unsupported. Owning reference/task/quiz/score implementation waits
for its own pinned contract and authority. No valV2 permit is inferred.

Rejected: retaining a shared warm-safe protocol, averaging away one band's
hard breach, treating a cooling coefficient multiplier as pump electrical
power, relabeling historical diagnostics or turning near-best tolerance into
a soft safety allowance. Reversal is a future superseding decision and new
packet/law/optimizer; old evidence and frozen score studies are untouched.
Science/Test Lead own uncertainty, power and score adoption. PR Lead owns
delivery. Notifications: #643 and #42; final proposal/remaining seams to #41.
