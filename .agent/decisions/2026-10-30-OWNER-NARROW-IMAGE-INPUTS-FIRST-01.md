# OWNER-NARROW-IMAGE-INPUTS-FIRST-01: narrow the validator image's build inputs to in-container code before the final testnet install

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); relayed by the Validator to the Lead, who records it here.
Owner's words: "Narrow it first". He was choosing between this and launching on Move B now, with the narrowing batched into the first testnet-week update.

Context: any change under carbon/ moves the worker image id. GPU receipts, pool packs and recal margins are bound to that id, so a testnet-week fix would force a reinstall, re-receipts, a re-pack with fresh copy OKs, and a recal.

## Decided

- Before the final testnet install, the worker image's build inputs are narrowed to the code that runs inside the container: about 10% of carbon/, taken from the static module closure plus a runtime-traced allow-list. A test fails if a container imports anything outside the list, and a build-time import of every listed module catches a missing lazy import. Anything wrongly excluded fails closed (an import error, never a different grade).
- It ships in Move B, with the rest of Move B. Packs, receipts and recals are built only after that install.
- After it lands, host-side fixes (receiver, door, grading host code, app) don't move the image, so they need no re-pack, re-receipt or recal.

## Bounds

- Estimated cost: about 9–11 hours of work plus about 2 hours of box time. The launch moves about half a day to a day later.
- The full removal of the pack-to-image tie is still after launch (OWNER-IMAGE-TIE-QUICK-FIX-NOW-FULL-LATER-01).
- Sets no score, threshold or economics.
