# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- 14 waves (A-N)
- 42 captured tickets across Wave A and Wave B
- 7 protocol-change routes
- 68 map-level change events
- 8 independent maturity states

## Captured current position

Wave **B**; current ticket: **B-E4**. Last completed: **B-E2** (`done`). Next selected: **none selected**. Wave B remains active in bounded development scope. B-E4 remains selected and in progress. PR #114 merged the disabled real transport, sequential 5-profile x 4-arm x 2-task DEVELOPMENT runner, durable journal, exact request, and 40-slot deterministic Carbon fixture-service integration. The Carbon owner has since approved exactly one non-qualifying DEVELOPMENT campaign under the frozen population, tasks, six-field egress, standard-retention alternative, evidence role, stopping rules, and $14.42 provider-charge cap, using one accountable principal for five role-specific decisions rather than five independent qualification ratifiers. The current successor implements a fresh authenticated-owner issuer, exact successor request, one journal-bound entitlement, safe restart, expiry/revocation/project/source/limit checks, real partial/stopped reports, and conservative unknown-billing reservations. The active workspace authenticated a different GitHub principal and had no provider key or project, so it issued no capability, dispatched no provider request, and incurred no charge. No calibration, shadow, attack, or qualifying campaign ran; v4 remains STILL_BLOCKED, no later ticket is selected, and B-GATE remains unstarted.

## Maintain

Read `orientation/AGENT_MAINTENANCE_CONTRACT.md`. Semantic map updates use
`data/hub_data_v2.json` and `data/change_events.json`; the event template,
renderer, and interactive template are maintained sources for their respective
schema or presentation behavior. Never hand-edit generated outputs. Then run:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/test_newcomer.py
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
```

The hub explains and routes; repository authority controls implementation and evidence. Manual Pages publication is available to authorized maintainers, but the workflow does not itself enforce owner approval. A required reviewer on the `github-pages` environment, if desired, is a separate human-controlled repository setting. Pages is public when enabled; this integration does not enable it or change settings.
