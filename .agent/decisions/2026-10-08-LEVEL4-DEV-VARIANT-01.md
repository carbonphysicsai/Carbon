## 2026-10-08 — LEVEL4-DEV-VARIANT-01: battery's development-only Level 4 variant, graph-only

**Authority.**
- OWNER-LEVEL4-GRAPH-ONLY-01 (D1) adopts the proposal's §7. Its development
  row reads: "On the development-only Level 4 variant only: admissible as
  allowlisted graphs".
- OWNER-GRAPHITE-TEST-WAVE-03 §1 governs development variants.
  OWNER-GRAPHITE-DEV-LEVELS-01 F1 lets a variant widen to a surface Carbon
  drafts and the Test Lead reviews.
- The Test Lead's rulings for PR 8 (2026-10-08) set the scope:
  - the Level 4 capability is the surface itself: the allowlist, the constant
    caps, the compute budget and gates G0–G7, at maximum freedom;
  - this engineer drafts it, and the owner accepts;
  - Level 4 enters through the shared dispatch (BATTERY-DEV-DISPATCH-01);
  - G5 stays fail-closed.
- Engineering decision recorded by the Level 4 engineer.

**Seam classified.** OWNER-GRAPHITE-DEV-LEVELS-01 F2 says "Levels 4–5 are
refused until the security owner accepts isolation". It was written when
Levels 4–5 meant running participant code. D1 then defined Level 4 as
graph-only, where no participant code runs, and admitted a development Level
4 variant. Reading them together (NO_CONFLICT):
- the mechanism admits a **graph-only** Level 4;
- Level 5 stays refused;
- every compile or training of a submitted graph stays **fail-closed** until
  the security owner accepts the G5 profile (D3).

**Decision.**
1. **The mechanism** (`carbon/reconstruction/development_variants.py`).
   - `LEVELS` is `(1, 2, 3, 4)`.
   - A Level 4 document must widen exactly `hybrid.composition_graphs`, with no
     surface, and with bounds that pin `admission: graph_only` and an
     allowlist `{version, digest}`. Anything else is refused as
     `development_variant_level4_is_graph_only`.
   - `participant_code` stays `false`.
2. **The variant** is `battery-l4-graph-v1`, registered, pinned and recorded
   (`dev/0004.json`).
   - `carbon.battery.level4.variant_document` builds it, so the policy and the
     code can't drift apart.
   - Its bounds pin allowlist v1 (`level4-allowlist-v1`), the submission
     schema and gates G0–G7. The caps stay `HUMAN_INPUT`.
3. **The reconstruction** of `hybrid.composition_graphs` is the submission's
   digest, pinned with its allowlist. The documents arrive through the
   Launchpad slot (LAUNCHPAD-LEVELS-01) and are verified by
   `carbon.level4.intake`.
4. **Dispatch.**
   - `development_rebuild` routes a Level 4 record to `level4_worker` before
     any other level, so a Level 4 record is never read as Level 0 or Level 1.
   - Every rebuild fails closed as Carbon's environment, never the
     candidate's: the staged program and the in-process build raise
     `ImportError(level4_requires_security_owner_g5_acceptance_d3)`.
   - The rebuild label says so.
5. **The capability draft** is
   `docs/development/graphite/level4/LEVEL4_CAPABILITY_DRAFT.md`. It is not
   written into `level-4.json`, because that file requires Graphite as the
   proposer (OWNER-CHALLENGE-ROADMAP-03). The draft names two ways to file it.
6. **Graphite runners.** The carrier lane and phase 3 still refuse Levels 4–5,
   and the Attacker has no Level 4 adapter until the next slice. Level 4 runs
   through the Launchpad from Phase 3 (owner, 2026-10-07).

**Unchanged.**
- Miner-facing contracts still exclude `hybrid.composition_graphs`. Every
  miner door refuses the variant's digest
  (`tests/invariants/test_development_variants_unreachable.py`).
- No cap, bound, deadline or budget is chosen. D2–D6 stay open.
