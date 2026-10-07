## 2026-10-07 — OWNER-MOTOR-HIDDEN-POOL-01: hidden motor batches on the producer, for testnet

**Authority.** The owner, in the Carbon Validator session, 2026-10-07. Asked
which rule values motor's hidden pool should use, they chose "Mirror battery
v2 (Recommended)". The Test Lead's sequencing ruling of the same day is
motor first, then cooling.

It supplements:
- OWNER-SHARED-ANSWER-KEY-01;
- OWNER-VALIDATOR-MAINNET-PARITY-01;
- OWNER-REHEARSAL-AND-RELEASE-01;
- OWNER-DATA-MOTOR-01.

**Scope** (VALIDATOR-21):
1. **The producer** draws, solves once and seals hidden motor screening and
   finalist batches, under `producer.require_approval` pinned to this file.
   - Draws are uniform from motor's DEVELOPMENT population (Q = P), from the
     producer's own motor root.
   - Solves run in the image pinned by OWNER-DATA-MOTOR-01.
2. **Validators** import these batches through the answer key and score
   recipes on them with motor's existing exam, unchanged. Hidden material is
   never disclosed to miners.
3. **The hidden rule's values** are provisional DEVELOPMENT values, mirroring
   battery rule v2 (OWNER-BATTERY-SCORING-WINDOW-01):
   - **Rotation:** a fresh screening batch every **1080** finalized blocks.
   - **Active batches:** **3** live at once.
   - **Batch size:** **30** cases, at about 18 core-minutes per case.
   - **Per-hotkey cap:** one scored submission per hotkey per **360**-block
     window.

**Not granted here:**
- any qualification, LIVE, reward or production claim;
- releasing retired batches (HUMAN_INPUT, as for battery);
- motor's quiz or tuning set (Data Collection proposes, the owner approves);
- any change to motor's exam, gates, scales or population.

A different value needs a new owner record, and it applies prospectively
(invariant 10).
