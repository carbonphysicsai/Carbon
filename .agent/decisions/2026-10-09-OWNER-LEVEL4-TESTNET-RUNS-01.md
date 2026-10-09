## 2026-10-09 — OWNER-LEVEL4-TESTNET-RUNS-01: live Level 4 runs on testnet

**Authority.** This is the owner's own decision. The owner gave it directly
in the Level 4 engineer session on 2026-10-09:

> I approve level 4 runs on testnet. This is testing

It answers a question that set out the scope below, testnet only, and asked
whether the approval also covers running submitted graphs in the isolated
rebuild worker on testnet. Earlier the same day the owner gave the same
direction to two other sessions:
- to the Test Lead: "I approve level 4 runs. This is testing";
- to PR Head: "I approve all Level 4 testing. Results will unlock mainnet".

This record rests on the direct answer and quotes the others as context.
Recorded by the Level 4 engineer session.

**Decided.**
1. **Live Level 4 runs on testnet.**
   - Battery's development Level 4 variants (graph only, `battery-l4-graph-*`)
     may run live on testnet. That includes Graphite stage C.
   - The runs go through the development-ladder deployment (VALIDATOR-25)
     and the development door.
   - On those runs, Carbon builds and trains submitted graphs in the
     isolated rebuild worker (`CarrierBackend`, the reconstruct program).
     They are compiled under G5's accepted development and testnet profile
     (OWNER-L4-G5-COMPILE-ISOLATION-01).
2. **The ladder's Level 4 slot may open on testnet.** The validator's
   `ladder_level_4_not_open` refusal (VALIDATOR-25 slice 4) may be lifted
   for the development-ladder deployment on Carbon's testnet. The validator
   owns that change.

**Not decided, and unchanged.**
- **Mainnet stays closed.** The ladder's testnet-only refusal
  (`evaluation_config_ladder_testnet_only`) and G5's mainnet block remain.
  The owner's words to PR Head make mainnet a later step that the testing
  results inform; nothing here opens it.
- **No security qualification.** This approves testnet runs. It is not
  production security qualification, a mainnet isolation acceptance or a
  claim of secure execution.
- **No lock.** No level is locked and no frozen rule changes. Level 4 is
  not served to miners on any miner-facing contract.
- **No value changes.** The owner's caps, bounds and deadline stay as set
  (OWNER-L4-VALUES-01). The loss slot's aux limit stays `HUMAN_INPUT`.
