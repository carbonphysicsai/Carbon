# OWNER-CONTAINMENT-ACCEPT-TESTNET-01: owner security acceptance for testnet and rehearsal

Date: 2026-10-21
Status: APPROVED by the owner, directly in the Carbon Validator's session. The owner selected both items, and the question named them explicitly as security sign-offs recorded as the owner's.

## Accepted (scope: DEVELOPMENT, testnet and rehearsal only; not mainnet)

1. **Intake containment bounds for allowlist v7 versions** (Test Engineer `ab1a35f732822e3eecde533d92f808384d744301` on `387dc6c8196e2c9b9826bc8515ce41fa205c32ca`):
   - 64 MiB per graph document and 192 MiB per submission;
   - parse within 120 s and 4 GiB;
   - graph nesting depth at most 256 (`graph_call_depth_containment`, REFUSED).
2. **The miner sandbox for testnet and rehearsal,** based on the containment evidence:
   - Run F passed, 175 tests and the bounded real lane;
   - head `5882b62ce841482c28df837cc4c7e70ecab201a2`;
   - the landing real-lane run on images built from tree `fce94da2834a2b1ae3210bd10e60c56b391acf3e`;
   - `CONTAINMENT_VM_RUN_RESULT_20261020.md`.

   The owner accepted this without a separate human review of escape paths.

## Not accepted here

- **Mainnet:** that needs its own acceptance on the mainnet validator class, which is TBD until launch.
- **The rows the containment runs didn't cover:**
  - row 1, weights hidden in permitted source;
  - row 4, the G6 finding;
  - the cause of memory exhaustion.
- **The python-cpu (jNO) worker parent:** it still needs its own real-lane containment run before this acceptance covers it.
- **Any later change** to the sandbox, the images or these bounds: that's a new acceptance.

## Also approved in the same answer (not security acceptances)

- **Raising worker resources so large models (PROSE) can run.** The Validator returns with a specific figure and its cost before anything changes.
- **A sized and priced GPU test plan** for the mainnet validator decision, which the Validator drafts.

## Confirmed again directly

The owner confirmed this acceptance again, directly in the Test Lead's session on 2026-10-21 ("I approve and accept 1 and 2"), with the same scope: testnet and rehearsal only, not mainnet, and not the jNO python-cpu parent.
