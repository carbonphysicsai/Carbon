# OPT-15c section E: bounded synthetic measurement study

Authority: the owner's SCORE-LAB-EXPERIMENT-PLAN-01 section 2E and Root's
2026-10-14 direction to continue the next existing engineering gap while
PR #1361 is reviewed. Base: 42f875c23f391cf11582b655de85dd487cc2c431.
The authority files are unchanged from the prior 306dcbc0 read. The Hub is
retired. One separate main-based PR, Root review/integration, no adopted rule.

Handoff check: read the Test Engineer's execution handoff, preliminary
ScoreLab verdict/control code and Graphite executor sections 2.2-2.6.
KEEP campaign_gate, campaign_reference, campaign_blocks, core.analyze,
score_proof bootstrap and the pinned existing ten candidate proxies.
The missing piece is an executed measurement-design study, not another
launcher or statistical implementation. No rented/host-bound execution occurs.

Do not change physics.questions_per_side to measure sample efficiency:
physics.build also expands the context range with that parameter. Instead
build the existing six-score-question/36-value-question analytic profile
once and draw from its explicitly finite value population. The scoring side
and model traits stay fixed. Additional rows are simulated sampling draws,
not new independent trained models or enlarged physical support.

Register two studies before any result run:

1. Sample/block study: N = 30/300/3000 draw rows, B = 3/10/30 equal-size
   independent blocks, within-block draws either iid or perfectly replicated,
   three explicit toy sampling seeds. P = Q = uniform over the finite value
   support; buyer w = 1. This is 54 cells. Holding B fixed while increasing
   identical within-block copies must not create information.
2. Proposal/outage study: N = 300, B = 10, both dependence assumptions, three
   sampling seeds, requested outages 0/1/5 percent, strict-complete versus
   common-complete-block exclusion, and two explicitly separate estimands:
   raw proposal Q and importance-corrected P. Q gives half its probability
   to extrapolation and distributes the other half uniformly over the other
   finite questions; P remains uniform, buyer w remains 1. This is 72 cells.

All numeric values are synthetic ASSUMPTION settings within the experiment
plan, not Challenge registration or recommendations. Keep P, Q, buyer w and
the P/Q correction separately in every receipt. Use the unnormalised
Horvitz-Thompson mean to target P; never label the unweighted Q result as P.
With exclusions, label the conditional retained-draw estimand and its mask.

Each cell runs the same frozen ten candidate proxies, physics OFF and the
existing neighbourhood score blend. Compute score once per candidate/member
and reuse it; measurement choices never reach scoring callbacks. Include
the existing cheap map/always-abstain controls with honest cost/physics limits.
For each candidate compare the existing crossed recipe/case bootstrap with
the existing crossed recipe/block bootstrap on the SAME complete-block mask.
Record original unresolved and otherwise-resolved-but-excluded counts. No
outage is a candidate failure. No surviving whole block means unscored.

Report tau, exploratory interval width/undefined fraction, selected-member
value/regret, known-bad/probe placement, population tau from the finite support,
and descriptive coverage/rank stability across the three toy seeds. These
are conditional finite-population simulations, not real sample-size advice.
Use 60 bootstrap replicates; no winner, threshold, weight search or holdout.
Other section-E aggregation choices, score-side failure modes and full
population calibration remain explicit later gaps, not silently completed.

Resource plan: sequential canonical local run, 1800 CPU-second and 1900
wall-second hard caps, 2 GiB address-space cap, complete-cell pre-dispatch
reservation, checkpoint after every cell. Stop on first error or cap; retain
partial results and never select a favourable subset. Public aggregate/toy
controls run first using the existing gate. Count real scorer calls separately
from cached bootstrap/readout; no solver, reconstruction or inference calls.

Focused tests must distinguish iid from repeated blocks, show duplicate rows
cannot shrink the block interval, prove P/Q correction on an exact fixture,
preserve fixed scorer inputs, refuse public/partial/invalid law inputs and
explain complete-block losses. Freeze source/plan/candidate digests before the
actual run. Reuse unchanged adapter evidence; add canonical focused controls,
Black/Ruff/hygiene and actual result reproduction for the new module only.
