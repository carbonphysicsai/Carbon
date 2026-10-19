# F08 near-feasible public pilot: solver evidence (2026-10-19)

**What this set is.** The raw judged output of RR-PACKS-03, the owner-released run of the
frozen plan `docs/development/evidence/reference-solvers-2026-10-15/plans/f08-near-feasible-public-pilot.json`
at code `67dafcf3` on a Targon VM. It covers eight TRAIN-informed near-feasible geometries at
mesh h = 3, 2.25 and 1.7 mm (24 CalculiX solves).

**What it supports.** Eight **accepted public DEVELOPMENT decision references** for F08.
- **Judges:** the existing ones, run inside the plan's `observe` step: `f08_deck.convergence`
  and `f08_freeze.bank_mesh` under the F08-SCIENCE-VALUES-01 bands.
- **Results:** all 24 mode ladders PASS, all 8 geometries converge to the h = 1.7 reference, and
  the bank mesh passes. Every deck matched its pinned manifest (`deck-verification.json`).
- **Review:** the Carbon Validator accepted these references on 2026-10-19 (physics review in
  `codex-queue/reports/PACKS_F08_SOLVER_RESULT_20261019/README.md`).
- **Use:** `carbon/challenge_kit/physical_pack.py` reads `observed.json` (sha256-pinned) as F08's
  evaluation-pack bank.

**What it does not support:**
- **Not a feasibility test.** All eight references are feasible with wide margins, so the set
  tests **ranking only** (`RANKING_ONLY_NO_FEASIBILITY_BOUNDARY`). It cannot show a
  false-feasible pick.
- **Not an independent population.** The geometries are a TRAIN-informed local neighbourhood.
- **Not a qualification, a model result or a LIVE claim.**

**Files:**
- `observed.json`: per-solve verdicts and summaries, the judges' output.
- `deck-verification.json`: the manifest check.
- `pod-phase.json` and `pilot-pod-phase.json`: phase results.
- `pod-environment.json`: host and solver binary digests.
- `payload.json`: the run payload identity.

The `cost.host_profile` label inside `observed.json` reads `runpod-cpu-pod-native` because that
is the observer's fixed label. The run itself was on a Targon VM.
