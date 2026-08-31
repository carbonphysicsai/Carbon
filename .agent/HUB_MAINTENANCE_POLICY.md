# Carbon Development Hub Maintenance Policy

**Status:** OWNER-DIRECTED development-process policy.  
**Scope:** every active Carbon ticket, protocol change, implementation repair, decision, evidence update, and wave transition.  
**Hub location:** `docs/development_hub/`.  
**Authority ceiling:** the hub explains and routes work. It never replaces the Constitution, domain specifications, active wave board, ticket, decision record, pull request, or evidence record.

## Required ticket-loop behavior

At ticket start, the executor must:

1. locate the work's primary hub `map_ref`;
2. compare the hub against `.agent/WAVE.md`, the controlling wave board, the ticket, and its primary specifications;
3. record any pre-existing drift before implementation.

Before merge, the pull request must contain exactly one completed declaration:

```text
HUB_UPDATE_REQUIRED: <map refs and changed hub source paths>
```

or

```text
HUB_IMPACT_NONE: <specific reason the map remains accurate>
```

A wave, ticket, Build Out, or master-plan structural change cannot use `HUB_IMPACT_NONE`.

## Update triggers

Update the hub in the same pull request when work changes any of these map-visible facts:

- active wave, selected ticket, ticket status, or current stage;
- wave or ticket purpose, dependency, owner, reviewer, target, or authority ceiling;
- protocol object ownership or cross-wave placement;
- primary contract, decision, issue, pull request, or evidence link;
- routing for a new Challenge, model architecture or family, miner prior, reference path, measurement, product mode, frontier rule, or settlement path;
- a material bug, blocker, risk, adjustment, or superseding decision that changes team understanding;
- a recurring change pattern that needs a new route, glossary term, or onboarding explanation.

When an update is required:

1. edit `docs/development_hub/data/hub_data_v2.json` for structural/current-state changes;
2. append or supersede a concise record in `docs/development_hub/data/change_events.json` for decisions, adjustments, bugs, blockers, risks, and evidence changes;
3. run the renderer and commit generated outputs;
4. run the hub validation and impact checks;
5. keep detailed implementation and evidence in the repository records linked by the hub.

## Required commands

```bash
python docs/development_hub/tools/render_hub.py
python docs/development_hub/tools/render_hub.py --check
python docs/development_hub/tools/validate_hub.py --repo-root .
node docs/development_hub/tools/test_routes.js
```

CI enforces generated-file freshness, structural validation, route coverage, and pull-request impact classification.

## Historical and security rules

Do not erase prior events. Use `supersedes` and preserve the earlier record. Do not place code diffs, long test logs, review threads, or exact wire schemas in the hub. Never add secrets, private keys, seed phrases, passwords, or recovery credentials.
