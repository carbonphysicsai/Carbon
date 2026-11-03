# OWNER-RB20-PAD-B2-AND-FINE-MESH-CAP-40-01: Ribbed Bracket 2.0 load pad = B2; finest error-bar mesh cap up to 40 GiB

Date: 2026-11-03 (CST, ~07:25)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: Ribbed Bracket 2.0 load pad = B2 (anywhere in the clear gap between the ribs), clearance 0.5 mm, or 3 mm if the fixed-mesher 0.5 mm probes fail; and raise the memory limit to up to 40 GiB for the finest error-bar fillet mesh only, measured, stopping at the limit if more is needed."
Asked from: codex-queue/reports/RB20_OWNER_MESSAGE_DRAFT_20261103.md (EQ, sha b7ace5de), with the Lead's edits (the conditional margin; the 40 GiB marked as an estimate and an upper limit).

## Decided
- **Load position (B2):** the RB 2.0 load position is re-signed as "anywhere in the clear gap between the two ribs".
  - The pad keeps at least the clearance below from each rib footprint and its fillet.
  - The design space stays a box. Loads outboard of a rib are out of scope for 2.0.
- **Clearance:** 0.5 mm, IF the four 0.5 mm probe designs pass on the fixed (hoo2) mesher at every rung, under the Validator's pass rule. If any fails, the clearance is 3 mm. No other value applies without a new owner decision.
- **Memory:** the per-case reference memory limit is raised to up to 40 GiB for the finest error-bar fillet rung (f0.25) only.
  - Every other rung and the production mesh keep the existing limit.
  - The peak is measured on the run.
  - A case needing more than 40 GiB stops at the limit. It comes back to the owner and is never raised silently.
- **Unchanged:** every other signed RB 2.0 value. The fillet 0.5–3, rib 3–5 and width 60–100 ranges keep their signed numbers.
- **Never rescored:** the live RB 1.7 is unaffected (no load offset; 0 live cases had the pad on a rib).

## Next (team)
- **EQ:** writes the B2 region / offset-domain rev from this record, and the Validator receipts it.
- **TE:** the pad_clears_rib gate goes into the deck, in the B2 form. It is typed and applies to every draw.
- **Launchpad:** the hoo2 0.5 mm probes run (~10:30–11:00), and their verdict selects 0.5 vs 3 mm. Then the U-panel / UEDGE rerun on hoo2 runs under the RB line of the USD 135, with the f0.25 rung at up to 40 GiB and its density planned for memory.
- The cells are redrawn by the registered draw on the valid domain.
