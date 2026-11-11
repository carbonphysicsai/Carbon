# OWNER-BT32-REGION-SIGNED-01: Burst Thermal 3.2 hidden region signed

Date: 2026-11-10 (CST, about 10:00)
Status: DECIDED by the owner, typed in the DC-B session (the BT 3.2 owner session).

Line typed (verbatim): "DC-B: yes, sign the BT 3.2 hidden region drawn under key 0a11147f (canonical 9f5e254f): every drawn side passed the probe and edge check under the 3.1 rules. Custody only, shas only."

## Decided
- The BT 3.2 hidden region is the region drawn under key id 0a11147f (drawn canonical 9f5e254fcd75c19c15935f93d7237900b624c6fec6cbd35826f8bb311b039f3b), now with status OWNER_SIGNED.
- Carbon Validator-BT's per-side probe and edge check (board, Tue 10 Nov 07:49 CST): every drawn side passed with no redraw. The failed corner cells are excluded from every case drawn on this region; the exclusion is recorded in custody, never here.
- The signature changes only the status and adds a signature block that records the owner's words and the custody file shas. The inputs and the nonce are unchanged.
- The post-signature canonical is 55fae831e40518120f550993cf6a3e28bf92ffd80df7ab0d02372eacf39bee0f. That is the deck's form: sha256 of the compact, sorted JSON without `region_sha256`.

## Implemented by
- `scripts/dev/reference_packages/elmer/f02_deck_v32.py`: `V32_REGION_SHA256` = 55fae831..., and `V32_REGION_RECORD` = this record.
- The signed file stays in custody. Neither the file nor any region value is published.
- The pin becomes exam authority only after gate + Validator-2B FINAL.

## Not covered by this record
- No region bound, corner, seed or drawn-case input is recorded here.
- Not covered: the battery, gate-set and design-value draws; spend; door words.
