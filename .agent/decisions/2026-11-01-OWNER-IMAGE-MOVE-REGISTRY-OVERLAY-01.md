# OWNER-IMAGE-MOVE-REGISTRY-OVERLAY-01: one worker-image move now, adding the add-only version-registry overlay hook, shipped with Cooling 1.7

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "A"
Question asked: (A) do the one image move NOW with Cooling 1.7, so Cooling becomes winnable in ~2 days and F02 3.0 / F08 2.0 need no further image move (recommended by the Validator and the Lead); or (B) batch it with F02 3.0 (~day 6), leaving Cooling unwinnable until then. The Lead stated that "A" also counts as the owner's yes to publish the new image once it's built and checked.

## Decided
- Build ONE new worker image now, adding an add-only, fingerprinted version-registry overlay hook, so later exam versions register without image moves.
- Ship it with Cooling 1.7 (baseline graded through the miners' path; the minimums and bar per Option B; the new-version rules).
- Publish the new image once it's built and has passed the Validator's checks (owner image-publish word given by "A").
- The one-time cost is accepted: repack the four live exams, GPU receipts for the catalog, margin recal, about a day of box work, with zero-downtime cutovers.

## Bounds
- Live exam versions are repacked, not rescored. Nothing already graded changes.
- Zero-downtime procedure for every receiver change; smoke checks before box-heavy steps.
- Testnet. Mainnet image decisions stay separate.
