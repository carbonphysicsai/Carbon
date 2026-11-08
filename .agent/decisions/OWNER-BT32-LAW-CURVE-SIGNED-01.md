# OWNER-BT32-LAW-CURVE-SIGNED-01: Burst Thermal 3.2 uses the signed 3.1 leakage law and the registered r2 curve

Date: 2026-11-08 (CST, about 15:0x)
Status: DECIDED by the owner, typed in the Lead session (decision ledger, Sun 8 Nov ~15:0x CST), answering the Lead's question "Sign Burst Thermal 3.2's law and curve line?".

Line signed (verbatim): "BT 3.2 uses the signed 3.1 leakage law (f3eefda9, 5 %) and the researcher's r2 HFE-7100 curve 28be87ad, pinned as its registered copy dacf57f4 (same values; only the schema label and status changed)."
Owner's words (verbatim): "Yes, sign it".

## Decided
- The BT 3.2 leakage law is the signed 3.1 law, byte-identical: file sha256 f3eefda98fcadd0a14b3b1b57050a166a96c6a2e4fe66d8df49a037a5a42ae35, decision OWNER-BT31-LAW-ANCHOR-SIGNED-01 (ledger N8; 5 %, ITRS-anchored). Carbon Validator-BT checked it equal, key by key, to the TEST law (7c25f20e) used for the screening and pilot runs. Only the 'decision' and 'source' text differ.
- The BT 3.2 boiling curve is the researcher's r2 HFE-7100 file 28be87ad, pinned as its registered copy dacf57f4. The pin itself was set under OWNER-BT32-BOX-B1T3-SIGNED-01 (pin change 2); this record confirms it by name.

## Implemented by
- `scripts/dev/reference_packages/elmer/f02_deck_v32.py`:
  - `V32_LAW_SHA256` = f3eefda9... (= `V31_LAW_SHA256`).
  - `V32_LAW_DECISION` = OWNER-BT31-LAW-ANCHOR-SIGNED-01, the law file's own decision id, which `write_case_v32` checks.
  - `V32_LAW_RECORD` = this record.
- The region pin (`V32_REGION_SHA256`) stays HUMAN_INPUT.
- The 3.0 / 3.1 deck files stay byte-identical.
- The pins become exam authority only after gate + Validator-2B FINAL.

## Not covered by this record
- The hidden region (`V32_REGION_SHA256`): it needs the owner's region signature after the per-side probe + edge-U check.
- Spend and door words.
