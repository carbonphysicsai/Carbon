# Development Hub source shape: proposal and migration plan

Status: **proposal, answered.** Nothing is migrated by this document, which
changes no tool, schema, gate or Hub source. Core platform responded in full,
ran the reproduction, and measured the `repo_links` claim independently; every
question §8 asked is now settled, and the resolutions are recorded inline below.
Launchpad has not responded. Stage 1 is implemented in a follow-up change.

Owner authority: the owner-forwarded assignment of 2026-09-22 to take
Launchpad's proposed restructure — one file per event or marker, assembled at
render time, instead of shared `hub_data_v2.json` and `change_events.json` —
beginning with the migration plan and its negative controls, and posting it for
cross-workstream objection before migrating.

Raised by: the Workbench workstream. Launchpad and core platform own the
surfaces this would touch, and the request is that they object here before any
migration begins.

## 1. The cost, measured

Taken from this repository's own history rather than from recollection: the last
40 revisions of `data/hub_data_v2.json`, comparing each consecutive pair.

| Top-level key | Changed in |
|---|---|
| `tickets` | 31 of 39 pairs |
| `waves` | 31 |
| `meta` | 31 |
| `change_paths` | 31 |
| `sources` | 30 |
| `impact_policy` | 12 |
| `authority_source_checks` | 6 |

A typical `tickets` change touches **36 of 73 tickets**, and some touch all 73.
Across those 1,185 touched tickets, the only field that ever differs is
`repo_links`. In `meta`, the fields that move are `captured_at_utc` (31 of 39)
and `authority_snapshot_commit` (30 of 39).

`repo_links` entries are GitHub permalinks with a commit embedded in the path:

```
https://github.com/carbonphysicsai/Carbon/blob/<commit>/.agent/tickets/A-1_orientation.md
```

So the dominant churn is not authoring. It is the **authority repin**: one PR
advances `authority_snapshot_commit` and rewrites the embedded commit across
roughly half the tickets. Two Hub-touching PRs therefore conflict in dozens of
places regardless of what either one meant to change. That is the mechanism
behind "#257 invalidated four times for a one-constant change": the constant was
not the problem.

## 2. What was proved about loss

Reproduced in an isolated clone carrying this repository's real 235-event ledger
and real tools. Two branches each append one event, then merge.

**Finding 1 — git does not present the two events as two blocks.** It
interleaves them field by field inside a single object, producing two conflict
hunks: one over the header fields, one over `affects`. The resolver is not
choosing between two records. They are choosing, line by line, inside one.

**Finding 2 — keeping one side destroys the other, and CI's protection depends
on where the lost event already lived.** `validate_hub.py` compares the ledger
against `diff_base_sha`, the PR base:

| Case | `removed` reported | Outcome |
|---|---|---|
| The lost event had already merged to main | `['WS-B-EVENT-01']` | **caught** |
| The lost event was a sibling PR's, not yet in main | `none` | **not caught** |

The second row is the common case and the one every cited incident sits in —
#252, #257, #265 against #264, #266, #278, and Launchpad's four retargets are
all sibling branches. An event that never reached main was never in the base, so
nothing notices it is gone.

**Finding 3 — a mechanical hunk-wise resolution destroyed both events.** Taking
the first hunk from one side and the second from the other produced a ledger
containing *neither* new event. It parsed as valid JSON, and the immutability
comparison reported nothing: no removals, because neither event was in the base,
and no additions, because both were gone.

Together: the ledger's semantics are per-event, git's are per-line, and the only
thing bridging them is an author noticing. The checks that exist are real but
face main, not the sibling.

## 3. What the proposed shape fixes, verified

The same two branches, with the ledger split into one file per event under
`data/events/<event_id>.json`:

```
$ git merge split-b
 docs/.../data/events/WS-B-EVENT-01.json | 14 ++++++++++++++
 1 file changed, 14 insertions(+)
both events present: 2
```

No conflict, no resolution, both events retained. The loss mode in §2 is not
mitigated, it is **absent**: there is no conflict for an author to resolve
wrongly, because two new files are not a contested region.

What this does **not** claim: an author can still delete a file. That remains a
visible deletion in the diff and is caught by the same base-relative comparison
that exists today, with the same sibling-branch limitation. The change closes
the *merge* path, which is where every cited incident happened.

## 4. What the proposed shape does not fix

**Splitting markers per file does not address the marker collision, and may
worsen it.** The collision is `repo_links` and `authority_snapshot_commit`,
rewritten en masse by a repin. One file per ticket converts a single large
conflict into roughly thirty-six small ones, in the same field, all mechanically
derivable. Thirty-six trivial conflicts are worse than one, because each is an
opportunity to resolve inattentively and none is obviously important.

