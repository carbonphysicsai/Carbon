# Hub Update Playbook

## Role of the hub

The Carbon Development Hub gives a new hire enough context to understand the development system and gives the team one place to locate protocol work. It explains what Carbon is changing, why the change belongs there, which work depends on it, and where the repository keeps the detail.

The hub remains an orientation and navigation layer. It does not activate tickets, define protocol truth, or qualify science.

## Update the hub when

- the active wave changes;
- a wave closes, opens, or becomes blocked;
- the selected ticket changes;
- a ticket changes status, scope, owner, reviewer, dependency, or downstream route;
- a new Challenge, model architecture, miner prior, reference path, measurement, protocol contract, commercial mode, or recurring implementation pattern enters the plan;
- a material decision changes map placement or downstream impact;
- a bug, blocker, risk, or evidence result needs a stable map location;
- a new PR, contract, decision, or evidence record becomes the primary detail link.

## Keep out of the hub

- code diffs;
- full decision rationale;
- exact wire schemas;
- test logs;
- review threads;
- long defect histories;
- unverified maturity claims.

Link those records instead.

## Required ticket cadence

### At ticket start

1. Open the hub and locate the active wave and ticket.
2. Confirm one primary `map_ref`, such as `WAVE-B/B-03`.
3. Confirm the upstream dependencies, downstream consumers, owner lane, and review route.
4. Reconcile the source data when the active board changed.

### During implementation

Append or update a concise record in `data/change_events.json` for each material:

- decision;
- adjustment;
- bug;
- blocker;
- risk;
- evidence update.

The event describes the map-level change in one sentence. The linked repository record carries the detail.

### Before merge

1. Read `.agent/WAVE.md` and the active wave board.
2. Reconcile ticket status, scope, dependencies, owners, and primary links.
3. Update `data/hub_data_v2.json` and `data/change_events.json`.
4. Run `python tools/render_hub.py`.
5. Run `python tools/render_hub.py --check`.
6. Run `python tools/validate_hub.py --repo-root ../../..` from the hub directory.
7. Run `python tools/check_change_coverage.py --repo-root ../../.. --base <base-sha> --head <head-sha>`.
8. Inspect `index.html` with JavaScript disabled or in a restricted preview.

## Static-first publication rule

`index.html` must contain real HTML content. A preview that blocks inline scripts must still show the orientation, current position, waves, tickets, routes, events, maturity ladder, glossary, and sources.

`interactive.html` is optional. Never make it the only route to content.

## Event attachment schema

```yaml
map_ref: WAVE-B/B-03
event_type: decision | adjustment | bug | blocker | risk | evidence
event_id: B-03-D9
owner_lane: sciml_technical_lead
status: proposed | active | blocked | implemented | superseded | closed
date: 2026-08-31
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

## Freshness rule

The hub records the repository commit used for reconciliation. The current wave register and controlling board resolve any disagreement. A stale hub is a maintenance defect and must not be used to select work.
