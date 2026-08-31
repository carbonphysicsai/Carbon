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

## Snapshot procedure

1. Read `.agent/WAVE.md` and the active wave board.
2. Pin the current `main` commit.
3. Reconcile ticket statuses, dependencies, and primary links.
4. Update `data/hub_data_v2.json` and append a concise record to
   `data/change_events.json` when a material map trigger applies.
5. Run `python tools/render_hub.py`.
6. Run `python tools/render_hub.py --check`.
7. Run `python tools/validate_hub.py --repo-root ../../..` from this directory,
   or pass the repository root explicitly.
8. Run `node tools/test_routes.js` and `python tools/browser_smoke_test.py`.
9. Inspect desktop and narrow/mobile layouts and record the explicit snapshot
   commit and capture time in source.

Current snapshot: `b86daa5d8b0f8b3e86bb82c2661f405747a200df`, reconciled 2026-08-31T21:15:10Z.

## Event attachment schema

```yaml
map_ref: WAVE-B/B-03
event_type: decision | adjustment | bug | blocker | risk | evidence
event_id: B-03-D9
owner_lane: sciml_technical_lead
status: proposed | active | blocked | implemented | superseded | closed
summary: One sentence that tells the team what changed.
primary_detail: Repository path or URL
affects:
- WAVE-B/B-04
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
is complete without JavaScript or remote resources. GitHub Pages publication
is public and owner-controlled; automatic deployment remains disabled unless
`CARBON_HUB_PUBLISH=true`. Future internal-only material belongs on an
access-controlled static host and never in this public-safe source set.

## Content-model reference

See `orientation/HUB_CONTENT_MODEL.md` for required fields and the event attachment model.
