## 2026-10-03 — OWNER-WORKFLOW-SPEED-01: retire the Development Hub, shard CI, one decision per file, one merge manager, auto-merge

**Owner, verbatim, in session on 2026-10-03:**
- "You are the head of PR management. Fix this Merging Main issue AND the
  ridiculous 75 minutes CI runs so often! I want this workflow optimized NOW"
- "I don't care about this HUB anymore"
- On the proposal to stop requiring the Hub in the Merge gate and to run the
  canonical job on 8 parallel shards: "Approve both".
- "tell all sessions to go through you for optimized merge priority and
  keeping main in optimal state"
- "Your role is to receive, order, and push our PRs as efficiently as we can
  to keep work moving"
- On the proposal to allow auto-merge with the ruleset (repository and
  apply-tool change, applying the ruleset with "Allow auto-merge" on, and the
  merge manager arming pinned auto-merge): "if you think this is best for our
  workflow and is safe lets do it", then "Approve all three".

**Context.** Under OWNER-MERGE-HYGIENE-01 (same day, `.agent/DECISIONS.md`),
every PR still committed generated Hub files and a Hub snapshot repin and
appended to `.agent/DECISIONS.md`. Each merge to main therefore put every other
open PR into conflict, and each re-merge restarted a canonical job of about 55
minutes, 46 of them one serial run of 9,688 tests. The Hub job also failed
untouched PRs when main's Hub data moved.

**Decision.**
1. **The Development Hub is retired.** It is no merge requirement:
   `scripts/dev/check_merge_gate.py` no longer names it (#532), and PRs carry
   no Hub declaration, events, regenerated files or repin. The files under
   `docs/development/carbon_hub/` stay as frozen history: one invariant test
   reads its last recorded program state, and the Launchpad browser smoke
   imports its browser helper.
2. **The canonical CI job runs on parallel shards**: 8 in #532, then 6 in this
   decision's follow-up, because the first run's measured timings showed 6
   finish as fast (one 11.4-minute test file is the floor) with a quarter fewer
   runners on GitHub Free's 20-job limit. Every test still runs
   exactly once, and the job succeeds only when every shard does.
3. **One decision per file**, `.agent/decisions/YYYY-MM-DD-<ID>.md`. This is
   OWNER-MERGE-HYGIENE-01 part B rule 10, now in force. `.agent/DECISIONS.md`
   is frozen as the history before this date.
4. **No re-merging main into a green PR without a real conflict.** Main does
   not require up-to-date branches and CI tests the PR's own head
   (`docs/development/MERGE_HYGIENE.md` rule 3).
5. **One merge manager.** All sessions route merges through the owner's
   designated merge-manager session ("PR Head" on 2026-10-03), which owns merge
   order, the `merge-priority` lane, any merge of main into a branch, and the
   health of `main` (`docs/development/MERGE_HYGIENE.md` rule 0).
6. **Auto-merge is allowed, only with the required check live.**
   - `.github/rulesets/main.v1.json` now sets `allow_auto_merge: true`.
   - `scripts/dev/apply_github_ruleset.py` applies the ruleset and verifies it:
     `Merge gate` required on main with no bypass actors, pull requests only,
     merge commits only, no force-push or deletion, no required review, and no
     up-to-date requirement.
   - The merge manager arms `gh pr merge --auto --merge --match-head-commit
     <sha>`. GitHub then merges only a head whose own `Merge gate` passed.
   - This amends AGENTS.md §18 ("do not enable auto-merge").

**Unchanged.** Every scientific, security, economic and delivery rule; the
`Merge gate` requirement itself; what any test asserts. A GitHub merge queue
remains a separate owner decision.
