# OWNER-F02-V3-REGION-SIGNED-A-01: Burst Thermal 3.0 extended region signed as is (option A)

Date: 2026-11-02 (CST, ~19:35)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Please sign and approve the region signature. Press forward"

## What was asked
The owner text `codex-queue/reports/F02_V3_REGION_FINAL_REV2_20261102/OWNER_SIGNATURE_TEXT.md`. It offered: A, sign as is (recommended); B, a smaller region he names; C, no signature (in range only); D, register the graded outputs first and re-run the check. Only A is a signature of the file as it stands. B needs a region he names, and C and D are not signatures. So his words select A.

## Decided
- **The region:** Burst Thermal 3.0's extended region is `F02_V3_REGION_FINAL_REV2_20261102/region.final.json`.
  - file sha256 2bc68ac917150a104b7bd267b719baf70e224f5fdb863a62b4b62191bbe75a55
  - canonical sha256 d932d08ac7e01b9b4b4616dab38663b89d73d9ca05e52fb8d5744119436f2787 (the sha the exam loader checks)
- **Extended sides (10):** these stay at +25 %:
  - coolant low;
  - gap, both sides;
  - heat-transfer coefficient high;
  - left-source fraction, both sides;
  - on-time low;
  - peak power, both sides;
  - TIM thickness low.
- **Sides kept at the box edge (6):** coolant high, heat-transfer coefficient low, initial temperature low and high, on-time high, TIM thickness high.
- **Held at their physical ends:** pulse count and ramp fraction.
- **Corners:** all 5 pass, with 0 exclusions.
- **What the signature allows:** out-of-range exam cases (the shell and MINE B1/B2/B4/B9–B11) may now be drawn inside this region only.
- **Unchanged:** the signed box C6, the leakage law, the 95 °C limit, scores and money.
- **The E2 flag, as he was told:** the 0.5 °C nonlinearity bar is about 3 × U (0.169 °C), which is below the 10 × U he asked to be told about. The signed value is unchanged.

## Next (team)
- **Data Collection** starts the staged run (BT30_STAGING_D932D08A_20261102): coverage draw, then the 6-case probe, S4a, checks (1)–(3), DV-CURVE and the mix.
- **Disclosure is unchanged:** the signed file says the region is hidden and never published (as 2.5: OWNER-MINER-SOLVER-ACCESS-01), and the owner's words don't mention publishing. So the miner page shows the region kinds and the rule only. The exact extents are published only if the owner explicitly decides that. (A Lead note said "publish to every miner"; the Validator caught that as a conflict, and it is corrected here.)

## Disclosure confirmed (owner, Lead session, ~19:50 CST, AskUserQuestion)
Asked: "should miners see its exact out-of-range edges, or only the kinds and rule (today's rule from 2.5)?" Owner's answer: "Kinds + rule only (Recommended)". The exact extents stay hidden, and the miner page names the region kinds and the rule that sets them.
