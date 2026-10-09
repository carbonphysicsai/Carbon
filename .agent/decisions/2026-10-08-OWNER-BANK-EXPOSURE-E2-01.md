## OWNER-BANK-EXPOSURE-E2-01: battery's pool bank exposure E = 2

**Authority.** The owner, 2026-10-08, relayed by the Test Lead: "approve if
you agree". The Test Lead agrees. The aim is a shorter score-release lag:
VALIDATOR-29 releases a window only when every case it drew has retired and
been published, and a case retires after E draws.

**Decided:**
- **battery's pool bank:** E (`bank.pool.retire_at`) is 2, down from
  OWNER-BANK-ARCHITECTURE-01's cheap-class testing value of 5. It is a
  development testing value.
- **the design (Q3) bank:** E is unchanged, until the cross-window power
  curves (#850) are in. Q3 detection accumulates evidence across windows,
  so a lower E there costs power.

**How it applies** (rule `v2-bank-e2`, VALIDATOR-23):
- **A new rule version, not an edit of `v2-bank`.** A deployment's seed pin
  binds its rule digest, and `operate upgrade` cannot carry a rule change.
  So a producer or validator moves to E = 2 by a new deployment naming
  `v2-bank-e2`. `v2-bank` and its deployments (including the running bank
  fill) are untouched.
- **The tranches carry over.**
  - A tranche's identity is its bank, role and cases, and its Merkle leaves
    are each case's id, inputs and reference. E is not part of either.
  - Exposure is counted when a window draws a case.
  - So the pool bank filled under `v2-bank` serves `v2-bank-e2` as it is,
    and no tranche is redrawn or re-solved.
- **Capacity:** at B = 2,000 live and E = 2, the bank serves about 40
  windows of 98 cases before top-ups (it was about 100 at E = 5). Top-ups
  draw new tranches from the deployment's root.

**Not decided here:**
- production values;
- the design bank's E;
- when the testnet producer and validators move to `v2-bank-e2` (an
  operator step, with its new deployments).
