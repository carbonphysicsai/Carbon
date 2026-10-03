# Merge hygiene: standing rules for every agent

**Authority:** OWNER-MERGE-HYGIENE-01 (2026-10-03), recorded in
`.agent/DECISIONS.md`. Applies to every branch and every PR, by every agent
and human executor. It changes how PRs are assembled and merged, not what any
PR may decide: every scientific, security and delivery-protocol rule is
unchanged.

**Why.** On 2026-10-02/03, one green PR (#504) had to merge main seven times
in one night. Every conflict was in generated Hub files or the append-only
`.agent/DECISIONS.md`, never in code. Each re-merge restarted roughly 75
minutes of required CI, while other sessions kept merging.

## A. In force now

1. **Never hand-edit generated Hub files.** These are outputs:
   `docs/development/carbon_hub/index.html`, `interactive.html`, `README.md`,
   `Carbon_Development_Hub_v2.md`, `data/hub_index_v2.yaml` and
   `data/hub_data_v2.json`. Change Hub source (`data/events/*.json`, the
   impact rules) and run `docs/development/carbon_hub/tools/render_hub.py`.
2. **A conflict in a generated Hub file** is resolved by taking main's version
   (`git checkout --theirs <file>` while merging main), re-running
   `render_hub.py`, then `validate_hub.py`. Never merge their text by hand.
3. **A conflict in `.agent/DECISIONS.md`** keeps both sides: main's sections
   first, yours after. Never drop, reorder within, or reword another
   session's section.
4. **Merge main just before your final push**, not earlier. Run the repo's
   fast checks on the merge result, then push once.
5. **Merge the moment you are green.** Time your check-in to when required CI
   ends (about 75 minutes for the canonical job), not later. A green,
   mergeable PR is merged at once with the expected-head guard; it never
   waits for a later check-in.
6. **Priority lane.** When a PR has had to merge main twice because of
   conflicts while green or in CI, its owner adds the label
   `merge-priority`. Before merging anything, every agent checks for an open
   PR carrying `merge-priority` whose required CI is running or green:

   ```bash
   gh api 'repos/carbonphysicsai/carbon/issues?labels=merge-priority&state=open' \
     --jq '.[] | select(.pull_request) | .number'
   ```

   If one exists and your PR is not it, wait until it merges or its required
   CI fails, then merge. The PR's owner removes the label once it merges. If
   more than one PR carries the label, the lowest-numbered goes first.
7. **Touch shared files only when your change needs them.** Add a decision
   only for a real decision, and a Hub event only when the Hub's impact rules
   require one.
8. **Report a blocked merge once, plainly**: which files conflicted, how many
   rounds, and what would unblock it. Do not loop silently.

## B. In force once the MERGE-HYGIENE-01 ticket merges

Not yet in force: today CI still expects generated Hub files to be committed
with each PR. The MERGE-HYGIENE-01 ticket (listed below) builds the change and switches
these on.

9. **PRs never commit generated Hub outputs.** CI renders and validates the
   Hub from source; the outputs are rebuilt on main after each merge.
10. **One decision per file**: `.agent/decisions/YYYY-MM-DD-<ID>.md`. Never
    append to a shared decision file; the index is generated.
11. **Enforced:** once in force, CI refuses a PR that edits a generated Hub
    file or appends to a shared decision file.

### Part B work

**Work list for the MERGE-HYGIENE-01 ticket** (opened when the work starts):
- [ ] Generated Hub outputs (`index.html`, `interactive.html`, `README.md`,
      `Carbon_Development_Hub_v2.md`, `data/hub_index_v2.yaml`,
      `data/hub_data_v2.json`) are no longer committed by PRs. CI renders them
      from source and validates the result; main rebuilds them after each
      merge, or the publish step builds them. Choose one and record why.
- [ ] `validate_hub.py` and the Hub CI job check source, not committed
      outputs, and still reject an invalid event or a missing impact
      declaration.
- [ ] Decisions move to one file each: `.agent/decisions/YYYY-MM-DD-<ID>.md`.
      `.agent/DECISIONS.md` becomes a generated index (or a pointer), and its
      existing history is preserved byte-for-byte or split losslessly, with a
      digest check proving nothing changed.
- [ ] Everything that reads `.agent/DECISIONS.md` (tests, the Hub, tools,
      `AGENTS.md` references) keeps working.
- [ ] CI refuses a PR that edits a generated Hub output or appends to a shared
      decision file (rule 11).
- [ ] `docs/development/MERGE_HYGIENE.md` part B is marked in force, and
      `AGENTS.md`'s OWNER-MERGE-HYGIENE-01 block is updated.
- [ ] Demonstration: two branches that each add a Hub event and a decision
      merge into main in either order with no conflict.

**Must not:** change any decision's content, any Hub event's meaning, any
scientific or security rule, or the `Merge gate` requirement. A merge queue is
out of scope (separate owner decision; the rules forbid auto-merge).

A merge queue (GitHub merging each PR onto the latest main in order) is a
separate owner decision: the repository's rules currently forbid auto-merge.
