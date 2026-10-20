# F08 near-limit public evidence: exam ladder and TRAIN N1r (2026-10-20)

**What this set is.** The judged outputs behind F08 Challenge version 1.1. Two runs on Targon
VMs produced them, and each run first passed its own solver build's `f08_verify` (MMS and rod)
before any deck was frozen:
- **RR-PACKS-07**, with ccx `21edfdcb…`, produced the exam ladder.
- **RR-PACKS-07b**, with ccx `cf2fb358…`, produced the N1r TRAIN stratum.

In each run the decks were pinned before solving, and `*-ledger-check.json` records
pin = ledger = step record with zero refused decks.

**What it supports:**
- **The 1.1 exam (`ladder-*`):** eight lattice neighbours of pilot-0000, approved by the
  Validator on 2026-10-20.
  - Each was solved at h = 3, 2.25 and 1.7 mm; all are asymptotic and the h = 1.7 references
    converged.
  - 4 are safe and 4 unsafe at the 0.15 mm/N dynamic limit.
  - The smallest margin is 0.00286 mm/N, about 95× its h2.25 − h1.7 reference error.
  - Coverage is `RANKING_AND_FEASIBILITY_STRADDLE`, so the exam can now show a
    false-feasible pick.
  - `carbon/challenge_kit/physical_pack.py` reads `ladder-observed.json` (sha256-pinned) and
    checks its rows against `ladder-actions.json`.
- **TRAIN v2's near-limit stratum (`near-limit-0000…0031`):** 32 h = 3 mm solves from four
  frozen action batches.
  - 16 measured safe and 16 unsafe (worst dynamic 0.1238–0.1789 mm/N), which meets the
    pre-registered one-third rule.
  - `carbon/challenge_kit/f08_train.py` re-derives `f08-dev-train-287-v2.npz` from these files
    byte for byte. That artifact is v1's 255 rows unchanged, followed by these 32.
  - The `convergence` block in each `n1r-b*-observed.json` reads `INCOMPLETE_NATIVE_EXECUTION`
    because TRAIN rows are solved at h = 3 only. That is expected and is not a fault.
- **Mesh statement (carried in the kit):** F08 TRAIN is h = 3 mm and the exam truth is
  h = 1.7 mm. At the 0.15 mm/N limit, h3 reads about 0.07 % (about 1e-4 mm/N) lower.
  - The figure is measured on the 16 cases solved at both meshes (the 8 RR-PACKS-07 N1
    batch-0 spot-checks and the 8 ladder cases).
  - The shift is −0.000090 to −0.000131 mm/N, about 22× under the smallest ladder margin.

**What it does not support:**
- **Not an independent population.** The ladder and N1r are placed on purpose near the limit.
- **Not a hidden exam.** Every file here is public.
- **Not a qualification, a model result or a LIVE claim.**
- **RR-PACKS-07's first N1 stratum** (4/32 safe, which fails its one-third rule) is history,
  not TRAIN. Its outputs are not committed here.

**Files:**
- `ladder-observed.json`, `ladder-deck-verification.json` and `ladder-actions.json`.
- `n1r-b{0..3}-observed.json`, `n1r-b{0..3}-deck-verification.json` and
  `n1r-b{0..3}-actions.json`.
- `rr07-*` and `rr07b-*`: pod environment (host and solver binary digests), phase result,
  solver-build verification and ledger check, one set for each run.

Each observed row carries `cost.host_profile` = `runpod-cpu-pod-native`. That is the observer's
fixed label; the runs were on Targon VMs.
