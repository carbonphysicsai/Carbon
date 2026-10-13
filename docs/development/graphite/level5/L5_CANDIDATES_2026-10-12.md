# Level 5 candidates from the first hunt (2026-10-12)

**Proposals only. Adoption is the owner's.** Level 5 is not built: no op, kernel, image or host exists for it, and nothing in
this page changes what a miner or a Level can do. The security sign-off for running Attacker code on disposable hosts, bounty
terms, licensing and per-run Level 5 grants all stay `HUMAN_INPUT` (OWNER-LEVEL5-INTERNAL-LANE-01).

## In one paragraph

The hunt asked Graphite's builders where today's Levels stop them from building real physics into a model. They named **three
ideas** (four filings: one idea was filed twice). All three are about making the model obey a law it should obey. The cheapest to
open is a **monotone capacity fade** (capacity can only go down as the cell ages). Next is a **physics-aware loss** (teach the
model what matters in the charge curve). The most expensive to contain is a **second-order optimiser** (a better training
finish). Every gain below is **the agents' own claim and is UNMEASURED**: nothing here shows it would help a buyer yet.

## Read this before relying on "nothing else was found"

The hunt had a tooling gap. The wish line is only counted if it sits at the start of a line, and the agents wrote theirs at the end
of a sentence, so the log captured none of them live; the four below were recovered afterwards from the stored proposals (parser
fixed in #1223). Only the third run (Level 3) ran with a physics theme; the first two ran without one (their session records name none). So a missing idea is **not
evidence that none exists**. The next run (H4, Level 4, lane G, after the Level 4 grant) goes with the `causal-structure` theme, and
every hunt run from now on is launched with a theme: that theme asks whether a model's prediction at time t can use only the
charging steps up to t, which none of 100 real battery models did (research #1193).

## The candidates, best first

Ranking is a judgement, not a measurement: what a buyer would plausibly value against how hard the change is to contain. It uses
only what the agents stated and what the registry shows.

### 1. Monotone capacity fade (filed twice: Level 1 and Level 2)

- **What a miner could build.** A capacity curve that is non-increasing by construction (each checkpoint falls by a non-negative
  step), so a model can never predict a cell getting its capacity back.
- **Why it matters first.** It is plain maths on a quantity the reference data already obeys (the agents report capacity falls in
  every training case), and capacity was the largest error component the Level 2 run reported (0.0786).
- **How we know it was blocked.** The registry lists `physical_structure.structure_layers` as research-only and "not designed yet";
  the Level 2 run found only an unconstrained fade head.
- **Expected gain (the agents' claim, UNMEASURED).** Removes predicted capacity increases and shrinks the dominant capacity error,
  especially with few training cases.
- **What must be true before opening it.** Plain maths becomes an allowed op or block: Carbon implements it, checks it is
  deterministic and counted at its true cost, runs the Level 4 attack suite on it, and ships it in a versioned image tied to a new
  Challenge version (nothing changes mid-competition; old results stay bound to their toolkit).

### 2. Physics-aware loss expressions (Level 1)

- **What a miner could build.** A training objective that weights the parts of the charge curve that matter (the transition into
  constant-voltage charging, hot-cell behaviour) instead of only an overall time weighting.
- **How we know it was blocked.** The Level 1 documentation lists `objective.loss_expressions`, but the dry validation answers
  `parameter.not_rebuildable`: the freedom the level documents is not served. This one may be a gap in what Level 1 already promises,
  which makes it the first thing to check. Related committed work: `docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md`.
- **Expected gain (claimed, UNMEASURED).** Encodes ramp alignment and high-temperature robustness directly in the objective.
- **What must be true before opening it.** It is declarative (no code), so the checks are: the rebuild is deterministic, every term
  is counted at its true cost, the attack suite covers the loss-expression families, and the version is tied to a new Challenge
  version.

### 3. Quasi-Newton polish (Level 3)

- **What a miner could build.** A second-order finish to training (a self-scaled BFGS or Broyden step with a chosen line search)
  instead of the memory-limited L-BFGS available today.
- **How we know it was blocked.** The run asked for `parameters.quasi_newton_family` and `parameters.line_search`; both were
  refused as unrecognized, although the Level 3 additions list them.
- **Expected gain (claimed, UNMEASURED).** A better-conditioned full-batch polish on a smooth objective of 400 cases.
- **What must be true before opening it.** It is a solver-like loop, so it gets a hard rule (training only, never at inference),
  every iteration is counted at its true cost, results are checked for determinism across backends and GPU device classes, and the
  Level 4 attack suite runs against it before it ships in a versioned image.

## What this page does not say

It does not say any of these will improve a model: the gains are claims. It does not open a freedom, schedule a Level 5 run, or
accept any security risk. The refused-capability log (`docs/development/graphite/level4/REFUSED_CAPABILITY_LOG.md`) holds the four
filings with their proposal ids; the next step the plan proposes is the themed Level 4 hunt, then the owner decides what, if
anything, to build.
