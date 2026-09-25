# BATTERY-TESTNET-M1 — Battery construction contract (per-Challenge contracts)

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** OWNER-BATTERY-TESTNET-01 (OD-1, OD-8), OWNER-CONSTRUCTION-DECLARATIVE-01,
OWNER-CONSTRUCTION-ESCALATION-01, OWNER-DX-03.
**Detail:** `docs/development/DECLARATIVE_CONSTRUCTION_MAP.md` ("Per-Challenge contracts").

## Scope

Register the battery Challenge and its declarative vocabulary, make construction
contracts per Challenge, and give an honest per-Challenge answer to "can I
submit this?". No exam, scoring rule, threshold, chain action or paid work.

## Definition of Done

- [x] Battery Challenge identity and vocabulary are registered. The kNN and MLP
      families, and the declared construction choices, are promoted into
      `carbon/battery/`. The math is KEPT and held bit-identical to the
      campaign recipes.
- [x] Per-Challenge contracts: one registry and one compiler. Each Challenge
      resolves only its own contract. A Burgers family is refused under battery
      by name, and the reverse.
- [x] Catalogs derive from the registry. The historical session and GPU lane
      family lists come from registry lanes.
- [x] `dry_validate` is closed for every Challenge through
      `validate_for_challenge`: unknown Challenges, families and fields are
      refused by name.
- [x] Applicability of FNO, DeepONet, Transolver, Haar, GNO and GINO for battery
      is assessed and recorded as research-only, with reasons.
- [x] A contract digest per Challenge version is recorded in check-design and in
      candidate records. A mismatch is refused by name.
- [x] Tests:
  - declarative only;
  - every surface changes behaviour;
  - the same seed gives the same weights;
  - Burgers is unchanged;
  - a digest mismatch is refused.

## Handoff to later milestones

- **M2:** the exam module, truth service and seed service.
- **M3:** the validator daemon calls `compile_submission(...,
  contract_digest=...)` on admission.
- **M4:** packages the pinned public material into the GPU image.
- **M5a/M5b:** carry the Challenge selector and the contract digest into the
  Launchpad submission path (M3a commitment).
