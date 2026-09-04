# Hub Update Playbook

## Role of the hub

The hub explains Carbon's development system and routes the team to the authoritative repository record. It must stay useful to a new hire without duplicating PR-level detail.

## Update the hub when

- the active wave changes;
- a wave closes or becomes blocked;
- the selected ticket changes;
- a ticket changes status;
- a dependency or accountable owner changes;
- a material decision changes the map placement or downstream route;
- a new PR, contract, or evidence record becomes the primary detail link;
- a new recurring change path needs orientation coverage.

## Keep out of the hub

- code diffs;
- full decision rationale;
- test logs;
- review threads;
- exact wire schemas;
- long defect histories;
- unverified maturity claims.

Link those records instead.

## Authority snapshot and build procedure

1. Read `.agent/WAVE.md` and the active wave board.
2. Ensure the mapped authority, ticket, decision, or evidence change exists in
   a committed authority snapshot. This is commit `A` in the two-commit model.
3. Set `meta.authority_snapshot_commit` to `A`; keep
   `meta.hub_build_commit` null in source because a commit cannot record its own
   identity without a self-reference problem.
4. Reconcile ticket statuses, dependencies, maturity states, primary links,
   `current.controlling_board_fingerprint`, and the exact marker assertions in
   `authority_source_checks`. Each asserted path must be linked at `A`, and its
   markers must exist both at `A` and candidate `HEAD`.
5. Update `data/hub_data_v2.json` and append a concise record to
   `data/change_events.json` when a material map trigger applies.
6. Commit the Hub source and generated outputs as commit `H`, after `A`. All
   current-role source, active-wave, selected-ticket, and new-event links use
   `A`; immutable historical wave, ticket, and event links keep the exact
   ancestor snapshot they originally recorded. Diff/event coverage uses the
   independent PR or push comparison base supplied as `HUB_DIFF_BASE_SHA`.
7. Run `python tools/render_hub.py`. The renderer compares complete bytes and
   writes only outputs whose rendered content changed.
8. Run `python tools/render_hub.py --check`.
9. Run `python tools/validate_hub.py --repo-root ../../..` from this directory,
   or pass the repository root explicitly.
10. Run `node tools/test_routes.js` and `python tools/browser_smoke_test.py`.
11. Inspect desktop and narrow/mobile layouts and record the explicit authority
    snapshot and capture time in source.

Current authority snapshot: `c9c7f519f1357a8d33d568c5ecbf339a6771785c`, reconciled 2026-09-04T21:59:13Z.

The current long-horizon dependency graph is intentionally not fully linear:
Wave D feeds the launch-critical D → H → I branch, while E, F, and G are
independent post-D lanes with no successor edge into H or I. Do not restore a
linear D → E → F → G → H chain when regenerating the Hub.

### Link-pin and dependency conventions

- Repin `sources`, the active wave, the selected ticket, and every link used by
  an `authority_source_checks` assertion to the current authority snapshot.
  Preserve frozen former-wave, former-selection, historical-ticket, and prior-
  event blob links at their immutable ancestor snapshots. Changing one valid
  historical ancestor pin to another is itself semantic; advancing the current
  snapshot while an unchanged former-current link stays frozen is not.
- In a board `Depends on` cell, split clauses at semicolons. A clause containing
  `non-blocking` contributes context but no dependency IDs; every other clause
  contributes its ticket IDs. The selected ticket's own `Depends on` field
  mirrors the board's leading direct-dependency clause, while later blocking
  clauses may record phase gates such as a runtime prerequisite.
- Generated-output fan-out follows rendered meaning. Update the overview,
  affected wave/ticket pages, and required indexes or routes whose bytes truly
  change. Do not rewrite unrelated explainers, and do not impose a numeric cap
  that could hide a legitimate cross-cutting update.

## Repository-path impact classes

- `map_structural` changes orientation-bearing selection, status, dependency,
  ownership, maturity, boundary, route, or primary-link meaning. They require a
  semantic Hub update and a new immutable event. A ticket title, purpose,
  status, dependency, owner/reviewer route, authority/boundary, or primary
  contract/plan/evidence link change is structurally escalated even though
  routine ticket body detail defaults to `mapped_detail`.
- `mapped_detail` changes have an explicit owner but do not automatically change
  orientation meaning. A specific `HUB_IMPACT_NONE` is valid for routine
  implementation, plan, or evidence detail when the mapped meaning remains
  unchanged.
- `unmapped_authority` changes fail until `data/hub_data_v2.json` records an
  explicit bounded path owner. They never fall back to the active wave.

## Event attachment schema

```yaml
map_ref: WAVE-B/B-04
event_type: decision | adjustment | bug | blocker | risk | evidence
event_id: B-04-D11
owner_lane: sciml_technical_lead
status: proposed | active | blocked | implemented | superseded | closed
summary: One sentence that tells the team what changed.
primary_detail: Repository path or URL
affects:
- WAVE-B/B-05
supersedes: null

```

## Source precedence

```text
scientific constitution
-> normative protocol and domain specifications
-> build and agentic development plan
-> implementation and test evidence

business constitution
-> commercial operating system
```

The hub summarizes those sources. It does not override them.

## Publication rule

Publish the whole `docs/development/carbon_hub/` directory. The primary page
is complete without JavaScript or remote resources. Manual GitHub Pages
publication is available to authorized repository maintainers. The workflow
does not itself enforce owner approval. If desired, a required reviewer on the
`github-pages` environment is a separate human-controlled repository setting.
Automatic publication remains disabled unless `CARBON_HUB_PUBLISH=true`.
This integration neither enables Pages nor changes repository settings.
Future internal-only material belongs on an access-controlled static host and
never in this public-safe source set.

## Content-model reference

See `orientation/HUB_CONTENT_MODEL.md` for required fields and the event attachment model.
