# OWNER-TESTNET-HOTFIX-AUTHORITY-01: standing authority for testnet hotfixes that don't touch scoring, exams, money or security

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "yes, hotfix authority." This answers the Lead's question: "may testnet hotfixes that don't change scoring or exams go live without waiting for you? ... Reply 'yes, hotfix authority'". The owner also gave the miner reporting contact: "My telegram @RBequette".
- **Decided:**
  - **What may land without waiting for the owner:** testnet fixes to broken behaviour, following the hotfix runbook in codex-queue/reports/OWNER_POST_CALIBRATION_TEST_PLAN_20261029.md: one author, the Validator's receipt, targeted canonical tests, a validator box update, miner --update, and the full gate overnight afterwards.
  - **Reporting:** the owner gets a short summary of each hotfix after it lands.
  - **Miner reporting contact:** the owner's Telegram, @RBequette.
- **Never covered (still the owner's, first):**
  - any scoring, gate, exam, pool-constant or reference-data change (these ship only as new versions);
  - security or containment changes and acceptances;
  - money, spend beyond standing grants, economics and weights policy;
  - mainnet, public publishing and pushes.
- **Bounds:** pausing crowns and weights through the pause switch during a P0 is covered, because it protects miners and changes no scoring.
