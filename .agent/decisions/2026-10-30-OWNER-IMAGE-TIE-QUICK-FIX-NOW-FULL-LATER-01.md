# OWNER-IMAGE-TIE-QUICK-FIX-NOW-FULL-LATER-01: keep margins and constants from moving the validator image now; remove the exact pack-to-image tie after launch

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Okay yes 1", answering the Lead's option 1. Earlier in the same thread: "Remove the exam to software ID tie that's fkn stupid".

## Decided

- Now (Move B): the margin registry (koth_rebuild_noise.json) moves out of the validator image's build inputs, so writing a margin never moves the image. Move B is the final testnet launch image. Every pack is built after it, on its inference image id.
- After launch, before mainnet: the exact inference-image id is removed from pool packs and copies. Grading checks instead, fail-closed, that the running image is in the host class's registered stage-2 list, records which image ran, and confirms a crown on the same image (the Validator's conditions).

## Bounds

- Sets no score, threshold, margin or economics.
- The post-launch change moves every producer digest once, so packs and copies are rebuilt once at that point.
