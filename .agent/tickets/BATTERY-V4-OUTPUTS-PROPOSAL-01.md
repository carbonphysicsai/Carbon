# PLT-02 — BATTERY-V4-OUTPUTS-PROPOSAL-01

Status: prospective implementation/test candidate. Reviewer: Carbon Validator.
Owner assigned this Platform queue item on 2026-10-12. One independent PR to
main, starting at `726c2cfc4ce9f250567bb7624dbe64d1a3293ce1`.

Authority: queue item; PHYSICS_CONTRACT_01_DRAFT.md §3.2; constitution,
scientific canon, invariants, current delivery/delegated-decision protocols;
BATTERY-TESTNET-M2; existing reference SPEC and truth-environment lock.

KEEP the pinned reference simulation, its solver tolerances, existing v3
extractor and training modules. WRAP simulation construction in reference_v4.py
and existing truth isolation/provenance in a dedicated solve-v4 route. Add a
new prospective output contract and record schema in outputs_v4.py, without
registering a Challenge version, migrating a model, changing scoring or
rewriting old records. v4 files bind a sidecar identity; both routes refuse
the other schema's files.

Quantities: current_a(t), heat_w(t), soc(t), alongside the four historical
outputs, on 121 points from 0 to 3600 s. Current keeps PyBaMM's positive
discharge sign. heat_w is signed total heating. soc is explicitly nominal
capacity coulomb counting, using the solver's discharge-capacity variable and
its published nominal-capacity parameter, not a qualified ageing-aware SOC.

The proposed charge identity includes the sign and seconds-to-Ah conversion.
B13 needs a registered thermal parameter contract. B14 needs an explicit
irreversible/reversible heat decomposition; signed total heat alone is
insufficient. All law adoption, tolerance and Challenge registration fields
remain HUMAN_INPUT. The Validator/owner must review those scientific seams.

Tests: exact fixture extraction/sign/units/grid, malformed or truncated
outputs, one-solve extraction, typed solver/infra failures, prospective
record identity, append-only resume, v3 refusal and explicit offline container
route. Run the canonical focused suite with science-jax/chain groups, existing
truth-service/construction regressions, invariants, quality/package checks
and the exact-head CI/Merge gate. Real PyBaMM solves are not fixture evidence.

Historical map_ref SYSTEM/AGENT-EXECUTION; the current protocol retires Hub
maintenance. No Hub changes. Ceiling: DEVELOPMENT SPECIFIED/IMPLEMENTED/TESTED
only for recorded evidence; scientific/security/production qualification and
LIVE remain unavailable. No merge or approval by this session.
