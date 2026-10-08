## 2026-10-07 — BATTERY-DEV-DISPATCH-01: one dispatch for battery's development rebuilds

**Authority.**
- **The lesson.** BATTERY-L3-NUMERICS-BUILD-01's lesson: a development level
  must never be silently rebuilt as Level 0, so the dispatch gets one shared
  helper before more levels land.
- **The order.** The Test Lead's build order (2026-10-07). This is an
  engineering refactor, and no behaviour changes.

**Decision.**
- **One module.** `carbon/battery/development_rebuild.py` is the one router for
  development records (Levels 1-3):
  - `record` finds a construction's record;
  - `kind` names its level;
  - `stage` gives the program, files and trainer;
  - `rebuild_label` gives "rebuild: CPU-verified only";
  - `build_in_process` builds the model.
- **The four call sites** now call it instead of branching per level:
  `worker.CarrierBackend.reconstruct`, `DirectBackend.reconstruct` (one
  `_rebuild_development`), `battery_scoring.built_from` and
  `daemon._development`.
- **What stays the authority.** Each level's own module still owns its
  staging. Level 1's programs (validator and pod) are passed in unchanged.
- **Level 0** passes through untouched.

**Tests.**
- `tests/cpu/test_battery_development_rebuild.py`:
  - Level 0 passes through;
  - each level's record is found and never read as Level 0;
  - defaults and off switches are Level 0;
  - Levels 2 and 3 replace the build line.
- **Existing suites, unchanged and passing (199):** the Level 1, 2 and 3
  suites, the Graphite hidden-L1 and development-level suites, the variants,
  the Level 1 attack adapter, the development-variant invariants and the
  battery validator daemon.
