# OWNER-BT32-BOX-B1T3-SIGNED-01: Burst Thermal 3.2 box = B1T3 (base power 7.90 W)

Date: 2026-11-08 (CST, about 06:51)
Status: DECIDED by the owner, typed in the Lead session, answering the Lead's BT 3.2 question after Carbon Validator-B's B1T3 GO (04:45 CST).

Question (as brought by the Lead): box = B1T3, that is the B1T designs, base (idle) power 7.90 W, HFE-7100, the r2 curve.
Owner's words (verbatim): "Yes, sign. But no dates. Just ready as soon as the can be."

## Decided
- The BT 3.2 box is B1T3 as stated. Its base (idle) power is 7.90 W. Before this record, 7.90 W was a TEST_ONLY screening value.
- No release date. BT 3.2 ships as soon as it is ready.

## Implemented by
- `scripts/dev/reference_packages/elmer/f02_deck_v32.py`: `V32_BASE_W = 7.90`, `V32_BASE_W_DECISION` = this record. The 3.0 deck's `BASE_W` (20.0 W) is unchanged, and the 3.0 / 3.1 deck files stay byte-identical. The value becomes exam authority only after gate + Validator-2B FINAL.

## Not covered by this record
- Leakage-law coverage for 3.2 (N8): the `V32_LAW_*` pins stay HUMAN_INPUT.
- The curve pin (`V32_HT_*`) and the box file pin (`V32_BOX_SHA256`) need their own reviewed change citing the signed files by sha.
- Region carry vs fresh draw (`V32_REGION_SHA256`).
- Spend and door words.

Screening evidence (TEST_ONLY, custody2, shas only): B1T3 bounds 39c0d9bb, designs 3b099b1c; read by Carbon Validator-B (GO 04:45 CST).
