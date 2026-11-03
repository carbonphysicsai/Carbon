# OWNER-MAIN-ONLY-SUBNET-UPGRADES-01: only subnet upgrades go to main; everything else on branches

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Yes: only subnet upgrades go to main (receivers, grading/scoring/registry, worker image, dashboard, miner app, published docs). Everything else stays on branches: PR Head may push to origin dev/* branches without asking me; Validator receipts by SHA; tooling lands on main later with the upgrade that needs it."

## Decided
1. MAIN gets only subnet upgrades:
   - receivers;
   - grading/scoring/registry;
   - the worker image;
   - the dashboard and the miner app;
   - published docs.
   Each main push still needs the owner's named-SHA words, the right gate tier and receipt rules: hot-fix tier 1 (c6f36e94); tier 2 for receivers, grading and the image.
2. EVERYTHING ELSE stays on branches. That covers exam-building tools, harnesses, analysis scripts, payload builders, LN/sep_read/dv_curve tooling and in-development decks. It is delivered to hosts as git bundles or fetched from origin `dev/*` branches.
3. PR Head may push to origin `dev/*` branches WITHOUT asking the owner. It never pushes to main or to any other namespace this way, never force-pushes over another session's work, never pushes banned heads, and never pushes secrets or sealed material.
4. Validator receipts are by exact SHA, wherever the commit lives.
5. Tooling lands on main later, batched with the subnet upgrade that needs it (e.g. a version's registration).

## Notes
- The receiver accepted-revision guard (`merge-base --is-ancestor <rev> origin/main`) still applies to anything the doors run, so door code must reach main.
- The 4-head batch drafted before this decision (94c346bc → e7360810 → fba53c68 → d98d4892) was already gated and receipted as one chain, and may land as drafted.
