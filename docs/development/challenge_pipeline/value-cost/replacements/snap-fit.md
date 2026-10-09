# Tolerance-aware snap-fit assembly — f08 candidate 3

**Strongest cheap baseline first:** BASF's analytical **and parametric 3D FE**
Snapfit app, plus a fitted force/strain response surface and exact bank lookup.
Do not benchmark only elementary beam formulas. BASF advertises answers in
seconds: plain cantilever sizing is a likely **V4 failure**. DEVELOPMENT /
SPECIFIED; [common contract](README.md), no replacement or safety adoption.

## V1 — real assembly decision

Buyer role: polymer enclosure/trim design engineer choosing a latch profile
that an assembly worker/machine can insert, that retains the mating part, and
that stays below the approved material-strain limit across geometric tolerances.

[BASF's Snapfit documentation](https://ultrasimweb.basf.com/snapfit/blog/introduction/)
supports insertion, extraction and strain decisions with analytical and FE modes.
[Stefanoaea, Rusu and Pascu (2024)](https://etasr.com/index.php/ETASR/article/view/6715)
independently study assembly/retention FE and note convergence trouble when
snap motion becomes dynamic. Their reinforced-polymer model is an analogue,
not a transferable material law for Carbon. A custom curved latch in a finite-
compliance housing is a candidate only if actual buyers use it; do not invent
complexity to escape the seconds-fast incumbent.

## V2 / V3 — scenarios, not traction

ASSUMPTION engineer effort 1 / 4 / 10 h per latch revision, rates
60 / 90 / 120 EUR/h: **60 / 360 / 1,200 EUR** gross effort at stake.
ASSUMPTION cohort 5 / 20 / 50 teams × 12 / 60 / 150 revisions/team/year:
**60 / 1,200 / 7,500 design decisions/year**. Sources establish the recurring
geometry/force workflow, not annual counts. Each changed latch/assembly
tolerance brief is one decision; not each latch on a shipped product.
Ask buyers for revision/assembly-force logs and avoidable engineer effort.
No tool re-cut, recall, injury or productivity improvement is monetized without
evidence. Actual benefit may be zero.

## Supported step and reference

Geometry actions: hook/lead-in profile, local fillet and compliant housing/latch
dimensions. Four stated tolerance/friction/service-condition strata; approved
material strain and assembly/retention force requirements remain HUMAN_INPUT,
as do material/rate support and P/Q/w. Preserve all hard limits. Outputs are
full signed insertion/removal force-displacement and critical strain histories,
not averaged peak safety errors. Exclude repeated-cycle fatigue, creep and
fracture; those remain the buyer's validation obligations.

Open route: [CalculiX](https://www.dhondt.de/) 3D geometric/material nonlinear
contact, controlled assembly/removal programme. Static continuation must
actually traverse the force drop; otherwise a properly energy-checked dynamic
route must be registered and repriced or the candidate rejected. No incomplete
pre-snap curve may count as success. Immutable source/image/material/deck and
extractor pins pending. Matched buyer Abaqus/Ansys/BASF deck: Tier 2 target only.

## C1 / C2 estimates and falsification

Complete case includes insertion **and removal**, mesh/extraction and every
increment. Hypothesis CPU-h 0.02 / 0.06 / 0.20 (1.2 / 3.6 / 12 CPU-min);
RAM 1 / 4 / 12 GiB. 24 × 4 = 96 primary, 32 twice-cost refined, 20 failures,
8 two-tool witness pairs: 196 equivalents. C2 **22.91 / 35.69 / 80.43 EUR**
under [common assumptions](scenarios.json); dynamic resolution may exceed it.

Carbon could plausibly help only if the permitted non-beam housing/contact
interactions defeat both the vendor tool and ordinary fitted surface at the
accepted quality/latency. Compare whole designs, full curves and retained
verification fairly. Reject if BASF's FE mode already solves the job in seconds,
if transient/rate adequacy is unsupported, or if a real buyer does not need the
extra scope. Ranked third: genuine high-repeat assembly work, but strongest
incumbent and nonlinear convergence risks, not an asserted model advantage.
