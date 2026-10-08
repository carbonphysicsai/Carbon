## 2026-10-08 — OWNER-CANARY-MINER-01: a Carbon-owned canary miner, plan first

**Authority.** The owner, 2026-10-08. The Test Lead session relayed it
verbatim to the Launchpad Acceptance session:

> I approve the canary miner(s).

**Decision.**
- Carbon builds a canary miner. It drives the real path through the
  Launchpad every window: freeze, commit, submit to each live validator,
  a sealed verdict within a registered deadline, then the weights check.
- A stage that misses its deadline alerts through Ops 2.
- The plan comes first: `docs/development/CANARY_MINER_PLAN.md`, ticket
  CANARY-01.

**Not decided here.** The plan's §9 lists these as owner decisions:
- unattended commitment confirmation (SIGNER-AUTOCONFIRM-01);
- the canary hotkey;
- excluding canary scores from nomination, standings and weights;
- where it runs, and any purchase;
- the stage deadlines;
- the cadence.

**Unchanged:**
- every scientific value, gate and score;
- weights and settlement;
- OWNER-COMMITMENT-POSTER-01 D10, until an owner record amends it.

**No execution** happens through this record.
