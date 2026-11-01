# OWNER-F02-V3-LEAK-BOX-SIGNED-01: Burst Thermal 3.0 box C6, Vth0 0.35 V, leakage share 2 % (signed)

Date: 2026-11-01 (CST)
Status: DECIDED and SIGNED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: box C6, Vth0 0.35 V, share 2 %"
This answered the Validator's FINAL phone message: `codex-queue/reports/F02_OWNER_LEAK_MESSAGE_DRAFT_20261101.md`, the part between the --- lines, sent with the Lead's own view.

## Signed
1. Box C6: pulse up to 90 W, on-time up to 8 s, TIM up to 0.15 mm, cooling h at least 2500, coolant up to 35 °C. Every input stays a real range.
2. Leak curve: HotLeakage Eq. 2 with the BSIM3v3.2.2 textbook defaults (two-pass transcription; Voff -0.08, Nfactor 1.0, Tnom 27 °C, Kt1 -0.11), threshold voltage Vth0 = 0.35 V.
3. Leak size: 2 % of the 20 W base at 27 °C (0.4 W).

## Evidence
- DIAG-01 = PHYSICAL (d6443987fa93fef9ee4bd524bbc7c29a29e4e26caab3f60b77341c17cab180ba).
- CUT-03 Stage A (8260c73b1fe6596dd303686afd2db559efaf5528d4ecce310fa8f57f0315dd9d): C6 at 2 % peaks 136.8 °C, leak effect +6.7 °C, 17 K below the static runaway crossing (426.8 K).
- LOWSHARE tables 52075934…; desk check a6c3d662…; share sweep 9525a0a2….

## Notes
- Vth0 = 0.35 V is illustrative, not from a datasheet. The F02 3.0 intended-use text must say the leakage is representative, not a specific real device (Lead's caveat, given with the recommendation).
- The day-6 sheet still re-checks that the 90 °C threshold sits inside the signed box's full peak range.
- Stage B (F02-STAGE2-01) unblocks only after the Validator's receipt of the payload SUMS that binds this signed box digest.