The fix that addresses the actual cost is to stop storing a derived value per
record. `repo_links` is `{label, path, pin}`, where `pin` is either the current
authority snapshot or a deliberately frozen historical commit — ticket `A-1`
pins `4f84329c`, not the current `fa269bc5`, so the distinction is real and must
be preserved. Store the symbolic pin and resolve the URL at render time, and a
repin changes exactly one value.

That is a larger change than the assignment asked for, it is core's surface, and
it is offered here for objection rather than assumed.

## 5. Proposed migration, in bounded stages

Each stage is independently shippable and independently revertible.

**Stage 1 — the ledger.** `change_events.json` becomes
`data/events/<event_id>.json`, assembled at render time in a deterministic
order. This is where loss happens and where the fix is total.

**Stage 2 — the repin.** `repo_links` carries a symbolic pin resolved at render
time; `authority_snapshot_commit` stays the single stored value. Only after
core has accepted the approach.

**Stage 3 — per-marker files,** if Stage 2 lands and the remaining churn still
justifies it. Explicitly conditional: after Stage 2 the measured churn may not
support Stage 3 at all, and doing it anyway would be doing the work the
measurement no longer asks for.

### Order, which the split forces into the open

**Settled: authored `recorded_at` with `event_id` as tiebreak**, on core
platform's argument, which is better than either option below. Commit-date
ordering would make the render a function of git history, so a shallow
checkout, an export or an archive would render a *different document* — which
would quietly break the byte-identical control this very migration is proved
safe by. Order stays a function of content.

Order is array position today. Once the array is gone it has to come from the
data, and an author-assigned integer reintroduces exactly the collision being
removed — in the verification above, both branches independently assigned
`ledger_sequence: 236`. Two candidates, both needing a decision:

- an authored `recorded_at` date with `event_id` as tiebreak; or
- the commit date of the commit that introduced the file, making order a
  property of history rather than of the record.

The second needs no new field and cannot collide, but it makes rendering depend
on git history, which a shallow checkout does not have.

### Negative controls, required before Stage 1 merges

1. **Loss is possible now** — the §2 reproduction, kept as a test.
2. **Loss is impossible after** — two independently added events merge with no
   conflict, asserted rather than observed once.
3. **Meaning is unchanged** — `render_hub.py` output is **byte-identical**
   before and after the migration. If a rendered page differs, the migration
   changed what the Hub says, and the migration is wrong.
3a. **For Stage 2, added by core platform: the rendered URL set is
   byte-identical.** On current main, 73 tickets carry 362 `repo_links` with
   exactly two distinct pins — 202 deliberately frozen, 127 the current
   snapshot — and **33 links with no blob pin at all**, being `pull/`, `issues/`
   and `actions/` URLs. A `{label, path, pin}` schema applied uniformly would
   either mangle those or invent pins for them, and URL-set equality catches it
   automatically where a schema assertion would not.
4. **Removal still fails** — deleting an event file fails validation exactly as
   removing an array entry does today.
5. **Every event survives the migration** — the set of event ids before equals
   the set after, compared as sets, not counted.

Control 3 is the one that matters most: it is the difference between moving the
source and editing it.

## 6. What this proposal cost to write, which is the same problem

The reproduction script lives at `docs/development/hub_source_shape_reproduction.py`
and the classifier scores it `RUNTIME_FULL` under "unknown path fails closed".
`#260` taught the classifier about top-level `docs/development/*.md`; it knows
nothing about a `.py` file there. So a read-only script that touches no runtime
pays a full Canonical run every time it changes.

Moving it does not help. `docs/development/carbon_hub/tools/` — where it would
most naturally live, beside the tools it exercises — is itself `RUNTIME_FULL` by
an explicit rule, so the Hub's own validator and renderer already pay the same
price. And `classify_changes.py` is digest-pinned by
`OWNER-CW1-DEVELOPMENT-CI-01`, so narrowing this is not a change this workstream
can make.

Recorded because it is the same class of cost as the one this document is about:
a rule that was correct when written, applied to a file shape nobody had then,
with the expense landing on whoever happens to touch it. The decision of whether
a documentation-directory script should be classified as runtime belongs to the
owner and core platform, not here.

## 7. Available now, independent of any restructure

The sibling-branch hole in §2 can be closed without moving a single file:
compare the ledger against **both merge parents** rather than only the PR base.
A candidate that merged a sibling branch and lost its events would fail, today,
under the current shape. It is a smaller change than the restructure, it is
core's file, and it is worth doing whether or not the restructure proceeds.

## 8. What is being asked

Launchpad and core platform, please object to any of these before migration:

1. Stage 1's shape — one file per event, `<event_id>.json`, assembled at render.
2. The ordering decision, which is genuinely open.
3. The §4 claim that per-marker files do not fix the marker collision, and the
   Stage 2 alternative, which is core's surface.
4. The §6 both-parents comparison, which is the cheap guard available now.

Silence is not agreement; this is posted for objection and will wait for it.
Nothing in this document authorises a migration, and no scientific, security,
qualification or deployment authority is created or implied.
