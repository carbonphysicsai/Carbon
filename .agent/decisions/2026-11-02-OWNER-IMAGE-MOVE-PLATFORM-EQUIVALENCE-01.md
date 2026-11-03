# OWNER-IMAGE-MOVE-PLATFORM-EQUIVALENCE-01: image move via a platform-equivalence proof, route (b)

Date: 2026-11-02 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "B", answering the Lead's two routes.
- (a) Re-calibrate the leg minimums on the new image under a new eval version (sealed pack rebuild).
- (b) Prove the old and new inference images compute bit-identical results on every live pack's calibration entries, then register a platform-equivalence record with no recalibration and no score changes.

## Context
- The M3 cutover onto main 34b2a71c would score every door UNAVAILABLE, with `leg_minimum_platform_mismatch` (carbon/.../physical_dual_pack.py:837).
- All 4 live packs bind their leg minimums to inference image 97b1eda2, while the M3 torch image is 582fcb9a.
- The F08 route-A E2E already showed bit-equal predictions between the old and M3 roots.

## Decided
- Route (b). The TL runs the bit-equality check on each live pack's calibration entries, the baselines that set the leg minimums, comparing old 97b1eda2 with M3 582fcb9a on the same host and driver.
- **If ALL are bit-equal:** the Validator receipts a platform-equivalence record (582fcb9a ≡ 97b1eda2 for those packs, citing the proof shas). The cutover then proceeds under the standing re-prepare yes (spare-port proof, door by door, rollback on failure). Leg minimums are unchanged and no graded result is rescored.
- **If ANY entry differs:** route (b) stops for that pack, and the Lead brings route (a) back to the owner with the measured differences.
- Equivalence covers only the packs and entries proven, and never a later image.

## Proof standard (Validator ruling, folded in; it tightens the proof and does not change the owner's choice)
For each live pack (all 4), the TL works on the custody host.
- **Re-run:** the pack's own CALIBRATION grade of its registered baseline on M3 582fcb9a: the route-A fresh rebuild plus the two repeats.
- **PASS means all three:**
  - predictions are bit-equal to the 97b1eda2 run;
  - the recomputed legs A and D equal the registered minimums bit for bit;
  - the device class is unchanged.
- The F08 king result supports the case but is not the proof.
- **Code:** a per-pack equivalence record checked at l.837 (exact image pair, fail closed), then tier 2, the Validator receipt, then main on the owner's words through PR Head. No cutover happens until it lands.

## Route note (2 Nov, Validator ruling; no grading binding changes, so no new owner words needed)
- Any edit to physical_dual_pack.py moves every live pack's producer_digest (checked at l.777-786), so the equivalence-record code (09db1215) is parked.
- Instead, each door grades on its pack's registered inference image (97b1eda2) through receiver config, `inference_image_manifest` (direct_receiver.py:1420). Everything else moves to main and the M3 images.
- The 4/4 calibration reruns (note 6bc31c7e) stay on record as the proof for a later re-seal of these packs onto M3.
- If a door refuses this config, it returns to the owner as a choice between re-seal and code.
