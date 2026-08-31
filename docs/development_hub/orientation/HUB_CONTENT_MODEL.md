# Hub Content Model

## Purpose

The Carbon Development Hub gives a new hire enough context to place work before opening implementation detail. It also gives the team one navigation surface for decisions, protocol changes, defects, blockers, risks, and evidence.

## Three layers

### Orientation

The hub explains:

- what Carbon is building;
- why each wave exists;
- what each ticket contributes;
- where a change belongs;
- current status and dependencies;
- which repository record holds the detail.

### Working context

The hub links owners, decisions, affected nodes, maturity, blockers, primary PRs, and evidence. It keeps summaries short enough to scan.

### Repository authority

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
date: 2026-08-31
summary: One sentence that tells the team what changed.
primary_detail: Repository path or URL
affects:
  - WAVE-B/B-04
supersedes: null
```

Every event has one primary `map_ref`. `affects` records other nodes without creating multiple owners. Post-merge corrections use `supersedes`; they do not rewrite history.

## Rendering contract

`data/hub_data_v2.json` and `data/change_events.json` are the generation sources. The renderer creates the static index, Markdown map, YAML index, and wave and ticket explainers.

`index.html` must expose its core content without JavaScript. Optional interaction may enhance navigation but cannot own the content.

## Freshness rule

Every published hub version records the repository commit and capture time used for reconciliation. Readers should treat the hub as a maintained orientation view. The current wave register and controlling board resolve disagreement.

## Editing rule

Update the hub after the repository changes placement, status, dependency, owner, maturity, or primary links. Add concise events for material decisions, bugs, blockers, risks, adjustments, and evidence. Keep design rationale, code, tests, and review history in the repository.
