# OWNER-DASHBOARD-LIVE-SWITCH-01: switch dashboard.carbonphysics.ai to the live boards once the first board is published

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Go: switch the dashboard to the live version once the first board is published, after the Validator confirms the feed is correct."

## Context

The static "launching soon" dashboard (claude/dashboard-ux @ 8cee42f1e8, names for the four launch Challenges, no Battery) was deployed earlier the same night with the owner's word.

## Decided

- Once the first launch Challenge publishes a board, the Lead deploys the live dashboard Worker (carbon/dashboard/wrangler.dashboard.toml) from the reviewed dashboard branch. Its feed points only at the four launch boards, with the Challenge display names and the validator's pinned signing key, and the fixture key is refused.
- This happens only after the Validator confirms that board's feed is correct: signed by the pinned key, the right Challenge and version, and no fixture rows.

## Bounds

- The Lead checks the live page after deploying. If anything is wrong, the Lead rolls back to the static page (`wrangler rollback`).
- Covers this one switch. Later dashboard design changes follow the normal flow.
