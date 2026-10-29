# OWNER-BRANCH-PRUNE-POST-LAUNCH-01: after the testnet door opens, prune to a handful of branches, with a full archive bundle first

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "I don't understand keeping more than a handful of branches". Then "Yes" to the Lead's plan to schedule the prune for right after the door opens, with the archive file made first.
- **Decided (after the testnet door opens, not before):**
  1. Make one `git bundle` of every local branch, verify it, and store it with the archives.
  2. Delete the branches merged into the launch base.
  3. Land the live unmerged ones (about 35, per UNLANDED_TRIAGE_20261029.md) in the next batch, or archive them through the bundle and delete them.
  4. Archive the stale unmerged ones through the bundle and delete them.
  5. Remove the old worktrees, checking each one first for uncommitted work.
  6. Keep about 5–10 branches: main, the launch candidate plus one rollback, and branches with work in progress.
  7. From then on, delete a branch as soon as it lands.
- **Bounds:**
  - This extends OWNER-BRANCH-CLEANUP-RULE (10-23, `-d` only) to unmerged branches, but only after a verified bundle.
  - Nothing is pushed or force-deleted on any remote without a separate owner go.
  - Paths that may hold keys are not opened.
