## 2026-10-06 — OWNER-TESTNET-V2-SWITCH-01: v1 frozen as EV5's archive; testnet moves to the v2 deployment

**Authority.** The owner, 2026-10-06: "approve those", relayed by the Test
Lead. Recorded by the Carbon Validator session.

1. **v1 is frozen.** The v1 testnet deployment (`battery-validator`) is
   frozen as EV5's archive. It holds EV5's sealed confirmation batch (journal
   sequence 14, OWNER-EV5-FREEZE-01).
   - It is never run, `operate upgrade`d or used as a weight source again
     without a new owner record.
   - Its configuration carries `"archived": "OWNER-TESTNET-V2-SWITCH-01"`. A
     writable start, `operate upgrade`, and `testnet_winner_publication`
     refuse it (`evaluation_config_archived` / `WEIGHT_SOURCE_ARCHIVED`).
   - Read-only use stays possible, so EV5 can still regenerate its pinned
     batch.
2. **Testnet moves to v2.** The v2 deployment (`battery-validator-v2`:
   rule v2, its batches already prepared) becomes testnet's deployment
   (programme state row 19: held → active).
   - It adopts the released image and implementation 2.0 by `operate
     upgrade`, once #684 and the TORCH-GPU-01 work merge.
   - It keeps the testnet 567 identities.
3. **Later:** testnet's batch production moves behind the Hetzner producer
   (VALIDATOR-19 S1 onward, import-only `batch_source: "answer_key"`).

**Where.** `docs/development/BATTERY_TESTNET_PROGRAMME_STATE.md` row 19, and
`docs/development/BATTERY_VALIDATOR_SERVICE_RUNBOOK.md` §4.4 (the
switch-over steps).

**Unchanged.**
- No chain transaction is made here.
- The weights rule stays OWNER-TESTNET-WEIGHTS-01.
- Security acceptance stays the owner's (AGENTS.md §13).
