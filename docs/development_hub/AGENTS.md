# Carbon Development Hub agent instructions

This directory is Carbon's required orientation and map-maintenance surface. It explains **what**, **why**, **where**, **status**, and **dependency**. It does not replace repository authority.

## Read before editing

1. repository-root `AGENTS.md`;
2. `CONSTITUTION.md`;
3. `.agent/WAVE.md`;
4. the active wave board and ticket;
5. `orientation/HUB_CONTENT_MODEL.md`;
6. `orientation/HUB_UPDATE_PLAYBOOK.md`;
7. `orientation/AGENT_MAINTENANCE_CONTRACT.md`.

## Source and generated files

Edit these sources:

- `data/hub_data_v2.json` for waves, tickets, routing, maturity, glossary, current state, dependencies, and primary links;
- `data/change_events.json` for concise decisions, adjustments, bugs, blockers, risks, and evidence updates;
- `orientation/*.md` when the onboarding or maintenance model changes.

Do not hand-edit generated wave explainers, ticket explainers, `Carbon_Development_Hub_v2.md`, `data/hub_index_v2.yaml`, or `index.html`. Run the renderer.

`interactive.html` is optional and may use JavaScript. `index.html` must remain static-first and useful when scripts are blocked.

## Required update points

At ticket start:

- confirm the work's primary `map_ref`;
- confirm the owning wave, ticket, dependencies, and review route;
- update the map when the board or ticket definition changed.

During work:

- add or update one concise event for every material decision, adjustment, bug, blocker, risk, or evidence change;
- link the event to the ticket, decision, PR, contract, or evidence record that holds the detail;
- list affected nodes without assigning multiple primary locations.

Before merge:

- reconcile current wave and ticket status against `.agent/WAVE.md` and the active board;
- update dependencies, owners, maturity language, and primary links where changed;
- preserve historical events and use `supersedes` rather than rewriting prior history;
- run `python tools/render_hub.py`;
- run `python tools/render_hub.py --check`;
- run `python tools/validate_hub.py --repo-root ../../..` from this directory;
- run the repository change-coverage check used by CI.

## Content boundary

Keep the hub high level. Put code diffs, wire schemas, test logs, review threads, full decision rationale, and defect history in the repository records the hub links.

Never use the hub to claim `LIVE`, scientific qualification, security qualification, network qualification, commercial validation, or production qualification unless the owning repository evidence grants that exact state.
