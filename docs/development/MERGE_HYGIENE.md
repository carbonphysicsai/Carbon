# Merge hygiene: standing rules for every agent

**Authority:** OWNER-MERGE-HYGIENE-01 (2026-10-03, in `.agent/DECISIONS.md`), as
amended the same day by OWNER-WORKFLOW-SPEED-01
(`.agent/decisions/2026-10-03-OWNER-WORKFLOW-SPEED-01.md`). These rules apply to
every branch and PR, by every agent and human executor. They change how PRs are
assembled and merged, not what any PR may decide; every scientific, security
and delivery-protocol rule is unchanged.

**Why.** On 2026-10-02/03, one green PR (#504) had to merge main seven times in
one night. Every conflict was in generated Development Hub files, the Hub's
snapshot repin, or the append-only `.agent/DECISIONS.md`, never in code, and
each re-merge restarted about 55 minutes of serial CI. The owner then retired
the Hub ("I don't care about this HUB anymore") and asked for the workflow to
be optimized. The canonical CI job now runs on parallel shards (#532: 8; 6 since the
first run's measured timings showed 6 finish as fast with fewer runners).

## Rules

0. **One merge manager.** The owner designates one merge-manager session
   (2026-10-03: "PR Head"). It owns merge order, `merge-priority`, the merge
   of main into a branch when one is needed, and the health of `main`. Every
   other session or agent:
   - does not merge PRs;
   - does not merge main into a branch;
   - sends the merge manager each ready PR's number and head SHA, either by
     message or with a `Ready for PR Head: <sha>` comment on the PR;
   - fixes failures as normal commits, never force-pushing;
   - reports anything broken on `main` to the merge manager.

   With no merge manager running, the remaining rules apply to everyone.
1. **The Development Hub is retired.** It is no merge requirement: no
   `HUB_UPDATE_REQUIRED` / `HUB_IMPACT_NONE` line in PR bodies, no Hub events,
   no regenerated Hub files, no snapshot repin. Do not edit
   `docs/development/carbon_hub/`; its files stay as frozen history. A
   conflict in a Hub file (from a PR opened before the retirement) is resolved
   by taking main's copy (`git checkout --theirs <file>`); nothing is
   re-rendered.
2. **One decision per file.** Record each new decision as
   `.agent/decisions/YYYY-MM-DD-<ID>.md` (see `.agent/decisions/README.md`).
   Never append to `.agent/DECISIONS.md`; it holds every decision before
   2026-10-03 and stays byte-for-byte as it is. A conflict in it (from a PR
   opened before this rule) keeps both sides, main's sections first; never
   drop, reorder or reword another session's section.
3. **Validate the exact integration pair (PLT-12).** CI tests both the exact
   head and its clean merge with an exact main base. The receipt keeps both
   results. Head or base movement requires re-validation; conflicts have no
   head-only fallback. The intended strict main rule requires the branch to
   be up to date at merge time. PR Head alone owns branch synchronization and
   the resulting validation; other sessions report the changed base and stop
   the affected handoff. This prospectively replaces the head-only exemption.
4. **Merge the moment you are green.** The merge manager arms GitHub
   auto-merge on each queued PR, pinned to its head:

   ```bash
   gh pr merge <N> --auto --merge --match-head-commit <sha>
   ```

   GitHub may merge only after `Merge gate` passes and the strict base rule
   permits the current pair. A newer base requires fresh validation. The
   versioned rule must be applied and verified; its file is not live
   enforcement. Arm independent PRs together; arm dependent ones one at a
   time, in order. Disarm with `gh pr merge <N> --disable-auto`. Without the
   live ruleset, never arm auto-merge: merge a green PR at once with
   `gh pr merge --merge --match-head-commit <sha>`. The sharded canonical job
   takes about 10-20 minutes.
5. **Priority lane.** When a PR has had to merge main twice because of
   conflicts while green or in CI, its owner adds the label `merge-priority`.
   Before merging anything, every agent checks for an open PR carrying
   `merge-priority` whose required CI is running or green:

   ```bash
   gh api 'repos/carbonphysicsai/carbon/issues?labels=merge-priority&state=open' \
     --jq '.[] | select(.pull_request) | .number'
   ```

   If one exists and your PR is not it, wait until it merges or its required
   CI fails, then merge. The PR's owner removes the label once it merges. If
   more than one PR carries the label, the lowest-numbered goes first.
6. **Touch shared files only when your change needs them.** Add a decision
   only for a real decision.
7. **Report a blocked merge once, plainly**: which files conflicted, how many
   rounds, and what would unblock it. Do not loop silently.

## What changed in CI (#532)

- The canonical job is a matrix of 6 shards. `scripts/dev/ci.sh` reads
  `CARBON_CI_SHARD=<index>/<count>`; the default CPU suite is split by test
  file (`scripts/dev/ci_shard.py`) and every other lane runs whole on one
  shard. The job succeeds only when every shard does. Unset, `ci.sh` is the
  full serial command (local runs and the dev-image job).
- The Merge gate no longer requires the Hub job. Merge gate runs the protected
  base's gate, so the Hub job runs only while that gate still names it.

- Auto-merge is allowed (owner, 2026-10-03), together with the versioned
  ruleset `.github/rulesets/main.v1.json`, applied with
  `scripts/dev/apply_github_ruleset.py`:
  - `Merge gate` is required on main, with no bypass actors;
  - main accepts only pull requests, merged with merge commits;
  - force-pushes and deletion of main are blocked;
  - no human review is required; strict status checks guard the validated base.

PLT-12 activation is an administrative change owned by PR Head/the owner.
See [CI merge validation](CI_MERGE_VALIDATION.md). Until the strict rule has
been applied and verified, the merge watcher refuses to authorize a merge.
