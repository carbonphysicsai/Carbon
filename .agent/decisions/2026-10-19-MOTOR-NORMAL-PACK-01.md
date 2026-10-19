# Motor normal-construction evaluation pack: public roles

Packs lane (Data Collection), 2026-10-19. Base `8f5170177` (F08 guard, which
carries the Motor/Cooling material `09e18dcb` and its guard `76844e88`).

**Problem.** The receiver binds an opted-in pack to the construction material:
its `construction_kit`, `interface` and `physics_contract` must equal the
material's documents, and its `train` must equal the material's TRAIN bytes
(`direct_receiver._pack_check`). The 18 Oct Motor pack (v4) carries the older
counted-dual kit, an inline interface and the native JSONL. A model built
through the normal path on the five-field kit and the NPZ derivative would be
refused with `evaluation_pack.construction_mismatch` / `train_mismatch`.

**Decision.** `carbon/challenge_kit/physical_pack.py` builds every public role
from the same source-owned functions as the construction path:
- `construction_kit` and `interface` from `physical_public`;
- `train` from the pinned NPZ.

Four reviewed files are committed byte for byte under
`carbon/challenge_kit/data/`, each with its sha256 pinned:
- the scorer's Motor physics contract (`74e3f30c…`);
- the scorer's G1 measurement contract (`8f374907…`);
- the counted-pack limit document (`3b532c6e…`);
- the counted-pack objective document (`cfc30f1e…`).

`physics_contract()` is exposed so the receiver's Motor material can carry the
identical document. Private roles are written HUMAN_INPUT. No value, threshold,
reference or private payload is created or moved.

**Evidence.** The receiver's own `_pack_check` accepts the sealed pack against
the construction material, and refuses a changed kit, physics contract or train.
Edited role bytes after sealing are refused. 9 focused tests and the existing
physical material/guard tests: 52 native PASS. Black 26.5.1 and Ruff 0.16.3 are
clean. Canonical is pending.

**Not earned.** No model, EVAL, score or qualification. The receiver does not
yet register Motor as a direct Challenge, which is construction-lane work.
Private roles are a separate custody decision.
