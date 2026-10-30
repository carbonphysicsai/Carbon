# TRANSOLVER-ADMISSION-01 — Promote Transolver out of RESEARCH_ONLY, for one Challenge

**Status:** proposed; awaiting an owner decision. Nothing in this ticket
changes `Status`, `Blocker` or `BLOCKED` in `capability_registry.py` — only
the decision this ticket asks for can.
**Primary Hub map_ref:** `carbon/reconstruction/capability_registry.py` and
`carbon/reconstruction/_vendor/carbon_jax_lab/` are map_structural
(reconstruction profile / backbone map). This ticket file itself changes no
code, so `HUB_IMPACT_NONE` applies to the ticket alone; any implementation
slice below needs its own Hub reconciliation.
**Authority:** `Blocker.OWNER_DECISION`, as `capability_registry.py` already
marks `TRANSOLVER` (grouped with `FNO`, `HAAR`, `GNO`, `GINO` in `BLOCKED`).
This ticket cannot close itself — it exists to put the call in front of
whoever holds OWNER-CHALLENGE-ADMISSION-01 / OWNER-DEV-AUTONOMY-01 authority,
the same authority `MOTOR-NEURAL-01` (2026-10-10) used to move motor's `mlp`
and `deeponet` from nothing to `REBUILDABLE_DEVELOPMENT`.

## Why now

Carbon won Pitchtensor at Exploit Summit; more outside engineers are reading
this code than before. Three Challenge validators already treat Transolver
as a live reference point, not a stub:
- `carbon/battery/track_a.py` names `"transolver"` as the example of a
  backbone a miner cannot yet submit (`not_permitted_family`).
- `motor_scoring.py`, `battery_scoring.py`, `cooling_scoring.py` all call it
  out as a comparison baseline strategy.

So the team has already been comparing against Transolver internally while
no miner can select it. That gap is now visible externally too.

Separately, `carbon/development_session/library_bundles.py` has pinned
discovery snapshots for `THUML/Transolver_plus` (Transolver++) and
`THUML/Neural-Solver-Library` — candidates for a *later* port. Deciding the
base Transolver's status first avoids stacking three undecided architectures
on top of each other.

## What already exists (no new engineering needed to reach this point)

- A full JAX port: `carbon/reconstruction/_vendor/carbon_jax_lab/models.py`,
  the slice/attention/deslice core, attributed to THUML/Transolver (MIT) with
  declared departures (softplus temperature, optional quadrature weights,
  dropout fixed at zero).
- Full field mapping in `capability_registry.py`: `heads`, `slices`,
  `expansion` surfaces, all scoped to `TRANSOLVER`.
- The license question is already settled by the carve-out in the root
  `LICENSE` / vendor NOTICE — this is not an IP decision, only an engineering
  admission one.

`RESEARCH_ONLY` already permits a miner to explore Transolver in research.
The blocker is specifically on Carbon *rebuilding* it through a registered
DEVELOPMENT path, i.e. whether a miner's submitted recipe naming
`"transolver"` compiles and scores instead of being refused.

## What the owner is actually deciding

Not admission for an evaluation contract — `Status.ADMITTED` is explicitly
"never set by this registry" per its own docstring; that needs qualification
evidence this ticket doesn't supply.

The decision is narrower, matching `MOTOR-NEURAL-01`'s precedent exactly:
for which Challenge(s) — motor, battery, and/or cooling, the three that
already reference it — to move `transolver` from `RESEARCH_ONLY` to
`REBUILDABLE_DEVELOPMENT`, through the same shared JAX/PyTorch trainers,
with the same fail-closed refusals everywhere it isn't served yet, and the
same finite Level-0 catalog menu pattern.

## If granted: the slices (one PR unless a real dependency forces a split)

1. Decision record + Hub mapping (this ticket's successor, once an owner
   actually decides — quoting them verbatim, per `.agent/decisions/README.md`).
2. Wire `transolver` as a selectable backbone in the chosen Challenge's
   compile path, mirroring `carbon/motor/neural.py`'s pattern for `mlp`/
   `deeponet`.
3. Fail-closed refusals in practice and validator paths wherever the backend
   isn't served yet (`*_family_not_served`, `Unavailable`), same as
   `MotorPractice.backend_refusal`.
4. A comparison evidence table against the kernel-ridge baseline and
   existing neural families on public TRAIN/PRACTICE, before any further
   promotion is discussed.

## Open questions for the owner

- Which Challenge(s) first — motor, battery, cooling, or the Burgers
  contract where `capability_registry.py`'s `REGISTRY` already lives?
- Ship the vanilla Transolver core now and treat Transolver++'s
  improvements as a separate later port, or fold them in together?
- Should `Transolver_plus` and `Neural-Solver-Library`
  (`library_bundles.py` discovery snapshots) get their own tickets once this
  one resolves — not decided here, flagged for sequencing only.

**Note on evidence:** unlike `MOTOR-NEURAL-01`, this ticket carries no
practice-score table — it was written without running Carbon's training
pipeline. Whoever picks up slice 4 needs to produce that evidence before any
promotion past `REBUILDABLE_DEVELOPMENT` is credible.
