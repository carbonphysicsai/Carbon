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

- Pin change 2 (Sun 8 Nov 2026, after Carbon Validator-BT's receipts 10:55 / 10:56 CST):
  - `V32_BOX_SHA256` = d620a81f82889d344a7721d4175716fc42ac6c5e5412931e880eb97fdea10799, the canonical sha of the public box file `bt32-box-B1T3.json` (file 4ba6eb09). It is the signed 3.0 box C6 under the exact B1T map. Coolant is fixed at the curve inlet (not a range), and the start offset is in [0, 5] K.
  - `V32_HT_SHA256` = dacf57f4a3dc082f12c87569389a585e699abce5331477ce8b0a601bee8e50d3, `V32_HT_DECISION` = this record ("the r2 curve" by name; N16 O7). It is the registered copy of the researcher's r2 HFE-7100 file 28be87ad. Only the schema label and status changed, and its h(T) tables are byte-equal on all 128 B1T3 designs.

## Not covered by this record
- Leakage-law coverage for 3.2 (N8): decided separately by OWNER-BT32-LAW-CURVE-SIGNED-01 (Sun 8 Nov ~15:0x CST). The `V32_LAW_*` pins are set there.
- Region carry vs fresh draw (`V32_REGION_SHA256`).
- Spend and door words.

Screening evidence (TEST_ONLY, custody2, shas only): B1T3 bounds 39c0d9bb, designs 3b099b1c; read by Carbon Validator-B (GO 04:45 CST).
