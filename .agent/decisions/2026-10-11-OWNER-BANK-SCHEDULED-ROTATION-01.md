## 2026-10-11 — OWNER-BANK-SCHEDULED-ROTATION-01: battery's banks rotate on a schedule (B = 20n, E = 5, stride 3); testnet r360, mainnet r1080

**Authority.** The owner, 2026-10-11.
- **Relayed by the Test Lead**, on rule `v2-bank-e1-r360` (E = 1):
  > we shouldn't be constantly reloading the hidden test bank I thought
  > there was a batch rotation schedule

  and then:
  > Yes keep it that way for mainnet validation. We were just trying to
  > optimize test cadence. Let me know when validator has the correct
  > version for me to approve. I'm holding off for now
- **Directly in the Carbon Validator session**, choosing between the options
  the Validator laid out:
  > Batch rotation: option (1) active_batches=3 with stride 3, rotation r360
  > for testnet (r1080 for mainnet), E=5, B=20n, E_q=10. Build it as
  > v2-bank-sched in r8.

**Background.** OWNER-BANK-ARCHITECTURE-01 approved battery's bank at B = 20n
and E = 5. Uniform draws made a window's release wait for its slowest case's
E-th draw (about 16 days at E = 2). E = 1 removed the wait, but only by
reloading the bank every window. The publication lag came from uniform
draws, not from E.

**Decided:**
- **The scheduled rotation.** A case's E = 5 exposures fall in the windows
  `active_batches` = 3 slots apart (stride 3, one lane per kind). So they
  never meet in concurrently live windows, and each score still pools 3
  live windows of disjoint cases.
  - A lane's first window staggers its cases' budgets, so one group
    retires each window.
  - Each window then draws about n/E fresh cases.
  - A case due in a window that was never drawn is retired, never drawn
    late.
- **Publication:** a window's cases have all retired 4 strides after it, so
  it publishes about E × 3 rotations after it opens.
- **Testnet: rule `v2-bank-sched`.**
  - Rotation 360 blocks: about 5,400 blocks (~18 h) to publication.
  - B = 2,000 (20n), E = 5.
  - Q3 design bank: k = 8 questions a screening window, E_q = 10, the same
    schedule.
  - Both banks are refilled by the operator's timers, never inside a tick.
    A short bank leaves the slot unfilled (`bank_short`) and never reuses a
    case past its budget. `BANK_LOW` covers both banks.
- **Mainnet:** the same model at rotation 1,080 blocks. It is recorded here,
  not deployed: a mainnet deployment is its own decision.
- **`v2-bank-e1-r360`** stays registered for its history. Its sheet
  (`RELEASE_E1_VALV2.md`) is superseded and was never run.

**Not decided here:**
- the owner's approval to run the corrected AX42 sheet (he is holding);
- security acceptance;
- the rule-v3 score composition (VALIDATOR-26).
