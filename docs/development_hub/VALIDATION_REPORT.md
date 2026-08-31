# Carbon Development Hub v2.1 Validation Report

## Blank-page diagnosis

The original `index.html` rendered every view into an empty content shell with one inline JavaScript application. Browsers that executed the script showed the hub. File previews and security layers that suppressed inline scripts showed a blank page.

## Repair

The primary `index.html` now contains the complete orientation hub as ordinary HTML:

- New to Carbon orientation;
- the Wave A through Wave N map;
- all 39 captured Wave A and Wave B ticket explainers;
- protocol-change routes;
- the map-level change log;
- the maturity ladder;
- the glossary;
- repository source links.

The primary file contains no script tag and makes no network request. `interactive.html` preserves the optional client-side application, but no core content depends on it.

## Snapshot check

- Repository branch checked: `main`
- Reconciled head: `b86daa5d8b0f8b3e86bb82c2661f405747a200df`
- Reconciled merge: PR #67, B-03 generator runtime contract
- Captured repository time: `2026-08-31T15:15:20Z`
- Captured active state: Wave B, B-03 `in_progress`

## Content checks

- 14 wave explainers: Wave A through Wave N
- 39 ticket explainers: all captured Wave A and Wave B tickets
- 7 protocol-change routes
- 8 independent maturity states
- 11 glossary entries
- 2 initial map-level events

## Technical checks

- `hub_data_v2.json`: parsed
- `change_events.json`: parsed and schema-checked
- `hub_index_v2.yaml`: generated and structurally checked
- generated outputs: current under `render_hub.py --check`
- internal HTML links: checked
- internal Markdown links: checked
- duplicate wave, ticket, and event IDs: none
- missing explainer files: none
- primary `index.html`: 209,523 bytes and 83,039 source-visible text characters
- primary `index.html` script tags: zero
- JavaScript route smoke test: 13 routes passed for the optional app
- Chromium with JavaScript enabled: 22,972 visible characters in the primary view
- Chromium with JavaScript disabled: the same 22,972 visible characters
- optional interactive view: 4,229 visible characters with no page error

## Repository enforcement checks

The repository payload adds:

- root agent instructions requiring map placement and upkeep;
- an executor ticket-loop checkpoint;
- scoped hub maintenance instructions;
- a generated-output drift check;
- current wave, selected ticket, active-board status, and ticket-source alignment checks;
- pull-request change coverage for wave, ticket, implementation, decision, plan, specification, evidence, and test changes.

A simulated active-board status change without a matching hub update caused the validator to fail, which confirms the intended drift guard.

## Boundary

These checks establish rendering resilience, navigation integrity, source-data consistency, and development-process enforcement. They do not qualify protocol implementation, scientific evidence, security, network behavior, commercial readiness, LIVE status, or production operation.
