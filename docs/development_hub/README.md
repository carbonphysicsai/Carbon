# Carbon Development Hub v2

This directory is Carbon's orientation and protocol-change navigation layer.

Open **`index.html`** first. It contains the complete hub and remains readable when a preview blocks JavaScript.

## Included

- New to Carbon orientation;
- full Wave A-N what-and-why map;
- explainers for captured Wave A and Wave B tickets;
- protocol-change routes for new Challenges, model architecture, miner priors, reference and measurement changes, protocol changes, defects, and commercial/private modes;
- map-level change event registry;
- maturity ladder and authority map;
- source JSON, renderer, validators, and maintenance playbook.

## Authority boundary

The hub explains what, why, where, status, and dependency. The repository owns how, exact semantics, code, decisions, tests, review, evidence, and authority.

## Source snapshot

- Repository: https://github.com/carbonphysicsai/Carbon
- Branch: `main`
- Commit reconciled: `b86daa5d8b0f8b3e86bb82c2661f405747a200df`
- Captured: 2026-08-31T15:15:20Z
- Current wave: B
- Current ticket: B-03

## Required development use

Read `AGENTS.md` in this directory, `orientation/AGENT_MAINTENANCE_CONTRACT.md`, and the repository root instructions. Material ticket work must place itself in the hub, update map-visible state and links, append a concise change event, regenerate outputs, and pass validation before merge.

Repository wiring and publication notes live in `orientation/REPOSITORY_INTEGRATION.md`.

## Update path

1. Read `.agent/WAVE.md`, the active wave board, and the active ticket.
2. Edit `data/hub_data_v2.json` and `data/change_events.json`.
3. Run `python tools/render_hub.py`.
4. Run `python tools/validate_hub.py --repo-root ../../..` from this directory, or pass the repository root explicitly.
5. Run `python tools/check_change_coverage.py --repo-root ../../.. --base <base> --head <head>` in PR validation.
