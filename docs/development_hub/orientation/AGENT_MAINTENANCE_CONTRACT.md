# Carbon Development Hub Agent Maintenance Contract

**Status:** owner-directed development-process requirement.  
**Scope:** every Carbon executor working under root `AGENTS.md` and `agent_pack/EXECUTION_PROTOCOL.md`.  
**Authority ceiling:** this contract requires orientation upkeep. It does not grant protocol, scientific, security, economic, launch, qualification, or production authority.

## Purpose

The hub is the team's development navigation layer. A new hire should understand what Carbon is building and why. An implementer should be able to place a protocol change, locate the active wave and ticket, and follow links into repository authority.

## Required behavior

At the start of each ticket, the executor must:

1. locate the ticket's primary hub `map_ref`;
2. compare the hub summary with `.agent/WAVE.md`, the controlling wave board, the active ticket, and its primary specifications;
3. note and repair pre-existing map drift in the authorized change path.

During implementation, the executor must add or update a concise map event for each material decision, adjustment, defect, blocker, risk, or evidence result. The event points to the detailed repository record.

Before merge or ticket closeout, the executor must:

1. reconcile active wave, selected ticket, status, placement, purpose, dependencies, boundaries, owners, reviewers, and primary links;
2. update `data/hub_data_v2.json` for structural changes;
3. update `data/change_events.json` for map-level traceability;
4. run `python tools/render_hub.py` and `python tools/render_hub.py --check`;
5. run `python tools/validate_hub.py --repo-root ../../..` from the hub directory;
6. satisfy the repository development-hub CI gate.

## Update triggers

An update is required when work changes:

- the active wave, selected ticket, ticket status, or current stage;
- a ticket dependency, driver, reviewer, target, or authority ceiling;
- protocol object ownership or cross-wave placement;
- a primary contract, PR, decision, issue, or evidence link;
- the route for a new Challenge, model architecture or family, miner prior, reference path, measurement, product mode, frontier rule, or settlement path;
- a material defect, blocker, risk, superseding decision, or evidence result that changes team understanding;
- a recurring implementation pattern that needs a new orientation route or glossary entry.

## Content boundary

The hub contains concise orientation. Keep code, exact schemas, full rationale, review discussion, test logs, and historical evidence in the repository records it links.

Never put secrets, private keys, seed phrases, passwords, recovery credentials, hidden evaluation material, or customer-confidential data in the hub.

## Closeout rule

A ticket cannot claim documentation closeout while its merged state leaves the hub materially stale. Hub drift does not rewrite protocol authority, but agents must repair it before treating the orientation layer as current.
