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

**The owner's answers to the plan's §9, 2026-10-08.** The Test Lead relayed
them verbatim:

> approve canary 2-4

- **(2) The hotkey:** a new `carbon-canary` hotkey on its own coldkey, which
  the owner creates. It is not one of minerD–G, and not on the owner's
  coldkey.
- **(3) Excluding canary scores:** a registered canary list on the
  validator. Canary submissions are scored but never incumbent, in
  standings, weighted or promoted. The Carbon Validator builds it, under
  its own record, OWNER-CANARY-LIST-01.
- **(4) Where it runs:** carbon-fresh first, attended. The always-on box
  (CX23 class) is decided later.

**Still open:**
- (1) unattended commitment confirmation (SIGNER-AUTOCONFIRM-01), pending
  with the owner in the building session;
- (5) the stage deadlines, set from the first attended runs' measurements;
- (6) the cadence (one cycle per rotation, proposed).

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
