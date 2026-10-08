# LAUNCHPAD-ACCEPT-01: real end-to-end acceptance of the miner Launchpad

**Authority.**
- The owner, 2026-10-07, through the Test Lead: be "super confident" in the
  Launchpad before launch.
- The owner, 2026-10-07: "I want our testing running through launchpad as
  soon as it can like it will on mainnet."

**Status:** SPECIFIED. The plan is
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`; no cell has run.

**Scope.**
- The acceptance matrix (plan §3).
- The fresh-machine install run (plan §4; C-MLP-04's acceptance).
- The real submit-to-verdict path through rehearsal 3a (plan §5).
- Moving test traffic onto the Launchpad (plan §6).

**Wire-in gaps, each its own ticket and PR:**
- LAUNCHPAD-ACCEPT-02: the commitment op;
- LAUNCHPAD-ACCEPT-03: the receiver-hotkey check;
- LAUNCHPAD-ACCEPT-04: the testnet submit target and verdict readback;
- LAUNCHPAD-ACCEPT-05: the research share check at the launch door.

**Definition of done.** Plan §3.6's completion predicate holds, with every
cell's evidence under `docs/development/evidence/launchpad-acceptance-<date>/`.

**Boundaries.**
- No spend without an owner-approved grant.
- Carbon rents and bills no miner compute.
- Keys by file path only.
- Signing, registration, commitment confirmation and everything on the AX42
  are the owner's.
- No hidden material.
- Testnet 567, DEVELOPMENT, device class CPU.
- Engineering evidence only: passing qualifies nothing.
