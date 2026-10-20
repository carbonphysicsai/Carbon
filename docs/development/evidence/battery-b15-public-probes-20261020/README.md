# Battery B15 public DEVELOPMENT probe plan (2026-10-20)

**What this is.** The probe plan the adopted B15 gate (OWNER-PHYSICS-GATES-01,
`carbon/battery/physics_gate.py`) reads on the exposed DEVELOPMENT bank. Until now no plan was
committed, so the gate could not run and Battery stayed unscored.

**Where it comes from.**
- **The generator** is `scripts/dev/battery/b15_public_probes.py`. It is the
  PHYSICS-CALIBRATION-01 generator, `physcal_plan.py`, which built the plan B15 was screened
  on, run under a new public seed.
  - It draws 100 uniform base points from the probe region, each kept below its upper edge by
    the screen plan's largest move along that input, in the same draw order.
  - Each base gets one c1 and one c2 partner, moved up by B15's 0.05 step.
- **Proof it is the same generator:** with the screen's seed `physics-calibration-01` it
  reproduces the screen plan's 100 bases exactly (tested).
- **Count:** 200 pairs, 100 per axis. That is what the gate was screened at
  (`physics-contract-01/physics-screen-pairs.json` → `pair_cache_provenance`: pairs_per_base
  100, plan `83d7ddce…`). It is not a new value.
- **Seed:** `carbon-battery-b15-public-development-20261020`.
  - It is recorded in `provenance.json`, because the gate accepts a plan with exactly
    `schema`, `contract_sha256` and `pairs`.
- **Disjoint from the screen plan:** 0 shared pairs and 0 shared input points against every
  job of the screen plan, checked against its committed public copies.

**What it is not:**
- No reference solves are needed; the gate reads only model predictions on these pairs.
- It is not the sealed exam's private draw.
- It is not a qualification, a model result or a LIVE claim.

**Files:**
- `plan.json` (`carbon.battery.physics-probes.v1`) and `provenance.json`.
- `screen-plan-physics-calibration-01.json` (`83d7ddce…`) and
  `screen-jobs-physics-calibration-01.json` (`eebb8066…`), the public screen plan and its job
  inputs. These are copies of `physics-calibration-01/` from Data Collection's public inputs.
