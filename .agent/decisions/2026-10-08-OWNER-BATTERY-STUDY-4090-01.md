## 2026-10-08 — OWNER-BATTERY-STUDY-4090-01: the battery training budget study moves to the RTX 4090, grant -02

**Authority.**
- **The move.** The owner approved moving the TRAINING-BUDGET-01 study from
  the A40 to the RTX 4090, relayed by the Test Lead on 2026-10-08:
  - RunPod's Secure Cloud A40 create returned provider errors, while the
    same create worked on other GPUs;
  - Vast listed no A40s.
- **The grant.** The owner approved it directly in the Test Engineer's
  session, 2026-10-08: "I approve the TRAINING-BUDGET-01 study on RTX 4090:
  cap USD 34.80, pause at USD 27.84, re-issued as grant -02".
- **The provider.**
  - The owner told PR Head "Yes on runpod".
  - Shown RunPod's list prices, the owner then chose, in the Test Engineer's
    session, **RunPod Community Cloud at USD 34.80**.
  - The alternatives were Secure Cloud at about USD 53.55 (4090 USD 0.74 and
    A100 USD 1.59 an hour) and keeping Vast.

**Decision.**
1. **The grant.**
   `docs/development/training_budget_study/grants/TRAINING-BUDGET-GRANT-BATTERY-STUDY-02.json`,
   provider `runpod`, Community Cloud, ceiling USD 34.80. Its limits (schema v2) bind each leg's
   rate cap and pod-hours:
   - **The RTX 4090 leg:** USD 0.48 an hour for 65 h, covering runs A-H and
     the B repeat.
   - **The A100 80 GB leg:** USD 1.20 an hour for 3 h, covering run S.
     Run S measures the FNO cells over the 4090's memory ceiling.
   - **Both legs:** RunPod Community Cloud only (list prices: 4090 USD 0.34,
     A100-80 PCIe USD 1.19), a pause at USD 27.84, and a
     re-estimate after Phase A.
2. **Grant -01 is superseded.** Its figures stay as recorded, but it is not
   spendable: its ceiling no longer matches the sheet's.
3. **The sheet** (`battery-fastcharge-ageing-development-v1.json`):
   - `gpu_model` is `nvidia-rtx-4090`;
   - `spend_ceiling` is 34.80;
   - `memory_ceiling` is 20 GiB, the A40's 40-of-48 headroom rule applied to
     24 GB;
   - `image_digest` is HUMAN_INPUT until worker-images-v3 is released.
     v2's PyTorch GPU image fails every FNO rebuild (#826), so the study stays
     refused until then.
4. **What is unchanged:**
   - the rest of the study design (R1-R11, the TRAIN size ladder, the study
     ranges and the recipes);
   - the status, TEAM-PROPOSED and OWNER-APPROVED FOR TESTING, never
     production.

**Device-class sensitivity** (estimates; run S measures them):
- **Within today's contract caps,** every battery recipe fits 20 GiB. The
  largest FNO needs about 7.4 GiB.
- **The MLP and DeepONet** stay under about 1.3 GiB, even at the study's
  widest settings (XLA memory analysis).
- **Only the study's above-cap FNO cells** exceed 20 GiB:
  - four the A40 would have run (21.8-38.3 GiB);
  - four only an A100-80 fits.
- **The 4090 is a new device class.** Its curves are never pooled with
  another class.

**Not claimed.**
- **No rebuild has been timed on a 4090.** The hours are estimates.
- **The pod runner** (slice 2c) is not built. It must bind provider `runpod` and Community Cloud.
- **The A100 leg's cap is tight:** USD 1.19 list plus disk against USD 1.20.
  If no offer fits, run S is refused and goes back to the owner.
- **Level 1-4 recipes** join Phase H only once TRAINING-BUDGET-02 (#806)
  prices them.
