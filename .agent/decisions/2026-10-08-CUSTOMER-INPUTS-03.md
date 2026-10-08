# CUSTOMER-INPUTS-03 — prospective input and question-law recommendations

Ticket CHALLENGE-CUSTOMER-INPUTS-03. Ryan selects **continuous-primary** Battery
questions directly; numeric laws, spreader choices and numerical adequacy are
recommendations pending owner/science decisions. No execution grant.

KEEP #804's packet semantics and all earlier observed identities. WRAP with
`round1/cooling-spreader-v2.md`, `cooling-spreader-panel-v2.json`,
`question-laws/battery-continuous-v3.json` and its explanation, and
`optimizers/battery-ev-fast-charge-v2.md`. Only index pointers are updated.
No sampler, reference solver, task schema or scoring code is changed.

Recommend a 30-mm-square, 1.5-mm C11000 copper lid, an indium-foil TIM1 and
a phase-change TIM2 with separately stated effective areal resistances.
Owner must approve the stack before a physical panel. Published IHS examples
and supplier test joints motivate these inputs; they do not certify this
synthetic high-load package. The existing cold-plate 0.5-mm channel cover is
**not** this added die-side lid. Do not double-count either TIM or copper.

An axial conduction reduction can fit the current periodic scope, but the
post-spreader map depends on the cooling design's boundary. Reject a universal
isothermal-map assumption; specify candidate-specific coupling and repeating-
cell coupled witnesses. The reference lacks a generic map input today. This
is MIGRATION_REQUIRED, not fixed by inventing a Gaussian ratio. Full plate
and manifold remain excluded. No existing Cooling law value is changed.

Battery continuous margins replace the tiny grid as the primary proposed
question route. Current reference supports ambient and soc0, not arbitrary
initial aged states. Varying soc0 requires a new start-to80 session observer;
the SOC0.10 slice retains the v2 10–80% anchor. Recommend a current-support
fresh-state point mass and separately blocked aged-restart extension, rather
than pretending cycle10 output is an independently initialized aged cell.
Time stays an objective, not a safety trade or cutoff. Capacity floor remains
fixed0.99 in the primary margin variant; the previous thermal/capacity grid is
the four-vector audit only. Aggregation/weights/bands remain HUMAN_INPUT.

Rejected: silent rescoring; picking stack values until hotspots pass; treating
supplier R'' as bulk t/k plus the same contacts a second time; arbitrary heat-
map smoothing; interpolating unsolved physical contexts as reference truth;
redrawing NONE_FEASIBLE to fabricate diversity; claiming independent SOH input
from a30-cycle degradation solve; copying hidden cases into witnesses.

Reversibility: supersede these prospective supplements, never edit observed
versions. Downstream Data Collection owns pinned map/reference packages and
bank truth; Test Lead/Validator own observer/task projections, scoring/power
and uncertainty adoption. #815/VALIDATOR-26 and #808 are separate lanes.
Change the new JSON/documents to supersede recommendations; no runtime repair
is necessary in this PR. Remaining owner decisions: stack, distribution
numerics, variable-SOC timing adoption, restart policy and numerical adequacy.
Scientific/security/product/launch authority remains unavailable.

Notification: #643 comment6061301571, #42 comment6061302513. Owner receives the
completed proposal on #41. Motor and five-family laws unchanged. EV5, sealed
journal14, live contract, queue, grants, 45/30/25 candidate and Hub unchanged.
