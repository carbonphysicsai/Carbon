# MOTOR-PILOT-COMPLETE-PANEL-01

Ticket PKT-13 / BATCH2-RUNNABILITY-MOTOR-01; working engineering decision.
NO_CONFLICT with PKT-09/motor-round2: the old holding export is insufficient.
Use one composite observation for every geometry/skew action. Its independent
outputs are holding and peak means, peak-to-peak and fractional ripple,
zero-current cogging, plus three signed stack curves. Objective is holding
ripple only; every mandatory peak constraint remains a hard limit.

Wrap motor_10p12s_kit's gamma-5d queries and curve reductions, applying theta+d
and 1/3 weights once. Eleven unique slice sweeps cover J0 plus five phase
offsets at each of J10 and J15 for all three skews. Do not interpolate missing
peak curves, average peak and holding objectives, substitute 8p24s, or use
ordinal geometry coordinates. Group TRAIN/heldout by physical geometry.

Reuse the #1275 retained-worker pattern via existing main primitives. A new
generic worker refactor would overlap active lanes and create an unnecessary
dependency; copying solenoid physics would be incorrect. A local wrapper and
worker can be removed independently; raw slice TRAIN schema stays unchanged.
Supersede motor_pilot_kit.py and motor_pilot.py if a later registered observer
or job law changes. Data Collection supplies physical export, reference
adequacy/uncertainty and strongest cheap method; owner adopts law/P/Q/w and
grants. Synthetic stand-ins cannot enter public execution. No scientific
claim, reference acceptance or production authority is created.

Equal-budget replay charges each complete geometry's eleven sweeps once,
yielding the best reference-feasible skew (or UNRESOLVED when a sibling is
unsettled). The registered 6/12/24 geometry ladder therefore does not charge
three times for one slice bundle. Screening ranks collapse from raw actions
to first-occurrence geometry order; raw unsafe-pick/learning diagnostics retain
the initial specific skew action. No cross-geometry free cache is assumed.
Physical geometry identity compares exact numeric coordinates in fixed grammar
order. JSON integer/float spelling cannot create a distinct geometry or bypass
TRAIN/heldout separation. No tolerance, rounding or approximate equivalence is
introduced; this supersedes byte-spelling comparison within the working worker.
The worker places both fit and inference on `jax.devices("cpu")[0]` through
`jax.default_device`, so a local GPU cannot silently escape CPU accounting.
Public execution cannot inject an alternate trainer; stand-ins belong only
to the explicitly marked fixture path. The shared recipe itself is unchanged.

Operational DOCUMENTATION_LAG: PKT-09's conditional USD77.20 scenario exceeds
the existing shared launcher's USD50 per-run guard. Job-spec generation takes
explicit operator minutes/rate/cap, validates the standing guard unchanged,
and includes the export tail in 64 hours. No defaults, automatic split, shorter
scientific question, or larger grant is selected. A lower authorized quote/
complete duration fitting both caps can run; otherwise that cloud sub-scope
remains HOLD for the operator/owner. Local retained-data execution is independent.
