# OWNER-INTAKE-EXPOSURE-03K: one public read-only "current king" route (testnet)

Date: 2026-10-23
Status: **ACCEPTED by the owner, directly in the Carbon Validator's session.** Asked: one new public, read-only address per Challenge showing the king's mining address, its score, the score to beat, and Carbon's starting score when there is no king. Answer: "Allow, testnet only (Recommended)".
Extends: OWNER-INTAKE-EXPOSURE-03 (same host, tunnel design, limits and go-live checks). Adds one route to its allow-list.

## Accepted (testnet 567 only)

- **Route:** `GET /carbon/v1/koth/<challenge>`, read-only, with no request body. It is added to the exact edge and ingress allow-list; everything else still 404s.
- **Response fields, allow-listed (nothing else):**
  - challenge id and version label;
  - `king`: {hotkey ss58, total stepped to the Ladder grid, since_epoch} or null;
  - `margin`: the registered `koth_rebuild_noise.json` value for that challenge_id, absolute in total units (OWNER-KOTH-MARGIN-SEED-SPREAD-01), or null when unregistered;
  - `to_beat` = total + margin, or null when either is null;
  - `baseline_total` (stepped to the Ladder grid) when there is no king.
- **Never in the response:** the pack-set key or any exam fingerprint, legs, per-case values, inputs, references, probes, recipes, or operator-only KOTH reasons.
- **Built on the validator lane** (Test Engineer builds; Validator receipts). Tests: the allow-listed fields only (a no-leak test), the 404 for unknown challenges, and a null margin → a null to_beat.
- The EXPOSURE-03 go-live checks are re-run with the route added.

## Not covered

Mainnet; any write; any field beyond the list above.
