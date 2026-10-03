## 2026-10-03 — OWNER-WORKFLOW-SPEED-01: retire the Development Hub, shard CI, one decision per file

**Owner, verbatim, in session on 2026-10-03:**
- "You are the head of PR management. Fix this Merging Main issue AND the
  ridiculous 75 minutes CI runs so often! I want this workflow optimized NOW"
- "I don't care about this HUB anymore"
- On the proposal to stop requiring the Hub in the Merge gate and to run the
  canonical job on 8 parallel shards: "Approve both".
- "tell all sessions to go through you for optimized merge priority and
  keeping main in optimal state"

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
2. **The canonical CI job runs on 8 shards** (#532). Every test still runs
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

**Unchanged.** Every scientific, security, economic and delivery rule; the
`Merge gate` requirement itself; what any test asserts. A merge queue remains
a separate owner decision.
