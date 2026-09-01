# Hub Content Model

## Purpose

The Carbon Development Hub gives a new hire enough context to place work before opening implementation detail. It also gives the team one navigation surface for decisions, protocol changes, defects, blockers, and evidence.

## Three layers

### 1. Orientation

The hub explains:

- what Carbon is building;
- why each wave exists;
- what each ticket contributes;
- where a change belongs;
- current status and dependencies;
- which repository record holds the detail.

### 2. Working context

The hub links decisions, owners, affected nodes, maturity, blockers, primary PRs, and evidence. It keeps summaries short enough to scan.

### 3. Repository authority

The repository owns exact semantics, source code, migration behavior, tests, reviews, merge identity, and evidence. A hub summary cannot activate work or change scientific authority.

## Core records

### Wave

Required fields:

- ID and title;
- status;
- one-line purpose;
- what it is;
- why Carbon needs it;
- success condition;
- what it unlocks;
- authority ceiling;
- key objects;
- ticket list;
- source links.

### Ticket

Required fields:

- ID, wave, title, and status;
- one-line purpose;
- why it exists;
- system contribution;
- dependencies and downstream tickets;
- driver and review route;
- master questions;
- current stage;
- authority ceiling;
- ticket, contract, PR, decision, and evidence links.

### Change route

Required fields:

- change class;
- starting question;
- likely waves;
- current ticket anchors;
- decisions that must be named;
- human-reserved inputs;
- repository handoff;
- authority warning.

### Event attachment

Use an event record when a decision, adjustment, defect, blocker, risk, or evidence update needs a stable hub location.

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

## Freshness rule

Every published hub version records a repository commit and capture time. Readers should treat the hub as a snapshot. The current wave register and controlling board resolve any disagreement.

## Source and generation rule

Editable records are `data/hub_data_v2.json`, `data/change_events.json`, and
the event template. The HTML pages, compact Markdown map, YAML index, package
README, Start Here guide, change-routing guide, glossary, and wave/ticket
explainers are generated and must not be hand-edited.

Every wave, ticket, route, and event has a stable ID. Every event has exactly
one primary `map_ref`; other nodes belong in `affects`. Preserve historical
events and use `supersedes` for a prospective correction.

## Editing rule

Update the hub after the repository changes purpose, placement, status,
dependency, owner/reviewer routing, boundary, maturity, recurring change route,
material risk/evidence interpretation, or primary links. Keep design rationale,
code, tests, and review history in the repository.
