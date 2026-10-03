## 2026-10-03 — OWNER-EV5-FREEZE-01: EV5 frozen; H3 frozen unchanged; the confirmation batch sealed from the testnet validator's deployment

**Authority.** The owner, 2026-10-03, in the EV5 freeze session:
- On the confirmation batch's source: "use the one the testnet validator runs
  on".
- Asked whether to freeze now, which closes the SciML lead's window to amend
  H3 (EV5 §8 item 3): "SciML lead approve received".

1. **H3 frozen unchanged.** The SciML/technical lead approved the proposed
   localized measurement as it stands: near-limit false acceptance
   (`carbon/battery/value/false_acceptance.py`), descriptive, with no cutoff
   (OWNER-EXEC-APPROVALS-01). The amendment window in EV5 §8 item 3 closes at
   the freeze.
2. **Confirmation batch.** It was sealed on the operator host by
   `python -m carbon.battery.value.ev5 seal-confirmation` (#543), from the
   testnet validator's deployment (v1). The v2 deployment is held
   (programme state item 19) and was not used.
   - Role `ev5-confirmation`: 120 cases and 4 hidden duplicates.
   - Fingerprint
     `sha256:0add08ed7a3c6568a0779b0becb123578eedee6ca8e4f9f014588ed4ba934f3e`.
   - Journal sequence 14.
   - Newly committed, never recorded in the testnet pool.
3. **EV5 is frozen**, before any EV5 solve. `python -m carbon.battery.value.ev5
   freeze` wrote these once:
   - the contract, `carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json`;
   - the reference and panel plans, `docs/development/evidence/ev5-2026-10-03/plans/`;
   - the freeze manifest, `docs/development/evidence/ev5-2026-10-03/freeze-manifest.json`.

   The manifest pins the pre-registration, the study sheet and H3's module by
   digest.
4. **Where.** `docs/development/BATTERY_ENGINEERING_VALUE_EV5.md` (status, §4
   H3, §8) and `docs/development/BATTERY_TESTNET_PROGRAMME_STATE.md` item 24.
5. **Unchanged.**
   - Nothing is dispatched.
   - Spend stays under OWNER-EV5-CAP-01 (USD 6, inside the USD 25 L0 cap).
   - The private cases are solved on the operator host only (OWNER-EV5-Q3-01).
   - A rung pass still needs all three verdicts and the owner's signed lock
     (OWNER-TRACK-A-L0-02).
   - No qualification, chain, reward or testnet-rule change.
